"""Retrieval over chunks.

Three modes are exposed:

- :func:`search` — pure vector retrieval (pgvector cosine).
- :func:`search_bm25` — pure lexical retrieval (Postgres FTS, ``ts_rank_cd``).
- :func:`search_hybrid` — both of the above fused with Reciprocal Rank
  Fusion (RRF), which is the default configurable via ``RETRIEVE_MODE``.

We store normalized embeddings, so cosine distance == ``1 - dot``.
The ``<=>`` operator returns cosine distance; we expose vector scores as
``1 - distance`` (cosine similarity) so callers see "higher is better"
without thinking.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest.embedder import embed_query
from app.models import Chunk, Document

# Reciprocal Rank Fusion constant. 60 is the value from the original
# Cormack et al. (2009) paper and it works well enough that no one
# bothers tuning it in practice.
RRF_K = 60


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


async def search_bm25(
    session: AsyncSession,
    query: str,
    *,
    top_k: int = 5,
) -> list[Hit]:
    """Lexical retrieval via Postgres full-text search.

    Uses ``websearch_to_tsquery`` so the query string accepts the same
    natural-language syntax users already type into Google ("foo OR bar",
    quoted phrases, ``-excluded``). Ranking is ``ts_rank_cd`` over the
    pre-computed ``chunks.text_tsv`` GIN-indexed column.
    """
    if not query.strip():
        return []
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    tsquery = func.websearch_to_tsquery("english", bindparam("q", query))
    text_tsv = text("chunks.text_tsv")
    rank = func.ts_rank_cd(text_tsv, tsquery).label("rank")

    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.heading,
            Chunk.text,
            Document.source,
            rank,
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(text_tsv.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(top_k)
    )
    result = await session.execute(stmt)
    return [
        Hit(
            chunk_id=row.id,
            document_id=row.document_id,
            source=row.source,
            heading=row.heading,
            text=row.text,
            score=float(row.rank),
        )
        for row in result
    ]


def reciprocal_rank_fusion(
    rankings: list[list[Hit]],
    *,
    top_k: int,
    k: int = RRF_K,
) -> list[Hit]:
    """Fuse multiple ranked lists into a single ranking via RRF.

    For each document ``d`` and ranking ``r`` where ``d`` appears at
    rank ``rank_r(d)`` (1-based), the fused score is::

        score(d) = sum over r of  1 / (k + rank_r(d))

    Score from each contributing ranking is accumulated regardless of
    the original similarity / rank values, which makes RRF robust to
    incommensurate score scales (e.g. cosine similarity vs ``ts_rank_cd``).
    The returned ``Hit.score`` is the RRF score; ``Hit.text`` etc. come
    from the first ranking that contained the chunk.

    Returns up to ``top_k`` hits, sorted by fused score descending.
    """
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    fused_score: dict[int, float] = {}
    representative: dict[int, Hit] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            fused_score[hit.chunk_id] = fused_score.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
            representative.setdefault(hit.chunk_id, hit)

    ordered = sorted(fused_score.items(), key=lambda kv: kv[1], reverse=True)
    return [
        replace(representative[chunk_id], score=score)
        for chunk_id, score in ordered[:top_k]
    ]


async def search_hybrid(
    session: AsyncSession,
    query: str,
    *,
    top_k: int = 5,
    min_score: float = 0.0,
    candidates_per_branch: int | None = None,
) -> list[Hit]:
    """Hybrid retrieval: vector + BM25 fused with Reciprocal Rank Fusion.

    Both branches over-fetch ``candidates_per_branch`` (default ``4 * top_k``)
    candidates so that the fusion has enough material to re-order. The
    ``min_score`` threshold is applied to the *vector* branch only,
    matching the behaviour of pure vector search; BM25 already filters
    via the ``@@`` predicate.
    """
    over_fetch = candidates_per_branch or max(top_k * 4, 20)

    vec = await search(session, query, top_k=over_fetch, min_score=min_score)
    lex = await search_bm25(session, query, top_k=over_fetch)

    # Short-circuit: if one branch is empty, fall back to the other so
    # we never lose recall just because FTS rejected the query string.
    if not vec:
        return lex[:top_k]
    if not lex:
        return vec[:top_k]
    return reciprocal_rank_fusion([vec, lex], top_k=top_k)
