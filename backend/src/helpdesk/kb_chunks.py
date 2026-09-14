"""Splits knowledge text into sections for AI retrieval.

Markdown (help center articles, .md uploads, text with `#` headings) is split
at headings, ignoring `#` lines inside code fences, and every chunk carries its
heading trail ("Article > Section > Subsection") so it still makes sense on
its own.

Plain text has no such anchors, so it's cut into windows of at most
`MAX_CHUNK_CHARS` that end at the most natural break available - paragraph,
line, sentence, then word - and neighbouring windows overlap by about
`OVERLAP_CHARS`, so a fact straddling a boundary is whole in one of them.
"""

import re
from dataclasses import dataclass

MAX_CHUNK_CHARS = 3_000
OVERLAP_CHARS = 300

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_ANY_HEADING = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_FENCE = re.compile(r"^\s*(```|~~~)")
_WHITESPACE = re.compile(r"\s")
# Cut points, best first.
_BREAKS = ("\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ")


@dataclass(frozen=True)
class TextChunk:
    heading: str
    content: str


def looks_like_markdown(text: str) -> bool:
    """Whether text has Markdown headings worth splitting at."""
    return _ANY_HEADING.search(text) is not None


def split_markdown(title: str, body: str) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    trail: list[tuple[int, str]] = []
    lines: list[str] = []
    in_fence = False

    def flush() -> None:
        content = "\n".join(lines).strip()
        lines.clear()
        if not content:
            return
        heading = " > ".join([title, *(text for _, text in trail)])
        chunks.extend(TextChunk(heading, piece) for piece in _windows(content, 0))

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

    # Text without a body is still findable by its title.
    return chunks or [TextChunk(title, title)]


# Name used by the kb_retrieval migration to chunk existing articles.
split_article = split_markdown


def split_plain_text(title: str, text: str) -> list[TextChunk]:
    pieces = _windows(text.strip(), OVERLAP_CHARS)
    return [TextChunk(title, piece) for piece in pieces] or [TextChunk(title, title)]


def _windows(text: str, overlap: int) -> list[str]:
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = start + MAX_CHUNK_CHARS
        if end >= len(text):
            end = len(text)
        else:
            # Never cut in the first half of a window: pieces stay substantial.
            end = _natural_break(text, start + MAX_CHUNK_CHARS // 2, end)
        if piece := text[start:end].strip():
            pieces.append(piece)
        if end == len(text):
            break
        start = _word_start(text, end - overlap, end) if overlap else end
    return pieces


def _natural_break(text: str, lo: int, hi: int) -> int:
    for separator in _BREAKS:
        index = text.rfind(separator, lo, hi)
        if index != -1:
            return index + len(separator)
    return hi


def _word_start(text: str, position: int, end: int) -> int:
    """Start an overlapping window after whitespace, not mid-word."""
    match = _WHITESPACE.search(text, position, end)
    return match.end() if match else position
