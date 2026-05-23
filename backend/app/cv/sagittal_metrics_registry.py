"""Sagittal-view metrics registry (Session 3, L2-SAGITTAL-INFRA-01).

Single source of truth for the 16 sagittal-view metrics that Sessions 4-7
will populate. Backend serves this list via
``GET /api/v1/expert/sagittal-metrics-registry``; the frontend
``<UnvalidatedMetricsPanel />`` renders the rows.

Keys here are FINAL -- Sessions 4-7 write to these exact JSONB key names in
``rep_metrics.metrics``. Renaming a key is a breaking change requiring a
data migration.

See ADR-SAGITTAL-METRICS-REGISTRY and design Section 4 of
``docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md``.
"""
from __future__ import annotations

from dataclasses import dataclass

# Supported exercises (matches user_profile + analyses constraints).
EXERCISE_ENUM_VALUES: frozenset[str] = frozenset({"squat", "bench", "deadlift"})


@dataclass(frozen=True)
class SagittalMetricEntry:
    """Immutable description of one sagittal-view metric.

    All 16 entries share this shape so the frontend can render them
    uniformly. Threshold values are NOT included -- those live in
    ``config/thresholds_v1.json`` and are validated post-onboarding via
    FR-EXPV-08.
    """

    key_name: str
    """The exact JSONB key written into ``rep_metrics.metrics`` by the
    Session 4-7 extractor."""

    display_label: str
    """Human-readable label shown in the expert panel column header."""

    unit: str
    """Unit string. Empty for categorical / classification metrics."""

    description: str
    """One-sentence description rendered as the row tooltip. Must avoid
    'injury risk' / 'injury prevention' / 'safety score' (project rule)."""

    exercise_applicability: frozenset[str]
    """Which exercises this metric applies to. Subset of EXERCISE_ENUM_VALUES."""

    computed_yet: bool
    """False after Session 3 (no extractor exists). Sessions 4-7 flip
    per-metric. Read by the panel to render 'Not yet computed' badges."""

    in_scoring: bool
    """False after Session 3. Session 4 flips ``depth_classification`` and
    ``ecc_con_ratio``. Other 14 stay False until expert-validated."""


# Aliases for brevity below.
_SQ = frozenset({"squat"})
_BN = frozenset({"bench"})
_DL = frozenset({"deadlift"})
_SQ_DL = frozenset({"squat", "deadlift"})
_ALL = frozenset({"squat", "bench", "deadlift"})


SAGITTAL_METRICS_REGISTRY: frozenset[SagittalMetricEntry] = frozenset({
    # ------------------------------------------------------------------ #
    # Session 4 metrics (4)
    # ------------------------------------------------------------------ #
    SagittalMetricEntry(
        key_name="depth_classification",
        display_label="Depth Classification",
        unit="",  # categorical
        description=(
            "Categorical relabel of squat depth: above_parallel, at_parallel, "
            "or below_parallel. Derived from existing depth_angle."
        ),
        exercise_applicability=_SQ,
        computed_yet=True,
        in_scoring=True,
    ),
    SagittalMetricEntry(
        key_name="ecc_con_ratio",
        display_label="Eccentric / Concentric Ratio",
        unit="ratio",
        description=(
            "Per-rep descent_duration_s divided by ascent_duration_s. "
            "Session mean drives the Control score."
        ),
        exercise_applicability=_ALL,
        computed_yet=True,
        in_scoring=True,
    ),
    SagittalMetricEntry(
        key_name="pause_duration_s",
        display_label="Pause Duration",
        unit="s",
        description=(
            "Time spent within +/-2 degrees of the rep-bottom angle, per rep. "
            "Computed from rep-detection segment boundaries."
        ),
        exercise_applicability=_ALL,
        computed_yet=True,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="lockout_torso_lean_deg",
        display_label="Lockout Torso Lean",
        unit="deg",
        description=(
            "Torso-vertical angle at the rep peak-angle (lockout) frame, "
            "per rep. Zero degrees is upright."
        ),
        exercise_applicability=_SQ_DL,
        computed_yet=True,
        in_scoring=False,
    ),

    # ------------------------------------------------------------------ #
    # Session 5 metrics (8 keys, 7 design entries)
    # ------------------------------------------------------------------ #
    SagittalMetricEntry(
        key_name="ankle_dorsiflexion_deg",
        display_label="Ankle Dorsiflexion",
        unit="deg",
        description=(
            "Angle at the ankle between the knee-vector and foot-index-vector "
            "at rep bottom. 90 minus this is dorsiflexion magnitude. Companion "
            "boolean heel_rise_flag written alongside this key in rep_metrics."
        ),
        exercise_applicability=_SQ,
        computed_yet=True,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="wrist_alignment_deg",
        display_label="Wrist Alignment",
        unit="deg",
        description=(
            "Sagittal-plane wrist-elbow stacking angle at bench bottom. "
            "Positive values mean the wrist is anterior to the elbow."
        ),
        exercise_applicability=_BN,
        computed_yet=True,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="bar_touch_height_pct",
        display_label="Bar Touch Height",
        unit="ratio",
        description=(
            "Bench bar-touch y relative to the shoulder-hip span. "
            "0.0 means touching at shoulder level, 1.0 at hip level."
        ),
        exercise_applicability=_BN,
        computed_yet=True,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="setup_shoulder_x_offset",
        display_label="Setup Shoulder Offset",
        unit="ratio",
        description=(
            "Deadlift shoulder-x offset from wrist-x at the first lift frame, "
            "normalized by forearm length. Positive = shoulders over the bar."
        ),
        exercise_applicability=_DL,
        computed_yet=True,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="shin_angle_deg",
        display_label="Shin Angle",
        unit="deg",
        description=(
            "Sagittal-plane shin-vertical angle at squat rep bottom. "
            "Zero is vertical shin; positive is forward lean."
        ),
        exercise_applicability=_SQ,
        computed_yet=True,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="setup_knee_angle_deg",
        display_label="Setup Knee Angle",
        unit="deg",
        description=(
            "Deadlift knee angle (hip-knee-ankle) at the first lift frame."
        ),
        exercise_applicability=_DL,
        computed_yet=True,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="arch_deg",
        display_label="Arch Angle",
        unit="deg",
        description=(
            "Mean shoulder-hip vertical separation across non-rep frames, "
            "expressed as a sagittal angle. Positive = hips higher than "
            "shoulders (bench arch)."
        ),
        exercise_applicability=_BN,
        computed_yet=True,
        in_scoring=False,
    ),

    # ------------------------------------------------------------------ #
    # Session 6 metrics (2)
    # ------------------------------------------------------------------ #
    SagittalMetricEntry(
        key_name="bar_to_hip_distance",
        display_label="Bar-to-Hip Distance",
        unit="ratio",
        description=(
            "Deadlift bar-x minus hip-x at four phase frames "
            "(setup / liftoff / knee_pass / lockout), normalized by "
            "shoulder-to-hip distance at setup. JSONB value is a dict."
        ),
        exercise_applicability=_DL,
        computed_yet=False,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="shoulder_protraction_proxy_px",
        display_label="Shoulder Protraction Proxy",
        unit="ratio",
        description=(
            "Bench shoulder-x drift from setup to rep bottom, normalized by "
            "shoulder-to-hip distance. Proxy -- actual scapular protraction "
            "requires a frontal-plane camera."
        ),
        exercise_applicability=_BN,
        computed_yet=False,
        in_scoring=False,
    ),

    # ------------------------------------------------------------------ #
    # Session 7 metrics (3)
    # ------------------------------------------------------------------ #
    SagittalMetricEntry(
        key_name="lumbar_flexion_proxy_delta_deg",
        display_label="Lumbar Flexion Proxy (Delta)",
        unit="deg",
        description=(
            "Composite trunk-flexion proxy: shoulder-hip-vertical angle at "
            "rep bottom minus the same angle at the standing baseline. "
            "Not lumbar-isolated -- see ADR-LUMBAR-FLEXION-PROXY-NAMING."
        ),
        exercise_applicability=_SQ_DL,
        computed_yet=False,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="bar_path_classification",
        display_label="Bar Path Classification",
        unit="",  # categorical
        description=(
            "Bench bar-x trajectory shape: vertical, j_curve, or drift. "
            "Heuristic v0 -- expect post-onboarding refinement."
        ),
        exercise_applicability=_BN,
        computed_yet=False,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="technique_consistency_std",
        display_label="Technique Consistency",
        unit="deg",
        description=(
            "Standard deviation of a chosen technique metric across reps "
            "(depth_angle for squat, lockout_torso_lean_deg for deadlift). "
            "Lower = more consistent."
        ),
        exercise_applicability=_SQ_DL,
        computed_yet=False,
        in_scoring=False,
    ),
})


__all__ = [
    "EXERCISE_ENUM_VALUES",
    "SAGITTAL_METRICS_REGISTRY",
    "SagittalMetricEntry",
]
