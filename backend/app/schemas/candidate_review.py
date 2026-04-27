"""Pydantic v2 schemas for the admin Coach Brain candidate review queue.

Kept separate from app.schemas.coach_brain_candidate (which models the
distillation write path) so review-path contracts can evolve without
re-validating every candidate row produced upstream.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.coach_brain import (
    EntryTypeLiteral,
    ExerciseLiteral,
    PhaseLiteral,
)
from app.schemas.coach_brain_candidate import (
    LifecycleLiteral,
    ReviewStatusLiteral,
)


class CandidateListItem(BaseModel):
    """Subset of CoachBrainCandidate surfaced to the admin review UI."""

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
    lifecycle_decision: LifecycleLiteral
    nearest_entry_id: uuid.UUID | None
    nearest_cosine_sim: float | None
    nearest_entry_confirmation_count: int | None = None
    contradiction_flag: bool
    requires_technical_review: bool = False
    review_status: ReviewStatusLiteral
    created_at: datetime


class ApproveRequest(BaseModel):
    """Body for POST /admin/coach-brain/candidates/{id}/approve.

    ``content_override`` optionally replaces the candidate's content verbatim
    when the admin edits the cue inline. Empty / whitespace-only strings are
    normalised to ``None`` so the backend falls through to the candidate's
    original content. Post-normalisation content must be 5-500 chars --
    FR-BRAIN-02 specifies 5-20 words for coaching actions; 500 chars is a
    generous upper bound that prevents essay-length pastes from degrading
    retrieval quality.
    """

    content_override: str | None = Field(default=None, min_length=5, max_length=500)

    @field_validator("content_override", mode="before")
    @classmethod
    def _normalise_blank(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class RejectRequest(BaseModel):
    """Body for POST /admin/coach-brain/candidates/{id}/reject.

    ``reason`` is required (min 1 non-whitespace char). Stored verbatim on
    ``coach_brain_candidates.rejected_reason`` for audit.
    """

    reason: str = Field(min_length=1)

    @field_validator("reason", mode="before")
    @classmethod
    def _strip(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


class ApproveResponse(BaseModel):
    candidate_id: uuid.UUID
    entry_id: uuid.UUID
    qdrant_point_id: str


class RejectResponse(BaseModel):
    candidate_id: uuid.UUID
    rejected_reason: str


class PendingQueueResponse(BaseModel):
    """Paginated list response for GET /admin/coach-brain/candidates."""

    items: list[CandidateListItem]
    total_pending: int


class PendingQueueStats(BaseModel):
    """Response for GET /admin/coach-brain/candidates/stats."""

    total_pending: int


class SimilarEntry(BaseModel):
    """One nearest approved/seed Coach Brain entry surfaced on the review card.

    D-037 / FR-ADMN-12: the reviewer needs to see up to 2 existing entries
    that already cover similar ground, so they can spot near-duplicates
    before promoting a new candidate.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str
    exercise: ExerciseLiteral
    phase: PhaseLiteral | None
    entry_type: EntryTypeLiteral
    cosine_sim: float


class SimilarEntriesResponse(BaseModel):
    items: list[SimilarEntry]
