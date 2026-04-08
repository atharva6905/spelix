"""Profile service — business logic for user profile operations.

Requirements: FR-PROF-01 through FR-PROF-05
"""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.user_profile import UserProfile
from app.repositories.user_profile import UserProfileRepository
from app.schemas.profile import ProfileUpdate


class ProfileService:
    def __init__(self, repo: UserProfileRepository) -> None:
        self._repo = repo

    async def get_or_404(self, user_id: UUID) -> UserProfile:
        """Return the profile for the given user, or raise 404."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "PROFILE_NOT_FOUND",
                        "message": "Profile not found. Please complete onboarding first.",
                        "detail": None,
                    }
                },
            )
        return profile

    async def upsert(self, user_id: UUID, data: ProfileUpdate) -> UserProfile:
        """Create or update the user's profile (upsert).

        If no profile exists for user_id, a new row is created.
        If a profile already exists, all supplied fields are updated.
        """
        existing = await self._repo.get_by_user_id(user_id)

        if existing is None:
            profile = UserProfile(
                user_id=user_id,
                height_cm=data.height_cm,
                weight_kg=data.weight_kg,
                age=data.age,
                experience_level=data.experience_level,
                arm_span_cm=data.arm_span_cm,
                femur_length_cm=data.femur_length_cm,
            )
            return await self._repo.create(profile)

        # Update all fields on the existing record
        existing.height_cm = data.height_cm
        existing.weight_kg = data.weight_kg
        existing.age = data.age
        existing.experience_level = data.experience_level
        existing.arm_span_cm = data.arm_span_cm
        existing.femur_length_cm = data.femur_length_cm
        return await self._repo.update(existing)
