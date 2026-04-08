"""Unit tests for SummaryService (B-030 / FR-HIST-04).

TDD gate: given analysis + rep metrics → correct summary_json structure.

All DB calls are mocked via AsyncMock — no real database required.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.summary import SummaryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis(
    *,
    confidence_score: float = 0.85,
    exercise_type: str = "squat",
    exercise_variant: str = "high_bar",
    quality_gate_result: dict[str, Any] | None = None,
) -> MagicMock:
    """Return a mock Analysis ORM object with the given attributes."""
    analysis = MagicMock()
    analysis.id = uuid.uuid4()
    analysis.confidence_score = confidence_score
    analysis.exercise_type = exercise_type
    analysis.exercise_variant = exercise_variant
    analysis.quality_gate_result = quality_gate_result
    analysis.summary_json = None
    return analysis


def _make_rep_metric(metrics_json: dict[str, Any] | None = None) -> MagicMock:
    """Return a mock RepMetric ORM object."""
    rm = MagicMock()
    rm.metrics_json = metrics_json
    return rm


def _make_service(
    analysis: MagicMock,
    rep_metrics: list[MagicMock],
) -> tuple[SummaryService, MagicMock, MagicMock]:
    """Wire up a SummaryService with mocked repos and return (service, repo, rep_repo)."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=analysis)
    repo.update = AsyncMock(return_value=analysis)

    rep_metric_repo = MagicMock()
    rep_metric_repo.get_by_analysis = AsyncMock(return_value=rep_metrics)

    service = SummaryService(repo=repo, rep_metric_repo=rep_metric_repo)
    return service, repo, rep_metric_repo


# ---------------------------------------------------------------------------
# Test 1: happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_summary_happy_path() -> None:
    """Mock repo returns analysis + 3 rep metrics → summary has correct structure."""
    analysis = _make_analysis(
        confidence_score=0.88,
        exercise_type="squat",
        exercise_variant="high_bar",
    )
    rep_metrics = [
        _make_rep_metric({"hip_angle_min_deg": 85.0, "knee_angle_min_deg": 80.0}),
        _make_rep_metric({"hip_angle_min_deg": 87.0, "knee_angle_min_deg": 82.0}),
        _make_rep_metric({"hip_angle_min_deg": 84.0, "knee_angle_min_deg": 79.0}),
    ]

    service, repo, rep_metric_repo = _make_service(analysis, rep_metrics)

    result = await service.compute_and_store(analysis.id)

    assert result["confidence_score"] == pytest.approx(0.88)
    assert result["confidence_label"] == "High"
    assert result["rep_count"] == 3
    assert result["exercise_type"] == "squat"
    assert result["exercise_variant"] == "high_bar"
    assert result["quality_gate_warnings"] == []
    assert isinstance(result["top_metric_keys"], list)

    # Verify update was called with summary written back
    repo.update.assert_awaited_once_with(analysis)
    assert analysis.summary_json == result

    # Verify repos were called with correct IDs
    repo.get_by_id.assert_awaited_once_with(analysis.id)
    rep_metric_repo.get_by_analysis.assert_awaited_once_with(analysis.id)


# ---------------------------------------------------------------------------
# Test 2: quality gate warnings extracted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quality_gate_warnings_extracted() -> None:
    """Analysis with a failed quality gate check → warnings list populated."""
    quality_gate_result = {
        "passed": False,
        "checks": [
            {
                "name": "body_visibility",
                "passed": False,
                "user_message": "Body not fully visible — re-record with camera further back.",
            },
            {
                "name": "min_frames",
                "passed": True,
                "user_message": "Sufficient frames detected.",
            },
        ],
    }
    analysis = _make_analysis(
        confidence_score=0.42,
        exercise_type="deadlift",
        exercise_variant="conventional",
        quality_gate_result=quality_gate_result,
    )
    rep_metrics = [_make_rep_metric({"hip_hinge_angle_deg": 45.0})]

    service, _, _ = _make_service(analysis, rep_metrics)

    result = await service.compute_and_store(analysis.id)

    assert len(result["quality_gate_warnings"]) == 1
    assert "Body not fully visible" in result["quality_gate_warnings"][0]


# ---------------------------------------------------------------------------
# Test 3: no reps → zero count and empty keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_reps_returns_zero_count() -> None:
    """Empty rep metrics → rep_count=0, top_metric_keys=[]."""
    analysis = _make_analysis(
        confidence_score=0.71,
        exercise_type="bench",
        exercise_variant="flat",
    )
    service, _, _ = _make_service(analysis, [])

    result = await service.compute_and_store(analysis.id)

    assert result["rep_count"] == 0
    assert result["top_metric_keys"] == []
    assert result["confidence_label"] == "Moderate"


# ---------------------------------------------------------------------------
# Test 4: metric keys collected across reps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metric_keys_collected() -> None:
    """Rep metrics with different keys → union in top_metric_keys, sorted."""
    analysis = _make_analysis(
        confidence_score=0.82,
        exercise_type="squat",
        exercise_variant="low_bar",
    )
    rep_metrics = [
        _make_rep_metric({"hip_angle_min_deg": 80.0, "knee_angle_min_deg": 75.0}),
        _make_rep_metric({"hip_angle_min_deg": 82.0, "knee_valgus_deg": 5.0}),
        _make_rep_metric({"bar_path_deviation_mm": 12.0, "knee_angle_min_deg": 77.0}),
    ]
    service, _, _ = _make_service(analysis, rep_metrics)

    result = await service.compute_and_store(analysis.id)

    keys = result["top_metric_keys"]
    assert "hip_angle_min_deg" in keys
    assert "knee_angle_min_deg" in keys
    assert "knee_valgus_deg" in keys
    assert "bar_path_deviation_mm" in keys
    # Keys should be sorted
    assert keys == sorted(keys)
    # No duplicates
    assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# Test 5: analysis not found raises ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_not_found_raises() -> None:
    """If the analysis doesn't exist, a ValueError is raised."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    rep_metric_repo = MagicMock()

    service = SummaryService(repo=repo, rep_metric_repo=rep_metric_repo)

    with pytest.raises(ValueError, match="not found"):
        await service.compute_and_store(uuid.uuid4())


# ---------------------------------------------------------------------------
# Test 6: confidence_label boundary values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "score,expected_label",
    [
        (0.80, "High"),
        (0.95, "High"),
        (0.65, "Moderate"),
        (0.79, "Moderate"),
        (0.50, "Low"),
        (0.64, "Low"),
        (0.49, "Very Low"),
        (0.00, "Very Low"),
    ],
)
async def test_confidence_label_boundaries(score: float, expected_label: str) -> None:
    """Confidence label thresholds: >=0.80 High, >=0.65 Moderate, >=0.50 Low, else Very Low."""
    analysis = _make_analysis(confidence_score=score)
    service, _, _ = _make_service(analysis, [])

    result = await service.compute_and_store(analysis.id)

    assert result["confidence_label"] == expected_label


# ---------------------------------------------------------------------------
# Test 7: quality gate with all checks passed → no warnings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quality_gate_all_passed_no_warnings() -> None:
    """All checks passing → quality_gate_warnings is empty."""
    quality_gate_result = {
        "passed": True,
        "checks": [
            {"name": "body_visibility", "passed": True, "user_message": "OK"},
            {"name": "min_frames", "passed": True, "user_message": "OK"},
        ],
    }
    analysis = _make_analysis(quality_gate_result=quality_gate_result)
    service, _, _ = _make_service(analysis, [])

    result = await service.compute_and_store(analysis.id)

    assert result["quality_gate_warnings"] == []


# ---------------------------------------------------------------------------
# Test 8: None confidence_score defaults to 0.0 (no confidence data yet)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_none_confidence_score_defaults_zero() -> None:
    """If analysis.confidence_score is None, summary uses 0.0 (Very Low)."""
    analysis = _make_analysis(confidence_score=None)  # type: ignore[arg-type]
    analysis.confidence_score = None
    service, _, _ = _make_service(analysis, [])

    result = await service.compute_and_store(analysis.id)

    assert result["confidence_score"] == 0.0
    assert result["confidence_label"] == "Very Low"


# ---------------------------------------------------------------------------
# Test 9: rep metric with None metrics_json is skipped gracefully
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_none_metrics_json_skipped() -> None:
    """Rep metrics where metrics_json is None contribute no keys."""
    analysis = _make_analysis()
    rep_metrics = [
        _make_rep_metric(None),
        _make_rep_metric({"knee_angle_min_deg": 80.0}),
        _make_rep_metric(None),
    ]
    service, _, _ = _make_service(analysis, rep_metrics)

    result = await service.compute_and_store(analysis.id)

    assert result["rep_count"] == 3
    assert result["top_metric_keys"] == ["knee_angle_min_deg"]
