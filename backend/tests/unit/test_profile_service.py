"""Unit tests for profile service (B-008).

Tests cover:
- get_or_404 returns profile when exists
- get_or_404 raises 404 when no profile
- upsert creates new profile when none exists
- upsert updates existing profile
- experience level validation rejects invalid values
- positive number validation for height, weight, age

Requirements: FR-PROF-01 through FR-PROF-05
"""

import uuid
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.models.user_profile import UserProfile
from app.schemas.profile import ProfileUpdate
from app.services.profile import ProfileService


def _make_profile(user_id: UUID | None = None, **kwargs) -> UserProfile:
    """Build a minimal UserProfile ORM object for tests."""
    uid = user_id or uuid.uuid4()
    return UserProfile(
        id=uuid.uuid4(),
        user_id=uid,
        height_cm=kwargs.get("height_cm", 175.0),
        weight_kg=kwargs.get("weight_kg", 75.0),
        age=kwargs.get("age", 28),
        experience_level=kwargs.get("experience_level", "intermediate"),
        arm_span_cm=kwargs.get("arm_span_cm", None),
        femur_length_cm=kwargs.get("femur_length_cm", None),
    )


class TestProfileServiceGetOrNotFound:
    """Tests for get_or_404 method."""

    async def test_returns_profile_when_exists(self):
        user_id = uuid.uuid4()
        profile = _make_profile(user_id=user_id)

        repo = AsyncMock()
        repo.get_by_user_id.return_value = profile

        service = ProfileService(repo)
        result = await service.get_or_404(user_id)

        assert result is profile
        repo.get_by_user_id.assert_awaited_once_with(user_id)

    async def test_raises_404_when_no_profile(self):
        user_id = uuid.uuid4()

        repo = AsyncMock()
        repo.get_by_user_id.return_value = None

        service = ProfileService(repo)
        with pytest.raises(HTTPException) as exc_info:
            await service.get_or_404(user_id)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"]["code"] == "PROFILE_NOT_FOUND"


class TestProfileServiceUpsert:
    """Tests for upsert method (create or update)."""

    async def test_creates_new_profile_when_none_exists(self):
        user_id = uuid.uuid4()
        data = ProfileUpdate(
            height_cm=180.0,
            weight_kg=82.0,
            age=30,
            experience_level="beginner",
        )

        created_profile = _make_profile(
            user_id=user_id,
            height_cm=180.0,
            weight_kg=82.0,
            age=30,
            experience_level="beginner",
        )

        repo = AsyncMock()
        repo.get_by_user_id.return_value = None
        repo.create.return_value = created_profile

        service = ProfileService(repo)
        result = await service.upsert(user_id, data)

        repo.create.assert_awaited_once()
        created_arg = repo.create.call_args[0][0]
        assert created_arg.user_id == user_id
        assert created_arg.height_cm == 180.0
        assert created_arg.experience_level == "beginner"
        assert result is created_profile

    async def test_updates_existing_profile(self):
        user_id = uuid.uuid4()
        existing = _make_profile(user_id=user_id, height_cm=170.0, experience_level="beginner")

        data = ProfileUpdate(
            height_cm=175.0,
            weight_kg=80.0,
            age=25,
            experience_level="intermediate",
            arm_span_cm=182.0,
        )

        repo = AsyncMock()
        repo.get_by_user_id.return_value = existing
        repo.update.return_value = existing  # mutated in-place

        service = ProfileService(repo)
        result = await service.upsert(user_id, data)

        repo.update.assert_awaited_once_with(existing)
        assert existing.height_cm == 175.0
        assert existing.experience_level == "intermediate"
        assert existing.arm_span_cm == 182.0
        assert result is existing

    async def test_optional_fields_are_none_when_not_provided(self):
        user_id = uuid.uuid4()
        data = ProfileUpdate(
            height_cm=170.0,
            weight_kg=65.0,
            age=22,
            experience_level="beginner",
        )

        repo = AsyncMock()
        repo.get_by_user_id.return_value = None
        repo.create.return_value = _make_profile(user_id=user_id)

        service = ProfileService(repo)
        await service.upsert(user_id, data)

        created_arg = repo.create.call_args[0][0]
        assert created_arg.arm_span_cm is None
        assert created_arg.femur_length_cm is None


class TestProfileUpdateSchema:
    """Tests for Pydantic v2 input validation on ProfileUpdate."""

    def test_valid_experience_levels_accepted(self):
        for level in ("beginner", "intermediate", "advanced"):
            schema = ProfileUpdate(
                height_cm=170.0,
                weight_kg=70.0,
                age=25,
                experience_level=level,
            )
            assert schema.experience_level == level

    def test_invalid_experience_level_raises_validation_error(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProfileUpdate(
                height_cm=170.0,
                weight_kg=70.0,
                age=25,
                experience_level="expert",
            )

    def test_zero_height_raises_validation_error(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProfileUpdate(
                height_cm=0,
                weight_kg=70.0,
                age=25,
                experience_level="beginner",
            )

    def test_negative_weight_raises_validation_error(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProfileUpdate(
                height_cm=170.0,
                weight_kg=-5.0,
                age=25,
                experience_level="beginner",
            )

    def test_zero_age_raises_validation_error(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProfileUpdate(
                height_cm=170.0,
                weight_kg=70.0,
                age=0,
                experience_level="beginner",
            )

    def test_optional_fields_default_to_none(self):
        schema = ProfileUpdate(
            height_cm=170.0,
            weight_kg=70.0,
            age=25,
            experience_level="advanced",
        )
        assert schema.arm_span_cm is None
        assert schema.femur_length_cm is None

    def test_optional_fields_accepted_when_provided(self):
        schema = ProfileUpdate(
            height_cm=170.0,
            weight_kg=70.0,
            age=25,
            experience_level="intermediate",
            arm_span_cm=175.0,
            femur_length_cm=45.0,
        )
        assert schema.arm_span_cm == 175.0
        assert schema.femur_length_cm == 45.0
