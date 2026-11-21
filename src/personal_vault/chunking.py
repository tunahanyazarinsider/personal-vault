import re

from personal_vault.models import Chunk

CHUNKER_VERSION = 1
MAX_CHARS = 1500
HEADING = re.compile(r"^(#{1,6})\s+(.+)")


def chunk_markdown(text: str, path: str, file_hash: str) -> list[Chunk]:
    chunks = []
    for heading, lines in _sections(text):
        for line, body in _pack(lines):
            chunks.append(
                Chunk(path=path, index=len(chunks), line=line, heading=heading, text=body, file_hash=file_hash)
            )
    return chunks


def _sections(text: str) -> list[tuple[str, list[tuple[int, str]]]]:
    sections = []
    trail: list[tuple[int, str]] = []
    lines: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else HEADING.match(line)
        if match is None:
            lines.append((number, line))
            continue
        sections.append((_heading_path(trail), lines))
        level = len(match.group(1))
        while trail and trail[-1][0] >= level:
            trail.pop()
        trail.append((level, match.group(2).strip()))
        lines = []
    sections.append((_heading_path(trail), lines))
    return sections


def _heading_path(trail: list[tuple[int, str]]) -> str:
    return " > ".join(title for _, title in trail)


def _pack(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    # ponytail: cuts at line boundaries, and mid-line past MAX_CHARS; use a sentence
    # splitter if answers that straddle a cut are missed
    packed: list[tuple[int, str]] = []
    buffer: list[str] = []
    size = 0
    first_line = 0
    for number, line in lines:
        pieces = [line[start:start + MAX_CHARS] for start in range(0, len(line), MAX_CHARS)] or [""]
        for piece in pieces:
            if not buffer and not piece.strip():
                continue
            if buffer and size + len(piece) > MAX_CHARS:
                _flush(packed, first_line, buffer)
                buffer = []
                size = 0
            if not buffer:
                first_line = number
            buffer.append(piece)
            size += len(piece) + 1
    _flush(packed, first_line, buffer)
    return packed


def _flush(packed: list[tuple[int, str]], first_line: int, buffer: list[str]) -> None:
    body = "\n".join(buffer).strip()
    if body:
        packed.append((first_line, body))
