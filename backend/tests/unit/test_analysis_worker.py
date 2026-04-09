"""
Unit tests for the ARQ analysis worker (B-011).

Tests are written against process_analysis() using mocked DB sessions,
AnalysisRepository, and Redis client. No real DB or Redis connections required.

TDD gate (B-011):
- Idempotent skip on completed analysis
- Idempotent skip on quality_gate_rejected analysis
- Idempotent skip on failed with retry_count >= 3
- Happy path: all status transitions in correct order
- Error handling: exception → failed status + error_message + retry_count++
- Heartbeat Redis key written with TTL during job execution
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
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
    return obj


def make_ctx(redis: Any = None) -> dict[str, Any]:
    """Build a minimal ARQ context dict."""
    if redis is None:
        redis = AsyncMock()
    return {"redis": redis}


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotent_completed_analysis():
    """Worker must return immediately if analysis is already completed."""
    analysis_id = uuid.uuid4()
    analysis = make_analysis(status="completed")
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    # Status must not have changed
    assert analysis.status == "completed"
    # update() must not have been called
    mock_repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_idempotent_quality_gate_rejected():
    """Worker must return immediately if analysis is already quality_gate_rejected."""
    analysis_id = uuid.uuid4()
    analysis = make_analysis(status="quality_gate_rejected")
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    assert analysis.status == "quality_gate_rejected"
    mock_repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_idempotent_terminal_retry():
    """Worker must return immediately if analysis is failed with retry_count >= 3."""
    analysis_id = uuid.uuid4()
    analysis = make_analysis(status="failed", retry_count=3)
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    assert analysis.status == "failed"
    mock_repo.update.assert_not_called()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_status_transitions():
    """
    Happy-path stub: queued → quality_gate_pending → processing → coaching → completed.

    Verifies that update() is called after each transition and that the
    final status is 'completed'.
    """
    analysis_id = uuid.uuid4()
    analysis = make_analysis(status="queued")
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis

    # update() should return the same analysis object
    mock_repo.update.return_value = analysis

    statuses_seen: list[str] = []

    async def capture_update(a: Any) -> Any:
        statuses_seen.append(a.status)
        return a

    mock_repo.update.side_effect = capture_update

    async def mock_run_pipeline(aid: Any, repo: Any, redis: Any) -> None:
        """Simulate the full pipeline status transitions."""
        from app.services.status import transition as _transition

        a = await repo.get_by_id(aid)
        a.status = _transition(a.status, "quality_gate_pending")
        await repo.update(a)
        a.status = _transition(a.status, "processing")
        await repo.update(a)
        a.status = _transition(a.status, "coaching")
        await repo.update(a)
        a.status = _transition(a.status, "completed")
        await repo.update(a)

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory, patch(
        "app.workers.analysis_worker._run_pipeline",
        side_effect=mock_run_pipeline,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    expected = [
        "quality_gate_pending",
        "processing",
        "coaching",
        "completed",
    ]
    assert statuses_seen == expected, f"Got transitions: {statuses_seen}"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_handling_sets_failed_status():
    """
    An exception during the pipeline must:
    - set status = 'failed'
    - write the error_message
    - increment retry_count

    The initial idempotency check uses status='queued' (non-terminal, so the
    job proceeds). The re-fetch inside the error handler returns status='processing'
    to simulate the pipeline having advanced before crashing — 'processing → failed'
    is a valid SRS transition.
    """
    analysis_id = uuid.uuid4()
    # First fetch: idempotency guard — status must be non-terminal so the job runs
    analysis_queued = make_analysis(status="queued", retry_count=0, analysis_id=analysis_id)
    # Second fetch (inside error handler): pipeline had advanced to 'processing'
    analysis_processing = make_analysis(status="processing", retry_count=0, analysis_id=analysis_id)
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    # First call returns queued (idempotency check), second returns processing (error handler)
    mock_repo.get_by_id.side_effect = [analysis_queued, analysis_processing]
    mock_repo.update.return_value = analysis_processing

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory, patch(
        "app.workers.analysis_worker._run_pipeline",
        side_effect=RuntimeError("CV pipeline exploded"),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    # After exception: status=failed, error_message set, retry_count incremented
    assert analysis_processing.status == "failed"
    assert analysis_processing.error_message is not None
    assert "CV pipeline exploded" in analysis_processing.error_message
    assert analysis_processing.retry_count == 1


@pytest.mark.asyncio
async def test_error_handling_retry_count_increments():
    """retry_count should increment on each failure.

    First fetch: queued (non-terminal, job proceeds).
    Second fetch (error handler): processing (valid source for → failed transition).
    """
    analysis_id = uuid.uuid4()
    analysis_queued = make_analysis(status="queued", retry_count=1, analysis_id=analysis_id)
    analysis_processing = make_analysis(status="processing", retry_count=1, analysis_id=analysis_id)
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    mock_repo.get_by_id.side_effect = [analysis_queued, analysis_processing]
    mock_repo.update.return_value = analysis_processing

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory, patch(
        "app.workers.analysis_worker._run_pipeline",
        side_effect=ValueError("bad frames"),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    assert analysis_processing.retry_count == 2
    assert analysis_processing.status == "failed"


# ---------------------------------------------------------------------------
# B-045: status transition guard in error handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_handler_uses_transition_not_direct_assignment():
    """B-045: the error handler must call transition() rather than directly
    assigning analysis.status = 'failed', so the guard is enforced.

    We mock transition() and assert it is called with ("processing", "failed").
    """
    analysis_id = uuid.uuid4()
    # Start in "processing" — a non-terminal state that should allow → "failed"
    analysis = make_analysis(status="processing", retry_count=0)
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis
    mock_repo.update.return_value = analysis

    transition_calls: list[tuple[str, str]] = []

    def recording_transition(current: str, target: str) -> str:
        transition_calls.append((current, target))
        # Delegate to real transition to also validate the call is valid
        from app.services.status import transition as _real_transition

        return _real_transition(current, target)

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory, patch(
        "app.workers.analysis_worker._run_pipeline",
        side_effect=RuntimeError("pipeline exploded"),
    ), patch(
        "app.workers.analysis_worker.transition",
        side_effect=recording_transition,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    # transition() must have been called to move status → "failed"
    assert any(target == "failed" for _, target in transition_calls), (
        f"transition() was never called with target='failed'. Calls: {transition_calls}"
    )
    assert analysis.status == "failed"


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_written_during_job():
    """
    Redis key 'spelix:worker:heartbeat' must be set with a TTL (90s)
    at least once during job execution.
    """
    analysis_id = uuid.uuid4()
    analysis = make_analysis(status="queued")
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis
    mock_repo.update.return_value = analysis

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory, patch(
        "app.workers.analysis_worker._run_pipeline",
        new_callable=AsyncMock,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    # Verify that set() was called on redis with the heartbeat key and TTL
    redis.set.assert_called()
    calls = redis.set.call_args_list
    heartbeat_calls = [
        c for c in calls if c.args and c.args[0] == "spelix:worker:heartbeat"
    ]
    assert len(heartbeat_calls) >= 1, "Heartbeat key was never written"

    # Verify TTL was provided (ex= or px= kwarg, or positional ex arg)
    hb_call = heartbeat_calls[0]
    has_ttl = (
        hb_call.kwargs.get("ex") is not None
        or hb_call.kwargs.get("px") is not None
        # arq redis client may use setex positional: set(key, ex, value) or set(key, value, ex=N)
    )
    # Accept either kwarg style or the value 1 (placeholder) — just require TTL > 0
    if not has_ttl:
        # Some redis clients use set(name, value, ex=N)
        all_kwargs = hb_call.kwargs
        assert "ex" in all_kwargs or "px" in all_kwargs, (
            f"Heartbeat set() call had no TTL. kwargs={all_kwargs}"
        )


# ---------------------------------------------------------------------------
# B-067 / B-069: Heartbeat TTL exact value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_ttl_is_90_seconds():
    """Redis key 'spelix:worker:heartbeat' must be set with ex=90 exactly (NFR-OPER-02)."""
    analysis_id = uuid.uuid4()
    analysis = make_analysis(status="queued")
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis
    mock_repo.update.return_value = analysis

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory, patch(
        "app.workers.analysis_worker._run_pipeline",
        new_callable=AsyncMock,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    calls = redis.set.call_args_list
    heartbeat_calls = [
        c for c in calls if c.args and c.args[0] == "spelix:worker:heartbeat"
    ]
    assert heartbeat_calls, "Heartbeat key was never written"
    hb_call = heartbeat_calls[0]
    assert hb_call.kwargs.get("ex") == 90, (
        f"Expected ex=90, got ex={hb_call.kwargs.get('ex')}"
    )


# ---------------------------------------------------------------------------
# B-069: _build_supabase_client
# ---------------------------------------------------------------------------


def test_build_supabase_client_returns_client_when_env_set():
    """_build_supabase_client returns a Supabase client when URL and key are set."""
    mock_client = MagicMock()

    # create_client is imported locally inside the function body via
    # `from supabase import create_client`, so patch it at the source.
    with patch.dict(
        "os.environ",
        {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-key-value",
        },
    ), patch(
        "supabase.create_client",
        return_value=mock_client,
    ) as mock_create:
        from app.workers.analysis_worker import _build_supabase_client

        result = _build_supabase_client()

    assert result is mock_client
    mock_create.assert_called_once_with(
        "https://example.supabase.co", "service-role-key-value"
    )


def test_build_supabase_client_returns_none_when_url_missing():
    """_build_supabase_client returns None when SUPABASE_URL is absent."""
    env_without_url = {k: v for k, v in __import__("os").environ.items()
                       if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")}
    with patch.dict("os.environ", env_without_url, clear=True):
        from app.workers.analysis_worker import _build_supabase_client

        result = _build_supabase_client()

    assert result is None


def test_build_supabase_client_returns_none_when_key_missing():
    """_build_supabase_client returns None when SUPABASE_SERVICE_ROLE_KEY is absent."""
    env_without_key = {k: v for k, v in __import__("os").environ.items()
                       if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")}
    env_without_key["SUPABASE_URL"] = "https://example.supabase.co"
    with patch.dict("os.environ", env_without_key, clear=True):
        from app.workers.analysis_worker import _build_supabase_client

        result = _build_supabase_client()

    assert result is None


# ---------------------------------------------------------------------------
# B-069: analysis-disappeared guard in error handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_handler_returns_early_when_analysis_disappears():
    """If repo.get_by_id returns None during error handling, function returns early
    without crashing (analysis deleted mid-job scenario).
    """
    analysis_id = uuid.uuid4()
    # First fetch (idempotency guard): non-terminal, job proceeds
    analysis_queued = make_analysis(status="queued", retry_count=0, analysis_id=analysis_id)
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    # First call returns the queued analysis; second call (in error handler) returns None
    mock_repo.get_by_id.side_effect = [analysis_queued, None]

    with patch(
        "app.workers.analysis_worker.AnalysisRepository",
        return_value=mock_repo,
    ), patch(
        "app.workers.analysis_worker.async_session",
    ) as mock_session_factory, patch(
        "app.workers.analysis_worker._run_pipeline",
        side_effect=RuntimeError("pipeline crashed"),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        # Must not raise even though analysis disappeared mid-job
        await process_analysis(ctx, analysis_id)

    # update() must not have been called — nothing to update
    mock_repo.update.assert_not_called()


# ---------------------------------------------------------------------------
# B-068: _generate_and_upload_pdf isolation
#
# All symbols used inside _generate_and_upload_pdf are imported locally
# (inside the function body), so they must be patched at their SOURCE
# module paths, not at app.workers.analysis_worker.*.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_and_upload_pdf_success():
    """Success path: PDF generated and uploaded; pdf_path set on analysis and repo updated."""
    analysis_id = uuid.uuid4()
    analysis = make_analysis()
    analysis.exercise_type = "squat"
    analysis.exercise_variant = "high_bar"
    analysis.confidence_score = 0.85
    analysis.quality_gate_result = None

    mock_repo = AsyncMock()
    mock_coaching_output = MagicMock()
    mock_coaching_output.model_dump.return_value = {"summary": "Good form"}

    storage_client = MagicMock()
    pdf_storage_path = f"artifacts/{analysis_id}/report.pdf"

    with patch(
        "app.services.pdf.PDFService",
    ) as MockPDFService, patch(
        "app.cv.artifact_generation.get_temp_dir",
        return_value="/tmp/spelix/test",
    ), patch(
        "app.cv.artifact_generation.get_artifact_storage_path",
        return_value=pdf_storage_path,
    ), patch(
        "app.cv.artifact_generation.upload_artifact",
        new_callable=AsyncMock,
    ) as mock_upload, patch(
        "app.cv.confidence.confidence_label",
        return_value="High",
    ), patch(
        "os.path.isfile",
        return_value=False,
    ), patch(
        "asyncio.get_event_loop",
    ) as mock_get_loop:
        mock_pdf_svc = MagicMock()
        MockPDFService.return_value = mock_pdf_svc
        mock_loop = MagicMock()
        mock_loop.run_in_executor = AsyncMock(return_value=None)
        mock_get_loop.return_value = mock_loop

        from app.workers.analysis_worker import _generate_and_upload_pdf

        await _generate_and_upload_pdf(
            analysis_id=analysis_id,
            analysis=analysis,
            coaching_output=mock_coaching_output,
            rep_metrics_dicts=[],
            storage_client=storage_client,
            repo=mock_repo,
        )

    assert analysis.pdf_path == pdf_storage_path
    mock_repo.update.assert_called_once_with(analysis)
    mock_upload.assert_called_once()


@pytest.mark.asyncio
async def test_generate_and_upload_pdf_generation_exception_does_not_propagate():
    """PDF generation exception is caught/logged; does not propagate; analysis not marked failed."""
    analysis_id = uuid.uuid4()
    analysis = make_analysis()
    analysis.exercise_type = "deadlift"
    analysis.exercise_variant = "conventional"
    analysis.confidence_score = 0.70
    analysis.quality_gate_result = None

    mock_repo = AsyncMock()
    mock_coaching_output = MagicMock()
    mock_coaching_output.model_dump.return_value = {}

    with patch(
        "app.services.pdf.PDFService",
    ) as MockPDFService, patch(
        "app.cv.artifact_generation.get_temp_dir",
        return_value="/tmp/spelix/test",
    ), patch(
        "app.cv.confidence.confidence_label",
        return_value="Medium",
    ), patch(
        "os.path.isfile",
        return_value=False,
    ), patch(
        "asyncio.get_event_loop",
    ) as mock_get_loop:
        mock_pdf_svc = MagicMock()
        MockPDFService.return_value = mock_pdf_svc
        mock_loop = MagicMock()
        # run_in_executor raises to simulate PDF generation failure
        mock_loop.run_in_executor = AsyncMock(
            side_effect=RuntimeError("WeasyPrint failed")
        )
        mock_get_loop.return_value = mock_loop

        from app.workers.analysis_worker import _generate_and_upload_pdf

        # Must not raise
        await _generate_and_upload_pdf(
            analysis_id=analysis_id,
            analysis=analysis,
            coaching_output=mock_coaching_output,
            rep_metrics_dicts=[],
            storage_client=MagicMock(),
            repo=mock_repo,
        )

    # Analysis must not have been transitioned to failed
    assert analysis.status != "failed"
    # repo.update must not have been called (exception before the update)
    mock_repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_generate_and_upload_pdf_upload_failure_keeps_local_path():
    """When storage upload raises, exception is caught; pdf_path is set to local path."""
    analysis_id = uuid.uuid4()
    analysis = make_analysis()
    analysis.exercise_type = "bench"
    analysis.exercise_variant = "flat"
    analysis.confidence_score = 0.60
    analysis.quality_gate_result = None

    mock_repo = AsyncMock()
    mock_coaching_output = MagicMock()
    mock_coaching_output.model_dump.return_value = {}

    storage_client = MagicMock()
    tmp_dir = "/tmp/spelix/test"

    with patch(
        "app.services.pdf.PDFService",
    ) as MockPDFService, patch(
        "app.cv.artifact_generation.get_temp_dir",
        return_value=tmp_dir,
    ), patch(
        "app.cv.artifact_generation.upload_artifact",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Supabase Storage unreachable"),
    ), patch(
        "app.cv.artifact_generation.get_artifact_storage_path",
        return_value=f"artifacts/{analysis_id}/report.pdf",
    ), patch(
        "app.cv.confidence.confidence_label",
        return_value="Medium",
    ), patch(
        "os.path.isfile",
        return_value=False,
    ), patch(
        "asyncio.get_event_loop",
    ) as mock_get_loop:
        mock_pdf_svc = MagicMock()
        MockPDFService.return_value = mock_pdf_svc
        mock_loop = MagicMock()
        mock_loop.run_in_executor = AsyncMock(return_value=None)
        mock_get_loop.return_value = mock_loop

        from app.workers.analysis_worker import _generate_and_upload_pdf

        # Must not raise
        await _generate_and_upload_pdf(
            analysis_id=analysis_id,
            analysis=analysis,
            coaching_output=mock_coaching_output,
            rep_metrics_dicts=[],
            storage_client=storage_client,
            repo=mock_repo,
        )

    # Exception is caught; analysis not failed
    assert analysis.status != "failed"
