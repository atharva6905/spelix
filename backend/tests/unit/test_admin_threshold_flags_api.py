"""Unit tests for FR-EXPV-08 admin threshold-flag endpoints.

Tests:
    GET  /api/v1/admin/threshold-flags          — list all flags (mocked repo)
    PATCH /api/v1/admin/threshold-flags/{id}    — resolve flag (mocked repo)
    PATCH /api/v1/admin/threshold-flags/{id}    — 404 when flag missing (mocked repo)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_admin_user
from app.api.v1.admin import _get_threshold_flag_repo, router as admin_router
from app.models.threshold_flag import ThresholdFlag


@pytest.fixture
def admin_user():
    return {"id": uuid4(), "role": "admin"}


@pytest.fixture
def fake_repo():
    return AsyncMock()


@pytest.fixture
def client(admin_user, fake_repo):
    test_app = FastAPI()
    test_app.include_router(admin_router, prefix="/api/v1/admin")
    test_app.dependency_overrides[get_admin_user] = lambda: admin_user
    test_app.dependency_overrides[_get_threshold_flag_repo] = lambda: fake_repo
    return TestClient(test_app)


def _make_flag(**overrides) -> ThresholdFlag:
    """Factory helper — ThresholdFlagResponse requires non-null created_at/updated_at,
    so we populate them explicitly (server_default only fires on real DB insert)."""
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid4(),
        reviewer_id=uuid4(),
        section="squat",
        key="knee_valgus_caution_deg",
        current_value=5.0,
        current_citation="Myer et al. 2010",
        proposed_value=8.0,
        proposed_citation="Krosshaug 2016",
        rationale="An adequate-length rationale explaining the issue.",
        status="open",
        resolution_note=None,
        resolved_by=None,
        resolved_at=None,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return ThresholdFlag(**defaults)


def test_admin_list_threshold_flags_returns_rows(client, fake_repo):
    flag = _make_flag()
    fake_repo.list_all.return_value = [flag]

    resp = client.get("/api/v1/admin/threshold-flags?status=open")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "open"
    fake_repo.list_all.assert_awaited_once_with(status="open", limit=50, offset=0)


def test_admin_resolve_threshold_flag_returns_updated(client, fake_repo, admin_user):
    flag_id = uuid4()
    now = datetime.now(timezone.utc)
    resolved = _make_flag(
        id=flag_id,
        status="resolved",
        resolution_note="Merged PR #999",
        resolved_by=admin_user["id"],
        resolved_at=now,
    )
    fake_repo.update_status.return_value = resolved

    resp = client.patch(
        f"/api/v1/admin/threshold-flags/{flag_id}",
        json={"status": "resolved", "resolution_note": "Merged PR #999"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolution_note"] == "Merged PR #999"


def test_admin_resolve_returns_404_when_row_missing(client, fake_repo):
    fake_repo.update_status.return_value = None

    resp = client.patch(
        f"/api/v1/admin/threshold-flags/{uuid4()}",
        json={"status": "rejected", "resolution_note": None},
    )

    assert resp.status_code == 404
