"""FastAPI router for user profile endpoints.

Routes:
    GET  /api/v1/profiles/me  — get current user's profile (FR-PROF-05)
    PUT  /api/v1/profiles/me  — create or update current user's profile (FR-PROF-01..05)

All routes require a valid Supabase JWT.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db import get_db
from app.repositories.user_profile import UserProfileRepository
from app.schemas.profile import ProfileResponse, ProfileUpdate
from app.services.profile import ProfileService

router = APIRouter(tags=["profiles"])


def _get_service(db: AsyncSession = Depends(get_db)) -> ProfileService:
    repo = UserProfileRepository(db)
    return ProfileService(repo)


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    user: CurrentUser = Depends(get_current_user),
    service: ProfileService = Depends(_get_service),
) -> ProfileResponse:
    """Return the authenticated user's profile.

    Raises 404 if the user has not completed onboarding yet.
    """
    profile = await service.get_or_404(user["id"])
    return ProfileResponse.model_validate(profile)


@router.put("/me", response_model=ProfileResponse)
async def upsert_my_profile(
    body: ProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
    service: ProfileService = Depends(_get_service),
) -> ProfileResponse:
    """Create or update the authenticated user's profile.

    Creates a new profile on first call; updates all fields on subsequent calls.
    """
    profile = await service.upsert(user["id"], body)
    return ProfileResponse.model_validate(profile)
