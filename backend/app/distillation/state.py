"""DistillationState TypedDict + supporting Pydantic models.

Three models (CandidateInsight, LifecycleDecision, BrainCoveResult)
live here because they are the lingua franca of the pipeline — every
node reads or writes at least one of them.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

from app.schemas.coach_brain import EntryTypeLiteral, ExerciseLiteral, PhaseLiteral
from app.schemas.coach_brain_candidate import CoachBrainCandidateCreate
from app.schemas.coaching import CoachingOutput
from app.schemas.rag import RetrievedContext


ValidationDecision = Literal["pass", "review", "reject"]
LifecycleLabel = Literal["ADD", "UPDATE", "NOOP"]


class CandidateInsight(BaseModel):
    """One extracted coaching insight prior to lifecycle routing."""

    content: str = Field(min_length=1)
    exercise: ExerciseLiteral
    phase: PhaseLiteral | None = None
    entry_type: EntryTypeLiteral
    trigger_tags: list[str] = Field(default_factory=list)
    confidence_score: float | None = None


class LifecycleDecision(BaseModel):
    """Output of the lifecycle_decision node for one CandidateInsight."""

    decision: LifecycleLabel
    nearest_entry_id: uuid.UUID | None = None
    cosine_sim: float = 0.0


class BrainCoveResult(BaseModel):
    """Output of BrainCoveService.verify_claim for one candidate."""

    verified: bool
    explanation: str
    trace: list[dict[str, Any]] = Field(default_factory=list)


class DistillationState(TypedDict):
    # inputs
    analysis_id: uuid.UUID
    exercise_type: str
    coaching_output: CoachingOutput
    retrieved_papers_contexts: list[RetrievedContext]
    eval_scores: dict[str, Any]

    # working set
    candidates: list[CandidateInsight]
    validation_decision: ValidationDecision
    decisions: list[LifecycleDecision]
    cove_results: list[BrainCoveResult]
    formatted: list[CoachBrainCandidateCreate]

    # output
    stored_ids: list[uuid.UUID]
    trace: list[dict[str, Any]]


def make_initial_distillation_state(
    *,
    analysis_id: uuid.UUID,
    exercise_type: str,
    coaching_output: CoachingOutput,
    retrieved_papers_contexts: list[RetrievedContext],
    eval_scores: dict[str, Any],
) -> DistillationState:
    """Construct a DistillationState with safe defaults for every field."""
    return DistillationState(
        analysis_id=analysis_id,
        exercise_type=exercise_type,
        coaching_output=coaching_output,
        retrieved_papers_contexts=retrieved_papers_contexts,
        eval_scores=eval_scores,
        candidates=[],
        validation_decision="pass",
        decisions=[],
        cove_results=[],
        formatted=[],
        stored_ids=[],
        trace=[],
    )
