"""End-to-end ingest pipeline: load → chunk → embed → upsert."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.ingest.chunker import Chunk as TextChunk
from app.ingest.chunker import chunk_markdown
from app.ingest.embedder import embed_texts
from app.ingest.loader import LoadedDocument
from app.models import Chunk, Document


@dataclass(slots=True, frozen=True)
class IngestResult:
    document_id: int
    chunk_count: int
    replaced: bool


async def ingest_document(session: AsyncSession, loaded: LoadedDocument) -> IngestResult:
    """Persist ``loaded`` as a Document plus its embedded chunks.

    If a Document with the same ``source`` already exists, its chunks are
    replaced so re-ingesting an updated page is idempotent.
    """
    settings = get_settings()
    chunks = chunk_markdown(
        loaded.text,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    if not chunks:
        raise ValueError(f"no extractable text for source: {loaded.source}")

    existing = await session.scalar(select(Document).where(Document.source == loaded.source))
    replaced = existing is not None
    if existing is not None:
        await session.delete(existing)
        await session.flush()

    document = Document(
        source=loaded.source,
        title=loaded.title,
        content_type=loaded.content_type,
    )
    session.add(document)
    await session.flush()

    vectors = embed_texts([c.text for c in chunks])
    session.add_all(_to_orm_chunks(document.id, chunks, vectors))
    await session.commit()

    return IngestResult(
        document_id=document.id,
        chunk_count=len(chunks),
        replaced=replaced,
    )


def _to_orm_chunks(
    document_id: int,
    chunks: list[TextChunk],
    vectors: list[list[float]],
) -> list[Chunk]:
    return [
        Chunk(
            document_id=document_id,
            ordinal=c.ordinal,
            text=c.text,
            heading=c.heading,
            embedding=v,
        )
        for c, v in zip(chunks, vectors, strict=True)
    ]
