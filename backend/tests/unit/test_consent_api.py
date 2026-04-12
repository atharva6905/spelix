"""Unit tests for consent API endpoints (P2-029).

Tests cover:
- POST /consent grants consent (201)
- GET /consent returns latest state per type
- POST /consent/withdraw inserts withdrawal row
- Unauthenticated requests return 401
- Invalid consent_type returns 422

Requirements: FR-BRAIN-11, NFR-PRIV-01
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.consent import router
from app.models.consent_record import ConsentRecord

TEST_USER_ID = uuid.uuid4()
TEST_EMAIL = "test@example.com"
NOW = datetime.now(timezone.utc)

VALID_CONSENT_TYPES = [
    "health_data_processing",
    "coach_brain_contribution",
    "analytics",
]


def _make_orm_record(
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
def app_client():
    """TestClient with auth dependency overridden."""
    from app.api.deps import get_current_user

    app = FastAPI()
    app.include_router(router, prefix="/consent")

    async def _mock_user():
        return {"id": TEST_USER_ID, "email": TEST_EMAIL, "role": "user"}

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def unauthed_client():
    """TestClient with no auth override — uses real dependency which raises 401."""
    app = FastAPI()
    app.include_router(router, prefix="/consent")
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /consent — grant
# ---------------------------------------------------------------------------


class TestGrantConsent:
    def test_grant_consent_creates_record(self, app_client: TestClient):
        record = _make_orm_record(consent_type="health_data_processing", granted=True)

        with patch("app.api.v1.consent.ConsentRepository") as MockRepo:
            instance = AsyncMock()
            instance.create.return_value = record
            MockRepo.return_value = instance

            resp = app_client.post(
                "/consent/",
                json={
                    "consent_type": "health_data_processing",
                    "granted": True,
                    "consent_version": "1.0",
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["consent_type"] == "health_data_processing"
        assert body["granted"] is True

    def test_grant_with_ip_hash_accepted(self, app_client: TestClient):
        record = _make_orm_record(
            consent_type="analytics",
            granted=True,
            ip_address_hash="abc123hash",
        )

        with patch("app.api.v1.consent.ConsentRepository") as MockRepo:
            instance = AsyncMock()
            instance.create.return_value = record
            MockRepo.return_value = instance

            resp = app_client.post(
                "/consent/",
                json={
                    "consent_type": "analytics",
                    "granted": True,
                    "consent_version": "1.0",
                    "ip_address_hash": "abc123hash",
                },
            )

        assert resp.status_code == 201

    def test_invalid_consent_type_rejected(self, app_client: TestClient):
        resp = app_client.post(
            "/consent/",
            json={
                "consent_type": "invalid_type",
                "granted": True,
                "consent_version": "1.0",
            },
        )
        assert resp.status_code == 422

    def test_missing_consent_version_returns_422(self, app_client: TestClient):
        resp = app_client.post(
            "/consent/",
            json={
                "consent_type": "analytics",
                "granted": True,
            },
        )
        assert resp.status_code == 422

    def test_consent_requires_auth(self, unauthed_client: TestClient):
        resp = unauthed_client.post(
            "/consent/",
            json={
                "consent_type": "health_data_processing",
                "granted": True,
                "consent_version": "1.0",
            },
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /consent — list user consents
# ---------------------------------------------------------------------------


class TestGetConsents:
    def test_returns_latest_per_type(self, app_client: TestClient):
        records = [
            _make_orm_record(consent_type="health_data_processing", granted=True),
            _make_orm_record(consent_type="analytics", granted=False, withdrawn_at=NOW),
        ]

        with patch("app.api.v1.consent.ConsentRepository") as MockRepo:
            instance = AsyncMock()
            instance.get_by_user.return_value = records
            MockRepo.return_value = instance

            resp = app_client.get("/consent/")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 2

    def test_returns_empty_list_when_no_consents(self, app_client: TestClient):
        with patch("app.api.v1.consent.ConsentRepository") as MockRepo:
            instance = AsyncMock()
            instance.get_by_user.return_value = []
            MockRepo.return_value = instance

            resp = app_client.get("/consent/")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_requires_auth(self, unauthed_client: TestClient):
        resp = unauthed_client.get("/consent/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /consent/withdraw — withdraw
# ---------------------------------------------------------------------------


class TestWithdrawConsent:
    def test_withdraw_consent_inserts_new_row(self, app_client: TestClient):
        """Withdrawal must create a new row (granted=False), not update existing."""
        withdrawal_record = _make_orm_record(
            consent_type="coach_brain_contribution",
            granted=False,
            granted_at=None,
            withdrawn_at=NOW,
        )

        with patch("app.api.v1.consent.ConsentRepository") as MockRepo:
            instance = AsyncMock()
            instance.create.return_value = withdrawal_record
            MockRepo.return_value = instance

            resp = app_client.post(
                "/consent/withdraw",
                json={"consent_type": "coach_brain_contribution"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["granted"] is False
        assert body["withdrawn_at"] is not None

    def test_withdraw_invalid_type_returns_422(self, app_client: TestClient):
        resp = app_client.post(
            "/consent/withdraw",
            json={"consent_type": "not_a_real_type"},
        )
        assert resp.status_code == 422

    def test_withdraw_requires_auth(self, unauthed_client: TestClient):
        resp = unauthed_client.post(
            "/consent/withdraw",
            json={"consent_type": "analytics"},
        )
        assert resp.status_code == 401
