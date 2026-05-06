"""Unit tests for ThresholdFlagRepository (FR-EXPV-08)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.threshold_flag import ThresholdFlag
from app.repositories.threshold_flag import ThresholdFlagRepository


@pytest_asyncio.fixture
async def db_session():
    raw_url = os.environ["DATABASE_URL"]
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(raw_url, connect_args={"statement_cache_size": 0})
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()
    await engine.dispose()


pytestmark = pytest.mark.asyncio


async def _make_flag(reviewer_id):
    return ThresholdFlag(
        id=uuid4(),
        reviewer_id=reviewer_id,
        section="squat",
        key="knee_valgus_caution_deg",
        current_value=5.0,
        current_citation="Myer et al. 2010",
        proposed_value=8.0,
        proposed_citation="Krosshaug 2016 — 8° not replicated",
        rationale="Original Myer finding did not replicate in larger cohorts.",
        status="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


async def test_create_returns_persisted_flag(db_session: AsyncSession):
    repo = ThresholdFlagRepository(db_session)
    reviewer_id = uuid4()
    flag = await _make_flag(reviewer_id)

    created = await repo.create(flag)
    await db_session.flush()

    assert created.id == flag.id
    assert created.reviewer_id == reviewer_id
    assert created.status == "open"


async def test_list_by_reviewer_orders_created_desc(db_session: AsyncSession):
    repo = ThresholdFlagRepository(db_session)
    reviewer_id = uuid4()
    now = datetime.now(timezone.utc)

    first = await _make_flag(reviewer_id)
    first.created_at = now - timedelta(seconds=2)

    second = await _make_flag(reviewer_id)
    second.created_at = now

    await repo.create(first)
    await repo.create(second)
    await db_session.flush()

    rows = await repo.list_by_reviewer(reviewer_id, limit=10, offset=0)

    assert [r.id for r in rows] == [second.id, first.id]


async def test_update_status_sets_resolution_metadata(db_session: AsyncSession):
    repo = ThresholdFlagRepository(db_session)
    reviewer_id = uuid4()
    admin_id = uuid4()
    flag = await _make_flag(reviewer_id)
    await repo.create(flag)
    await db_session.flush()

    updated = await repo.update_status(
        flag.id,
        status="resolved",
        resolution_note="Merged in PR #XXX.",
        resolved_by=admin_id,
    )

    assert updated is not None
    assert updated.status == "resolved"
    assert updated.resolution_note == "Merged in PR #XXX."
    assert updated.resolved_by == admin_id
    assert updated.resolved_at is not None


# ---------------------------------------------------------------------------
# Mock-based unit tests for get_by_id, list_all, and update_status branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_returns_flag_mock():
    """get_by_id delegates to scalar_one_or_none (mock-based, no real DB)."""
    from unittest.mock import AsyncMock, MagicMock

    flag_id = uuid4()
    flag = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = flag

    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = ThresholdFlagRepository(db)
    result = await repo.get_by_id(flag_id)

    assert result is flag


@pytest.mark.asyncio
async def test_get_by_id_returns_none_mock():
    """get_by_id returns None when flag not found."""
    from unittest.mock import AsyncMock, MagicMock

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = ThresholdFlagRepository(db)
    result = await repo.get_by_id(uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_list_all_no_status_filter_mock():
    """list_all without status filter returns all rows."""
    from unittest.mock import AsyncMock, MagicMock

    row = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = [row]
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result

    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = ThresholdFlagRepository(db)
    result = await repo.list_all(status=None, limit=50, offset=0)

    assert result == [row]


@pytest.mark.asyncio
async def test_list_all_with_status_filter_mock():
    """list_all with status filter adds a WHERE clause."""
    from unittest.mock import AsyncMock, MagicMock

    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result

    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = ThresholdFlagRepository(db)
    result = await repo.list_all(status="open", limit=10, offset=0)

    assert result == []


@pytest.mark.asyncio
async def test_update_status_flushes_when_row_found_mock():
    """update_status calls flush when the row is found (the if-branch is covered)."""
    from unittest.mock import AsyncMock, MagicMock

    flag = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = flag

    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()

    repo = ThresholdFlagRepository(db)
    result = await repo.update_status(
        uuid4(),
        status="resolved",
        resolution_note="done",
        resolved_by=uuid4(),
    )

    assert result is flag
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_status_returns_none_when_not_found_mock():
    """update_status returns None without calling flush when row is not found."""
    from unittest.mock import AsyncMock, MagicMock

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()

    repo = ThresholdFlagRepository(db)
    result = await repo.update_status(
        uuid4(),
        status="rejected",
        resolution_note=None,
        resolved_by=uuid4(),
    )

    assert result is None
    db.flush.assert_not_awaited()
