"""Unit tests for AnalysisRepository.list_recent_by_user (FR-AICP-18)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.analysis import AnalysisRepository


def _make_mock_db(scalars_return_value: list) -> MagicMock:
    """Return a mock AsyncSession whose execute().scalars().all() returns the given list."""
    scalars_result = MagicMock()
    scalars_result.all.return_value = scalars_return_value

    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result

    db = AsyncMock()
    db.execute.return_value = execute_result
    return db


@pytest.mark.asyncio
async def test_list_recent_by_user_returns_completed_for_exercise():
    user_id = uuid.uuid4()
    row = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        status="completed",
        exercise_type="squat",
    )
    db = _make_mock_db([row])
    repo = AnalysisRepository(db)

    result = await repo.list_recent_by_user(user_id, limit=5, exercise_type="squat")

    assert result == [row]
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_recent_by_user_no_exercise_filter():
    user_id = uuid.uuid4()
    db = _make_mock_db([])
    repo = AnalysisRepository(db)

    result = await repo.list_recent_by_user(user_id, limit=3)

    assert result == []
    db.execute.assert_awaited_once()
