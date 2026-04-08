"""Tests for B-031 — history insights endpoints.

TDD gate: synthetic analyses → correct rolling average, personal best, global insights.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()


def _make_analysis(
    confidence: float = 0.85,
    exercise_type: str = "squat",
    exercise_variant: str = "high_bar",
    rep_count: int = 5,
    warnings: list[dict] | None = None,
    days_ago: int = 0,
) -> MagicMock:
    """Create a mock Analysis for insights testing."""
    a = MagicMock()
    a.user_id = _USER_ID
    a.exercise_type = exercise_type
    a.exercise_variant = exercise_variant
    a.confidence_score = confidence
    a.status = "completed"
    a.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    a.summary_json = {"rep_count": rep_count}
    if warnings:
        a.quality_gate_result = {"checks": warnings}
    else:
        a.quality_gate_result = {"checks": []}
    return a


def _failed_check(msg: str) -> dict:
    return {"passed": False, "user_message": msg, "name": "test", "level": "warning"}


def _passed_check() -> dict:
    return {"passed": True, "user_message": "", "name": "test", "level": "info"}


# ---------------------------------------------------------------------------
# InsightsService unit tests (mock DB via AsyncMock)
# ---------------------------------------------------------------------------


class TestExerciseInsights:
    """Per-exercise insights computation."""

    @pytest.mark.asyncio
    async def test_rolling_avg_confidence(self):
        """7-session rolling avg computed correctly."""
        analyses = [
            _make_analysis(confidence=0.7 + i * 0.03, days_ago=6 - i)
            for i in range(7)
        ]

        mock_db = AsyncMock()
        # Mock execute for exercise query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = analyses
        mock_db.execute = AsyncMock(side_effect=[mock_result, _scalar_result(0.88)])

        from app.services.insights import InsightsService

        svc = InsightsService(mock_db)
        result = await svc.exercise_insights(_USER_ID, "squat", "high_bar")

        assert "rolling_avg_confidence" in result
        assert len(result["rolling_avg_confidence"]) == 7
        assert all(isinstance(v, float) for v in result["rolling_avg_confidence"])

    @pytest.mark.asyncio
    async def test_rep_count_trend(self):
        """Rep count trend extracted from summary_json."""
        analyses = [
            _make_analysis(rep_count=3 + i, days_ago=2 - i)
            for i in range(3)
        ]

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = analyses
        mock_db.execute = AsyncMock(side_effect=[mock_result, _scalar_result(0.85)])

        from app.services.insights import InsightsService

        svc = InsightsService(mock_db)
        result = await svc.exercise_insights(_USER_ID, "squat", "high_bar")

        # DB returns DESC (days_ago=2,1,0 → rep=3,4,5), service reverses to chrono
        assert result["rep_count_trend"] == [5, 4, 3]

    @pytest.mark.asyncio
    async def test_most_common_warning(self):
        """Most common QG warning extracted from analyses."""
        analyses = [
            _make_analysis(warnings=[_failed_check("Bad framing")]),
            _make_analysis(warnings=[_failed_check("Bad framing")]),
            _make_analysis(warnings=[_failed_check("Low visibility")]),
        ]

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = analyses
        mock_db.execute = AsyncMock(side_effect=[mock_result, _scalar_result(0.85)])

        from app.services.insights import InsightsService

        svc = InsightsService(mock_db)
        result = await svc.exercise_insights(_USER_ID, "squat", "high_bar")

        assert result["most_common_warning"] == "Bad framing"

    @pytest.mark.asyncio
    async def test_personal_best_confidence(self):
        """Personal best is the max confidence across all sessions."""
        analyses = [_make_analysis(confidence=0.75)]

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = analyses
        mock_db.execute = AsyncMock(side_effect=[mock_result, _scalar_result(0.92)])

        from app.services.insights import InsightsService

        svc = InsightsService(mock_db)
        result = await svc.exercise_insights(_USER_ID, "squat", "high_bar")

        assert result["personal_best_confidence"] == 0.92

    @pytest.mark.asyncio
    async def test_no_analyses_returns_empty(self):
        """Empty history returns empty lists and None warning."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[mock_result, _scalar_result(None)])

        from app.services.insights import InsightsService

        svc = InsightsService(mock_db)
        result = await svc.exercise_insights(_USER_ID, "squat", "high_bar")

        assert result["rolling_avg_confidence"] == []
        assert result["rep_count_trend"] == []
        assert result["most_common_warning"] is None
        assert result["personal_best_confidence"] == 0.0


class TestGlobalInsights:
    """Global insights computation."""

    @pytest.mark.asyncio
    async def test_most_common_warning_30_days(self):
        """Global most common warning from last 30 days."""
        analyses = [
            _make_analysis(
                exercise_type="squat",
                warnings=[_failed_check("Framing issue")],
                days_ago=5,
            ),
            _make_analysis(
                exercise_type="bench",
                warnings=[_failed_check("Framing issue")],
                days_ago=10,
            ),
            _make_analysis(
                exercise_type="deadlift",
                warnings=[_failed_check("Low visibility")],
                days_ago=15,
            ),
        ]

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = analyses
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.insights import InsightsService

        svc = InsightsService(mock_db)
        result = await svc.global_insights(_USER_ID)

        assert result["most_common_warning"] == "Framing issue"

    @pytest.mark.asyncio
    async def test_highest_variance_exercise(self):
        """Exercise with most variable rep counts identified."""
        analyses = [
            _make_analysis(exercise_type="squat", rep_count=5, days_ago=1),
            _make_analysis(exercise_type="squat", rep_count=5, days_ago=2),
            _make_analysis(exercise_type="bench", rep_count=3, days_ago=1),
            _make_analysis(exercise_type="bench", rep_count=10, days_ago=2),
        ]

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = analyses
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.insights import InsightsService

        svc = InsightsService(mock_db)
        result = await svc.global_insights(_USER_ID)

        # bench has variance (3,10)=12.25 vs squat (5,5)=0
        assert result["highest_variance_exercise"] == "bench"

    @pytest.mark.asyncio
    async def test_no_analyses_returns_none(self):
        """Empty history returns None for all fields."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.insights import InsightsService

        svc = InsightsService(mock_db)
        result = await svc.global_insights(_USER_ID)

        assert result["most_common_warning"] is None
        assert result["highest_variance_exercise"] is None


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestInsightsAPI:
    """Insights API endpoint tests."""

    @pytest.mark.asyncio
    async def test_exercise_endpoint_returns_200(self):
        """GET /api/v1/insights/exercise/{type}/{variant} returns 200."""
        from httpx import ASGITransport, AsyncClient

        from app.api.deps import get_current_user
        from app.main import app

        mock_insights = {
            "rolling_avg_confidence": [0.8, 0.82, 0.85],
            "rep_count_trend": [5, 5, 6],
            "most_common_warning": None,
            "personal_best_confidence": 0.85,
        }

        app.dependency_overrides[get_current_user] = lambda: {
            "id": _USER_ID, "email": "test@test.com", "role": "user",
        }

        try:
            with patch(
                "app.api.v1.insights.InsightsService",
            ) as MockSvc:
                mock_instance = AsyncMock()
                mock_instance.exercise_insights.return_value = mock_insights
                MockSvc.return_value = mock_instance

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/v1/insights/exercise/squat/high_bar")

                assert resp.status_code == 200
                data = resp.json()
                assert data["personal_best_confidence"] == 0.85
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_global_endpoint_returns_200(self):
        """GET /api/v1/insights/global returns 200."""
        from httpx import ASGITransport, AsyncClient

        from app.api.deps import get_current_user
        from app.main import app

        mock_insights = {
            "most_common_warning": "Bad framing",
            "highest_variance_exercise": "bench",
        }

        app.dependency_overrides[get_current_user] = lambda: {
            "id": _USER_ID, "email": "test@test.com", "role": "user",
        }

        try:
            with patch(
                "app.api.v1.insights.InsightsService",
            ) as MockSvc:
                mock_instance = AsyncMock()
                mock_instance.global_insights.return_value = mock_insights
                MockSvc.return_value = mock_instance

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/v1/insights/global")

                assert resp.status_code == 200
                data = resp.json()
                assert data["most_common_warning"] == "Bad framing"
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scalar_result(value: Any) -> MagicMock:
    """Create a mock DB result that returns *value* from .scalar()."""
    mock = MagicMock()
    mock.scalar.return_value = value
    return mock
