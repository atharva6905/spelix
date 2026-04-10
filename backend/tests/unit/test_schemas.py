"""Unit tests for Pydantic schemas in app/schemas/analysis.py.

Covers B-072 (Literal types for exercise_type / exercise_variant) and
B-073 (optional weight_kg field on AnalysisCreate, FR-REPM-06).
"""

import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisCreate


# ---------------------------------------------------------------------------
# B-072: Literal types — exercise_type
# ---------------------------------------------------------------------------


class TestExerciseTypeValidation:
    """exercise_type must be one of squat | bench | deadlift."""

    @pytest.mark.parametrize("valid_type", ["squat", "bench", "deadlift"])
    def test_valid_exercise_type_accepted(self, valid_type: str) -> None:
        obj = AnalysisCreate(
            exercise_type=valid_type,
            exercise_variant="high_bar",
            filename="video.mp4",
            file_size_bytes=1024,
        )
        assert obj.exercise_type == valid_type

    @pytest.mark.parametrize(
        "invalid_type",
        ["bench_press", "SQUAT", "Deadlift", "overhead_press", "", "unknown"],
    )
    def test_invalid_exercise_type_rejected(self, invalid_type: str) -> None:
        with pytest.raises(ValidationError):
            AnalysisCreate(
                exercise_type=invalid_type,
                exercise_variant="high_bar",
                filename="video.mp4",
                file_size_bytes=1024,
            )


# ---------------------------------------------------------------------------
# B-072: Literal types — exercise_variant
# ---------------------------------------------------------------------------


class TestExerciseVariantValidation:
    """exercise_variant must be one of the defined variant Literal values."""

    @pytest.mark.parametrize(
        "valid_variant",
        [
            "high_bar",
            "low_bar",
            "flat",
            "incline",
            "decline",
            "conventional",
            "sumo",
            "romanian",
        ],
    )
    def test_valid_exercise_variant_accepted(self, valid_variant: str) -> None:
        # Use a compatible exercise_type — variant validation is per-field, not
        # cross-field, so any valid type works here.
        obj = AnalysisCreate(
            exercise_type="squat",
            exercise_variant=valid_variant,
            filename="video.mp4",
            file_size_bytes=1024,
        )
        assert obj.exercise_variant == valid_variant

    @pytest.mark.parametrize(
        "invalid_variant",
        ["FLAT", "High_Bar", "paused", "close_grip", "", "unknown"],
    )
    def test_invalid_exercise_variant_rejected(self, invalid_variant: str) -> None:
        with pytest.raises(ValidationError):
            AnalysisCreate(
                exercise_type="bench",
                exercise_variant=invalid_variant,
                filename="video.mp4",
                file_size_bytes=1024,
            )


# ---------------------------------------------------------------------------
# B-073: Optional weight_kg field (FR-REPM-06)
# ---------------------------------------------------------------------------


class TestWeightKgField:
    """weight_kg is optional: accepts float, None, or absent; rejects non-numeric."""

    def test_weight_kg_absent_defaults_to_none(self) -> None:
        obj = AnalysisCreate(
            exercise_type="deadlift",
            exercise_variant="conventional",
            filename="lift.mp4",
            file_size_bytes=2048,
        )
        assert obj.weight_kg is None

    def test_weight_kg_none_accepted(self) -> None:
        obj = AnalysisCreate(
            exercise_type="squat",
            exercise_variant="low_bar",
            filename="squat.mp4",
            file_size_bytes=2048,
            weight_kg=None,
        )
        assert obj.weight_kg is None

    def test_weight_kg_float_accepted(self) -> None:
        obj = AnalysisCreate(
            exercise_type="bench",
            exercise_variant="flat",
            filename="bench.mp4",
            file_size_bytes=2048,
            weight_kg=100.0,
        )
        assert obj.weight_kg == pytest.approx(100.0)

    def test_weight_kg_integer_coerced_to_float(self) -> None:
        obj = AnalysisCreate(
            exercise_type="squat",
            exercise_variant="high_bar",
            filename="squat.mp4",
            file_size_bytes=2048,
            weight_kg=80,
        )
        assert obj.weight_kg == pytest.approx(80.0)

    def test_weight_kg_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisCreate(
                exercise_type="deadlift",
                exercise_variant="sumo",
                filename="dl.mp4",
                file_size_bytes=2048,
                weight_kg="heavy",  # type: ignore[arg-type]
            )

    def test_weight_kg_list_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisCreate(
                exercise_type="bench",
                exercise_variant="incline",
                filename="bench.mp4",
                file_size_bytes=2048,
                weight_kg=[100.0],  # type: ignore[arg-type]
            )
