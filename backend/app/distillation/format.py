"""format_entry — pure function that packs Pydantic write models.

Aligned-iteration (candidates, decisions, cove_results). NOOP decisions
are dropped entirely — no row written. UPDATE decisions emit a
candidate row with review_status='superseded' (audit-only, not in
review queue). ADD decisions emit review_status='pending'.

Contradiction flag: set when decision='UPDATE' AND cove_verified=false.
"""

from __future__ import annotations

from typing import Any

from app.distillation.state import DistillationState
from app.schemas.coach_brain_candidate import CoachBrainCandidateCreate


async def format_entry(state: DistillationState) -> dict[str, Any]:
    """Zip candidates/decisions/cove_results into CoachBrainCandidateCreate rows."""
    candidates = state.get("candidates") or []
    decisions = state.get("decisions") or []
    cove_results = state.get("cove_results") or []
    analysis_id = state["analysis_id"]
    eval_scores = state.get("eval_scores") or {}

    formatted: list[CoachBrainCandidateCreate] = []
    for candidate, decision, cove in zip(
        candidates, decisions, cove_results, strict=True
    ):
        if decision.decision == "NOOP":
            continue

        contradiction = (
            decision.decision == "UPDATE" and cove.verified is False
        )
        review_status = "superseded" if decision.decision == "UPDATE" else "pending"

        formatted.append(
            CoachBrainCandidateCreate(
                exercise=candidate.exercise,
                phase=candidate.phase,
                entry_type=candidate.entry_type,
                content=candidate.content,
                trigger_tags=candidate.trigger_tags,
                source_analysis_ids=[analysis_id],
                confidence_score=candidate.confidence_score,
                eval_scores=eval_scores,
                cove_verified=cove.verified,
                cove_explanation=cove.explanation,
                cove_trace={"trace": cove.trace},
                lifecycle_decision=decision.decision,
                nearest_entry_id=decision.nearest_entry_id,
                nearest_cosine_sim=decision.cosine_sim,
                contradiction_flag=contradiction,
                review_status=review_status,
            )
        )
    return {"formatted": formatted}
