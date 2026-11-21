import hashlib

import pytest
from qdrant_client import QdrantClient

from personal_vault.stores import QdrantStore

DIMENSION = 8


class FakeEmbedder:
    def __init__(self):
        self.documents: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.documents.extend(texts)
        return [_vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return _vector(text)


def _vector(text: str) -> list[float]:
    digest = hashlib.sha1(text.encode()).digest()
    return [byte / 255 + 0.01 for byte in digest[:DIMENSION]]


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def store() -> QdrantStore:
    store = QdrantStore(QdrantClient(location=":memory:"), "test")
    store.reset(DIMENSION)
    return store
