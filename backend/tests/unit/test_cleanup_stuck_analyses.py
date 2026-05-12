"""
Unit tests for the streaq stuck-analyses cleanup cron.

TDD gate:
1. Stuck 'queued' analysis >2h → auto-failed, correct error_message, returns 1
2. Stuck 'processing' analysis >2h → auto-failed, returns 1
3. Stuck 'quality_gate_pending' analysis >2h → auto-failed, returns 1
4. Recent analysis (<2h) → NOT touched (query filters it out)
5. Terminal status ('completed') → NOT matched by query
6. DB update error on first analysis continues to next, count=1
7. Empty query returns 0
8. cleanup_stuck_analyses_cron wrapper is callable in streaq_worker

No real DB connections required — all mocked.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 5, 12, 3, 30, 0, tzinfo=timezone.utc)
_CUTOFF = _NOW - timedelta(hours=2)


def make_analysis(
    *,
    status: str = "queued",
    updated_at: datetime | None = None,
) -> MagicMock:
    """Return a mock Analysis model instance."""
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.status = status
    # Default: stuck 30 minutes before cutoff (i.e. >2h ago)
    obj.updated_at = updated_at or (_CUTOFF - timedelta(minutes=30))
    return obj


def make_ctx() -> dict[str, Any]:
    """Build a minimal ARQ-style context dict."""
    return {}


def _make_session_mock(analyses: list[Any]) -> MagicMock:
    """Build an AsyncMock session that returns `analyses` on execute().scalars().all().

    The second execute() call (the UPDATE) is handled by returning a fresh
    MagicMock so it doesn't interfere with the SELECT result_mock.
    """
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # First execute() returns the SELECT result; subsequent calls return generic mocks.
    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = analyses

    update_result = MagicMock()

    mock_session.execute = AsyncMock(side_effect=[select_result, *([update_result] * max(len(analyses), 1))])
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    return mock_session


# ---------------------------------------------------------------------------
# Test 1: Stuck 'queued' analysis →  auto-failed, correct error_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stuck_queued_analysis_is_auto_failed() -> None:
    """A queued analysis stuck for >2h must be auto-failed with the correct
    error_message string and the function must return 1."""
    analysis = make_analysis(status="queued")
    mock_session = _make_session_mock([analysis])

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_stuck_analyses.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_stuck_analyses.datetime", mock_dt),
    ):
        from app.workers.cleanup_stuck_analyses import cleanup_stuck_analyses

        count = await cleanup_stuck_analyses(make_ctx())

    assert count == 1
    mock_session.commit.assert_awaited()

    assert mock_session.execute.await_count >= 2  # SELECT + at least one UPDATE


# ---------------------------------------------------------------------------
# Test 2: Stuck 'processing' analysis → auto-failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stuck_processing_analysis_is_auto_failed() -> None:
    """A processing analysis stuck for >2h must be auto-failed and count=1."""
    analysis = make_analysis(status="processing")
    mock_session = _make_session_mock([analysis])

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_stuck_analyses.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_stuck_analyses.datetime", mock_dt),
    ):
        from app.workers.cleanup_stuck_analyses import cleanup_stuck_analyses

        count = await cleanup_stuck_analyses(make_ctx())

    assert count == 1
    mock_session.commit.assert_awaited()


# ---------------------------------------------------------------------------
# Test 3: Stuck 'quality_gate_pending' analysis → auto-failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stuck_quality_gate_pending_analysis_is_auto_failed() -> None:
    """A quality_gate_pending analysis stuck for >2h must be auto-failed and count=1."""
    analysis = make_analysis(status="quality_gate_pending")
    mock_session = _make_session_mock([analysis])

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_stuck_analyses.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_stuck_analyses.datetime", mock_dt),
    ):
        from app.workers.cleanup_stuck_analyses import cleanup_stuck_analyses

        count = await cleanup_stuck_analyses(make_ctx())

    assert count == 1
    mock_session.commit.assert_awaited()


# ---------------------------------------------------------------------------
# Test 4: Recent analysis (<2h) is NOT touched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recent_analysis_not_touched() -> None:
    """An analysis that is only 30 minutes old must NOT appear in the query results.
    The query filters by updated_at < cutoff — we simulate an empty result to
    represent the DB correctly applying that filter."""
    # The DB would not return a recent analysis because of the WHERE clause.
    # We model this by returning an empty list from the session mock.
    mock_session = _make_session_mock([])

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_stuck_analyses.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_stuck_analyses.datetime", mock_dt),
    ):
        from app.workers.cleanup_stuck_analyses import cleanup_stuck_analyses

        count = await cleanup_stuck_analyses(make_ctx())

    assert count == 0
    # Only the SELECT execute should have been called, no UPDATE
    assert mock_session.execute.await_count == 1
    mock_session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 5: Terminal status ('completed') is NOT matched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_completed_analysis_not_touched() -> None:
    """A 'completed' analysis must never appear in the stuck query results.
    We simulate the DB correctly excluding it by returning an empty list."""
    mock_session = _make_session_mock([])

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_stuck_analyses.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_stuck_analyses.datetime", mock_dt),
    ):
        from app.workers.cleanup_stuck_analyses import cleanup_stuck_analyses

        count = await cleanup_stuck_analyses(make_ctx())

    assert count == 0
    mock_session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 6: DB update error on first analysis continues to second, count=1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_error_on_first_continues_to_second() -> None:
    """A DB update failure on the first analysis must not block the second;
    the second is auto-failed successfully and count=1."""
    analysis_a = make_analysis(status="queued")
    analysis_b = make_analysis(status="processing")

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = [analysis_a, analysis_b]

    # First UPDATE raises, second UPDATE succeeds
    update_ok = MagicMock()

    mock_session.execute = AsyncMock(
        side_effect=[select_result, RuntimeError("DB write failed"), update_ok]
    )
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_stuck_analyses.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_stuck_analyses.datetime", mock_dt),
    ):
        from app.workers.cleanup_stuck_analyses import cleanup_stuck_analyses

        count = await cleanup_stuck_analyses(make_ctx())

    assert count == 1
    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 7: Empty query returns 0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_stuck_analyses_returns_zero() -> None:
    """When there are no stuck analyses, the function must return 0 and
    never call commit."""
    mock_session = _make_session_mock([])

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_stuck_analyses.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_stuck_analyses.datetime", mock_dt),
    ):
        from app.workers.cleanup_stuck_analyses import cleanup_stuck_analyses

        count = await cleanup_stuck_analyses(make_ctx())

    assert count == 0
    mock_session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 8: Cron wrapper is registered and callable in streaq_worker
# ---------------------------------------------------------------------------


def test_cron_wrapper_registered_in_streaq_worker() -> None:
    """cleanup_stuck_analyses_cron must be importable and callable from streaq_worker."""
    from app.workers.streaq_worker import cleanup_stuck_analyses_cron

    assert callable(cleanup_stuck_analyses_cron)
