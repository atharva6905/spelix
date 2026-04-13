"""Pydantic v2 schemas for RAG document admin views.

FR-RAGK-08: Admin corpus view with title, year, exercise type, quality tier,
quality score, chunk count, review status, reviewer name.
FR-RAGK-09: Admin delete + re-embed actions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ReviewStatusLiteral = Literal[
    "pending",
    "needs_revision",
    "reviewed_approved",
    "reviewed_rejected",
]

DocumentTypeLiteral = Literal[
    "research_paper",
    "textbook",
    "clinical_guideline",
    "expert_annotation",
    "other",
]

QualityTierLiteral = Literal[
    "L1_systematic_review",
    "L2_rct",
    "L3_observational",
    "L4_guideline",
]

StudyDesignLiteral = Literal[
    "rct",
    "observational",
    "systematic_review",
    "narrative_review",
    "guideline",
    "other",
]


class RagDocumentResponse(BaseModel):
    """Full RAG document response for admin corpus view (FR-RAGK-08)."""

    id: uuid.UUID
    title: str
    source_url: str | None
    document_type: str
    exercise_tags: list[str]
    chunk_count: int
    ingested_at: datetime
    authors: list[str]
    year: int | None
    doi: str | None
    study_design: str | None
    population: str | None
    measurement_method: str | None
    quality_tier: str | None
    quality_score: float | None
    review_status: str
    reviewer_id: uuid.UUID | None
    reviewed_at: datetime | None
    storage_path: str | None
    created_at: datetime
    updated_at: datetime


class RagDocumentUpload(BaseModel):
    """Schema for paper upload metadata (FR-EXPV-05)."""

    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    exercise_tags: list[str] = Field(default_factory=list)
    quality_tier: QualityTierLiteral | None = None
    study_design: StudyDesignLiteral | None = None
    population: str | None = None
    measurement_method: str | None = None
    document_type: DocumentTypeLiteral = "research_paper"


class RagDocumentReviewAction(BaseModel):
    """Schema for paper review decision (FR-EXPV-06)."""

    decision: Literal["reviewed_approved", "reviewed_rejected", "needs_revision"]
    review_notes: str | None = None


class RagDocumentReviewResponse(BaseModel):
    """Response after review action."""

    id: uuid.UUID
    title: str
    review_status: str
    reviewer_id: uuid.UUID | None
    reviewed_at: datetime | None


class ReEmbedResponse(BaseModel):
    """Response for re-embed action (FR-RAGK-09)."""

    message: str
    document_id: uuid.UUID
