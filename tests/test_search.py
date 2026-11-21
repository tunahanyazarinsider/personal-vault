from personal_vault.chunking import chunk_markdown
from personal_vault.search import link_sources, search


def add(store, embedder, path, text):
    chunks = chunk_markdown(text, path, "h")
    store.upsert(chunks, embedder.embed_documents([chunk.text for chunk in chunks]))


def test_linked_holds_notes_the_hit_links_to_and_notes_linking_to_it(embedder, store):
    add(store, embedder, "a/hit.md", "alpha, see [[Target]]\n")
    add(store, embedder, "b/target.md", "target body\n")
    add(store, embedder, "c/back.md", "points at [[hit]]\n")
    add(store, embedder, "d/unrelated.md", "nothing\n")

    found = search("alpha, see [[Target]]", embedder, store, 1)

    assert [hit.path for hit in found.hits] == ["a/hit.md"]
    assert sorted(hit.path for hit in found.linked) == ["b/target.md", "c/back.md"]
    assert link_sources(found.linked[0], found.hits) == ["a/hit.md"]


def test_linked_never_repeats_a_hit_and_can_be_turned_off(embedder, store):
    add(store, embedder, "a.md", "alpha [[b]]\n")
    add(store, embedder, "b.md", "beta [[a]]\n")

    assert search("alpha [[b]]", embedder, store, 2).linked == []
    assert search("alpha [[b]]", embedder, store, 1, linked=0).linked == []


def test_index_without_link_payloads_still_searches(embedder, store):
    add(store, embedder, "a.md", "alpha\n")
    store.client.delete_payload("test", keys=["links", "name"], points=[point.id for point in store.client.scroll("test")[0]])

    found = search("alpha", embedder, store, 1)

    assert [hit.path for hit in found.hits] == ["a.md"]
    assert found.linked == []
