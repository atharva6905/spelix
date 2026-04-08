"""FastAPI router for history insights endpoints (B-031).

Routes:
    GET /api/v1/insights/exercise/{type}/{variant} — per-exercise insights
    GET /api/v1/insights/global                    — global insights

All routes require a valid Supabase JWT.

Requirements: FR-HIST-02, FR-HIST-03
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db import get_db
from app.services.insights import InsightsService

router = APIRouter(tags=["insights"])


@router.get("/exercise/{exercise_type}/{exercise_variant}")
async def get_exercise_insights(
    exercise_type: str,
    exercise_variant: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return per-exercise insights for the current user."""
    svc = InsightsService(db)
    return await svc.exercise_insights(user["id"], exercise_type, exercise_variant)


@router.get("/global")
async def get_global_insights(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return global insights across all exercises for the current user."""
    svc = InsightsService(db)
    return await svc.global_insights(user["id"])
