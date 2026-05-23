# Session 7 — Complex Multi-Frame Analysis Implementation Plan (EXPANDED)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for every task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the final 3 sagittal metrics (#2 `lumbar_flexion_proxy_delta_deg`, #6 `bar_path_classification`, #16 `technique_consistency_std`), all compute-only, completing the 16-metric registry.

**Architecture:** Per-rep analyzers in `metric_extraction.py` gain optional cross-rep context args (`all_reps`, `rep_position`) mirroring Session 5's `lifter_side` pattern. #2 uses a standing-baseline frame (squat: `reps[0].start_frame`; DL: previous rep's `end_frame`, first-rep: `liftoff_frame-1`). #6 classifies the wrist-midpoint x-trajectory with a side-agnostic symmetrized heuristic. #16 is computed in a post-pass inside `extract_rep_metrics` and injected into every rep's dict. `None` is stored as JSON null (no 0.0 sentinel) — `RepMetricValue` widened to include `None`.

**Tech Stack:** Python 3.12, NumPy, pytest. No frontend, no migrations, no threshold config.

**Spike decisions (authoritative):** `docs/superpowers/plans/2026-05-23-session-7-complex-metrics-plan.md`.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/cv/metric_extraction.py` | All 3 extractors + `identify_standing_baseline_frame`, `_classify_bar_path`, `_inject_technique_consistency_std`, `session_modal_bar_path_classification` helpers; widen `RepMetricValue`; wire into analyzers + `extract_rep_metrics`. |
| `backend/app/cv/sagittal_metrics_registry.py` | Flip `computed_yet=True` for #2/#6/#16; ensure #2 description contains exact phrase "composite torso angle — not lumbar-isolated". |
| `backend/tests/unit/test_metric_extraction_sagittal.py` | `test_session7_*` cases (butt-wink/no-butt-wink/no-baseline; vertical/j_curve/drift/degenerate; clean/fatigued/single-rep) + mirror tests. |
| `backend/tests/unit/test_metric_extraction.py` | Update `test_all_*_metric_values_are_floats` invariant to allow `None` for the 3 Session 7 keys. |
| `backend/tests/integration/test_pipeline_sagittal_metrics.py` | `test_session7_*` on all 3 fixtures for applicable metrics. |
| `backend/scripts/oneoff/smoke_sagittal_metrics_session7.py` (new) | Dump lumbar proxy, bar-path labels + session modal, consistency std per fixture. |

### Files NOT touched
`scoring.py`, `thresholds_v1.json`, frontend (registry-driven), alembic.

---

## Task 1: Widen `RepMetricValue` + standing-baseline helper (TDD)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py:39` (type alias)
- Modify: `backend/app/cv/metric_extraction.py` (add `identify_standing_baseline_frame`)
- Test: `backend/tests/unit/test_metric_extraction_sagittal.py`

- [ ] **Step 1: Write failing tests for the baseline helper**

```python
# ---------------------------------------------------------------------------
# Session 7 #2 — standing baseline frame identification
# ---------------------------------------------------------------------------
from app.cv.metric_extraction import identify_standing_baseline_frame  # noqa: E402


def test_session7_baseline_squat_uses_first_rep_start() -> None:
    """Squat baseline is the global first-rep start frame, for every rep."""
    reps = [
        DetectedRep(rep_index=0, start_frame=5, end_frame=40),
        DetectedRep(rep_index=1, start_frame=45, end_frame=80),
    ]
    # rep_position is ignored for squat — always returns reps[0].start_frame
    assert identify_standing_baseline_frame(
        "squat", reps[1], rep_position=1, all_reps=reps, bar_y_series=None
    ) == 5


def test_session7_baseline_squat_no_reps_returns_none() -> None:
    assert identify_standing_baseline_frame(
        "squat", DetectedRep(0, 0, 10), rep_position=0, all_reps=None, bar_y_series=None
    ) is None


def test_session7_baseline_deadlift_uses_prev_rep_lockout() -> None:
    """DL non-first rep baseline = previous rep's end_frame (lockout)."""
    reps = [
        DetectedRep(rep_index=0, start_frame=0, end_frame=30),
        DetectedRep(rep_index=1, start_frame=35, end_frame=70),
    ]
    bar_y = np.full(80, 0.5)
    assert identify_standing_baseline_frame(
        "deadlift", reps[1], rep_position=1, all_reps=reps, bar_y_series=bar_y
    ) == 30


def test_session7_baseline_deadlift_first_rep_uses_preliftoff() -> None:
    """DL first rep: liftoff detected at frame 10 → baseline = 9."""
    rep = DetectedRep(rep_index=0, start_frame=2, end_frame=40)
    bar_y = np.full(50, 0.80)          # set position, bar low (high y)
    bar_y[10:] = 0.50                  # bar rises (y drops) at frame 10 → liftoff
    out = identify_standing_baseline_frame(
        "deadlift", rep, rep_position=0, all_reps=[rep], bar_y_series=bar_y
    )
    assert out == 9


def test_session7_baseline_deadlift_first_rep_no_liftoff_falls_back_to_start() -> None:
    """DL first rep, bar never lifts → fall back to rep.start_frame."""
    rep = DetectedRep(rep_index=0, start_frame=3, end_frame=40)
    bar_y = np.full(50, 0.80)  # never rises
    out = identify_standing_baseline_frame(
        "deadlift", rep, rep_position=0, all_reps=[rep], bar_y_series=bar_y
    )
    assert out == 3
```

- [ ] **Step 2: Run — expect ImportError / failures**

Run: `uv run pytest backend/tests/unit/test_metric_extraction_sagittal.py -k session7_baseline -x`
Expected: FAIL (`cannot import name 'identify_standing_baseline_frame'`).

- [ ] **Step 3: Widen the type alias + implement helper**

In `metric_extraction.py`, change line 39:
```python
# Categorical strings, dict-valued phase-frame maps, and None (Session 7
# #2/#16 cannot-compute sentinel — stored as JSON null, NOT a 0.0 sentinel,
# because 0.0 is a valid biomechanical outcome for a delta / std).
RepMetricValue = float | str | dict[str, float | None] | None
```

Add (near the Session 6 phase-frame helpers, after `identify_knee_pass_frame`):
```python
def identify_standing_baseline_frame(
    exercise_type: str,
    rep: DetectedRep,
    rep_position: int,
    all_reps: list[DetectedRep] | None,
    bar_y_series: np.ndarray | None,
) -> int | None:
    """Session 7 #2 — index of the standing-baseline frame for the lumbar
    flexion proxy delta.

    Squat: one global baseline = ``all_reps[0].start_frame`` (the cleanest
    upright posture in the clip — see ADR-LUMBAR-FLEXION-PROXY-NAMING).
    Deadlift: previous rep's ``end_frame`` (lockout). First rep has no
    previous rep, so use the last frame before liftoff
    (``identify_liftoff_frame - 1``), falling back to ``rep.start_frame``
    when liftoff is undetectable.

    Returns ``None`` when no reps are available.
    """
    ex = exercise_type.lower()
    if ex == "squat":
        if not all_reps:
            return None
        return all_reps[0].start_frame
    if ex == "deadlift":
        if all_reps and rep_position > 0:
            return all_reps[rep_position - 1].end_frame
        # First rep: pre-liftoff frame, fallback to start.
        if bar_y_series is not None:
            liftoff = identify_liftoff_frame(
                bar_y_series, rep.start_frame, rep.end_frame,
            )
            if liftoff is not None:
                return max(rep.start_frame, liftoff - 1)
        return rep.start_frame
    return None
```

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest backend/tests/unit/test_metric_extraction_sagittal.py -k session7_baseline -x`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): Session 7 standing-baseline-frame helper + widen RepMetricValue for None"
```

---

## Task 2: `extract_lumbar_flexion_proxy_delta_deg` (#2) (TDD)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Test: `backend/tests/unit/test_metric_extraction_sagittal.py`

Math (spike Side-Agnosticism + design Section 4 #2): `proxy_angle(frame) = degrees(atan2((shoulder_x - hip_x) * facing_sign, hip_y - shoulder_y))`; `delta = proxy(bottom) - proxy(baseline)`. Returns `None` if baseline is None, or either frame's shoulder/hip visibility < 0.30, or geometry degenerate.

- [ ] **Step 1: Write failing tests**

```python
from app.cv.metric_extraction import extract_lumbar_flexion_proxy_delta_deg  # noqa: E402


def _upright_then_flexed_frames(flex_dx: float) -> list[np.ndarray]:
    """Frame 0 = upright (shoulder over hip); frame 1 = trunk flexed forward
    by flex_dx (shoulder ahead of hip in +x for a right-facing lifter)."""
    upright = _make_landmark_frame_right_side(shoulder_xy=(0.50, 0.20), hip_xy=(0.50, 0.55))
    flexed = _make_landmark_frame_right_side(shoulder_xy=(0.50 + flex_dx, 0.20), hip_xy=(0.50, 0.55))
    return [upright, flexed]


def test_session7_lumbar_proxy_no_buttwink_near_zero() -> None:
    """Clean squat: trunk angle at bottom ≈ trunk angle at baseline → delta ≈ 0."""
    frames = _upright_then_flexed_frames(flex_dx=0.0)
    right_idx = landmark_indices_for_side("right")
    delta = extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame=frames, bottom_frame=1, baseline_frame=0,
        side_idx=right_idx, lifter_side="right",
    )
    assert delta == pytest.approx(0.0, abs=0.5)


def test_session7_lumbar_proxy_buttwink_positive_delta() -> None:
    """Pronounced forward flexion at bottom → delta > 15°."""
    dy = 0.35
    flex_dx = dy * math.tan(math.radians(20.0))  # ~20° of trunk flexion
    frames = _upright_then_flexed_frames(flex_dx=flex_dx)
    right_idx = landmark_indices_for_side("right")
    delta = extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame=frames, bottom_frame=1, baseline_frame=0,
        side_idx=right_idx, lifter_side="right",
    )
    assert delta is not None and delta > 15.0


def test_session7_lumbar_proxy_no_baseline_returns_none() -> None:
    frames = _upright_then_flexed_frames(flex_dx=0.1)
    right_idx = landmark_indices_for_side("right")
    assert extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame=frames, bottom_frame=1, baseline_frame=None,
        side_idx=right_idx, lifter_side="right",
    ) is None


def test_session7_lumbar_proxy_low_visibility_returns_none() -> None:
    frames = _upright_then_flexed_frames(flex_dx=0.1)
    frames[0][24, 3] = 0.1  # hip low-vis at baseline frame
    right_idx = landmark_indices_for_side("right")
    assert extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame=frames, bottom_frame=1, baseline_frame=0,
        side_idx=right_idx, lifter_side="right",
    ) is None


@pytest.mark.parametrize("flex_deg", [0.0, 10.0, 20.0])
def test_session7_lumbar_proxy_side_agnostic(flex_deg: float) -> None:
    """Same physical flexion filmed from either side → equal delta."""
    dy = 0.35
    dx = dy * math.tan(math.radians(flex_deg))
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frames = [
        _make_landmark_frame_right_side((0.50, 0.20), (0.50, 0.55)),
        _make_landmark_frame_right_side((0.50 + dx, 0.20), (0.50, 0.55)),
    ]
    left_frames = [
        _make_landmark_frame_left_side((1.0 - 0.50, 0.20), (1.0 - 0.50, 0.55)),
        _make_landmark_frame_left_side((1.0 - (0.50 + dx), 0.20), (1.0 - 0.50, 0.55)),
    ]
    rd = extract_lumbar_flexion_proxy_delta_deg(right_frames, 1, 0, right_idx, "right")
    ld = extract_lumbar_flexion_proxy_delta_deg(left_frames, 1, 0, left_idx, "left")
    assert rd == pytest.approx(ld, abs=0.5)
```

- [ ] **Step 2: Run — expect ImportError/FAIL**

Run: `uv run pytest backend/tests/unit/test_metric_extraction_sagittal.py -k session7_lumbar -x`

- [ ] **Step 3: Implement**

```python
def _lumbar_proxy_angle(
    landmarks: np.ndarray, side_idx: SideIndices, side: Literal["left", "right"],
) -> float | None:
    """Composite trunk-flexion proxy angle at one frame:
    ``degrees(atan2((shoulder_x - hip_x)*facing_sign, hip_y - shoulder_y))``.
    NOT lumbar-isolated (ADR-LUMBAR-FLEXION-PROXY-NAMING). Returns None on
    low visibility or degenerate (zero-length) torso vector."""
    if not _vis_ok(landmarks, side_idx.shoulder, side_idx.hip):
        return None
    shoulder = _xy(landmarks, side_idx.shoulder)
    hip = _xy(landmarks, side_idx.hip)
    dx = (float(shoulder[0]) - float(hip[0])) * _facing_sign(side)
    dy = float(hip[1]) - float(shoulder[1])  # +ve: hip below shoulder (normal)
    if abs(dx) < _S5_DEGENERATE_MAGNITUDE and abs(dy) < _S5_DEGENERATE_MAGNITUDE:
        return None
    return float(np.degrees(np.arctan2(dx, dy)))


def extract_lumbar_flexion_proxy_delta_deg(
    landmarks_per_frame: list[np.ndarray],
    bottom_frame: int,
    baseline_frame: int | None,
    side_idx: SideIndices,
    lifter_side: Literal["left", "right"] = "right",
) -> float | None:
    """Session 7 #2 — composite trunk-flexion proxy delta (NOT lumbar-isolated).
    ``proxy(bottom) - proxy(baseline)``. Returns None if baseline is None,
    a frame is out of bounds, or either proxy angle is None."""
    n = len(landmarks_per_frame)
    if baseline_frame is None or not (0 <= baseline_frame < n) or not (0 <= bottom_frame < n):
        return None
    base = _lumbar_proxy_angle(landmarks_per_frame[baseline_frame], side_idx, lifter_side)
    bot = _lumbar_proxy_angle(landmarks_per_frame[bottom_frame], side_idx, lifter_side)
    if base is None or bot is None:
        return None
    return bot - base
```

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest backend/tests/unit/test_metric_extraction_sagittal.py -k session7_lumbar -x`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(cv): #2 lumbar_flexion_proxy_delta_deg extractor (compute-only, _proxy suffix)"
```

---

## Task 3: `_classify_bar_path` (#6) (TDD)

**Files:** Modify `metric_extraction.py`; Test in `test_metric_extraction_sagittal.py`.

Symmetrized side-agnostic heuristic (spike Decision 2): `j_curve` if `abs(ascent_end_x - bottom_x) > 0.03`; elif `abs(descent_start_x - ascent_end_x) < 0.02` → `vertical`; else `drift`. Degenerate (<3 frames span) → None.

- [ ] **Step 1: Write failing tests**

```python
from app.cv.metric_extraction import _classify_bar_path  # noqa: E402


def test_session7_barpath_vertical() -> None:
    assert _classify_bar_path(descent_start_x=0.50, bottom_x=0.50, ascent_end_x=0.50) == "vertical"


def test_session7_barpath_jcurve() -> None:
    assert _classify_bar_path(descent_start_x=0.50, bottom_x=0.50, ascent_end_x=0.44) == "j_curve"


def test_session7_barpath_drift() -> None:
    assert _classify_bar_path(descent_start_x=0.50, bottom_x=0.52, ascent_end_x=0.54) == "drift"


def test_session7_barpath_jcurve_mirrored_left_facing() -> None:
    """Left-facing lifter's j-curve sweeps to higher x — symmetrized abs() catches it."""
    assert _classify_bar_path(descent_start_x=0.50, bottom_x=0.50, ascent_end_x=0.56) == "j_curve"


def test_session7_barpath_jcurve_precedence_over_neardrift() -> None:
    assert _classify_bar_path(descent_start_x=0.50, bottom_x=0.50, ascent_end_x=0.46) == "j_curve"


def test_session7_barpath_degenerate_none() -> None:
    assert _classify_bar_path(None, None, None) is None
```

- [ ] **Step 2: Run — expect FAIL.** `uv run pytest ... -k session7_barpath -x`

- [ ] **Step 3: Implement**

```python
_S7_JCURVE_THRESHOLD = 0.03
_S7_VERTICAL_DEADBAND = 0.02


def _classify_bar_path(
    descent_start_x: float | None,
    bottom_x: float | None,
    ascent_end_x: float | None,
) -> str | None:
    """Session 7 #6 — bar-path shape from three x anchors (wrist-midpoint).
    Side-agnostic: uses ``abs()`` so a left-facing lifter's j-curve (which
    sweeps toward higher x) classifies identically to a right-facing one
    (v0 heuristic — design R5; expect post-onboarding refinement)."""
    if descent_start_x is None or bottom_x is None or ascent_end_x is None:
        return None
    if abs(ascent_end_x - bottom_x) > _S7_JCURVE_THRESHOLD:
        return "j_curve"
    if abs(descent_start_x - ascent_end_x) < _S7_VERTICAL_DEADBAND:
        return "vertical"
    return "drift"
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(cv): #6 bar_path_classification side-agnostic v0 heuristic"
```

---

## Task 4: `session_modal_bar_path_classification` + `_inject_technique_consistency_std` (#16) (TDD)

**Files:** Modify `metric_extraction.py`; Test in `test_metric_extraction_sagittal.py`.

#16 (spike Decision 3): population std (`np.std`, ddof=0) of `depth_angle` (squat) / `lockout_torso_lean_deg` (DL) across reps; single-rep → None; injected into every rep.

- [ ] **Step 1: Write failing tests**

```python
from app.cv.metric_extraction import (  # noqa: E402
    _inject_technique_consistency_std,
    session_modal_bar_path_classification,
)
from app.cv.metric_extraction import RepMetrics  # noqa: E402


def _rep_with(metrics: dict) -> RepMetrics:
    return RepMetrics(rep_index=0, start_frame=0, end_frame=1, metrics=dict(metrics))


def test_session7_consistency_identical_reps_zero() -> None:
    reps = [_rep_with({"depth_angle": 90.0}) for _ in range(3)]
    _inject_technique_consistency_std(reps, "squat")
    assert all(r.metrics["technique_consistency_std"] == pytest.approx(0.0) for r in reps)


def test_session7_consistency_fatigued_reps_positive() -> None:
    reps = [_rep_with({"depth_angle": v}) for v in (90.0, 95.0, 105.0)]
    _inject_technique_consistency_std(reps, "squat")
    std = reps[0].metrics["technique_consistency_std"]
    assert std == pytest.approx(float(np.std([90.0, 95.0, 105.0])))  # ddof=0
    assert std > 0.0


def test_session7_consistency_deadlift_uses_lockout_lean() -> None:
    reps = [_rep_with({"lockout_torso_lean_deg": v}) for v in (5.0, 9.0)]
    _inject_technique_consistency_std(reps, "deadlift")
    assert reps[0].metrics["technique_consistency_std"] == pytest.approx(2.0)


def test_session7_consistency_single_rep_none() -> None:
    reps = [_rep_with({"depth_angle": 90.0})]
    _inject_technique_consistency_std(reps, "squat")
    assert reps[0].metrics["technique_consistency_std"] is None


def test_session7_session_modal_bar_path() -> None:
    reps = [
        _rep_with({"bar_path_classification": "vertical"}),
        _rep_with({"bar_path_classification": "vertical"}),
        _rep_with({"bar_path_classification": "drift"}),
    ]
    assert session_modal_bar_path_classification(reps) == "vertical"


def test_session7_session_modal_all_none() -> None:
    reps = [_rep_with({"bar_path_classification": None})]
    assert session_modal_bar_path_classification(reps) is None
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
_S7_CONSISTENCY_KEY = {
    "squat": "depth_angle",
    "deadlift": "lockout_torso_lean_deg",
}


def _inject_technique_consistency_std(
    result: list[RepMetrics], exercise_type: str,
) -> None:
    """Session 7 #16 — population std (ddof=0) of the chosen technique metric
    across reps, written into EVERY rep's dict. Single-rep → None (one
    observation has no measurable consistency). In-place mutation."""
    key = _S7_CONSISTENCY_KEY.get(exercise_type.lower())
    if key is None:
        return
    values = [
        float(r.metrics[key]) for r in result
        if isinstance(r.metrics.get(key), (int, float))
    ]
    std: float | None = float(np.std(values)) if len(values) >= 2 else None
    for r in result:
        r.metrics["technique_consistency_std"] = std


def session_modal_bar_path_classification(
    rep_metrics_list: list[RepMetrics],
) -> str | None:
    """Most common non-None bar_path_classification across reps (smoke/
    calibration only — NOT persisted to JSONB)."""
    from collections import Counter
    labels = [
        rm.metrics.get("bar_path_classification")
        for rm in rep_metrics_list
        if isinstance(rm.metrics.get("bar_path_classification"), str)
    ]
    if not labels:
        return None
    return Counter(labels).most_common(1)[0][0]
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(cv): #16 technique_consistency_std post-pass + session-modal bar-path helper"
```

---

## Task 5: Wire all 3 into analyzers + `extract_rep_metrics` (TDD)

**Files:** Modify `metric_extraction.py` analyzers + orchestrator; Test in `test_metric_extraction_sagittal.py`.

- [ ] **Step 1: Write failing analyzer key-emission tests**

```python
def test_session7_squat_emits_lumbar_and_consistency_keys() -> None:
    frames, angles, _ = _make_full_squat_session_with_landmarks(80)
    reps = [
        DetectedRep(rep_index=0, start_frame=2, end_frame=38),
        DetectedRep(rep_index=1, start_frame=42, end_frame=78),
    ]
    out = extract_rep_metrics(reps, frames, angles, "squat", "standard", 30.0, "right")
    assert "lumbar_flexion_proxy_delta_deg" in out[0].metrics
    assert "technique_consistency_std" in out[0].metrics
    # consistency identical across reps
    assert out[0].metrics["technique_consistency_std"] == out[1].metrics["technique_consistency_std"]
    # bench-only key absent
    assert "bar_path_classification" not in out[0].metrics


def test_session7_bench_emits_bar_path_only() -> None:
    frames, angles, rep = _make_full_bench_session_with_landmarks(60)
    out = extract_rep_metrics([rep], frames, angles, "bench", "standard", 30.0, "right")
    assert "bar_path_classification" in out[0].metrics
    assert "lumbar_flexion_proxy_delta_deg" not in out[0].metrics
    assert "technique_consistency_std" not in out[0].metrics
```

> NOTE: if `_make_full_bench_session_with_landmarks` does not yet exist in the test file, add a minimal helper that builds a multi-frame bench session with elbow/shoulder angle series and a wrist-midpoint trajectory (landmarks 15/16), mirroring `_make_full_squat_session_with_landmarks`.

- [ ] **Step 2: Run — expect FAIL** (keys missing).

- [ ] **Step 3: Implement wiring**

In `_squat_metrics` (add `all_reps`/`rep_position` args with defaults; compute #2):
```python
def _squat_metrics(
    rep, landmarks_per_frame, angle_timeseries, fps, side_idx,
    lifter_side: Literal["left", "right"] = "right",
    all_reps: list[DetectedRep] | None = None,
    rep_position: int = 0,
) -> dict[str, RepMetricValue]:
    ...
    # Session 7 #2 — lumbar flexion proxy delta vs standing baseline.
    baseline = identify_standing_baseline_frame(
        "squat", rep, rep_position, all_reps, bar_y_series=None,
    )
    lumbar_delta = extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame, depth_frame, baseline, side_idx, lifter_side,
    )
    return {
        ...,
        "lumbar_flexion_proxy_delta_deg": lumbar_delta,  # None or float
    }
```

In `_deadlift_metrics` (same new args; `bar_y_series` is the `bar_y_series` already computed there):
```python
def _deadlift_metrics(
    rep, landmarks_per_frame, angle_timeseries, fps, side_idx,
    lifter_side: Literal["left", "right"] = "right",
    all_reps: list[DetectedRep] | None = None,
    rep_position: int = 0,
) -> dict[str, RepMetricValue]:
    ...
    # (bar_x_series, bar_y_series already computed for #4 above)
    baseline = identify_standing_baseline_frame(
        "deadlift", rep, rep_position, all_reps, bar_y_series=bar_y_series,
    )
    lumbar_delta = extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame, bottom_frame, baseline, side_idx, lifter_side,
    )
    return {
        ...,
        "lumbar_flexion_proxy_delta_deg": lumbar_delta,
    }
```

In `_bench_metrics` (compute #6 using wrist-midpoint x at the three anchor frames):
```python
    bar_x_series, _ = _wrist_midpoint_trajectory(landmarks_per_frame)
    span = rep.end_frame - rep.start_frame
    if span < 2:
        bar_path = None
    else:
        bar_path = _classify_bar_path(
            descent_start_x=float(bar_x_series[start]),
            bottom_x=float(bar_x_series[bottom_frame]),
            ascent_end_x=float(bar_x_series[end]),
        )
    return {
        ...,
        "bar_path_classification": bar_path,  # None or str
    }
```

In `extract_rep_metrics` — pass cross-rep context to squat/DL, then post-pass:
```python
    for i, rep in enumerate(reps):
        if ex in ("squat", "deadlift"):
            metrics = analyzer(
                rep, landmarks_per_frame, angle_timeseries, fps, side_idx,
                lifter_side, all_reps=reps, rep_position=i,
            )
        else:
            metrics = analyzer(
                rep, landmarks_per_frame, angle_timeseries, fps, side_idx, lifter_side,
            )
        result.append(RepMetrics(rep.rep_index, rep.start_frame, rep.end_frame, metrics))

    # Session 7 #16 — session-level consistency std injected into every rep.
    _inject_technique_consistency_std(result, ex)
    return result
```

- [ ] **Step 4: Run — expect PASS.** Also run full sagittal file: `uv run pytest backend/tests/unit/test_metric_extraction_sagittal.py -x`.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(cv): wire Session 7 metrics into squat/bench/deadlift analyzers + extract_rep_metrics"
```

---

## Task 6: Update float-invariant test for None values

**Files:** Modify `backend/tests/unit/test_metric_extraction.py`.

- [ ] **Step 1:** Locate `test_all_*_metric_values_are_floats` (the invariants that iterate metric values). Update to allow `None` for the 3 Session 7 keys AND `str`/`dict` already allowed:

```python
_SESSION7_NULLABLE = {
    "lumbar_flexion_proxy_delta_deg",
    "technique_consistency_std",
    "bar_path_classification",
}
for key, val in metrics.items():
    if key in _SESSION7_NULLABLE:
        assert val is None or isinstance(val, (float, int, str))
        continue
    # ... existing assertions ...
```

- [ ] **Step 2: Run** `uv run pytest backend/tests/unit/test_metric_extraction.py -x` — expect PASS (no other assertion changes).
- [ ] **Step 3: Commit** `git commit -am "test(cv): allow None for Session 7 nullable metric keys in float invariants"`

---

## Task 7: Flip registry flags + naming-honesty (TDD)

**Files:** Modify `sagittal_metrics_registry.py`; Test in `backend/tests/unit/test_sagittal_metrics_registry.py`.

- [ ] **Step 1: Write failing tests**

```python
def test_session7_registry_flags_computed() -> None:
    by_key = {e.key_name: e for e in SAGITTAL_METRICS_REGISTRY}
    for k in ("lumbar_flexion_proxy_delta_deg", "bar_path_classification", "technique_consistency_std"):
        assert by_key[k].computed_yet is True
        assert by_key[k].in_scoring is False  # all compute-only


def test_session7_lumbar_naming_honesty() -> None:
    by_key = {e.key_name: e for e in SAGITTAL_METRICS_REGISTRY}
    desc = by_key["lumbar_flexion_proxy_delta_deg"].description
    assert "composite torso angle — not lumbar-isolated" in desc
    assert by_key["lumbar_flexion_proxy_delta_deg"].key_name.endswith("_proxy_delta_deg")
    assert "_proxy" in by_key["lumbar_flexion_proxy_delta_deg"].key_name


def test_session7_barpath_names_v0_heuristic() -> None:
    by_key = {e.key_name: e for e in SAGITTAL_METRICS_REGISTRY}
    assert "v0" in by_key["bar_path_classification"].description.lower()
```

- [ ] **Step 2: Run — expect FAIL** (`computed_yet=False`; description lacks exact phrase).

- [ ] **Step 3: Implement** — set `computed_yet=True` on the 3 entries; update #2 description to include the exact em-dash phrase:

```python
        description=(
            "Composite trunk-flexion proxy: shoulder-hip-vertical angle at "
            "rep bottom minus the same angle at the standing baseline — a "
            "composite torso angle — not lumbar-isolated. "
            "See ADR-LUMBAR-FLEXION-PROXY-NAMING."
        ),
```

(Also check `test_expert_sagittal_metrics_endpoint.py` for a hardcoded count of computed entries — bump from 13 → 16 if asserted.)

- [ ] **Step 4: Run — expect PASS.** `uv run pytest backend/tests/unit/test_sagittal_metrics_registry.py backend/tests/unit/test_expert_sagittal_metrics_endpoint.py -x`
- [ ] **Step 5: Commit** `git commit -am "feat(cv): flip Session 7 registry flags computed_yet=True + #2 naming honesty"`

---

## Task 8: Integration tests on all 3 fixtures

**Files:** Modify `backend/tests/integration/test_pipeline_sagittal_metrics.py`.

- [ ] **Step 1: Add `test_session7_*` per fixture** (squat → #2 + #16; deadlift → #2 + #16; bench → #6). Assert applicable keys present and non-None for multi-rep fixtures; sanity bounds:

```python
@pytest.mark.integration
def test_session7_squat_fixture(squat_pipeline_result):
    rep_metrics = squat_pipeline_result  # list[RepMetrics]
    for rm in rep_metrics:
        assert "lumbar_flexion_proxy_delta_deg" in rm.metrics
        assert "technique_consistency_std" in rm.metrics
    # multi-rep fixture → consistency not None
    assert rep_metrics[0].metrics["technique_consistency_std"] is not None
    # lumbar proxy delta sanity: |delta| < 60° on a real squat
    deltas = [rm.metrics["lumbar_flexion_proxy_delta_deg"] for rm in rep_metrics
              if rm.metrics["lumbar_flexion_proxy_delta_deg"] is not None]
    assert deltas, "expected at least one computable lumbar delta"
    assert all(abs(d) < 60.0 for d in deltas)


@pytest.mark.integration
def test_session7_bench_fixture(bench_pipeline_result):
    rep_metrics = bench_pipeline_result
    labels = {rm.metrics.get("bar_path_classification") for rm in rep_metrics}
    assert labels & {"vertical", "j_curve", "drift"}  # at least one real label


@pytest.mark.integration
def test_session7_deadlift_fixture(deadlift_pipeline_result):
    rep_metrics = deadlift_pipeline_result
    for rm in rep_metrics:
        assert "lumbar_flexion_proxy_delta_deg" in rm.metrics
    assert rep_metrics[0].metrics["technique_consistency_std"] is not None
```

> Reuse the existing fixture-runner pattern in this file (it already runs the full pipeline once per atharva fixture and caches the result). If session-scoped fixtures `*_pipeline_result` don't exist, follow the Session 5/6 pattern in the same file.

- [ ] **Step 2: Run in BACKGROUND** (each fixture ≈ 15-20 min on MediaPipe; exceeds the 600s foreground Bash limit):

Run (background): `uv run pytest backend/tests/integration/test_pipeline_sagittal_metrics.py -k session7 -v`
Expected: passed (await completion notification).

- [ ] **Step 3: Commit** `git commit -am "test(cv): Session 7 integration tests on all 3 atharva fixtures"`

---

## Task 9: Smoke script

**Files:** Create `backend/scripts/oneoff/smoke_sagittal_metrics_session7.py`.

- [ ] **Step 1: Write the script** mirroring `smoke_sagittal_metrics_session6.py`. For each fixture: run pipeline → print per-rep `lumbar_flexion_proxy_delta_deg`, per-rep `bar_path_classification` + `session_modal_bar_path_classification(...)`, and `technique_consistency_std`, plus detected `lifter_side`.
- [ ] **Step 2: Run in BACKGROUND**, dump output to chat.
- [ ] **Step 3: Commit** `git commit -am "chore(cv): Session 7 smoke script for calibration"`

---

## Task 10: Local verification → PR

- [ ] `uv run pytest backend/tests/unit/test_metric_extraction_sagittal.py backend/tests/unit/test_metric_extraction.py backend/tests/unit/test_sagittal_metrics_registry.py backend/tests/unit/test_expert_sagittal_metrics_endpoint.py -q` → all pass.
- [ ] `ruff check backend/app/cv/metric_extraction.py backend/app/cv/sagittal_metrics_registry.py` → clean.
- [ ] `pyright backend/app/cv/metric_extraction.py backend/app/cv/sagittal_metrics_registry.py` → 0 errors.
- [ ] Coverage on the new functions ≥90%: `uv run pytest backend/tests/unit/test_metric_extraction_sagittal.py --cov=app.cv.metric_extraction --cov-report=term-missing`.
- [ ] Push branch `feat/sagittal-complex-metrics`, open PR via `mcp__github__create_pull_request`.

---

## Task 11: CI gate → merge → deploy → E2E + calibration

- [ ] `gh pr checks <PR>` — all PR-level checks pass (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel).
- [ ] `spelix-auditor` on diff (no CRITICAL).
- [ ] Merge via `mcp__github__merge_pull_request` (`merge_method="merge"`).
- [ ] `gh run watch <main-run-id>` — Deploy to Production conclusion='success'.
- [ ] SSH droplet `git log --oneline -1` matches merge SHA; containers (healthy).
- [ ] **Calibration mini-session**: re-upload all 3 fixtures on prod via Playwright MCP; eyeball new metric values against video frames; document expected-vs-measured in handoff with frame-referenced screenshots. STOP + escalate if any metric outside sanity (lumbar delta inverted-sign OR >2× expected magnitude on a visually clean rep).
- [ ] E2E: expert panel shows the 3 new metrics populated on each fixture; screenshots.

---

## Task 12: Docs + close-out

- [ ] ADR-LUMBAR-FLEXION-PROXY-NAMING in `decisions.md` (naming honesty + DL first-rep pre-liftoff baseline + J-curve v0 symmetrization + consistency-metric choices).
- [ ] `Spelix_Expert_Reviewer_Guide.docx`: final pass — all 16 sagittal metrics + sagittal-view measurement scope.
- [ ] `backlog.md`: L2-SAGITTAL-COMPLEX-01..03 → done with merge SHA.
- [ ] Master manifest: Session 7 → complete; add "Completion summary" block; ALL 7 sessions complete.
- [ ] `.claude/handoff.md`: final completion handoff + post-onboarding follow-up list (threshold validation + scoring wiring for the 14 compute-only metrics + PDF + multi-camera).

---

## Acceptance criteria

- 3 extractors + helpers implemented + side-agnostic mirror-tested.
- `lumbar_flexion_proxy_delta_deg` uses `_proxy` suffix; registry description contains exact phrase "composite torso angle — not lumbar-isolated".
- 3 registry flags flipped (`computed_yet=True`, `in_scoring=False`).
- `None` stored as JSON null (no 0.0 sentinel); `RepMetricValue` widened.
- Integration tests pass on all 3 fixtures; smoke output sane.
- ADR + Expert Guide + manifest + handoff updated; all 7 sessions complete.

## Self-review notes
- Spec coverage: #2/#6/#16 each have an extractor task + tests; naming honesty (Task 7); session-level storage (Task 4/5); None-handling (Task 1/6). ✓
- Type consistency: `identify_standing_baseline_frame`, `extract_lumbar_flexion_proxy_delta_deg`, `_classify_bar_path`, `_inject_technique_consistency_std`, `session_modal_bar_path_classification` names used identically across tasks. ✓
- No placeholders: all test bodies + implementations + commit messages concrete. ✓
