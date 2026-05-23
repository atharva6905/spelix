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
            # Session 5 (7 design entries -- heel_rise_flag is a companion key
            # written alongside ankle_dorsiflexion_deg, not a separate row).
            "ankle_dorsiflexion_deg",
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
# Computed / scoring flags — Session 4 invariant: 4 computed, 2 in_scoring
# ---------------------------------------------------------------------------


_SESSION_4_COMPUTED_KEYS = frozenset({
    "depth_classification",
    "ecc_con_ratio",
    "pause_duration_s",
    "lockout_torso_lean_deg",
})

_SESSION_4_IN_SCORING_KEYS = frozenset({
    "depth_classification",
    "ecc_con_ratio",
})


class TestSessionFourFlags:
    def test_session4_computed_yet_flipped(self) -> None:
        entries = {e.key_name: e for e in SAGITTAL_METRICS_REGISTRY}
        for key in _SESSION_4_COMPUTED_KEYS:
            assert entries[key].computed_yet is True, (
                f"Entry {key!r} should have computed_yet=True after Session 4."
            )

    def test_session4_in_scoring_flipped(self) -> None:
        entries = {e.key_name: e for e in SAGITTAL_METRICS_REGISTRY}
        for key in _SESSION_4_IN_SCORING_KEYS:
            assert entries[key].in_scoring is True, (
                f"Entry {key!r} should have in_scoring=True after Session 4."
            )

    def test_compute_only_session4_metrics_stay_out_of_scoring(self) -> None:
        entries = {e.key_name: e for e in SAGITTAL_METRICS_REGISTRY}
        for key in _SESSION_4_COMPUTED_KEYS - _SESSION_4_IN_SCORING_KEYS:
            assert entries[key].in_scoring is False, (
                f"Entry {key!r} is compute-only — in_scoring must be False."
            )

    def test_session_6_plus_entries_remain_pristine(self) -> None:
        """Guard: only Sessions 4-5 metrics flip; Sessions 6-7 entries
        keep computed_yet=False and in_scoring=False until their own session.
        Session 5 keys were narrowed out of this guard in Session 5 when
        their extractors were implemented."""
        entries = {e.key_name: e for e in SAGITTAL_METRICS_REGISTRY}
        for key in (
            "bar_to_hip_distance", "shoulder_protraction_proxy_px",
            "lumbar_flexion_proxy_delta_deg", "bar_path_classification",
            "technique_consistency_std",
        ):
            assert entries[key].computed_yet is False, (
                f"Entry {key!r} must stay computed_yet=False (Session 6+ scope)."
            )
            assert entries[key].in_scoring is False, (
                f"Entry {key!r} must stay in_scoring=False (Session 6+ scope)."
            )


class TestRegistrySession5Flips:
    SESSION5_KEYS = frozenset({
        "ankle_dorsiflexion_deg",
        "wrist_alignment_deg",
        "bar_touch_height_pct",
        "setup_shoulder_x_offset",
        "shin_angle_deg",
        "setup_knee_angle_deg",
        "arch_deg",
    })

    def test_session5_entries_have_computed_yet_true(self) -> None:
        flipped = {
            e.key_name for e in SAGITTAL_METRICS_REGISTRY
            if e.key_name in self.SESSION5_KEYS and e.computed_yet
        }
        assert flipped == self.SESSION5_KEYS, (
            f"Missing flips: {self.SESSION5_KEYS - flipped}"
        )

    def test_session5_entries_remain_out_of_scoring(self) -> None:
        in_scoring = {
            e.key_name for e in SAGITTAL_METRICS_REGISTRY
            if e.key_name in self.SESSION5_KEYS and e.in_scoring
        }
        # Per design Section-4: Session 5 metrics are compute-only.
        assert in_scoring == frozenset(), (
            f"These Session 5 keys are unexpectedly in scoring: {in_scoring}"
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
        assert (
            "std" in lower or "standard deviation" in lower or "consistency" in lower
        )


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


# ---------------------------------------------------------------------------
# Pydantic schema round-trip (Session 3, schema task)
# ---------------------------------------------------------------------------


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
