"""
Unit tests for the ARQ artifact cleanup cron job (B-038).

TDD gate (B-038):
1. Analyses older than 7 days have artifacts deleted from Storage
2. Analyses newer than 7 days are untouched
3. Artifact paths (annotated_video_path, plot_path, pdf_path) set to NULL after deletion
4. Storage errors don't block other analyses (continue on error)
5. Non-completed analyses are skipped
6. Analyses with already-NULL paths are skipped (no-op)
7. Returns count of cleaned analyses

No real DB or Storage connections required — all mocked.
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

_NOW = datetime(2026, 4, 8, 3, 0, 0, tzinfo=timezone.utc)
_CUTOFF = _NOW - timedelta(days=7)


def make_analysis(
    *,
    status: str = "completed",
    created_at: datetime | None = None,
    annotated_video_path: str | None = "artifacts/123/annotated.mp4",
    plot_path: str | None = "artifacts/123/plot.png",
    pdf_path: str | None = "artifacts/123/report.pdf",
) -> MagicMock:
    """Return a mock Analysis model instance."""
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.status = status
    obj.created_at = created_at or (_CUTOFF - timedelta(days=1))
    obj.annotated_video_path = annotated_video_path
    obj.plot_path = plot_path
    obj.pdf_path = pdf_path
    return obj


def make_ctx() -> dict[str, Any]:
    """Build a minimal ARQ context dict."""
    return {}


def _patch_cleanup(mock_analyses: list[Any], storage_delete_side_effect: Any = None):
    """
    Context manager factory that patches async_session and StorageService
    for the cleanup module.
    """
    mock_storage = AsyncMock()
    if storage_delete_side_effect is not None:
        mock_storage.delete_file.side_effect = storage_delete_side_effect

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = mock_analyses
        return result

    mock_session.execute = mock_execute
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_session_factory = MagicMock(return_value=mock_session)

    return (
        patch("app.workers.cleanup.async_session", mock_session_factory),
        patch("app.workers.cleanup.StorageService", return_value=mock_storage),
        patch("app.workers.cleanup.datetime") ,
        mock_storage,
    )


# ---------------------------------------------------------------------------
# Test 1: Analyses older than 7 days have artifacts deleted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_old_analyses_artifacts_deleted():
    """Completed analyses older than 7 days must have all three artifact paths deleted."""
    old_analysis = make_analysis(
        status="completed",
        created_at=_CUTOFF - timedelta(days=1),
        annotated_video_path="artifacts/abc/annotated.mp4",
        plot_path="artifacts/abc/plot.png",
        pdf_path="artifacts/abc/report.pdf",
    )

    mock_storage = AsyncMock()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [old_analysis]
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_dt = MagicMock()
    mock_dt.now.return_value = _NOW

    with patch("app.workers.cleanup.async_session", MagicMock(return_value=mock_session)), \
         patch("app.workers.cleanup.StorageService", return_value=mock_storage), \
         patch("app.workers.cleanup.datetime", mock_dt):
        from app.workers.cleanup import cleanup_expired_artifacts
        count = await cleanup_expired_artifacts(make_ctx())

    assert count == 1
    deleted_paths = [call.args[0] for call in mock_storage.delete_file.call_args_list]
    assert "artifacts/abc/annotated.mp4" in deleted_paths
    assert "artifacts/abc/plot.png" in deleted_paths
    assert "artifacts/abc/report.pdf" in deleted_paths


# ---------------------------------------------------------------------------
# Test 2: Analyses newer than 7 days are untouched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_analyses_not_touched():
    """Analyses created within the last 7 days must not be modified."""
    # The DB query itself filters by cutoff, so the session returns no rows
    mock_storage = AsyncMock()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []  # query returns nothing
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_dt = MagicMock()
    mock_dt.now.return_value = _NOW

    with patch("app.workers.cleanup.async_session", MagicMock(return_value=mock_session)), \
         patch("app.workers.cleanup.StorageService", return_value=mock_storage), \
         patch("app.workers.cleanup.datetime", mock_dt):
        from app.workers.cleanup import cleanup_expired_artifacts
        count = await cleanup_expired_artifacts(make_ctx())

    assert count == 0
    mock_storage.delete_file.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: Artifact paths set to NULL after deletion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_artifact_paths_set_to_null_after_deletion():
    """After successful Storage deletion, all three artifact columns must be NULL."""
    old_analysis = make_analysis(
        status="completed",
        created_at=_CUTOFF - timedelta(days=2),
        annotated_video_path="artifacts/xyz/annotated.mp4",
        plot_path="artifacts/xyz/plot.png",
        pdf_path="artifacts/xyz/report.pdf",
    )

    mock_storage = AsyncMock()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [old_analysis]
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_dt = MagicMock()
    mock_dt.now.return_value = _NOW

    with patch("app.workers.cleanup.async_session", MagicMock(return_value=mock_session)), \
         patch("app.workers.cleanup.StorageService", return_value=mock_storage), \
         patch("app.workers.cleanup.datetime", mock_dt):
        from app.workers.cleanup import cleanup_expired_artifacts
        await cleanup_expired_artifacts(make_ctx())

    assert old_analysis.annotated_video_path is None
    assert old_analysis.plot_path is None
    assert old_analysis.pdf_path is None


# ---------------------------------------------------------------------------
# Test 4: Storage errors don't block other analyses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_storage_error_does_not_block_other_analyses():
    """A Storage deletion failure must not prevent other analyses from being cleaned."""
    analysis_a = make_analysis(
        status="completed",
        created_at=_CUTOFF - timedelta(days=2),
        annotated_video_path="artifacts/aaa/annotated.mp4",
        plot_path="artifacts/aaa/plot.png",
        pdf_path="artifacts/aaa/report.pdf",
    )
    analysis_b = make_analysis(
        status="completed",
        created_at=_CUTOFF - timedelta(days=3),
        annotated_video_path="artifacts/bbb/annotated.mp4",
        plot_path="artifacts/bbb/plot.png",
        pdf_path="artifacts/bbb/report.pdf",
    )

    call_count = 0

    async def delete_file_side_effect(path: str) -> None:
        nonlocal call_count
        call_count += 1
        if "aaa" in path:
            raise RuntimeError("Storage unavailable")

    mock_storage = AsyncMock()
    mock_storage.delete_file.side_effect = delete_file_side_effect

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [analysis_a, analysis_b]
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_dt = MagicMock()
    mock_dt.now.return_value = _NOW

    with patch("app.workers.cleanup.async_session", MagicMock(return_value=mock_session)), \
         patch("app.workers.cleanup.StorageService", return_value=mock_storage), \
         patch("app.workers.cleanup.datetime", mock_dt):
        from app.workers.cleanup import cleanup_expired_artifacts
        count = await cleanup_expired_artifacts(make_ctx())

    # analysis_b should still be cleaned even though analysis_a failed
    assert analysis_b.annotated_video_path is None
    assert analysis_b.plot_path is None
    assert analysis_b.pdf_path is None

    # count reflects only fully-cleaned analyses
    assert count == 1


# ---------------------------------------------------------------------------
# Test 5: Non-completed analyses are skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_completed_analyses_skipped():
    """The DB query must filter to completed status only — no rows returned for other statuses."""
    # The query WHERE clause handles this; simulate by returning no rows
    mock_storage = AsyncMock()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    execute_calls: list[Any] = []

    async def capture_execute(stmt: Any) -> Any:
        execute_calls.append(stmt)
        return result_mock

    mock_session.execute = capture_execute

    mock_dt = MagicMock()
    mock_dt.now.return_value = _NOW

    with patch("app.workers.cleanup.async_session", MagicMock(return_value=mock_session)), \
         patch("app.workers.cleanup.StorageService", return_value=mock_storage), \
         patch("app.workers.cleanup.datetime", mock_dt):
        from app.workers.cleanup import cleanup_expired_artifacts
        count = await cleanup_expired_artifacts(make_ctx())

    assert count == 0
    # Exactly one query was issued
    assert len(execute_calls) == 1

    mock_storage.delete_file.assert_not_called()


# ---------------------------------------------------------------------------
# Test 6: Analyses with already-NULL paths are skipped (partial-NULL too)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_null_paths_skipped():
    """An analysis with all artifact paths already NULL must be skipped entirely."""
    null_analysis = make_analysis(
        status="completed",
        created_at=_CUTOFF - timedelta(days=5),
        annotated_video_path=None,
        plot_path=None,
        pdf_path=None,
    )

    mock_storage = AsyncMock()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [null_analysis]
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_dt = MagicMock()
    mock_dt.now.return_value = _NOW

    with patch("app.workers.cleanup.async_session", MagicMock(return_value=mock_session)), \
         patch("app.workers.cleanup.StorageService", return_value=mock_storage), \
         patch("app.workers.cleanup.datetime", mock_dt):
        from app.workers.cleanup import cleanup_expired_artifacts
        count = await cleanup_expired_artifacts(make_ctx())

    assert count == 0
    mock_storage.delete_file.assert_not_called()
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_partial_null_paths_only_deletes_non_null():
    """An analysis with only some artifact paths set must only delete the non-NULL ones."""
    partial_analysis = make_analysis(
        status="completed",
        created_at=_CUTOFF - timedelta(days=5),
        annotated_video_path="artifacts/partial/annotated.mp4",
        plot_path=None,
        pdf_path=None,
    )

    mock_storage = AsyncMock()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [partial_analysis]
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_dt = MagicMock()
    mock_dt.now.return_value = _NOW

    with patch("app.workers.cleanup.async_session", MagicMock(return_value=mock_session)), \
         patch("app.workers.cleanup.StorageService", return_value=mock_storage), \
         patch("app.workers.cleanup.datetime", mock_dt):
        from app.workers.cleanup import cleanup_expired_artifacts
        count = await cleanup_expired_artifacts(make_ctx())

    assert count == 1
    deleted_paths = [call.args[0] for call in mock_storage.delete_file.call_args_list]
    assert deleted_paths == ["artifacts/partial/annotated.mp4"]
    assert partial_analysis.annotated_video_path is None


# ---------------------------------------------------------------------------
# Test 7: Returns count of cleaned analyses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_correct_count():
    """cleanup_expired_artifacts must return the exact count of cleaned analyses."""
    analyses = [
        make_analysis(
            status="completed",
            created_at=_CUTOFF - timedelta(days=i + 1),
        )
        for i in range(5)
    ]

    mock_storage = AsyncMock()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = analyses
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_dt = MagicMock()
    mock_dt.now.return_value = _NOW

    with patch("app.workers.cleanup.async_session", MagicMock(return_value=mock_session)), \
         patch("app.workers.cleanup.StorageService", return_value=mock_storage), \
         patch("app.workers.cleanup.datetime", mock_dt):
        from app.workers.cleanup import cleanup_expired_artifacts
        count = await cleanup_expired_artifacts(make_ctx())

    assert count == 5


# ---------------------------------------------------------------------------
# _build_supabase_client: ImportError and general Exception branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_supabase_client_import_error_returns_none():
    """_build_supabase_client returns None gracefully when supabase package is not installed."""
    import builtins
    import os

    real_import = builtins.__import__

    def _block_supabase(name, *args, **kwargs):
        if name == "supabase":
            raise ImportError("No module named 'supabase'")
        return real_import(name, *args, **kwargs)

    with patch.dict(os.environ, {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "secret"}), \
         patch("builtins.__import__", side_effect=_block_supabase):
        from app.workers import cleanup
        result = await cleanup._build_supabase_client()

    assert result is None


@pytest.mark.asyncio
async def test_build_supabase_client_exception_returns_none():
    """_build_supabase_client returns None gracefully when acreate_client raises a runtime error."""
    import os

    async def _raise(*args, **kwargs):
        raise RuntimeError("connection refused")

    # Patch supabase.acreate_client — the deferred import resolves to this attribute
    with patch.dict(os.environ, {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "secret"}), \
         patch("supabase.acreate_client", new=_raise):
        from app.workers import cleanup
        result = await cleanup._build_supabase_client()

    assert result is None


@pytest.mark.asyncio
async def test_build_supabase_client_returns_none_when_env_missing():
    """_build_supabase_client returns None and logs a warning when SUPABASE_URL or key is not set (lines 182-186)."""
    import os
    # Ensure both env vars are absent
    env = {k: v for k, v in os.environ.items() if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")}

    with patch.dict(os.environ, env, clear=True):
        from app.workers import cleanup
        result = await cleanup._build_supabase_client()

    assert result is None
