"""Unit tests for CoachBrainRepository — branch coverage uplift."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.coach_brain import CoachBrainRepository


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_scalars_db(rows: list) -> MagicMock:
    scalars_result = MagicMock()
    scalars_result.all.return_value = rows
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


def _make_scalar_db(value) -> MagicMock:
    execute_result = MagicMock()
    execute_result.scalar_one.return_value = value
    execute_result.scalar_one_or_none.return_value = value
    execute_result.rowcount = 1 if value else 0
    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


# ---------------------------------------------------------------------------
# list_all — all filter branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_no_filters():
    entry = SimpleNamespace(id=uuid.uuid4())
    db = _make_scalars_db([entry])
    repo = CoachBrainRepository(db)

    result = await repo.list_all(limit=50, offset=0)

    assert result == [entry]


@pytest.mark.asyncio
async def test_list_all_with_exercise_filter():
    db = _make_scalars_db([])
    repo = CoachBrainRepository(db)

    result = await repo.list_all(limit=10, offset=0, exercise="squat")

    assert result == []


@pytest.mark.asyncio
async def test_list_all_with_phase_filter():
    db = _make_scalars_db([])
    repo = CoachBrainRepository(db)

    result = await repo.list_all(limit=10, offset=0, phase="descent")

    assert result == []


@pytest.mark.asyncio
async def test_list_all_with_entry_type_filter():
    db = _make_scalars_db([])
    repo = CoachBrainRepository(db)

    result = await repo.list_all(limit=10, offset=0, entry_type="correction")

    assert result == []


@pytest.mark.asyncio
async def test_list_all_with_status_filter():
    db = _make_scalars_db([])
    repo = CoachBrainRepository(db)

    result = await repo.list_all(limit=10, offset=0, status="active")

    assert result == []


@pytest.mark.asyncio
async def test_list_all_all_filters():
    db = _make_scalars_db([])
    repo = CoachBrainRepository(db)

    result = await repo.list_all(
        limit=5, offset=0, exercise="bench", phase="bottom", entry_type="cue", status="seed"
    )

    assert result == []


# ---------------------------------------------------------------------------
# count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_returns_integer():
    db = _make_scalar_db(12)
    repo = CoachBrainRepository(db)

    result = await repo.count()

    assert result == 12


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_returns_entry():
    entry_id = uuid.uuid4()
    entry = SimpleNamespace(id=entry_id)
    db = _make_scalar_db(entry)
    repo = CoachBrainRepository(db)

    result = await repo.get_by_id(entry_id)

    assert result is entry


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing():
    db = _make_scalar_db(None)
    repo = CoachBrainRepository(db)

    result = await repo.get_by_id(uuid.uuid4())

    assert result is None


# ---------------------------------------------------------------------------
# create / update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_adds_and_returns_entry():
    entry = SimpleNamespace(id=uuid.uuid4())
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    repo = CoachBrainRepository(db)
    result = await repo.create(entry)

    db.add.assert_called_once_with(entry)
    db.flush.assert_awaited_once()
    assert result is entry


@pytest.mark.asyncio
async def test_update_flushes_and_refreshes():
    entry = SimpleNamespace(id=uuid.uuid4())
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    repo = CoachBrainRepository(db)
    result = await repo.update(entry)

    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(entry)
    assert result is entry


# ---------------------------------------------------------------------------
# delete_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_by_id_returns_true_when_found():
    execute_result = MagicMock()
    execute_result.rowcount = 1
    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = CoachBrainRepository(db)
    result = await repo.delete_by_id(uuid.uuid4())

    assert result is True


@pytest.mark.asyncio
async def test_delete_by_id_returns_false_when_not_found():
    execute_result = MagicMock()
    execute_result.rowcount = 0
    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = CoachBrainRepository(db)
    result = await repo.delete_by_id(uuid.uuid4())

    assert result is False


# ---------------------------------------------------------------------------
# remove_analysis_ids_for_user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_analysis_ids_empty_list_returns_zero():
    db = AsyncMock()
    repo = CoachBrainRepository(db)

    result = await repo.remove_analysis_ids_for_user([])

    assert result == 0
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_analysis_ids_returns_rowcount_sum():
    execute_result = MagicMock()
    execute_result.rowcount = 1

    db = AsyncMock()
    db.execute.return_value = execute_result

    analysis_ids = [uuid.uuid4(), uuid.uuid4()]
    repo = CoachBrainRepository(db)

    result = await repo.remove_analysis_ids_for_user(analysis_ids)

    assert result == 2  # 1 per each ID
    assert db.execute.await_count == 2


# ---------------------------------------------------------------------------
# soft_delete_empty_unconfirmed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_delete_empty_unconfirmed_returns_rowcount():
    execute_result = MagicMock()
    execute_result.rowcount = 3
    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = CoachBrainRepository(db)
    result = await repo.soft_delete_empty_unconfirmed()

    assert result == 3


@pytest.mark.asyncio
async def test_soft_delete_empty_unconfirmed_predicate_uses_cardinality():
    """FR-BRAIN-16 (issue #203): the empty-array predicate must use
    cardinality(source_analysis_ids) = 0, NOT a dict/JSON equality.

    ``source_analysis_ids`` is ``ARRAY(UUID)``. Comparing it against a Python
    ``{}`` renders SQL that never matches the array-emptied rows produced by
    ``array_remove`` during a GDPR consent-withdrawal cascade, so the tombstone
    silently never fires. This test compiles the statement actually passed to
    ``db.execute`` against the postgresql dialect and inspects the rendered SQL
    — exactly the layer the original rowcount-only mock could not see.
    """
    from sqlalchemy.dialects import postgresql

    execute_result = MagicMock()
    execute_result.rowcount = 0
    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = CoachBrainRepository(db)
    await repo.soft_delete_empty_unconfirmed()

    assert db.execute.await_count == 1
    stmt = db.execute.await_args.args[0]

    sql = str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()

    # The intended empty-array predicate.
    assert "cardinality(coach_brain_entries.source_analysis_ids) = 0" in sql
    # Guard against the original bug: the array column must never be compared
    # directly against a literal value (the dict/JSON-equality form).
    assert "source_analysis_ids = " not in sql
    # Seed protection (ADR-BRAIN-08): seeds ship with source_analysis_ids=[]
    # and confirmation_count=1, so the cascade must target ONLY
    # analysis-derived entries. A broader guard like status != 'deprecated'
    # would tombstone the whole seed corpus on the first cascade run.
    assert "coach_brain_entries.status = 'active'" in sql
    assert "status != 'deprecated'" not in sql
