import re
import urllib.parse

from personal_vault.models import Chunk, note_name

CHUNKER_VERSION = 2
MAX_CHARS = 1500
HEADING = re.compile(r"^(#{1,6})\s+(.+)")
WIKILINK = re.compile(r"\[\[([^\[\]]+)\]\]")
MARKDOWN_LINK = re.compile(r"\]\(([^()\s]+\.md)(?:#[^()\s]*)?\)")


def chunk_markdown(text: str, path: str, file_hash: str) -> list[Chunk]:
    chunks = []
    for heading, line, body in _merge(text):
        chunks.append(
            Chunk(
                path=path,
                index=len(chunks),
                line=line,
                heading=heading,
                text=body,
                file_hash=file_hash,
                links=find_links(body),
            )
        )
    return chunks


def find_links(text: str) -> list[str]:
    targets = WIKILINK.findall(text)
    targets += [urllib.parse.unquote(target) for target in MARKDOWN_LINK.findall(text) if "://" not in target]
    names: list[str] = []
    for target in targets:
        name = note_name(target.split("|")[0].split("#")[0].rstrip("\\"))
        if name and name not in names:
            names.append(name)
    return names


def _merge(text: str) -> list[tuple[str, int, str]]:
    # Sections are packed together while they fit in MAX_CHARS; a joined section keeps its heading line
    merged: list[tuple[str, int, str]] = []
    last_heading = ""
    for heading, title, lines in _sections(text):
        for line, body in _pack(lines):
            if merged:
                first_heading, first_line, text_so_far = merged[-1]
                addition = body if heading == last_heading else f"{title}\n{body}"
                if len(text_so_far) + len(addition) + 2 <= MAX_CHARS:
                    merged[-1] = (first_heading, first_line, f"{text_so_far}\n\n{addition}")
                    last_heading = heading
                    continue
            merged.append((heading, line, body))
            last_heading = heading
    return merged


def _sections(text: str) -> list[tuple[str, str, list[tuple[int, str]]]]:
    sections = []
    trail: list[tuple[int, str]] = []
    lines: list[tuple[int, str]] = []
    title = ""
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else HEADING.match(line)
        if match is None:
            lines.append((number, line))
            continue
        sections.append((_heading_path(trail), title, lines))
        level = len(match.group(1))
        while trail and trail[-1][0] >= level:
            trail.pop()
        trail.append((level, match.group(2).strip()))
        title = line.strip()
        lines = []
    sections.append((_heading_path(trail), title, lines))
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
