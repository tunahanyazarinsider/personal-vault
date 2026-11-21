from dataclasses import dataclass, field
from pathlib import PurePosixPath


class PersonalVaultError(Exception):
    pass


@dataclass
class Chunk:
    path: str
    index: int
    line: int
    heading: str
    text: str
    file_hash: str

    def embedding_text(self) -> str:
        title = PurePosixPath(self.path).stem
        if self.heading:
            title = f"{title} > {self.heading}"
        return f"{title}\n{self.text}"


@dataclass
class Hit:
    path: str
    line: int
    heading: str
    text: str
    score: float


@dataclass
class VaultConfig:
    name: str
    path: str
    host: str
    model: str
    query_prefix: str = ""
    doc_prefix: str = ""
    exclude: list[str] = field(default_factory=list)
    store: str = ""
    signature: str = ""
