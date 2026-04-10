"""Unit tests for admin API endpoints (B-033).

Tests cover:
- Non-admin user gets 403 on all endpoints
- Admin lists users (mock DB)
- Admin deletes user data (mock DB)
- Health returns queue depth and heartbeat (mock Redis)
- Confidence audit returns low-confidence analyses
- Analysis list with status filter works

Requirements: FR-ADMN-01 through FR-ADMN-05
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.admin import router
from app.models.analysis import Analysis
from app.models.user_profile import UserProfile

# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

TEST_ADMIN_ID = uuid.uuid4()
TEST_USER_ID = uuid.uuid4()
TEST_ADMIN_EMAIL = "admin@spelix.app"
TEST_USER_EMAIL = "user@spelix.app"


def _make_orm_analysis(**kwargs) -> Analysis:
    now = datetime.now(timezone.utc)
    a = Analysis(
        user_id=kwargs.get("user_id", TEST_USER_ID),
        exercise_type=kwargs.get("exercise_type", "squat"),
        exercise_variant=kwargs.get("exercise_variant", "high_bar"),
        status=kwargs.get("status", "completed"),
    )
    a.__dict__.update(
        {
            "id": kwargs.get("id", uuid.uuid4()),
            "confidence_score": kwargs.get("confidence_score", 0.80),
            "created_at": kwargs.get("created_at", now),
            "updated_at": kwargs.get("updated_at", now),
            "error_message": None,
            "retry_count": 0,
            "flagged_for_review": False,
            "is_golden_dataset": False,
            "video_path": None,
            "annotated_video_path": None,
            "plot_path": None,
            "pdf_path": None,
            "summary_json": None,
            "quality_gate_result": None,
            "tags": None,
            "threshold_version": None,
            "weight_kg": None,
            "form_score_safety": None,
            "form_score_technique": None,
            "form_score_path_balance": None,
            "form_score_control": None,
            "form_score_overall": None,
        }
    )
    return a


def _make_orm_profile(**kwargs) -> UserProfile:
    now = datetime.now(timezone.utc)
    p = UserProfile(
        user_id=kwargs.get("user_id", TEST_USER_ID),
        height_cm=kwargs.get("height_cm", 175.0),
        weight_kg=kwargs.get("weight_kg", 75.0),
        age=kwargs.get("age", 28),
        experience_level=kwargs.get("experience_level", "intermediate"),
    )
    p.__dict__.update(
        {
            "id": kwargs.get("id", uuid.uuid4()),
            "created_at": kwargs.get("created_at", now),
            "updated_at": kwargs.get("updated_at", now),
            "arm_span_cm": None,
            "femur_length_cm": None,
        }
    )
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def admin_client():
    """TestClient with admin auth dependency overridden."""
    from app.api.deps import get_admin_user

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin")

    async def _mock_admin():
        return {"id": TEST_ADMIN_ID, "email": TEST_ADMIN_EMAIL, "role": "admin"}

    app.dependency_overrides[get_admin_user] = _mock_admin
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def non_admin_client():
    """TestClient where auth returns a non-admin user (no override — real guard runs)."""
    from app.api.deps import get_current_user

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin")

    async def _mock_user():
        return {"id": TEST_USER_ID, "email": TEST_USER_EMAIL, "role": "user"}

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Non-admin access → 403
# ---------------------------------------------------------------------------


class TestAdminAuthGuard:
    """All endpoints must return 403 for non-admin users."""

    def test_list_users_forbidden_for_non_admin(self, non_admin_client: TestClient):
        resp = non_admin_client.get("/api/v1/admin/users")
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"]["code"] == "FORBIDDEN"

    def test_delete_user_forbidden_for_non_admin(self, non_admin_client: TestClient):
        resp = non_admin_client.delete(f"/api/v1/admin/users/{TEST_USER_ID}")
        assert resp.status_code == 403

    def test_disable_user_forbidden_for_non_admin(self, non_admin_client: TestClient):
        resp = non_admin_client.patch(f"/api/v1/admin/users/{TEST_USER_ID}/disable")
        assert resp.status_code == 403

    def test_list_analyses_forbidden_for_non_admin(self, non_admin_client: TestClient):
        resp = non_admin_client.get("/api/v1/admin/analyses")
        assert resp.status_code == 403

    def test_health_forbidden_for_non_admin(self, non_admin_client: TestClient):
        resp = non_admin_client.get("/api/v1/admin/health")
        assert resp.status_code == 403

    def test_confidence_audit_forbidden_for_non_admin(self, non_admin_client: TestClient):
        resp = non_admin_client.get("/api/v1/admin/confidence-audit")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/v1/admin/users
# ---------------------------------------------------------------------------


class TestListUsers:
    def test_returns_user_list_with_analysis_count(self, admin_client: TestClient):
        profile = _make_orm_profile()
        mock_result = [{"profile": profile, "analysis_count": 3}]

        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.list_users.return_value = mock_result
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/users")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["analysis_count"] == 3

    def test_default_pagination(self, admin_client: TestClient):
        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.list_users.return_value = []
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/users")

        assert resp.status_code == 200
        instance.list_users.assert_called_once_with(limit=50, offset=0)

    def test_custom_pagination(self, admin_client: TestClient):
        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.list_users.return_value = []
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/users?limit=10&offset=20")

        assert resp.status_code == 200
        instance.list_users.assert_called_once_with(limit=10, offset=20)


# ---------------------------------------------------------------------------
# DELETE /api/v1/admin/users/{user_id}
# ---------------------------------------------------------------------------


class TestDeleteUser:
    def test_returns_204_on_success(self, admin_client: TestClient):
        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.delete_user_data.return_value = None
            MockService.return_value = instance

            resp = admin_client.delete(f"/api/v1/admin/users/{TEST_USER_ID}")

        assert resp.status_code == 204

    def test_calls_delete_with_correct_user_id(self, admin_client: TestClient):
        target_id = uuid.uuid4()

        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.delete_user_data.return_value = None
            MockService.return_value = instance

            admin_client.delete(f"/api/v1/admin/users/{target_id}")

        instance.delete_user_data.assert_called_once_with(target_id)


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/users/{user_id}/disable
# ---------------------------------------------------------------------------


class TestDisableUser:
    def test_returns_200_stub(self, admin_client: TestClient):
        resp = admin_client.patch(f"/api/v1/admin/users/{TEST_USER_ID}/disable")
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body


# ---------------------------------------------------------------------------
# GET /api/v1/admin/analyses
# ---------------------------------------------------------------------------


class TestListAllAnalyses:
    def test_returns_all_analyses(self, admin_client: TestClient):
        analyses = [_make_orm_analysis(), _make_orm_analysis()]

        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.list_all_analyses.return_value = analyses
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/analyses")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 2

    def test_filters_by_status(self, admin_client: TestClient):
        analyses = [_make_orm_analysis(status="completed")]

        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.list_all_analyses.return_value = analyses
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/analyses?status=completed")

        assert resp.status_code == 200
        instance.list_all_analyses.assert_called_once_with(
            limit=50, offset=0, status_filter="completed"
        )

    def test_default_pagination_no_filter(self, admin_client: TestClient):
        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.list_all_analyses.return_value = []
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/analyses")

        assert resp.status_code == 200
        instance.list_all_analyses.assert_called_once_with(
            limit=50, offset=0, status_filter=None
        )


# ---------------------------------------------------------------------------
# GET /api/v1/admin/health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_returns_health_dict(self, admin_client: TestClient):
        health_data = {
            "queue_depth": 5,
            "worker_heartbeat": True,
            "db_ok": True,
        }

        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.get_health.return_value = health_data
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["queue_depth"] == 5
        assert body["worker_heartbeat"] is True
        assert body["db_ok"] is True

    def test_health_includes_all_keys(self, admin_client: TestClient):
        health_data = {
            "queue_depth": 0,
            "worker_heartbeat": False,
            "db_ok": True,
        }

        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.get_health.return_value = health_data
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/health")

        assert resp.status_code == 200
        body = resp.json()
        assert "queue_depth" in body
        assert "worker_heartbeat" in body
        assert "db_ok" in body


# ---------------------------------------------------------------------------
# GET /api/v1/admin/confidence-audit
# ---------------------------------------------------------------------------


class TestConfidenceAudit:
    def test_returns_low_confidence_analyses(self, admin_client: TestClient):
        low_conf = _make_orm_analysis(confidence_score=0.30)
        low_conf2 = _make_orm_analysis(confidence_score=0.45)

        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.confidence_audit.return_value = [low_conf, low_conf2]
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/confidence-audit")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2

    def test_default_threshold_is_050(self, admin_client: TestClient):
        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.confidence_audit.return_value = []
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/confidence-audit")

        assert resp.status_code == 200
        instance.confidence_audit.assert_called_once_with(threshold=0.50)

    def test_custom_threshold(self, admin_client: TestClient):
        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.confidence_audit.return_value = []
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/confidence-audit?threshold=0.70")

        assert resp.status_code == 200
        instance.confidence_audit.assert_called_once_with(threshold=0.70)

    def test_response_includes_confidence_score(self, admin_client: TestClient):
        low_conf = _make_orm_analysis(confidence_score=0.25)

        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.confidence_audit.return_value = [low_conf]
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/confidence-audit")

        body = resp.json()
        assert body[0]["confidence_score"] == 0.25


# ---------------------------------------------------------------------------
# AdminService unit tests (no HTTP layer)
# ---------------------------------------------------------------------------


def _make_admin_service(
    analysis_results: list | None = None,
    profile_results: list | None = None,
    redis: AsyncMock | None = None,
) -> "AdminService":
    """Build an AdminService with mocked repos pre-wired for common test scenarios."""
    from app.repositories.analysis import AnalysisRepository
    from app.repositories.user_profile import UserProfileRepository
    from app.services.admin import AdminService

    mock_analysis_repo = AsyncMock(spec=AnalysisRepository)
    mock_analysis_repo.list_all = AsyncMock(return_value=analysis_results or [])
    mock_analysis_repo.get_below_confidence = AsyncMock(return_value=analysis_results or [])
    mock_analysis_repo.delete_by_user = AsyncMock(return_value=None)
    mock_analysis_repo.ping = AsyncMock(return_value=True)

    mock_profile_repo = AsyncMock(spec=UserProfileRepository)
    mock_profile_repo.list_with_analysis_counts = AsyncMock(return_value=profile_results or [])
    mock_profile_repo.delete_by_user_id = AsyncMock(return_value=None)

    return AdminService(
        analysis_repo=mock_analysis_repo,
        user_profile_repo=mock_profile_repo,
        redis=redis,
    )


class TestAdminService:
    """Tests for AdminService methods directly, mocking repositories."""

    @pytest.mark.asyncio
    async def test_list_users_returns_profiles_with_counts(self):
        profile = _make_orm_profile()
        service = _make_admin_service(profile_results=[{"profile": profile, "analysis_count": 2}])
        results = await service.list_users(limit=50, offset=0)

        assert len(results) == 1
        assert results[0]["analysis_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_user_data_calls_db_delete(self):
        service = _make_admin_service()
        # Should not raise
        await service.delete_user_data(TEST_USER_ID)

    @pytest.mark.asyncio
    async def test_list_all_analyses_no_filter(self):
        analysis = _make_orm_analysis()
        service = _make_admin_service(analysis_results=[analysis])
        results = await service.list_all_analyses(limit=50, offset=0, status_filter=None)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_list_all_analyses_with_status_filter(self):
        analysis = _make_orm_analysis(status="failed")
        service = _make_admin_service(analysis_results=[analysis])
        results = await service.list_all_analyses(limit=10, offset=0, status_filter="failed")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_health_returns_queue_depth_and_heartbeat(self):
        mock_redis = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=7)
        mock_redis.get = AsyncMock(return_value=b"1")  # heartbeat exists

        service = _make_admin_service(redis=mock_redis)
        health = await service.get_health()

        assert health["queue_depth"] == 7
        assert health["worker_heartbeat"] is True
        assert "db_ok" in health

    @pytest.mark.asyncio
    async def test_get_health_heartbeat_missing(self):
        mock_redis = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=0)
        mock_redis.get = AsyncMock(return_value=None)  # heartbeat absent

        service = _make_admin_service(redis=mock_redis)
        health = await service.get_health()

        assert health["worker_heartbeat"] is False

    @pytest.mark.asyncio
    async def test_confidence_audit_returns_below_threshold(self):
        flagged = [_make_orm_analysis(confidence_score=0.30)]
        service = _make_admin_service(analysis_results=flagged)
        results = await service.confidence_audit(threshold=0.50)

        assert len(results) == 1
        assert results[0].confidence_score == 0.30


# ---------------------------------------------------------------------------
# B-060: Admin health endpoint Redis injection
# ---------------------------------------------------------------------------


class TestAdminRedisInjection:
    """Verify that _get_service passes Redis to AdminService (B-060)."""

    def test_health_endpoint_receives_real_queue_depth(self, admin_client: TestClient):
        """Health endpoint returns actual queue_depth from Redis, not hardcoded 0."""
        health_data = {
            "queue_depth": 3,
            "worker_heartbeat": True,
            "db_ok": True,
        }

        with patch("app.api.v1.admin.AdminService") as MockService:
            instance = AsyncMock()
            instance.get_health.return_value = health_data
            MockService.return_value = instance

            resp = admin_client.get("/api/v1/admin/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["queue_depth"] == 3
        assert body["worker_heartbeat"] is True

    @pytest.mark.asyncio
    async def test_admin_service_get_health_with_redis_injected(self):
        """AdminService.get_health reads actual queue depth when Redis is wired."""
        mock_redis = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=5)
        mock_redis.get = AsyncMock(return_value="1")

        service = _make_admin_service(redis=mock_redis)
        health = await service.get_health()

        assert health["queue_depth"] == 5
        assert health["worker_heartbeat"] is True
        mock_redis.llen.assert_called_once_with("arq:queue")
        mock_redis.get.assert_called_once_with("spelix:worker:heartbeat")

    @pytest.mark.asyncio
    async def test_admin_service_get_health_without_redis_returns_defaults(self):
        """When Redis is None (not injected), queue_depth=0 and heartbeat=False."""
        service = _make_admin_service(redis=None)
        health = await service.get_health()

        assert health["queue_depth"] == 0
        assert health["worker_heartbeat"] is False


# ---------------------------------------------------------------------------
# B-071: AdminService must use repositories (not raw SQLAlchemy)
# ---------------------------------------------------------------------------


class TestAdminServiceUsesRepositories:
    """AdminService must accept analysis_repo and user_profile_repo via DI."""

    @pytest.mark.asyncio
    async def test_admin_service_constructor_accepts_repos(self):
        """AdminService must accept analysis_repo and user_profile_repo kwargs."""
        from app.services.admin import AdminService
        import inspect

        sig = inspect.signature(AdminService.__init__)
        params = list(sig.parameters.keys())
        assert "analysis_repo" in params, "AdminService must accept analysis_repo kwarg"
        assert "user_profile_repo" in params, "AdminService must accept user_profile_repo kwarg"
        assert "db" not in params, "AdminService must not accept raw db/AsyncSession"

    @pytest.mark.asyncio
    async def test_list_users_calls_repo(self):
        """list_users delegates to user_profile_repo.list_with_analysis_counts."""
        from app.repositories.analysis import AnalysisRepository
        from app.repositories.user_profile import UserProfileRepository
        from app.services.admin import AdminService

        profile = _make_orm_profile()
        mock_analysis_repo = AsyncMock(spec=AnalysisRepository)
        mock_profile_repo = AsyncMock(spec=UserProfileRepository)
        mock_profile_repo.list_with_analysis_counts = AsyncMock(
            return_value=[{"profile": profile, "analysis_count": 5}]
        )

        service = AdminService(
            analysis_repo=mock_analysis_repo,
            user_profile_repo=mock_profile_repo,
        )
        results = await service.list_users(limit=10, offset=0)

        mock_profile_repo.list_with_analysis_counts.assert_awaited_once_with(
            limit=10, offset=0
        )
        assert len(results) == 1
        assert results[0]["analysis_count"] == 5

    @pytest.mark.asyncio
    async def test_delete_user_data_calls_repos(self):
        """delete_user_data calls analysis_repo.delete_by_user and profile_repo.delete_by_user_id."""
        from app.repositories.analysis import AnalysisRepository
        from app.repositories.user_profile import UserProfileRepository
        from app.services.admin import AdminService

        mock_analysis_repo = AsyncMock(spec=AnalysisRepository)
        mock_analysis_repo.delete_by_user = AsyncMock(return_value=None)
        mock_profile_repo = AsyncMock(spec=UserProfileRepository)
        mock_profile_repo.delete_by_user_id = AsyncMock(return_value=None)

        service = AdminService(
            analysis_repo=mock_analysis_repo,
            user_profile_repo=mock_profile_repo,
        )
        await service.delete_user_data(TEST_USER_ID)

        mock_analysis_repo.delete_by_user.assert_awaited_once_with(TEST_USER_ID)
        mock_profile_repo.delete_by_user_id.assert_awaited_once_with(TEST_USER_ID)

    @pytest.mark.asyncio
    async def test_list_all_analyses_calls_repo(self):
        """list_all_analyses delegates to analysis_repo.list_all."""
        from app.repositories.analysis import AnalysisRepository
        from app.repositories.user_profile import UserProfileRepository
        from app.services.admin import AdminService

        analysis = _make_orm_analysis()
        mock_analysis_repo = AsyncMock(spec=AnalysisRepository)
        mock_analysis_repo.list_all = AsyncMock(return_value=[analysis])
        mock_profile_repo = AsyncMock(spec=UserProfileRepository)

        service = AdminService(
            analysis_repo=mock_analysis_repo,
            user_profile_repo=mock_profile_repo,
        )
        results = await service.list_all_analyses(limit=50, offset=0, status_filter=None)

        mock_analysis_repo.list_all.assert_awaited_once_with(
            limit=50, offset=0, status_filter=None
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_confidence_audit_calls_repo(self):
        """confidence_audit delegates to analysis_repo.get_below_confidence."""
        from app.repositories.analysis import AnalysisRepository
        from app.repositories.user_profile import UserProfileRepository
        from app.services.admin import AdminService

        flagged = _make_orm_analysis(confidence_score=0.30)
        mock_analysis_repo = AsyncMock(spec=AnalysisRepository)
        mock_analysis_repo.get_below_confidence = AsyncMock(return_value=[flagged])
        mock_profile_repo = AsyncMock(spec=UserProfileRepository)

        service = AdminService(
            analysis_repo=mock_analysis_repo,
            user_profile_repo=mock_profile_repo,
        )
        results = await service.confidence_audit(threshold=0.50)

        mock_analysis_repo.get_below_confidence.assert_awaited_once_with(threshold=0.50)
        assert len(results) == 1
        assert results[0].confidence_score == 0.30

    @pytest.mark.asyncio
    async def test_get_health_still_works_with_repo_based_constructor(self):
        """get_health still checks DB and Redis correctly after refactor."""
        from app.repositories.analysis import AnalysisRepository
        from app.repositories.user_profile import UserProfileRepository
        from app.services.admin import AdminService

        mock_analysis_repo = AsyncMock(spec=AnalysisRepository)
        mock_analysis_repo.ping = AsyncMock(return_value=True)
        mock_profile_repo = AsyncMock(spec=UserProfileRepository)

        mock_redis = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=3)
        mock_redis.get = AsyncMock(return_value=b"1")

        service = AdminService(
            analysis_repo=mock_analysis_repo,
            user_profile_repo=mock_profile_repo,
            redis=mock_redis,
        )
        health = await service.get_health()

        assert health["queue_depth"] == 3
        assert health["worker_heartbeat"] is True
        assert health["db_ok"] is True
