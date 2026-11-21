import uuid
from pathlib import Path
from typing import Protocol

from qdrant_client import QdrantClient, models

from personal_vault.models import Chunk, Hit, PersonalVaultError, note_name

PAGE = 1000
DELETE_BATCH = 100


class Store(Protocol):
    def exists(self) -> bool: ...

    def reset(self, dimension: int) -> None: ...

    def file_hashes(self) -> dict[str, str]: ...

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...

    def delete_paths(self, paths: list[str]) -> None: ...

    def move_path(self, old: str, new: str) -> None: ...

    def search(self, vector: list[float], limit: int) -> list[Hit]: ...

    def search_linked(self, vector: list[float], limit: int, hits: list[Hit]) -> list[Hit]: ...

    def count(self) -> int: ...

    def drop(self) -> None: ...


def point_id(path: str, index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{path}#{index}"))


class QdrantStore:
    def __init__(self, client: QdrantClient, collection: str):
        self.client = client
        self.collection = collection

    @classmethod
    def open(cls, collection: str, url: str, folder: Path) -> "QdrantStore":
        if url:
            client = QdrantClient(url=url)
            try:
                client.get_collections()
            except Exception as error:
                raise PersonalVaultError(
                    f"cannot reach Qdrant at {url} ({type(error).__name__}). Start it, or index without store= "
                    "to use the embedded store"
                ) from error
            return cls(client, collection)
        folder.mkdir(parents=True, exist_ok=True)
        try:
            client = QdrantClient(path=str(folder))
        except RuntimeError as error:
            raise PersonalVaultError(f"the index is in use by another personal-vault process: {error}") from error
        return cls(client, collection)

    def exists(self) -> bool:
        return self.client.collection_exists(self.collection)

    def reset(self, dimension: int) -> None:
        if self.exists():
            self.client.delete_collection(self.collection)
        self.client.create_collection(
            self.collection,
            vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
        )

    def file_hashes(self) -> dict[str, str]:
        hashes = {}
        for point in self._scroll(None, with_vectors=False):
            hashes[point.payload["path"]] = point.payload["file_hash"]
        return hashes

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        points = [
            models.PointStruct(
                id=point_id(chunk.path, chunk.index),
                vector=vector,
                payload={
                    "path": chunk.path,
                    "name": note_name(chunk.path),
                    "links": chunk.links,
                    "index": chunk.index,
                    "line": chunk.line,
                    "heading": chunk.heading,
                    "text": chunk.text,
                    "file_hash": chunk.file_hash,
                },
            )
            for chunk, vector in zip(chunks, vectors)
        ]
        self.client.upsert(self.collection, points=points)

    def delete_paths(self, paths: list[str]) -> None:
        for start in range(0, len(paths), DELETE_BATCH):
            batch = paths[start:start + DELETE_BATCH]
            self.client.delete(
                self.collection,
                points_selector=models.FilterSelector(filter=_path_filter(models.MatchAny(any=batch))),
            )

    def move_path(self, old: str, new: str) -> None:
        points = self._scroll(_path_filter(models.MatchValue(value=old)), with_vectors=True)
        moved = [
            models.PointStruct(
                id=point_id(new, point.payload["index"]),
                vector=point.vector,
                payload={**point.payload, "path": new, "name": note_name(new)},
            )
            for point in points
        ]
        if moved:
            self.client.upsert(self.collection, points=moved)
        self.delete_paths([old])

    def search(self, vector: list[float], limit: int) -> list[Hit]:
        return self._query(vector, limit, None)

    def search_linked(self, vector: list[float], limit: int, hits: list[Hit]) -> list[Hit]:
        # ponytail: unindexed payload filter; in server mode add keyword indexes on name and links if this gets slow
        linked_from_hits = sorted({name for hit in hits for name in hit.links})
        hit_names = sorted({note_name(hit.path) for hit in hits})
        if not hits or limit <= 0:
            return []
        conditions = [models.FieldCondition(key="links", match=models.MatchAny(any=hit_names))]
        if linked_from_hits:
            conditions.append(models.FieldCondition(key="name", match=models.MatchAny(any=linked_from_hits)))
        already_found = models.HasIdCondition(has_id=[point_id(hit.path, hit.index) for hit in hits])
        return self._query(vector, limit, models.Filter(should=conditions, must_not=[already_found]))

    def _query(self, vector: list[float], limit: int, query_filter: models.Filter | None) -> list[Hit]:
        result = self.client.query_points(
            self.collection, query=vector, query_filter=query_filter, limit=limit, with_payload=True
        )
        return [
            Hit(
                path=point.payload["path"],
                line=point.payload["line"],
                heading=point.payload["heading"],
                text=point.payload["text"],
                score=point.score,
                index=point.payload["index"],
                links=point.payload.get("links", []),
            )
            for point in result.points
        ]

    def count(self) -> int:
        return self.client.count(self.collection).count

    def drop(self) -> None:
        if self.exists():
            self.client.delete_collection(self.collection)

    def _scroll(self, query_filter: models.Filter | None, with_vectors: bool) -> list[models.Record]:
        records = []
        offset = None
        while True:
            page, offset = self.client.scroll(
                self.collection,
                scroll_filter=query_filter,
                limit=PAGE,
                offset=offset,
                with_payload=True,
                with_vectors=with_vectors,
            )
            records.extend(page)
            if offset is None:
                return records


def _path_filter(match: models.MatchValue | models.MatchAny) -> models.Filter:
    return models.Filter(must=[models.FieldCondition(key="path", match=match)])
