"""Splits knowledge base articles into sections for AI retrieval.

Articles are Markdown, so they're split at headings (ignoring `#` lines inside
code fences). A section longer than `MAX_CHUNK_CHARS` is split further at
paragraph breaks. Every chunk carries its heading trail ("Article > Section >
Subsection") so it still makes sense when it's the only part of the article a
request sees.
"""

import re
from dataclasses import dataclass

MAX_CHUNK_CHARS = 3_000

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class ArticleChunk:
    heading: str
    content: str


def split_article(title: str, body: str) -> list[ArticleChunk]:
    chunks: list[ArticleChunk] = []
    trail: list[tuple[int, str]] = []
    lines: list[str] = []
    in_fence = False

    def flush() -> None:
        content = "\n".join(lines).strip()
        lines.clear()
        if not content:
            return
        heading = " > ".join([title, *(text for _, text in trail)])
        chunks.extend(ArticleChunk(heading, piece) for piece in _pieces(content))

    for line in body.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        match = None if in_fence else _HEADING.match(line)
        if match is None:
            lines.append(line)
            continue
        flush()
        level = len(match.group(1))
        trail = [(lvl, text) for lvl, text in trail if lvl < level]
        trail.append((level, match.group(2)))
    flush()

    # An article without body text is still findable by its title.
    return chunks or [ArticleChunk(title, title)]


def _pieces(content: str) -> list[str]:
    if len(content) <= MAX_CHUNK_CHARS:
        return [content]
    pieces: list[str] = []
    current = ""
    for paragraph in _PARAGRAPH_BREAK.split(content):
        while len(paragraph) > MAX_CHUNK_CHARS:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(paragraph[:MAX_CHUNK_CHARS])
            paragraph = paragraph[MAX_CHUNK_CHARS:]
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > MAX_CHUNK_CHARS:
            pieces.append(current)
            current = paragraph
        else:
            current = candidate
    if current.strip():
        pieces.append(current)
    return pieces
