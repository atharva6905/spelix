"""E2E integration test — full analysis flow (B-041).

Full flow: create analysis → start → worker processes → verify completion.

Uses httpx AsyncClient against full FastAPI app for API layer.
Worker processing tested directly with mocked external services.
All external services (Supabase Storage, Anthropic API, MediaPipe) are mocked.

Requirements: NFR-MAIN-04
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.schemas.coaching import CoachingOutput

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


def _mock_user() -> dict:
    return {"id": _USER_ID, "email": "e2e@test.com", "role": "user"}


def _mock_coaching_output() -> CoachingOutput:
    return CoachingOutput(
        summary="Good squat form with minor depth issues.",
        strengths=["Consistent tempo", "Good bracing"],
        issues=[
            {
                "rep_number": 1,
                "joint": "hip",
                "description": "Slightly above parallel",
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
# E2E: API endpoints test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_list_analyses():
    """Create an analysis via API, then list it."""
    from app.main import app
    from app.services.analysis import AnalysisService

    app.dependency_overrides[get_current_user] = _mock_user

    analysis_id = uuid.uuid4()

    # Mock the service dependency
    mock_service = AsyncMock(spec=AnalysisService)
    mock_result = MagicMock()
    mock_result.analysis = MagicMock()
    mock_result.analysis.id = analysis_id
    mock_result.analysis.status = "queued"
    mock_result.upload_url = "https://storage.supabase.co/fake"
    mock_result.expires_at = datetime.now(timezone.utc)
    mock_service.create_analysis.return_value = mock_result

    # Mock list
    mock_summary = MagicMock()
    mock_summary.id = analysis_id
    mock_summary.status = "queued"
    mock_summary.exercise_type = "squat"
    mock_summary.exercise_variant = "high_bar"
    mock_summary.confidence_score = None
    mock_summary.created_at = datetime.now(timezone.utc)
    mock_summary.updated_at = datetime.now(timezone.utc)
    mock_summary.tags = None
    mock_summary.error_message = None
    mock_summary.summary_json = None
    mock_service.list_analyses.return_value = [mock_summary]

    from app.api.v1.analyses import _get_service

    app.dependency_overrides[_get_service] = lambda: mock_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create
            resp = await client.post(
                "/api/v1/analyses",
                json={
                    "exercise_type": "squat",
                    "exercise_variant": "high_bar",
                    "filename": "squat.mp4",
                    "file_size_bytes": 5_000_000,
                },
            )
            assert resp.status_code == 201, f"Create failed: {resp.text}"
            data = resp.json()
            assert data["status"] == "queued"
            assert "upload_url" in data

            # List
            resp = await client.get("/api/v1/analyses")
            assert resp.status_code == 200
            items = resp.json()
            assert len(items) >= 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(_get_service, None)


# ---------------------------------------------------------------------------
# E2E: Worker pipeline flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_full_pipeline_flow():
    """
    Worker E2E: queued → quality_gate_pending → processing → coaching → completed.

    Verifies:
    - All status transitions occur in correct order
    - Rep metrics are persisted
    - Coaching service is called with correct args
    - Coaching result is stored in DB
    - Final status is completed
    """
    analysis_id = uuid.uuid4()
    redis = AsyncMock()

    # Mock analysis
    analysis = MagicMock()
    analysis.id = analysis_id
    analysis.status = "queued"
    analysis.retry_count = 0
    analysis.user_id = _USER_ID
    analysis.exercise_type = "squat"
    analysis.exercise_variant = "high_bar"
    analysis.confidence_score = None
    analysis.video_path = f"videos/{analysis_id}/squat.mp4"
    analysis.quality_gate_result = None
    analysis.annotated_video_path = None
    analysis.plot_path = None
    analysis.summary_json = None
    analysis.error_message = None

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis
    mock_repo._db = MagicMock()

    statuses: list[str] = []

    async def track_update(a: Any) -> Any:
        statuses.append(a.status)
        return a

    mock_repo.update.side_effect = track_update

    # Mock CV pipeline — returns a PipelineResult so the worker can access
    # .keyframes, .bar_path, etc. (Phase 1 worker reads these post-pipeline).
    async def mock_cv_pipeline(**kwargs: Any) -> Any:
        from app.services.pipeline import PipelineResult
        from app.services.status import transition

        a = kwargs["analysis"]
        repo = kwargs["repo"]
        a.status = transition(a.status, "quality_gate_pending")
        a.quality_gate_result = {"passed": True, "status": "passed", "checks": []}
        await repo.update(a)
        a.status = transition(a.status, "processing")
        a.confidence_score = 0.85
        await repo.update(a)

        result = PipelineResult()
        result.keyframes = []
        result.bar_path = None
        return result

    # Mock coaching
    coaching_output = _mock_coaching_output()
    coaching_created: list[Any] = []

    mock_coaching_repo = AsyncMock()

    async def capture_coaching(cr: Any) -> Any:
        coaching_created.append(cr)
        return cr

    mock_coaching_repo.create.side_effect = capture_coaching

    mock_rep_repo = AsyncMock()
    mock_rep = MagicMock()
    mock_rep.rep_index = 0
    mock_rep.metrics_json = {"depth_angle": 85.0, "knee_angle_at_depth": 90.0}
    mock_rep_repo.get_by_analysis.return_value = [mock_rep]

    mock_summary_svc = AsyncMock()
    mock_summary_svc.compute_and_store.return_value = {}

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_sf, patch(
        "app.workers.analysis_worker.run_cv_pipeline",
        side_effect=mock_cv_pipeline,
    ), patch(
        "app.workers.analysis_worker.CoachingResultRepository",
        return_value=mock_coaching_repo,
    ), patch(
        "app.workers.analysis_worker.RepMetricRepository",
        return_value=mock_rep_repo,
    ), patch(
        "app.workers.analysis_worker.CoachingService",
    ) as MockCS, patch(
        "app.workers.analysis_worker.anthropic",
    ), patch(
        "app.workers.analysis_worker.ThresholdConfig",
    ), patch(
        "app.workers.analysis_worker.cleanup_temp_files",
    ), patch(
        "app.workers.analysis_worker.SummaryService",
        return_value=mock_summary_svc,
    ), patch(
        "app.workers.analysis_worker._generate_and_upload_pdf",
        new_callable=AsyncMock,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = mock_session

        mock_svc = AsyncMock()
        # Phase 1 uses SSE streaming coaching (FR-AICP-07); Phase 0
        # generate_coaching is deprecated.
        mock_svc.generate_coaching_streaming.return_value = coaching_output
        MockCS.return_value = mock_svc

        from app.workers.analysis_worker import process_analysis

        await process_analysis({"redis": redis}, analysis_id)

    # Verify full transition chain
    assert "quality_gate_pending" in statuses
    assert "processing" in statuses
    assert "coaching" in statuses
    assert "completed" in statuses
    assert statuses[-1] == "completed"

    # Verify coaching was called
    mock_svc.generate_coaching_streaming.assert_called_once()
    call_kwargs = mock_svc.generate_coaching_streaming.call_args[1]
    assert call_kwargs["exercise_type"] == "squat"
    assert call_kwargs["exercise_variant"] == "high_bar"

    # Verify coaching result persisted
    assert len(coaching_created) == 1
    cr = coaching_created[0]
    assert cr.analysis_id == analysis_id
    assert cr.structured_output_json["summary"] == coaching_output.summary
    assert cr.stream_complete is True

    # Verify rep metrics were fetched for coaching
    mock_rep_repo.get_by_analysis.assert_called_once_with(analysis_id)

    # Verify heartbeat written
    redis.set.assert_called()
    heartbeat_calls = [
        c for c in redis.set.call_args_list
        if c.args and c.args[0] == "spelix:worker:heartbeat"
    ]
    assert len(heartbeat_calls) >= 1


@pytest.mark.asyncio
async def test_worker_quality_gate_rejection():
    """Worker correctly handles quality gate rejection — terminal state."""
    analysis_id = uuid.uuid4()
    redis = AsyncMock()

    analysis = MagicMock()
    analysis.id = analysis_id
    analysis.status = "queued"
    analysis.retry_count = 0
    analysis.error_message = None

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis
    mock_repo._db = MagicMock()

    statuses: list[str] = []

    async def track(a: Any) -> Any:
        statuses.append(a.status)
        return a

    mock_repo.update.side_effect = track

    from app.services.pipeline import QualityGateRejection

    async def mock_cv_reject(**kwargs: Any) -> None:
        from app.services.status import transition

        a = kwargs["analysis"]
        repo = kwargs["repo"]
        a.status = transition(a.status, "quality_gate_pending")
        await repo.update(a)
        a.status = transition(a.status, "quality_gate_rejected")
        await repo.update(a)
        raise QualityGateRejection("Body not visible")

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_sf, patch(
        "app.workers.analysis_worker.run_cv_pipeline",
        side_effect=mock_cv_reject,
    ), patch(
        "app.workers.analysis_worker.cleanup_temp_files",
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis({"redis": redis}, analysis_id)

    # Should stop at quality_gate_rejected — no coaching, no completed
    assert "quality_gate_pending" in statuses
    assert "quality_gate_rejected" in statuses
    assert "coaching" not in statuses
    assert "completed" not in statuses
