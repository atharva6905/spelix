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


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_adds_and_returns_analysis():
    analysis = SimpleNamespace(id=uuid.uuid4())

    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    repo = AnalysisRepository(db)
    result = await repo.create(analysis)

    db.add.assert_called_once_with(analysis)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(analysis)
    assert result is analysis


# ---------------------------------------------------------------------------
# get_by_user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_user_returns_list():
    user_id = uuid.uuid4()
    row = SimpleNamespace(id=uuid.uuid4(), user_id=user_id)
    db = _make_mock_db([row])
    repo = AnalysisRepository(db)

    result = await repo.get_by_user(user_id, limit=50, offset=0)

    assert result == [row]
    db.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_sets_status_and_returns_analysis():
    analysis_id = uuid.uuid4()
    analysis = SimpleNamespace(id=analysis_id, status="queued")

    execute_result = MagicMock()
    execute_result.scalar_one.return_value = analysis

    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    repo = AnalysisRepository(db)
    result = await repo.update_status(analysis_id, "processing")

    assert result is analysis
    assert analysis.status == "processing"
    db.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_flushes_and_refreshes():
    analysis = SimpleNamespace(id=uuid.uuid4())

    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    repo = AnalysisRepository(db)
    result = await repo.update(analysis)

    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(analysis)
    assert result is analysis


# ---------------------------------------------------------------------------
# get_by_id_with_relations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_with_relations_returns_analysis():
    analysis_id = uuid.uuid4()
    analysis = SimpleNamespace(id=analysis_id)

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = analysis

    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = AnalysisRepository(db)
    result = await repo.get_by_id_with_relations(analysis_id)

    assert result is analysis


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_removes_analysis_when_found():
    analysis_id = uuid.uuid4()
    analysis = SimpleNamespace(id=analysis_id)

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = analysis

    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()
    db.delete = AsyncMock()

    repo = AnalysisRepository(db)
    await repo.delete(analysis_id)

    db.delete.assert_awaited_once_with(analysis)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_does_nothing_when_not_found():
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()
    db.delete = AsyncMock()

    repo = AnalysisRepository(db)
    await repo.delete(uuid.uuid4())

    db.delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# Helpers for scalar_one / scalar / scalar_one_or_none results
# ---------------------------------------------------------------------------


def _make_scalar_db(scalar_value) -> MagicMock:
    """Return mock db whose execute().scalar_one() returns scalar_value."""
    execute_result = MagicMock()
    execute_result.scalar_one.return_value = scalar_value
    execute_result.scalar_one_or_none.return_value = scalar_value
    execute_result.scalar.return_value = scalar_value

    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_returns_analysis():
    analysis_id = uuid.uuid4()
    expected = SimpleNamespace(id=analysis_id)
    db = _make_scalar_db(expected)
    repo = AnalysisRepository(db)

    result = await repo.get_by_id(analysis_id)

    assert result is expected


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing():
    db = _make_scalar_db(None)
    repo = AnalysisRepository(db)

    result = await repo.get_by_id(uuid.uuid4())

    assert result is None


# ---------------------------------------------------------------------------
# get_recent_for_exercise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_recent_for_exercise_returns_list():
    user_id = uuid.uuid4()
    row = SimpleNamespace(id=uuid.uuid4(), exercise_type="squat")
    db = _make_mock_db([row])
    repo = AnalysisRepository(db)

    result = await repo.get_recent_for_exercise(user_id, "squat", "high_bar", limit=7)

    assert result == [row]
    db.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_personal_best_confidence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_personal_best_confidence_returns_float():
    user_id = uuid.uuid4()
    db = _make_scalar_db(0.92)
    repo = AnalysisRepository(db)

    result = await repo.get_personal_best_confidence(user_id, "squat", "high_bar")

    assert result == 0.92


@pytest.mark.asyncio
async def test_get_personal_best_confidence_returns_zero_when_none():
    user_id = uuid.uuid4()
    db = _make_scalar_db(None)  # no analyses → scalar returns None
    repo = AnalysisRepository(db)

    result = await repo.get_personal_best_confidence(user_id, "bench", "competition")

    assert result == 0.0


# ---------------------------------------------------------------------------
# get_completed_since
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_completed_since_returns_list():
    from datetime import datetime, timezone

    user_id = uuid.uuid4()
    row = SimpleNamespace(id=uuid.uuid4())
    db = _make_mock_db([row])
    repo = AnalysisRepository(db)

    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = await repo.get_completed_since(user_id, since)

    assert result == [row]


# ---------------------------------------------------------------------------
# list_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_without_filter():
    row = SimpleNamespace(id=uuid.uuid4())
    db = _make_mock_db([row])
    repo = AnalysisRepository(db)

    result = await repo.list_all(limit=50, offset=0)

    assert result == [row]


@pytest.mark.asyncio
async def test_list_all_with_status_filter():
    row = SimpleNamespace(id=uuid.uuid4(), status="failed")
    db = _make_mock_db([row])
    repo = AnalysisRepository(db)

    result = await repo.list_all(limit=10, offset=0, status_filter="failed")

    assert result == [row]


# ---------------------------------------------------------------------------
# get_below_confidence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_below_confidence_returns_low_conf_analyses():
    row = SimpleNamespace(id=uuid.uuid4(), confidence_score=0.30)
    db = _make_mock_db([row])
    repo = AnalysisRepository(db)

    result = await repo.get_below_confidence(threshold=0.50)

    assert result == [row]


# ---------------------------------------------------------------------------
# delete_by_user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_by_user_deletes_all_analyses():
    user_id = uuid.uuid4()
    row = SimpleNamespace(id=uuid.uuid4(), user_id=user_id)

    scalars_result = MagicMock()
    scalars_result.all.return_value = [row]
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result

    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()
    db.delete = AsyncMock()

    repo = AnalysisRepository(db)
    await repo.delete_by_user(user_id)

    db.delete.assert_awaited_once_with(row)
    db.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ping_returns_true_on_success():
    db = AsyncMock()
    db.execute = AsyncMock()
    repo = AnalysisRepository(db)

    result = await repo.ping()

    assert result is True


@pytest.mark.asyncio
async def test_ping_returns_false_on_exception():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=Exception("connection refused"))
    repo = AnalysisRepository(db)

    result = await repo.ping()

    assert result is False


# ---------------------------------------------------------------------------
# list_flagged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_flagged_returns_flagged_analyses():
    row = SimpleNamespace(id=uuid.uuid4(), flagged_for_review=True)
    db = _make_mock_db([row])
    repo = AnalysisRepository(db)

    result = await repo.list_flagged(limit=50, offset=0)

    assert result == [row]


# ---------------------------------------------------------------------------
# count_flagged / count_annotated / count_golden
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_flagged_returns_integer():
    db = _make_scalar_db(5)
    repo = AnalysisRepository(db)

    result = await repo.count_flagged()

    assert result == 5


@pytest.mark.asyncio
async def test_count_annotated_returns_integer():
    db = _make_scalar_db(3)
    repo = AnalysisRepository(db)

    result = await repo.count_annotated()

    assert result == 3


@pytest.mark.asyncio
async def test_count_golden_returns_integer():
    db = _make_scalar_db(2)
    repo = AnalysisRepository(db)

    result = await repo.count_golden()

    assert result == 2
