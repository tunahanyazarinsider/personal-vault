from pathlib import Path
from typing import Protocol


class Loader(Protocol):
    extensions: set[str]

    def load(self, path: Path) -> str: ...


class TextLoader:
    extensions = {".md", ".txt"}

    def load(self, path: Path) -> str:
        return path.read_bytes().decode("utf-8", errors="replace")
