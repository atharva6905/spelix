"""Tests for Qdrant unavailable fallback (P2-019).

Requirements: FR-AICP-15

Verifies that when Qdrant is unavailable:
1. degraded_mode=True is set on CoachingOutput
2. SSE "degraded" phase event is published
3. Pipeline completes (no 500 error)
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.coaching import CoachingOutput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis(analysis_id: uuid.UUID | None = None) -> MagicMock:
    obj = MagicMock()
    obj.id = analysis_id or uuid.uuid4()
    obj.status = "queued"
    obj.retry_count = 0
    obj.error_message = None
    obj.exercise_type = "squat"
    obj.exercise_variant = "high_bar"
    obj.confidence_score = 0.85
    obj.video_path = None
    obj.quality_gate_result = None
    obj.annotated_video_path = None
    obj.plot_path = None
    obj.summary_json = None
    obj.retrieval_context = None
    obj.eval_scores = None
    obj.flagged_for_review = False
    obj.user_id = uuid.uuid4()
    return obj


def _mock_coaching_output() -> CoachingOutput:
    return CoachingOutput(
        summary="Good squat form overall.",
        strengths=["Consistent tempo", "Good bracing"],
        issues=[],
        correction_plan=["Focus on depth."],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=500,
        raw_completion_tokens=300,
    )


def _build_worker_patches(
    analysis: MagicMock,
    coaching_output: CoachingOutput,
    mock_pubsub_redis: AsyncMock,
    *,
    qdrant_return: Any = None,
    qdrant_side_effect: Exception | None = None,
):
    """Return a context manager stack for patching the worker."""
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis
    mock_repo.update.return_value = analysis
    mock_repo._db = MagicMock()

    mock_coaching_repo = AsyncMock()
    coaching_created: list[Any] = []

    async def capture_create(cr: Any) -> Any:
        coaching_created.append(cr)
        return cr

    mock_coaching_repo.create.side_effect = capture_create

    mock_rep_metric_repo = AsyncMock()
    mock_rep_metric = MagicMock()
    mock_rep_metric.rep_index = 0
    mock_rep_metric.metrics_json = {"depth_angle": 85.0}
    mock_rep_metric_repo.get_by_analysis.return_value = [mock_rep_metric]

    mock_svc_instance = AsyncMock()
    mock_svc_instance.generate_coaching_streaming.return_value = coaching_output

    async def mock_cv_pipeline(**kwargs: Any) -> MagicMock:
        from app.services.status import transition as _transition

        a = kwargs["analysis"]
        repo_arg = kwargs["repo"]
        a.status = _transition(a.status, "quality_gate_pending")
        await repo_arg.update(a)
        a.status = _transition(a.status, "processing")
        await repo_arg.update(a)

        result = MagicMock()
        result.keyframes = []
        return result

    # Build get_qdrant_client mock
    get_qdrant_mock = AsyncMock(return_value=qdrant_return)
    if qdrant_side_effect:
        get_qdrant_mock = AsyncMock(side_effect=qdrant_side_effect)

    # Mock cohere client (needed because inline import raises without COHERE_API_KEY)
    mock_cohere = MagicMock()

    patches = {
        "repo": patch("app.workers.analysis_worker.AnalysisRepository", return_value=mock_repo),
        "session": patch("app.workers.analysis_worker.async_session"),
        "cv": patch("app.workers.analysis_worker.run_cv_pipeline", side_effect=mock_cv_pipeline),
        # CoachingResultRepository / CoachingService / anthropic are now local imports
        # inside _run_coaching_imperative — patch the source modules instead.
        "coaching_repo": patch(
            "app.repositories.coaching_result.CoachingResultRepository",
            return_value=mock_coaching_repo,
        ),
        "rep_metric_repo": patch(
            "app.workers.analysis_worker.RepMetricRepository",
            return_value=mock_rep_metric_repo,
        ),
        "coaching_svc": patch("app.services.coaching.CoachingService"),
        "anthropic": patch("anthropic.AsyncAnthropic", return_value=MagicMock()),
        "threshold": patch("app.workers.analysis_worker.ThresholdConfig"),
        "cleanup": patch("app.workers.analysis_worker.cleanup_temp_files"),
        "summary": patch(
            "app.workers.analysis_worker.SummaryService",
            return_value=AsyncMock(compute_and_store=AsyncMock(return_value={})),
        ),
        "pdf": patch("app.workers.analysis_worker._generate_and_upload_pdf", new_callable=AsyncMock),
        "qdrant": patch("app.services.qdrant.get_qdrant_client", get_qdrant_mock),
        "cohere": patch("app.services.cohere_client.get_cohere_client", return_value=mock_cohere),
    }

    return patches, mock_svc_instance, coaching_created


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_degraded_mode_flag_set_when_qdrant_none() -> None:
    """When get_qdrant_client returns None, coaching_output.degraded_mode=True."""
    analysis_id = uuid.uuid4()
    analysis = _make_analysis(analysis_id)
    coaching_output = _mock_coaching_output()

    mock_pubsub_redis = AsyncMock()
    mock_pubsub_redis.aclose = AsyncMock()

    patches, mock_svc, coaching_created = _build_worker_patches(
        analysis, coaching_output, mock_pubsub_redis, qdrant_return=None
    )

    import redis.asyncio as real_aioredis

    with (
        patches["repo"],
        patches["session"] as mock_session_factory,
        patches["cv"],
        patches["coaching_repo"],
        patches["rep_metric_repo"],
        patches["coaching_svc"] as MockCoachingSvc,
        patches["anthropic"],
        patches["threshold"],
        patches["cleanup"],
        patches["summary"],
        patches["pdf"],
        patches["qdrant"],
        patches["cohere"],
        patch.object(real_aioredis, "from_url", return_value=mock_pubsub_redis),
    ):
        MockCoachingSvc.return_value = mock_svc

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        ctx = {"redis": AsyncMock()}
        await process_analysis(ctx, analysis_id)

    # The stored coaching result should have degraded_mode=True
    assert len(coaching_created) == 1
    stored = coaching_created[0].structured_output_json
    assert stored["degraded_mode"] is True


@pytest.mark.asyncio
async def test_degraded_sse_event_published_when_qdrant_none() -> None:
    """When Qdrant is None, a 'degraded' phase SSE event must be published."""
    analysis_id = uuid.uuid4()
    analysis = _make_analysis(analysis_id)
    coaching_output = _mock_coaching_output()

    mock_pubsub_redis = AsyncMock()
    mock_pubsub_redis.aclose = AsyncMock()
    published_messages: list[str] = []

    async def capture_publish(channel: str, message: str) -> None:
        published_messages.append(message)

    mock_pubsub_redis.publish = AsyncMock(side_effect=capture_publish)

    patches, mock_svc, coaching_created = _build_worker_patches(
        analysis, coaching_output, mock_pubsub_redis, qdrant_return=None
    )

    import redis.asyncio as real_aioredis

    with (
        patches["repo"],
        patches["session"] as mock_session_factory,
        patches["cv"],
        patches["coaching_repo"],
        patches["rep_metric_repo"],
        patches["coaching_svc"] as MockCoachingSvc,
        patches["anthropic"],
        patches["threshold"],
        patches["cleanup"],
        patches["summary"],
        patches["pdf"],
        patches["qdrant"],
        patches["cohere"],
        patch.object(real_aioredis, "from_url", return_value=mock_pubsub_redis),
    ):
        MockCoachingSvc.return_value = mock_svc

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        ctx = {"redis": AsyncMock()}
        await process_analysis(ctx, analysis_id)

    # Find the degraded phase event in published messages
    degraded_events = [
        m for m in published_messages
        if "degraded" in m
    ]
    assert len(degraded_events) >= 1
    parsed = json.loads(degraded_events[0])
    assert parsed["type"] == "phase"
    assert parsed["phase"] == "degraded"


@pytest.mark.asyncio
async def test_no_degraded_flag_when_qdrant_available() -> None:
    """When Qdrant is available, degraded_mode should remain False."""
    analysis_id = uuid.uuid4()
    analysis = _make_analysis(analysis_id)
    coaching_output = _mock_coaching_output()

    mock_pubsub_redis = AsyncMock()
    mock_pubsub_redis.aclose = AsyncMock()

    # Qdrant is available — use a non-None mock so we enter the retrieval path.
    # The retrieval block will raise (cohere embed not mocked deeply enough)
    # but that's caught by the except — and since qdrant WAS available, we
    # should NOT set degraded_mode. Wait — the except currently sets
    # degraded_mode=True. That's correct per FR-AICP-15: any retrieval failure
    # triggers degraded mode. So the correct test is: when qdrant is available
    # AND retrieval succeeds (guard passes), degraded_mode stays False.
    #
    # Simplest approach: patch DualCollectionOrchestrator.retrieve to return results
    # and RetrievalGuard.check to pass.
    from app.schemas.rag import ChunkPayload, RetrievalResult, RetrievedContext
    from app.services.retrieval_guard import RetrievalGuardResult

    mock_ctx = RetrievedContext(
        chunk=ChunkPayload(
            id="a" * 64,
            text="Test paper.",
            paper_id="p1",
            chunk_index=0,
            section="results",
            token_count=10,
            quality_tier="L1_systematic_review",
            title="Test",
            authors=["A"],
            year=2022,
            doi=None,
        ),
        score=0.9,
        collection="papers_rag",
    )
    mock_retrieval_result = RetrievalResult(
        primary=[mock_ctx] * 3,
        supplementary=[],
        retrieval_source="papers_only_fallback",
    )
    mock_qdrant = MagicMock()  # non-None so worker enters the retrieval path

    patches, mock_svc, coaching_created = _build_worker_patches(
        analysis, coaching_output, mock_pubsub_redis, qdrant_return=mock_qdrant
    )
    # Additionally patch the retrieval internals to avoid deep async mock issues
    patches["orchestrator"] = patch(
        "app.services.dual_collection.DualCollectionOrchestrator.retrieve",
        new_callable=AsyncMock,
        return_value=mock_retrieval_result,
    )
    patches["retrieval_guard"] = patch(
        "app.services.retrieval_guard.RetrievalGuard.check",
        return_value=RetrievalGuardResult(passed=True, reason="ok"),
    )

    import redis.asyncio as real_aioredis

    with (
        patches["repo"],
        patches["session"] as mock_session_factory,
        patches["cv"],
        patches["coaching_repo"],
        patches["rep_metric_repo"],
        patches["coaching_svc"] as MockCoachingSvc,
        patches["anthropic"],
        patches["threshold"],
        patches["cleanup"],
        patches["summary"],
        patches["pdf"],
        patches["qdrant"],
        patches["cohere"],
        patches["orchestrator"],
        patches["retrieval_guard"],
        patch.object(real_aioredis, "from_url", return_value=mock_pubsub_redis),
    ):
        MockCoachingSvc.return_value = mock_svc

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        ctx = {"redis": AsyncMock()}
        await process_analysis(ctx, analysis_id)

    assert len(coaching_created) == 1
    stored = coaching_created[0].structured_output_json
    assert stored["degraded_mode"] is False
