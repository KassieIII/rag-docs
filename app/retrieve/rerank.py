"""Optional cross-encoder reranking.

Bi-encoder retrieval (what bge-small does) is fast but only sees query and
passage independently. A cross-encoder reads the pair together and gives
a sharper relevance score, at higher cost. We over-fetch ``top_k * 4``
chunks and rerank to the final ``top_k``.

This is enabled per-call (``rerank=True``) or globally via settings.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.retrieve.search import Hit

if TYPE_CHECKING:  # pragma: no cover
    from sentence_transformers import CrossEncoder

_DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _model() -> CrossEncoder:
    from sentence_transformers import CrossEncoder

    return CrossEncoder(_DEFAULT_MODEL, max_length=512)


def rerank(query: str, hits: list[Hit], *, top_k: int) -> list[Hit]:
    if not hits:
        return []
    pairs = [(query, h.text) for h in hits]
    scores = _model().predict(pairs, show_progress_bar=False)
    rescored = [
        Hit(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            source=h.source,
            heading=h.heading,
            text=h.text,
            score=float(s),
        )
        for h, s in zip(hits, scores, strict=True)
    ]
    rescored.sort(key=lambda h: h.score, reverse=True)
    return rescored[:top_k]
