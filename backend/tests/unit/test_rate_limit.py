"""Unit tests for rate limiting on POST /api/v1/analyses.

NFR-SECU-10: 10 uploads per user per day.

These tests verify the rate limit integration by checking that the limiter
is attached to the create_analysis endpoint and that the 429 response is
returned after exceeding the limit.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.deps import CurrentUser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()


def _mock_user() -> CurrentUser:
    return CurrentUser(id=_USER_ID, email="test@example.com", role="user")


class _FakeCreateResult:
    def __init__(self) -> None:
        self.analysis = MagicMock()
        self.analysis.id = uuid.uuid4()
        self.analysis.status = "queued"
        self.upload_url = "https://storage.example.com/upload"
        self.expires_at = datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def client():
    """Create a test client with rate limiting enabled but using memory storage."""
    # Import inside fixture to avoid import-time side effects
    from app.main import app
    from app.api.deps import get_current_user
    from app.api.v1.analyses import _get_service

    # Mock auth
    async def _auth_override():
        return _mock_user()

    app.dependency_overrides[get_current_user] = _auth_override

    # Mock service
    fake_analysis = MagicMock()
    fake_analysis.id = uuid.uuid4()
    fake_analysis.status = "quality_gate_pending"

    mock_service = AsyncMock()
    mock_service.create_analysis = AsyncMock(return_value=_FakeCreateResult())
    mock_service.start_analysis = AsyncMock(return_value=fake_analysis)

    async def _service_override():
        return mock_service

    app.dependency_overrides[_get_service] = _service_override

    from limits.storage import MemoryStorage

    from app.rate_limit import limiter

    # Swap to in-memory storage AFTER app startup to avoid Redis dependency
    with TestClient(app) as c:
        mem = MemoryStorage()
        limiter._storage = mem
        limiter._limiter.storage = mem
        limiter.reset()
        yield c

    app.dependency_overrides.clear()


_VALID_BODY = {
    "exercise_type": "squat",
    "exercise_variant": "high_bar",
    "filename": "test.mp4",
    "file_size_bytes": 1_000_000,
}


class TestRateLimiting:
    """Verify that POST /api/v1/analyses is rate limited to 10/day per user."""

    def test_request_within_limit_succeeds(self, client: TestClient) -> None:
        resp = client.post("/api/v1/analyses", json=_VALID_BODY)
        assert resp.status_code == status.HTTP_201_CREATED

    def test_11th_request_returns_429(self, client: TestClient) -> None:
        """After 10 successful requests, the 11th should be rejected."""
        for i in range(10):
            resp = client.post("/api/v1/analyses", json=_VALID_BODY)
            assert resp.status_code == status.HTTP_201_CREATED, (
                f"Request {i + 1} should succeed, got {resp.status_code}"
            )

        # 11th request should be rate limited
        resp = client.post("/api/v1/analyses", json=_VALID_BODY)
        assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_rate_limit_headers_present(self, client: TestClient) -> None:
        """Rate limit response headers should be present."""
        resp = client.post("/api/v1/analyses", json=_VALID_BODY)
        assert resp.status_code == status.HTTP_201_CREATED
        # slowapi adds X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
        assert "X-RateLimit-Limit" in resp.headers or "x-ratelimit-limit" in resp.headers

    def test_start_endpoint_not_rate_limited(self, client: TestClient) -> None:
        """POST /analyses/{id}/start should NOT be rate limited even after many calls."""
        fake_id = uuid.uuid4()
        # Call start endpoint 11+ times — it should never return 429
        # (it will return other errors like 500 due to mock, but not 429)
        for _ in range(12):
            resp = client.post(f"/api/v1/analyses/{fake_id}/start")
            assert resp.status_code != status.HTTP_429_TOO_MANY_REQUESTS
