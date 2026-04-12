"""Tests for B-024 — coaching wired into ARQ worker.

TDD gate: integration test with mocked LLM → status=completed.
coaching_results row exists with valid structured_output_json.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.coaching import CoachingOutput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_analysis(
    status: str = "queued",
    retry_count: int = 0,
    analysis_id: uuid.UUID | None = None,
) -> MagicMock:
    """Return a mock Analysis model instance."""
    obj = MagicMock()
    obj.id = analysis_id or uuid.uuid4()
    obj.status = status
    obj.retry_count = retry_count
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


def make_ctx(redis: Any = None) -> dict[str, Any]:
    """Build a minimal ARQ context dict."""
    if redis is None:
        redis = AsyncMock()
    return {"redis": redis}


def _mock_coaching_output() -> CoachingOutput:
    """Build a valid CoachingOutput for mock return."""
    return CoachingOutput(
        summary="Good squat form overall with minor depth issues.",
        strengths=["Consistent tempo", "Good bracing"],
        issues=[
            {
                "rep_number": 1,
                "joint": "hip",
                "description": "Slightly above parallel at depth",
                "severity": "Medium",
            }
        ],
        correction_plan=["Focus on hitting parallel", "Add pause squats"],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=500,
        raw_completion_tokens=300,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_coaching_wired_produces_completed_status():
    """Full pipeline mock → coaching called → status=completed."""
    analysis_id = uuid.uuid4()
    analysis = make_analysis(status="queued", analysis_id=analysis_id)
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis
    mock_repo.update.return_value = analysis
    # Track _db for sub-repos
    mock_repo._db = MagicMock()

    statuses_seen: list[str] = []
    coaching_created: list[Any] = []

    async def capture_update(a: Any) -> Any:
        statuses_seen.append(a.status)
        return a

    mock_repo.update.side_effect = capture_update

    # Mock coaching repo
    mock_coaching_repo = AsyncMock()

    async def capture_coaching_create(cr: Any) -> Any:
        coaching_created.append(cr)
        return cr

    mock_coaching_repo.create.side_effect = capture_coaching_create

    # Mock rep metric repo
    mock_rep_metric_repo = AsyncMock()
    mock_rep_metric = MagicMock()
    mock_rep_metric.rep_index = 0
    mock_rep_metric.metrics_json = {"depth_angle": 85.0, "knee_angle_at_depth": 90.0}
    mock_rep_metric_repo.get_by_analysis.return_value = [mock_rep_metric]

    # Mock coaching service
    mock_coaching_output = _mock_coaching_output()

    async def mock_cv_pipeline(**kwargs: Any) -> MagicMock:
        """Simulate CV pipeline: queued → qg_pending → processing."""
        from app.services.status import transition as _transition

        a = kwargs["analysis"]
        repo_arg = kwargs["repo"]
        a.status = _transition(a.status, "quality_gate_pending")
        await repo_arg.update(a)
        a.status = _transition(a.status, "processing")
        await repo_arg.update(a)

        # Return a PipelineResult-like object
        result = MagicMock()
        result.keyframes = []
        return result

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory, patch(
        "app.workers.analysis_worker.run_cv_pipeline",
        side_effect=mock_cv_pipeline,
    ), patch(
        "app.workers.analysis_worker.CoachingResultRepository",
        return_value=mock_coaching_repo,
    ), patch(
        "app.workers.analysis_worker.RepMetricRepository",
        return_value=mock_rep_metric_repo,
    ), patch(
        "app.workers.analysis_worker.CoachingService",
    ) as MockCoachingSvc, patch(
        "app.workers.analysis_worker.anthropic",
    ), patch(
        "app.workers.analysis_worker.ThresholdConfig",
    ), patch(
        "app.workers.analysis_worker.cleanup_temp_files",
    ), patch(
        "app.workers.analysis_worker.SummaryService",
        return_value=AsyncMock(compute_and_store=AsyncMock(return_value={})),
    ), patch(
        "app.workers.analysis_worker._generate_and_upload_pdf",
        new_callable=AsyncMock,
    ):
        # Configure coaching service mock — Phase 1 uses generate_coaching_streaming
        mock_svc_instance = AsyncMock()
        mock_svc_instance.generate_coaching_streaming.return_value = mock_coaching_output
        mock_svc_instance.generate_coaching.return_value = mock_coaching_output
        MockCoachingSvc.return_value = mock_svc_instance

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        # Patch redis.asyncio for pub/sub (worker opens dedicated connection)
        mock_pubsub_redis = AsyncMock()
        mock_pubsub_redis.aclose = AsyncMock()

        import redis.asyncio as real_aioredis

        with patch.object(
            real_aioredis, "from_url", return_value=mock_pubsub_redis,
        ):
            from app.workers.analysis_worker import process_analysis

            await process_analysis(ctx, analysis_id)

    # Verify status transitions include coaching → completed
    assert "coaching" in statuses_seen
    assert "completed" in statuses_seen
    assert statuses_seen[-1] == "completed"

    # Verify coaching service was called
    mock_svc_instance.generate_coaching_streaming.assert_called_once()

    # Verify coaching result was persisted
    assert len(coaching_created) == 1
    cr = coaching_created[0]
    assert cr.analysis_id == analysis_id
    assert cr.structured_output_json is not None
    assert cr.structured_output_json["summary"] == mock_coaching_output.summary
    assert cr.stream_complete is True


@pytest.mark.asyncio
async def test_coaching_failure_sets_failed_status():
    """If coaching raises, analysis should be marked failed."""
    analysis_id = uuid.uuid4()
    analysis = make_analysis(status="queued", analysis_id=analysis_id)
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis
    mock_repo.update.return_value = analysis
    mock_repo._db = MagicMock()

    async def mock_cv_pipeline2(**kwargs: Any) -> MagicMock:
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

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory, patch(
        "app.workers.analysis_worker.run_cv_pipeline",
        side_effect=mock_cv_pipeline2,
    ), patch(
        "app.workers.analysis_worker.CoachingResultRepository",
    ), patch(
        "app.workers.analysis_worker.RepMetricRepository",
    ) as MockRepMetricRepo, patch(
        "app.workers.analysis_worker.CoachingService",
    ) as MockCoachingSvc, patch(
        "app.workers.analysis_worker.anthropic",
    ), patch(
        "app.workers.analysis_worker.ThresholdConfig",
    ), patch(
        "app.workers.analysis_worker.cleanup_temp_files",
    ):
        mock_rep_repo = AsyncMock()
        mock_rep_repo.get_by_analysis.return_value = []
        MockRepMetricRepo.return_value = mock_rep_repo

        mock_svc = AsyncMock()
        mock_svc.generate_coaching_streaming.side_effect = RuntimeError("LLM exploded")
        MockCoachingSvc.return_value = mock_svc

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        # Patch redis.asyncio for pub/sub
        mock_pubsub_redis = AsyncMock()
        mock_pubsub_redis.aclose = AsyncMock()

        import redis.asyncio as real_aioredis

        with patch.object(
            real_aioredis, "from_url", return_value=mock_pubsub_redis,
        ):
            from app.workers.analysis_worker import process_analysis

            await process_analysis(ctx, analysis_id)

    assert analysis.status == "failed"
    assert "LLM exploded" in analysis.error_message
    assert analysis.retry_count == 1


# ---------------------------------------------------------------------------
# P2-016 — Four-stage wiring tests
# ---------------------------------------------------------------------------

from app.schemas.rag import ChunkPayload, RetrievedContext


def _make_contexts(n: int = 5) -> list[RetrievedContext]:
    """Build a list of mock RetrievedContext objects."""
    return [
        RetrievedContext(
            chunk=ChunkPayload(
                id=f"chunk_{i}",
                text=f"Research finding {i} about squat biomechanics.",
                paper_id=f"paper_{i}",
                chunk_index=0,
                section="results",
                token_count=50,
                quality_tier="L2_rct",
                title=f"Paper {i}",
                authors=["Author A"],
                year=2024,
                doi=None,
            ),
            score=0.9 - i * 0.05,
            collection="papers_rag",
        )
        for i in range(n)
    ]


def _base_worker_patches(
    mock_repo: AsyncMock,
    mock_coaching_repo: AsyncMock,
    mock_rep_metric_repo: AsyncMock,
    mock_coaching_output: CoachingOutput,
    mock_pubsub_redis: AsyncMock,
    *,
    retrieval_results: list[RetrievedContext] | None = None,
    cove_verified: bool = True,
    cove_raise: bool = False,
    faithfulness_score: float = 0.9,
    faithfulness_raise: bool = False,
    retrieval_raise: bool = False,
):
    """Return a context manager stack for the worker patches.

    Yields the mock coaching service instance for assertions.
    """
    from unittest.mock import patch as _patch

    from app.services.cove import CoveResult
    from app.services.faithfulness_gate import FaithfulnessResult

    mock_cv_result = MagicMock()
    mock_cv_result.keyframes = []
    mock_cv_result.bar_path = None

    async def mock_cv_pipeline(**kwargs: Any) -> MagicMock:
        from app.services.status import transition as _transition

        a = kwargs["analysis"]
        repo_arg = kwargs["repo"]
        a.status = _transition(a.status, "quality_gate_pending")
        await repo_arg.update(a)
        a.status = _transition(a.status, "processing")
        await repo_arg.update(a)
        return mock_cv_result

    # Build retrieval mock
    mock_retrieval_svc = AsyncMock()
    if retrieval_raise:
        mock_retrieval_svc.hybrid_search.side_effect = RuntimeError("Qdrant down")
    else:
        mock_retrieval_svc.hybrid_search.return_value = retrieval_results or []

    # Build CoVe mock
    mock_cove_svc = AsyncMock()
    if cove_raise:
        mock_cove_svc.verify.side_effect = RuntimeError("CoVe exploded")
    else:
        mock_cove_svc.verify.return_value = CoveResult(
            output=mock_coaching_output,
            cove_verified=cove_verified,
            iterations_run=1,
            trace=[{"iteration": 1, "converged": cove_verified}],
        )

    # Build faithfulness mock
    mock_fg_svc = AsyncMock()
    if faithfulness_raise:
        mock_fg_svc.evaluate.side_effect = RuntimeError("FG exploded")
    else:
        passed = faithfulness_score >= 0.8
        mock_fg_svc.evaluate.return_value = FaithfulnessResult(
            score=faithfulness_score,
            passed=passed,
            reasoning="test",
            unsupported_claims=[],
            flagged_for_review=not passed,
        )

    # Build mock coaching service
    mock_coaching_svc_instance = AsyncMock()
    mock_coaching_svc_instance.generate_coaching_streaming.return_value = mock_coaching_output

    import contextlib

    @contextlib.contextmanager
    def patch_stack():
        with _patch(
            "app.workers.analysis_worker.AnalysisRepository",
            return_value=mock_repo,
        ), _patch(
            "app.workers.analysis_worker.async_session",
        ) as mock_sf, _patch(
            "app.workers.analysis_worker.run_cv_pipeline",
            side_effect=mock_cv_pipeline,
        ), _patch(
            "app.workers.analysis_worker.CoachingResultRepository",
            return_value=mock_coaching_repo,
        ), _patch(
            "app.workers.analysis_worker.RepMetricRepository",
            return_value=mock_rep_metric_repo,
        ), _patch(
            "app.workers.analysis_worker.CoachingService",
            return_value=mock_coaching_svc_instance,
        ), _patch(
            "app.workers.analysis_worker.anthropic",
        ), _patch(
            "app.workers.analysis_worker.ThresholdConfig",
        ), _patch(
            "app.workers.analysis_worker.cleanup_temp_files",
        ), _patch(
            "app.workers.analysis_worker.SummaryService",
            return_value=AsyncMock(compute_and_store=AsyncMock(return_value={})),
        ), _patch(
            "app.workers.analysis_worker._generate_and_upload_pdf",
            new_callable=AsyncMock,
        ), _patch(
            "app.services.cohere_client.get_cohere_client",
            return_value=MagicMock(),
        ), _patch(
            "app.services.qdrant.get_qdrant_client",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ), _patch(
            "app.services.retrieval.RetrievalService",
            return_value=mock_retrieval_svc,
        ), _patch(
            "app.services.sparse_retrieval.SparseRetrievalService",
            return_value=MagicMock(),
        ), _patch(
            "app.services.cove.CoveVerificationService",
            return_value=mock_cove_svc,
        ), _patch(
            "app.services.faithfulness_gate.FaithfulnessGateService",
            return_value=mock_fg_svc,
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_sf.return_value = mock_session

            import redis.asyncio as real_aioredis

            with _patch.object(
                real_aioredis, "from_url", return_value=mock_pubsub_redis,
            ):
                yield mock_coaching_svc_instance

    return patch_stack()


def _setup_worker_test(
    *,
    retrieval_results: list[RetrievedContext] | None = None,
    cove_verified: bool = True,
    cove_raise: bool = False,
    faithfulness_score: float = 0.9,
    faithfulness_raise: bool = False,
    retrieval_raise: bool = False,
):
    """Common setup for P2-016 worker tests."""
    analysis_id = uuid.uuid4()
    analysis = make_analysis(status="queued", analysis_id=analysis_id)
    redis_mock = AsyncMock()
    ctx = make_ctx(redis_mock)
    mock_coaching_output = _mock_coaching_output()

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis
    mock_repo.update.return_value = analysis
    mock_repo._db = MagicMock()
    mock_repo.db = MagicMock()

    mock_coaching_repo = AsyncMock()
    coaching_created: list[Any] = []

    async def capture_create(cr: Any) -> Any:
        coaching_created.append(cr)
        return cr

    mock_coaching_repo.create.side_effect = capture_create

    mock_rep_metric_repo = AsyncMock()
    mock_rm = MagicMock()
    mock_rm.rep_index = 0
    mock_rm.metrics_json = {"depth_angle": 85.0}
    mock_rep_metric_repo.get_by_analysis.return_value = [mock_rm]

    mock_pubsub_redis = AsyncMock()
    mock_pubsub_redis.aclose = AsyncMock()

    patches = _base_worker_patches(
        mock_repo=mock_repo,
        mock_coaching_repo=mock_coaching_repo,
        mock_rep_metric_repo=mock_rep_metric_repo,
        mock_coaching_output=mock_coaching_output,
        mock_pubsub_redis=mock_pubsub_redis,
        retrieval_results=retrieval_results,
        cove_verified=cove_verified,
        cove_raise=cove_raise,
        faithfulness_score=faithfulness_score,
        faithfulness_raise=faithfulness_raise,
        retrieval_raise=retrieval_raise,
    )

    return (
        ctx, analysis_id, analysis, patches, coaching_created,
        mock_pubsub_redis, mock_coaching_output,
    )


@pytest.mark.asyncio
async def test_pipeline_passes_contexts_to_coaching():
    """When retrieval returns 5 contexts, coaching receives them."""
    contexts = _make_contexts(5)
    ctx, aid, analysis, patches, created, pubsub, _ = _setup_worker_test(
        retrieval_results=contexts,
    )
    with patches as mock_svc:
        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, aid)

    mock_svc.generate_coaching_streaming.assert_called_once()
    call_kwargs = mock_svc.generate_coaching_streaming.call_args.kwargs
    assert call_kwargs["retrieved_contexts"] is not None
    assert len(call_kwargs["retrieved_contexts"]) == 5
    assert analysis.status == "completed"


@pytest.mark.asyncio
async def test_retrieval_guard_failure_no_contexts():
    """When retrieval returns <3 results, coaching called with None."""
    contexts = _make_contexts(2)  # below MIN_DOCS_FOR_GENERATION=3
    ctx, aid, analysis, patches, created, pubsub, _ = _setup_worker_test(
        retrieval_results=contexts,
    )
    with patches as mock_svc:
        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, aid)

    call_kwargs = mock_svc.generate_coaching_streaming.call_args.kwargs
    assert call_kwargs["retrieved_contexts"] is None
    assert analysis.status == "completed"


@pytest.mark.asyncio
async def test_retrieval_failure_pipeline_continues():
    """If hybrid_search raises, pipeline still completes."""
    ctx, aid, analysis, patches, created, pubsub, _ = _setup_worker_test(
        retrieval_raise=True,
    )
    with patches as mock_svc:
        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, aid)

    assert analysis.status == "completed"
    call_kwargs = mock_svc.generate_coaching_streaming.call_args.kwargs
    assert call_kwargs["retrieved_contexts"] is None


@pytest.mark.asyncio
async def test_cove_verified_stored():
    """When CoVe returns verified=True, coaching_result has cove_verified=True."""
    contexts = _make_contexts(5)
    ctx, aid, analysis, patches, created, pubsub, _ = _setup_worker_test(
        retrieval_results=contexts,
        cove_verified=True,
    )
    with patches:
        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, aid)

    assert len(created) == 1
    assert created[0].cove_verified is True


@pytest.mark.asyncio
async def test_cove_failure_pipeline_continues():
    """If CoVe raises, pipeline still completes with cove_verified=False."""
    contexts = _make_contexts(5)
    ctx, aid, analysis, patches, created, pubsub, _ = _setup_worker_test(
        retrieval_results=contexts,
        cove_raise=True,
    )
    with patches:
        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, aid)

    assert analysis.status == "completed"
    assert len(created) == 1
    assert created[0].cove_verified is False


@pytest.mark.asyncio
async def test_faithfulness_stores_eval_scores():
    """FG score stored in analysis.eval_scores when retrieval succeeds."""
    contexts = _make_contexts(5)
    ctx, aid, analysis, patches, created, pubsub, _ = _setup_worker_test(
        retrieval_results=contexts,
        faithfulness_score=0.9,
    )
    with patches:
        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, aid)

    assert analysis.eval_scores is not None
    assert analysis.eval_scores["faithfulness_score"] == 0.9
    assert analysis.eval_scores["faithfulness_passed"] is True


@pytest.mark.asyncio
async def test_faithfulness_below_threshold_flags():
    """Sub-threshold faithfulness score sets flagged_for_review=True."""
    contexts = _make_contexts(5)
    ctx, aid, analysis, patches, created, pubsub, _ = _setup_worker_test(
        retrieval_results=contexts,
        faithfulness_score=0.5,
    )
    with patches:
        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, aid)

    assert analysis.flagged_for_review is True


@pytest.mark.asyncio
async def test_faithfulness_failure_pipeline_continues():
    """If FG raises, pipeline still completes."""
    contexts = _make_contexts(5)
    ctx, aid, analysis, patches, created, pubsub, _ = _setup_worker_test(
        retrieval_results=contexts,
        faithfulness_raise=True,
    )
    with patches:
        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, aid)

    assert analysis.status == "completed"


@pytest.mark.asyncio
async def test_retrieved_sources_stored():
    """Retrieved contexts stored in coaching_result.retrieved_sources_json."""
    contexts = _make_contexts(5)
    ctx, aid, analysis, patches, created, pubsub, _ = _setup_worker_test(
        retrieval_results=contexts,
    )
    with patches:
        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, aid)

    assert len(created) == 1
    assert created[0].retrieved_sources_json is not None
    assert len(created[0].retrieved_sources_json) == 5


@pytest.mark.asyncio
async def test_phase_events_published():
    """Worker publishes retrieving and verifying phase events via pubsub."""
    import json

    contexts = _make_contexts(5)
    ctx, aid, analysis, patches, created, pubsub, _ = _setup_worker_test(
        retrieval_results=contexts,
    )
    with patches:
        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, aid)

    # Collect all published messages
    published = [
        json.loads(call.args[1]) if len(call.args) > 1 else json.loads(call.kwargs.get("message", "{}"))
        for call in pubsub.publish.call_args_list
        if len(call.args) > 1 or "message" in call.kwargs
    ]
    phase_events = [m for m in published if m.get("type") == "phase"]
    phases = [e["phase"] for e in phase_events]
    assert "retrieving" in phases
    assert "verifying" in phases
