"""Endpoint tests for GET /api/v1/expert/sagittal-metrics-registry.

Session 3, L2-SAGITTAL-INFRA-02. The endpoint returns the 16-entry registry
to expert_reviewer + admin roles. Regular users get 403, anonymous gets 401/403.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_expert_reviewer_user
from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _expert_user() -> dict[str, Any]:
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "expert@example.com",
        "role": "expert_reviewer",
    }


def _admin_user() -> dict[str, Any]:
    return {
        "id": "00000000-0000-0000-0000-000000000002",
        "email": "admin@example.com",
        "role": "admin",
    }


@pytest.fixture
def expert_client() -> Iterator[TestClient]:
    """TestClient where get_expert_reviewer_user returns an expert."""
    app.dependency_overrides[get_expert_reviewer_user] = lambda: _expert_user()
    app.dependency_overrides[get_current_user] = lambda: _expert_user()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client() -> Iterator[TestClient]:
    app.dependency_overrides[get_expert_reviewer_user] = lambda: _admin_user()
    app.dependency_overrides[get_current_user] = lambda: _admin_user()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client() -> Iterator[TestClient]:
    """No overrides -- get_expert_reviewer_user runs its real JWT check
    which rejects unauthenticated calls."""
    yield TestClient(app)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestSagittalMetricsRegistryEndpoint:
    def test_expert_reviewer_gets_200_with_sixteen_entries(
        self, expert_client: TestClient
    ) -> None:
        resp = expert_client.get("/api/v1/expert/sagittal-metrics-registry")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "entries" in body
        assert len(body["entries"]) == 16

    def test_admin_gets_200_with_sixteen_entries(
        self, admin_client: TestClient
    ) -> None:
        resp = admin_client.get("/api/v1/expert/sagittal-metrics-registry")
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["entries"]) == 16

    def test_response_shape_matches_schema(
        self, expert_client: TestClient
    ) -> None:
        resp = expert_client.get("/api/v1/expert/sagittal-metrics-registry")
        entries = resp.json()["entries"]
        required_fields = {
            "key_name",
            "display_label",
            "unit",
            "description",
            "exercise_applicability",
            "computed_yet",
            "in_scoring",
        }
        for entry in entries:
            assert required_fields.issubset(entry.keys()), (
                f"Missing fields in entry {entry.get('key_name', '?')!r}: "
                f"{required_fields - set(entry.keys())}"
            )
            assert isinstance(entry["exercise_applicability"], list)
            assert isinstance(entry["computed_yet"], bool)
            assert isinstance(entry["in_scoring"], bool)

    def test_after_session3_no_metric_is_computed(
        self, expert_client: TestClient
    ) -> None:
        resp = expert_client.get("/api/v1/expert/sagittal-metrics-registry")
        for entry in resp.json()["entries"]:
            assert entry["computed_yet"] is False
            assert entry["in_scoring"] is False

    def test_lumbar_flexion_proxy_carries_naming_honesty(
        self, expert_client: TestClient
    ) -> None:
        resp = expert_client.get("/api/v1/expert/sagittal-metrics-registry")
        entries = {e["key_name"]: e for e in resp.json()["entries"]}
        lumbar = entries["lumbar_flexion_proxy_delta_deg"]
        assert "not lumbar" in lumbar["description"].lower()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestSagittalMetricsRegistryAuth:
    def test_unauthenticated_request_is_rejected(
        self, unauth_client: TestClient
    ) -> None:
        resp = unauth_client.get("/api/v1/expert/sagittal-metrics-registry")
        # get_expert_reviewer_user (via get_current_user) raises 401 / 403
        # when no JWT is present, depending on framework configuration.
        assert resp.status_code in (401, 403), resp.text

    def test_regular_user_role_is_rejected(self) -> None:
        """Override get_expert_reviewer_user to simulate a non-expert hitting
        the dependency -- the dep itself raises HTTPException(403)."""
        from fastapi import HTTPException, status

        def _reject() -> Any:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "expert_reviewer role required",
                        "detail": None,
                    }
                },
            )

        app.dependency_overrides[get_expert_reviewer_user] = _reject
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/expert/sagittal-metrics-registry")
            assert resp.status_code == 403, resp.text
        finally:
            app.dependency_overrides.clear()
