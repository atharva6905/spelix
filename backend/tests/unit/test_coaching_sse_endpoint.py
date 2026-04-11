"""
Integration-style tests for the coaching SSE HTTP endpoint (FR-AICP-07).

Tests the full GET /api/v1/analyses/{id}/coaching/stream endpoint
via httpx AsyncClient with mocked dependencies.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_redis
from app.api.v1.coaching_sse import router
from app.db import get_db

TEST_USER_ID = uuid.uuid4()
TEST_ANALYSIS_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis(*, user_id=None, analysis_id=None):
    obj = MagicMock()
    obj.id = analysis_id or TEST_ANALYSIS_ID
    obj.user_id = user_id or TEST_USER_ID
    obj.status = "coaching"
    return obj


def _make_coaching_result(*, stream_complete: bool = True):
    result = MagicMock()
    result.stream_complete = stream_complete
    result.structured_output_json = {
        "summary": "Good squat depth.",
        "strengths": ["Solid depth", "Knees tracking well"],
        "issues": [],
        "correction_plan": ["Keep it up."],
        "disclaimer": (
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        "raw_prompt_tokens": 400,
        "raw_completion_tokens": 200,
    }
    return result


def _build_app(
    *,
    analysis=None,
    coaching_result=None,
    redis_mock=None,
):
    """Build a FastAPI app with coaching SSE router and mocked deps."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/analyses")

    # Auth override
    async def _mock_user():
        return {"id": str(TEST_USER_ID), "email": "test@example.com", "role": "user"}

    app.dependency_overrides[get_current_user] = _mock_user

    # DB override — mock the session + repos
    mock_db = AsyncMock()

    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_db] = _mock_db

    # Redis override
    if redis_mock is None:
        redis_mock = AsyncMock()

    async def _mock_redis():
        yield redis_mock

    app.dependency_overrides[get_redis] = _mock_redis

    # Patch repositories at the module level
    from unittest.mock import patch

    mock_analysis_repo = AsyncMock()
    mock_analysis_repo.get_by_id = AsyncMock(return_value=analysis)

    mock_coaching_repo = AsyncMock()
    mock_coaching_repo.get_by_analysis = AsyncMock(return_value=coaching_result)

    app._test_patches = [
        patch("app.api.v1.coaching_sse.AnalysisRepository", return_value=mock_analysis_repo),
        patch("app.api.v1.coaching_sse.CoachingResultRepository", return_value=mock_coaching_repo),
    ]
    for p in app._test_patches:
        p.start()

    return app


def _stop_patches(app):
    for p in getattr(app, "_test_patches", []):
        p.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCoachingSSEEndpoint:
    @pytest.mark.asyncio
    async def test_returns_stored_output_when_complete(self):
        """When coaching is already complete, return stored output as SSE."""
        analysis = _make_analysis()
        coaching = _make_coaching_result(stream_complete=True)
        app = _build_app(analysis=analysis, coaching_result=coaching)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/v1/analyses/{TEST_ANALYSIS_ID}/coaching/stream",
                )

            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")

            # Parse SSE events
            body = resp.text
            assert "event: complete" in body
            # Extract data payload
            for line in body.strip().split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    assert data["summary"] == "Good squat depth."
                    assert "disclaimer" in data
                    break
            else:
                pytest.fail("No data line found in SSE response")
        finally:
            _stop_patches(app)

    @pytest.mark.asyncio
    async def test_404_when_analysis_not_found(self):
        """Returns 404 when analysis does not exist."""
        app = _build_app(analysis=None)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/v1/analyses/{uuid.uuid4()}/coaching/stream",
                )
            assert resp.status_code == 404
        finally:
            _stop_patches(app)

    @pytest.mark.asyncio
    async def test_403_when_not_owner(self):
        """Returns 403 when user does not own the analysis."""
        analysis = _make_analysis(user_id=OTHER_USER_ID)
        app = _build_app(analysis=analysis)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/v1/analyses/{TEST_ANALYSIS_ID}/coaching/stream",
                )
            assert resp.status_code == 403
        finally:
            _stop_patches(app)

    @pytest.mark.asyncio
    async def test_sse_headers_present(self):
        """SSE response has correct headers (Cache-Control, content-type)."""
        analysis = _make_analysis()
        coaching = _make_coaching_result(stream_complete=True)
        app = _build_app(analysis=analysis, coaching_result=coaching)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/v1/analyses/{TEST_ANALYSIS_ID}/coaching/stream",
                )
            assert resp.headers["cache-control"] == "no-cache"
            assert resp.headers.get("x-accel-buffering") == "no"
        finally:
            _stop_patches(app)

    @pytest.mark.asyncio
    async def test_pubsub_stream_when_not_complete(self):
        """When coaching is not yet complete, subscribes to Redis pub/sub."""
        analysis = _make_analysis()
        coaching_incomplete = _make_coaching_result(stream_complete=False)

        # Mock Redis pubsub that yields chunks then done
        mock_pubsub = AsyncMock()

        async def mock_listen():
            messages = [
                {"type": "subscribe", "data": 1},
                {"type": "message", "data": json.dumps({"type": "chunk", "text": "Keep "})},
                {"type": "message", "data": json.dumps({"type": "chunk", "text": "pushing."})},
                {"type": "message", "data": json.dumps({"type": "done"})},
            ]
            for msg in messages:
                yield msg

        mock_pubsub.listen = mock_listen
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Override coaching repo: first call returns incomplete, second returns complete
        from unittest.mock import patch

        complete_coaching = _make_coaching_result(stream_complete=True)

        app = _build_app(
            analysis=analysis,
            coaching_result=coaching_incomplete,
            redis_mock=mock_redis,
        )

        # Re-patch coaching repo for the pubsub path's second DB check
        mock_coaching_repo = AsyncMock()
        mock_coaching_repo.get_by_analysis = AsyncMock(
            side_effect=[
                coaching_incomplete,  # Initial endpoint check
                None,  # Race check inside _stream_from_pubsub
                complete_coaching,  # Final fetch on "done"
            ]
        )
        # Stop existing patches and re-apply with new coaching repo
        _stop_patches(app)
        mock_analysis_repo = AsyncMock()
        mock_analysis_repo.get_by_id = AsyncMock(return_value=analysis)
        app._test_patches = [
            patch("app.api.v1.coaching_sse.AnalysisRepository", return_value=mock_analysis_repo),
            patch("app.api.v1.coaching_sse.CoachingResultRepository", return_value=mock_coaching_repo),
        ]
        for p in app._test_patches:
            p.start()

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/v1/analyses/{TEST_ANALYSIS_ID}/coaching/stream",
                )

            assert resp.status_code == 200
            body = resp.text

            # Should have chunk data events and a complete event
            assert '"text": "Keep "' in body
            assert '"text": "pushing."' in body
            assert "event: complete" in body
        finally:
            _stop_patches(app)
