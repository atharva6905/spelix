"""Tests for DualCollectionOrchestrator — P2-026 dual-collection retrieval routing.

Requirements: FR-BRAIN-04, FR-BRAIN-05, FR-AICP-09

TDD protocol: tests written before implementation.
All Cohere and Qdrant calls are mocked (ADR-032).

The orchestrator queries BOTH papers_rag and coach_brain concurrently,
merges results, reranks the combined set with Cohere Rerank 4.0,
and classifies the result into one of three retrieval modes per FR-BRAIN-05:
  - coach_brain_primary (top coach_brain score >= 0.82)
  - hybrid_brain_supplementary (0.65 <= score < 0.82)
  - papers_only_fallback (score < 0.65)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.rag import ChunkPayload, RetrievedContext


# ---------------------------------------------------------------------------
# Helpers — shared mock factories
# ---------------------------------------------------------------------------


def _make_chunk(
    chunk_id: str = "a" * 64,
    text: str = "Squat depth improves with hip mobility.",
    paper_id: str = "paper-001",
) -> ChunkPayload:
    return ChunkPayload(
        id=chunk_id,
        text=text,
        paper_id=paper_id,
        chunk_index=0,
        section="results",
        token_count=12,
        quality_tier="L1_systematic_review",
        title="Test Paper",
        authors=["Author A"],
        year=2022,
        doi=None,
    )


def _make_ctx(
    chunk_id: str = "a" * 64,
    score: float = 0.85,
    collection: str = "papers_rag",
    text: str = "Squat depth improves with hip mobility.",
) -> RetrievedContext:
    return RetrievedContext(
        chunk=_make_chunk(chunk_id=chunk_id, text=text),
        score=score,
        collection=collection,  # type: ignore[arg-type]
    )


def _make_retrieval_service(
    papers_results: list[RetrievedContext] | None = None,
    brain_results: list[RetrievedContext] | None = None,
) -> MagicMock:
    """Return a mock RetrievalService whose hybrid_search returns per-collection results."""
    if papers_results is None:
        papers_results = [_make_ctx(chunk_id="p" * 64, score=0.80, collection="papers_rag")]
    if brain_results is None:
        brain_results = []

    svc = MagicMock()

    async def _hybrid_search(
        query: str,
        collection: str = "papers_rag",
        **kwargs,
    ) -> list[RetrievedContext]:
        if collection == "papers_rag":
            return papers_results
        elif collection == "coach_brain":
            return brain_results
        return []

    svc.hybrid_search = AsyncMock(side_effect=_hybrid_search)
    return svc


def _make_cohere_client(
    rerank_results: list[tuple[int, float]] | None = None,
) -> MagicMock:
    """Return a mock CohereEmbedClient with rerank support."""
    client = MagicMock()
    if rerank_results is None:
        rerank_results = [(0, 0.90)]
    client.rerank = AsyncMock(return_value=rerank_results)
    return client


# ---------------------------------------------------------------------------
# Gate 1 — concurrent gather: both collections queried before either completes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_queries_both_collections_concurrently() -> None:
    """asyncio.gather must issue both collection queries simultaneously,
    not sequentially (FR-AICP-09)."""
    from app.services.dual_collection import DualCollectionOrchestrator

    call_order: list[str] = []
    call_entered: dict[str, asyncio.Event] = {
        "papers_rag": asyncio.Event(),
        "coach_brain": asyncio.Event(),
    }

    async def _tracking_hybrid_search(
        query: str,
        collection: str = "papers_rag",
        **kwargs,
    ) -> list[RetrievedContext]:
        call_order.append(f"enter_{collection}")
        call_entered[collection].set()
        # Wait for the other collection to also enter before returning
        other = "coach_brain" if collection == "papers_rag" else "papers_rag"
        await asyncio.wait_for(call_entered[other].wait(), timeout=2.0)
        call_order.append(f"exit_{collection}")
        return [_make_ctx(collection=collection)]

    svc = MagicMock()
    svc.hybrid_search = AsyncMock(side_effect=_tracking_hybrid_search)
    cohere = _make_cohere_client(rerank_results=[(0, 0.5), (1, 0.4)])

    orchestrator = DualCollectionOrchestrator(svc, cohere)
    await orchestrator.retrieve("squat depth", exercise_type="squat")

    # Both must have entered before either exited — proves gather, not sequential
    assert "enter_papers_rag" in call_order
    assert "enter_coach_brain" in call_order
    enter_papers_idx = call_order.index("enter_papers_rag")
    enter_brain_idx = call_order.index("enter_coach_brain")
    exit_papers_idx = call_order.index("exit_papers_rag")
    exit_brain_idx = call_order.index("exit_coach_brain")
    assert enter_papers_idx < exit_brain_idx, "papers query must start before brain exits"
    assert enter_brain_idx < exit_papers_idx, "brain query must start before papers exits"


# ---------------------------------------------------------------------------
# Gate 2 — coach_brain_primary routing (top brain score >= 0.82)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_coach_brain_primary_when_score_above_threshold() -> None:
    """When top coach_brain score >= 0.82 after rerank, retrieval_source
    must be 'coach_brain_primary' and primary contains coach_brain items."""
    from app.services.dual_collection import DualCollectionOrchestrator

    papers = [_make_ctx(chunk_id="p" * 64, score=0.75, collection="papers_rag")]
    brain = [_make_ctx(chunk_id="b" * 64, score=0.90, collection="coach_brain")]

    svc = _make_retrieval_service(papers_results=papers, brain_results=brain)
    # Rerank: brain item scores 0.88 (>= 0.82), papers item scores 0.70
    cohere = _make_cohere_client(rerank_results=[(1, 0.88), (0, 0.70)])

    orchestrator = DualCollectionOrchestrator(svc, cohere)
    result = await orchestrator.retrieve("squat depth", exercise_type="squat")

    assert result.retrieval_source == "coach_brain_primary"
    # Primary should contain the coach_brain item
    primary_collections = {ctx.collection for ctx in result.primary}
    assert "coach_brain" in primary_collections


# ---------------------------------------------------------------------------
# Gate 3 — hybrid_brain_supplementary routing (0.65 <= score < 0.82)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_hybrid_supplementary_when_score_in_middle() -> None:
    """When top coach_brain score is 0.65-0.82, retrieval_source is
    'hybrid_brain_supplementary' and both collections appear in primary."""
    from app.services.dual_collection import DualCollectionOrchestrator

    papers = [_make_ctx(chunk_id="p" * 64, score=0.75, collection="papers_rag")]
    brain = [_make_ctx(chunk_id="b" * 64, score=0.70, collection="coach_brain")]

    svc = _make_retrieval_service(papers_results=papers, brain_results=brain)
    # Rerank: brain scores 0.72 (0.65-0.82 range), papers scores 0.80
    cohere = _make_cohere_client(rerank_results=[(0, 0.80), (1, 0.72)])

    orchestrator = DualCollectionOrchestrator(svc, cohere)
    result = await orchestrator.retrieve("squat depth", exercise_type="squat")

    assert result.retrieval_source == "hybrid_brain_supplementary"
    # Both collections should appear in primary for hybrid mode
    primary_collections = {ctx.collection for ctx in result.primary}
    assert "papers_rag" in primary_collections
    assert "coach_brain" in primary_collections


# ---------------------------------------------------------------------------
# Gate 4 — papers_only_fallback routing (score < 0.65)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_papers_only_fallback_when_brain_score_low() -> None:
    """When top coach_brain score < 0.65, retrieval_source is
    'papers_only_fallback' and primary contains only papers_rag items."""
    from app.services.dual_collection import DualCollectionOrchestrator

    papers = [_make_ctx(chunk_id="p" * 64, score=0.80, collection="papers_rag")]
    brain = [_make_ctx(chunk_id="b" * 64, score=0.50, collection="coach_brain")]

    svc = _make_retrieval_service(papers_results=papers, brain_results=brain)
    # Rerank: brain scores 0.55 (< 0.65), papers scores 0.85
    cohere = _make_cohere_client(rerank_results=[(0, 0.85), (1, 0.55)])

    orchestrator = DualCollectionOrchestrator(svc, cohere)
    result = await orchestrator.retrieve("squat depth", exercise_type="squat")

    assert result.retrieval_source == "papers_only_fallback"
    # Primary should contain only papers_rag items
    primary_collections = {ctx.collection for ctx in result.primary}
    assert primary_collections == {"papers_rag"}


# ---------------------------------------------------------------------------
# Gate 5 — empty coach_brain → papers_only_fallback (P2-027 cold-start)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_empty_brain_routes_to_papers_only_fallback() -> None:
    """When coach_brain returns zero results, top_coach_brain_score is 0.0
    which routes to papers_only_fallback. P2-027 cold-start case."""
    from app.services.dual_collection import DualCollectionOrchestrator

    papers = [
        _make_ctx(chunk_id="p1" + "0" * 62, score=0.85, collection="papers_rag"),
        _make_ctx(chunk_id="p2" + "0" * 62, score=0.80, collection="papers_rag"),
    ]
    brain: list[RetrievedContext] = []  # empty — cold start

    svc = _make_retrieval_service(papers_results=papers, brain_results=brain)
    # Rerank only sees papers items
    cohere = _make_cohere_client(rerank_results=[(0, 0.90), (1, 0.85)])

    orchestrator = DualCollectionOrchestrator(svc, cohere)
    result = await orchestrator.retrieve("squat depth", exercise_type="squat")

    assert result.retrieval_source == "papers_only_fallback"
    assert len(result.primary) >= 1
    assert all(ctx.collection == "papers_rag" for ctx in result.primary)


# ---------------------------------------------------------------------------
# Gate 6 — cross-collection rerank called once on merged texts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_calls_rerank_once_on_merged_texts() -> None:
    """The orchestrator must call cohere_client.rerank exactly once with
    texts from both collections merged (ADR-RAG-01: single rerank call)."""
    from app.services.dual_collection import DualCollectionOrchestrator

    papers = [_make_ctx(chunk_id="p" * 64, score=0.8, collection="papers_rag", text="paper text")]
    brain = [_make_ctx(chunk_id="b" * 64, score=0.7, collection="coach_brain", text="brain text")]

    svc = _make_retrieval_service(papers_results=papers, brain_results=brain)
    cohere = _make_cohere_client(rerank_results=[(0, 0.85), (1, 0.70)])

    orchestrator = DualCollectionOrchestrator(svc, cohere)
    await orchestrator.retrieve("squat depth", exercise_type="squat")

    # Rerank called exactly once
    cohere.rerank.assert_called_once()
    # Check that both texts are in the documents list
    call_args = cohere.rerank.call_args
    documents = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("documents")
    assert "paper text" in documents
    assert "brain text" in documents


# ---------------------------------------------------------------------------
# Gate 7 — status="active" filter on coach_brain queries (FR-BRAIN-04)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_adds_status_active_filter_on_coach_brain() -> None:
    """Coach brain hybrid_search call must include additional_filters with
    status='active' FieldCondition (FR-BRAIN-04)."""
    from app.services.dual_collection import DualCollectionOrchestrator

    svc = _make_retrieval_service()
    cohere = _make_cohere_client()

    orchestrator = DualCollectionOrchestrator(svc, cohere)
    await orchestrator.retrieve("squat depth", exercise_type="squat")

    # Find the coach_brain call
    brain_call = None
    for call in svc.hybrid_search.call_args_list:
        kwargs = call.kwargs
        if kwargs.get("collection") == "coach_brain":
            brain_call = kwargs
            break

    assert brain_call is not None, "hybrid_search must be called for coach_brain"
    additional = brain_call.get("additional_filters")
    assert additional is not None, "coach_brain call must have additional_filters"
    assert len(additional) >= 1, "Must have at least one additional filter"

    status_filter = additional[0]
    assert status_filter.key == "status", f"Filter key must be 'status', got {status_filter.key}"
    assert status_filter.match.value == "active", (
        f"Filter value must be 'active', got {status_filter.match.value}"
    )


# ---------------------------------------------------------------------------
# Gate 8 — rerank timeout → RRF fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_rerank_timeout_falls_back_to_rrf() -> None:
    """When Cohere rerank times out, the orchestrator must return RRF-fused
    results directly rather than raising (P2-020 pattern)."""
    from app.services.dual_collection import DualCollectionOrchestrator

    papers = [_make_ctx(chunk_id="p" * 64, score=0.80, collection="papers_rag")]
    brain = [_make_ctx(chunk_id="b" * 64, score=0.70, collection="coach_brain")]

    svc = _make_retrieval_service(papers_results=papers, brain_results=brain)
    cohere = _make_cohere_client()
    cohere.rerank = AsyncMock(side_effect=asyncio.TimeoutError)

    orchestrator = DualCollectionOrchestrator(svc, cohere)
    result = await orchestrator.retrieve("squat depth", exercise_type="squat")

    # Should not raise — returns results even on timeout
    assert result is not None
    assert len(result.primary) >= 1
    # Without rerank, no coach_brain score is available → papers_only_fallback
    assert result.retrieval_source == "papers_only_fallback"


# ---------------------------------------------------------------------------
# FR-BRAIN-13 (P2-032): Langfuse retrieval metrics logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_langfuse_logging_called_on_retrieve():
    """Langfuse trace is called with retrieval metrics after retrieve()."""
    from app.services.dual_collection import DualCollectionOrchestrator

    papers = [_make_ctx(chunk_id="p" * 64, score=0.80, collection="papers_rag")]
    brain = [_make_ctx(chunk_id="b" * 64, score=0.70, collection="coach_brain")]

    svc = _make_retrieval_service(papers_results=papers, brain_results=brain)
    cohere = _make_cohere_client(rerank_results=[(0, 0.80), (1, 0.70)])

    mock_langfuse = MagicMock()
    mock_trace = MagicMock()
    mock_langfuse.trace.return_value = mock_trace

    orchestrator = DualCollectionOrchestrator(svc, cohere, langfuse_client=mock_langfuse)
    result = await orchestrator.retrieve("squat depth", exercise_type="squat")

    assert result is not None
    mock_langfuse.trace.assert_called_once()
    call_kwargs = mock_langfuse.trace.call_args
    metadata = call_kwargs.kwargs["metadata"]
    assert metadata["retrieval_source"] in (
        "coach_brain_primary",
        "hybrid_brain_supplementary",
        "papers_only_fallback",
    )
    assert "brain_hit_count" in metadata
    assert "papers_hit_count" in metadata
    assert "brain_contribution_pct" in metadata
    mock_trace.score.assert_called_once()


@pytest.mark.asyncio
async def test_langfuse_none_does_not_crash():
    """No error when langfuse_client is None."""
    from app.services.dual_collection import DualCollectionOrchestrator

    papers = [_make_ctx(chunk_id="p" * 64, score=0.80, collection="papers_rag")]

    svc = _make_retrieval_service(papers_results=papers)
    cohere = _make_cohere_client(rerank_results=[(0, 0.80)])

    orchestrator = DualCollectionOrchestrator(svc, cohere, langfuse_client=None)
    result = await orchestrator.retrieve("squat depth", exercise_type="squat")

    assert result is not None
    assert result.retrieval_source == "papers_only_fallback"


@pytest.mark.asyncio
async def test_langfuse_error_does_not_crash():
    """Langfuse errors are swallowed — never fail the pipeline."""
    from app.services.dual_collection import DualCollectionOrchestrator

    papers = [_make_ctx(chunk_id="p" * 64, score=0.80, collection="papers_rag")]

    svc = _make_retrieval_service(papers_results=papers)
    cohere = _make_cohere_client(rerank_results=[(0, 0.80)])

    mock_langfuse = MagicMock()
    mock_langfuse.trace.side_effect = RuntimeError("Langfuse down")

    orchestrator = DualCollectionOrchestrator(svc, cohere, langfuse_client=mock_langfuse)
    result = await orchestrator.retrieve("squat depth", exercise_type="squat")

    assert result is not None
    assert result.retrieval_source == "papers_only_fallback"
