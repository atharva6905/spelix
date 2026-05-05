"""Unit tests for UserProfileRepository — branch coverage uplift."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.user_profile import UserProfileRepository


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_scalar_db(value) -> MagicMock:
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = value
    execute_result.all.return_value = [value] if value is not None else []
    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_adds_and_returns_profile():
    profile = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    repo = UserProfileRepository(db)
    result = await repo.create(profile)

    db.add.assert_called_once_with(profile)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(profile)
    assert result is profile


# ---------------------------------------------------------------------------
# get_by_user_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_user_id_returns_profile():
    user_id = uuid.uuid4()
    profile = SimpleNamespace(id=uuid.uuid4(), user_id=user_id)
    db = _make_scalar_db(profile)
    repo = UserProfileRepository(db)

    result = await repo.get_by_user_id(user_id)

    assert result is profile


@pytest.mark.asyncio
async def test_get_by_user_id_returns_none_when_missing():
    db = _make_scalar_db(None)
    repo = UserProfileRepository(db)

    result = await repo.get_by_user_id(uuid.uuid4())

    assert result is None


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_flushes_and_refreshes():
    profile = SimpleNamespace(id=uuid.uuid4())
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    repo = UserProfileRepository(db)
    result = await repo.update(profile)

    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(profile)
    assert result is profile


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_calls_db_delete_when_found():
    profile = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    db = _make_scalar_db(profile)
    repo = UserProfileRepository(db)

    await repo.delete(profile.id)

    db.delete.assert_awaited_once_with(profile)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_does_nothing_when_not_found():
    db = _make_scalar_db(None)
    repo = UserProfileRepository(db)

    await repo.delete(uuid.uuid4())

    db.delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# delete_by_user_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_by_user_id_calls_db_delete_when_found():
    user_id = uuid.uuid4()
    profile = SimpleNamespace(id=uuid.uuid4(), user_id=user_id)
    db = _make_scalar_db(profile)
    repo = UserProfileRepository(db)

    await repo.delete_by_user_id(user_id)

    db.delete.assert_awaited_once_with(profile)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_by_user_id_does_nothing_when_not_found():
    db = _make_scalar_db(None)
    repo = UserProfileRepository(db)

    await repo.delete_by_user_id(uuid.uuid4())

    db.delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# list_with_analysis_counts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_with_analysis_counts_returns_dicts():
    profile = SimpleNamespace(user_id=uuid.uuid4())

    execute_result = MagicMock()
    execute_result.all.return_value = [(profile, 3)]

    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = UserProfileRepository(db)
    result = await repo.list_with_analysis_counts(limit=50, offset=0)

    assert len(result) == 1
    assert result[0]["profile"] is profile
    assert result[0]["analysis_count"] == 3


@pytest.mark.asyncio
async def test_list_with_analysis_counts_returns_empty_list():
    execute_result = MagicMock()
    execute_result.all.return_value = []

    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = UserProfileRepository(db)
    result = await repo.list_with_analysis_counts(limit=10, offset=0)

    assert result == []
