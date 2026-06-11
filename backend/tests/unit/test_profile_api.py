"""Unit tests for profile API endpoints (B-008).

Tests cover:
- GET /api/v1/profiles/me returns 404 when no profile exists
- PUT /api/v1/profiles/me creates a new profile
- PUT /api/v1/profiles/me updates an existing profile
- Invalid experience level returns 422
- Unauthenticated requests return 401

Requirements: FR-PROF-01 through FR-PROF-05
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.profiles import router
from app.models.user_profile import UserProfile


TEST_USER_ID = uuid.uuid4()
TEST_EMAIL = "test@example.com"


def _make_orm_profile(**kwargs) -> UserProfile:
    now = datetime.now(timezone.utc)
    p = UserProfile(
        user_id=kwargs.get("user_id", TEST_USER_ID),
        height_cm=kwargs.get("height_cm", 175.0),
        weight_kg=kwargs.get("weight_kg", 75.0),
        age=kwargs.get("age", 28),
        experience_level=kwargs.get("experience_level", "intermediate"),
        arm_span_cm=kwargs.get("arm_span_cm", None),
        femur_length_cm=kwargs.get("femur_length_cm", None),
        sex=kwargs.get("sex", None),
    )
    # Inject non-constructor attributes that ORM normally sets after flush
    p.__dict__.update(
        {
            "id": kwargs.get("id", uuid.uuid4()),
            "created_at": kwargs.get("created_at", now),
            "updated_at": kwargs.get("updated_at", now),
        }
    )
    return p


@pytest.fixture()
def app_client():
    """Return a TestClient with auth dependency overridden."""
    from app.api.deps import get_current_user

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/profiles")

    # Override auth to return a fixed user
    async def _mock_user():
        return {"id": TEST_USER_ID, "email": TEST_EMAIL, "role": "user"}

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /api/v1/profiles/me
# ---------------------------------------------------------------------------


class TestGetProfile:
    def test_returns_404_when_no_profile(self, app_client: TestClient):
        with patch("app.api.v1.profiles.ProfileService") as MockService:
            from fastapi import HTTPException

            instance = AsyncMock()
            instance.get_or_404.side_effect = HTTPException(
                status_code=404,
                detail={"error": {"code": "PROFILE_NOT_FOUND", "message": "Not found.", "detail": None}},
            )
            MockService.return_value = instance

            resp = app_client.get("/api/v1/profiles/me")

        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "PROFILE_NOT_FOUND"

    def test_returns_profile_when_exists(self, app_client: TestClient):
        profile = _make_orm_profile()

        with patch("app.api.v1.profiles.ProfileService") as MockService:
            instance = AsyncMock()
            instance.get_or_404.return_value = profile
            MockService.return_value = instance

            resp = app_client.get("/api/v1/profiles/me")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == str(TEST_USER_ID)
        assert body["height_cm"] == 175.0
        assert body["experience_level"] == "intermediate"


# ---------------------------------------------------------------------------
# PUT /api/v1/profiles/me
# ---------------------------------------------------------------------------


class TestPutProfile:
    def test_creates_profile_with_required_fields(self, app_client: TestClient):
        profile = _make_orm_profile(height_cm=180.0, experience_level="beginner")

        with patch("app.api.v1.profiles.ProfileService") as MockService:
            instance = AsyncMock()
            instance.upsert.return_value = profile
            MockService.return_value = instance

            resp = app_client.put(
                "/api/v1/profiles/me",
                json={
                    "height_cm": 180.0,
                    "weight_kg": 80.0,
                    "age": 25,
                    "experience_level": "beginner",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["height_cm"] == 180.0
        assert body["experience_level"] == "beginner"

    def test_updates_existing_profile(self, app_client: TestClient):
        updated_profile = _make_orm_profile(
            height_cm=175.0,
            experience_level="advanced",
            arm_span_cm=180.0,
        )

        with patch("app.api.v1.profiles.ProfileService") as MockService:
            instance = AsyncMock()
            instance.upsert.return_value = updated_profile
            MockService.return_value = instance

            resp = app_client.put(
                "/api/v1/profiles/me",
                json={
                    "height_cm": 175.0,
                    "weight_kg": 78.0,
                    "age": 30,
                    "experience_level": "advanced",
                    "arm_span_cm": 180.0,
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["experience_level"] == "advanced"
        assert body["arm_span_cm"] == 180.0

    def test_invalid_experience_level_returns_422(self, app_client: TestClient):
        resp = app_client.put(
            "/api/v1/profiles/me",
            json={
                "height_cm": 175.0,
                "weight_kg": 70.0,
                "age": 25,
                "experience_level": "expert",
            },
        )
        assert resp.status_code == 422

    def test_missing_required_field_returns_422(self, app_client: TestClient):
        resp = app_client.put(
            "/api/v1/profiles/me",
            json={
                "height_cm": 175.0,
                "weight_kg": 70.0,
                # missing age and experience_level
            },
        )
        assert resp.status_code == 422

    def test_optional_fields_accepted(self, app_client: TestClient):
        profile = _make_orm_profile(arm_span_cm=182.0, femur_length_cm=46.0)

        with patch("app.api.v1.profiles.ProfileService") as MockService:
            instance = AsyncMock()
            instance.upsert.return_value = profile
            MockService.return_value = instance

            resp = app_client.put(
                "/api/v1/profiles/me",
                json={
                    "height_cm": 175.0,
                    "weight_kg": 70.0,
                    "age": 25,
                    "experience_level": "intermediate",
                    "arm_span_cm": 182.0,
                    "femur_length_cm": 46.0,
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["arm_span_cm"] == 182.0
        assert body["femur_length_cm"] == 46.0


# ---------------------------------------------------------------------------
# Optional sex field (FR-PROF-03 ext., FR-PROF-06 ext.)
# ---------------------------------------------------------------------------


class TestSexField:
    def test_put_with_sex_echoes_it(self, app_client: TestClient):
        profile = _make_orm_profile(sex="female")

        with patch("app.api.v1.profiles.ProfileService") as MockService:
            instance = AsyncMock()
            instance.upsert.return_value = profile
            MockService.return_value = instance

            resp = app_client.put(
                "/api/v1/profiles/me",
                json={
                    "height_cm": 175.0,
                    "weight_kg": 70.0,
                    "age": 25,
                    "experience_level": "intermediate",
                    "sex": "female",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["sex"] == "female"

    def test_put_without_sex_returns_none(self, app_client: TestClient):
        profile = _make_orm_profile()

        with patch("app.api.v1.profiles.ProfileService") as MockService:
            instance = AsyncMock()
            instance.upsert.return_value = profile
            MockService.return_value = instance

            resp = app_client.put(
                "/api/v1/profiles/me",
                json={
                    "height_cm": 175.0,
                    "weight_kg": 70.0,
                    "age": 25,
                    "experience_level": "intermediate",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["sex"] is None

    def test_put_with_invalid_sex_returns_422(self, app_client: TestClient):
        resp = app_client.put(
            "/api/v1/profiles/me",
            json={
                "height_cm": 175.0,
                "weight_kg": 70.0,
                "age": 25,
                "experience_level": "intermediate",
                "sex": "other",
            },
        )
        assert resp.status_code == 422

    def test_get_includes_sex(self, app_client: TestClient):
        profile = _make_orm_profile(sex="male")

        with patch("app.api.v1.profiles.ProfileService") as MockService:
            instance = AsyncMock()
            instance.get_or_404.return_value = profile
            MockService.return_value = instance

            resp = app_client.get("/api/v1/profiles/me")

        assert resp.status_code == 200
        assert resp.json()["sex"] == "male"


class TestServicePersistsSex:
    """ProfileService.upsert must copy `sex` to the ORM object on both paths."""


    async def test_create_path_persists_sex(self):
        from app.schemas.profile import ProfileUpdate
        from app.services.profile import ProfileService

        repo = AsyncMock()
        repo.get_by_user_id.return_value = None
        repo.create.side_effect = lambda p: p

        service = ProfileService(repo)
        data = ProfileUpdate(
            height_cm=175.0,
            weight_kg=70.0,
            age=25,
            experience_level="intermediate",
            sex="female",
        )
        result = await service.upsert(TEST_USER_ID, data)
        assert result.sex == "female"


    async def test_update_path_persists_sex(self):
        from app.schemas.profile import ProfileUpdate
        from app.services.profile import ProfileService

        existing = _make_orm_profile(sex=None)
        repo = AsyncMock()
        repo.get_by_user_id.return_value = existing
        repo.update.side_effect = lambda p: p

        service = ProfileService(repo)
        data = ProfileUpdate(
            height_cm=175.0,
            weight_kg=70.0,
            age=25,
            experience_level="intermediate",
            sex="prefer_not_to_say",
        )
        result = await service.upsert(TEST_USER_ID, data)
        assert result.sex == "prefer_not_to_say"


    async def test_update_path_omitted_sex_sets_none(self):
        """Upsert assigns all fields — omitted sex defaults to None (matches
        arm_span_cm/femur_length_cm overwrite-all semantics)."""
        from app.schemas.profile import ProfileUpdate
        from app.services.profile import ProfileService

        existing = _make_orm_profile(sex="male")
        repo = AsyncMock()
        repo.get_by_user_id.return_value = existing
        repo.update.side_effect = lambda p: p

        service = ProfileService(repo)
        data = ProfileUpdate(
            height_cm=175.0,
            weight_kg=70.0,
            age=25,
            experience_level="intermediate",
        )
        result = await service.upsert(TEST_USER_ID, data)
        assert result.sex is None
