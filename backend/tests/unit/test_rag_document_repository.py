"""Unit tests for RagDocumentRepository — branch coverage uplift."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.rag_document import RagDocumentRepository


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_scalars_db(rows: list) -> MagicMock:
    """Mock db whose execute().scalars().all() returns rows."""
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
    """Mock db whose execute().scalar_one() / .scalar_one_or_none() returns value."""
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
# list_all — all branch combinations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_no_filters():
    doc = SimpleNamespace(id=uuid.uuid4())
    db = _make_scalars_db([doc])
    repo = RagDocumentRepository(db)

    result = await repo.list_all(limit=50, offset=0)

    assert result == [doc]
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_all_with_review_status_filter():
    doc = SimpleNamespace(id=uuid.uuid4(), review_status="approved")
    db = _make_scalars_db([doc])
    repo = RagDocumentRepository(db)

    result = await repo.list_all(limit=10, offset=0, review_status="approved")

    assert result == [doc]


@pytest.mark.asyncio
async def test_list_all_with_exclude_uploading():
    """exclude_uploading branch: used when review_status is None but exclude_uploading=True."""
    doc = SimpleNamespace(id=uuid.uuid4(), review_status="pending")
    db = _make_scalars_db([doc])
    repo = RagDocumentRepository(db)

    result = await repo.list_all(limit=50, offset=0, exclude_uploading=True)

    assert result == [doc]


@pytest.mark.asyncio
async def test_list_all_with_exercise_tag_filter():
    doc = SimpleNamespace(id=uuid.uuid4())
    db = _make_scalars_db([doc])
    repo = RagDocumentRepository(db)

    result = await repo.list_all(limit=50, offset=0, exercise_tag="squat")

    assert result == [doc]


@pytest.mark.asyncio
async def test_list_all_with_quality_tier_filter():
    doc = SimpleNamespace(id=uuid.uuid4())
    db = _make_scalars_db([doc])
    repo = RagDocumentRepository(db)

    result = await repo.list_all(limit=50, offset=0, quality_tier="high")

    assert result == [doc]


# ---------------------------------------------------------------------------
# count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_without_filter():
    db = _make_scalar_db(7)
    repo = RagDocumentRepository(db)

    result = await repo.count()

    assert result == 7


@pytest.mark.asyncio
async def test_count_with_review_status_filter():
    db = _make_scalar_db(3)
    repo = RagDocumentRepository(db)

    result = await repo.count(review_status="approved")

    assert result == 3


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_returns_doc():
    doc_id = uuid.uuid4()
    doc = SimpleNamespace(id=doc_id)
    db = _make_scalar_db(doc)
    repo = RagDocumentRepository(db)

    result = await repo.get_by_id(doc_id)

    assert result is doc


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing():
    db = _make_scalar_db(None)
    repo = RagDocumentRepository(db)

    result = await repo.get_by_id(uuid.uuid4())

    assert result is None


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_returns_true_when_found():
    execute_result = MagicMock()
    execute_result.rowcount = 1

    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = RagDocumentRepository(db)
    result = await repo.delete(uuid.uuid4())

    assert result is True


@pytest.mark.asyncio
async def test_delete_returns_false_when_not_found():
    execute_result = MagicMock()
    execute_result.rowcount = 0

    db = AsyncMock()
    db.execute.return_value = execute_result

    repo = RagDocumentRepository(db)
    result = await repo.delete(uuid.uuid4())

    assert result is False


# ---------------------------------------------------------------------------
# update_review_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_review_status_returns_none_when_not_found():
    db = _make_scalar_db(None)
    repo = RagDocumentRepository(db)

    result = await repo.update_review_status(uuid.uuid4(), review_status="approved")

    assert result is None


@pytest.mark.asyncio
async def test_update_review_status_without_reviewer():
    doc = SimpleNamespace(id=uuid.uuid4(), review_status="pending", reviewer_id=None, reviewed_at=None)
    db = _make_scalar_db(doc)
    repo = RagDocumentRepository(db)

    result = await repo.update_review_status(doc.id, review_status="approved", reviewer_id=None)

    assert result is doc
    assert doc.review_status == "approved"
    assert doc.reviewer_id is None  # not set


@pytest.mark.asyncio
async def test_update_review_status_with_reviewer_sets_reviewer_id_and_reviewed_at():
    reviewer_id = uuid.uuid4()
    doc = SimpleNamespace(id=uuid.uuid4(), review_status="pending", reviewer_id=None, reviewed_at=None)
    db = _make_scalar_db(doc)
    repo = RagDocumentRepository(db)

    result = await repo.update_review_status(doc.id, review_status="approved", reviewer_id=reviewer_id)

    assert result is doc
    assert doc.review_status == "approved"
    assert doc.reviewer_id == reviewer_id
    assert doc.reviewed_at is not None


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_adds_and_returns_doc():
    doc_id = uuid.uuid4()
    doc = SimpleNamespace(id=doc_id)

    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    repo = RagDocumentRepository(db)
    result = await repo.create(doc)

    db.add.assert_called_once_with(doc)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(doc)
    assert result is doc
