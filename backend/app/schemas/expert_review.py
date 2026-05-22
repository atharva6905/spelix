"""Pydantic v2 schemas for the Expert Validation System.

FR-EXPV-02: Expert review queue items.
FR-EXPV-03: Anonymized analysis detail (no user_id).
FR-EXPV-04: Structured annotation submission.
FR-EXPV-07: Golden dataset labeling.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnnotationCreate(BaseModel):
    """Expert annotation submission (FR-EXPV-04).

    coaching_quality_score: 1.0–10.0 scale.
    issues_identified: freeform JSON object describing issues found.
    cited_sources: list of source references used by the reviewer.
    is_golden_label: if True, marks the analysis as a golden dataset entry (FR-EXPV-07).
    """

    issues_identified: dict[str, Any] = Field(default_factory=dict)
    coaching_quality_score: float | None = Field(default=None, ge=1.0, le=10.0)
    movement_advice_accurate: bool | None = None
    engagement_advice_accurate: bool | None = None
    suggested_corrections: str | None = None
    cited_sources: list[dict[str, Any]] = Field(default_factory=list)
    is_golden_label: bool = False


class AnnotationResponse(BaseModel):
    """Expert annotation read model."""

    id: uuid.UUID
    analysis_id: uuid.UUID
    annotator_id: uuid.UUID
    issues_identified: dict[str, Any]
    coaching_quality_score: float | None
    movement_advice_accurate: bool | None
    engagement_advice_accurate: bool | None
    suggested_corrections: str | None
    cited_sources: list[dict[str, Any]]
    is_golden_label: bool
    created_at: datetime
    updated_at: datetime


class ExpertQueueItem(BaseModel):
    """Queue item for expert review (FR-EXPV-02).

    Anonymized — no user_id field.
    """

    analysis_id: uuid.UUID
    exercise_type: str
    exercise_variant: str | None
    confidence_score: float | None
    form_score_overall: float | None
    flagged_for_review: bool
    created_at: datetime
    annotation_count: int = 0


class ExpertAnalysisDetail(BaseModel):
    """Anonymized analysis detail for expert review (FR-EXPV-03).

    Intentionally excludes user_id and all PII fields.
    """

    id: uuid.UUID
    exercise_type: str
    exercise_variant: str | None
    confidence_score: float | None
    form_score_safety: float | None
    form_score_technique: float | None
    form_score_path_balance: float | None
    form_score_control: float | None
    form_score_overall: float | None
    summary_json: dict[str, Any] | None
    quality_gate_result: dict[str, Any] | None
    coaching_result: dict[str, Any] | None
    rep_metrics: list[dict[str, Any]]
    retrieval_context: dict[str, Any] | None
    eval_scores: dict[str, Any] | None
    flagged_for_review: bool
    is_golden_dataset: bool
    created_at: datetime
    annotated_video_url: str | None = None


class AdminExpertQueueItem(BaseModel):
    """Admin view of expert review queue (FR-ADMN-07)."""

    analysis_id: uuid.UUID
    exercise_type: str
    exercise_variant: str | None
    confidence_score: float | None
    flagged_for_review: bool
    created_at: datetime
    annotation_count: int = 0
    latest_annotation_at: datetime | None = None


class AdminExpertQueueStats(BaseModel):
    """Stats for admin expert queue overview."""

    total_flagged: int
    total_annotated: int
    golden_dataset_count: int


class GoldenLabelAction(BaseModel):
    """Schema for golden dataset labeling (FR-EXPV-07)."""

    is_golden_dataset: bool


class SagittalMetricRegistryEntry(BaseModel):
    """One row in the sagittal metrics registry response (Session 3,
    L2-SAGITTAL-INFRA-01 / ADR-SAGITTAL-METRICS-REGISTRY)."""

    key_name: str
    display_label: str
    unit: str
    description: str
    exercise_applicability: list[str]
    computed_yet: bool
    in_scoring: bool


class SagittalMetricRegistryResponse(BaseModel):
    """Response envelope for GET /api/v1/expert/sagittal-metrics-registry."""

    entries: list[SagittalMetricRegistryEntry]
