"""Pydantic v2 schemas for RAG document admin views.

FR-RAGK-08: Admin corpus view with title, year, exercise type, quality tier,
quality score, chunk count, review status, reviewer name.
FR-RAGK-09: Admin delete + re-embed actions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal
from uuid import UUID

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


class RagDocumentUploadRequest(BaseModel):
    """Phase 1 request: metadata + filename + size, server returns signed URL.

    Reuses DocumentTypeLiteral / QualityTierLiteral / StudyDesignLiteral from
    this module for consistency with RagDocumentUpload (FR-EXPV-05).
    """

    title: str = Field(..., min_length=1, max_length=500)
    document_type: DocumentTypeLiteral = "research_paper"
    exercise_tags: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1900, le=2100)
    doi: str | None = Field(default=None, max_length=200)
    study_design: StudyDesignLiteral | None = None
    population: str | None = Field(default=None, max_length=500)
    measurement_method: str | None = Field(default=None, max_length=500)
    quality_tier: QualityTierLiteral | None = None

    filename: str = Field(..., min_length=5, max_length=255)
    file_size_bytes: int = Field(..., gt=0, le=52_428_800)


class RagDocumentUploadResponse(BaseModel):
    id: UUID
    upload_url: str
    storage_path: str
    expires_at: datetime


class RagDocumentCompleteResponse(BaseModel):
    id: UUID
    review_status: Literal["pending"]
    storage_path: str
