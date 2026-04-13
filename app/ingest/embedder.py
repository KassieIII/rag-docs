"""Embedding via sentence-transformers (BAAI/bge-small-en-v1.5 by default).

The model is loaded lazily on first use because importing
``sentence_transformers`` at module import time hurts test startup and
isn't needed for unit tests of pure-Python code.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:  # pragma: no cover
    from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer  # local import

    settings = get_settings()
    return SentenceTransformer(settings.embed_model)


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Return one embedding per input string. Output is a list of lists for
    easy serialization and pgvector binding."""
    if not texts:
        return []
    settings = get_settings()
    vectors = _model().encode(
        list(texts),
        batch_size=settings.embed_batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [list(map(float, v)) for v in vectors]


def embed_query(query: str) -> list[float]:
    """Embed a single query. bge models expect an instruction prefix for
    queries; we apply it here so callers don't have to remember."""
    prefixed = f"Represent this sentence for searching relevant passages: {query}"
    return embed_texts([prefixed])[0]
