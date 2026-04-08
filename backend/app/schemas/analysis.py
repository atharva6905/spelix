"""Pydantic v2 schemas for the analyses resource.

Requirements: FR-UPLD-07, FR-UPLD-16, FR-UPLD-17, FR-RESL-13, FR-UPLD-10, FR-UPLD-11, FR-HIST-01
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Exercise type / variant constraints
# ---------------------------------------------------------------------------

ExerciseType = Literal["squat", "bench", "deadlift"]

SquatVariant = Literal["high_bar", "low_bar"]
BenchVariant = Literal["flat", "incline", "decline"]
DeadliftVariant = Literal["conventional", "sumo", "romanian"]

MAX_FILE_SIZE_BYTES = 52_428_800  # 50 MB


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AnalysisCreate(BaseModel):
    """Request body for POST /api/v1/analyses.

    Validates exercise type, variant, filename, and file size.
    File size must be > 0 and <= 50 MB (FR-UPLD-16).
    """

    exercise_type: str = Field(..., description="Exercise type: squat | bench | deadlift")
    exercise_variant: str = Field(..., description="Exercise variant (depends on type)")
    filename: str = Field(..., min_length=1, description="Original filename of the video")
    file_size_bytes: int = Field(..., description="File size in bytes (1 to 50 MB)")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AnalysisCreateResponse(BaseModel):
    """201 response for POST /api/v1/analyses."""

    id: UUID
    upload_url: str
    status: str
    expires_at: datetime

    model_config = {"from_attributes": True}


class AnalysisStartResponse(BaseModel):
    """202 response for POST /api/v1/analyses/{id}/start."""

    id: UUID
    status: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Status poll schema (B-027, FR-RESL-13)
# ---------------------------------------------------------------------------


class AnalysisStatusResponse(BaseModel):
    """200 response for GET /api/v1/analyses/{id}/status."""

    id: UUID
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Update schema (B-028, FR-UPLD-10)
# ---------------------------------------------------------------------------


class AnalysisUpdate(BaseModel):
    """Request body for PATCH /api/v1/analyses/{id}."""

    tags: list[str] | None = None


# ---------------------------------------------------------------------------
# Nested schemas for detail response (B-029)
# ---------------------------------------------------------------------------


class CoachingResultSchema(BaseModel):
    """Nested coaching result for AnalysisDetail."""

    structured_output_json: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RepMetricSchema(BaseModel):
    """Nested rep metric for AnalysisDetail."""

    rep_index: int
    start_frame: int
    end_frame: int
    confidence_score: float | None
    metrics_json: dict | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Detail and summary response schemas (B-029, FR-HIST-01)
# ---------------------------------------------------------------------------


class AnalysisDetail(BaseModel):
    """Full analysis detail including nested coaching result and rep metrics."""

    id: UUID
    status: str
    exercise_type: str
    exercise_variant: str
    confidence_score: float | None
    video_path: str | None
    annotated_video_path: str | None
    plot_path: str | None
    pdf_path: str | None
    tags: list[str] | None
    quality_gate_result: dict | None
    summary_json: dict | None
    created_at: datetime
    updated_at: datetime
    coaching_result: CoachingResultSchema | None = None
    rep_metrics: list[RepMetricSchema] = []

    model_config = {"from_attributes": True}


class AnalysisSummary(BaseModel):
    """Analysis list item — no nested relationships."""

    id: UUID
    status: str
    exercise_type: str
    exercise_variant: str
    confidence_score: float | None
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
