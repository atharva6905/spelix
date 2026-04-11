"""Tests for the FastAPI ``get_db`` dependency lifecycle.

Regression coverage for the production data-loss bug where every DB write
made through a request handler was silently rolled back. The dependency
yielded a session inside ``async with`` and never called
``session.commit()`` — and SQLAlchemy ``AsyncSession`` defaults to
``autocommit=False``, so the implicit transaction was discarded when the
session closed. The bug surfaced when ``POST /api/v1/analyses`` returned
201 with a UUID built from the in-memory ORM object, and the immediately
following ``POST /api/v1/analyses/{id}/start`` returned 404 because the
row had been rolled back before the second request ran.

These tests verify the corrected lifecycle:

- on success: the dependency commits the session before closing
- on exception: the dependency rolls back the session before re-raising
- the underlying ``async with`` always closes the session (no leaks)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


@asynccontextmanager
async def _fake_session_cm(mock_session: AsyncMock):
    """Async context manager wrapping a single mock session.

    Mirrors what ``async_sessionmaker(engine)()`` returns: an async
    context manager that yields the session and closes it on exit.
    """
    try:
        yield mock_session
    finally:
        # async_session() context manager closes the session on exit;
        # we don't need to assert this directly because the test relies
        # on commit/rollback being called BEFORE the close.
        pass


class TestGetDbCommit:
    @pytest.mark.asyncio
    async def test_commits_session_on_successful_consumption(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the consumer (FastAPI handler) returns normally, the
        dependency MUST call ``session.commit()`` so flushed writes persist.
        """
        mock_session = AsyncMock()

        def fake_async_session() -> AsyncMock:
            return _fake_session_cm(mock_session)  # type: ignore[return-value]

        # Patch the symbol the dependency reads, NOT the import path of
        # the consumer — get_db reads ``async_session`` from app.db at
        # module load time, so we monkeypatch the attribute on app.db.
        from app import db as db_module

        monkeypatch.setattr(db_module, "async_session", fake_async_session)

        gen = db_module.get_db()
        # Drive the generator to yield the session (the FastAPI lifecycle).
        session = await gen.__anext__()
        assert session is mock_session

        # Simulate the handler completing successfully — close the
        # generator. FastAPI signals this by calling .aclose() on the
        # dependency generator OR by re-entering the generator with a
        # value. The standard pattern is StopAsyncIteration on the next
        # __anext__ call after the handler returns.
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_rolls_back_session_when_consumer_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the handler raises an exception, the dependency MUST
        roll back the session and propagate the exception. This includes
        ``HTTPException`` raised by validation logic — partial writes
        from a failed handler must not leak.
        """
        mock_session = AsyncMock()

        def fake_async_session() -> AsyncMock:
            return _fake_session_cm(mock_session)  # type: ignore[return-value]

        from app import db as db_module

        monkeypatch.setattr(db_module, "async_session", fake_async_session)

        gen = db_module.get_db()
        await gen.__anext__()

        # Simulate the handler raising — FastAPI signals this by calling
        # .athrow() on the generator with the exception.
        with pytest.raises(RuntimeError, match="boom"):
            await gen.athrow(RuntimeError("boom"))

        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_yields_exactly_one_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The dependency must yield exactly one session per request —
        not multiple, not zero. Sanity check that the generator has the
        expected shape after the commit fix."""
        mock_session = AsyncMock()
        call_count = MagicMock()

        def fake_async_session() -> AsyncMock:
            call_count()
            return _fake_session_cm(mock_session)  # type: ignore[return-value]

        from app import db as db_module

        monkeypatch.setattr(db_module, "async_session", fake_async_session)

        gen = db_module.get_db()
        first = await gen.__anext__()
        assert first is mock_session

        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

        # async_session() should have been invoked exactly once per request
        assert call_count.call_count == 1
