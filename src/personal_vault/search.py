from personal_vault.embedders import Embedder
from personal_vault.models import Hit
from personal_vault.stores import Store


def search(question: str, embedder: Embedder, store: Store, limit: int) -> list[Hit]:
    return store.search(embedder.embed_query(question), limit)
