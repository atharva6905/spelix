from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Only angle/metric thresholds surface to the UI — see plan Scope Boundaries.
# Non-angle sections (scoring_weights, phase_multipliers, confidence_landmark_weights,
# experience_tolerance, score_descriptors) are filtered out of the listing.
ALLOWED_SECTIONS: frozenset[str] = frozenset({"squat", "bench", "deadlift", "control"})

StatusLiteral = Literal["open", "resolved", "rejected"]


class ThresholdRow(BaseModel):
    """A single threshold entry as shown in the reviewer UI."""

    model_config = ConfigDict(from_attributes=True)

    section: str = Field(..., max_length=30)
    key: str = Field(..., max_length=100)
    value: float
    unit: str
    provenance_citation: str | None
    last_modified_by: str | None


class ThresholdListing(BaseModel):
    """Full listing grouped by section."""

    version: str
    sections: dict[str, list[ThresholdRow]]


class ThresholdFlagCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    section: Literal["squat", "bench", "deadlift", "control"]
    key: str = Field(..., min_length=1, max_length=100)
    proposed_value: float
    proposed_citation: str = Field(..., min_length=5, max_length=500)
    rationale: str = Field(..., min_length=20, max_length=2000)


class ThresholdFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reviewer_id: UUID
    section: str
    key: str
    current_value: float
    current_citation: str | None
    proposed_value: float
    proposed_citation: str
    rationale: str
    status: StatusLiteral
    resolution_note: str | None
    resolved_by: UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ThresholdFlagResolveAction(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: Literal["resolved", "rejected"]
    resolution_note: str | None = Field(default=None, max_length=2000)
