"""Unit tests for retrieval-side pure-function logic.

These tests don't need a database; they exercise the Reciprocal Rank
Fusion algorithm and the hybrid search short-circuit behaviour with
hand-crafted ranking lists.
"""

from __future__ import annotations

from app.retrieve.search import Hit, reciprocal_rank_fusion


def _hit(chunk_id: int, *, score: float = 0.0, text: str = "") -> Hit:
    return Hit(
        chunk_id=chunk_id,
        document_id=1,
        source="https://example.com",
        heading=None,
        text=text or f"chunk-{chunk_id}",
        score=score,
    )


def test_rrf_promotes_chunks_present_in_both_rankings() -> None:
    # Chunk 7 is rank 3 in vector and rank 1 in BM25 -> highest fused score.
    # Chunk 1 is rank 1 only in vector. Chunk 2 only in BM25 at rank 2.
    vector = [_hit(3), _hit(1), _hit(7), _hit(9)]
    bm25 = [_hit(7), _hit(2), _hit(5)]

    fused = reciprocal_rank_fusion([vector, bm25], top_k=3, k=60)

    assert next(h.chunk_id for h in fused) == 7  # in both lists -> top
    assert {h.chunk_id for h in fused} == {7, 3, 1} or {h.chunk_id for h in fused} == {
        7,
        3,
        2,
    }


def test_rrf_score_is_actual_rrf_value() -> None:
    vector = [_hit(7)]
    bm25 = [_hit(7)]
    [hit] = reciprocal_rank_fusion([vector, bm25], top_k=1, k=60)
    # Both rankings put chunk 7 at rank 1, so RRF = 2 * 1/(60+1)
    assert hit.score == 2.0 / 61.0


def test_rrf_takes_first_rankings_representative_for_metadata() -> None:
    vector = [_hit(7, text="vector text")]
    bm25 = [_hit(7, text="bm25 text")]
    [hit] = reciprocal_rank_fusion([vector, bm25], top_k=1)
    # Vector ranking is passed first, so its hit is the representative.
    assert hit.text == "vector text"


def test_rrf_empty_inputs_yield_no_results() -> None:
    assert reciprocal_rank_fusion([], top_k=5) == []
    assert reciprocal_rank_fusion([[], []], top_k=5) == []


def test_rrf_stable_truncation_to_top_k() -> None:
    vector = [_hit(i) for i in range(1, 11)]
    bm25 = [_hit(i) for i in range(11, 21)]
    fused = reciprocal_rank_fusion([vector, bm25], top_k=4)
    assert len(fused) == 4
    # No chunk appears in both, so both branches contribute equally and the
    # top-4 should come from the heads of each ranking interleaved.
    assert {h.chunk_id for h in fused} == {1, 2, 11, 12}


def test_rrf_rejects_non_positive_top_k() -> None:
    import pytest

    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[_hit(1)]], top_k=0)
