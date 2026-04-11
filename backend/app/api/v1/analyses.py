"""FastAPI router for analyses endpoints.

Routes:
    POST /api/v1/analyses                — create analysis + get signed upload URL
    POST /api/v1/analyses/{id}/start     — enqueue ARQ job, transition to quality_gate_pending
    GET  /api/v1/analyses/{id}/status    — poll analysis status (fallback for Realtime)
    DELETE /api/v1/analyses/{id}         — delete analysis + Storage artifacts
    PATCH /api/v1/analyses/{id}          — update mutable fields (tags)
    GET  /api/v1/analyses/{id}           — full analysis detail with nested coaching + reps
    GET  /api/v1/analyses                — list analyses for current user

All routes require a valid Supabase JWT.
Rate limiting (10/user/day) is added in B-010.

Requirements: FR-UPLD-07, FR-UPLD-16, FR-UPLD-17, FR-RESL-13, FR-UPLD-10, FR-UPLD-11, FR-HIST-01
"""

import logging
import os
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db import get_db
from app.rate_limit import limiter
from app.repositories.analysis import AnalysisRepository
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisCreateResponse,
    AnalysisDetail,
    AnalysisStartResponse,
    AnalysisStatusResponse,
    AnalysisSummary,
    AnalysisUpdate,
)
from app.services.analysis import AnalysisService
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analyses"])


# ---------------------------------------------------------------------------
# Dependency factories
# ---------------------------------------------------------------------------

# Module-level cache for the async Supabase client. ``acreate_client``
# performs a (synchronous-looking but async-defined) HTTPS handshake; we want
# to do that exactly once per process, not on every request. The two-state
# cache (initialised flag + value) lets us cache ``None`` so that a startup
# misconfiguration doesn't make us retry the failing constructor on every
# request.
_async_supabase_client_cache: Any | None = None
_async_supabase_client_cache_initialized: bool = False


async def _make_storage_service() -> StorageService:
    """Build a StorageService backed by a real *async* Supabase client.

    Reads ``SUPABASE_URL`` and ``SUPABASE_SERVICE_ROLE_KEY`` from the
    environment and constructs the client via ``supabase.acreate_client``
    (the async variant — the sync ``create_client`` returns a
    ``supabase._sync.client.Client`` whose storage methods are NOT
    awaitable, which is the bug that took down POST /analyses for the
    entire existence of Phase 0 + Phase 1).

    The constructed client is cached at module level so that subsequent
    requests reuse the same HTTPS connection pool. If env vars are missing
    or ``acreate_client`` raises, the cache stores ``None`` and the returned
    ``StorageService`` will raise ``RuntimeError`` at call time with an
    actionable message.

    Regression coverage:
    ``tests/unit/test_storage_service.py::TestMakeStorageServiceFactory``.
    """
    global _async_supabase_client_cache, _async_supabase_client_cache_initialized

    if not _async_supabase_client_cache_initialized:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

        if not supabase_url or not supabase_key:
            _async_supabase_client_cache = None
        else:
            try:
                from supabase import acreate_client

                _async_supabase_client_cache = await acreate_client(
                    supabase_url, supabase_key
                )
            except Exception as e:
                logger.warning("Failed to create async Supabase client: %s", e)
                _async_supabase_client_cache = None

        _async_supabase_client_cache_initialized = True

    return StorageService(supabase_client=_async_supabase_client_cache)


async def _get_service(db: AsyncSession = Depends(get_db)) -> AnalysisService:
    """Build AnalysisService with an AnalysisRepository and StorageService."""
    repo = AnalysisRepository(db)
    storage = await _make_storage_service()
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


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=list[AnalysisSummary],
    summary="List analyses for current user",
)
async def list_analyses(
    user: CurrentUser = Depends(get_current_user),
    service: AnalysisService = Depends(_get_service),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AnalysisSummary]:
    """Return analyses for the authenticated user in reverse chronological order.

    Supports pagination via ``limit`` and ``offset`` query parameters.
    """
    analyses = await service.list_analyses(
        user_id=user["id"],
        limit=limit,
        offset=offset,
    )
    return [AnalysisSummary.model_validate(a) for a in analyses]


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


@router.get(
    "/{analysis_id}/status",
    status_code=status.HTTP_200_OK,
    response_model=AnalysisStatusResponse,
    summary="Poll analysis status",
)
async def get_analysis_status(
    analysis_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AnalysisService = Depends(_get_service),
) -> AnalysisStatusResponse:
    """Return the current status of an analysis.

    Used as a polling fallback when the Supabase Realtime subscription disconnects.
    Returns only ``id``, ``status``, and ``updated_at``.

    Requirements: FR-RESL-13
    """
    analysis = await service.get_analysis_status(
        analysis_id=analysis_id,
        user_id=user["id"],
    )
    return AnalysisStatusResponse.model_validate(analysis)


@router.get(
    "/{analysis_id}",
    status_code=status.HTTP_200_OK,
    response_model=AnalysisDetail,
    summary="Get full analysis detail",
)
async def get_analysis_detail(
    analysis_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AnalysisService = Depends(_get_service),
) -> AnalysisDetail:
    """Return full analysis detail including nested coaching result and rep metrics."""
    analysis = await service.get_analysis_detail(
        analysis_id=analysis_id,
        user_id=user["id"],
    )
    return AnalysisDetail.model_validate(analysis)


@router.patch(
    "/{analysis_id}",
    status_code=status.HTTP_200_OK,
    response_model=AnalysisSummary,
    summary="Update analysis metadata",
)
async def update_analysis(
    analysis_id: UUID,
    body: AnalysisUpdate,
    user: CurrentUser = Depends(get_current_user),
    service: AnalysisService = Depends(_get_service),
) -> AnalysisSummary:
    """Update mutable fields on an analysis (currently: tags).

    Requirements: FR-UPLD-10
    """
    analysis = await service.update_analysis(
        analysis_id=analysis_id,
        user_id=user["id"],
        tags=body.tags,
    )
    return AnalysisSummary.model_validate(analysis)


@router.delete(
    "/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete analysis and all artifacts",
)
async def delete_analysis(
    analysis_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AnalysisService = Depends(_get_service),
) -> None:
    """Delete an analysis record, cascaded rep_metrics and coaching_results, and Storage artifacts.

    Requirements: FR-UPLD-10, FR-UPLD-11
    """
    await service.delete_analysis(
        analysis_id=analysis_id,
        user_id=user["id"],
    )
