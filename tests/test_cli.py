import pytest

from personal_vault import cli
from personal_vault.config import Registry


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSONAL_VAULT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def register(home, tmp_path, name):
    folder = tmp_path / name
    folder.mkdir()
    registry = Registry.load(home / "config.json")
    registry.prepare(name, str(folder))
    registry.save()
    index = home / "index" / name
    index.mkdir(parents=True)
    (index / "storage.sqlite").write_bytes(b"x" * 2_000_000)
    return folder


def test_vaults_lists_every_vault_and_marks_the_default(home, tmp_path, capsys):
    register(home, tmp_path, "work")
    register(home, tmp_path, "home-notes")
    assert cli.main(["vaults", "--default", "work"]) == 0
    capsys.readouterr()

    assert cli.main(["vaults"]) == 0
    out = capsys.readouterr().out
    assert "work (default)" in out
    assert "home-notes\n" in out
    assert "embedded, 2 MB" in out


def test_single_vault_is_shown_as_default(home, tmp_path, capsys):
    register(home, tmp_path, "only")
    cli.main(["vaults"])
    assert "only (default)" in capsys.readouterr().out


def test_remove_deletes_index_and_registration_but_not_notes(home, tmp_path, capsys):
    notes = register(home, tmp_path, "old")
    (notes / "note.md").write_text("keep me\n")
    cli.main(["vaults", "--default", "old"])

    assert cli.main(["vaults", "--remove", "old"]) == 0

    registry = Registry.load(home / "config.json")
    assert registry.vaults == {}
    assert registry.default is None
    assert not (home / "index" / "old").exists()
    assert (notes / "note.md").read_text() == "keep me\n"


def test_unknown_vault_is_an_error(home, tmp_path, capsys):
    register(home, tmp_path, "work")
    assert cli.main(["vaults", "--remove", "nope"]) == 1
    assert "no vault named 'nope'" in capsys.readouterr().err
    assert (home / "index" / "work").exists()


def test_no_vaults_message(home, capsys):
    cli.main(["vaults"])
    assert "no vaults yet" in capsys.readouterr().out
