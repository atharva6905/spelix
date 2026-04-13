"""FastAPI router for expert reviewer endpoints.

All routes require expert_reviewer or admin role via get_expert_reviewer_user.
Requirements: FR-EXPV-01 through FR-EXPV-07
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_expert_reviewer_user
from app.db import get_db
from app.models.rag_document import RagDocument
from app.repositories.analysis import AnalysisRepository
from app.repositories.analysis_expert_review import AnalysisExpertReviewRepository
from app.repositories.rag_document import RagDocumentRepository
from app.schemas.expert_review import (
    AnnotationCreate,
    AnnotationResponse,
    ExpertAnalysisDetail,
    ExpertQueueItem,
    GoldenLabelAction,
)
from app.schemas.rag_document import (
    RagDocumentResponse,
    RagDocumentReviewAction,
    RagDocumentReviewResponse,
    RagDocumentUpload,
)
from app.services.expert import ExpertService

router = APIRouter(tags=["expert"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def _get_service(db: AsyncSession = Depends(get_db)) -> ExpertService:
    return ExpertService(
        analysis_repo=AnalysisRepository(db),
        review_repo=AnalysisExpertReviewRepository(db),
        rag_doc_repo=RagDocumentRepository(db),
    )


async def _get_rag_repo(db: AsyncSession = Depends(get_db)) -> RagDocumentRepository:
    return RagDocumentRepository(db)


async def _get_review_repo(db: AsyncSession = Depends(get_db)) -> AnalysisExpertReviewRepository:
    return AnalysisExpertReviewRepository(db)


# ---------------------------------------------------------------------------
# Review Queue (P2-039, FR-EXPV-02)
# ---------------------------------------------------------------------------


@router.get("/queue", response_model=list[ExpertQueueItem])
async def get_expert_queue(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    queue_type: str = Query("all", pattern="^(flagged|low_quality|first_run|all)$"),
    user: CurrentUser = Depends(get_expert_reviewer_user),
    service: ExpertService = Depends(_get_service),
) -> list[ExpertQueueItem]:
    return await service.get_review_queue(
        queue_type=queue_type, limit=limit, offset=offset
    )


# ---------------------------------------------------------------------------
# Analysis Detail — Anonymized (P2-040, FR-EXPV-03)
# ---------------------------------------------------------------------------


@router.get("/analyses/{analysis_id}", response_model=ExpertAnalysisDetail)
async def get_expert_analysis_detail(
    analysis_id: UUID,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    service: ExpertService = Depends(_get_service),
) -> ExpertAnalysisDetail:
    detail = await service.get_analysis_detail(analysis_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Analysis not found.", "detail": None}},
        )
    return detail


# ---------------------------------------------------------------------------
# Annotation Submission (P2-041, FR-EXPV-04)
# ---------------------------------------------------------------------------


@router.post(
    "/analyses/{analysis_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_annotation(
    analysis_id: UUID,
    body: AnnotationCreate,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    service: ExpertService = Depends(_get_service),
) -> Any:
    # Verify analysis exists

    review = await service.submit_annotation(
        analysis_id=analysis_id,
        annotator_id=user["id"],
        data=body,
    )
    return AnnotationResponse.model_validate(review, from_attributes=True)


@router.get(
    "/analyses/{analysis_id}/annotations",
    response_model=list[AnnotationResponse],
)
async def list_annotations(
    analysis_id: UUID,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    review_repo: AnalysisExpertReviewRepository = Depends(_get_review_repo),
) -> list[Any]:
    reviews = await review_repo.list_by_analysis(analysis_id)
    return [AnnotationResponse.model_validate(r, from_attributes=True) for r in reviews]


# ---------------------------------------------------------------------------
# Paper Upload (P2-042, FR-EXPV-05)
# ---------------------------------------------------------------------------


@router.post(
    "/papers",
    response_model=RagDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_paper(
    body: RagDocumentUpload,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    rag_repo: RagDocumentRepository = Depends(_get_rag_repo),
) -> Any:
    doc = RagDocument(
        title=body.title,
        document_type=body.document_type,
        exercise_tags=body.exercise_tags,
        authors=body.authors,
        year=body.year,
        doi=body.doi,
        study_design=body.study_design,
        population=body.population,
        measurement_method=body.measurement_method,
        quality_tier=body.quality_tier,
        review_status="pending",
        extra_metadata={},
    )
    created = await rag_repo.create(doc)
    return RagDocumentResponse.model_validate(created, from_attributes=True)


# ---------------------------------------------------------------------------
# Paper Review (P2-043, FR-EXPV-06)
# ---------------------------------------------------------------------------


@router.patch("/papers/{doc_id}/review", response_model=RagDocumentReviewResponse)
async def review_paper(
    doc_id: UUID,
    body: RagDocumentReviewAction,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    rag_repo: RagDocumentRepository = Depends(_get_rag_repo),
) -> Any:
    doc = await rag_repo.update_review_status(
        doc_id,
        review_status=body.decision,
        reviewer_id=user["id"],
    )
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Document not found.", "detail": None}},
        )
    return RagDocumentReviewResponse.model_validate(doc, from_attributes=True)


# ---------------------------------------------------------------------------
# Golden Dataset Labeling (P2-044, FR-EXPV-07)
# ---------------------------------------------------------------------------


@router.patch("/analyses/{analysis_id}/golden")
async def label_golden_dataset(
    analysis_id: UUID,
    body: GoldenLabelAction,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    service: ExpertService = Depends(_get_service),
) -> dict[str, Any]:
    result = await service.set_golden_label(analysis_id, body.is_golden_dataset)
    if not result:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Analysis not found.", "detail": None}},
        )
    return result
