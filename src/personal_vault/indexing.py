import fnmatch
import hashlib
import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from personal_vault.chunking import chunk_markdown
from personal_vault.embedders import Embedder
from personal_vault.loaders import Loader
from personal_vault.stores import Store

ALWAYS_EXCLUDED = ["*password*", "*passwd*", "*secret*", "*credential*", "*şifre*", "*sifre*", "*.env*"]


@dataclass
class IndexReport:
    files: int = 0
    embedded: int = 0
    chunks: int = 0
    unchanged: int = 0
    empty: int = 0
    moved: int = 0
    removed: int = 0


def index_vault(
    root: Path,
    loaders: dict[str, Loader],
    embedder: Embedder,
    store: Store,
    exclude: list[str],
    progress: Callable[[int, int], None] | None = None,
) -> IndexReport:
    on_disk = scan(root, set(loaders), ALWAYS_EXCLUDED + exclude)
    known = store.file_hashes()
    gone = {path for path in known if path not in on_disk}
    gone_by_hash = {known[path]: path for path in gone}
    report = IndexReport(files=len(on_disk))

    for done, (path, (file, file_hash)) in enumerate(on_disk.items(), start=1):
        if known.get(path) == file_hash:
            report.unchanged += 1
        elif path not in known and file_hash in gone_by_hash:
            old = gone_by_hash.pop(file_hash)
            gone.discard(old)
            store.move_path(old, path)
            report.moved += 1
        else:
            text = loaders[file.suffix.lower()].load(file)
            chunks = chunk_markdown(text, path, file_hash)
            vectors = embedder.embed_documents([chunk.embedding_text() for chunk in chunks]) if chunks else []
            if path in known:
                store.delete_paths([path])
            if chunks:
                store.upsert(chunks, vectors)
                report.embedded += 1
                report.chunks += len(chunks)
            else:
                report.empty += 1
        if progress is not None:
            progress(done, len(on_disk))

    if gone:
        store.delete_paths(sorted(gone))
    report.removed = len(gone)
    return report


def scan(root: Path, extensions: set[str], patterns: list[str]) -> dict[str, tuple[Path, str]]:
    found = {}
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = sorted(name for name in subdirectories if not name.startswith("."))
        for name in sorted(names):
            file = Path(directory) / name
            # macOS returns decomposed names; without NFC "şifre" never matches a typed pattern
            path = unicodedata.normalize("NFC", file.relative_to(root).as_posix())
            if file.suffix.lower() in extensions and not is_excluded(path, patterns):
                found[path] = (file, hashlib.sha1(file.read_bytes()).hexdigest())
    return found


def is_excluded(path: str, patterns: list[str]) -> bool:
    path = unicodedata.normalize("NFC", path).lower()
    return any(fnmatch.fnmatch(path, unicodedata.normalize("NFC", pattern).lower()) for pattern in patterns)
