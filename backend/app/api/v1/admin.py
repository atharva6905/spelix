"""FastAPI router for admin endpoints.

All routes require admin auth via get_admin_user dependency.
Requirements: FR-ADMN-01 through FR-ADMN-05
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_admin_user, get_redis
from app.db import get_db
from app.repositories.analysis import AnalysisRepository
from app.repositories.user_profile import UserProfileRepository
from app.services.admin import AdminService

router = APIRouter(tags=["admin"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AdminUserResponse(BaseModel):
    user_id: UUID
    height_cm: float | None
    weight_kg: float | None
    age: int | None
    experience_level: str | None
    analysis_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminAnalysisResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: str
    exercise_type: str
    exercise_variant: str
    confidence_score: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    queue_depth: int
    worker_heartbeat: bool
    db_ok: bool


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


async def _get_service(
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> AdminService:
    return AdminService(
        analysis_repo=AnalysisRepository(db),
        user_profile_repo=UserProfileRepository(db),
        redis=redis,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_admin_user),
    service: AdminService = Depends(_get_service),
) -> list[dict[str, Any]]:
    rows = await service.list_users(limit=limit, offset=offset)
    results = []
    for row in rows:
        profile = row["profile"]
        results.append({
            "user_id": profile.user_id,
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
            "age": profile.age,
            "experience_level": profile.experience_level,
            "analysis_count": row["analysis_count"],
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        })
    return results


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    user_id: UUID,
    user: CurrentUser = Depends(get_admin_user),
    service: AdminService = Depends(_get_service),
) -> None:
    await service.delete_user_data(user_id)


@router.patch("/users/{user_id}/disable")
async def disable_user(
    user_id: UUID,
    user: CurrentUser = Depends(get_admin_user),
) -> dict[str, str]:
    # Phase 0 stub — actual disable is via Supabase Admin API
    return {"message": f"User {user_id} disable is a Phase 1 feature (Supabase Admin API)."}


@router.get("/analyses", response_model=list[AdminAnalysisResponse])
async def list_all_analyses(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    user: CurrentUser = Depends(get_admin_user),
    service: AdminService = Depends(_get_service),
) -> list[Any]:
    return await service.list_all_analyses(
        limit=limit, offset=offset, status_filter=status_filter
    )


@router.get("/health", response_model=HealthResponse)
async def health(
    user: CurrentUser = Depends(get_admin_user),
    service: AdminService = Depends(_get_service),
) -> dict[str, Any]:
    return await service.get_health()


@router.get("/confidence-audit", response_model=list[AdminAnalysisResponse])
async def confidence_audit(
    threshold: float = Query(0.50, ge=0.0, le=1.0),
    user: CurrentUser = Depends(get_admin_user),
    service: AdminService = Depends(_get_service),
) -> list[Any]:
    return await service.confidence_audit(threshold=threshold)
