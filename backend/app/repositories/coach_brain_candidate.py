"""Repository for coach_brain_candidates table.

All DB access for candidates passes through this class. Distillation
store_entry node uses `create`; Batch 3 admin UI uses `list_pending`
+ `get_by_id`.
"""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import func, literal_column, select
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
        stmt = select(CoachBrainCandidateRow).where(
            CoachBrainCandidateRow.id == candidate_id
        )
        result = await self._db.execute(stmt)
        row = result.scalars().one_or_none()
        return CoachBrainCandidate.model_validate(row) if row is not None else None

    async def list_pending_ordered(
        self, *, limit: int = 50, offset: int = 0
    ) -> Sequence[CoachBrainCandidate]:
        """Pending candidates sorted for review: highest quality first.

        Sort key precedence:
          1. eval_scores->>'overall' DESC NULLS LAST
          2. eval_scores->>'faithfulness' DESC NULLS LAST
          3. created_at DESC

        Mirrors the distillation gate fallback (PR #80 / PR #81): `overall`
        is Phase-4-populated; until then `faithfulness` carries the sort.
        """
        overall_sort = (
            literal_column("(eval_scores->>'overall')::float").desc().nulls_last()
        )
        faith_sort = (
            literal_column("(eval_scores->>'faithfulness')::float").desc().nulls_last()
        )
        stmt = (
            select(CoachBrainCandidateRow)
            .where(CoachBrainCandidateRow.review_status == "pending")
            .order_by(
                overall_sort, faith_sort, CoachBrainCandidateRow.created_at.desc()
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return [CoachBrainCandidate.model_validate(r) for r in result.scalars().all()]

    async def count_pending(self) -> int:
        stmt = select(func.count(CoachBrainCandidateRow.id)).where(
            CoachBrainCandidateRow.review_status == "pending"
        )
        result = await self._db.execute(stmt)
        return int(result.scalar_one())

    async def get_by_id_for_update(
        self, candidate_id: uuid.UUID
    ) -> CoachBrainCandidateRow | None:
        """Fetch the ORM row with SELECT ... FOR UPDATE for approve/reject.

        Returns the ORM object (not the Pydantic schema) so the caller can
        mutate ``review_status``, ``rejected_reason``, ``promoted_entry_id``
        in-session and flush alongside the entry INSERT.
        """
        stmt = (
            select(CoachBrainCandidateRow)
            .where(CoachBrainCandidateRow.id == candidate_id)
            .with_for_update()
        )
        result = await self._db.execute(stmt)
        return result.scalars().one_or_none()
