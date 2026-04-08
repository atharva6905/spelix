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

    async def mock_cv_pipeline(**kwargs: Any) -> None:
        """Simulate CV pipeline: queued → qg_pending → processing."""
        from app.services.status import transition as _transition

        a = kwargs["analysis"]
        repo_arg = kwargs["repo"]
        a.status = _transition(a.status, "quality_gate_pending")
        await repo_arg.update(a)
        a.status = _transition(a.status, "processing")
        await repo_arg.update(a)

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
    ):
        # Configure coaching service mock
        mock_svc_instance = AsyncMock()
        mock_svc_instance.generate_coaching.return_value = mock_coaching_output
        MockCoachingSvc.return_value = mock_svc_instance

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    # Verify status transitions include coaching → completed
    assert "coaching" in statuses_seen
    assert "completed" in statuses_seen
    assert statuses_seen[-1] == "completed"

    # Verify coaching service was called
    mock_svc_instance.generate_coaching.assert_called_once()

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

    async def mock_cv_pipeline2(**kwargs: Any) -> None:
        from app.services.status import transition as _transition

        a = kwargs["analysis"]
        repo_arg = kwargs["repo"]
        a.status = _transition(a.status, "quality_gate_pending")
        await repo_arg.update(a)
        a.status = _transition(a.status, "processing")
        await repo_arg.update(a)

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
        mock_svc.generate_coaching.side_effect = RuntimeError("LLM exploded")
        MockCoachingSvc.return_value = mock_svc

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    assert analysis.status == "failed"
    assert "LLM exploded" in analysis.error_message
    assert analysis.retry_count == 1
