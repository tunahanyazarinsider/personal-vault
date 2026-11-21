from dataclasses import dataclass

from personal_vault.embedders import Embedder
from personal_vault.models import Hit, note_name
from personal_vault.stores import Store

HITS_LIMIT = 16
LINKED_LIMIT = 4


@dataclass
class SearchResult:
    hits: list[Hit]
    linked: list[Hit]


def search(question: str, embedder: Embedder, store: Store, limit: int, linked: int = LINKED_LIMIT) -> SearchResult:
    vector = embedder.embed_query(question)
    hits = store.search(vector, limit)
    return SearchResult(hits=hits, linked=store.search_linked(vector, linked, hits))


def link_sources(linked: Hit, hits: list[Hit]) -> list[str]:
    name = note_name(linked.path)
    sources = []
    for hit in hits:
        if (name in hit.links or note_name(hit.path) in linked.links) and hit.path not in sources:
            sources.append(hit.path)
    return sources
