"""Session 4 integration test — atharva-squat fixture must populate the four
new sagittal metrics in rep_metrics, and the two auto-flow scoring branches
must run on the aggregated session data without exception.

Per design Section-5 — the squat fixture is the canonical Session-4 sanity
check; bench and deadlift fixtures get the same treatment in later sessions.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

# Wire ThresholdConfig to v1 before any app.* imports.
_V1_PATH = (
    Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
)
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig  # noqa: E402
from app.cv.lifter_side import detect_lifter_side  # noqa: E402
from app.cv.metric_extraction import extract_rep_metrics  # noqa: E402
from app.cv.pose_extraction import extract_landmarks  # noqa: E402
from app.cv.rep_detection import detect_reps  # noqa: E402
from app.cv.scoring import OverallFormScore  # noqa: E402
from app.cv.signal_processing import compute_angle_timeseries  # noqa: E402
from app.services.pipeline import _aggregate_rep_metrics  # noqa: E402


_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3] / "e2e" / "fixtures" / "atharva-squat.mov"
)


def _skip_if_fixture_missing() -> None:
    if not _FIXTURE_PATH.exists():
        pytest.skip(f"atharva-squat fixture not present at {_FIXTURE_PATH}")


def _run_squat_pipeline_through_metrics():
    """Helper: pose → side → angles → reps → rep_metrics for the squat fixture."""
    _skip_if_fixture_missing()
    landmarks, fps, _w, _h = extract_landmarks(str(_FIXTURE_PATH))
    assert landmarks, "no landmarks extracted from atharva-squat fixture"
    session = np.stack(landmarks)
    side = detect_lifter_side(session, fps=fps)
    angles = compute_angle_timeseries(landmarks, exercise_type="squat", lifter_side=side)
    cfg = ThresholdConfig(_V1_PATH)
    reps = detect_reps(
        angle_timeseries=angles["hip_angle"],
        landmarks_per_frame=landmarks,
        exercise_type="squat",
        exercise_variant="standard",
        fps=fps,
        cfg=cfg,
    )
    assert len(reps) >= 1, "fixture must contain at least one detected rep"
    rep_metrics = extract_rep_metrics(
        reps=reps,
        landmarks_per_frame=landmarks,
        angle_timeseries=angles,
        exercise_type="squat",
        exercise_variant="standard",
        fps=fps,
        lifter_side=side,
    )
    return rep_metrics, reps, cfg, fps, side


@pytest.mark.integration
def test_session4_atharva_squat_populates_four_new_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rep_metrics, _reps, _cfg, _fps, side = _run_squat_pipeline_through_metrics()
    with capsys.disabled():
        print(f"\n[session-4-integration] detected side: {side}")
        print(f"[session-4-integration] {len(rep_metrics)} reps in atharva-squat fixture")

    for r in rep_metrics:
        m = r.metrics
        assert "depth_classification" in m
        assert m["depth_classification"] in {"above_parallel", "at_parallel", "below_parallel"}
        assert "ecc_con_ratio" in m
        assert isinstance(m["ecc_con_ratio"], float)
        assert m["ecc_con_ratio"] >= 0.0
        assert "pause_duration_s" in m
        assert isinstance(m["pause_duration_s"], float)
        assert m["pause_duration_s"] >= 0.0
        assert "lockout_torso_lean_deg" in m
        assert isinstance(m["lockout_torso_lean_deg"], float)
        with capsys.disabled():
            print(
                f"[session-4-integration] rep {r.rep_index}: "
                f"depth={m['depth_classification']}, "
                f"ecc/con={m['ecc_con_ratio']:.2f}, "
                f"pause={m['pause_duration_s']:.2f}s, "
                f"lockout_lean={m['lockout_torso_lean_deg']:.1f}°"
            )


@pytest.mark.integration
def test_session4_atharva_squat_scoring_runs_and_surfaces_badges(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scoring on the real fixture must execute without exception and the
    aggregate dict must carry the Session-4 keys so the auto-flow branches
    have something to read. The fixture is real-world footage so we don't
    assert which specific badges fire — only that the surface is wired."""
    rep_metrics, reps, cfg, _fps, _side = _run_squat_pipeline_through_metrics()
    agg = _aggregate_rep_metrics(rep_metrics, reps, session_confidence=0.9)
    assert "depth_classification" in agg, (
        "aggregator must forward modal depth_classification to scoring"
    )
    assert "ecc_con_ratio" in agg, (
        "aggregator must forward mean ecc_con_ratio to scoring"
    )

    scorer = OverallFormScore()
    result = scorer.compute(agg, bar_path=None, cfg=cfg, exercise_type="squat")
    assert result.overall is not None

    # Surface new badges for visibility in CI logs.
    session4_keys = {
        "squat_depth_classification_above",
        "ecc_con_ratio_rushed",
        "ecc_con_ratio_excessive",
    }
    new_badges = [
        b
        for dim in result.dimensions
        for b in dim.badges
        if b.issue_key in session4_keys
    ]
    with capsys.disabled():
        print(
            f"\n[session-4-integration] aggregate depth={agg['depth_classification']}, "
            f"ecc/con={agg['ecc_con_ratio']:.2f}"
        )
        print(
            f"[session-4-integration] OverallFormScore.overall={result.overall:.2f}; "
            f"new auto-flow badges fired: {len(new_badges)}"
        )
        for b in new_badges:
            print(
                f"[session-4-integration]   - {b.dimension}/{b.severity}/"
                f"{b.issue_key}: {b.message}"
            )
