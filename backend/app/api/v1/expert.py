"""FastAPI router for expert reviewer endpoints.

All routes require expert_reviewer or admin role via get_expert_reviewer_user.
Requirements: FR-EXPV-01 through FR-EXPV-07, FR-EXPV-08
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_expert_reviewer_user
from app.cv.sagittal_metrics_registry import SAGITTAL_METRICS_REGISTRY
from app.db import get_db
from app.models.rag_document import RagDocument
from app.repositories.analysis import AnalysisRepository
from app.repositories.analysis_expert_review import AnalysisExpertReviewRepository
from app.repositories.rag_document import RagDocumentRepository
from app.repositories.threshold_flag import ThresholdFlagRepository
from app.schemas.expert_review import (
    AnnotationCreate,
    AnnotationResponse,
    ExpertAnalysisDetail,
    ExpertQueueItem,
    GoldenLabelAction,
    SagittalMetricRegistryEntry,
    SagittalMetricRegistryResponse,
)
from app.schemas.rag_document import (
    RagDocumentCompleteResponse,
    RagDocumentReviewAction,
    RagDocumentReviewResponse,
    RagDocumentUploadRequest,
    RagDocumentUploadResponse,
)
from app.schemas.threshold_flag import (
    ThresholdFlagCreate,
    ThresholdFlagResponse,
    ThresholdListing,
)
from app.services.expert import ExpertService
from app.services.paper_storage import PaperStorageService
from app.services.supabase_client import get_service_role_client
from app.services.threshold_flag import (
    InvalidThresholdKey,
    ThresholdFlagService,
)
from app.utils.pdf_upload import PDF_MAGIC_BYTES, FilenameValidationError, sanitize_pdf_filename

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level streaq worker cache (same pattern as analyses.py / consent.py).
# Exactly one worker reference per process; two-state cache so a failed init
# doesn't retry.
# ---------------------------------------------------------------------------
_streaq_worker_cache: Any | None = None
_streaq_worker_cache_initialized: bool = False


async def get_streaq_worker() -> Any | None:
    """Return the cached streaq Worker for enqueueing paper-ingestion jobs.

    Named `get_streaq_worker` (no leading underscore) so that unit tests can
    patch `app.api.v1.expert.get_streaq_worker`. Same two-state cache shape
    as `analyses.py::_get_streaq_worker` and `consent.py::_get_streaq_worker`.
    Returns None when REDIS_URL is unset or when the lazy import raises; the
    enqueue site treats None as 'enqueue disabled' so HTTP requests succeed
    even if the worker is unavailable.
    """
    global _streaq_worker_cache, _streaq_worker_cache_initialized

    if _streaq_worker_cache_initialized:
        return _streaq_worker_cache

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        _streaq_worker_cache = None
        _streaq_worker_cache_initialized = True
        return None

    try:
        from app.workers.streaq_worker import worker

        _streaq_worker_cache = worker
    except Exception as e:
        logger.warning("Failed to import streaq worker: %s", e)
        _streaq_worker_cache = None

    _streaq_worker_cache_initialized = True
    return _streaq_worker_cache


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


async def _get_threshold_flag_repo(
    db: AsyncSession = Depends(get_db),
) -> ThresholdFlagRepository:
    return ThresholdFlagRepository(db)


async def _get_threshold_service(
    db: AsyncSession = Depends(get_db),
) -> ThresholdFlagService:
    return ThresholdFlagService(repo=ThresholdFlagRepository(db))


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

    if detail.annotated_video_url:
        try:
            from app.services.storage import StorageService

            storage = StorageService()
            signed = await storage.create_signed_read_url(
                detail.annotated_video_url, expires_in=3600
            )
            detail = detail.model_copy(update={"annotated_video_url": signed})
        except Exception:
            logger.warning(
                "Failed to sign video URL for expert analysis %s", analysis_id
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
# Paper Upload (P2-042, FR-EXPV-02)
# ---------------------------------------------------------------------------


@router.post(
    "/papers",
    response_model=RagDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_paper_upload(
    body: RagDocumentUploadRequest,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    rag_repo: RagDocumentRepository = Depends(_get_rag_repo),
) -> Any:
    """Phase 1 of expert PDF upload (ADR-EXPERT-01).

    Validates the proposed filename + size, generates a UUID, creates
    a rag_documents row with review_status='uploading', and returns a
    signed Supabase Storage upload URL that the browser PUTs the file
    to directly (FastAPI never sees the bytes).

    The client must call POST /papers/{id}/complete after the PUT to
    trigger the magic-byte check + ingestion enqueue (Task 6).
    """
    try:
        safe_name = sanitize_pdf_filename(body.filename)
    except FilenameValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_FILENAME", "message": str(err), "detail": None}},
        ) from err

    paper_id = uuid4()
    storage_path = f"papers/{paper_id}/{safe_name}"

    doc = RagDocument(
        id=paper_id,
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
        review_status="uploading",
        storage_path=storage_path,
        extra_metadata={"uploaded_by": str(user["id"])},
        ingested_at=datetime.now(timezone.utc),
    )
    created = await rag_repo.create(doc)

    storage = PaperStorageService(client=await get_service_role_client())
    signed = await storage.generate_signed_upload_url(storage_path)

    return RagDocumentUploadResponse(
        id=created.id,
        upload_url=signed.url,
        storage_path=storage_path,
        expires_at=signed.expires_at,
    )


# ---------------------------------------------------------------------------
# Paper Upload Complete (FR-EXPV-02, ADR-EXPERT-01 phase 3)
# ---------------------------------------------------------------------------


@router.post(
    "/papers/{paper_id}/complete",
    response_model=RagDocumentCompleteResponse,
    status_code=status.HTTP_200_OK,
)
async def complete_paper_upload(
    paper_id: UUID,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    rag_repo: RagDocumentRepository = Depends(_get_rag_repo),
) -> Any:
    """Phase 3 of expert PDF upload (ADR-EXPERT-01).

    Called by the client after the direct Supabase Storage PUT succeeds.
    Downloads the first 8 bytes of the stored object via service-role
    client to verify the PDF magic-byte prefix (b"%PDF-"). On failure
    the storage object and DB row are deleted and 422 INVALID_PDF is
    returned. On success the DB row flips from review_status='uploading'
    to 'pending' and an ingest_paper ARQ job is enqueued.
    """
    doc = await rag_repo.get_by_id(paper_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "paper not found",
                    "detail": None,
                }
            },
        )

    if doc.review_status != "uploading":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "INVALID_STATE",
                    "message": (
                        f"paper is not in 'uploading' state"
                        f" (current: {doc.review_status!r})"
                    ),
                    "detail": None,
                }
            },
        )

    # An 'uploading' row is always created with a non-null storage_path in
    # request_paper_upload; assert for the type-checker so the downstream
    # storage_path arguments narrow to str. A None here indicates corrupt
    # state and should be treated as a server error.
    storage_path = doc.storage_path
    if storage_path is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CORRUPT_STATE",
                    "message": "uploading row has no storage_path",
                    "detail": None,
                }
            },
        )

    storage = PaperStorageService(client=await get_service_role_client())
    head = await storage.download_head_bytes(storage_path, n=8)

    if not head.startswith(PDF_MAGIC_BYTES):
        await storage.delete_object(storage_path)
        await rag_repo.delete(paper_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "INVALID_PDF",
                    "message": "uploaded bytes are not a PDF",
                    "detail": None,
                }
            },
        )

    # Confirm the ingestion queue is reachable BEFORE flipping the row —
    # otherwise a missing REDIS_URL leaves the paper in 'pending' with no
    # job enqueued (silent orphan, security review C-1).
    streaq_worker = await get_streaq_worker()
    if streaq_worker is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "QUEUE_UNAVAILABLE",
                    "message": "ingestion queue is not configured; try again later",
                    "detail": None,
                }
            },
        )

    # System-initiated transition (uploading → pending). reviewer_id stays
    # NULL until an actual human reviews the paper via the review queue.
    updated = await rag_repo.update_review_status(
        paper_id,
        review_status="pending",
    )
    # update_review_status is typed Optional (returns None if the row vanished
    # between the earlier get_by_id and now). A concurrent delete on an
    # 'uploading' row is not expected, but narrow for the type-checker.
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CORRUPT_STATE",
                    "message": "paper row vanished during complete",
                    "detail": None,
                }
            },
        )

    # Lazy-imported to avoid api.v1 → worker → api.v1 cycle.
    from app.workers.streaq_worker import ingest_paper

    await ingest_paper.enqueue(str(paper_id))

    return RagDocumentCompleteResponse(
        id=updated.id,
        review_status="pending",
        storage_path=storage_path,
    )


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

    if body.decision == "reviewed_approved":
        from app.workers.streaq_worker import ingest_paper

        await ingest_paper.enqueue(str(doc_id))

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


# ---------------------------------------------------------------------------
# Threshold Validation (FR-EXPV-08)
# ---------------------------------------------------------------------------


@router.get("/thresholds", response_model=ThresholdListing)
async def get_thresholds(
    user: CurrentUser = Depends(get_expert_reviewer_user),
    service: ThresholdFlagService = Depends(_get_threshold_service),
) -> ThresholdListing:
    """Return current angle thresholds grouped by exercise section.

    Source: ``config/thresholds_v1.json``. This endpoint is read-only —
    edits to values happen via PR review (FR-SCOR-11).
    """
    return service.get_listing()


@router.post(
    "/thresholds/flags",
    response_model=ThresholdFlagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_threshold_flag(
    body: ThresholdFlagCreate,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    service: ThresholdFlagService = Depends(_get_threshold_service),
) -> Any:
    try:
        flag = await service.create_flag(
            reviewer_id=user["id"],
            section=body.section,
            key=body.key,
            proposed_value=body.proposed_value,
            proposed_citation=body.proposed_citation,
            rationale=body.rationale,
        )
    except InvalidThresholdKey as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "UNKNOWN_THRESHOLD_KEY",
                    "message": str(err),
                    "detail": None,
                }
            },
        ) from err
    return ThresholdFlagResponse.model_validate(flag, from_attributes=True)


# ---------------------------------------------------------------------------
# Sagittal Metrics Registry (Session 3, L2-SAGITTAL-INFRA-02,
# ADR-SAGITTAL-METRICS-REGISTRY)
# ---------------------------------------------------------------------------


@router.get(
    "/sagittal-metrics-registry",
    response_model=SagittalMetricRegistryResponse,
)
async def get_sagittal_metrics_registry(
    user: CurrentUser = Depends(get_expert_reviewer_user),
) -> SagittalMetricRegistryResponse:
    """Return the 16-entry sagittal metrics registry.

    Single source of truth for the metrics Sessions 4-7 will populate.
    Static data -- no DB lookup. Auth: expert_reviewer or admin.
    """
    entries = [
        SagittalMetricRegistryEntry(
            key_name=e.key_name,
            display_label=e.display_label,
            unit=e.unit,
            description=e.description,
            exercise_applicability=sorted(e.exercise_applicability),
            computed_yet=e.computed_yet,
            in_scoring=e.in_scoring,
        )
        # Sort for deterministic ordering -- display label gives a sensible
        # UX ordering for the panel.
        for e in sorted(
            SAGITTAL_METRICS_REGISTRY, key=lambda x: x.display_label
        )
    ]
    return SagittalMetricRegistryResponse(entries=entries)


@router.get("/thresholds/flags", response_model=list[ThresholdFlagResponse])
async def list_my_threshold_flags(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_expert_reviewer_user),
    repo: ThresholdFlagRepository = Depends(_get_threshold_flag_repo),
) -> list[Any]:
    rows = await repo.list_by_reviewer(user["id"], limit=limit, offset=offset)
    return [ThresholdFlagResponse.model_validate(r, from_attributes=True) for r in rows]


# ---------------------------------------------------------------------------
# My Papers (expert-uploaded documents)
# ---------------------------------------------------------------------------


@router.get("/papers")
async def list_my_papers(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_expert_reviewer_user),
    db: AsyncSession = Depends(get_db),
) -> list[Any]:
    from sqlalchemy import select

    from app.schemas.rag_document import RagDocumentResponse

    stmt = (
        select(RagDocument)
        .where(
            RagDocument.extra_metadata["uploaded_by"].as_string() == str(user["id"]),
            RagDocument.review_status != "uploading",
        )
        .order_by(RagDocument.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [RagDocumentResponse.model_validate(r, from_attributes=True) for r in rows]
