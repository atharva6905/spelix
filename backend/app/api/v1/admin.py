"""FastAPI router for admin endpoints.

All routes require admin auth via get_admin_user dependency.
Requirements: FR-ADMN-01 through FR-ADMN-05, FR-ADMN-06/07/10
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_admin_user, get_redis
from app.db import get_db
from app.models.coach_brain_entry import CoachBrainEntry as CoachBrainEntryModel
from app.repositories.analysis import AnalysisRepository
from app.repositories.analysis_expert_review import AnalysisExpertReviewRepository
from app.repositories.coach_brain import CoachBrainRepository
from app.repositories.rag_document import RagDocumentRepository
from app.repositories.user_profile import UserProfileRepository
from app.schemas.coach_brain import (
    CoachBrainEntry as CoachBrainEntrySchema,
    CoachBrainEntryCreate,
    CoachBrainEntryUpdate,
)
from app.schemas.expert_review import AdminExpertQueueItem, AdminExpertQueueStats
from app.schemas.rag_document import RagDocumentResponse, ReEmbedResponse
from app.services.admin import AdminService

# Keep references alive so ruff doesn't strip them (used in response_model)
_USED = (
    AnalysisExpertReviewRepository,
    CoachBrainRepository,
    CoachBrainEntryModel,
    CoachBrainEntrySchema,
    CoachBrainEntryCreate,
    CoachBrainEntryUpdate,
    AdminExpertQueueItem,
    AdminExpertQueueStats,
    RagDocumentRepository,
    RagDocumentResponse,
    ReEmbedResponse,
)

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _brain_entry_to_schema(entry: CoachBrainEntryModel) -> CoachBrainEntrySchema:
    """Convert ORM CoachBrainEntry to Pydantic schema.

    The ORM model uses 'extra_metadata' to avoid collision with SQLAlchemy's
    MetaData descriptor, but the Pydantic schema field is 'metadata'.
    """
    return CoachBrainEntrySchema(
        id=entry.id,
        content=entry.content,
        exercise=entry.exercise,
        phase=entry.phase,
        entry_type=entry.entry_type,
        status=entry.status,
        confirmation_count=entry.confirmation_count,
        source_analysis_ids=entry.source_analysis_ids,
        trigger_tags=entry.trigger_tags,
        confidence_score=float(entry.confidence_score) if entry.confidence_score is not None else None,
        metadata=entry.extra_metadata,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


# ---------------------------------------------------------------------------
# RAG Corpus Management (P2-035, FR-ADMN-06, FR-RAGK-08, FR-RAGK-09)
# ---------------------------------------------------------------------------


async def _get_rag_repo(db: AsyncSession = Depends(get_db)) -> RagDocumentRepository:
    return RagDocumentRepository(db)


async def _get_brain_repo(db: AsyncSession = Depends(get_db)) -> CoachBrainRepository:
    return CoachBrainRepository(db)


async def _get_review_repo(
    db: AsyncSession = Depends(get_db),
) -> AnalysisExpertReviewRepository:
    return AnalysisExpertReviewRepository(db)


@router.get("/rag/documents", response_model=list[RagDocumentResponse])
async def list_rag_documents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    review_status: str | None = Query(None),
    exercise_tag: str | None = Query(None),
    quality_tier: str | None = Query(None),
    user: CurrentUser = Depends(get_admin_user),
    repo: RagDocumentRepository = Depends(_get_rag_repo),
) -> list[Any]:
    docs = await repo.list_all(
        limit=limit,
        offset=offset,
        review_status=review_status,
        exercise_tag=exercise_tag,
        quality_tier=quality_tier,
    )
    return [RagDocumentResponse.model_validate(d, from_attributes=True) for d in docs]


@router.delete(
    "/rag/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_rag_document(
    doc_id: UUID,
    user: CurrentUser = Depends(get_admin_user),
    repo: RagDocumentRepository = Depends(_get_rag_repo),
) -> None:

    doc = await repo.get_by_id(doc_id)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Document not found.", "detail": None}},
        )
    await repo.delete(doc_id)


@router.post("/rag/documents/{doc_id}/re-embed", response_model=ReEmbedResponse)
async def re_embed_rag_document(
    doc_id: UUID,
    user: CurrentUser = Depends(get_admin_user),
    repo: RagDocumentRepository = Depends(_get_rag_repo),
) -> dict[str, Any]:

    doc = await repo.get_by_id(doc_id)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Document not found.", "detail": None}},
        )
    if doc.review_status != "reviewed_approved":
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Only reviewed_approved documents can be re-embedded.",
                    "detail": None,
                }
            },
        )
    # Re-embed is a placeholder — full ARQ integration deferred until storage_path is populated
    return {"message": "Re-embed queued.", "document_id": doc_id}


# ---------------------------------------------------------------------------
# Expert Reviewer Queue (P2-036, FR-ADMN-07)
# ---------------------------------------------------------------------------


@router.get("/expert-queue", response_model=list[AdminExpertQueueItem])
async def list_expert_queue(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_admin_user),
    service: AdminService = Depends(_get_service),
    review_repo: AnalysisExpertReviewRepository = Depends(_get_review_repo),
) -> list[dict[str, Any]]:
    flagged = await service.list_flagged_analyses(limit=limit, offset=offset)
    results = []
    for a in flagged:
        count = await review_repo.count_by_analysis(a.id)
        latest = await review_repo.latest_annotation_at(a.id)
        results.append(
            AdminExpertQueueItem(
                analysis_id=a.id,
                exercise_type=a.exercise_type,
                exercise_variant=getattr(a, "exercise_variant", None),
                confidence_score=a.confidence_score,
                flagged_for_review=a.flagged_for_review,
                created_at=a.created_at,
                annotation_count=count,
                latest_annotation_at=latest,
            ).model_dump()
        )
    return results


@router.get("/expert-queue/stats", response_model=AdminExpertQueueStats)
async def expert_queue_stats(
    user: CurrentUser = Depends(get_admin_user),
    service: AdminService = Depends(_get_service),
) -> dict[str, Any]:
    stats = await service.get_expert_queue_stats()
    return AdminExpertQueueStats(**stats).model_dump()


# ---------------------------------------------------------------------------
# Coach Brain Management (P2-037, FR-ADMN-10)
# ---------------------------------------------------------------------------


@router.get("/coach-brain", response_model=list[CoachBrainEntrySchema])
async def list_coach_brain(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    exercise: str | None = Query(None),
    phase: str | None = Query(None),
    entry_type: str | None = Query(None),
    entry_status: str | None = Query(None, alias="status"),
    user: CurrentUser = Depends(get_admin_user),
    repo: CoachBrainRepository = Depends(_get_brain_repo),
) -> list[Any]:
    entries = await repo.list_all(
        limit=limit,
        offset=offset,
        exercise=exercise,
        phase=phase,
        entry_type=entry_type,
        status=entry_status,
    )
    return [_brain_entry_to_schema(e) for e in entries]


@router.post(
    "/coach-brain",
    response_model=CoachBrainEntrySchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_coach_brain_entry(
    body: CoachBrainEntryCreate,
    user: CurrentUser = Depends(get_admin_user),
    repo: CoachBrainRepository = Depends(_get_brain_repo),
) -> Any:
    entry = CoachBrainEntryModel(
        exercise=body.exercise,
        phase=body.phase or "general",
        entry_type=body.entry_type,
        content=body.content,
        trigger_tags=body.trigger_tags,
        confirmation_count=body.confirmation_count,
        status=body.status,
        source_analysis_ids=body.source_analysis_ids,
        confidence_score=body.confidence_score,
        extra_metadata=body.metadata,
    )
    created = await repo.create(entry)
    return _brain_entry_to_schema(created)


@router.patch("/coach-brain/{entry_id}", response_model=CoachBrainEntrySchema)
async def update_coach_brain_entry(
    entry_id: UUID,
    body: CoachBrainEntryUpdate,
    user: CurrentUser = Depends(get_admin_user),
    repo: CoachBrainRepository = Depends(_get_brain_repo),
) -> Any:

    entry = await repo.get_by_id(entry_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Coach Brain entry not found.", "detail": None}},
        )
    updates = body.model_dump(exclude_none=True)
    if "metadata" in updates:
        updates["extra_metadata"] = updates.pop("metadata")
    for k, v in updates.items():
        setattr(entry, k, v)
    updated = await repo.update(entry)
    return _brain_entry_to_schema(updated)


@router.delete(
    "/coach-brain/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_coach_brain_entry(
    entry_id: UUID,
    user: CurrentUser = Depends(get_admin_user),
    repo: CoachBrainRepository = Depends(_get_brain_repo),
) -> None:

    entry = await repo.get_by_id(entry_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Coach Brain entry not found.", "detail": None}},
        )
    await repo.delete_by_id(entry_id)
