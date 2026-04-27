"""Vector search over chunks using pgvector cosine distance.

We store normalized embeddings, so cosine distance == ``1 - dot``.
The ``<=>`` operator returns cosine distance; we expose ``score`` as
``1 - distance`` (i.e. cosine similarity) so callers see "higher is
better" without thinking.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest.embedder import embed_query
from app.models import Chunk, Document


@dataclass(slots=True, frozen=True)
class Hit:
    chunk_id: int
    document_id: int
    source: str
    heading: str | None
    text: str
    score: float


async def search(
    session: AsyncSession,
    query: str,
    *,
    top_k: int = 5,
    min_score: float = 0.0,
) -> list[Hit]:
    """Return the top ``top_k`` chunks for ``query`` ordered by similarity desc.

    Hits with similarity below ``min_score`` are filtered out. This stops us
    from feeding noise to the LLM when the index has nothing relevant.
    """
    if not query.strip():
        return []
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    vector = embed_query(query)
    distance = Chunk.embedding.cosine_distance(vector)
    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.heading,
            Chunk.text,
            Document.source,
            distance.label("distance"),
        )
        .join(Document, Document.id == Chunk.document_id)
        .order_by(distance.asc())
        .limit(top_k)
    )
    result = await session.execute(stmt)
    hits = [
        Hit(
            chunk_id=row.id,
            document_id=row.document_id,
            source=row.source,
            heading=row.heading,
            text=row.text,
            score=1.0 - float(row.distance),
        )
        for row in result
    ]
    return [h for h in hits if h.score >= min_score]
