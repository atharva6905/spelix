"""Unit tests for /api/v1/admin/beta-requests endpoints.

Admin beta-request approval UI — no SRS FR-ID (ops task).
Pattern mirrors test_admin_candidates_api.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.admin import router


TEST_ADMIN_ID = uuid.uuid4()


def _make_beta_request(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    defaults = dict(
        id=str(uuid.uuid4()),
        email="user@example.com",
        source="hero",
        status="pending",
        created_at=now,
        approved_at=None,
        approved_by=None,
        invite_sent_at=None,
    )
    defaults.update(overrides)
    return defaults


@pytest.fixture()
def mock_repo():
    from unittest.mock import MagicMock
    return MagicMock()


@pytest.fixture()
def admin_client(mock_repo):
    from app.api.deps import get_admin_user
    from app.api.v1.admin import _get_beta_repo

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin")

    async def _mock_admin():
        return {
            "id": TEST_ADMIN_ID,
            "email": "admin@spelix.app",
            "role": "admin",
        }

    async def _mock_beta_repo():
        return mock_repo

    app.dependency_overrides[get_admin_user] = _mock_admin
    app.dependency_overrides[_get_beta_repo] = _mock_beta_repo
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def non_admin_client():
    from app.api.deps import get_admin_user

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin")

    # Override get_admin_user to raise 403 (simulate non-admin)
    async def _forbidden():
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")

    app.dependency_overrides[get_admin_user] = _forbidden
    return TestClient(app, raise_server_exceptions=False)


class TestListBetaRequests:
    def test_non_admin_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/beta-requests")
        assert resp.status_code == 403

    def test_admin_list_returns_200(self, admin_client, mock_repo):
        rows = [_make_beta_request(), _make_beta_request(email="b@x.com")]
        mock_repo.list_all = AsyncMock(return_value=rows)

        resp = admin_client.get("/api/v1/admin/beta-requests")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["email"] == "user@example.com"
        assert "created_at" in body[0]


class TestBetaRequestStats:
    def test_stats_returns_counts(self, admin_client, mock_repo):
        mock_repo.get_stats = AsyncMock(
            return_value={"pending": 3, "approved": 1, "rejected": 0, "total": 4}
        )

        resp = admin_client.get("/api/v1/admin/beta-requests/stats")

        assert resp.status_code == 200
        body = resp.json()
        assert body["pending"] == 3
        assert body["approved"] == 1
        assert body["rejected"] == 0
        assert body["total"] == 4


class TestApproveBetaRequest:
    def test_approve_returns_200(self, admin_client, mock_repo):
        rid = uuid.uuid4()
        now = datetime.now(timezone.utc).isoformat()
        approved = _make_beta_request(
            id=str(rid),
            status="approved",
            approved_at=now,
            approved_by=str(TEST_ADMIN_ID),
        )
        mock_repo.approve = AsyncMock(return_value=approved)

        resp = admin_client.post(f"/api/v1/admin/beta-requests/{rid}/approve")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["approved_by"] == str(TEST_ADMIN_ID)

    def test_approve_nonexistent_returns_404(self, admin_client, mock_repo):
        rid = uuid.uuid4()
        mock_repo.approve = AsyncMock(return_value=None)

        resp = admin_client.post(f"/api/v1/admin/beta-requests/{rid}/approve")

        assert resp.status_code == 404


class TestRejectBetaRequest:
    def test_reject_returns_200(self, admin_client, mock_repo):
        rid = uuid.uuid4()
        rejected = _make_beta_request(id=str(rid), status="rejected")
        mock_repo.reject = AsyncMock(return_value=rejected)

        resp = admin_client.post(f"/api/v1/admin/beta-requests/{rid}/reject")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rejected"
