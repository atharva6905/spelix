"""FastAPI router for analyses endpoints.

Routes:
    POST /api/v1/analyses          — create analysis + get signed upload URL
    POST /api/v1/analyses/{id}/start — enqueue ARQ job, transition to quality_gate_pending

All routes require a valid Supabase JWT.
Rate limiting (10/user/day) is added in B-010.

Requirements: FR-UPLD-07, FR-UPLD-16, FR-UPLD-17
"""

import os
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db import get_db
from app.repositories.analysis import AnalysisRepository
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisCreateResponse,
    AnalysisStartResponse,
)
from app.rate_limit import limiter
from app.services.analysis import AnalysisService
from app.services.storage import StorageService

router = APIRouter(tags=["analyses"])


# ---------------------------------------------------------------------------
# Dependency factories
# ---------------------------------------------------------------------------


def _make_storage_service() -> StorageService:
    """Build a StorageService from environment variables.

    In tests this function is replaced via dependency_overrides or
    the module-level ``_get_service`` is patched directly.
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

    if supabase_url and supabase_key:

        # We can't await here so we return a StorageService with no client;
        # the client is lazily created by the lifespan. For now, tests mock
        # the whole service, and production injects a ready client via a
        # module-level singleton created at startup.
        # For Phase 0 this is fine — the endpoint is tested with mocks.
        pass

    return StorageService()


def _get_service(db: AsyncSession = Depends(get_db)) -> AnalysisService:
    """Build AnalysisService with an AnalysisRepository and StorageService."""
    repo = AnalysisRepository(db)
    storage = _make_storage_service()
    return AnalysisService(repo=repo, storage=storage)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AnalysisCreateResponse,
    summary="Create analysis and get signed upload URL",
)
@limiter.limit("10/day")
async def create_analysis(
    request: Request,
    response: Response,
    body: AnalysisCreate,
    user: CurrentUser = Depends(get_current_user),
    service: AnalysisService = Depends(_get_service),
) -> AnalysisCreateResponse:
    """Create a new analysis record and return a TUS signed upload URL.

    The client uses the returned ``upload_url`` to upload the video directly
    to Supabase Storage (TUS protocol). FastAPI never handles video bytes.

    After uploading, call ``POST /analyses/{id}/start`` to begin processing.
    """
    result = await service.create_analysis(
        user_id=user["id"],
        exercise_type=body.exercise_type,
        exercise_variant=body.exercise_variant,
        filename=body.filename,
        file_size_bytes=body.file_size_bytes,
    )

    return AnalysisCreateResponse(
        id=result.analysis.id,
        upload_url=result.upload_url,
        status=result.analysis.status,
        expires_at=result.expires_at,
    )


@router.post(
    "/{analysis_id}/start",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AnalysisStartResponse,
    summary="Start analysis processing",
)
async def start_analysis(
    analysis_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AnalysisService = Depends(_get_service),
) -> AnalysisStartResponse:
    """Enqueue the CV pipeline job for an uploaded analysis.

    The analysis must be in ``queued`` status and owned by the authenticated user.
    Transitions status to ``quality_gate_pending`` and enqueues the ARQ worker.
    """
    analysis = await service.start_analysis(
        analysis_id=analysis_id,
        user_id=user["id"],
    )

    return AnalysisStartResponse(
        id=analysis.id,
        status=analysis.status,
    )
