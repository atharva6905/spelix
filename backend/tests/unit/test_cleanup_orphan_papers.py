"""
Unit tests for the streaq orphan rag_documents cleanup cron (D-030).

TDD gate (D-030):
1. Doc with storage_path is cleaned from Storage and hard-deleted from DB
2. Empty query returns 0 — no deletions
3. Storage error on first doc continues to next doc, count=1
4. Null storage_path skips Storage call but still hard-deletes row, count=1
5. Three docs return count=3
6. cleanup_orphan_papers_cron wrapper is callable in streaq_worker

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

_NOW = datetime(2026, 4, 19, 4, 0, 0, tzinfo=timezone.utc)
_CUTOFF = _NOW - timedelta(hours=2)


def make_doc(
    *,
    review_status: str = "uploading",
    created_at: datetime | None = None,
    storage_path: str | None = "papers/abc/document.pdf",
) -> MagicMock:
    """Return a mock RagDocument model instance."""
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.review_status = review_status
    obj.created_at = created_at or (_CUTOFF - timedelta(minutes=30))
    obj.storage_path = storage_path
    return obj


def make_ctx() -> dict[str, Any]:
    """Build a minimal ARQ context dict."""
    return {}


def _make_session_mock(docs: list[Any]) -> MagicMock:
    """Build an AsyncMock session that returns `docs` on execute().scalars().all()."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = docs
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    return mock_session


# ---------------------------------------------------------------------------
# Test 1: doc with storage_path is cleaned from Storage and hard-deleted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_uploading_rows_deleted_from_storage_and_db() -> None:
    """A stale 'uploading' doc with a storage_path must be deleted from Storage
    and hard-deleted from the DB; returns count=1."""
    doc = make_doc(storage_path="papers/abc/document.pdf")
    mock_session = _make_session_mock([doc])
    mock_storage = AsyncMock()
    mock_supabase = MagicMock()

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_orphan_papers.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_orphan_papers.PaperStorageService", return_value=mock_storage),
        patch("app.workers.cleanup_orphan_papers._build_supabase_client", AsyncMock(return_value=mock_supabase)),
        patch("app.workers.cleanup_orphan_papers.datetime", mock_dt),
    ):
        from app.workers.cleanup_orphan_papers import cleanup_orphan_papers

        count = await cleanup_orphan_papers(make_ctx())

    assert count == 1
    mock_storage.delete_object.assert_awaited_once_with("papers/abc/document.pdf")
    mock_session.commit.assert_awaited()


# ---------------------------------------------------------------------------
# Test 2: empty query returns 0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_stale_rows_returns_zero() -> None:
    """When the DB query returns no rows, count=0 and no Storage calls are made."""
    mock_session = _make_session_mock([])
    mock_storage = AsyncMock()
    mock_supabase = MagicMock()

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_orphan_papers.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_orphan_papers.PaperStorageService", return_value=mock_storage),
        patch("app.workers.cleanup_orphan_papers._build_supabase_client", AsyncMock(return_value=mock_supabase)),
        patch("app.workers.cleanup_orphan_papers.datetime", mock_dt),
    ):
        from app.workers.cleanup_orphan_papers import cleanup_orphan_papers

        count = await cleanup_orphan_papers(make_ctx())

    assert count == 0
    mock_storage.delete_object.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: Storage error on first doc continues to second doc, count=1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_storage_error_continues_to_next_row() -> None:
    """A Storage deletion failure on the first doc must not block the second;
    the second is cleaned successfully and count=1."""
    doc_a = make_doc(storage_path="papers/aaa/first.pdf")
    doc_b = make_doc(storage_path="papers/bbb/second.pdf")
    mock_session = _make_session_mock([doc_a, doc_b])

    async def delete_side_effect(path: str) -> None:
        if "aaa" in path:
            raise RuntimeError("Storage unavailable")

    mock_storage = AsyncMock()
    mock_storage.delete_object.side_effect = delete_side_effect
    mock_supabase = MagicMock()

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_orphan_papers.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_orphan_papers.PaperStorageService", return_value=mock_storage),
        patch("app.workers.cleanup_orphan_papers._build_supabase_client", AsyncMock(return_value=mock_supabase)),
        patch("app.workers.cleanup_orphan_papers.datetime", mock_dt),
    ):
        from app.workers.cleanup_orphan_papers import cleanup_orphan_papers

        count = await cleanup_orphan_papers(make_ctx())

    assert count == 1
    # doc_b must have been committed (second row succeeded)
    assert mock_session.commit.await_count >= 1


# ---------------------------------------------------------------------------
# Test 4: null storage_path skips Storage call, still hard-deletes row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_null_storage_path_skips_storage_still_deletes_row() -> None:
    """A doc with storage_path=None must not trigger a Storage delete call,
    but the DB row is still hard-deleted and count=1."""
    doc = make_doc(storage_path=None)
    mock_session = _make_session_mock([doc])
    mock_storage = AsyncMock()
    mock_supabase = MagicMock()

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_orphan_papers.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_orphan_papers.PaperStorageService", return_value=mock_storage),
        patch("app.workers.cleanup_orphan_papers._build_supabase_client", AsyncMock(return_value=mock_supabase)),
        patch("app.workers.cleanup_orphan_papers.datetime", mock_dt),
    ):
        from app.workers.cleanup_orphan_papers import cleanup_orphan_papers

        count = await cleanup_orphan_papers(make_ctx())

    assert count == 1
    mock_storage.delete_object.assert_not_called()
    mock_session.commit.assert_awaited()


# ---------------------------------------------------------------------------
# Test 5: three docs returns count=3
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_rows_returns_correct_count() -> None:
    """cleanup_orphan_papers must return the exact count of hard-deleted rows."""
    docs = [
        make_doc(storage_path=f"papers/doc{i}/file.pdf")
        for i in range(3)
    ]
    mock_session = _make_session_mock(docs)
    mock_storage = AsyncMock()
    mock_supabase = MagicMock()

    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _NOW

    with (
        patch("app.workers.cleanup_orphan_papers.async_session", MagicMock(return_value=mock_session)),
        patch("app.workers.cleanup_orphan_papers.PaperStorageService", return_value=mock_storage),
        patch("app.workers.cleanup_orphan_papers._build_supabase_client", AsyncMock(return_value=mock_supabase)),
        patch("app.workers.cleanup_orphan_papers.datetime", mock_dt),
    ):
        from app.workers.cleanup_orphan_papers import cleanup_orphan_papers

        count = await cleanup_orphan_papers(make_ctx())

    assert count == 3
    assert mock_storage.delete_object.await_count == 3


# ---------------------------------------------------------------------------
# Test 6: cron wrapper is callable in streaq_worker
# ---------------------------------------------------------------------------


def test_cron_wrapper_registered_in_streaq_worker() -> None:
    """cleanup_orphan_papers_cron must be importable and callable from streaq_worker."""
    from app.workers.streaq_worker import cleanup_orphan_papers_cron

    assert callable(cleanup_orphan_papers_cron)
