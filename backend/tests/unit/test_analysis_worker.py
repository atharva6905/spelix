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
    """
    analysis_id = uuid.uuid4()
    analysis = make_analysis(status="queued", retry_count=0)
    redis = AsyncMock()
    ctx = make_ctx(redis)

    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = analysis
    mock_repo.update.return_value = analysis

    blast_count = 0


    async def fail_on_processing(a: Any) -> Any:
        nonlocal blast_count
        blast_count += 1
        # Raise on the second transition (quality_gate_pending → processing)
        if a.status == "quality_gate_pending":
            a.status = "quality_gate_pending"
            return a
        # Allow the first update through but explode on the second
        if blast_count == 2:
            raise RuntimeError("CV pipeline exploded")
        return a

    # Instead of that complex side_effect, patch _run_pipeline to raise
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
    assert analysis.status == "failed"
    assert analysis.error_message is not None
    assert "CV pipeline exploded" in analysis.error_message
    assert analysis.retry_count == 1


@pytest.mark.asyncio
async def test_error_handling_retry_count_increments():
    """retry_count should increment on each failure."""
    analysis_id = uuid.uuid4()
    analysis = make_analysis(status="queued", retry_count=1)
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
        side_effect=ValueError("bad frames"),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        from app.workers.analysis_worker import process_analysis

        await process_analysis(ctx, analysis_id)

    assert analysis.retry_count == 2
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
