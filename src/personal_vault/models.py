import unicodedata
from dataclasses import dataclass, field
from pathlib import PurePosixPath


class PersonalVaultError(Exception):
    pass


def note_name(path: str) -> str:
    # Obsidian resolves [[Note]] by file name alone, so links and notes are matched on this
    name = unicodedata.normalize("NFC", path).strip().rsplit("/", 1)[-1].lower()
    for extension in (".md", ".txt"):
        if name.endswith(extension):
            return name[: -len(extension)]
    return name


@dataclass
class Chunk:
    path: str
    index: int
    line: int
    heading: str
    text: str
    file_hash: str
    links: list[str] = field(default_factory=list)

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
    index: int = 0
    links: list[str] = field(default_factory=list)


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
    chunks: int = 0
    indexed_at: str = ""
