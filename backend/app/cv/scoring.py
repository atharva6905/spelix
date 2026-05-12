"""Form scoring system — ScoreComponent Protocol + four concrete scorers.

Requirements: FR-SCOR-01 through FR-SCOR-08

Uses Protocol (not ABC) — adding a 5th scorer requires zero base changes.
Linear penalty model: start at 10.0, subtract penalties per threshold violation,
clamp to [1.0, 10.0].

Internal name "safety" maps to DB column form_score_safety.
User-facing display_name is "Movement Quality" (ADR-009 — never "injury risk"
or "safety" in user-facing strings).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.config import ThresholdConfig
from app.cv.types import (
    BadgeResult,
    DimensionName,
    ScoreDescriptor,
    ScoreDimension,
    ScoreResult,
)


# ---------------------------------------------------------------------------
# ScoreComponent Protocol (FR-SCOR-06)
# ---------------------------------------------------------------------------


@runtime_checkable
class ScoreComponent(Protocol):
    """Protocol satisfied by all four concrete scorers and any future additions.

    Adding a 5th scorer requires implementing this interface — no changes to
    OverallFormScore or any existing class.
    """

    weight: float
    display_name: DimensionName
    internal_name: str

    def compute(
        self,
        metrics: dict[str, float],
        bar_path: dict | None,
        cfg: ThresholdConfig,
        exercise_type: str,
    ) -> tuple[float, list[BadgeResult]]:
        """Return (raw_score, badges). raw_score is clamped by caller."""
        ...


# ---------------------------------------------------------------------------
# score_descriptor (FR-SCOR-07)
# ---------------------------------------------------------------------------


def score_descriptor(score: float, cfg: ThresholdConfig) -> ScoreDescriptor:
    """Map a numeric score to its descriptor label using configured thresholds."""
    if score >= cfg.get("score_descriptors", "elite_min"):
        return "Elite"
    if score >= cfg.get("score_descriptors", "advanced_min"):
        return "Advanced"
    if score >= cfg.get("score_descriptors", "intermediate_min"):
        return "Intermediate"
    if score >= cfg.get("score_descriptors", "needs_work_min"):
        return "Needs Work"
    return "Needs Attention"


# ---------------------------------------------------------------------------
# SafetyScore (FR-SCOR-01)
# ---------------------------------------------------------------------------


class SafetyScore:
    """Movement Quality scorer — penalises threshold violations in key joints.

    Internal name: "safety" (DB column: form_score_safety).
    User-facing display: "Movement Quality".
    Weight: 0.40.
    """

    weight: float = 0.40
    display_name: DimensionName = "Movement Quality"
    internal_name: str = "safety"

    def compute(
        self,
        metrics: dict[str, float],
        bar_path: dict | None,
        cfg: ThresholdConfig,
        exercise_type: str,
    ) -> tuple[float, list[BadgeResult]]:
        score = 10.0
        badges: list[BadgeResult] = []

        if exercise_type == "squat":
            score, badges = self._score_squat(score, badges, metrics, cfg)
        elif exercise_type == "deadlift":
            score, badges = self._score_deadlift(score, badges, metrics, cfg)
        elif exercise_type == "bench":
            score, badges = self._score_bench(score, badges, metrics, cfg)

        # Confidence cap: if confidence < 0.50 cap at 5.0
        confidence = metrics.get("confidence_score", 1.0)
        if confidence < 0.50:
            score = min(score, 5.0)

        return score, badges

    def _score_squat(
        self,
        score: float,
        badges: list[BadgeResult],
        metrics: dict[str, float],
        cfg: ThresholdConfig,
    ) -> tuple[float, list[BadgeResult]]:
        torso_lean = metrics.get("torso_lean")
        if torso_lean is not None:
            caution = cfg.get("squat", "torso_lean_caution_deg")
            high = cfg.get("squat", "torso_lean_high_deg")
            if torso_lean > high:
                score -= 3.0
                badges.append(
                    BadgeResult(
                        dimension="Movement Quality",
                        issue_key="torso_lean_high",
                        severity="High",
                        message=(
                            f"Torso lean {torso_lean:.0f}° exceeds safe range "
                            f"(>{high:.0f}°). Focus on an upright torso."
                        ),
                    )
                )
            elif torso_lean > caution:
                score -= 1.5
                badges.append(
                    BadgeResult(
                        dimension="Movement Quality",
                        issue_key="torso_lean_caution",
                        severity="Medium",
                        message=(
                            f"Torso lean {torso_lean:.0f}° is elevated "
                            f"(caution >{caution:.0f}°). Consider a more upright position."
                        ),
                    )
                )

        knee_angle_at_depth = metrics.get("knee_angle_at_depth")
        if knee_angle_at_depth is not None:
            min_knee = cfg.get("squat", "knee_angle_at_depth_min_deg")
            if knee_angle_at_depth < min_knee:
                score -= 2.0
                badges.append(
                    BadgeResult(
                        dimension="Movement Quality",
                        issue_key="knee_angle_at_depth_low",
                        severity="High",
                        message=(
                            f"Knee angle at depth {knee_angle_at_depth:.0f}° is very acute "
                            f"(<{min_knee:.0f}°). Check knee tracking and ankle mobility."
                        ),
                    )
                )

        return score, badges

    def _score_deadlift(
        self,
        score: float,
        badges: list[BadgeResult],
        metrics: dict[str, float],
        cfg: ThresholdConfig,
    ) -> tuple[float, list[BadgeResult]]:
        torso_lean = metrics.get("torso_lean_at_start", metrics.get("torso_lean"))
        if torso_lean is not None:
            caution = cfg.get("deadlift", "torso_lean_caution_deg")
            high = cfg.get("deadlift", "torso_lean_high_deg")
            if torso_lean > high:
                score -= 3.0
                badges.append(
                    BadgeResult(
                        dimension="Movement Quality",
                        issue_key="torso_lean_high",
                        severity="High",
                        message=(
                            f"Torso lean {torso_lean:.0f}° indicates excessive lumbar loading "
                            f"(>{high:.0f}°). Focus on maintaining a neutral spine."
                        ),
                    )
                )
            elif torso_lean > caution:
                score -= 1.5
                badges.append(
                    BadgeResult(
                        dimension="Movement Quality",
                        issue_key="torso_lean_caution",
                        severity="Medium",
                        message=(
                            f"Torso lean {torso_lean:.0f}° is elevated "
                            f"(caution >{caution:.0f}°). Work on maintaining a neutral spine."
                        ),
                    )
                )

        hip_angle = metrics.get("hip_angle_at_bottom")
        if hip_angle is not None:
            min_hip = cfg.get("deadlift", "hip_angle_at_bottom_min_deg")
            max_hip = cfg.get("deadlift", "hip_angle_at_bottom_max_deg")
            if hip_angle < min_hip or hip_angle > max_hip:
                score -= 2.0
                badges.append(
                    BadgeResult(
                        dimension="Movement Quality",
                        issue_key="hip_angle_extreme",
                        severity="High",
                        message=(
                            f"Hip angle at bottom {hip_angle:.0f}° is outside the optimal "
                            f"range [{min_hip:.0f}°–{max_hip:.0f}°]."
                        ),
                    )
                )

        return score, badges

    def _score_bench(
        self,
        score: float,
        badges: list[BadgeResult],
        metrics: dict[str, float],
        cfg: ThresholdConfig,
    ) -> tuple[float, list[BadgeResult]]:
        elbow_angle = metrics.get("elbow_angle_at_bottom")
        if elbow_angle is not None:
            min_elbow = cfg.get("bench", "elbow_angle_at_bottom_min_deg")
            max_elbow = cfg.get("bench", "elbow_angle_at_bottom_max_deg")
            if elbow_angle < min_elbow or elbow_angle > max_elbow:
                score -= 2.0
                badges.append(
                    BadgeResult(
                        dimension="Movement Quality",
                        issue_key="elbow_angle_extreme",
                        severity="High",
                        message=(
                            f"Elbow angle at bottom {elbow_angle:.0f}° is outside the "
                            f"recommended range [{min_elbow:.0f}°–{max_elbow:.0f}°]."
                        ),
                    )
                )

        shoulder_angle = metrics.get("shoulder_angle_at_bottom")
        if shoulder_angle is not None:
            max_shoulder = cfg.get("bench", "shoulder_angle_at_bottom_max_deg")
            if shoulder_angle > max_shoulder:
                score -= 2.0
                badges.append(
                    BadgeResult(
                        dimension="Movement Quality",
                        issue_key="shoulder_angle_high",
                        severity="High",
                        message=(
                            f"Shoulder angle at bottom {shoulder_angle:.0f}° exceeds "
                            f"recommended maximum ({max_shoulder:.0f}°). "
                            "Consider reducing shoulder opening angle for better stability."
                        ),
                    )
                )

        return score, badges


# ---------------------------------------------------------------------------
# TechniqueScore (FR-SCOR-02)
# ---------------------------------------------------------------------------


class TechniqueScore:
    """Technique scorer — evaluates depth, timing, and rep consistency.

    Weight: 0.30.
    """

    weight: float = 0.30
    display_name: DimensionName = "Technique"
    internal_name: str = "technique"

    def compute(
        self,
        metrics: dict[str, float],
        bar_path: dict | None,
        cfg: ThresholdConfig,
        exercise_type: str,
    ) -> tuple[float, list[BadgeResult]]:
        score = 10.0
        badges: list[BadgeResult] = []

        if exercise_type == "squat":
            score, badges = self._score_squat(score, badges, metrics, cfg)
        elif exercise_type == "deadlift":
            score, badges = self._score_deadlift(score, badges, metrics, cfg)
        elif exercise_type == "bench":
            score, badges = self._score_bench(score, badges, metrics, cfg)

        # Multi-rep consistency: high std dev on depth angle → penalty
        depth_std = metrics.get("depth_angle_std")
        if depth_std is not None and depth_std > 10.0:
            penalty = min(3.0, (depth_std - 10.0) * 0.2)
            score -= penalty
            badges.append(
                BadgeResult(
                    dimension="Technique",
                    issue_key="rep_consistency_low",
                    severity="Medium",
                    message=(
                        f"Rep-to-rep depth variation is high (std {depth_std:.1f}°). "
                        "Work on consistent depth across all reps."
                    ),
                )
            )

        return score, badges

    def _score_squat(
        self,
        score: float,
        badges: list[BadgeResult],
        metrics: dict[str, float],
        cfg: ThresholdConfig,
    ) -> tuple[float, list[BadgeResult]]:
        depth_angle = metrics.get("depth_angle")
        if depth_angle is not None:
            parallel = cfg.get("squat", "depth_parallel_hip_angle_deg")
            if depth_angle > parallel:
                # Above parallel — depth not achieved
                # Use 0.15 per degree so a 20° miss (110°) → 3.0 penalty (score 7.0)
                penalty = min(4.0, (depth_angle - parallel) * 0.15)
                score -= penalty
                badges.append(
                    BadgeResult(
                        dimension="Technique",
                        issue_key="squat_depth_insufficient",
                        severity="Medium",
                        message=(
                            f"Squat depth {depth_angle:.0f}° does not reach parallel "
                            f"({parallel:.0f}°). Aim to reach or pass parallel."
                        ),
                    )
                )

        torso_lean = metrics.get("torso_lean")
        if torso_lean is not None:
            caution = cfg.get("squat", "torso_lean_caution_deg")
            if torso_lean > caution:
                score -= 1.0
                badges.append(
                    BadgeResult(
                        dimension="Technique",
                        issue_key="torso_lean_technique",
                        severity="Low",
                        message=(
                            f"Torso lean {torso_lean:.0f}° affects technique efficiency."
                        ),
                    )
                )

        return score, badges

    def _score_deadlift(
        self,
        score: float,
        badges: list[BadgeResult],
        metrics: dict[str, float],
        cfg: ThresholdConfig,
    ) -> tuple[float, list[BadgeResult]]:
        hip_angle = metrics.get("hip_angle_at_bottom")
        if hip_angle is not None:
            hip_min = cfg.get("deadlift", "hip_hinge_min_deg")
            if hip_angle < hip_min:
                score -= 2.0
                badges.append(
                    BadgeResult(
                        dimension="Technique",
                        issue_key="hip_hinge_insufficient",
                        severity="Medium",
                        message=(
                            f"Hip angle at bottom {hip_angle:.0f}° indicates insufficient "
                            f"hip hinge (minimum {hip_min:.0f}°)."
                        ),
                    )
                )

        return score, badges

    def _score_bench(
        self,
        score: float,
        badges: list[BadgeResult],
        metrics: dict[str, float],
        cfg: ThresholdConfig,
    ) -> tuple[float, list[BadgeResult]]:
        elbow_angle = metrics.get("elbow_angle_at_bottom")
        if elbow_angle is not None:
            target_min = 70.0
            target_max = 90.0
            if not (target_min <= elbow_angle <= target_max):
                score -= 1.5
                badges.append(
                    BadgeResult(
                        dimension="Technique",
                        issue_key="elbow_angle_off_target",
                        severity="Medium",
                        message=(
                            f"Elbow angle at bottom {elbow_angle:.0f}° is outside the "
                            f"target range [{target_min:.0f}°–{target_max:.0f}°]."
                        ),
                    )
                )

        # NOTE: elbow_flare_deg is not currently produced by metric_extraction.py
        # (requires frontal-plane camera). Branch retained for MC/DC test coverage
        # and future multi-camera support. See cv-dimension-audit-2026-05-11.md.
        elbow_flare = metrics.get("elbow_flare_deg")
        if elbow_flare is not None:
            caution = cfg.get("bench", "elbow_flare_caution_deg")
            high = cfg.get("bench", "elbow_flare_high_deg")
            if elbow_flare > high:
                score -= 2.0
                badges.append(
                    BadgeResult(
                        dimension="Technique",
                        issue_key="elbow_flare_high",
                        severity="High",
                        message=f"Elbow flare {elbow_flare:.0f}° is excessive (>{high:.0f}°).",
                    )
                )
            elif elbow_flare > caution:
                score -= 1.0
                badges.append(
                    BadgeResult(
                        dimension="Technique",
                        issue_key="elbow_flare_caution",
                        severity="Medium",
                        message=(
                            f"Elbow flare {elbow_flare:.0f}° is elevated "
                            f"(caution >{caution:.0f}°)."
                        ),
                    )
                )

        return score, badges


# ---------------------------------------------------------------------------
# PathBalanceScore (FR-SCOR-03)
# ---------------------------------------------------------------------------


class PathBalanceScore:
    """Path & Balance scorer — evaluates bar path consistency and lateral deviation.

    Returns 5.0 with an "insufficient data" badge when bar_path is None.
    Weight: 0.20.
    """

    weight: float = 0.20
    display_name: DimensionName = "Path & Balance"
    internal_name: str = "path_balance"

    def compute(
        self,
        metrics: dict[str, float],
        bar_path: dict | None,
        cfg: ThresholdConfig,
        exercise_type: str,
    ) -> tuple[float, list[BadgeResult]]:
        if bar_path is None:
            return (
                5.0,
                [
                    BadgeResult(
                        dimension="Path & Balance",
                        issue_key="bar_path_no_data",
                        severity="Low",
                        message=(
                            "Insufficient data to evaluate bar path. "
                            "Ensure the barbell is visible throughout the lift."
                        ),
                    )
                ],
            )

        score = 10.0
        badges: list[BadgeResult] = []

        path_consistency = bar_path.get("path_consistency", 1.0)
        # penalty = (1.0 - consistency) * 8.0  →  perfect=0 penalty, 0→8 penalty
        # penalty = (1.0 - consistency) * 11.0
        # At consistency=0.98 → penalty 0.22 → score 9.78 (≥9.0 pass)
        # At consistency=0.7  → penalty 3.3  → score 6.7  (<7.0 pass)
        consistency_penalty = (1.0 - path_consistency) * 11.0
        score -= consistency_penalty
        if consistency_penalty > 1.0:
            sev = "High" if consistency_penalty >= 4.0 else "Medium"
            badges.append(
                BadgeResult(
                    dimension="Path & Balance",
                    issue_key="path_consistency_low",
                    severity=sev,
                    message=(
                        f"Bar path consistency is {path_consistency:.0%}. "
                        "Aim for a more consistent movement path."
                    ),
                )
            )

        lateral_dev = bar_path.get("lateral_deviation_px", 0.0)
        if lateral_dev > 0.05:
            lat_penalty = min(2.0, (lateral_dev - 0.05) * 10.0)
            score -= lat_penalty
            badges.append(
                BadgeResult(
                    dimension="Path & Balance",
                    issue_key="lateral_deviation_high",
                    severity="Medium",
                    message=(
                        f"Bar forward/backward deviation {lateral_dev:.2f} (normalised) is elevated. "
                        "Keep the bar over midfoot throughout the lift."
                    ),
                )
            )

        return score, badges


# ---------------------------------------------------------------------------
# ControlScore (FR-SCOR-04)
# ---------------------------------------------------------------------------


class ControlScore:
    """Control scorer — evaluates eccentric tempo, rep consistency, and lockout.

    Weight: 0.10.
    """

    weight: float = 0.10
    display_name: DimensionName = "Control"
    internal_name: str = "control"

    def compute(
        self,
        metrics: dict[str, float],
        bar_path: dict | None,
        cfg: ThresholdConfig,
        exercise_type: str,
    ) -> tuple[float, list[BadgeResult]]:
        score = 10.0
        badges: list[BadgeResult] = []

        descent = metrics.get("descent_duration_s")
        if descent is not None:
            caution_s = cfg.get("control", "descent_duration_caution_s")  # 1.5
            high_s = cfg.get("control", "descent_duration_high_s")  # 1.0
            if descent < high_s:
                score -= 3.0
                badges.append(
                    BadgeResult(
                        dimension="Control",
                        issue_key="descent_too_fast_high",
                        severity="High",
                        message=(
                            f"Descent duration {descent:.1f}s is very fast "
                            f"(<{high_s:.1f}s). Slow the eccentric to build control."
                        ),
                    )
                )
            elif descent < caution_s:
                score -= 2.0
                badges.append(
                    BadgeResult(
                        dimension="Control",
                        issue_key="descent_too_fast_caution",
                        severity="High",
                        message=(
                            f"Descent duration {descent:.1f}s is fast "
                            f"(<{caution_s:.1f}s). Aim for a slower, controlled descent."
                        ),
                    )
                )

        rep_std = metrics.get("rep_duration_std")
        if rep_std is not None:
            std_caution = cfg.get("control", "rep_duration_std_caution_s")
            if rep_std > std_caution:
                score -= 1.0
                badges.append(
                    BadgeResult(
                        dimension="Control",
                        issue_key="rep_duration_inconsistent",
                        severity="Medium",
                        message=(
                            f"Rep duration variation {rep_std:.2f}s is high "
                            f"(>{std_caution:.1f}s). Aim for consistent rep tempo."
                        ),
                    )
                )

        # Deadlift lockout check
        if exercise_type == "deadlift":
            lockout_angle = metrics.get("knee_angle_at_lockout")
            if lockout_angle is not None:
                min_lockout = cfg.get("deadlift", "knee_angle_at_lockout_min_deg")
                if lockout_angle < min_lockout:
                    score -= 1.5
                    badges.append(
                        BadgeResult(
                            dimension="Control",
                            issue_key="lockout_incomplete",
                            severity="Medium",
                            message=(
                                f"Knee angle at lockout {lockout_angle:.0f}° indicates "
                                f"incomplete lockout (<{min_lockout:.0f}°). "
                                "Fully extend hips and knees at the top."
                            ),
                        )
                    )

        return score, badges


# ---------------------------------------------------------------------------
# OverallFormScore (FR-SCOR-05)
# ---------------------------------------------------------------------------


class OverallFormScore:
    """Computes the weighted composite score across all ScoreComponent instances.

    Accepts any list of objects satisfying the ScoreComponent Protocol — the
    default four, or an extended set with additional scorers.
    """

    def __init__(self, components: list[ScoreComponent] | None = None) -> None:
        self._components: list[ScoreComponent] = components or [
            SafetyScore(),
            TechniqueScore(),
            PathBalanceScore(),
            ControlScore(),
        ]

    def compute(
        self,
        metrics: dict[str, float],
        bar_path: dict | None,
        cfg: ThresholdConfig,
        exercise_type: str,
    ) -> ScoreResult:
        """Compute all dimensions and return a ScoreResult with weighted composite."""
        dimensions: list[ScoreDimension] = []
        weighted_sum = 0.0

        for comp in self._components:
            raw_score, badges = comp.compute(metrics, bar_path, cfg, exercise_type)
            clamped = max(1.0, min(10.0, raw_score))
            weighted_sum += clamped * comp.weight
            dimensions.append(
                ScoreDimension(
                    internal_name=comp.internal_name,
                    display_name=comp.display_name,
                    score=round(clamped, 2),
                    weight=comp.weight,
                    descriptor=score_descriptor(clamped, cfg),
                    badges=tuple(badges),
                )
            )

        overall = max(1.0, min(10.0, round(weighted_sum, 2)))
        return ScoreResult(
            dimensions=dimensions,
            overall=overall,
            overall_descriptor=score_descriptor(overall, cfg),
        )
