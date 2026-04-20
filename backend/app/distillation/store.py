"""store_entry — DB transaction: INSERT candidate + conditional UPDATE on source entry.

Every formatted CoachBrainCandidateCreate produces one row in
coach_brain_candidates. When lifecycle_decision='UPDATE', the same
session also bumps the referenced coach_brain_entries row's
confirmation_count and appends the new source_analysis_id
(FR-BRAIN-18).

Both writes share the caller-provided AsyncSession so that a rollback
(raised elsewhere in the pipeline, not here) undoes both. The caller
owns commit/rollback — this node only flushes.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select

from app.distillation.state import DistillationState
from app.models.coach_brain_candidate import CoachBrainCandidate as CoachBrainCandidateRow
from app.models.coach_brain_entry import CoachBrainEntry

logger = logging.getLogger(__name__)


async def store_entry(
    state: DistillationState,
    *,
    db_session: Any,
) -> dict[str, Any]:
    """Persist formatted candidates + apply UPDATE-path confirmation bumps."""
    formatted = state.get("formatted") or []
    if not formatted:
        return {"stored_ids": []}

    stored_ids: list[uuid.UUID] = []

    for row in formatted:
        candidate_row = CoachBrainCandidateRow(
            exercise=row.exercise,
            phase=row.phase,
            entry_type=row.entry_type,
            content=row.content,
            trigger_tags=row.trigger_tags,
            source_analysis_ids=row.source_analysis_ids,
            confidence_score=row.confidence_score,
            eval_scores=row.eval_scores,
            cove_verified=row.cove_verified,
            cove_explanation=row.cove_explanation,
            cove_trace=row.cove_trace,
            lifecycle_decision=row.lifecycle_decision,
            nearest_entry_id=row.nearest_entry_id,
            nearest_cosine_sim=row.nearest_cosine_sim,
            contradiction_flag=row.contradiction_flag,
            requires_technical_review=(row.entry_type == "compensation"),
            review_status=row.review_status,
        )
        db_session.add(candidate_row)
        await db_session.flush()
        stored_ids.append(candidate_row.id)

        if row.lifecycle_decision == "UPDATE" and row.nearest_entry_id is not None:
            stmt = select(CoachBrainEntry).where(CoachBrainEntry.id == row.nearest_entry_id)
            result = await db_session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is None:
                logger.warning(
                    "store_entry: UPDATE-path nearest_entry_id=%s not found; "
                    "candidate %s stored without confirmation bump.",
                    row.nearest_entry_id,
                    candidate_row.id,
                )
                continue
            existing.confirmation_count = (existing.confirmation_count or 0) + 1
            # array_append via list assignment — SQLAlchemy serialises as ARRAY literal.
            existing.source_analysis_ids = list(existing.source_analysis_ids or []) + list(
                row.source_analysis_ids
            )
            await db_session.flush()

    return {"stored_ids": stored_ids}
