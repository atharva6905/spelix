"""Unit tests for ConsentRepository (P2-029).

Tests cover:
- get_by_user returns all records for a user
- get_latest_by_type returns the most recent record for a consent type
- create inserts a new consent record
- Append-only: withdrawals insert new rows, never update existing

Requirements: FR-BRAIN-11, NFR-PRIV-01
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.consent_record import ConsentRecord
from app.repositories.consent import ConsentRepository

TEST_USER_ID = uuid.uuid4()
NOW = datetime.now(timezone.utc)


def _make_consent_record(
    *,
    user_id: uuid.UUID = None,
    consent_type: str = "health_data_processing",
    granted: bool = True,
    granted_at: datetime = None,
    withdrawn_at: datetime = None,
    consent_version: str = "1.0",
    ip_address_hash: str = None,
) -> ConsentRecord:
    record = ConsentRecord(
        user_id=user_id or TEST_USER_ID,
        consent_type=consent_type,
        granted=granted,
        granted_at=granted_at or (NOW if granted else None),
        withdrawn_at=withdrawn_at,
        consent_version=consent_version,
        ip_address_hash=ip_address_hash,
    )
    record.__dict__.update(
        {
            "id": uuid.uuid4(),
            "created_at": NOW,
            "updated_at": NOW,
            "extra_metadata": {},
        }
    )
    return record


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture()
def repo(mock_db):
    return ConsentRepository(mock_db)


# ---------------------------------------------------------------------------
# get_by_user
# ---------------------------------------------------------------------------


class TestGetByUser:
    @pytest.mark.asyncio
    async def test_returns_all_records_for_user(self, repo, mock_db):
        records = [
            _make_consent_record(consent_type="health_data_processing"),
            _make_consent_record(consent_type="analytics"),
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = records
        mock_db.execute.return_value = result_mock

        result = await repo.get_by_user(TEST_USER_ID)

        assert len(result) == 2
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_records(self, repo, mock_db):
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = result_mock

        result = await repo.get_by_user(uuid.uuid4())

        assert result == []


# ---------------------------------------------------------------------------
# get_latest_by_type
# ---------------------------------------------------------------------------


class TestGetLatestByType:
    @pytest.mark.asyncio
    async def test_returns_most_recent_record(self, repo, mock_db):
        record = _make_consent_record(consent_type="health_data_processing", granted=True)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_db.execute.return_value = result_mock

        result = await repo.get_latest_by_type(TEST_USER_ID, "health_data_processing")

        assert result is record
        assert result.granted is True

    @pytest.mark.asyncio
    async def test_returns_none_when_no_record_exists(self, repo, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        result = await repo.get_latest_by_type(TEST_USER_ID, "analytics")

        assert result is None


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_inserts_and_returns_record(self, repo, mock_db):
        record = _make_consent_record(granted=True)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await repo.create(record)

        mock_db.add.assert_called_once_with(record)
        mock_db.flush.assert_called_once()
        mock_db.refresh.assert_called_once_with(record)
        assert result is record

    @pytest.mark.asyncio
    async def test_create_withdrawal_inserts_new_row(self, repo, mock_db):
        """Append-only: withdrawal is a new row with granted=False, not an update."""
        withdrawal_record = _make_consent_record(
            granted=False,
            granted_at=None,
            withdrawn_at=NOW,
        )
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await repo.create(withdrawal_record)

        mock_db.add.assert_called_once_with(withdrawal_record)
        assert result.granted is False
        assert result.withdrawn_at is not None
        # Crucially: no execute/update call — only add+flush+refresh
        mock_db.execute.assert_not_called()
