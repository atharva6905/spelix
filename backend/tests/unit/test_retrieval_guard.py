"""Unit tests for RetrievalGuard (FR-AICP-09, P2-012).

Guard ensures a minimum of 3 retrieved documents before coaching generation
proceeds. Fewer than 3 → coaching_unavailable sentinel.
"""

from __future__ import annotations


from app.schemas.rag import ChunkPayload, RetrievedContext
from app.services.retrieval_guard import (
    MIN_DOCS_FOR_GENERATION,
    RetrievalGuard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(chunk_id: str = "abc123") -> RetrievedContext:
    """Construct a minimal RetrievedContext for guard tests."""
    chunk = ChunkPayload(
        id=chunk_id,
        text="Sample chunk text.",
        paper_id="paper-001",
        chunk_index=0,
        section=None,
        token_count=10,
        quality_tier="L2_rct",
        title="Test Paper",
        authors=["Author A"],
        year=2022,
        doi=None,
    )
    return RetrievedContext(chunk=chunk, score=0.9, collection="papers_rag")


def _make_contexts(n: int) -> list[RetrievedContext]:
    return [_make_context(chunk_id=f"chunk-{i}") for i in range(n)]


# ---------------------------------------------------------------------------
# Tests — below threshold
# ---------------------------------------------------------------------------


def test_zero_results_fails():
    result = RetrievalGuard.check([])
    assert result.passed is False
    assert result.sentinel == "coaching_unavailable"
    assert result.reason is not None


def test_one_result_fails():
    result = RetrievalGuard.check(_make_contexts(1))
    assert result.passed is False
    assert result.sentinel == "coaching_unavailable"
    assert result.reason is not None


def test_two_results_fail():
    result = RetrievalGuard.check(_make_contexts(2))
    assert result.passed is False
    assert result.sentinel == "coaching_unavailable"
    assert result.reason is not None


# ---------------------------------------------------------------------------
# Tests — at and above threshold
# ---------------------------------------------------------------------------


def test_three_results_passes():
    result = RetrievalGuard.check(_make_contexts(3))
    assert result.passed is True
    assert result.sentinel is None
    assert result.reason is None


def test_ten_results_passes():
    result = RetrievalGuard.check(_make_contexts(10))
    assert result.passed is True
    assert result.sentinel is None


# ---------------------------------------------------------------------------
# Constant integrity
# ---------------------------------------------------------------------------


def test_min_docs_constant_is_three():
    assert MIN_DOCS_FOR_GENERATION == 3
