"""Repository for coach_brain_candidates table.

All DB access for candidates passes through this class. Distillation
store_entry node uses `create`; Batch 3 admin UI uses `list_pending`
+ `get_by_id`.
"""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coach_brain_candidate import CoachBrainCandidate as CoachBrainCandidateRow
from app.schemas.coach_brain_candidate import (
    CoachBrainCandidate,
    CoachBrainCandidateCreate,
)


class CoachBrainCandidateRepository:
    """DB access layer for coach_brain_candidates."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, create: CoachBrainCandidateCreate) -> CoachBrainCandidate:
        row = CoachBrainCandidateRow(
            exercise=create.exercise,
            phase=create.phase,
            entry_type=create.entry_type,
            content=create.content,
            trigger_tags=create.trigger_tags,
            source_analysis_ids=create.source_analysis_ids,
            confidence_score=create.confidence_score,
            eval_scores=create.eval_scores,
            cove_verified=create.cove_verified,
            cove_explanation=create.cove_explanation,
            cove_trace=create.cove_trace,
            lifecycle_decision=create.lifecycle_decision,
            nearest_entry_id=create.nearest_entry_id,
            nearest_cosine_sim=create.nearest_cosine_sim,
            contradiction_flag=create.contradiction_flag,
            review_status=create.review_status,
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return CoachBrainCandidate.model_validate(row)

    async def list_pending(self, limit: int = 100) -> Sequence[CoachBrainCandidate]:
        stmt = (
            select(CoachBrainCandidateRow)
            .where(CoachBrainCandidateRow.review_status == "pending")
            .order_by(CoachBrainCandidateRow.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return [CoachBrainCandidate.model_validate(r) for r in result.scalars().all()]

    async def get_by_id(self, candidate_id: uuid.UUID) -> CoachBrainCandidate | None:
        stmt = select(CoachBrainCandidateRow).where(CoachBrainCandidateRow.id == candidate_id)
        result = await self._db.execute(stmt)
        row = result.scalars().one_or_none()
        return CoachBrainCandidate.model_validate(row) if row is not None else None
