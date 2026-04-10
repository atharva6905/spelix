"""Shared types for CV pipeline — confidence tiers and scoring.

Used by confidence.py, scoring.py, and pipeline.py. Zero imports from
other app.cv.* modules to prevent circular dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Confidence types (FR-CVPL-20 through FR-CVPL-25)
# ---------------------------------------------------------------------------


@dataclass
class ConfidenceResult:
    """Per-rep confidence breakdown across all five tiers."""

    rep_index: int
    tier3_frame_scores: list[float] = field(default_factory=list)
    tier4_frame_scores: list[float] = field(default_factory=list)
    tier5: float = 0.0
    label: str = "Very Low"


# ---------------------------------------------------------------------------
# Scoring types (FR-SCOR-01 through FR-SCOR-08)
# ---------------------------------------------------------------------------

BadgeSeverity = Literal["High", "Medium", "Low"]
ScoreDescriptor = Literal[
    "Elite", "Advanced", "Intermediate", "Needs Work", "Needs Attention"
]
DimensionName = Literal[
    "Movement Quality", "Technique", "Path & Balance", "Control"
]


@dataclass(frozen=True)
class BadgeResult:
    """A single issue badge tied to a scoring dimension (FR-SCOR-08)."""

    dimension: DimensionName
    issue_key: str
    severity: BadgeSeverity
    message: str


@dataclass(frozen=True)
class ScoreDimension:
    """One of the four scoring dimensions with its computed result."""

    internal_name: str          # "safety", "technique", "path_balance", "control"
    display_name: DimensionName
    score: float                # 1.0–10.0
    weight: float
    descriptor: ScoreDescriptor
    badges: tuple[BadgeResult, ...] = ()


@dataclass
class ScoreResult:
    """Complete scoring output for an analysis (FR-SCOR-05)."""

    dimensions: list[ScoreDimension] = field(default_factory=list)
    overall: float = 0.0
    overall_descriptor: ScoreDescriptor = "Needs Attention"

    def get_dimension(self, internal_name: str) -> ScoreDimension | None:
        """Look up a dimension by internal name (e.g. 'safety')."""
        for d in self.dimensions:
            if d.internal_name == internal_name:
                return d
        return None
