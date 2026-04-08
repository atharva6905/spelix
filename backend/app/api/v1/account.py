"""FastAPI router for account management.

Routes:
    DELETE /api/v1/account — delete all user data (cascade)

Requirements: FR-AUTH-07, FR-XPRT-05, NFR-SECU-08
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db import get_db
from app.repositories.analysis import AnalysisRepository
from app.repositories.user_profile import UserProfileRepository
from app.services.account import AccountService
from app.services.storage import StorageService

router = APIRouter(tags=["account"])


def _get_service(db: AsyncSession = Depends(get_db)) -> AccountService:
    return AccountService(
        repo=AnalysisRepository(db),
        profile_repo=UserProfileRepository(db),
        storage=StorageService(),
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user: CurrentUser = Depends(get_current_user),
    service: AccountService = Depends(_get_service),
) -> None:
    """Delete all data for the authenticated user."""
    await service.delete_account(user["id"])
