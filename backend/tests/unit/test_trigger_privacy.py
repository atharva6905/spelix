"""Tests for TriggerPrivacyService — FR-BRAIN-10.

TDD gate for P2-028.

Covers:
- Height bins: <165 → short, 165-180 → average, >180 → tall
- Weight bins: <70 → light, 70-90 → moderate, >90 → heavy
- Limb ratio bins based on femur/height ratio
- Experience passthrough / normalization
- build_trigger_tags always includes exercise tag
- build_trigger_tags never contains raw numeric values
- build_trigger_tags omits None body proportion fields
- build_trigger_tags includes additional_tags
- check_group_size: 19 → False, 20 → True, 100 → True
- Boundary values exactly at bin edges
"""

from __future__ import annotations

import re


from app.services.trigger_privacy import TriggerPrivacyService


# ---------------------------------------------------------------------------
# Height binning
# ---------------------------------------------------------------------------


class TestCategorizeHeight:
    def test_below_165_is_short(self) -> None:
        assert TriggerPrivacyService.categorize_height(160.0) == "short"

    def test_above_180_is_tall(self) -> None:
        assert TriggerPrivacyService.categorize_height(185.0) == "tall"

    def test_165_is_average(self) -> None:
        # boundary: exactly 165 cm is the lower edge of "average"
        assert TriggerPrivacyService.categorize_height(165.0) == "average"

    def test_180_is_average(self) -> None:
        # boundary: exactly 180 cm is the upper edge of "average"
        assert TriggerPrivacyService.categorize_height(180.0) == "average"

    def test_just_below_165_is_short(self) -> None:
        assert TriggerPrivacyService.categorize_height(164.9) == "short"

    def test_just_above_180_is_tall(self) -> None:
        assert TriggerPrivacyService.categorize_height(180.1) == "tall"

    def test_midrange_is_average(self) -> None:
        assert TriggerPrivacyService.categorize_height(172.0) == "average"

    def test_very_short(self) -> None:
        assert TriggerPrivacyService.categorize_height(140.0) == "short"

    def test_very_tall(self) -> None:
        assert TriggerPrivacyService.categorize_height(210.0) == "tall"


# ---------------------------------------------------------------------------
# Weight binning
# ---------------------------------------------------------------------------


class TestCategorizeWeight:
    def test_below_70_is_light(self) -> None:
        assert TriggerPrivacyService.categorize_weight(65.0) == "light"

    def test_above_90_is_heavy(self) -> None:
        assert TriggerPrivacyService.categorize_weight(100.0) == "heavy"

    def test_70_is_moderate(self) -> None:
        # boundary: exactly 70 kg is lower edge of "moderate"
        assert TriggerPrivacyService.categorize_weight(70.0) == "moderate"

    def test_90_is_moderate(self) -> None:
        # boundary: exactly 90 kg is upper edge of "moderate"
        assert TriggerPrivacyService.categorize_weight(90.0) == "moderate"

    def test_just_below_70_is_light(self) -> None:
        assert TriggerPrivacyService.categorize_weight(69.9) == "light"

    def test_just_above_90_is_heavy(self) -> None:
        assert TriggerPrivacyService.categorize_weight(90.1) == "heavy"

    def test_midrange_is_moderate(self) -> None:
        assert TriggerPrivacyService.categorize_weight(80.0) == "moderate"

    def test_very_light(self) -> None:
        assert TriggerPrivacyService.categorize_weight(45.0) == "light"

    def test_very_heavy(self) -> None:
        assert TriggerPrivacyService.categorize_weight(150.0) == "heavy"


# ---------------------------------------------------------------------------
# Limb ratio binning (femur / height)
# ---------------------------------------------------------------------------


class TestCategorizeLimbRatio:
    """Femur-to-height ratio bins.

    Short-limbed: ratio < 0.26
    Proportional: 0.26 <= ratio <= 0.30
    Long-limbed: ratio > 0.30
    """

    def test_low_ratio_is_short_limbed(self) -> None:
        # femur=40cm, height=180cm → ratio=0.222
        assert TriggerPrivacyService.categorize_limb_ratio(40.0, 180.0) == "short_limbed"

    def test_high_ratio_is_long_limbed(self) -> None:
        # femur=58cm, height=180cm → ratio=0.322
        assert TriggerPrivacyService.categorize_limb_ratio(58.0, 180.0) == "long_limbed"

    def test_mid_ratio_is_proportional(self) -> None:
        # femur=50cm, height=180cm → ratio=0.278
        assert TriggerPrivacyService.categorize_limb_ratio(50.0, 180.0) == "proportional"

    def test_boundary_lower_edge_proportional(self) -> None:
        # ratio exactly 0.26 → proportional
        femur = 0.26 * 180.0
        assert TriggerPrivacyService.categorize_limb_ratio(femur, 180.0) == "proportional"

    def test_boundary_upper_edge_proportional(self) -> None:
        # ratio exactly 0.30 → proportional
        femur = 0.30 * 180.0
        assert TriggerPrivacyService.categorize_limb_ratio(femur, 180.0) == "proportional"

    def test_just_below_lower_edge_is_short_limbed(self) -> None:
        # ratio 0.259 → short_limbed
        femur = 0.259 * 180.0
        assert TriggerPrivacyService.categorize_limb_ratio(femur, 180.0) == "short_limbed"

    def test_just_above_upper_edge_is_long_limbed(self) -> None:
        # ratio 0.301 → long_limbed
        femur = 0.301 * 180.0
        assert TriggerPrivacyService.categorize_limb_ratio(femur, 180.0) == "long_limbed"


# ---------------------------------------------------------------------------
# Experience passthrough / normalization
# ---------------------------------------------------------------------------


class TestCategorizeExperience:
    def test_beginner_passthrough(self) -> None:
        assert TriggerPrivacyService.categorize_experience("beginner") == "beginner"

    def test_intermediate_passthrough(self) -> None:
        assert TriggerPrivacyService.categorize_experience("intermediate") == "intermediate"

    def test_advanced_passthrough(self) -> None:
        assert TriggerPrivacyService.categorize_experience("advanced") == "advanced"

    def test_elite_passthrough(self) -> None:
        assert TriggerPrivacyService.categorize_experience("elite") == "elite"

    def test_unknown_falls_back_to_intermediate(self) -> None:
        # Unrecognised free-text values fall back to the mid-bin "intermediate"
        assert TriggerPrivacyService.categorize_experience("novice") == "intermediate"

    def test_empty_string_falls_back_to_intermediate(self) -> None:
        assert TriggerPrivacyService.categorize_experience("") == "intermediate"


# ---------------------------------------------------------------------------
# build_trigger_tags
# ---------------------------------------------------------------------------


class TestBuildTriggerTags:
    def test_always_includes_exercise_tag(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(exercise="squat")
        assert "squat" in tags

    def test_exercise_tag_present_with_all_body_fields(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="deadlift",
            height_cm=175.0,
            weight_kg=80.0,
            femur_length_cm=50.0,
            experience_level="intermediate",
        )
        assert "deadlift" in tags

    def test_height_bin_present_not_raw_value(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="squat",
            height_cm=172.0,
        )
        assert any("average" in t for t in tags)
        # must not contain the literal raw number
        assert "172.0" not in tags
        assert "172" not in " ".join(tags)

    def test_weight_bin_present_not_raw_value(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="squat",
            weight_kg=80.0,
        )
        assert any("moderate" in t for t in tags)
        assert "80.0" not in tags
        assert "80" not in " ".join(tags)

    def test_limb_ratio_bin_present_when_both_measurements_given(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="squat",
            height_cm=180.0,
            femur_length_cm=50.0,
        )
        assert any(
            t in ("short_limbed", "proportional", "long_limbed") for t in tags
        ), f"Expected a limb ratio tag in {tags}"

    def test_limb_ratio_absent_when_femur_missing(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="squat",
            height_cm=180.0,
            # femur_length_cm intentionally omitted
        )
        assert not any(t in ("short_limbed", "proportional", "long_limbed") for t in tags)

    def test_limb_ratio_absent_when_height_missing(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="squat",
            femur_length_cm=50.0,
            # height_cm intentionally omitted
        )
        assert not any(t in ("short_limbed", "proportional", "long_limbed") for t in tags)

    def test_none_height_omitted(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="squat",
            height_cm=None,
        )
        assert not any(h in tags for h in ("short", "average", "tall"))

    def test_none_weight_omitted(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="squat",
            weight_kg=None,
        )
        assert not any(w in tags for w in ("light", "moderate", "heavy"))

    def test_none_experience_omitted(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="squat",
            experience_level=None,
        )
        assert not any(
            e in tags for e in ("beginner", "intermediate", "advanced", "elite")
        )

    def test_additional_tags_included(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="squat",
            additional_tags=["knee_cave", "forward_lean"],
        )
        assert "knee_cave" in tags
        assert "forward_lean" in tags

    def test_no_raw_numeric_values_in_tags(self) -> None:
        """Regex check: no tag may be or contain a standalone number."""
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="deadlift",
            height_cm=183.0,
            weight_kg=92.5,
            femur_length_cm=55.0,
            experience_level="advanced",
            additional_tags=["hip_hinge"],
        )
        # A tag must not look like a plain number (int or float)
        numeric_pattern = re.compile(r"^\d+(\.\d+)?$")
        for tag in tags:
            assert not numeric_pattern.match(tag), (
                f"Raw numeric value found in trigger tags: {tag!r}"
            )

    def test_returns_list_of_strings(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(exercise="bench")
        assert isinstance(tags, list)
        assert all(isinstance(t, str) for t in tags)

    def test_no_duplicate_tags(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="squat",
            height_cm=170.0,
            weight_kg=75.0,
            additional_tags=["squat"],  # deliberately duplicates exercise
        )
        # duplicates should be deduplicated
        assert len(tags) == len(set(tags))

    def test_all_body_fields_produces_expected_bins(self) -> None:
        tags = TriggerPrivacyService.build_trigger_tags(
            exercise="squat",
            height_cm=160.0,    # → short
            weight_kg=65.0,     # → light
            femur_length_cm=40.0,  # ratio=0.25 → short_limbed
            experience_level="beginner",
        )
        assert "squat" in tags
        assert "short" in tags
        assert "light" in tags
        assert "short_limbed" in tags
        assert "beginner" in tags


# ---------------------------------------------------------------------------
# check_group_size
# ---------------------------------------------------------------------------


class TestCheckGroupSize:
    def test_below_minimum_returns_false(self) -> None:
        assert TriggerPrivacyService.check_group_size(19) is False

    def test_at_minimum_returns_true(self) -> None:
        assert TriggerPrivacyService.check_group_size(20) is True

    def test_above_minimum_returns_true(self) -> None:
        assert TriggerPrivacyService.check_group_size(100) is True

    def test_zero_returns_false(self) -> None:
        assert TriggerPrivacyService.check_group_size(0) is False

    def test_one_returns_false(self) -> None:
        assert TriggerPrivacyService.check_group_size(1) is False

    def test_exactly_nineteen_returns_false(self) -> None:
        assert TriggerPrivacyService.check_group_size(19) is False

    def test_min_group_size_constant_is_20(self) -> None:
        """FR-BRAIN-10 hard requirement: MIN_GROUP_SIZE must be 20."""
        assert TriggerPrivacyService.MIN_GROUP_SIZE == 20
