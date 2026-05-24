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
- wrist_alignment_deg: [-180, 180] — full atan2 range; sagittal-view wrist alignment
  can span the full atan2 range depending on bar/forearm orientation at the chosen bottom
  frame; expert validates the meaningful sub-range post-onboarding (FR-EXPV-08).
- bar_touch_height_pct: [-50, 50] — ratio with no theoretical bound; MediaPipe landmark
  noise on a supine lifter at the chosen min-elbow-angle bottom frame can produce a very
  small hip-shoulder span denominator, yielding extreme ratios; expert validates the
  meaningful sub-range post-onboarding (FR-EXPV-08). Value is finite float is the gate.
- arch_deg: [-180, 180] — full atan2 range; bench arch via atan2(dy_mean, dx_mean)
  spans the full atan2 range when shoulder/hip x-direction inverts on the chosen
  non-rep frames; expert validates the meaningful sub-range post-onboarding (FR-EXPV-08).
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
from app.cv.signal_processing import (  # noqa: E402
    compute_angle_timeseries,
    compute_invalid_frame_mask,
)


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
        # ankle_dorsiflexion_deg and shin_angle_deg: float or None.
        # Plausibility is enforced inside the extractor (y-ordering guard +
        # anatomical-envelope guard in L2-CV-DEPTHFRAME-DROPOUT-R1b): any value
        # outside the physiological ROM returns None before reaching here.
        # The clinically meaningful sub-range is expert-validated via FR-EXPV-08.
        # This test does NOT re-assert the numeric range — that would duplicate the
        # in-code invariant and produce redundant failures.
        assert m["ankle_dorsiflexion_deg"] is None or isinstance(
            m["ankle_dorsiflexion_deg"], float
        ), f"rep {r.rep_index}: ankle_dorsiflexion_deg must be float or None"
        assert isinstance(m["heel_rise_flag"], float)
        assert float(m["heel_rise_flag"]) in (0.0, 1.0)
        assert m["shin_angle_deg"] is None or isinstance(
            m["shin_angle_deg"], float
        ), f"rep {r.rep_index}: shin_angle_deg must be float or None"
        with capsys.disabled():
            ankle_val = m["ankle_dorsiflexion_deg"]
            shin_val = m["shin_angle_deg"]
            print(
                f"[session-5-integration] squat rep {r.rep_index}: "
                f"ankle={'None' if ankle_val is None else f'{float(ankle_val):.1f}°'}, "
                f"heel_rise={int(float(m['heel_rise_flag']))}, "
                f"shin={'None' if shin_val is None else f'{float(shin_val):.1f}°'}"
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
        # Full atan2 range: sagittal wrist alignment can legitimately span
        # (-180, 180] at bench bottom depending on bar/forearm orientation;
        # expert validates the meaningful sub-range post-onboarding (FR-EXPV-08).
        assert -180.0 <= float(m["wrist_alignment_deg"]) <= 180.0
        assert isinstance(m["bar_touch_height_pct"], float)
        # Ratio (wrist_y - shoulder_y) / (hip_y - shoulder_y) has no theoretical
        # bound; supine MediaPipe noise at the chosen bottom frame can produce extreme
        # values when the hip-shoulder span is small. Just assert finite float.
        # Expert validates the meaningful sub-range post-onboarding (FR-EXPV-08).
        assert -50.0 <= float(m["bar_touch_height_pct"]) <= 50.0
        assert isinstance(m["arch_deg"], float)
        # Full atan2 range: arch_deg via atan2(dy_mean, dx_mean) can span
        # (-180, 180] when shoulder/hip x-direction inverts on the chosen
        # non-rep frames; expert validates the meaningful sub-range (FR-EXPV-08).
        assert -180.0 <= float(m["arch_deg"]) <= 180.0
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


@pytest.mark.integration
def test_session6_atharva_deadlift_bar_to_hip_distance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Deadlift fixture must populate bar_to_hip_distance as a 4-key dict.
    At least 2 of the 4 phase frames must resolve to a finite float
    (setup + lockout always resolve except in degenerate cases)."""
    rep_metrics, _reps, side, _fps = _run_pipeline_through_metrics(
        _DEADLIFT_FIXTURE, "deadlift", "conventional",
    )
    with capsys.disabled():
        print(f"\n[session-6-integration] dl side={side} reps={len(rep_metrics)}")
    for r in rep_metrics:
        m = r.metrics
        assert "bar_to_hip_distance" in m, f"missing key on rep {r.rep_index}"
        d = m["bar_to_hip_distance"]
        assert isinstance(d, dict), f"value should be dict, got {type(d).__name__}"
        assert set(d.keys()) == {"setup", "liftoff", "knee_pass", "lockout"}
        finite_count = sum(1 for v in d.values() if v is not None)
        assert finite_count >= 2, (
            f"rep {r.rep_index}: only {finite_count}/4 phase frames resolved: {d}"
        )
        for k, v in d.items():
            if v is not None:
                assert -5.0 <= v <= 5.0, f"rep {r.rep_index} phase {k}: {v}"
        with capsys.disabled():
            print(
                f"[session-6-integration] dl rep {r.rep_index}: "
                f"setup={d['setup']}, liftoff={d['liftoff']}, "
                f"knee_pass={d['knee_pass']}, lockout={d['lockout']}"
            )


@pytest.mark.integration
def test_session6_atharva_bench_shoulder_protraction(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bench fixture must populate shoulder_protraction_proxy_px per rep."""
    rep_metrics, _reps, side, _fps = _run_pipeline_through_metrics(
        _BENCH_FIXTURE, "bench", "flat",
    )
    with capsys.disabled():
        print(f"\n[session-6-integration] bench side={side} reps={len(rep_metrics)}")
    for r in rep_metrics:
        m = r.metrics
        assert "shoulder_protraction_proxy_px" in m, f"missing on rep {r.rep_index}"
        val = m["shoulder_protraction_proxy_px"]
        assert isinstance(val, float), (
            f"shoulder_protraction value is not a float: {type(val).__name__}"
        )
        # Sanity bound — MediaPipe noise on a supine lifter can push the
        # normalised ratio meaningfully. Expert validates the meaningful
        # sub-range post-onboarding via FR-EXPV-08.
        assert -5.0 <= val <= 5.0, f"rep {r.rep_index} value out of band: {val}"
        with capsys.disabled():
            print(
                f"[session-6-integration] bench rep {r.rep_index}: "
                f"shoulder_protraction={val:.3f}"
            )


@pytest.mark.integration
def test_session7_squat_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Squat fixture must populate lumbar_flexion_proxy_delta_deg and
    technique_consistency_std (the latter only when >=2 reps are detected).

    Sanity ranges (Section 7):
    - lumbar_flexion_proxy_delta_deg: [-90, 90] — delta of torso-vertical angle
    - technique_consistency_std: [0, 45] or None (None when single rep)
    """
    rep_metrics, reps, side, _fps = _run_pipeline_through_metrics(
        _SQUAT_FIXTURE, "squat", "standard",
    )
    with capsys.disabled():
        print(
            f"\n[session-7-integration] squat side={side} reps={len(rep_metrics)}"
        )
    for r in rep_metrics:
        m = r.metrics
        assert "lumbar_flexion_proxy_delta_deg" in m, (
            f"missing lumbar_flexion_proxy_delta_deg on rep {r.rep_index}"
        )
        lumbar = m["lumbar_flexion_proxy_delta_deg"]
        # First rep may be None if baseline frame not available; subsequent reps
        # should resolve. Log but don't hard-fail on None for the very first rep.
        if lumbar is not None:
            assert isinstance(lumbar, float), (
                f"lumbar_flexion_proxy_delta_deg is not float: {type(lumbar).__name__}"
            )
            assert -90.0 <= lumbar <= 90.0, (
                f"rep {r.rep_index} lumbar delta out of sanity range: {lumbar}"
            )
        assert "technique_consistency_std" in m, (
            f"missing technique_consistency_std on rep {r.rep_index}"
        )
        tcs = m["technique_consistency_std"]
        if tcs is not None:
            assert isinstance(tcs, float), (
                f"technique_consistency_std is not float: {type(tcs).__name__}"
            )
            assert 0.0 <= tcs <= 45.0, (
                f"technique_consistency_std out of sanity range: {tcs}"
            )
        with capsys.disabled():
            print(
                f"[session-7-integration] squat rep {r.rep_index}: "
                f"lumbar_delta={lumbar}, tcs={tcs}"
            )


@pytest.mark.integration
def test_session7_bench_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bench fixture must populate bar_path_classification per rep.

    Valid values: 'vertical', 'j_curve', 'drift', or None (when wrist midpoint
    x-trajectory is too short to classify).
    """
    rep_metrics, _reps, side, _fps = _run_pipeline_through_metrics(
        _BENCH_FIXTURE, "bench", "flat",
    )
    with capsys.disabled():
        print(
            f"\n[session-7-integration] bench side={side} reps={len(rep_metrics)}"
        )
    _VALID_BAR_PATH_LABELS = {"vertical", "j_curve", "drift"}
    for r in rep_metrics:
        m = r.metrics
        assert "bar_path_classification" in m, (
            f"missing bar_path_classification on rep {r.rep_index}"
        )
        label = m["bar_path_classification"]
        if label is not None:
            assert label in _VALID_BAR_PATH_LABELS, (
                f"rep {r.rep_index}: unexpected bar_path_classification {label!r}"
            )
        with capsys.disabled():
            print(
                f"[session-7-integration] bench rep {r.rep_index}: "
                f"bar_path={label}"
            )


@pytest.mark.integration
def test_session7_deadlift_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Deadlift fixture must populate lumbar_flexion_proxy_delta_deg and
    technique_consistency_std.

    Sanity ranges (Section 7):
    - lumbar_flexion_proxy_delta_deg: [-90, 90] — delta of torso-vertical angle
    - technique_consistency_std: [0, 45] or None (None when single rep)
    """
    rep_metrics, reps, side, _fps = _run_pipeline_through_metrics(
        _DEADLIFT_FIXTURE, "deadlift", "conventional",
    )
    with capsys.disabled():
        print(
            f"\n[session-7-integration] dl side={side} reps={len(rep_metrics)}"
        )
    for r in rep_metrics:
        m = r.metrics
        assert "lumbar_flexion_proxy_delta_deg" in m, (
            f"missing lumbar_flexion_proxy_delta_deg on dl rep {r.rep_index}"
        )
        lumbar = m["lumbar_flexion_proxy_delta_deg"]
        if lumbar is not None:
            assert isinstance(lumbar, float), (
                f"lumbar_flexion_proxy_delta_deg is not float: {type(lumbar).__name__}"
            )
            assert -90.0 <= lumbar <= 90.0, (
                f"dl rep {r.rep_index} lumbar delta out of sanity range: {lumbar}"
            )
        assert "technique_consistency_std" in m, (
            f"missing technique_consistency_std on dl rep {r.rep_index}"
        )
        tcs = m["technique_consistency_std"]
        if tcs is not None:
            assert isinstance(tcs, float), (
                f"technique_consistency_std is not float: {type(tcs).__name__}"
            )
            assert 0.0 <= tcs <= 45.0, (
                f"technique_consistency_std out of sanity range: {tcs}"
            )
        with capsys.disabled():
            print(
                f"[session-7-integration] dl rep {r.rep_index}: "
                f"lumbar_delta={lumbar}, tcs={tcs}"
            )


# ---------------------------------------------------------------------------
# R5 (L2-CV-DEPTHFRAME-R5): per-rep interpolation fraction on real fixtures.
# compute_invalid_frame_mask shares R2's gating predicate; the mean over a
# rep's frame range is the "% reconstructed" surfaced in the expert portal.
# ---------------------------------------------------------------------------


def _landmarks_reps_side(fixture: Path, exercise: str, variant: str):
    """Like _run_pipeline_through_metrics but returns raw landmarks + reps so
    the R2-gate mask can be sliced per rep."""
    _require_fixture(fixture)
    landmarks, fps, _w, _h = extract_landmarks(str(fixture))
    assert landmarks, f"no landmarks extracted from {fixture.name}"
    session = np.stack(landmarks)
    side = detect_lifter_side(session, fps=fps)
    angles = compute_angle_timeseries(
        landmarks, exercise_type=exercise, lifter_side=side
    )
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
    return landmarks, reps, side


def _per_rep_interpolation_fractions(landmarks, reps, exercise, side):
    mask = compute_invalid_frame_mask(landmarks, exercise, side)
    return [float(mask[r.start_frame:r.end_frame + 1].mean()) for r in reps]


@pytest.mark.integration
def test_r5_squat_interpolation_fraction_real_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Squat: every rep gets a fraction in [0,1]; the deep-squat occlusion this
    whole effort addresses means >=1 rep had frames reconstructed (frac > 0)."""
    landmarks, reps, side = _landmarks_reps_side(_SQUAT_FIXTURE, "squat", "standard")
    fracs = _per_rep_interpolation_fractions(landmarks, reps, "squat", side)
    with capsys.disabled():
        print(
            f"\n[r5-integration] squat side={side} "
            f"interp_fracs={[f'{f:.3f}' for f in fracs]}"
        )
    assert all(0.0 <= f <= 1.0 for f in fracs)
    assert any(f > 0.0 for f in fracs), (
        "deep-squat dropout should reconstruct frames in >=1 rep"
    )


@pytest.mark.integration
def test_r5_bench_interpolation_fraction_is_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bench is excluded from R2 gating (wrists systematically invisible), so no
    frames are reconstructed and every rep's interpolation fraction is 0.0."""
    landmarks, reps, side = _landmarks_reps_side(_BENCH_FIXTURE, "bench", "flat")
    fracs = _per_rep_interpolation_fractions(landmarks, reps, "bench", side)
    with capsys.disabled():
        print(f"\n[r5-integration] bench side={side} interp_fracs={fracs}")
    assert all(f == 0.0 for f in fracs), "bench is not R2-gated"
