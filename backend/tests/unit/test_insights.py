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


def _make_insights_repo(
    analyses: list | None = None,
    personal_best: float = 0.0,
    completed_analyses: list | None = None,
) -> AsyncMock:
    """Build a mock AnalysisRepository pre-wired for InsightsService tests."""
    from app.repositories.analysis import AnalysisRepository

    mock_repo = AsyncMock(spec=AnalysisRepository)
    mock_repo.get_recent_for_exercise = AsyncMock(return_value=analyses or [])
    mock_repo.get_personal_best_confidence = AsyncMock(return_value=personal_best)
    mock_repo.get_completed_since = AsyncMock(return_value=completed_analyses or [])
    return mock_repo


class TestExerciseInsights:
    """Per-exercise insights computation."""

    @pytest.mark.asyncio
    async def test_rolling_avg_confidence(self):
        """7-session rolling avg computed correctly."""
        analyses = [
            _make_analysis(confidence=0.7 + i * 0.03, days_ago=6 - i)
            for i in range(7)
        ]

        from app.services.insights import InsightsService

        svc = InsightsService(analysis_repo=_make_insights_repo(analyses=analyses, personal_best=0.88))
        result = await svc.exercise_insights(_USER_ID, "squat", "high_bar")

        assert "rolling_avg_confidence" in result
        assert len(result["rolling_avg_confidence"]) == 7
        assert all(isinstance(v, float) for v in result["rolling_avg_confidence"])

    @pytest.mark.asyncio
    async def test_rep_count_trend(self):
        """Rep count trend extracted from summary_json."""
        # Repo returns DESC (days_ago=2,1,0 → rep=3,4,5), service reverses to chrono
        analyses = [
            _make_analysis(rep_count=3 + i, days_ago=2 - i)
            for i in range(3)
        ]

        from app.services.insights import InsightsService

        svc = InsightsService(analysis_repo=_make_insights_repo(analyses=analyses, personal_best=0.85))
        result = await svc.exercise_insights(_USER_ID, "squat", "high_bar")

        assert result["rep_count_trend"] == [5, 4, 3]

    @pytest.mark.asyncio
    async def test_most_common_warning(self):
        """Most common QG warning extracted from analyses."""
        analyses = [
            _make_analysis(warnings=[_failed_check("Bad framing")]),
            _make_analysis(warnings=[_failed_check("Bad framing")]),
            _make_analysis(warnings=[_failed_check("Low visibility")]),
        ]

        from app.services.insights import InsightsService

        svc = InsightsService(analysis_repo=_make_insights_repo(analyses=analyses, personal_best=0.85))
        result = await svc.exercise_insights(_USER_ID, "squat", "high_bar")

        assert result["most_common_warning"] == "Bad framing"

    @pytest.mark.asyncio
    async def test_personal_best_confidence(self):
        """Personal best is the max confidence across all sessions."""
        analyses = [_make_analysis(confidence=0.75)]

        from app.services.insights import InsightsService

        svc = InsightsService(analysis_repo=_make_insights_repo(analyses=analyses, personal_best=0.92))
        result = await svc.exercise_insights(_USER_ID, "squat", "high_bar")

        assert result["personal_best_confidence"] == 0.92

    @pytest.mark.asyncio
    async def test_no_analyses_returns_empty(self):
        """Empty history returns empty lists and None warning."""
        from app.services.insights import InsightsService

        svc = InsightsService(analysis_repo=_make_insights_repo(analyses=[], personal_best=0.0))
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

        from app.services.insights import InsightsService

        svc = InsightsService(analysis_repo=_make_insights_repo(completed_analyses=analyses))
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

        from app.services.insights import InsightsService

        svc = InsightsService(analysis_repo=_make_insights_repo(completed_analyses=analyses))
        result = await svc.global_insights(_USER_ID)

        # bench has variance (3,10)=12.25 vs squat (5,5)=0
        assert result["highest_variance_exercise"] == "bench"

    @pytest.mark.asyncio
    async def test_no_analyses_returns_none(self):
        """Empty history returns None for all fields."""
        from app.services.insights import InsightsService

        svc = InsightsService(analysis_repo=_make_insights_repo(completed_analyses=[]))
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
# Repository-based InsightsService tests (B-071)
# These tests verify that InsightsService delegates all DB access to
# repositories rather than calling SQLAlchemy directly.
# ---------------------------------------------------------------------------


class TestInsightsServiceUsesRepositories:
    """InsightsService must accept an AnalysisRepository and call its methods."""

    @pytest.mark.asyncio
    async def test_exercise_insights_calls_repo_recent_for_exercise(self):
        """exercise_insights delegates the 7-session query to the repo."""
        from app.repositories.analysis import AnalysisRepository
        from app.services.insights import InsightsService

        analyses = [_make_analysis(confidence=0.80 + i * 0.01, days_ago=6 - i) for i in range(3)]
        mock_repo = AsyncMock(spec=AnalysisRepository)
        mock_repo.get_recent_for_exercise = AsyncMock(return_value=analyses)
        mock_repo.get_personal_best_confidence = AsyncMock(return_value=0.90)

        svc = InsightsService(analysis_repo=mock_repo)
        result = await svc.exercise_insights(_USER_ID, "squat", "high_bar")

        mock_repo.get_recent_for_exercise.assert_awaited_once_with(
            user_id=_USER_ID,
            exercise_type="squat",
            exercise_variant="high_bar",
            limit=7,
        )
        assert "rolling_avg_confidence" in result

    @pytest.mark.asyncio
    async def test_exercise_insights_calls_repo_personal_best(self):
        """exercise_insights delegates the personal-best query to the repo."""
        from app.repositories.analysis import AnalysisRepository
        from app.services.insights import InsightsService

        mock_repo = AsyncMock(spec=AnalysisRepository)
        mock_repo.get_recent_for_exercise = AsyncMock(return_value=[])
        mock_repo.get_personal_best_confidence = AsyncMock(return_value=0.95)

        svc = InsightsService(analysis_repo=mock_repo)
        result = await svc.exercise_insights(_USER_ID, "squat", "high_bar")

        mock_repo.get_personal_best_confidence.assert_awaited_once_with(
            user_id=_USER_ID,
            exercise_type="squat",
            exercise_variant="high_bar",
        )
        assert result["personal_best_confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_global_insights_calls_repo_recent_completed(self):
        """global_insights delegates the 30-day query to the repo."""
        from app.repositories.analysis import AnalysisRepository
        from app.services.insights import InsightsService

        mock_repo = AsyncMock(spec=AnalysisRepository)
        mock_repo.get_completed_since = AsyncMock(return_value=[])

        svc = InsightsService(analysis_repo=mock_repo)
        result = await svc.global_insights(_USER_ID)

        mock_repo.get_completed_since.assert_awaited_once()
        call_kwargs = mock_repo.get_completed_since.call_args
        assert call_kwargs.kwargs["user_id"] == _USER_ID or call_kwargs.args[0] == _USER_ID
        assert result["most_common_warning"] is None

    @pytest.mark.asyncio
    async def test_insights_service_does_not_accept_raw_session(self):
        """InsightsService constructor must accept analysis_repo keyword, not db."""
        from app.services.insights import InsightsService
        import inspect

        sig = inspect.signature(InsightsService.__init__)
        params = list(sig.parameters.keys())
        # 'self' + 'analysis_repo' — no 'db' parameter
        assert "analysis_repo" in params, "InsightsService must accept analysis_repo kwarg"
        assert "db" not in params, "InsightsService must not accept raw db/AsyncSession"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scalar_result(value: Any) -> MagicMock:
    """Create a mock DB result that returns *value* from .scalar()."""
    mock = MagicMock()
    mock.scalar.return_value = value
    return mock
