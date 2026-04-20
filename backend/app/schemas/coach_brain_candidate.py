"""Pydantic v2 schemas for coach_brain_candidates.

CoachBrainCandidateCreate is the write model used by the distillation
store_entry node. CoachBrainCandidate is the read model used by the
Batch 3 review queue.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.coach_brain import (
    EntryTypeLiteral,
    ExerciseLiteral,
    PhaseLiteral,
)

LifecycleLiteral = Literal["ADD", "UPDATE", "NOOP"]
ReviewStatusLiteral = Literal["pending", "approved", "rejected", "superseded"]


class CoachBrainCandidateCreate(BaseModel):
    """Write model for a newly distilled candidate."""

    exercise: ExerciseLiteral
    phase: PhaseLiteral | None = None
    entry_type: EntryTypeLiteral
    content: str
    trigger_tags: list[str] = Field(default_factory=list)
    source_analysis_ids: list[uuid.UUID] = Field(min_length=1)
    confidence_score: float | None = None
    eval_scores: dict[str, Any] = Field(default_factory=dict)
    cove_verified: bool | None = None
    cove_explanation: str | None = None
    cove_trace: dict[str, Any] | None = None
    lifecycle_decision: LifecycleLiteral
    nearest_entry_id: uuid.UUID | None = None
    nearest_cosine_sim: float | None = None
    contradiction_flag: bool = False
    requires_technical_review: bool = False
    review_status: ReviewStatusLiteral = "pending"


class CoachBrainCandidate(BaseModel):
    """Read model matching the coach_brain_candidates table row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exercise: ExerciseLiteral
    phase: PhaseLiteral | None
    entry_type: EntryTypeLiteral
    content: str
    trigger_tags: list[str]
    source_analysis_ids: list[uuid.UUID]
    confidence_score: float | None
    eval_scores: dict[str, Any]
    cove_verified: bool | None
    cove_explanation: str | None
    cove_trace: dict[str, Any] | None
    lifecycle_decision: LifecycleLiteral
    nearest_entry_id: uuid.UUID | None
    nearest_cosine_sim: float | None
    contradiction_flag: bool
    requires_technical_review: bool
    review_status: ReviewStatusLiteral
    rejected_reason: str | None
    promoted_entry_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
