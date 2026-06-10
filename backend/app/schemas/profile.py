"""Pydantic v2 schemas for the user profile resource.

Requirements: FR-PROF-01 through FR-PROF-05
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

ExperienceLevel = Literal["beginner", "intermediate", "advanced"]
SexLiteral = Literal["male", "female", "prefer_not_to_say"]


class ProfileUpdate(BaseModel):
    """Request body for PUT /api/v1/profiles/me.

    Required fields: height_cm, weight_kg, age, experience_level (FR-PROF-02).
    Optional fields: arm_span_cm, femur_length_cm (FR-PROF-03).
    Experience level must be one of beginner/intermediate/advanced (FR-PROF-04).
    All numeric fields must be positive (>0).
    """

    height_cm: float = Field(..., gt=0, description="Height in centimetres")
    weight_kg: float = Field(..., gt=0, description="Weight in kilograms")
    age: int = Field(..., gt=0, description="Age in years")
    experience_level: ExperienceLevel = Field(
        ..., description="Training experience level"
    )
    arm_span_cm: Optional[float] = Field(
        default=None, gt=0, description="Arm span in centimetres (optional)"
    )
    femur_length_cm: Optional[float] = Field(
        default=None, gt=0, description="Femur length in centimetres (optional)"
    )
    sex: Optional[SexLiteral] = Field(
        default=None, description="Sex (optional) — used to match coaching evidence"
    )


class ProfileResponse(BaseModel):
    """Response schema for GET and PUT /api/v1/profiles/me."""

    id: UUID
    user_id: UUID
    height_cm: Optional[float]
    weight_kg: Optional[float]
    age: Optional[int]
    experience_level: Optional[str]
    arm_span_cm: Optional[float]
    femur_length_cm: Optional[float]
    sex: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
