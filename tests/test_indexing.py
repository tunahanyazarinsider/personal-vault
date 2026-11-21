import unicodedata

from personal_vault.indexing import index_vault, is_excluded
from personal_vault.loaders import TextLoader

LOADERS = {".md": TextLoader(), ".txt": TextLoader()}


def run(root, embedder, store, exclude=None):
    return index_vault(root, LOADERS, embedder, store, exclude or [])


def paths_in(store):
    return sorted(store.file_hashes())


def test_first_run_indexes_supported_files_only(tmp_path, embedder, store):
    (tmp_path / "sub").mkdir()
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "a.md").write_text("# A\nalpha\n")
    (tmp_path / "sub" / "b.txt").write_text("beta\n")
    (tmp_path / ".obsidian" / "c.md").write_text("hidden\n")
    (tmp_path / "image.png").write_bytes(b"png")
    (tmp_path / "x_şifre.md").write_text("parola: hunter2\n")

    report = run(tmp_path, embedder, store)

    assert paths_in(store) == ["a.md", "sub/b.txt"]
    assert (report.files, report.embedded, report.chunks) == (2, 2, 2)
    assert not any("hunter2" in text for text in embedder.documents)


def test_unchanged_files_are_not_embedded_again(tmp_path, embedder, store):
    (tmp_path / "a.md").write_text("alpha\n")
    run(tmp_path, embedder, store)
    embedder.documents.clear()

    report = run(tmp_path, embedder, store)

    assert embedder.documents == []
    assert (report.unchanged, report.embedded) == (1, 0)


def test_changed_file_replaces_all_old_chunks(tmp_path, embedder, store):
    note = tmp_path / "a.md"
    note.write_text("# One\nfirst\n# Two\nsecond\n# Three\nthird\n")
    run(tmp_path, embedder, store)
    assert store.client.count("test").count == 3

    note.write_text("# One\nonly this\n")
    report = run(tmp_path, embedder, store)

    assert report.embedded == 1
    assert store.client.count("test").count == 1
    assert store.search(embedder.embed_query("x"), 5)[0].text == "only this"


def test_deleted_and_newly_excluded_files_are_removed(tmp_path, embedder, store):
    (tmp_path / "keep.md").write_text("keep\n")
    (tmp_path / "gone.md").write_text("gone\n")
    (tmp_path / "draft.md").write_text("draft\n")
    run(tmp_path, embedder, store)

    (tmp_path / "gone.md").unlink()
    report = run(tmp_path, embedder, store, exclude=["draft*"])

    assert paths_in(store) == ["keep.md"]
    assert report.removed == 2


def test_moved_file_is_not_embedded_again(tmp_path, embedder, store):
    (tmp_path / "old").mkdir()
    (tmp_path / "old" / "note.md").write_text("# A\nalpha\n# B\nbeta\n")
    run(tmp_path, embedder, store)
    embedder.documents.clear()

    (tmp_path / "new").mkdir()
    (tmp_path / "old" / "note.md").rename(tmp_path / "new" / "renamed.md")
    report = run(tmp_path, embedder, store)

    assert embedder.documents == []
    assert (report.moved, report.removed) == (1, 0)
    assert paths_in(store) == ["new/renamed.md"]
    assert store.client.count("test").count == 2


def test_file_without_text_is_counted_as_empty(tmp_path, embedder, store):
    (tmp_path / "blank.md").write_text("# only a heading\n")
    report = run(tmp_path, embedder, store)
    assert (report.empty, report.embedded) == (1, 0)
    assert embedder.documents == []


def test_exclusion_matches_decomposed_names_and_ignores_case():
    decomposed = unicodedata.normalize("NFD", "notes/X_Şifre.md")
    assert is_excluded(decomposed, ["*şifre*"])
    assert is_excluded("a/Prod ES Host.md", ["*prod es host*"])
    assert not is_excluded("6_aws/ec2/ami.md", ["*şifre*", "*secret*"])
