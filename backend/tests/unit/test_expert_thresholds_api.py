"""Unit tests for FR-EXPV-08 expert threshold endpoints.

Tests:
    GET  /api/v1/expert/thresholds          — threshold listing (real config)
    POST /api/v1/expert/thresholds/flags    — flag creation (mocked service)
    POST /api/v1/expert/thresholds/flags    — unknown key → 422 (mocked service)
    GET  /api/v1/expert/thresholds/flags    — reviewer flag listing (mocked repo)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_expert_reviewer_user
from app.api.v1.expert import _get_threshold_flag_repo, _get_threshold_service, router as expert_router
from app.models.threshold_flag import ThresholdFlag
from app.services.threshold_flag import InvalidThresholdKey, ThresholdFlagService


def _make_flag(reviewer_id, section: str, key: str, proposed_value: float) -> ThresholdFlag:
    """Create a ThresholdFlag with all required datetime fields set."""
    now = datetime.now(timezone.utc)
    return ThresholdFlag(
        id=uuid4(),
        reviewer_id=reviewer_id,
        section=section,
        key=key,
        current_value=5.0,
        current_citation="Myer et al. 2010",
        proposed_value=proposed_value,
        proposed_citation="Krosshaug 2016 — 8° not replicated",
        rationale="Original Myer finding did not replicate in larger cohorts.",
        status="open",
        resolution_note=None,
        resolved_by=None,
        resolved_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture()
def reviewer_user():
    return {"id": uuid4(), "role": "expert_reviewer"}


@pytest.fixture()
def bare_app(reviewer_user):
    """Fresh FastAPI with the expert router and auth mocked out."""
    app = FastAPI()
    app.include_router(expert_router, prefix="/api/v1/expert")

    async def _mock_expert():
        return reviewer_user

    app.dependency_overrides[get_expert_reviewer_user] = _mock_expert
    return app


def test_get_thresholds_returns_angle_sections_only(bare_app):
    # Relies on real ThresholdConfig loader — no service override needed
    # because get_listing() is pure.
    client = TestClient(bare_app)
    resp = client.get("/api/v1/expert/thresholds")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "v1"
    assert set(body["sections"].keys()) == {"squat", "bench", "deadlift", "control"}
    squat_keys = {r["key"] for r in body["sections"]["squat"]}
    assert "knee_valgus_caution_deg" in squat_keys


def test_post_flag_creates_row(bare_app, reviewer_user):
    fake_service = AsyncMock(spec=ThresholdFlagService)
    created = _make_flag(
        reviewer_id=reviewer_user["id"],
        section="squat",
        key="knee_valgus_caution_deg",
        proposed_value=8.0,
    )
    fake_service.create_flag.return_value = created

    bare_app.dependency_overrides[_get_threshold_service] = lambda: fake_service

    client = TestClient(bare_app)
    resp = client.post(
        "/api/v1/expert/thresholds/flags",
        json={
            "section": "squat",
            "key": "knee_valgus_caution_deg",
            "proposed_value": 8.0,
            "proposed_citation": "Krosshaug 2016 — 8° not replicated",
            "rationale": "Original Myer finding did not replicate in larger cohorts.",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["section"] == "squat"
    assert body["proposed_value"] == 8.0
    assert body["current_value"] == 5.0
    fake_service.create_flag.assert_awaited_once()


def test_post_flag_returns_422_for_unknown_key(bare_app):
    fake_service = AsyncMock(spec=ThresholdFlagService)
    fake_service.create_flag.side_effect = InvalidThresholdKey(
        "Unknown threshold key 'nope' for section 'squat'"
    )

    bare_app.dependency_overrides[_get_threshold_service] = lambda: fake_service

    client = TestClient(bare_app)
    resp = client.post(
        "/api/v1/expert/thresholds/flags",
        json={
            "section": "squat",
            "key": "knee_valgus_caution_deg",
            "proposed_value": 8.0,
            "proposed_citation": "Krosshaug 2016",
            "rationale": "An adequate-length rationale explaining the issue.",
        },
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]["error"]["code"] == "UNKNOWN_THRESHOLD_KEY"


def test_get_my_flags_returns_reviewer_flags(bare_app, reviewer_user):
    flag = _make_flag(
        reviewer_id=reviewer_user["id"],
        section="bench",
        key="elbow_flare_caution_deg",
        proposed_value=55.0,
    )
    flag.current_value = 45.0
    flag.current_citation = "Green & Comfort 2007"
    flag.proposed_citation = "Nuckols 2024"
    flag.rationale = "A more permissive flare may be biomechanically acceptable."

    fake_repo = AsyncMock()
    fake_repo.list_by_reviewer.return_value = [flag]

    bare_app.dependency_overrides[_get_threshold_flag_repo] = lambda: fake_repo

    client = TestClient(bare_app)
    resp = client.get("/api/v1/expert/thresholds/flags?limit=10&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["key"] == "elbow_flare_caution_deg"
