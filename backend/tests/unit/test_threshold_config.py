"""
Unit tests for ThresholdConfig v1 loader.

Requirements: FR-SCOR-11 (Phase 1), FR-SCOR-00 (v0 backward compat)

Tests the nested value unwrapping, citation access, scoring weights,
phase multipliers, and backward compatibility with v0 flat values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import ThresholdConfig

# tests/unit/ → backend/ → spelix/ (repo root where config/ lives)
_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_V0_PATH = _REPO_ROOT / "config" / "thresholds_v0.json"
_V1_PATH = _REPO_ROOT / "config" / "thresholds_v1.json"


# ---------------------------------------------------------------------------
# v1 default loading
# ---------------------------------------------------------------------------


class TestThresholdConfigV1:
    """ThresholdConfig v1 — nested objects with provenance."""

    def test_loads_v1_version(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.version == "v1"

    def test_get_unwraps_nested_value(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "depth_parallel_hip_angle_deg") == 90.0

    def test_get_raw_returns_full_dict(self) -> None:
        cfg = ThresholdConfig()
        raw = cfg.get_raw("squat", "depth_parallel_hip_angle_deg")
        assert isinstance(raw, dict)
        assert raw["value"] == 90.0
        assert raw["unit"] == "degrees"
        assert "provenance_citation" in raw
        assert "last_modified_by" in raw

    def test_get_citation(self) -> None:
        cfg = ThresholdConfig()
        assert "Schoenfeld" in cfg.get_citation(
            "squat", "depth_parallel_hip_angle_deg"
        )

    def test_get_citation_returns_none_for_flat_section(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get_citation("scoring_weights", "movement_quality") is None

    # --- Exercise thresholds match v0 values ---

    @pytest.mark.parametrize(
        "section,key,expected",
        [
            ("squat", "depth_parallel_hip_angle_deg", 90.0),
            ("deadlift", "hip_hinge_min_deg", 70.0),
            ("deadlift", "bar_drift_caution_cm", 5.0),
            ("experience_tolerance", "beginner_deg", 3.0),
            ("experience_tolerance", "intermediate_deg", 4.0),
            ("experience_tolerance", "advanced_deg", 5.0),
        ],
    )
    def test_v1_values_match_v0_defaults(
        self, section: str, key: str, expected: float
    ) -> None:
        cfg = ThresholdConfig()
        assert cfg.get(section, key) == expected

    # --- FR-SCOR-05: scoring weights ---

    def test_scoring_weights_sum_to_one(self) -> None:
        cfg = ThresholdConfig()
        total = sum(
            cfg.get("scoring_weights", k)
            for k in ("movement_quality", "technique", "path_balance", "control")
        )
        assert abs(total - 1.0) < 1e-9

    def test_scoring_weights_values(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("scoring_weights", "movement_quality") == 0.40
        assert cfg.get("scoring_weights", "technique") == 0.30
        assert cfg.get("scoring_weights", "path_balance") == 0.20
        assert cfg.get("scoring_weights", "control") == 0.10

    # --- FR-SCOR-07: score descriptors ---

    def test_score_descriptor_boundaries(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("score_descriptors", "elite_min") == 9.0
        assert cfg.get("score_descriptors", "advanced_min") == 7.5
        assert cfg.get("score_descriptors", "intermediate_min") == 5.0
        assert cfg.get("score_descriptors", "needs_work_min") == 3.0

    def test_score_descriptor_boundaries_ordered(self) -> None:
        cfg = ThresholdConfig()
        elite = cfg.get("score_descriptors", "elite_min")
        advanced = cfg.get("score_descriptors", "advanced_min")
        intermediate = cfg.get("score_descriptors", "intermediate_min")
        needs_work = cfg.get("score_descriptors", "needs_work_min")
        assert elite > advanced > intermediate > needs_work

    # --- FR-CVPL-23: phase multipliers ---

    def test_phase_multipliers(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("phase_multipliers", "static_peak") == 1.0
        assert cfg.get("phase_multipliers", "transition") == 0.90

    def test_phase_multiplier_high_occlusion(self) -> None:
        cfg = ThresholdConfig()
        occlusion = cfg.get("phase_multipliers", "high_occlusion")
        assert isinstance(occlusion, dict)
        assert occlusion["squat_deep_hip_fold"] == 0.75
        assert occlusion["bench_supine"] == 0.80

    # --- FR-CVPL-22: confidence landmark weights ---

    def test_confidence_landmark_weights_squat(self) -> None:
        cfg = ThresholdConfig()
        squat = cfg.get_section("confidence_landmark_weights")["squat"]
        # Primary landmarks (hips/knees/ankles) weighted 1.0
        assert squat["23"] == 1.0
        assert squat["25"] == 1.0
        # Shoulders weighted lower
        assert squat["11"] == 0.5

    def test_confidence_landmark_weights_bench(self) -> None:
        cfg = ThresholdConfig()
        bench = cfg.get_section("confidence_landmark_weights")["bench"]
        # Primary (shoulders/elbows/wrists) weighted 1.0
        assert bench["11"] == 1.0
        assert bench["13"] == 1.0
        # Hips weighted lower
        assert bench["23"] == 0.5

    # --- Error handling ---

    def test_unknown_section_raises(self) -> None:
        cfg = ThresholdConfig()
        with pytest.raises(KeyError, match="Unknown section"):
            cfg.get("nonexistent", "key")

    def test_unknown_key_raises(self) -> None:
        cfg = ThresholdConfig()
        with pytest.raises(KeyError, match="Unknown threshold key"):
            cfg.get("squat", "nonexistent_key")

    # --- all_for_exercise backward compat ---

    def test_all_for_exercise_returns_copy(self) -> None:
        cfg = ThresholdConfig()
        section = cfg.all_for_exercise("squat")
        assert "depth_parallel_hip_angle_deg" in section
        # Mutating the copy should not affect the original
        section["new_key"] = "test"
        assert "new_key" not in cfg.all_for_exercise("squat")


# ---------------------------------------------------------------------------
# v0 backward compatibility
# ---------------------------------------------------------------------------


class TestThresholdConfigV0:
    """ThresholdConfig v0 — flat values, no provenance."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_v0(self) -> None:
        if not _V0_PATH.exists():
            pytest.skip("thresholds_v0.json not present")

    def test_loads_v0_version(self) -> None:
        cfg = ThresholdConfig(path=_V0_PATH)
        assert cfg.version == "v0"

    def test_v0_get_returns_flat_value(self) -> None:
        cfg = ThresholdConfig(path=_V0_PATH)
        assert cfg.get("squat", "depth_parallel_hip_angle_deg") == 90

    def test_v0_get_citation_returns_none(self) -> None:
        cfg = ThresholdConfig(path=_V0_PATH)
        assert cfg.get_citation("squat", "depth_parallel_hip_angle_deg") is None

    def test_v0_get_raw_returns_flat_value(self) -> None:
        cfg = ThresholdConfig(path=_V0_PATH)
        raw = cfg.get_raw("squat", "depth_parallel_hip_angle_deg")
        assert raw == 90


# ---------------------------------------------------------------------------
# ThresholdConfig does not retroactively change
# ---------------------------------------------------------------------------


class TestThresholdVersionFrozen:
    """FR-SCOR-11: threshold_version is frozen at analysis time."""

    def test_version_string_is_v1(self) -> None:
        """Default config returns 'v1' — this is what gets written to analyses."""
        cfg = ThresholdConfig()
        assert cfg.version == "v1"

    def test_explicit_v0_path_returns_v0(self) -> None:
        """If an analysis was run with v0, its threshold_version should say 'v0'."""
        if not _V0_PATH.exists():
            pytest.skip("thresholds_v0.json not present")
        cfg = ThresholdConfig(path=_V0_PATH)
        assert cfg.version == "v0"


# ---------------------------------------------------------------------------
# cv-audit cleanup 2026-05-22 — deferred_multi_camera relocation
# ---------------------------------------------------------------------------


class TestThresholdsCvAuditCleanup:
    """Per docs/audit/cv-dimension-audit-2026-05-11.md items B-1 through B-5,
    frontal-plane threshold entries that no scoring code reads are relocated
    to a ``deferred_multi_camera`` subsection in ``thresholds_v1.json``. The
    Phase 0 snapshot ``thresholds_v0.json`` deletes them outright.
    """

    def test_v1_has_deferred_multi_camera_subsection(self) -> None:
        import json

        with _V1_PATH.open() as f:
            cfg = json.load(f)
        assert "deferred_multi_camera" in cfg
        deferred = cfg["deferred_multi_camera"]
        # squat group
        assert "knee_valgus_caution_deg" in deferred.get("squat", {})
        assert "knee_valgus_high_deg" in deferred.get("squat", {})
        assert "lumbar_flexion_caution_deg" in deferred.get("squat", {})
        assert "lumbar_flexion_high_deg" in deferred.get("squat", {})
        assert "toe_out_nominal_deg" in deferred.get("squat", {})
        assert "toe_out_tolerance_deg" in deferred.get("squat", {})
        # bench group
        assert "elbow_flare_caution_deg" in deferred.get("bench", {})
        assert "elbow_flare_high_deg" in deferred.get("bench", {})
        assert "grip_width_biacromial_ratio_max" in deferred.get("bench", {})
        assert "wrist_alignment_tolerance_deg" in deferred.get("bench", {})
        # deadlift group
        assert "lumbar_flexion_caution_deg" in deferred.get("deadlift", {})
        assert "lumbar_flexion_high_deg" in deferred.get("deadlift", {})

    def test_v1_deferred_entries_preserve_citations(self) -> None:
        """Each relocated entry preserves value + unit + provenance_citation."""
        import json

        with _V1_PATH.open() as f:
            cfg = json.load(f)
        entry = cfg["deferred_multi_camera"]["squat"]["knee_valgus_caution_deg"]
        assert entry["value"] == 5.0
        assert entry["unit"] == "degrees"
        assert "provenance_citation" in entry
        assert entry["provenance_citation"]  # non-empty

    def test_v1_active_sections_have_no_unmeasurable_keys(self) -> None:
        """Active squat/bench/deadlift sections must not contain frontal-plane keys."""
        import json

        with _V1_PATH.open() as f:
            cfg = json.load(f)
        forbidden = {
            "knee_valgus_caution_deg",
            "knee_valgus_high_deg",
            "lumbar_flexion_caution_deg",
            "lumbar_flexion_high_deg",
            "elbow_flare_caution_deg",
            "elbow_flare_high_deg",
            "grip_width_biacromial_ratio_max",
            "wrist_alignment_tolerance_deg",
            "toe_out_nominal_deg",
            "toe_out_tolerance_deg",
        }
        for section_name in ("squat", "bench", "deadlift"):
            section = cfg.get(section_name, {})
            for key in section:
                assert key not in forbidden, (
                    f"{section_name}.{key} is unmeasurable from sagittal view — "
                    f"move to deferred_multi_camera."
                )

    def test_v0_has_no_unmeasurable_keys(self) -> None:
        """v0 frozen snapshot deletes the dead entries outright."""
        if not _V0_PATH.exists():
            pytest.skip("thresholds_v0.json not present")
        import json

        with _V0_PATH.open() as f:
            cfg = json.load(f)
        forbidden = {
            "knee_valgus_caution_deg",
            "knee_valgus_high_deg",
            "lumbar_flexion_caution_deg",
            "lumbar_flexion_high_deg",
            "elbow_flare_caution_deg",
            "elbow_flare_high_deg",
            "grip_width_biacromial_ratio_max",
            "wrist_alignment_tolerance_deg",
        }
        for section_name in ("squat", "bench", "deadlift"):
            section = cfg.get(section_name, {})
            for key in section:
                assert key not in forbidden, (
                    f"{section_name}.{key} should be deleted in v0 snapshot."
                )
