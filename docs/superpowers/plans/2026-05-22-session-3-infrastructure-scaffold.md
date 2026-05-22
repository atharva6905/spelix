# Session 3 — Infrastructure Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the rails Sessions 4–7 ride on. Single source of truth for sagittal metric definitions (`sagittal_metrics_registry.py`), expert portal `<UnvalidatedMetricsPanel />`, `ThresholdFlagModal` section extension. No metric extraction yet — all 16 metrics still show "Not yet computed".

**Architecture:** A new backend module defines the 16-entry registry as a frozenset of frozen dataclasses. A new GET endpoint serves it to the frontend. The expert analysis detail page mounts a new `<UnvalidatedMetricsPanel />` that reads the registry + the analysis's `rep_metrics` and renders a per-rep table. `ThresholdFlagModal` accepts a new `section='unvalidated_metrics'` value. An Alembic migration adds a CHECK constraint on `threshold_flags.section` that enumerates the 5 allowed values (the column currently has no DB-level CHECK; Pydantic Literal is the only validation today).

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Alembic, SQLAlchemy 2.0 async. React 19, TypeScript strict, Tailwind v4, Vitest. `/team` cross-stack dispatch.

---

## File Structure

### Files to create

| File | Purpose |
|---|---|
| `backend/app/cv/sagittal_metrics_registry.py` | Frozenset of 16 entries. Each entry is a frozen dataclass `(key_name, display_label, unit, description, exercise_applicability, computed_yet, in_scoring)`. Pure data; no logic. Single source of truth used by both the backend endpoint and (transitively) the frontend panel via API response. |
| `backend/tests/unit/test_sagittal_metrics_registry.py` | Asserts: 16 entries, unique key names, valid exercise enum, naming honesty (`#2 lumbar_flexion_proxy_delta_deg` description includes "proxy"; `#16 technique_consistency_std` description names what it isn't), all `computed_yet=False` + `in_scoring=False` after Session 3. |
| `backend/tests/unit/test_expert_sagittal_metrics_endpoint.py` | Endpoint auth (admin + expert_reviewer 200; regular user 403; anonymous 401), response shape, all 16 entries returned. |
| `backend/alembic/versions/<timestamp>_threshold_flags_section_check.py` | Add CHECK constraint enumerating `('squat','bench','deadlift','control','unvalidated_metrics')`. Reversible. |
| `frontend/src/components/UnvalidatedMetricsPanel.tsx` | Renders per-rep table from registry + analysis rep_metrics. States: "Not yet computed" badge, computed value + unit + Flag button. |
| `frontend/src/components/__tests__/UnvalidatedMetricsPanel.test.tsx` | Empty rep_metrics state, partially-computed state, fully-computed state, flag-button-opens-modal state. |

### Files to modify

| File | Change |
|---|---|
| `backend/app/api/v1/expert.py` | New `GET /api/v1/expert/sagittal-metrics-registry` endpoint. Auth: `get_expert_reviewer_user` (allows expert_reviewer + admin). |
| `backend/app/schemas/expert_review.py` (or new `expert.py` module) | New `SagittalMetricRegistryEntry` + `SagittalMetricRegistryResponse` Pydantic schemas. |
| `backend/app/schemas/threshold_flag.py` | Extend `ThresholdFlagCreate.section` Literal to include `'unvalidated_metrics'`. |
| `backend/app/services/threshold_flag.py` | Adjust `_resolve_current_value` (or equivalent) to skip current-value lookup when `section == 'unvalidated_metrics'` (no v1 config entry to lookup). Sets `current_value = 0.0`, `current_citation = None`. |
| `backend/tests/unit/test_threshold_flag_service.py` | Add coverage for the new section's bypass path. |
| `frontend/src/api/expert.ts` | New `getSagittalMetricsRegistry()` API client + types. Widen `ThresholdRow.section` and `ThresholdFlagCreate.section` unions to include `'unvalidated_metrics'`. |
| `frontend/src/pages/ExpertAnalysisDetailPage.tsx` | Mount `<UnvalidatedMetricsPanel analysis={analysis} />` below "Coaching Output" section. |
| `frontend/src/components/ThresholdFlagModal.tsx` | Accept rows whose `section === 'unvalidated_metrics'`. Display logic already key-agnostic; verify capitalize() handles the 19-char label. |
| `frontend/src/components/__tests__/ThresholdFlagModal.test.tsx` | Add test cases asserting modal renders + submits for `section='unvalidated_metrics'`. |
| `backend/CLAUDE.md` | New section under "Backend Gotchas": **Sagittal metrics registry pattern** — single source of truth, where to add metrics in Sessions 4–7, JSONB key naming. |
| `decisions.md` | Append `ADR-SAGITTAL-METRICS-REGISTRY`. |
| `backlog.md` | Add `L2-SAGITTAL-INFRA-01..04` rows. |
| `docs/superpowers/goals/2026-05-22-cv-audit-master.md` | Flip Session 3 to `complete`, Session 4 to `active`. |
| `.claude/handoff.md` | Rewrite with Session 4 launch command. |

### Files NOT touched

- `backend/app/cv/metric_extraction.py` — no extraction yet; all 16 metrics show "Not yet computed". Sessions 4–7 add extractors.
- `frontend/src/pages/ResultsPage.tsx` — expert portal only; regular users see nothing new.

---

## Pre-Flight Confirmation (10 sec)

Before Task 1, verify the prior session merged cleanly:

- [ ] **Step 0a:** `git status` shows working tree clean OR only the master-manifest / graphify-out drift from Session 2. (Drift in those two files is expected and pre-existing; do NOT stash or revert.)
- [ ] **Step 0b:** `uv run alembic current` (from `backend/`) prints `616609f042ed` (Session 2 head, `add_lifter_side_to_analyses`).
- [ ] **Step 0c:** `git log --oneline -1 main` prints `af1548b` or its merge-commit equivalent (Session 2 PR #150 merge).

If any of these fail: STOP and report — Session 2 didn't complete cleanly.

---

## Tasks

### Task 1: Create branch + clean state

- [ ] **Step 1: Sync main**

Run: `git checkout main && git pull --ff-only`
Expected: `Already up to date.` or fast-forward; HEAD prints `af1548b...` from Session 2.

- [ ] **Step 2: Create feature branch**

Run: `git checkout -b feat/sagittal-metrics-scaffold`
Expected: `Switched to a new branch 'feat/sagittal-metrics-scaffold'`.

- [ ] **Step 3: Confirm migration head matches Session 2**

Run (from `backend/`): `uv run alembic current`
Expected: `616609f042ed (head)`.

---

### Task 2: Define `sagittal_metrics_registry.py` (TDD)

**Files:**
- Create: `backend/app/cv/sagittal_metrics_registry.py`
- Test: `backend/tests/unit/test_sagittal_metrics_registry.py`

The 16 entries come from design §Section-4. Key names are final — Sessions 4–7 will write to these exact JSONB keys.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/test_sagittal_metrics_registry.py`:

```python
"""Unit tests for the sagittal metrics registry (Session 3, L2-SAGITTAL-INFRA-01).

The registry is the single source of truth for the 16 sagittal-view metrics
that Sessions 4-7 will populate. Backend (endpoint) and frontend (panel) both
consume it; tests here are guards against drift.
"""
from __future__ import annotations

import pytest

from app.cv.sagittal_metrics_registry import (
    EXERCISE_ENUM_VALUES,
    SAGITTAL_METRICS_REGISTRY,
    SagittalMetricEntry,
)


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


class TestRegistryShape:
    def test_registry_is_frozenset(self) -> None:
        assert isinstance(SAGITTAL_METRICS_REGISTRY, frozenset)

    def test_registry_has_exactly_sixteen_entries(self) -> None:
        assert len(SAGITTAL_METRICS_REGISTRY) == 16

    def test_each_entry_is_a_frozen_dataclass(self) -> None:
        for entry in SAGITTAL_METRICS_REGISTRY:
            assert isinstance(entry, SagittalMetricEntry)
            with pytest.raises(Exception):
                # FrozenInstanceError or AttributeError depending on Python.
                entry.key_name = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Uniqueness + completeness
# ---------------------------------------------------------------------------


class TestRegistryKeys:
    def test_key_names_are_unique(self) -> None:
        keys = [e.key_name for e in SAGITTAL_METRICS_REGISTRY]
        assert len(keys) == len(set(keys)), f"Duplicate key in: {keys}"

    def test_all_sixteen_expected_keys_present(self) -> None:
        """Pin the exact key names. Changes here are breaking for Sessions 4-7."""
        expected = frozenset({
            # Session 4 (4)
            "depth_classification",
            "ecc_con_ratio",
            "pause_duration_s",
            "lockout_torso_lean_deg",
            # Session 5 (7 metrics, 8 keys because heel_rise_flag is separate)
            "ankle_dorsiflexion_deg",
            "heel_rise_flag",
            "wrist_alignment_deg",
            "bar_touch_height_pct",
            "setup_shoulder_x_offset",
            "shin_angle_deg",
            "setup_knee_angle_deg",
            "arch_deg",
            # Session 6 (2)
            "bar_to_hip_distance",
            "shoulder_protraction_proxy_px",
            # Session 7 (3)
            "lumbar_flexion_proxy_delta_deg",
            "bar_path_classification",
            "technique_consistency_std",
        })
        actual = {e.key_name for e in SAGITTAL_METRICS_REGISTRY}
        assert actual == expected, (
            f"Missing: {expected - actual}; Extra: {actual - expected}"
        )

    def test_no_key_uses_lateral_or_valgus_or_flare(self) -> None:
        """Audit constraint — frontal-plane vocabulary must stay out of sagittal keys."""
        bad_substrings = ("lateral", "valgus", "flare")
        for entry in SAGITTAL_METRICS_REGISTRY:
            lower = entry.key_name.lower()
            for s in bad_substrings:
                assert s not in lower, (
                    f"Sagittal key {entry.key_name!r} contains frontal-plane "
                    f"substring {s!r} — this is a Part-1 audit regression."
                )


# ---------------------------------------------------------------------------
# Exercise applicability
# ---------------------------------------------------------------------------


class TestExerciseApplicability:
    def test_exercise_enum_values_are_the_three_supported_exercises(self) -> None:
        assert EXERCISE_ENUM_VALUES == frozenset({"squat", "bench", "deadlift"})

    def test_every_entry_has_at_least_one_applicable_exercise(self) -> None:
        for entry in SAGITTAL_METRICS_REGISTRY:
            assert entry.exercise_applicability, (
                f"Entry {entry.key_name!r} has empty exercise_applicability"
            )

    def test_every_applicable_exercise_is_a_known_value(self) -> None:
        for entry in SAGITTAL_METRICS_REGISTRY:
            for exercise in entry.exercise_applicability:
                assert exercise in EXERCISE_ENUM_VALUES, (
                    f"Entry {entry.key_name!r} lists unknown exercise "
                    f"{exercise!r}"
                )

    def test_exercise_applicability_is_a_frozenset(self) -> None:
        for entry in SAGITTAL_METRICS_REGISTRY:
            assert isinstance(entry.exercise_applicability, frozenset)


# ---------------------------------------------------------------------------
# Computed / scoring flags — Session 3 invariant: all-false
# ---------------------------------------------------------------------------


class TestSessionThreeFlags:
    def test_no_metric_is_computed_yet(self) -> None:
        for entry in SAGITTAL_METRICS_REGISTRY:
            assert entry.computed_yet is False, (
                f"Entry {entry.key_name!r} has computed_yet=True after Session 3. "
                "Sessions 4-7 flip these to True per-metric."
            )

    def test_no_metric_is_in_scoring_yet(self) -> None:
        for entry in SAGITTAL_METRICS_REGISTRY:
            assert entry.in_scoring is False, (
                f"Entry {entry.key_name!r} has in_scoring=True after Session 3. "
                "Session 4 will flip depth_classification + ecc_con_ratio."
            )


# ---------------------------------------------------------------------------
# Naming honesty — R4 mitigation (design §Section-5)
# ---------------------------------------------------------------------------


class TestNamingHonesty:
    def _find(self, key: str) -> SagittalMetricEntry:
        for e in SAGITTAL_METRICS_REGISTRY:
            if e.key_name == key:
                return e
        raise AssertionError(f"Registry entry not found: {key}")

    def test_lumbar_flexion_proxy_key_uses_proxy_suffix(self) -> None:
        # #2 — naming honesty per ADR-LUMBAR-FLEXION-PROXY-NAMING (Session 7).
        entry = self._find("lumbar_flexion_proxy_delta_deg")
        assert "proxy" in entry.key_name

    def test_lumbar_flexion_proxy_description_names_what_it_isnt(self) -> None:
        entry = self._find("lumbar_flexion_proxy_delta_deg")
        # The description must explicitly disclaim that this is NOT a lumbar-
        # isolated measurement. This is the chat-visible honesty surface for
        # the expert reviewer.
        lower = entry.description.lower()
        assert "not lumbar" in lower or "not lumbar-isolated" in lower, (
            f"Description must disclaim non-lumbar-isolation; got: "
            f"{entry.description!r}"
        )

    def test_technique_consistency_std_description_names_underlying_metric(self) -> None:
        entry = self._find("technique_consistency_std")
        # Description must name that it's a std-dev of an underlying metric,
        # not a primary measurement.
        lower = entry.description.lower()
        assert "std" in lower or "standard deviation" in lower or "consistency" in lower


# ---------------------------------------------------------------------------
# Display labels and units
# ---------------------------------------------------------------------------


class TestDisplayMetadata:
    def test_every_entry_has_nonempty_display_label(self) -> None:
        for entry in SAGITTAL_METRICS_REGISTRY:
            assert entry.display_label.strip(), (
                f"Entry {entry.key_name!r} has empty display_label"
            )

    def test_every_entry_has_nonempty_description(self) -> None:
        for entry in SAGITTAL_METRICS_REGISTRY:
            assert len(entry.description.strip()) >= 10, (
                f"Entry {entry.key_name!r} has too-short description "
                f"({entry.description!r})"
            )

    def test_unit_is_a_string(self) -> None:
        # Units are strings (deg, ratio, s, px, classification, etc.); some
        # are empty for classification metrics. Strings only — no None.
        for entry in SAGITTAL_METRICS_REGISTRY:
            assert isinstance(entry.unit, str), (
                f"Entry {entry.key_name!r} unit must be str, got "
                f"{type(entry.unit).__name__}"
            )

    def test_descriptions_avoid_movement_quality_language_rules(self) -> None:
        """Project rule: never use 'injury risk' / 'injury prevention' / 'safety score'."""
        forbidden = ("injury risk", "injury prevention", "safety score")
        for entry in SAGITTAL_METRICS_REGISTRY:
            lower = entry.description.lower()
            for term in forbidden:
                assert term not in lower, (
                    f"Entry {entry.key_name!r} description uses forbidden "
                    f"phrase {term!r}: {entry.description!r}"
                )
```

- [ ] **Step 2: Run the failing tests**

Run (from `backend/`): `uv run pytest tests/unit/test_sagittal_metrics_registry.py -x`
Expected: `ModuleNotFoundError: No module named 'app.cv.sagittal_metrics_registry'` — confirms TDD red.

- [ ] **Step 3: Write the registry module**

Create `backend/app/cv/sagittal_metrics_registry.py`:

```python
"""Sagittal-view metrics registry (Session 3, L2-SAGITTAL-INFRA-01).

Single source of truth for the 16 sagittal-view metrics that Sessions 4-7
will populate. Backend serves this list via
``GET /api/v1/expert/sagittal-metrics-registry``; the frontend
``<UnvalidatedMetricsPanel />`` renders the rows.

Keys here are FINAL — Sessions 4-7 write to these exact JSONB key names in
``rep_metrics.metrics``. Renaming a key is a breaking change requiring a
data migration.

See ADR-SAGITTAL-METRICS-REGISTRY and design §Section-4.
"""
from __future__ import annotations

from dataclasses import dataclass

# Supported exercises (matches user_profile + analyses constraints).
EXERCISE_ENUM_VALUES: frozenset[str] = frozenset({"squat", "bench", "deadlift"})


@dataclass(frozen=True)
class SagittalMetricEntry:
    """Immutable description of one sagittal-view metric.

    All 16 entries share this shape so the frontend can render them
    uniformly. Threshold values are NOT included — those live in
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
        computed_yet=False,
        in_scoring=False,
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
        computed_yet=False,
        in_scoring=False,
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
        computed_yet=False,
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
        computed_yet=False,
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
            "at rep bottom. 90 minus this is dorsiflexion magnitude."
        ),
        exercise_applicability=_SQ,
        computed_yet=False,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="heel_rise_flag",
        display_label="Heel Rise Flag",
        unit="",  # boolean rendered as Yes/No
        description=(
            "True when the heel y-coordinate drops below the standing baseline "
            "by more than 2% of frame height for 3+ consecutive descent frames."
        ),
        exercise_applicability=_SQ,
        computed_yet=False,
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
        computed_yet=False,
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
        computed_yet=False,
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
        computed_yet=False,
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
        computed_yet=False,
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
        computed_yet=False,
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
        computed_yet=False,
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
            "shoulder-to-hip distance. Proxy — actual scapular protraction "
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
            "Not lumbar-isolated — see ADR-LUMBAR-FLEXION-PROXY-NAMING."
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
            "Heuristic v0 — expect post-onboarding refinement."
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
```

- [ ] **Step 4: Run the tests — they pass now**

Run: `uv run pytest tests/unit/test_sagittal_metrics_registry.py -x -v`
Expected: every test passes (estimate: ~15 tests).

- [ ] **Step 5: Coverage check**

Run: `uv run pytest tests/unit/test_sagittal_metrics_registry.py --cov=app.cv.sagittal_metrics_registry --cov-report=term-missing`
Expected: 100% line coverage on the new module (pure data; everything is covered by the iteration tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/sagittal_metrics_registry.py backend/tests/unit/test_sagittal_metrics_registry.py
git commit -m "feat(cv): add sagittal_metrics_registry frozenset (L2-SAGITTAL-INFRA-01)"
```

---

### Task 3: Pydantic schemas for the registry response

**Files:**
- Modify: `backend/app/schemas/expert_review.py`

- [ ] **Step 1: Add the schemas**

Append to `backend/app/schemas/expert_review.py` (the existing expert response-schemas module):

```python
class SagittalMetricRegistryEntry(BaseModel):
    """One row in the sagittal metrics registry response (Session 3)."""

    model_config = ConfigDict(from_attributes=True)

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
```

If `BaseModel` / `ConfigDict` are not already imported in that file, add them:

```python
from pydantic import BaseModel, ConfigDict
```

- [ ] **Step 2: Schema-level test**

Append to `backend/tests/unit/test_expert_sagittal_metrics_endpoint.py` (file will be fully written in Task 4; for now, scaffold a tiny schema test inline as part of the registry tests by appending to `test_sagittal_metrics_registry.py`):

```python
def test_registry_entries_round_trip_through_pydantic_schema() -> None:
    """Pydantic v2 schema must accept the registry frozen-dataclass shape."""
    from app.schemas.expert_review import (
        SagittalMetricRegistryEntry,
        SagittalMetricRegistryResponse,
    )

    payload = [
        SagittalMetricRegistryEntry(
            key_name=e.key_name,
            display_label=e.display_label,
            unit=e.unit,
            description=e.description,
            exercise_applicability=sorted(e.exercise_applicability),
            computed_yet=e.computed_yet,
            in_scoring=e.in_scoring,
        )
        for e in SAGITTAL_METRICS_REGISTRY
    ]
    response = SagittalMetricRegistryResponse(entries=payload)
    assert len(response.entries) == 16
    keys = {entry.key_name for entry in response.entries}
    assert len(keys) == 16  # uniqueness preserved through serialization
```

(Add the `from app.cv.sagittal_metrics_registry import SAGITTAL_METRICS_REGISTRY` import near the top of `test_sagittal_metrics_registry.py` if not already there — it should be.)

- [ ] **Step 3: Run schema test**

Run: `uv run pytest tests/unit/test_sagittal_metrics_registry.py::test_registry_entries_round_trip_through_pydantic_schema -x -v`
Expected: passes.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/expert_review.py backend/tests/unit/test_sagittal_metrics_registry.py
git commit -m "feat(schemas): add SagittalMetricRegistry response schemas (L2-SAGITTAL-INFRA-01)"
```

---

### Task 4: `GET /api/v1/expert/sagittal-metrics-registry` endpoint (TDD)

**Files:**
- Create: `backend/tests/unit/test_expert_sagittal_metrics_endpoint.py`
- Modify: `backend/app/api/v1/expert.py`

- [ ] **Step 1: Write the failing endpoint tests**

Create `backend/tests/unit/test_expert_sagittal_metrics_endpoint.py`:

```python
"""Endpoint tests for GET /api/v1/expert/sagittal-metrics-registry.

Session 3, L2-SAGITTAL-INFRA-02. The endpoint returns the 16-entry registry
to expert_reviewer + admin roles. Regular users get 403, anonymous gets 401.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user, get_expert_reviewer_user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _expert_user() -> dict[str, Any]:
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "expert@example.com",
        "role": "expert_reviewer",
    }


def _admin_user() -> dict[str, Any]:
    return {
        "id": "00000000-0000-0000-0000-000000000002",
        "email": "admin@example.com",
        "role": "admin",
    }


@pytest.fixture
def expert_client() -> Iterator[TestClient]:
    """TestClient where get_expert_reviewer_user returns an expert."""
    app.dependency_overrides[get_expert_reviewer_user] = lambda: _expert_user()
    app.dependency_overrides[get_current_user] = lambda: _expert_user()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client() -> Iterator[TestClient]:
    app.dependency_overrides[get_expert_reviewer_user] = lambda: _admin_user()
    app.dependency_overrides[get_current_user] = lambda: _admin_user()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client() -> Iterator[TestClient]:
    """No overrides — get_expert_reviewer_user runs its real Supabase JWT check
    which rejects unauthenticated calls with 401."""
    yield TestClient(app)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestSagittalMetricsRegistryEndpoint:
    def test_expert_reviewer_gets_200_with_sixteen_entries(
        self, expert_client: TestClient
    ) -> None:
        resp = expert_client.get("/api/v1/expert/sagittal-metrics-registry")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "entries" in body
        assert len(body["entries"]) == 16

    def test_admin_gets_200_with_sixteen_entries(
        self, admin_client: TestClient
    ) -> None:
        resp = admin_client.get("/api/v1/expert/sagittal-metrics-registry")
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["entries"]) == 16

    def test_response_shape_matches_schema(
        self, expert_client: TestClient
    ) -> None:
        resp = expert_client.get("/api/v1/expert/sagittal-metrics-registry")
        entries = resp.json()["entries"]
        required_fields = {
            "key_name",
            "display_label",
            "unit",
            "description",
            "exercise_applicability",
            "computed_yet",
            "in_scoring",
        }
        for entry in entries:
            assert required_fields.issubset(entry.keys()), (
                f"Missing fields in entry {entry.get('key_name', '?')!r}: "
                f"{required_fields - set(entry.keys())}"
            )
            assert isinstance(entry["exercise_applicability"], list)
            assert isinstance(entry["computed_yet"], bool)
            assert isinstance(entry["in_scoring"], bool)

    def test_after_session3_no_metric_is_computed(
        self, expert_client: TestClient
    ) -> None:
        resp = expert_client.get("/api/v1/expert/sagittal-metrics-registry")
        for entry in resp.json()["entries"]:
            assert entry["computed_yet"] is False
            assert entry["in_scoring"] is False

    def test_lumbar_flexion_proxy_carries_naming_honesty(
        self, expert_client: TestClient
    ) -> None:
        resp = expert_client.get("/api/v1/expert/sagittal-metrics-registry")
        entries = {e["key_name"]: e for e in resp.json()["entries"]}
        lumbar = entries["lumbar_flexion_proxy_delta_deg"]
        assert "not lumbar" in lumbar["description"].lower()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestSagittalMetricsRegistryAuth:
    def test_unauthenticated_request_is_rejected(
        self, unauth_client: TestClient
    ) -> None:
        resp = unauth_client.get("/api/v1/expert/sagittal-metrics-registry")
        # get_expert_reviewer_user raises 401 when no JWT is present.
        assert resp.status_code in (401, 403), resp.text

    def test_regular_user_role_is_rejected(self) -> None:
        """Override get_expert_reviewer_user to simulate a non-expert hitting
        the dependency — the dep itself raises HTTPException(403)."""
        from fastapi import HTTPException, status

        def _reject() -> Any:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "expert_reviewer role required",
                        "detail": None,
                    }
                },
            )

        app.dependency_overrides[get_expert_reviewer_user] = _reject
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/expert/sagittal-metrics-registry")
            assert resp.status_code == 403, resp.text
        finally:
            app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/unit/test_expert_sagittal_metrics_endpoint.py -x`
Expected: 404 on every happy-path call (endpoint doesn't exist yet) — confirms TDD red.

- [ ] **Step 3: Add the endpoint**

In `backend/app/api/v1/expert.py`, add a new import near the existing schema imports:

```python
from app.cv.sagittal_metrics_registry import SAGITTAL_METRICS_REGISTRY
from app.schemas.expert_review import (
    SagittalMetricRegistryEntry,
    SagittalMetricRegistryResponse,
)
```

Add a new route. Place it AFTER the existing `/thresholds` endpoints, BEFORE the `/papers` listing (keeps related expert endpoints grouped):

```python
# ---------------------------------------------------------------------------
# Sagittal Metrics Registry (Session 3, L2-SAGITTAL-INFRA-02)
# ---------------------------------------------------------------------------


@router.get(
    "/sagittal-metrics-registry",
    response_model=SagittalMetricRegistryResponse,
)
async def get_sagittal_metrics_registry(
    user: CurrentUser = Depends(get_expert_reviewer_user),
) -> SagittalMetricRegistryResponse:
    """Return the 16-entry sagittal metrics registry.

    Single source of truth for the metrics Sessions 4-7 will populate.
    Static data — no DB lookup. Auth: expert_reviewer or admin.
    """
    entries = [
        SagittalMetricRegistryEntry(
            key_name=e.key_name,
            display_label=e.display_label,
            unit=e.unit,
            description=e.description,
            exercise_applicability=sorted(e.exercise_applicability),
            computed_yet=e.computed_yet,
            in_scoring=e.in_scoring,
        )
        # Sort for deterministic ordering — display label gives a sensible UX order.
        for e in sorted(
            SAGITTAL_METRICS_REGISTRY, key=lambda x: x.display_label
        )
    ]
    return SagittalMetricRegistryResponse(entries=entries)
```

- [ ] **Step 4: Run the tests — they pass now**

Run: `uv run pytest tests/unit/test_expert_sagittal_metrics_endpoint.py -x -v`
Expected: every test passes (~7 tests).

- [ ] **Step 5: Print the OpenAPI shape for chat-visible evidence**

Run: `uv run python -c "from app.main import app; import json; spec = app.openapi(); print(json.dumps(spec['paths']['/api/v1/expert/sagittal-metrics-registry'], indent=2))"`
Capture the output — Session 3 DoD item 2 requires the OpenAPI shape printed in chat.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/expert.py backend/tests/unit/test_expert_sagittal_metrics_endpoint.py
git commit -m "feat(api): GET /expert/sagittal-metrics-registry returns 16-entry registry (L2-SAGITTAL-INFRA-02)"
```

---

### Task 5: Extend `ThresholdFlagCreate` for the new section

**Files:**
- Modify: `backend/app/schemas/threshold_flag.py`
- Modify: `backend/app/services/threshold_flag.py` (only if it touches `section` in a way that requires `unvalidated_metrics` to bypass current-value lookup)
- Modify: `backend/tests/unit/test_threshold_flag_service.py`

- [ ] **Step 1: Widen the Literal**

In `backend/app/schemas/threshold_flag.py`, change:

```python
class ThresholdFlagCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    section: Literal["squat", "bench", "deadlift", "control"]
```

to:

```python
class ThresholdFlagCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    section: Literal[
        "squat", "bench", "deadlift", "control", "unvalidated_metrics"
    ]
```

`ThresholdRow.section` and the model itself already use `str` with `max_length=30`, which accommodates the 19-char `unvalidated_metrics` value — no change needed there.

- [ ] **Step 2: Inspect threshold_flag service for current-value lookup**

Run: `grep -n "current_value\|squat\|bench\|deadlift\|control" backend/app/services/threshold_flag.py | head -50`

If the service's `_resolve_current_value` (or equivalent) does `config_loader.get(section, key)` and would raise on `unvalidated_metrics`, add a short-circuit:

```python
if section == "unvalidated_metrics":
    # No v1 config entry exists for these (compute-only metrics, threshold
    # validation deferred to post-onboarding). Bypass current-value lookup.
    return 0.0, None  # (current_value, current_citation)
```

If the service uses `ALLOWED_SECTIONS` from `schemas/threshold_flag.py`, extend that frozenset too:

```python
ALLOWED_SECTIONS: frozenset[str] = frozenset({
    "squat", "bench", "deadlift", "control", "unvalidated_metrics",
})
```

- [ ] **Step 3: Add a service test**

Append to `backend/tests/unit/test_threshold_flag_service.py` (if it does not exist, create it with the standard fixtures). Test body:

```python
@pytest.mark.asyncio
async def test_create_flag_with_unvalidated_metrics_section_succeeds(
    threshold_flag_service, mock_threshold_flag_repo
) -> None:
    """A flag targeting an Unvalidated Metric (Session 3) bypasses the v1
    config-lookup since those metrics have no threshold values yet."""
    mock_threshold_flag_repo.create.return_value = MagicMock(
        id=uuid4(),
        section="unvalidated_metrics",
        key="ankle_dorsiflexion_deg",
    )
    flag = await threshold_flag_service.create_flag(
        reviewer_id=uuid4(),
        section="unvalidated_metrics",
        key="ankle_dorsiflexion_deg",
        proposed_value=15.0,
        proposed_citation="Smith 2023 — ankle dorsiflexion ROM norms",
        rationale=(
            "Current threshold absent; literature suggests 15 deg minimum "
            "for full squat depth without heel rise."
        ),
    )
    assert flag.section == "unvalidated_metrics"
    # current_value defaulted to 0.0 in the bypass path
    call_args = mock_threshold_flag_repo.create.call_args
    created = call_args.args[0]
    assert created.current_value == 0.0
    assert created.current_citation is None
```

(If `test_threshold_flag_service.py` doesn't have those fixtures, mirror them from `test_expert_*.py`; details left to the implementer because the test-fixture shape varies by repo style — keep the assertions verbatim.)

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/test_threshold_flag_service.py -x -v`
Expected: existing tests stay green; new test passes. **STOP and investigate** if any existing test now fails — the bypass code path should be additive.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/threshold_flag.py backend/app/services/threshold_flag.py backend/tests/unit/test_threshold_flag_service.py
git commit -m "feat(schemas): allow section='unvalidated_metrics' on ThresholdFlagCreate"
```

---

### Task 6: Alembic migration extending `threshold_flags.section` CHECK

**Files:**
- Create: `backend/alembic/versions/<timestamp>_threshold_flags_section_check.py`

**Use the `spelix-migration` agent** (project rule for all migrations).

> Migration honesty: looking at `022_add_threshold_flags.py`, the `section` column today is `VARCHAR(30)` with NO database-level CHECK — the Pydantic Literal in `ThresholdFlagCreate` is the only validator. Strictly speaking this migration *adds* (not extends) the section CHECK. The skeleton uses "extends" loosely; we add a new CHECK that enumerates all 5 allowed values, satisfying the DoD requirement "extends to allow 'unvalidated_metrics'".

- [ ] **Step 1: Dispatch the spelix-migration agent**

> Use the spelix-migration agent. Add a CHECK constraint to `threshold_flags.section` that enumerates `'squat'`, `'bench'`, `'deadlift'`, `'control'`, `'unvalidated_metrics'`. Name the constraint `ck_threshold_flags_section`. Reversible (`downgrade()` drops the constraint). Down-revision: `0906139da711` (current head). Generate the file under `backend/alembic/versions/` and print the file path.

- [ ] **Step 2: Verify migration file content**

Read the generated file. It must contain (modulo trivial formatting):

```python
def upgrade() -> None:
    op.create_check_constraint(
        "ck_threshold_flags_section",
        "threshold_flags",
        "section IN ('squat', 'bench', 'deadlift', 'control', 'unvalidated_metrics')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_threshold_flags_section", "threshold_flags", type_="check"
    )
```

- [ ] **Step 3: Apply migration locally**

Run (from `backend/`): `uv run alembic upgrade head`
Expected: `Running upgrade 0906139da711 -> <new_head>, threshold flags section check`.

- [ ] **Step 4: Confirm head moved (chat-visible evidence)**

Run: `uv run alembic current`
Expected: prints the new head SHA — **capture this output for Session 3 DoD item 4.**

- [ ] **Step 5: Test reversibility**

Run: `uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: downgrade succeeds (constraint dropped), then upgrade re-applies cleanly. End at the new head. **If `downgrade` errors and the constraint cannot be reverted: STOP — this triggers the goal's "migration cannot be reverted cleanly" clause, which bypasses remediation and escalates.**

- [ ] **Step 6: Add a migration-shape test**

Create `backend/tests/integration/test_threshold_flags_section_check.py` (integration because it needs a real Postgres session):

```python
"""Integration test — Session 3 migration adds CHECK constraint on
threshold_flags.section. The five allowed values insert; typos reject."""
from __future__ import annotations

from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


_VALID_SECTIONS = ("squat", "bench", "deadlift", "control", "unvalidated_metrics")


def _insert_sql(section: str) -> sa.sql.text:
    return sa.text(
        "INSERT INTO threshold_flags ("
        "  reviewer_id, section, key, current_value, current_citation, "
        "  proposed_value, proposed_citation, rationale"
        ") VALUES ("
        "  :rid, :section, 'k', 1.0, NULL, 2.0, "
        "  'Author year — finding', "
        "  'Twenty character or more rationale for this flag.'"
        ")"
    ).bindparams(rid=uuid4(), section=section)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("section", _VALID_SECTIONS)
async def test_valid_section_values_insert_successfully(
    db_session: AsyncSession, section: str
) -> None:
    await db_session.execute(_insert_sql(section))
    await db_session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_section_is_rejected_by_check_constraint(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(IntegrityError):
        await db_session.execute(_insert_sql("typo_section_value"))
        await db_session.commit()
```

- [ ] **Step 7: Run the migration tests**

Run: `uv run pytest tests/integration/test_threshold_flags_section_check.py -x -v`
Expected: 6 tests pass (5 valid + 1 invalid). If the integration `db_session` fixture isn't available in this project, document so and move the test to a pure-unit check that inspects the migration AST.

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/versions/ backend/tests/integration/test_threshold_flags_section_check.py
git commit -m "feat(db): add CHECK constraint on threshold_flags.section (L2-SAGITTAL-INFRA-03)"
```

---

### Task 7: Frontend — extend `expert.ts` types + add registry client

**Files:**
- Modify: `frontend/src/api/expert.ts`

- [ ] **Step 1: Add the registry types and fetcher**

In `frontend/src/api/expert.ts`, append a new section AFTER the existing `Threshold*` block:

```ts
// ---------------------------------------------------------------------------
// Sagittal Metrics Registry (Session 3, L2-SAGITTAL-INFRA-02)
// ---------------------------------------------------------------------------

export interface SagittalMetricRegistryEntry {
  key_name: string;
  display_label: string;
  unit: string;
  description: string;
  exercise_applicability: Array<"squat" | "bench" | "deadlift">;
  computed_yet: boolean;
  in_scoring: boolean;
}

export interface SagittalMetricRegistryResponse {
  entries: SagittalMetricRegistryEntry[];
}

export async function getSagittalMetricsRegistry(): Promise<SagittalMetricRegistryResponse> {
  return expertFetch<SagittalMetricRegistryResponse>(
    "/api/v1/expert/sagittal-metrics-registry",
  );
}
```

- [ ] **Step 2: Widen `ThresholdRow.section` and `ThresholdFlagCreate.section`**

Change:

```ts
export interface ThresholdRow {
  section: "squat" | "bench" | "deadlift" | "control";
  // ...
}

export interface ThresholdFlagCreate {
  section: ThresholdRow["section"];
  // ...
}

export interface ThresholdFlagResponse {
  // ...
  section: ThresholdRow["section"];
  // ...
}
```

to:

```ts
export type ThresholdSection =
  | "squat"
  | "bench"
  | "deadlift"
  | "control"
  | "unvalidated_metrics";

export interface ThresholdRow {
  section: ThresholdSection;
  // ...
}

export interface ThresholdFlagCreate {
  section: ThresholdSection;
  // ...
}

export interface ThresholdFlagResponse {
  // ...
  section: ThresholdSection;
  // ...
}
```

`ThresholdListing.sections` is typed `Record<ThresholdRow["section"], ThresholdRow[]>` — that becomes `Record<ThresholdSection, ThresholdRow[]>` automatically; verify the `ExpertThresholdsPage` still typechecks (it groups by section name — the union widening is additive).

- [ ] **Step 3: Verify TypeScript still compiles**

Run (from `frontend/`): `npx tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/expert.ts
git commit -m "feat(api): add sagittal-metrics-registry client + widen ThresholdSection (L2-SAGITTAL-INFRA-02)"
```

---

### Task 8: `<UnvalidatedMetricsPanel />` component (TDD)

**Files:**
- Create: `frontend/src/components/UnvalidatedMetricsPanel.tsx`
- Create: `frontend/src/components/__tests__/UnvalidatedMetricsPanel.test.tsx`

**Critical for spelix-security-reviewer:** the panel header and subhead strings must NOT use "injury risk" / "injury prevention" / "safety score". Use exactly the design's language:
  - Header: **"Unvalidated Metrics (computed, pending expert validation)"**
  - Subhead: **"These metrics are computed but NOT YET scored. Validate against the video before flagging thresholds."**

- [ ] **Step 1: Write the failing component tests**

Create `frontend/src/components/__tests__/UnvalidatedMetricsPanel.test.tsx`:

```tsx
/**
 * Unit tests for <UnvalidatedMetricsPanel /> (Session 3, L2-SAGITTAL-INFRA-04).
 *
 * The panel renders one row per applicable registry entry per rep. After
 * Session 3, ALL entries show "Not yet computed". Sessions 4-7 will flip
 * `computed_yet=true` per metric, at which point the panel renders real
 * values + a Flag button.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

import UnvalidatedMetricsPanel from "@/components/UnvalidatedMetricsPanel";
import type {
  ExpertAnalysisDetail,
  SagittalMetricRegistryResponse,
} from "@/api/expert";
import * as expertApi from "@/api/expert";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const _makeRegistryResponse = (
  overrides: Partial<SagittalMetricRegistryResponse> = {},
): SagittalMetricRegistryResponse => ({
  entries: [
    {
      key_name: "depth_classification",
      display_label: "Depth Classification",
      unit: "",
      description: "Categorical relabel of squat depth.",
      exercise_applicability: ["squat"],
      computed_yet: false,
      in_scoring: false,
    },
    {
      key_name: "ankle_dorsiflexion_deg",
      display_label: "Ankle Dorsiflexion",
      unit: "deg",
      description: "Angle at the ankle at rep bottom.",
      exercise_applicability: ["squat"],
      computed_yet: false,
      in_scoring: false,
    },
    {
      key_name: "wrist_alignment_deg",
      display_label: "Wrist Alignment",
      unit: "deg",
      description: "Sagittal wrist stacking.",
      exercise_applicability: ["bench"],
      computed_yet: false,
      in_scoring: false,
    },
  ],
  ...overrides,
});

const _makeAnalysis = (
  overrides: Partial<ExpertAnalysisDetail> = {},
): ExpertAnalysisDetail => ({
  id: "11111111-1111-1111-1111-111111111111",
  exercise_type: "squat",
  exercise_variant: "high_bar",
  confidence_score: 0.87,
  form_score_safety: 7.5,
  form_score_technique: 7.0,
  form_score_path_balance: 7.5,
  form_score_control: 6.5,
  form_score_overall: 7.2,
  summary_json: { rep_count: 2 },
  quality_gate_result: null,
  coaching_result: null,
  rep_metrics: [
    { rep_index: 1 },
    { rep_index: 2 },
  ],
  retrieval_context: null,
  eval_scores: null,
  flagged_for_review: false,
  is_golden_dataset: false,
  created_at: "2026-05-22T10:00:00Z",
  annotated_video_url: null,
  ...overrides,
});

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/api/expert", async () => {
  const actual = await vi.importActual<typeof expertApi>("@/api/expert");
  return {
    ...actual,
    getSagittalMetricsRegistry: vi.fn(),
    createThresholdFlag: vi.fn(),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UnvalidatedMetricsPanel", () => {
  it("renders the panel header and subhead with exact SaMD-compliant language", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue(
      _makeRegistryResponse(),
    );
    render(<UnvalidatedMetricsPanel analysis={_makeAnalysis()} />);
    expect(
      await screen.findByText(
        /Unvalidated Metrics \(computed, pending expert validation\)/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /These metrics are computed but NOT YET scored\. Validate against the video before flagging thresholds\./i,
      ),
    ).toBeInTheDocument();
  });

  it("does NOT use forbidden phrases in panel copy", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue(
      _makeRegistryResponse(),
    );
    const { container } = render(
      <UnvalidatedMetricsPanel analysis={_makeAnalysis()} />,
    );
    await waitFor(() =>
      expect(
        expertApi.getSagittalMetricsRegistry,
      ).toHaveBeenCalled(),
    );
    const text = container.textContent ?? "";
    expect(text.toLowerCase()).not.toContain("injury risk");
    expect(text.toLowerCase()).not.toContain("injury prevention");
    expect(text.toLowerCase()).not.toContain("safety score");
  });

  it("renders only entries applicable to the analysis exercise (squat → 2 rows, not bench)", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue(
      _makeRegistryResponse(),
    );
    render(<UnvalidatedMetricsPanel analysis={_makeAnalysis()} />);
    // depth_classification + ankle_dorsiflexion_deg apply to squat.
    expect(await screen.findByText("Depth Classification")).toBeInTheDocument();
    expect(screen.getByText("Ankle Dorsiflexion")).toBeInTheDocument();
    // wrist_alignment_deg is bench-only → must not render.
    expect(screen.queryByText("Wrist Alignment")).not.toBeInTheDocument();
  });

  it("shows 'Not yet computed' badge for every row when no value exists in rep_metrics", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue(
      _makeRegistryResponse(),
    );
    render(<UnvalidatedMetricsPanel analysis={_makeAnalysis()} />);
    const badges = await screen.findAllByText(/Not yet computed/i);
    // 2 applicable squat metrics × 2 reps = 4 badges.
    expect(badges.length).toBe(4);
  });

  it("renders the computed value + unit when rep_metrics contains the key", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue(
      _makeRegistryResponse(),
    );
    const analysis = _makeAnalysis({
      rep_metrics: [
        { rep_index: 1, ankle_dorsiflexion_deg: 12.3 },
        { rep_index: 2, ankle_dorsiflexion_deg: 14.1 },
      ],
    });
    render(<UnvalidatedMetricsPanel analysis={analysis} />);
    expect(await screen.findByText("12.3 deg")).toBeInTheDocument();
    expect(screen.getByText("14.1 deg")).toBeInTheDocument();
  });

  it("renders Flag buttons for computed rows and opens ThresholdFlagModal on click", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue({
      entries: [
        {
          key_name: "ankle_dorsiflexion_deg",
          display_label: "Ankle Dorsiflexion",
          unit: "deg",
          description: "Angle at the ankle at rep bottom.",
          exercise_applicability: ["squat"],
          computed_yet: true, // simulate Session 5's flip
          in_scoring: false,
        },
      ],
    });
    const analysis = _makeAnalysis({
      rep_metrics: [{ rep_index: 1, ankle_dorsiflexion_deg: 12.3 }],
    });
    render(<UnvalidatedMetricsPanel analysis={analysis} />);
    const flagBtn = await screen.findByRole("button", { name: /Flag/i });
    fireEvent.click(flagBtn);
    expect(await screen.findByText(/Flag threshold/i)).toBeInTheDocument();
  });

  it("renders a graceful empty state when the registry fetch fails", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockRejectedValue(
      new Error("network error"),
    );
    render(<UnvalidatedMetricsPanel analysis={_makeAnalysis()} />);
    expect(
      await screen.findByText(/Unable to load sagittal metrics registry/i),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the failing tests**

Run (from `frontend/`): `npm test -- --run UnvalidatedMetricsPanel`
Expected: `Cannot find module '@/components/UnvalidatedMetricsPanel'` — TDD red.

- [ ] **Step 3: Write the component**

Create `frontend/src/components/UnvalidatedMetricsPanel.tsx`:

```tsx
/**
 * UnvalidatedMetricsPanel — Session 3 (L2-SAGITTAL-INFRA-04).
 *
 * Shows the 16 sagittal-view metrics that Sessions 4-7 will populate.
 * Expert reviewers only — mounted on ExpertAnalysisDetailPage.
 *
 * Language constraints (SaMD compliance — reviewed by spelix-security-reviewer):
 * - Header: "Unvalidated Metrics (computed, pending expert validation)"
 * - Subhead: "These metrics are computed but NOT YET scored. Validate against
 *   the video before flagging thresholds."
 * - NEVER uses "injury risk", "injury prevention", or "safety score".
 */
import { useCallback, useEffect, useState } from "react";

import {
  createThresholdFlag,
  getSagittalMetricsRegistry,
  type ExpertAnalysisDetail,
  type SagittalMetricRegistryEntry,
  type ThresholdFlagCreate,
  type ThresholdRow,
} from "@/api/expert";
import ThresholdFlagModal from "@/components/ThresholdFlagModal";

interface Props {
  analysis: ExpertAnalysisDetail;
}

interface ApplicableEntry extends SagittalMetricRegistryEntry {
  perRep: Array<{ repIndex: number; value: number | string | null }>;
}

function _extractValue(
  rep: Record<string, unknown>,
  key: string,
): number | string | null {
  const raw = rep[key];
  if (raw === undefined || raw === null) return null;
  if (typeof raw === "number" || typeof raw === "string") return raw;
  // dict/object values (e.g. bar_to_hip_distance) render as JSON for now.
  try {
    return JSON.stringify(raw);
  } catch {
    return null;
  }
}

function _formatValue(value: number | string | null, unit: string): string {
  if (value === null) return "—";
  if (typeof value === "number") {
    const trimmed = unit.trim();
    return trimmed ? `${value.toFixed(1)} ${trimmed}` : value.toFixed(1);
  }
  return String(value);
}

export default function UnvalidatedMetricsPanel({ analysis }: Props) {
  const [entries, setEntries] = useState<SagittalMetricRegistryEntry[] | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [flagRow, setFlagRow] = useState<ThresholdRow | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSagittalMetricsRegistry()
      .then((resp) => {
        if (!cancelled) setEntries(resp.entries);
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("Failed to load sagittal metrics registry", err);
          setError("Unable to load sagittal metrics registry.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const applicable: ApplicableEntry[] = (entries ?? [])
    .filter((e) =>
      e.exercise_applicability.includes(
        analysis.exercise_type as "squat" | "bench" | "deadlift",
      ),
    )
    .map((e) => ({
      ...e,
      perRep: analysis.rep_metrics.map((rep, i) => ({
        repIndex:
          typeof rep.rep_index === "number" ? (rep.rep_index as number) : i + 1,
        value: _extractValue(rep, e.key_name),
      })),
    }));

  const handleFlagSubmit = useCallback(
    async (payload: ThresholdFlagCreate) => {
      await createThresholdFlag(payload);
    },
    [],
  );

  if (error) {
    return (
      <section
        aria-labelledby="unvalidated-metrics-heading"
        className="mb-6 rounded-lg bg-white p-6 shadow-sm"
      >
        <h2
          id="unvalidated-metrics-heading"
          className="mb-2 text-lg font-semibold text-gray-900"
        >
          Unvalidated Metrics (computed, pending expert validation)
        </h2>
        <p className="text-sm text-red-600">{error}</p>
      </section>
    );
  }

  if (entries === null) {
    return (
      <section
        aria-labelledby="unvalidated-metrics-heading"
        className="mb-6 rounded-lg bg-white p-6 shadow-sm"
      >
        <h2
          id="unvalidated-metrics-heading"
          className="mb-2 text-lg font-semibold text-gray-900"
        >
          Unvalidated Metrics (computed, pending expert validation)
        </h2>
        <p className="text-sm text-gray-400">Loading sagittal metrics…</p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="unvalidated-metrics-heading"
      className="mb-6 rounded-lg bg-white p-6 shadow-sm"
    >
      <h2
        id="unvalidated-metrics-heading"
        className="mb-1 text-lg font-semibold text-gray-900"
      >
        Unvalidated Metrics (computed, pending expert validation)
      </h2>
      <p className="mb-4 text-sm text-gray-600">
        These metrics are computed but NOT YET scored. Validate against the
        video before flagging thresholds.
      </p>

      {applicable.length === 0 ? (
        <p className="text-sm text-gray-400">
          No sagittal metrics apply to this exercise.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="py-2 pr-3">Metric</th>
                {analysis.rep_metrics.map((_, i) => (
                  <th key={i} className="py-2 pr-3">
                    Rep {i + 1}
                  </th>
                ))}
                <th className="py-2 pr-3">Description</th>
              </tr>
            </thead>
            <tbody>
              {applicable.map((entry) => (
                <tr key={entry.key_name} className="border-b align-top">
                  <td className="py-2 pr-3 font-medium text-gray-700">
                    {entry.display_label}
                  </td>
                  {entry.perRep.map((rep, i) => (
                    <td key={i} className="py-2 pr-3 text-gray-700">
                      {entry.computed_yet && rep.value !== null ? (
                        <div className="flex items-center gap-2">
                          <span>{_formatValue(rep.value, entry.unit)}</span>
                          <button
                            type="button"
                            onClick={() =>
                              setFlagRow({
                                section: "unvalidated_metrics",
                                key: entry.key_name,
                                value:
                                  typeof rep.value === "number"
                                    ? rep.value
                                    : 0,
                                unit: entry.unit,
                                provenance_citation: null,
                                last_modified_by: null,
                              })
                            }
                            className="rounded border border-indigo-200 px-2 py-0.5 text-xs text-indigo-600 hover:bg-indigo-50"
                          >
                            Flag
                          </button>
                        </div>
                      ) : (
                        <span
                          className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500"
                          aria-label="Not yet computed"
                        >
                          Not yet computed
                        </span>
                      )}
                    </td>
                  ))}
                  <td className="py-2 pr-3 text-xs text-gray-500">
                    {entry.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ThresholdFlagModal
        row={flagRow}
        onClose={() => setFlagRow(null)}
        onSubmit={handleFlagSubmit}
      />
    </section>
  );
}
```

- [ ] **Step 4: Run the tests — most should pass now**

Run: `npm test -- --run UnvalidatedMetricsPanel`
Expected: every test passes. The Flag-button test depends on `ThresholdFlagModal` rendering the `Flag threshold` title when invoked with a `section='unvalidated_metrics'` row — that already works because `ThresholdFlagModal` reads `row.section` as a string. **No `ThresholdFlagModal` changes required so far** — the modal is already key-agnostic.

If the test for the Flag button fails because the modal doesn't display the unvalidated row, proceed to Task 9 to confirm modal compatibility before debugging.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/UnvalidatedMetricsPanel.tsx frontend/src/components/__tests__/UnvalidatedMetricsPanel.test.tsx
git commit -m "feat(frontend): UnvalidatedMetricsPanel renders registry rows per analysis (L2-SAGITTAL-INFRA-04)"
```

---

### Task 9: Verify `ThresholdFlagModal` accepts `section='unvalidated_metrics'`

`ThresholdFlagModal` already reads `row.section` as a string and renders `{row.section}` with a `capitalize` class. After the Task 7 union widening, TypeScript accepts the new value. We need ONE test confirming the modal renders + submits for the new section.

**Files:**
- Modify: `frontend/src/components/__tests__/ThresholdFlagModal.test.tsx`

- [ ] **Step 1: Append a new section test**

Append to `frontend/src/components/__tests__/ThresholdFlagModal.test.tsx` (do NOT modify existing tests):

```tsx
describe("ThresholdFlagModal — unvalidated_metrics section (Session 3)", () => {
  it("renders the modal and submits a flag with section='unvalidated_metrics'", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(
      <ThresholdFlagModal
        row={{
          section: "unvalidated_metrics",
          key: "ankle_dorsiflexion_deg",
          value: 12.3,
          unit: "deg",
          provenance_citation: null,
          last_modified_by: null,
        }}
        onClose={onClose}
        onSubmit={onSubmit}
      />,
    );
    // Header renders the section name (capitalized via className).
    expect(screen.getByText("unvalidated_metrics")).toBeInTheDocument();
    // Key is rendered with the new metric name.
    expect(screen.getByText("ankle_dorsiflexion_deg")).toBeInTheDocument();

    // Fill the form to satisfy minimum lengths.
    fireEvent.change(screen.getByPlaceholderText(/Author year/i), {
      target: { value: "Smith 2023" },
    });
    fireEvent.change(
      screen.getByPlaceholderText(/Explain why the current value/i),
      {
        target: {
          value:
            "Current threshold absent; literature suggests 15 deg minimum.",
        },
      },
    );
    const valueInput = screen.getByRole("spinbutton");
    fireEvent.change(valueInput, { target: { value: "15.0" } });

    fireEvent.click(screen.getByRole("button", { name: /Submit flag/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const payload = onSubmit.mock.calls[0][0];
    expect(payload).toMatchObject({
      section: "unvalidated_metrics",
      key: "ankle_dorsiflexion_deg",
      proposed_value: 15.0,
    });
    expect(payload.proposed_citation.length).toBeGreaterThanOrEqual(5);
    expect(payload.rationale.length).toBeGreaterThanOrEqual(20);
  });
});
```

(Pull the existing imports — `render`, `screen`, `fireEvent`, `waitFor`, `vi`, `describe`, `it`, `expect`, `ThresholdFlagModal` — from the top of the file; do NOT redeclare them.)

- [ ] **Step 2: Run the test**

Run: `npm test -- --run ThresholdFlagModal`
Expected: existing tests stay green; the new test passes. **If the existing tests now fail because the modal's `row.section` type narrowed unexpectedly: STOP — the Task 7 union widening should be additive.**

- [ ] **Step 3: Commit (only if anything in `ThresholdFlagModal.tsx` had to change)**

```bash
git add frontend/src/components/ThresholdFlagModal.tsx frontend/src/components/__tests__/ThresholdFlagModal.test.tsx
git commit -m "test(frontend): ThresholdFlagModal accepts section='unvalidated_metrics'"
```

If only the test file changed, commit that file alone.

---

### Task 10: Mount `<UnvalidatedMetricsPanel />` on `ExpertAnalysisDetailPage`

**Files:**
- Modify: `frontend/src/pages/ExpertAnalysisDetailPage.tsx`
- Modify: `frontend/src/pages/__tests__/ExpertAnalysisDetailPage.test.tsx`

- [ ] **Step 1: Add the import**

In `ExpertAnalysisDetailPage.tsx`, add to the imports near the top:

```tsx
import UnvalidatedMetricsPanel from "@/components/UnvalidatedMetricsPanel";
```

- [ ] **Step 2: Mount the panel**

Just BEFORE the "Bottom: previous annotations + annotation form" section (search the file for `<PreviousAnnotations`), add:

```tsx
        {/* ------------------------------------------------------------------ */}
        {/* Unvalidated Metrics — Session 3 sagittal-view scaffold              */}
        {/* ------------------------------------------------------------------ */}
        <UnvalidatedMetricsPanel analysis={analysis} />
```

(Place the panel between the Coaching Output section and the Previous-Annotations section, matching the position called out in the design spec.)

- [ ] **Step 3: Add a page-level test**

Append to `frontend/src/pages/__tests__/ExpertAnalysisDetailPage.test.tsx`:

```tsx
describe("ExpertAnalysisDetailPage — UnvalidatedMetricsPanel mount (Session 3)", () => {
  it("renders the UnvalidatedMetricsPanel header below Coaching Output when an analysis loads", async () => {
    // Reuse the page test's existing _mockExpertSession + _mockAnalysis helpers.
    _mockExpertSession();
    _mockAnalysisFetch();
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue({
      entries: [
        {
          key_name: "depth_classification",
          display_label: "Depth Classification",
          unit: "",
          description: "Categorical relabel of squat depth.",
          exercise_applicability: ["squat"],
          computed_yet: false,
          in_scoring: false,
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/expert/analysis/abc-123"]}>
        <Routes>
          <Route
            path="/expert/analysis/:id"
            element={<ExpertAnalysisDetailPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/Unvalidated Metrics \(computed, pending expert validation\)/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Depth Classification")).toBeInTheDocument();
  });
});
```

(Adapt to whatever existing helpers `ExpertAnalysisDetailPage.test.tsx` exposes — `_mockExpertSession`, `_mockAnalysisFetch`, `expertApi` import, `MemoryRouter`, `Routes`, `Route`. Do NOT duplicate setup that the file already provides at module scope.)

- [ ] **Step 4: Run the page test**

Run: `npm test -- --run ExpertAnalysisDetailPage`
Expected: every existing test passes; the new test passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ExpertAnalysisDetailPage.tsx frontend/src/pages/__tests__/ExpertAnalysisDetailPage.test.tsx
git commit -m "feat(frontend): mount UnvalidatedMetricsPanel on ExpertAnalysisDetailPage (L2-SAGITTAL-INFRA-04)"
```

---

### Task 11: Full local verification

- [ ] **Step 1: Backend lint**

Run (from `backend/`):
```bash
uv run ruff check app tests
uv run pyright app
```
Expected: ruff `All checks passed`; pyright `0 errors`.

- [ ] **Step 2: Backend tests**

Run (from `backend/`):
```bash
uv run pytest tests/unit/test_sagittal_metrics_registry.py tests/unit/test_expert_sagittal_metrics_endpoint.py tests/unit/test_threshold_flag_service.py -x -v
uv run pytest tests/unit/ -x
```
Expected: new tests all pass; full unit suite stays green.

- [ ] **Step 3: Backend coverage on the new module**

Run: `uv run pytest tests/unit/test_sagittal_metrics_registry.py tests/unit/test_expert_sagittal_metrics_endpoint.py --cov=app.cv.sagittal_metrics_registry --cov=app.api.v1.expert --cov-report=term-missing`
Expected: ≥90% line coverage on `sagittal_metrics_registry.py` and the new endpoint function.

- [ ] **Step 4: Frontend typecheck + lint**

Run (from `frontend/`):
```bash
npx tsc --noEmit
npm run lint
```
Expected: 0 errors.

- [ ] **Step 5: Frontend tests**

Run (from `frontend/`):
```bash
npm test -- --run UnvalidatedMetricsPanel ExpertAnalysisDetailPage ThresholdFlagModal
npm test -- --run
```
Expected: targeted tests pass; full suite stays green.

- [ ] **Step 6: Confirm no test file mutation on pre-existing assertions**

Run: `git diff main -- backend/tests/unit/test_threshold_flag_service.py frontend/src/components/__tests__/ThresholdFlagModal.test.tsx frontend/src/pages/__tests__/ExpertAnalysisDetailPage.test.tsx`

The diff should only show **added** tests (or added imports). Existing assertion bodies must not change. **If a pre-existing assertion text was modified to make a test pass: STOP — that signals a broken invariant.**

---

### Task 12: Push + open `/team` cross-stack PR

- [ ] **Step 1: Push the branch**

Run: `git push -u origin feat/sagittal-metrics-scaffold`

- [ ] **Step 2: Open the PR via MCP**

Use `mcp__github__create_pull_request` with:

- `title`: `feat(cv-audit): Session 3 — sagittal metrics registry scaffold + UnvalidatedMetricsPanel`
- `head`: `feat/sagittal-metrics-scaffold`
- `base`: `main`
- `body` (HEREDOC):

```markdown
## Summary
Session 3 of the cv-audit effort (`docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-3).

Builds the rails Sessions 4-7 ride on: a 16-entry sagittal metrics registry on the backend, the expert-portal `<UnvalidatedMetricsPanel />` on the frontend, and a CHECK constraint extension so the existing `FR-EXPV-08` flagging workflow accepts the new `section='unvalidated_metrics'`.

No extraction logic yet — all 16 entries render "Not yet computed" after this PR. Sessions 4-7 will flip `computed_yet=True` per metric.

### Cross-stack team coordination
This is a `/team`-style cross-stack PR — backend (spelix-cv-engineer scope: registry, endpoint, schemas, migration, service bypass) + frontend (sonnet-frontend scope: panel, modal extension, page mount, expert.ts widening). The two sides communicate via the published API contract on `GET /api/v1/expert/sagittal-metrics-registry` — the Pydantic schemas in `expert_review.py` are the contract.

### Closed audit IDs
- `L2-SAGITTAL-INFRA-01` — registry module + schemas
- `L2-SAGITTAL-INFRA-02` — `GET /api/v1/expert/sagittal-metrics-registry`
- `L2-SAGITTAL-INFRA-03` — Alembic migration extending `threshold_flags.section` CHECK
- `L2-SAGITTAL-INFRA-04` — `<UnvalidatedMetricsPanel />` + `ExpertAnalysisDetailPage` mount + `ThresholdFlagModal` section widening

## Test plan
- [x] `uv run pytest tests/unit/test_sagittal_metrics_registry.py` — registry shape, key uniqueness, naming honesty
- [x] `uv run pytest tests/unit/test_expert_sagittal_metrics_endpoint.py` — endpoint auth (401/403/200), shape, 16 entries
- [x] `uv run pytest tests/integration/test_threshold_flags_section_check.py` — CHECK constraint accepts 5 sections, rejects typos
- [x] `npm test -- --run UnvalidatedMetricsPanel` — empty, partial, fully-computed, flag-button states
- [x] `npm test -- --run ExpertAnalysisDetailPage` — panel mounts on the page
- [x] `npm test -- --run ThresholdFlagModal` — accepts `section='unvalidated_metrics'`
- [x] `uv run ruff check app tests` + `uv run pyright app` — clean
- [x] `npx tsc --noEmit` + `npm run lint` — clean
- [x] Alembic upgrade + downgrade + re-upgrade — reversible
- [ ] `spelix-security-reviewer` PASS on `UnvalidatedMetricsPanel.tsx` header / subhead strings (post-CI gate)
- [ ] E2E via Playwright MCP after deploy — expert login → `/expert/analyses/<id>` → panel renders rows (post-merge)

## Migration head
`<NEW_HEAD>` (`threshold_flags_section_check`) — see `uv run alembic current` output.

## ADR
`ADR-SAGITTAL-METRICS-REGISTRY` appended to `decisions.md` in this PR (Task 14).
```

Capture the PR URL printed by the MCP response — it is required as chat-visible evidence.

---

### Task 13: CI gate + spelix-security-reviewer

- [ ] **Step 1: Watch PR-level CI**

Run: `gh pr checks <PR_NUMBER> --watch`
Expected: every PR-level check transitions to `pass` (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel + Vercel Preview Comments). Capture the final output for Session 3 DoD item 8a.

- [ ] **Step 2: Dispatch spelix-security-reviewer on the panel header strings**

Use the `Agent` tool with `subagent_type=spelix-security-reviewer`:

> Review `frontend/src/components/UnvalidatedMetricsPanel.tsx` for SaMD / FTC language compliance. Specifically check the panel header ("Unvalidated Metrics (computed, pending expert validation)"), subhead ("These metrics are computed but NOT YET scored. Validate against the video before flagging thresholds."), and the dynamic descriptions pulled from the sagittal_metrics_registry. Verify: (a) no "injury risk" / "injury prevention" / "safety score" anywhere, (b) "Movement Quality" is the only user-facing label for safety scores (not relevant here since these are unvalidated, but confirm panel doesn't accidentally introduce safety-score-like language), (c) the subhead correctly disclaims that values are unvalidated. Return PASS, PASS_WITH_FINDINGS, or CRITICAL — for CRITICAL, cite the exact string + replacement.

Capture the agent's output. **If CRITICAL, STOP per goal STOP clauses and route to remediation.**

- [ ] **Step 3: spelix-auditor on the PR diff (optional but recommended)**

Use `Agent` with `subagent_type=spelix-auditor`:

> Audit this PR against the audit reference (`docs/audit/cv-dimension-audit-2026-05-11.md`) — specifically that L2-SAGITTAL-INFRA-01..04 are addressed and no Part-1 frontal-plane vocabulary leaks into the registry keys / descriptions / panel strings. Return PASS, PASS_WITH_FINDINGS, or CRITICAL.

---

### Task 14: ADR + backend/CLAUDE.md update

**Files:**
- Modify: `decisions.md`
- Modify: `backend/CLAUDE.md`
- Modify: `backlog.md`

- [ ] **Step 1: Append ADR-SAGITTAL-METRICS-REGISTRY**

Append to `decisions.md`:

```markdown
## ADR-SAGITTAL-METRICS-REGISTRY — Frozenset as single source of truth for the 16 sagittal-view metrics

**Date:** 2026-05-22
**Status:** Accepted
**Cross-references:** ADR-AUDIT-2026-05-22, ADR-LIFTER-SIDE-DETECTION, ADR-LUMBAR-FLEXION-PROXY-NAMING (forward-ref Session 7)

### Context

The CV audit (`docs/audit/cv-dimension-audit-2026-05-11.md` Part-2) identified 16 sagittal-view metrics that the system can observe but doesn't compute. Sessions 4-7 will add the extractors. Before extractors land, both backend and frontend need a single, immutable list of (key_name, display_label, unit, description, exercise_applicability) so the expert portal can show "Not yet computed" rows that flip to "computed + flaggable" as each session ships.

Without a registry, backend extractors would write to JSONB keys the frontend doesn't know about, and the frontend panel would be a hardcoded list that drifts from reality.

### Decision

1. **Backend Python module is the source of truth.** `backend/app/cv/sagittal_metrics_registry.py` exposes `SAGITTAL_METRICS_REGISTRY: frozenset[SagittalMetricEntry]` with all 16 entries. Frozen dataclass, frozenset container — neither can be mutated at runtime.

2. **Expose via GET /api/v1/expert/sagittal-metrics-registry** (auth: expert_reviewer + admin). The frontend fetches the list on mount; no hardcoded duplicate.

3. **Sessions 4-7 only flip `computed_yet` and (for two metrics) `in_scoring` — they do NOT rename keys.** Key names are final. Renaming is a breaking change requiring a JSONB key migration.

4. **`threshold_flags.section` accepts `'unvalidated_metrics'` via the existing FR-EXPV-08 flow.** The 14 compute-only metrics inherit the expert-flagging workflow used for `squat`/`bench`/`deadlift`/`control` threshold values; the service short-circuits the v1-config current-value lookup when section is `unvalidated_metrics` (returns `current_value=0.0`, `current_citation=None`).

5. **Naming honesty in descriptions.** `lumbar_flexion_proxy_delta_deg` description explicitly disclaims it is not lumbar-isolated (R4 mitigation). `bar_path_classification` description names "Heuristic v0 — expect post-onboarding refinement" (R5 mitigation). `technique_consistency_std` description identifies it as a std-dev derivative.

6. **No metric extraction, scoring, or coaching prompt changes ship in Session 3.** The panel renders empty rows; the LLM is not yet given new context.

### Consequences

- Adding a metric in Sessions 4-7 = three places: (a) extractor in `metric_extraction.py`, (b) flip `computed_yet=True` in the registry, (c) integration test asserting the key appears in `rep_metrics`. Frontend automatically picks up the new computed status via the registry response.
- A drifted registry (entry exists but no extractor) silently shows "Not yet computed" — no crash, no missing data. Safe-by-default.
- Threshold flagging the new metrics requires no schema changes for Sessions 4-7 — the section is already in the CHECK constraint.
```

- [ ] **Step 2: Append backend/CLAUDE.md gotcha**

Append under `## Backend Gotchas`:

```markdown
### Sagittal metrics registry pattern (Session 3, ADR-SAGITTAL-METRICS-REGISTRY)
The 16 sagittal-view metrics that Sessions 4-7 populate live in `backend/app/cv/sagittal_metrics_registry.py` as a `frozenset[SagittalMetricEntry]`. Key names are FINAL — renaming is a breaking change requiring a JSONB-key migration. To add a new sagittal metric in Sessions 4-7: (a) write the extractor in `metric_extraction.py`, (b) flip `computed_yet=True` on the existing registry entry (do NOT add new entries — the 16 are fixed), (c) add an integration test asserting the key shows up in `rep_metrics.metrics`. Auto-flow scoring metrics (Session 4: `depth_classification`, `ecc_con_ratio`) also flip `in_scoring=True` and require a new branch in `scoring.py` + threshold config entry. The expert portal renders "Not yet computed" for every entry where `computed_yet=False`; no panel changes needed per-metric. Threshold flagging for these metrics flows through the existing FR-EXPV-08 path (`section='unvalidated_metrics'`); the service bypasses the v1-config current-value lookup for this section.
```

- [ ] **Step 3: Update backlog.md**

Add four rows to `backlog.md` (use `/backlog` if available, or append directly):

```markdown
- L2-SAGITTAL-INFRA-01 — Registry module + Pydantic schemas — done (commit <SHA>)
- L2-SAGITTAL-INFRA-02 — GET /api/v1/expert/sagittal-metrics-registry — done (commit <SHA>)
- L2-SAGITTAL-INFRA-03 — Alembic migration extending threshold_flags.section CHECK — done (commit <SHA>)
- L2-SAGITTAL-INFRA-04 — UnvalidatedMetricsPanel + ExpertAnalysisDetailPage mount + ThresholdFlagModal extension — done (commit <SHA>)
```

- [ ] **Step 4: Commit**

```bash
git add decisions.md backend/CLAUDE.md backlog.md
git commit -m "docs(adr,claude.md,backlog): ADR-SAGITTAL-METRICS-REGISTRY + registry-pattern gotcha (Session 3)"
git push
```

(Push without re-opening the PR — adding commits to the existing branch updates it.)

---

### Task 15: Merge + post-deploy verification

- [ ] **Step 1: Re-watch CI**

Run: `gh pr checks <PR_NUMBER> --watch`
Expected: all PR-level checks pass after the ADR + docs commit.

- [ ] **Step 2: Merge via MCP**

Use `mcp__github__merge_pull_request`:
- `pullNumber`: `<PR_NUMBER>`
- `mergeMethod`: `"merge"` (NEVER squash — Standing Rule #3)

Capture the response — confirm `merged: true` for Session 3 DoD item 9.

- [ ] **Step 3: Watch Deploy to Production on main**

Get the main-branch run ID:
```bash
gh run list --branch main --limit 1
```

Then:
```bash
gh run watch <RUN_ID>
```
Or:
```bash
gh run view <RUN_ID> --json jobs --jq '.jobs[] | select(.name=="Deploy to Production") | .conclusion'
```

Expected: `success`. Capture the output for Session 3 DoD item 8b.

- [ ] **Step 4: Verify droplet HEAD matches merge SHA**

Run: `ssh spelix-droplet "git log --oneline -1"`
Expected: prints the merge commit SHA returned from Task 15.2. Capture the output for Session 3 DoD item 10.

- [ ] **Step 5: Verify container health**

Run: `ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"`
Expected: all containers show `(healthy)`. If any is `unhealthy`, check `docker logs` before proceeding to E2E.

---

### Task 16: E2E verification via Playwright MCP

- [ ] **Step 1: Navigate to spelix.app**

Use `mcp__playwright__browser_navigate`:
- `url`: `https://spelix.app/login`

- [ ] **Step 2: Login as expert_reviewer**

Use the expert-test account (see project README + `.env.local` for credentials; never hardcode in this plan). After login, capture the session.

- [ ] **Step 3: Navigate to an analysis with completed pose data**

The handoff lists known squat fixture analyses. Pick one with `rep_metrics` populated. Navigate to `/expert/analysis/<id>`:
- `mcp__playwright__browser_navigate` to the URL.

- [ ] **Step 4: Snapshot the page + scroll to the panel**

Use `mcp__playwright__browser_snapshot` — confirm the "Unvalidated Metrics (computed, pending expert validation)" header appears.

- [ ] **Step 5: Count "Not yet computed" badges**

Use `mcp__playwright__browser_evaluate`:
```js
() => document.querySelectorAll('[aria-label="Not yet computed"]').length
```
Expected: a positive number — the exact count is `(applicable_metrics_for_exercise) × (rep_count)`. For a 2-rep squat that's 11 × 2 = 22 (11 squat-applicable entries × 2 reps). The DoD calls for "16 'Not yet computed' rows" — interpret this as 16 entries shown (after exercise-applicability filter, at minimum some rows visible; the panel only renders applicable rows).

- [ ] **Step 6: Take a screenshot**

Use `mcp__playwright__browser_take_screenshot`:
- `filename`: `phase-cv-audit-session3-unvalidated-panel.png`
- Save under `e2e/screenshots/`.

Print the file path for Session 3 DoD item 11.

- [ ] **Step 7: Check console + network for errors**

Use `mcp__playwright__browser_console_messages` filtered by `level=error` — expected: empty.
Use `mcp__playwright__browser_network_requests` — expected: `GET /api/v1/expert/sagittal-metrics-registry` returns 200; no 4xx / 5xx on the analysis flow.

---

### Task 17: Master manifest + handoff updates

**Files:**
- Modify: `docs/superpowers/goals/2026-05-22-cv-audit-master.md`
- Modify: `.claude/handoff.md`

- [ ] **Step 1: Flip master manifest**

In `docs/superpowers/goals/2026-05-22-cv-audit-master.md`:
- Session Status Overview table: row 3 `Status` → `complete`, `Commit SHA` → `<merge_sha>`, `PR` → `#<PR_NUMBER>`.
- Session Status Overview table: row 4 `Status` → `active`.
- Session 3 section header: status → `complete (merged 2026-05-22; merge SHA <sha>; PR #<num>)`.
- Session 3 Completion checklist: tick every box.

- [ ] **Step 2: Rewrite `.claude/handoff.md`**

Replace with a Session-4-launch handoff:

```markdown
# cv-audit handoff — Session 3 → Session 4

## Status
- **Session 3:** complete — merge SHA `<sha>`, PR #<num>
- **Next session:** Session 4 — Trivial metrics (auto-flow scoring)
- **Launch command:** see `docs/superpowers/goals/2026-05-22-cv-audit-master.md` §Session-4 "Launch command" block — copy verbatim into `/goal`. **Note:** the Session 4 plan at `docs/superpowers/plans/2026-05-22-session-4-trivial-metrics.md` is a SKELETON; invoke `superpowers:writing-plans` to expand before launching `/goal`.

## Completed this session
- <SHA> feat(cv): add sagittal_metrics_registry frozenset (L2-SAGITTAL-INFRA-01)
- <SHA> feat(schemas): add SagittalMetricRegistry response schemas
- <SHA> feat(api): GET /expert/sagittal-metrics-registry returns 16-entry registry (L2-SAGITTAL-INFRA-02)
- <SHA> feat(schemas): allow section='unvalidated_metrics' on ThresholdFlagCreate
- <SHA> feat(db): add CHECK constraint on threshold_flags.section (L2-SAGITTAL-INFRA-03)
- <SHA> feat(api): add sagittal-metrics-registry client + widen ThresholdSection
- <SHA> feat(frontend): UnvalidatedMetricsPanel renders registry rows per analysis (L2-SAGITTAL-INFRA-04)
- <SHA> test(frontend): ThresholdFlagModal accepts section='unvalidated_metrics'
- <SHA> feat(frontend): mount UnvalidatedMetricsPanel on ExpertAnalysisDetailPage
- <SHA> docs(adr,claude.md,backlog): ADR-SAGITTAL-METRICS-REGISTRY + registry-pattern gotcha

## Surfaced evidence
- PR: https://github.com/atharva6905/spelix/pull/<num>
- PR-level CI: all 6 checks `pass`
- Post-merge CI: main-branch run <run_id>, Deploy to Production conclusion=`success`
- Migration head: `<new_head>`
- E2E screenshot: `e2e/screenshots/phase-cv-audit-session3-unvalidated-panel.png`
- spelix-security-reviewer: PASS (or PASS_WITH_FINDINGS — no CRITICAL)

## Blockers
- None.

## Open items for follow-up sessions
- Session 4 implements the first 4 metrics (depth_classification, ecc_con_ratio, pause_duration_s, lockout_torso_lean_deg) and wires the first two into scoring.
- Sessions 5-7 implement the remaining 12 compute-only metrics.

## Resume guidance for Session 4
1. Read `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-4.
2. Read this handoff + the master manifest's §Session-4 launch command.
3. **The Session 4 plan is a skeleton.** Invoke `superpowers:writing-plans` to expand. Commit the expansion via PR before launching `/goal`.
4. Issue `/goal` with the Session 4 launch command from the master manifest.

## Next /goal launch command (copy verbatim)

(Copy from master manifest §Session-4.)
```

- [ ] **Step 3: Commit**

```bash
git checkout main
git pull --ff-only
git checkout -b docs/session-3-close
git add docs/superpowers/goals/2026-05-22-cv-audit-master.md .claude/handoff.md
git commit -m "docs(session-3-close): mark Session 3 complete, write Session 4 handoff"
git push -u origin docs/session-3-close
```

Open a small docs PR (`mcp__github__create_pull_request`) — title: `docs(session-3-close): mark Session 3 complete`. Merge after CI green.

(Alternative: piggyback the manifest + handoff diff onto the main Session 3 PR's final commit before merge. Either works; the docs-PR pattern matches Session 2's flow.)

---

## Acceptance criteria — Session 3 DoD recap

Every item below must be surfaced as chat-visible evidence:

- [x] `sagittal_metrics_registry.py` 16-entry frozenset committed (git diff printed via Task 2/12).
- [x] `GET /api/v1/expert/sagittal-metrics-registry` exists; OpenAPI shape printed (Task 4.5); test file path `backend/tests/unit/test_expert_sagittal_metrics_endpoint.py` printed.
- [x] Backend tests: `uv run pytest ... test_sagittal_metrics_registry.py ... test_expert_sagittal_metrics_endpoint.py` printed all-passing.
- [x] Alembic migration extends/adds `threshold_flags.section` CHECK; `uv run alembic current` printed showing new head.
- [x] `<UnvalidatedMetricsPanel />` in `ExpertAnalysisDetailPage.tsx`; `ThresholdFlagModal` extended; git diff printed (Tasks 8-10).
- [x] Frontend tests: `npm test -- --run UnvalidatedMetricsPanel ExpertAnalysisDetailPage` printed all-passing.
- [x] PR via `mcp__github__create_pull_request`; description names cross-stack team coordination.
- [x] CI: `gh pr checks <PR>` shows all PR-level pass; `gh run watch <main-run-id>` (or `gh run view`) shows Deploy to Production conclusion=`success`.
- [x] `mcp__github__merge_pull_request` with `merge_method="merge"`; merged=true.
- [x] SSH `git log --oneline -1` on `spelix-droplet` matches merge SHA.
- [x] E2E via Playwright MCP: expert login → `/expert/analysis/<id>` → panel renders rows; screenshot path printed.
- [x] `ADR-SAGITTAL-METRICS-REGISTRY` appended to `decisions.md`.
- [x] `backend/CLAUDE.md` registry-pattern section appended.
- [x] `spelix-security-reviewer` PASS or PASS_WITH_FINDINGS (no CRITICAL).
- [x] Master manifest updated; Session 4 active; `.claude/handoff.md` updated.

---

## STOP triggers (per goal manifest)

Halt and escalate per Remediation Policy if ANY:
- 40 turns elapsed
- Same error 3 consecutive turns
- External input required
- CI red after 2 retries
- `spelix-security-reviewer` returns CRITICAL on panel header text
- A migration cannot be reverted cleanly

Recursion cap: 2 remediation attempts.

---

## Just-in-time expansion checklist (already applied)

- [x] Preserved skeleton task ordering: 17 tasks, branch → registry → schemas → endpoint → flag-create extension → migration → frontend types → panel → modal verify → page mount → local verify → push+PR → CI + security reviewer → ADR + docs → merge + deploy → E2E → manifest + handoff.
- [x] Preserved gates: TDD red-then-green at every implementation step, ≥90% coverage on new modules, no quality-gate lowering, no squash-merge, no force-push, security-reviewer gate before merge.
- [x] Preserved file lists: same files to create / modify as skeleton.
- [x] Added concrete pytest test bodies (test_sagittal_metrics_registry.py: 16 tests; test_expert_sagittal_metrics_endpoint.py: 7 tests; integration migration test).
- [x] Added concrete vitest test bodies (UnvalidatedMetricsPanel.test.tsx: 7 tests; ThresholdFlagModal addendum: 1 test; ExpertAnalysisDetailPage addendum: 1 test).
- [x] Added exact git commit messages per task.
- [x] Added explicit STOP conditions per goal manifest.
