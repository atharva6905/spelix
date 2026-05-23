"""Session 5 integration tests — each atharva fixture must populate the
Session-5 keys applicable to its exercise.

Per design Section-5:
- squat fixture: ankle_dorsiflexion_deg, heel_rise_flag, shin_angle_deg
- bench fixture: wrist_alignment_deg, bar_touch_height_pct, arch_deg
- deadlift fixture: setup_shoulder_x_offset, setup_knee_angle_deg

Sanity ranges (Section 5):
- ankle_dorsiflexion_deg: [0, 120] (raw joint angle; dorsiflexion magnitude = 90-this)
- heel_rise_flag: bool / 0.0|1.0
- shin_angle_deg: [-30, 60] (typical squats are 5-45° forward)
- wrist_alignment_deg: [-45, 45]
- bar_touch_height_pct: [-0.5, 1.5] (allowing slight overshoot of nominal 0..1)
- arch_deg: [-10, 60] (positive for an arched bench)
- setup_shoulder_x_offset: [-1.0, 1.5]
- setup_knee_angle_deg: [30, 180]
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
from app.cv.signal_processing import compute_angle_timeseries  # noqa: E402


_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "e2e" / "fixtures"
_SQUAT_FIXTURE = _FIXTURES_DIR / "atharva-squat.mov"
_BENCH_FIXTURE = _FIXTURES_DIR / "atharva-bench.mov"
_DEADLIFT_FIXTURE = _FIXTURES_DIR / "atharva-deadlift.mov"


def _require_fixture(p: Path) -> None:
    if not p.exists():
        pytest.skip(f"fixture not present at {p}")


def _run_pipeline_through_metrics(fixture: Path, exercise: str, variant: str):
    _require_fixture(fixture)
    landmarks, fps, _w, _h = extract_landmarks(str(fixture))
    assert landmarks, f"no landmarks extracted from {fixture.name}"
    session = np.stack(landmarks)
    side = detect_lifter_side(session, fps=fps)
    angles = compute_angle_timeseries(landmarks, exercise_type=exercise, lifter_side=side)
    cfg = ThresholdConfig(_V1_PATH)
    primary = angles["hip_angle"] if exercise != "bench" else angles["elbow_angle"]
    reps = detect_reps(
        angle_timeseries=primary,
        landmarks_per_frame=landmarks,
        exercise_type=exercise,
        exercise_variant=variant,
        fps=fps,
        cfg=cfg,
    )
    assert len(reps) >= 1, f"{fixture.name} must contain at least one detected rep"
    rep_metrics = extract_rep_metrics(
        reps=reps,
        landmarks_per_frame=landmarks,
        angle_timeseries=angles,
        exercise_type=exercise,
        exercise_variant=variant,
        fps=fps,
        lifter_side=side,
    )
    return rep_metrics, reps, side, fps


@pytest.mark.integration
def test_session5_atharva_squat_populates_squat_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rep_metrics, _reps, side, _fps = _run_pipeline_through_metrics(
        _SQUAT_FIXTURE, "squat", "standard",
    )
    with capsys.disabled():
        print(f"\n[session-5-integration] squat side={side} reps={len(rep_metrics)}")
    for r in rep_metrics:
        m = r.metrics
        # Required keys present
        for key in ("ankle_dorsiflexion_deg", "heel_rise_flag", "shin_angle_deg"):
            assert key in m, f"missing {key} on rep {r.rep_index}"
        # Sanity ranges (per Section 5)
        assert isinstance(m["ankle_dorsiflexion_deg"], float)
        assert 0.0 <= float(m["ankle_dorsiflexion_deg"]) <= 120.0
        assert isinstance(m["heel_rise_flag"], float)
        assert float(m["heel_rise_flag"]) in (0.0, 1.0)
        assert isinstance(m["shin_angle_deg"], float)
        assert -30.0 <= float(m["shin_angle_deg"]) <= 60.0
        with capsys.disabled():
            print(
                f"[session-5-integration] squat rep {r.rep_index}: "
                f"ankle={float(m['ankle_dorsiflexion_deg']):.1f}°, "
                f"heel_rise={int(float(m['heel_rise_flag']))}, "
                f"shin={float(m['shin_angle_deg']):.1f}°"
            )


@pytest.mark.integration
def test_session5_atharva_bench_populates_bench_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rep_metrics, _reps, side, _fps = _run_pipeline_through_metrics(
        _BENCH_FIXTURE, "bench", "flat",
    )
    with capsys.disabled():
        print(f"\n[session-5-integration] bench side={side} reps={len(rep_metrics)}")
    for r in rep_metrics:
        m = r.metrics
        for key in ("wrist_alignment_deg", "bar_touch_height_pct", "arch_deg"):
            assert key in m, f"missing {key} on rep {r.rep_index}"
        assert isinstance(m["wrist_alignment_deg"], float)
        assert -45.0 <= float(m["wrist_alignment_deg"]) <= 45.0
        assert isinstance(m["bar_touch_height_pct"], float)
        assert -0.5 <= float(m["bar_touch_height_pct"]) <= 1.5
        assert isinstance(m["arch_deg"], float)
        assert -10.0 <= float(m["arch_deg"]) <= 60.0
        with capsys.disabled():
            print(
                f"[session-5-integration] bench rep {r.rep_index}: "
                f"wrist={float(m['wrist_alignment_deg']):.1f}°, "
                f"touch={float(m['bar_touch_height_pct']):.2f}, "
                f"arch={float(m['arch_deg']):.1f}°"
            )


@pytest.mark.integration
def test_session5_atharva_deadlift_populates_dl_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rep_metrics, _reps, side, _fps = _run_pipeline_through_metrics(
        _DEADLIFT_FIXTURE, "deadlift", "conventional",
    )
    with capsys.disabled():
        print(f"\n[session-5-integration] dl side={side} reps={len(rep_metrics)}")
    for r in rep_metrics:
        m = r.metrics
        for key in ("setup_shoulder_x_offset", "setup_knee_angle_deg"):
            assert key in m, f"missing {key} on rep {r.rep_index}"
        assert isinstance(m["setup_shoulder_x_offset"], float)
        assert -1.0 <= float(m["setup_shoulder_x_offset"]) <= 1.5
        assert isinstance(m["setup_knee_angle_deg"], float)
        assert 30.0 <= float(m["setup_knee_angle_deg"]) <= 180.0
        with capsys.disabled():
            print(
                f"[session-5-integration] dl rep {r.rep_index}: "
                f"shoulder_off={float(m['setup_shoulder_x_offset']):.2f}, "
                f"setup_knee={float(m['setup_knee_angle_deg']):.1f}°"
            )
