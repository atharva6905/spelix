"""Admin expert-review orchestration for Coach Brain candidates (P3-006).

Implements FR-ADMN-12 (admin review queue surface), FR-BRAIN-07 (promote /
reject / edit actions), and FR-BRAIN-18 (confirmation_count=1 at promotion).

Approve flow (near-atomic, ADR-BRAIN-REVIEW-01):
  1. SELECT candidate ... FOR UPDATE (raises CandidateNotFound /
     CandidateAlreadyReviewed).
  2. INSERT coach_brain_entries with status='active', confirmation_count=1,
     and provenance metadata (approved_by, candidate_id, cove_verified, etc.).
  3. Embed + upsert to Qdrant via BrainEmbeddingService.embed_and_upsert.
  4. UPDATE candidate: review_status='approved', promoted_entry_id=new.id.
  5. COMMIT.

If step 3 raises, we catch, rollback the whole transaction, and raise
QdrantUpsertFailed. See ADR-BRAIN-REVIEW-01 for the documented limitation
(narrow window between step 3 success and step 5 commit failure).

Reject flow (FR-BRAIN-07):
  1. Lock candidate, enforce pending.
  2. UPDATE review_status='rejected', rejected_reason=<reason>.
  3. COMMIT.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.candidate_review import SimilarEntry

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coach_brain_entry import CoachBrainEntry
from app.repositories.coach_brain import CoachBrainRepository
from app.repositories.coach_brain_candidate import CoachBrainCandidateRepository
from app.schemas.candidate_review import ApproveResponse, RejectResponse
from app.schemas.coach_brain import CoachBrainEntry as CoachBrainEntrySchema
from app.services.brain_embedding import BrainEmbeddingService

logger = logging.getLogger(__name__)

# Prompt-injection denylist — patterns that, if promoted into coach_brain via
# content_override, would escape the retrieval-augmented coaching prompt at
# inference time. The expert reviewer is the primary defense, but we strip
# obvious separator sequences at the service layer as defence-in-depth.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\n\s*Human\s*:", re.IGNORECASE),
    re.compile(r"\n\s*Assistant\s*:", re.IGNORECASE),
    re.compile(r"<\|im_(start|end)\|>", re.IGNORECASE),
    re.compile(r"\[/?INST\]", re.IGNORECASE),
    re.compile(r"IGNORE\s+(PREVIOUS|PRIOR|ALL)\s+INSTRUCTIONS", re.IGNORECASE),
    re.compile(r"SYSTEM\s+PROMPT", re.IGNORECASE),
)


class CandidateNotFound(Exception):
    """Raised when the candidate UUID does not exist."""


class CandidateAlreadyReviewed(Exception):
    """Raised when the candidate is not in ``review_status='pending'``.

    The FOR UPDATE lock in ``get_by_id_for_update`` serialises two admins
    attempting to approve the same candidate; the second caller observes the
    mutated ``review_status`` and raises this exception.
    """


class PromptInjectionDetected(Exception):
    """Raised when ``content_override`` contains LLM separator sequences.

    Router maps this to HTTP 422 so the admin sees a clear rejection
    rather than a silent sanitisation that might mangle legitimate cues.
    """


class QdrantUpsertFailed(Exception):
    """Raised when the Cohere embed + Qdrant upsert step fails after the
    coach_brain_entries row was staged. The service rolls back the DB
    transaction so retrieval never observes a Postgres orphan."""


class NotBiomechanicsQualified(Exception):
    """Raised when a non-biomechanics-qualified admin attempts to approve
    a candidate flagged with requires_technical_review=True (FR-ADMN-12).
    """


class CandidateReviewService:
    """Orchestrates approve/reject for Coach Brain candidates."""

    def __init__(
        self,
        db: AsyncSession,
        candidate_repo: CoachBrainCandidateRepository,
        entry_repo: CoachBrainRepository,
        brain_embedding: BrainEmbeddingService,
        cohere_client: Any | None = None,
        qdrant_client: Any | None = None,
        cove_service: Any | None = None,
        retrieval_service: Any | None = None,
    ) -> None:
        self._db = db
        self._candidate_repo = candidate_repo
        self._entry_repo = entry_repo
        self._brain_embedding = brain_embedding
        self._cohere_client = cohere_client
        self._qdrant_client = qdrant_client
        self._cove_service = cove_service
        self._retrieval_service = retrieval_service

    async def _rerun_cove_for_edited_content(
        self,
        *,
        final_content: str,
        exercise: str,
        candidate: Any,
    ) -> dict[str, Any]:
        from app.schemas.rag import RetrievedContext
        from app.services.qdrant import COLLECTION_PAPERS_RAG

        assert self._retrieval_service is not None  # guarded by caller
        assert self._cove_service is not None  # guarded by caller

        try:
            contexts: list[RetrievedContext] = (
                await self._retrieval_service.hybrid_search(
                    query=final_content,
                    collection=COLLECTION_PAPERS_RAG,
                    top_k=5,
                    exercise_filter=exercise,
                    rerank=True,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "candidate_review: CoVe re-run retrieval failed for candidate=%s (%s)",
                candidate.id,
                type(exc).__name__,
            )
            return {"cove_rerun_error": type(exc).__name__}

        try:
            from app.distillation.state import BrainCoveResult

            result: BrainCoveResult = await self._cove_service.verify_claim(
                claim=final_content,
                contexts=contexts,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "candidate_review: CoVe re-run verify_claim failed for candidate=%s (%s)",
                candidate.id,
                type(exc).__name__,
            )
            return {"cove_rerun_error": type(exc).__name__}

        return {
            "cove_verified": result.verified,
            "cove_explanation": result.explanation,
            "cove_rerun": True,
        }

    async def approve(
        self,
        *,
        candidate_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        content_override: str | None = None,
        approver_qualified: bool = False,
    ) -> ApproveResponse:
        candidate = await self._candidate_repo.get_by_id_for_update(candidate_id)
        if candidate is None:
            raise CandidateNotFound(str(candidate_id))
        if candidate.review_status != "pending":
            raise CandidateAlreadyReviewed(
                f"candidate {candidate_id} review_status={candidate.review_status}"
            )

        # FR-ADMN-12: compensation entries require a biomechanics-qualified reviewer.
        if candidate.requires_technical_review and not approver_qualified:
            raise NotBiomechanicsQualified(
                f"Candidate {candidate.id} requires biomechanics-qualified reviewer"
            )

        if content_override is not None:
            for pattern in _INJECTION_PATTERNS:
                if pattern.search(content_override):
                    raise PromptInjectionDetected(
                        f"content_override matches denylist pattern: {pattern.pattern}"
                    )

        final_content = content_override if content_override else candidate.content
        edited = content_override is not None and content_override != candidate.content

        extra_metadata: dict[str, Any] = {
            "source": "distillation_pipeline",
            "candidate_id": str(candidate.id),
            "approved_by": str(admin_user_id),
            "lifecycle_decision": candidate.lifecycle_decision,
            "nearest_entry_id": (
                str(candidate.nearest_entry_id)
                if candidate.nearest_entry_id is not None
                else None
            ),
            "nearest_cosine_sim": (
                float(candidate.nearest_cosine_sim)
                if candidate.nearest_cosine_sim is not None
                else None
            ),
            "cove_verified": candidate.cove_verified,
            "cove_explanation": candidate.cove_explanation,
            "eval_scores": candidate.eval_scores or {},
            "edited": edited,
        }
        if edited:
            extra_metadata["original_content"] = candidate.content

            if self._cove_service is not None and self._retrieval_service is not None:
                cove_overrides = await self._rerun_cove_for_edited_content(
                    final_content=final_content,
                    exercise=candidate.exercise,
                    candidate=candidate,
                )
                extra_metadata.update(cove_overrides)

        entry = CoachBrainEntry(
            exercise=candidate.exercise,
            phase=candidate.phase if candidate.phase is not None else "general",
            entry_type=candidate.entry_type,
            content=final_content,
            trigger_tags=list(candidate.trigger_tags or []),
            confirmation_count=1,  # FR-BRAIN-18 initial value
            status="active",
            source_analysis_ids=list(candidate.source_analysis_ids or []),
            confidence_score=candidate.confidence_score,
            extra_metadata=extra_metadata,
        )
        created = await self._entry_repo.create(entry)

        entry_schema = CoachBrainEntrySchema.model_validate({
            "id": created.id,
            "content": created.content,
            "exercise": created.exercise,
            "phase": created.phase,
            "entry_type": created.entry_type,
            "status": created.status,
            "confirmation_count": created.confirmation_count,
            "source_analysis_ids": created.source_analysis_ids,
            "trigger_tags": created.trigger_tags,
            "confidence_score": (
                float(created.confidence_score)
                if created.confidence_score is not None
                else None
            ),
            "metadata": created.extra_metadata,
            "created_at": created.created_at,
            "updated_at": created.updated_at,
        })

        try:
            point_id = await self._brain_embedding.embed_and_upsert(entry_schema)
        except Exception as exc:
            logger.exception(
                "candidate_review: Qdrant upsert failed for candidate=%s, "
                "entry=%s - rolling back",
                candidate.id,
                created.id,
            )
            await self._db.rollback()
            raise QdrantUpsertFailed(str(exc)) from exc

        candidate.review_status = "approved"
        candidate.promoted_entry_id = created.id
        await self._db.flush()
        await self._db.commit()

        return ApproveResponse(
            candidate_id=candidate.id,
            entry_id=created.id,
            qdrant_point_id=point_id,
        )

    async def reject(
        self,
        *,
        candidate_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        reason: str,
    ) -> RejectResponse:
        candidate = await self._candidate_repo.get_by_id_for_update(candidate_id)
        if candidate is None:
            raise CandidateNotFound(str(candidate_id))
        if candidate.review_status != "pending":
            raise CandidateAlreadyReviewed(
                f"candidate {candidate_id} review_status={candidate.review_status}"
            )

        candidate.review_status = "rejected"
        candidate.rejected_reason = reason
        await self._db.flush()
        await self._db.commit()
        logger.info(
            "candidate_review: rejected candidate=%s by admin=%s",
            candidate.id,
            admin_user_id,
        )
        return RejectResponse(candidate_id=candidate.id, rejected_reason=reason)

    async def get_similar_entries(
        self,
        *,
        candidate_id: uuid.UUID,
        limit: int = 2,
    ) -> list[SimilarEntry]:
        """Return top-N nearest active/seed Coach Brain entries for a candidate.

        FR-ADMN-12 (D-037): reviewer sees up to 2 existing entries closest to
        the pending candidate so near-duplicates are obvious pre-approve.

        Re-embeds the candidate's contextual text on demand rather than storing
        the insight embedding — distillation runs daily at low volume and the
        Cohere call is cheap (<10 ms, <0.01¢) per card view. Avoids a schema
        change during the L2 sprint.
        """
        from qdrant_client import models as qdrant_models

        from app.schemas.candidate_review import SimilarEntry
        from app.schemas.coach_brain import CoachBrainEntryCreate
        from app.services.cohere_client import EmbedInputType
        from app.services.qdrant import COLLECTION_COACH_BRAIN

        candidate = await self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFound(str(candidate_id))

        if self._cohere_client is None or self._qdrant_client is None:
            logger.warning(
                "get_similar_entries: vector clients not wired — returning empty list"
            )
            return []

        proxy = CoachBrainEntryCreate(
            content=candidate.content,
            exercise=candidate.exercise,
            phase=candidate.phase,
            entry_type=candidate.entry_type,
            trigger_tags=list(candidate.trigger_tags or []),
        )
        ctx_text = self._brain_embedding.build_contextual_text(proxy)

        [vector] = await self._cohere_client.embed_batch(
            [ctx_text], input_type=EmbedInputType.SEARCH_DOCUMENT
        )

        # FR-BRAIN-05 cold-start: both active and seed are retrievable.
        query_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="exercise",
                    match=qdrant_models.MatchValue(value=candidate.exercise),
                ),
                qdrant_models.FieldCondition(
                    key="status",
                    match=qdrant_models.MatchAny(any=["active", "seed"]),
                ),
            ]
        )
        try:
            response = await self._qdrant_client.query_points(
                collection=COLLECTION_COACH_BRAIN,
                query=vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=False,
            )
            hits = list(response.points)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "get_similar_entries: qdrant query_points failed (%s) — returning empty list",
                exc,
            )
            hits = []

        results: list[SimilarEntry] = []
        for hit in hits:
            entry_id = uuid.UUID(hit.id) if isinstance(hit.id, str) else hit.id
            entry = await self._entry_repo.get_by_id(entry_id)
            if entry is None:
                # Qdrant/Postgres drift — skip the orphan silently; it's not
                # reviewer-relevant and the log line is enough.
                logger.warning(
                    "get_similar_entries: Qdrant hit %s missing in Postgres",
                    entry_id,
                )
                continue
            results.append(
                SimilarEntry.model_validate(
                    {
                        "id": entry.id,
                        "content": entry.content,
                        "exercise": entry.exercise,
                        "phase": entry.phase,
                        "entry_type": entry.entry_type,
                        "cosine_sim": float(hit.score),
                    }
                )
            )
        return results
