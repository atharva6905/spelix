"""Pydantic v2 schemas for the analyses resource.

Requirements: FR-UPLD-07, FR-UPLD-16, FR-UPLD-17
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
