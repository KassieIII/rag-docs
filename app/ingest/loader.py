"""Loaders turn a source (URL, file path, raw bytes) into plain text + a title.

We keep this small on purpose. PDF parsing is best-effort; if a document is
mostly images this loader returns whatever text pypdf can extract and the
caller decides what to do with empty results.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import httpx
from pypdf import PdfReader


@dataclass(slots=True, frozen=True)
class LoadedDocument:
    source: str
    title: str | None
    content_type: str
    text: str


def load_path(path: str | Path) -> LoadedDocument:
    p = Path(path)
    data = p.read_bytes()
    return _from_bytes(source=str(p), data=data, hint=p.suffix.lower())


async def load_url(url: str, *, client: httpx.AsyncClient | None = None) -> LoadedDocument:
    own_client = client is None
    client = client or httpx.AsyncClient(follow_redirects=True, timeout=30.0)
    try:
        response = await client.get(url)
        response.raise_for_status()
        ctype = response.headers.get("content-type", "").split(";")[0].strip().lower()
        return _from_bytes(source=url, data=response.content, hint=_hint_from_ctype(ctype))
    finally:
        if own_client:
            await client.aclose()


def _hint_from_ctype(ctype: str) -> str:
    if "pdf" in ctype:
        return ".pdf"
    if "html" in ctype:
        return ".html"
    return ".md"


def _from_bytes(*, source: str, data: bytes, hint: str) -> LoadedDocument:
    if hint == ".pdf":
        return _load_pdf(source, data)
    text = data.decode("utf-8", errors="replace")
    if hint == ".html":
        return LoadedDocument(source=source, title=None, content_type="text/html", text=text)
    return LoadedDocument(source=source, title=None, content_type="text/markdown", text=text)


def _load_pdf(source: str, data: bytes) -> LoadedDocument:
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    title = (reader.metadata.title if reader.metadata else None) or None
    return LoadedDocument(
        source=source,
        title=title,
        content_type="application/pdf",
        text="\n\n".join(pages).strip(),
    )
