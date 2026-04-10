"""Chunking strategy.

We do markdown-aware splitting first (heading boundaries are real semantic
breaks), then fall back to a fixed window with overlap inside any section
that's still too long. This is a deliberate compromise: cheaper than
embedding-based chunking, much better than naive ``text.split()``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$", re.MULTILINE)


@dataclass(slots=True, frozen=True)
class Chunk:
    ordinal: int
    text: str
    heading: str | None


def chunk_markdown(
    text: str,
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[Chunk]:
    """Split ``text`` into chunks suitable for embedding.

    Args:
        text: source text. Markdown-aware but tolerates plain text.
        chunk_size: target maximum length in characters.
        chunk_overlap: how many trailing characters of one chunk to repeat at
            the start of the next, so context isn't lost across boundaries.

    Returns:
        A list of :class:`Chunk` ordered by appearance.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    text = text.strip()
    if not text:
        return []

    sections = _split_by_headings(text)
    out: list[Chunk] = []
    for heading, body in sections:
        body = body.strip()
        if not body:
            continue
        for piece in _window(body, chunk_size=chunk_size, overlap=chunk_overlap):
            out.append(Chunk(ordinal=len(out), text=piece, heading=heading))
    return out


def _split_by_headings(text: str) -> list[tuple[str | None, str]]:
    """Return list of (heading or None, section body).

    The text before the first heading (if any) is returned with heading=None.
    """
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [(None, text)]

    sections: list[tuple[str | None, str]] = []
    first_start = matches[0].start()
    if first_start > 0:
        prelude = text[:first_start].strip()
        if prelude:
            sections.append((None, prelude))

    for i, match in enumerate(matches):
        title = match.group("title").strip()
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        sections.append((title, body))
    return sections


def _window(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    pieces: list[str] = []
    step = chunk_size - overlap
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        # try to land on a sentence/paragraph boundary near `end`
        cut = _soft_cut(text, end)
        pieces.append(text[start:cut].strip())
        if cut >= n:
            break
        start = max(cut - overlap, start + step)
    return [p for p in pieces if p]


def _soft_cut(text: str, hard_end: int) -> int:
    """Pull ``hard_end`` back to the nearest paragraph/sentence break."""
    if hard_end >= len(text):
        return len(text)
    window_start = max(hard_end - 120, 0)
    window = text[window_start:hard_end]
    for sep in ("\n\n", ". ", "! ", "? ", "\n"):
        idx = window.rfind(sep)
        if idx != -1:
            return window_start + idx + len(sep)
    return hard_end
