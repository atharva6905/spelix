"""Pydantic v2 schemas for AI coaching output.

Requirements: FR-RESL-03, FR-AICP-03, FR-AICP-06, Appendix D (B-023)

These schemas are enforced by the instructor library when calling Claude Sonnet
4.6. The structured_output_json JSONB column in coaching_results stores the
serialised form of CoachingOutput. Phase 1 extends CoachingOutput additively —
all new fields are Optional with defaults so Phase 0 JSONB blobs continue to
deserialise without error.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    """A single form issue identified in the coaching analysis.

    Attributes
    ----------
    rep_number:
        The rep during which the issue was observed (1-indexed).
    joint:
        The joint or body segment where the deviation occurred
        (e.g. "Left knee", "Lumbar spine").
    description:
        Specific, observable description of the deviation. Must reference
        the movement phase. Never speculate beyond what is observable.
    severity:
        Triage level: "High" for issues requiring immediate attention,
        "Medium" for technique improvements, "Low" for minor refinements.
        High-severity issues must appear first in the issues list.
    """

    rep_number: int = Field(ge=1, description="Rep number where the issue occurred (1-indexed).")
    joint: str = Field(min_length=1, description="Affected joint or body segment.")
    description: str = Field(
        min_length=1,
        description=(
            "Observable description of the deviation including movement phase. "
            "No speculation about causes outside the video."
        ),
    )
    severity: Literal["High", "Medium", "Low"] = Field(
        description="Triage severity. High issues must be listed first."
    )


class Citation(BaseModel):
    """Research citation supporting a coaching recommendation (FR-AICP-06)."""

    title: str
    authors: list[str]
    year: int
    doi: str | None = None


class CoachingOutput(BaseModel):
    """Full structured coaching output from the Phase 0/1 LLM call.

    Stored in coaching_results.structured_output_json as JSONB.
    Enforced via instructor + Pydantic v2 schema validation during the
    Anthropic API call.

    Phase 1 additions (FR-AICP-03, FR-AICP-06): recommended_cues, citations,
    confidence_level, safety_warnings, dimension_addressed. All are Optional
    with defaults so Phase 0 JSONB blobs continue to deserialise.

    Attributes
    ----------
    summary:
        Two-sentence overall assessment of the session.
    strengths:
        Two to three positive observations about the session.
    issues:
        Ordered list of form deviations. High-severity issues first.
    correction_plan:
        Three to five specific, actionable coaching cues.
    disclaimer:
        Mandatory disclaimer verbatim — must match exactly:
        "This feedback is for educational purposes only and is not a
        substitute for in-person coaching or medical advice."
    raw_prompt_tokens:
        Token count of the input prompt (logged for cost tracking).
    raw_completion_tokens:
        Token count of the completion (logged for cost tracking).
    recommended_cues:
        Recommended verbal/tactile cues for the lifter (Phase 1, FR-AICP-03).
    citations:
        Research citations supporting recommendations (Phase 1, FR-AICP-06).
    confidence_level:
        Overall confidence in the coaching assessment (Phase 1).
    safety_warnings:
        Safety-related observations requiring immediate attention (Phase 1).
    dimension_addressed:
        Primary scoring dimension this coaching addresses (Phase 1).
    """

    summary: str = Field(
        min_length=1,
        description="Two-sentence overall assessment of the session.",
    )
    strengths: list[str] = Field(
        min_length=1,
        description="Two to three positive observations.",
    )
    issues: list[Issue] = Field(
        default_factory=list,
        description="Ordered list of form deviations. High severity first.",
    )
    correction_plan: list[str] = Field(
        min_length=1,
        description="Three to five specific, actionable coaching cues.",
    )
    disclaimer: str = Field(
        description=(
            'Must be verbatim: "This feedback is for educational purposes only '
            'and is not a substitute for in-person coaching or medical advice."'
        ),
    )
    raw_prompt_tokens: int = Field(ge=0, description="Input token count for cost tracking.")
    raw_completion_tokens: int = Field(ge=0, description="Output token count for cost tracking.")

    # Phase 1 additions (FR-AICP-03, FR-AICP-06)
    recommended_cues: list[str] = Field(
        default_factory=list,
        description="Recommended verbal/tactile cues for the lifter.",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Research citations supporting recommendations.",
    )
    confidence_level: Literal["High", "Moderate", "Low", "Very Low"] | None = Field(
        default=None,
        description="Overall confidence in the coaching assessment.",
    )
    safety_warnings: list[str] = Field(
        default_factory=list,
        description="Safety-related warnings requiring immediate attention.",
    )
    dimension_addressed: Literal[
        "Movement Quality", "Technique", "Path & Balance", "Control"
    ] | None = Field(
        default=None,
        description="Primary scoring dimension this coaching addresses.",
    )
