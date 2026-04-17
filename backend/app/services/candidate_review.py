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
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coach_brain_entry import CoachBrainEntry
from app.repositories.coach_brain import CoachBrainRepository
from app.repositories.coach_brain_candidate import CoachBrainCandidateRepository
from app.schemas.candidate_review import ApproveResponse, RejectResponse
from app.schemas.coach_brain import CoachBrainEntry as CoachBrainEntrySchema
from app.services.brain_embedding import BrainEmbeddingService

logger = logging.getLogger(__name__)


class CandidateNotFound(Exception):
    """Raised when the candidate UUID does not exist."""


class CandidateAlreadyReviewed(Exception):
    """Raised when the candidate is not in ``review_status='pending'``.

    The FOR UPDATE lock in ``get_by_id_for_update`` serialises two admins
    attempting to approve the same candidate; the second caller observes the
    mutated ``review_status`` and raises this exception.
    """


class QdrantUpsertFailed(Exception):
    """Raised when the Cohere embed + Qdrant upsert step fails after the
    coach_brain_entries row was staged. The service rolls back the DB
    transaction so retrieval never observes a Postgres orphan."""


class CandidateReviewService:
    """Orchestrates approve/reject for Coach Brain candidates."""

    def __init__(
        self,
        db: AsyncSession,
        candidate_repo: CoachBrainCandidateRepository,
        entry_repo: CoachBrainRepository,
        brain_embedding: BrainEmbeddingService,
    ) -> None:
        self._db = db
        self._candidate_repo = candidate_repo
        self._entry_repo = entry_repo
        self._brain_embedding = brain_embedding

    async def approve(
        self,
        *,
        candidate_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        content_override: str | None = None,
    ) -> ApproveResponse:
        candidate = await self._candidate_repo.get_by_id_for_update(candidate_id)
        if candidate is None:
            raise CandidateNotFound(str(candidate_id))
        if candidate.review_status != "pending":
            raise CandidateAlreadyReviewed(
                f"candidate {candidate_id} review_status={candidate.review_status}"
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
