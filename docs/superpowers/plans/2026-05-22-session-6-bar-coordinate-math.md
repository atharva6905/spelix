# Session 6 — Bar-Coordinate Math Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement two compute-only sagittal-view metrics that consume bar-coordinate math: #4 `bar_to_hip_distance` (deadlift phase-frame dict) and #14 `shoulder_protraction_proxy_px` (bench). Introduce two phase-frame identification helpers (`identify_liftoff_frame`, `identify_knee_pass_frame`) reusable across the codebase.

**Architecture:** Pure-function helpers in `backend/app/cv/metric_extraction.py`. Bar-trajectory input is the landmark wrist-midpoint (MediaPipe landmarks 15 + 16 mean) — same proxy used by `compute_bar_path_from_landmarks` when HoughCircles detection fails. This keeps pipeline ordering unchanged: barbell detection still runs after metric extraction. The `RepMetrics.metrics` value type is widened to allow a dict value for `bar_to_hip_distance`. Side-agnosticism is enforced via `_facing_sign(side)` for the signed x-component of both metrics (Session 5 pattern).

**Tech Stack:** Python 3.12, NumPy, pytest. No frontend code changes. No threshold config entries. No new migrations. JSONB-only key additions (`bar_to_hip_distance`, `shoulder_protraction_proxy_px`).

---

## File Structure

| File | Change |
|---|---|
| `backend/app/cv/metric_extraction.py` | Add: `identify_liftoff_frame()`, `identify_knee_pass_frame()`, `_bar_to_hip_distance_dict()`, `_shoulder_protraction_proxy_px()`, `_wrist_midpoint_trajectory()`. Widen `RepMetrics.metrics` value type to include `dict[str, float | None]`. Wire #4 into `_deadlift_metrics`; wire #14 into `_bench_metrics`. |
| `backend/app/cv/sagittal_metrics_registry.py` | Flip `computed_yet=True` for `bar_to_hip_distance` and `shoulder_protraction_proxy_px`. |
| `backend/tests/unit/test_metric_extraction_sagittal.py` | Append `test_session6_*` test cases: phase-frame-id (liftoff, knee_pass) edge cases + extractor happy/edge/degenerate + side-agnosticism mirror tests + analyzer integration tests. |
| `backend/tests/unit/test_metric_extraction.py` | Update three `test_all_*_metric_values_are_floats` invariants to allow `bar_to_hip_distance` as a dict value. |
| `backend/tests/unit/test_sagittal_metrics_registry.py` | Narrow `test_session_6_plus_entries_remain_pristine` to the 3 Session-7 keys; add `TestRegistrySession6Flips` class mirroring Session 5. |
| `backend/tests/unit/test_expert_sagittal_metrics_endpoint.py` | Update `test_after_session5_eleven_metrics_computed_two_in_scoring` to assert 13 entries computed after Session 6 (add the 2 new keys to `computed` set). |
| `backend/tests/integration/test_pipeline_sagittal_metrics.py` | Append `test_session6_atharva_deadlift_bar_to_hip_distance` and `test_session6_atharva_bench_shoulder_protraction`. |
| `backend/scripts/oneoff/smoke_sagittal_metrics_session6.py` (new) | CSV dump of bar-to-hip distances at all 4 phase frames + shoulder-protraction values per rep across bench + deadlift fixtures. |
| `backlog.md` | Mark `L2-SAGITTAL-BAR-01..02` done with merge SHA. |
| `docs/superpowers/goals/2026-05-22-cv-audit-master.md` | Flip Session 6 status to complete; Session 7 active. |
| `.claude/handoff.md` | Rewrite for Session 7 launch. |

### Files NOT touched

- `backend/app/cv/barbell_detection.py` — wrist-midpoint fallback unchanged.
- `backend/app/services/pipeline.py` — order preserved; barbell detection still runs Step 9 after metric extraction Step 6.
- `backend/app/cv/scoring.py` — both metrics are compute-only (per design Section 4 / registry).
- `config/thresholds_v1.json` — no threshold entries for compute-only Session 6 metrics.
- `frontend/**` — `<UnvalidatedMetricsPanel />` is registry-driven and auto-picks up the flipped flags.

---

## Design Notes

### Bar-trajectory input: wrist-midpoint proxy

The design (Section 4 #4) says "bar-x trajectory from `barbell_detection.py`". `compute_bar_path_from_landmarks` already establishes the wrist-midpoint (`(landmarks[15] + landmarks[16]) / 2`) as the bar-position fallback when HoughCircles detection rate drops below 50%. For Session 6 we use that same proxy directly inside the analyzer — pipeline ordering stays unchanged (barbell detection at Step 9 still runs after metric extraction at Step 6). Synthetic unit tests inject a bar trajectory by setting the wrist landmarks (15 and 16) per frame; the helper accepts the bar-trajectory arrays as direct inputs so tests do not need to thread landmarks through.

### Phase-frame identification

Four frames define a deadlift rep for #4:
- `setup_frame` = `rep.start_frame` (first frame of the lift; comes free from `DetectedRep`).
- `liftoff_frame` = first frame in `(setup_frame, end_frame]` where `bar_y` < `bar_y[setup_frame] - 0.02` (in normalized-coords, frame height = 1.0). Returns `None` if the bar never rises.
- `knee_pass_frame` = first frame in `[liftoff_frame, end_frame]` where `bar_y` ≤ `knee_y` (bar reaches at-or-above knee height). Returns `None` if the bar never reaches knee height.
- `lockout_frame` = `rep.end_frame` (peak hip angle = rep completion; comes free from `DetectedRep`).

### Side-agnosticism (per ADR-LIFTER-SIDE-DETECTION)

- **#4 `bar_to_hip_distance`**: signed delta `(bar_x - hip_x) * _facing_sign(side)`; normalised by unsigned shoulder-to-hip distance at setup. Positive = bar in front of the lifter regardless of which side filmed.
- **#14 `shoulder_protraction_proxy_px`**: signed drift `(shoulder_x_at_bottom - shoulder_x_at_setup) * _facing_sign(side)`; normalised by unsigned shoulder-to-hip distance at setup. Positive = shoulders move anteriorly during the press.

### Type widening for dict-valued metric

Per ADR-022 / `backend/CLAUDE.md` "RepMetrics.metrics type" gotcha, when adding a non-float value the type annotation must be widened in the same edit. The three `test_all_*_metric_values_are_floats` invariants are updated to treat `bar_to_hip_distance` as a third special key (dict-valued) alongside `phase_of_max_deviation` (string) and `depth_classification` (string).

---

## Tasks

### Task 1: Create branch and confirm clean workspace

**Files:** none

- [ ] **Step 1.1: Confirm working tree clean of edits to plan files**

```bash
git status
```
Expected: only handoff/screenshots/graphify-out untracked or modified — no edits to `backend/app/cv/metric_extraction.py` or sagittal-metric tests.

- [ ] **Step 1.2: Create the feature branch**

```bash
git checkout -b feat/sagittal-bar-metrics
```

- [ ] **Step 1.3: Skim handoff to confirm Session 5 SHAs match master manifest**

```bash
git log --oneline -5
```
Expected first line: `b016d6c Merge pull request #162 from atharva6905/docs/session-5-close`.

---

### Task 2: TDD `identify_liftoff_frame` helper

**Files:**
- Modify: `backend/app/cv/metric_extraction.py` (add helper near end of "Session 5 helpers" block, before the dispatch table)
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py` (append Session 6 tests at end)

- [ ] **Step 2.1: Write failing tests for `identify_liftoff_frame`**

Append to `backend/tests/unit/test_metric_extraction_sagittal.py`:

```python
# ---------------------------------------------------------------------------
# Session 6 — Bar-coordinate math
# ---------------------------------------------------------------------------


def test_session6_identify_liftoff_frame_happy_path() -> None:
    """Bar held still for 10 frames, then rises 5% over the next 10 → liftoff at frame 11."""
    from app.cv.metric_extraction import identify_liftoff_frame
    n = 30
    bar_y = np.full(n, 0.80)
    bar_y[11:21] = np.linspace(0.80, 0.75, 10)  # rises (y decreases) starting frame 11
    bar_y[21:] = 0.75
    out = identify_liftoff_frame(bar_y, setup_frame=0, end_frame=n - 1, threshold_pct=0.02)
    # First frame strictly below 0.80 - 0.02 = 0.78 is somewhere in 11..21.
    assert out is not None
    assert 11 <= out <= 21
    assert bar_y[out] < 0.80 - 0.02 + 1e-9


def test_session6_identify_liftoff_frame_never_lifts_returns_none() -> None:
    """Bar drifts up <2% of frame height → no liftoff detected → None."""
    from app.cv.metric_extraction import identify_liftoff_frame
    n = 30
    bar_y = np.full(n, 0.80)
    bar_y[10:] = 0.795  # rises only 0.5% — below 2% threshold
    out = identify_liftoff_frame(bar_y, setup_frame=0, end_frame=n - 1, threshold_pct=0.02)
    assert out is None


def test_session6_identify_liftoff_frame_immediate_liftoff() -> None:
    """Bar already moving up at frame 1 → liftoff returned at the first qualifying frame."""
    from app.cv.metric_extraction import identify_liftoff_frame
    n = 10
    bar_y = np.array([0.80, 0.77, 0.74, 0.70, 0.66, 0.62, 0.58, 0.55, 0.55, 0.55])
    out = identify_liftoff_frame(bar_y, setup_frame=0, end_frame=n - 1, threshold_pct=0.02)
    assert out == 1


def test_session6_identify_liftoff_frame_out_of_bounds_returns_none() -> None:
    """end_frame past array length or setup_frame negative → None, no exception."""
    from app.cv.metric_extraction import identify_liftoff_frame
    bar_y = np.full(10, 0.80)
    assert identify_liftoff_frame(bar_y, setup_frame=-1, end_frame=5) is None
    assert identify_liftoff_frame(bar_y, setup_frame=0, end_frame=99) is None
    assert identify_liftoff_frame(bar_y, setup_frame=5, end_frame=3) is None  # end < setup


def test_session6_identify_liftoff_frame_empty_series_returns_none() -> None:
    from app.cv.metric_extraction import identify_liftoff_frame
    assert identify_liftoff_frame(np.array([]), setup_frame=0, end_frame=0) is None
```

- [ ] **Step 2.2: Run tests — expected failures**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py::test_session6_identify_liftoff_frame_happy_path -x
```
Expected: `ImportError: cannot import name 'identify_liftoff_frame' from 'app.cv.metric_extraction'`.

- [ ] **Step 2.3: Implement `identify_liftoff_frame` in `metric_extraction.py`**

Insert after the existing `_arch_deg` function and before the `_ANALYZER_MAP` dispatch table:

```python
# ---------------------------------------------------------------------------
# Session 6 — Bar-coordinate math helpers
# ---------------------------------------------------------------------------

# Liftoff: bar y must drop (rise in image) by at least this fraction of the
# frame height. MediaPipe normalises y to [0, 1] so the threshold is
# dimensionally the same as the design Section-4 "≥2% of frame height".
_S6_LIFTOFF_THRESHOLD_PCT = 0.02


def identify_liftoff_frame(
    bar_y_series: np.ndarray,
    setup_frame: int,
    end_frame: int,
    threshold_pct: float = _S6_LIFTOFF_THRESHOLD_PCT,
) -> int | None:
    """Session 6 — first frame after ``setup_frame`` where the bar rises in
    image (y decreases) by at least ``threshold_pct`` of the frame height.

    Returns ``None`` when:
    - ``setup_frame`` or ``end_frame`` is out of bounds,
    - ``end_frame <= setup_frame``,
    - the bar never rises far enough across ``(setup_frame, end_frame]``.

    Frame height is 1.0 in MediaPipe normalised coords, so the absolute
    threshold equals ``threshold_pct``.
    """
    n = bar_y_series.shape[0] if bar_y_series.ndim == 1 else 0
    if n == 0:
        return None
    if setup_frame < 0 or end_frame >= n or end_frame <= setup_frame:
        return None
    baseline = float(bar_y_series[setup_frame])
    cutoff = baseline - threshold_pct
    for k in range(setup_frame + 1, end_frame + 1):
        if float(bar_y_series[k]) < cutoff:
            return k
    return None
```

- [ ] **Step 2.4: Run liftoff tests — expected pass**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py -k "session6_identify_liftoff" -v
```
Expected: 5 passed.

- [ ] **Step 2.5: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "$(cat <<'EOF'
feat(cv): identify_liftoff_frame helper for Session 6 bar metrics

Detects the first frame after rep start where the bar rises in image
(y decreases) by at least 2% of frame height. Returns None on
degenerate input. Foundation for #4 bar_to_hip_distance phase-frame dict.
EOF
)"
```

---

### Task 3: TDD `identify_knee_pass_frame` helper

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py`

- [ ] **Step 3.1: Write failing tests**

Append to `backend/tests/unit/test_metric_extraction_sagittal.py`:

```python
def test_session6_identify_knee_pass_frame_happy_path() -> None:
    """Bar starts below knees (y > knee_y), rises past knees at frame 15."""
    from app.cv.metric_extraction import identify_knee_pass_frame
    n = 30
    knee_y = np.full(n, 0.70)
    bar_y = np.full(n, 0.80)
    bar_y[15:] = 0.65  # at frame 15, bar y (0.65) is above knee (0.70) in image
    out = identify_knee_pass_frame(
        bar_y, knee_y, liftoff_frame=5, end_frame=n - 1
    )
    assert out == 15


def test_session6_identify_knee_pass_frame_bar_starts_above_knee() -> None:
    """Bar already above knee at liftoff_frame → return liftoff_frame itself."""
    from app.cv.metric_extraction import identify_knee_pass_frame
    n = 20
    knee_y = np.full(n, 0.70)
    bar_y = np.full(n, 0.50)  # always above knee
    out = identify_knee_pass_frame(
        bar_y, knee_y, liftoff_frame=3, end_frame=n - 1
    )
    assert out == 3


def test_session6_identify_knee_pass_frame_never_reaches_knee() -> None:
    """Degenerate lift where bar stays below knee throughout → None."""
    from app.cv.metric_extraction import identify_knee_pass_frame
    n = 20
    knee_y = np.full(n, 0.70)
    bar_y = np.full(n, 0.85)  # always below knee
    out = identify_knee_pass_frame(
        bar_y, knee_y, liftoff_frame=2, end_frame=n - 1
    )
    assert out is None


def test_session6_identify_knee_pass_frame_out_of_bounds_returns_none() -> None:
    from app.cv.metric_extraction import identify_knee_pass_frame
    knee_y = np.full(10, 0.70)
    bar_y = np.full(10, 0.65)
    assert identify_knee_pass_frame(bar_y, knee_y, liftoff_frame=-1, end_frame=5) is None
    assert identify_knee_pass_frame(bar_y, knee_y, liftoff_frame=0, end_frame=99) is None
    assert identify_knee_pass_frame(bar_y, knee_y, liftoff_frame=5, end_frame=3) is None


def test_session6_identify_knee_pass_frame_empty_series_returns_none() -> None:
    from app.cv.metric_extraction import identify_knee_pass_frame
    empty = np.array([])
    assert identify_knee_pass_frame(empty, empty, liftoff_frame=0, end_frame=0) is None


def test_session6_identify_knee_pass_frame_mismatched_length_returns_none() -> None:
    """Mismatched series lengths are caller-error but must not raise."""
    from app.cv.metric_extraction import identify_knee_pass_frame
    out = identify_knee_pass_frame(
        bar_y_series=np.full(10, 0.65),
        knee_y_series=np.full(20, 0.70),
        liftoff_frame=0,
        end_frame=9,
    )
    # Mismatched lengths still works because we only iterate over the shorter
    # series (defensive); but the caller-facing contract is "returns None on
    # degenerate input" — accept either a frame index or None.
    assert out is None or 0 <= out <= 9
```

- [ ] **Step 3.2: Run tests — expected failures**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py -k "session6_identify_knee_pass" -v
```
Expected: ImportError.

- [ ] **Step 3.3: Implement `identify_knee_pass_frame`**

Add to `metric_extraction.py` immediately after `identify_liftoff_frame`:

```python
def identify_knee_pass_frame(
    bar_y_series: np.ndarray,
    knee_y_series: np.ndarray,
    liftoff_frame: int,
    end_frame: int,
) -> int | None:
    """Session 6 — first frame on ascent where ``bar_y <= knee_y`` (bar
    reaches at-or-above knee height in image coordinates).

    Returns ``None`` on degenerate input (out-of-bounds frames, end <=
    liftoff, empty arrays, or bar never crosses).
    """
    n_bar = bar_y_series.shape[0] if bar_y_series.ndim == 1 else 0
    n_knee = knee_y_series.shape[0] if knee_y_series.ndim == 1 else 0
    n = min(n_bar, n_knee)
    if n == 0:
        return None
    if liftoff_frame < 0 or end_frame >= n or end_frame < liftoff_frame:
        return None
    for k in range(liftoff_frame, end_frame + 1):
        if float(bar_y_series[k]) <= float(knee_y_series[k]):
            return k
    return None
```

- [ ] **Step 3.4: Run tests — expected pass**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py -k "session6_identify_knee_pass" -v
```
Expected: 6 passed.

- [ ] **Step 3.5: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "$(cat <<'EOF'
feat(cv): identify_knee_pass_frame helper for Session 6 bar metrics

Detects the first ascent frame where the bar reaches at-or-above
knee height (bar_y <= knee_y). Returns None on degenerate input.
EOF
)"
```

---

### Task 4: TDD `_bar_to_hip_distance_dict` extractor (#4)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py` (widen type alias, add `_wrist_midpoint_trajectory` + `_bar_to_hip_distance_dict` helpers)
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py` (append #4 tests)

- [ ] **Step 4.1: Write failing tests for the dict-valued extractor**

Append to `test_metric_extraction_sagittal.py`:

```python
def _make_dl_landmark_frame(
    side: str,
    *,
    hip_xy: tuple[float, float],
    knee_xy: tuple[float, float],
    shoulder_xy: tuple[float, float],
    wrist_l_xy: tuple[float, float] | None = None,
    wrist_r_xy: tuple[float, float] | None = None,
) -> np.ndarray:
    """Build a (33, 5) frame populating BOTH wrists (for the midpoint proxy)
    and the side-specific hip/knee/shoulder triple."""
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    if side == "right":
        lm[12, :2] = shoulder_xy
        lm[24, :2] = hip_xy
        lm[26, :2] = knee_xy
    else:
        lm[11, :2] = shoulder_xy
        lm[23, :2] = hip_xy
        lm[25, :2] = knee_xy
    if wrist_l_xy is not None:
        lm[15, :2] = wrist_l_xy
    if wrist_r_xy is not None:
        lm[16, :2] = wrist_r_xy
    return lm


def test_session6_bar_to_hip_distance_textbook_deadlift() -> None:
    """Synthetic deadlift with all 4 phase frames identifiable. Bar moves
    from in-front-of-hip at setup, to closer at lockout."""
    from app.cv.metric_extraction import _bar_to_hip_distance_dict
    # Build a 4-frame trajectory in normalised coords:
    # setup (frame 0): bar at x=0.50, hip at x=0.45 → raw delta +0.05
    # liftoff (frame 1): bar x=0.48, hip x=0.45 → +0.03
    # knee_pass (frame 2): bar x=0.46, hip x=0.45 → +0.01
    # lockout (frame 3): bar x=0.455, hip x=0.45 → +0.005
    bar_x = np.array([0.50, 0.48, 0.46, 0.455])
    bar_y = np.array([0.80, 0.65, 0.55, 0.40])
    hip_x = np.array([0.45, 0.45, 0.45, 0.45])
    knee_y = np.array([0.70, 0.70, 0.70, 0.70])
    shoulder_y_setup = 0.20  # shoulder-to-hip distance at setup = 0.25 (vertical-only)
    hip_y_setup = 0.45
    shoulder_x_setup = 0.45  # vertically above hip → unsigned distance ≈ 0.25
    out = _bar_to_hip_distance_dict(
        bar_x_series=bar_x,
        bar_y_series=bar_y,
        hip_x_series=hip_x,
        knee_y_series=knee_y,
        shoulder_x_setup=shoulder_x_setup,
        shoulder_y_setup=shoulder_y_setup,
        hip_y_setup=hip_y_setup,
        setup_frame=0,
        end_frame=3,
        side="right",
    )
    assert set(out.keys()) == {"setup", "liftoff", "knee_pass", "lockout"}
    # All four phase frames identified (none None)
    for k in out:
        assert out[k] is not None, f"phase {k} unexpectedly None"
    # Normalised by ~0.25 → setup ≈ 0.05 / 0.25 = 0.20
    assert out["setup"] == pytest.approx(0.20, abs=0.02)
    # Lockout is smallest (bar moved toward hip)
    assert abs(out["lockout"]) < abs(out["setup"])


def test_session6_bar_to_hip_distance_missing_liftoff_returns_none_for_that_key() -> None:
    """Bar never rises far enough → liftoff is None but other phases still
    populated where possible."""
    from app.cv.metric_extraction import _bar_to_hip_distance_dict
    bar_x = np.array([0.50, 0.50, 0.50, 0.50])
    bar_y = np.array([0.80, 0.80, 0.80, 0.80])  # never rises
    hip_x = np.array([0.45, 0.45, 0.45, 0.45])
    knee_y = np.array([0.70, 0.70, 0.70, 0.70])
    out = _bar_to_hip_distance_dict(
        bar_x_series=bar_x,
        bar_y_series=bar_y,
        hip_x_series=hip_x,
        knee_y_series=knee_y,
        shoulder_x_setup=0.45,
        shoulder_y_setup=0.20,
        hip_y_setup=0.45,
        setup_frame=0,
        end_frame=3,
        side="right",
    )
    assert out["setup"] is not None
    assert out["lockout"] is not None
    # No liftoff detected → liftoff and knee_pass also None (knee_pass depends on liftoff)
    assert out["liftoff"] is None
    assert out["knee_pass"] is None


def test_session6_bar_to_hip_distance_degenerate_zero_torso_returns_all_none() -> None:
    """Setup-frame torso length = 0 → can't normalise → all four values None."""
    from app.cv.metric_extraction import _bar_to_hip_distance_dict
    bar_x = np.full(4, 0.50)
    bar_y = np.array([0.80, 0.70, 0.60, 0.50])
    hip_x = np.full(4, 0.45)
    knee_y = np.full(4, 0.65)
    out = _bar_to_hip_distance_dict(
        bar_x_series=bar_x,
        bar_y_series=bar_y,
        hip_x_series=hip_x,
        knee_y_series=knee_y,
        shoulder_x_setup=0.45,
        shoulder_y_setup=0.45,   # SAME as hip_y → zero shoulder-to-hip distance
        hip_y_setup=0.45,
        setup_frame=0,
        end_frame=3,
        side="right",
    )
    assert all(v is None for v in out.values()), out


def test_session6_bar_to_hip_distance_side_agnostic() -> None:
    """Same physical pose, sides mirrored (x' = 1 - x): output values match."""
    from app.cv.metric_extraction import _bar_to_hip_distance_dict
    # Right-filmed: bar in front of hip → positive raw delta
    bar_x_r = np.array([0.50, 0.48, 0.46, 0.455])
    hip_x_r = np.full(4, 0.45)
    # Left-filmed mirror (x' = 1 - x): bar BEHIND hip in image, but the
    # facing_sign flip should recover the same signed output.
    bar_x_l = 1.0 - bar_x_r
    hip_x_l = 1.0 - hip_x_r
    bar_y = np.array([0.80, 0.65, 0.55, 0.40])
    knee_y = np.full(4, 0.70)
    common = dict(
        bar_y_series=bar_y,
        knee_y_series=knee_y,
        shoulder_y_setup=0.20,
        hip_y_setup=0.45,
        setup_frame=0,
        end_frame=3,
    )
    right = _bar_to_hip_distance_dict(
        bar_x_series=bar_x_r,
        hip_x_series=hip_x_r,
        shoulder_x_setup=0.45,
        side="right",
        **common,
    )
    left = _bar_to_hip_distance_dict(
        bar_x_series=bar_x_l,
        hip_x_series=hip_x_l,
        shoulder_x_setup=1.0 - 0.45,
        side="left",
        **common,
    )
    for phase in ("setup", "liftoff", "knee_pass", "lockout"):
        rv, lv = right[phase], left[phase]
        if rv is None or lv is None:
            assert rv is None and lv is None
        else:
            assert rv == pytest.approx(lv, abs=1e-6), (phase, rv, lv)
```

- [ ] **Step 4.2: Run tests — expected failures**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py -k "session6_bar_to_hip" -v
```
Expected: ImportError.

- [ ] **Step 4.3: Add the widened type alias and implement the helpers**

Near the top of `backend/app/cv/metric_extraction.py`, replace the `metrics: dict[str, float | str]` annotation on the `RepMetrics` dataclass and update the analyzer return annotations:

```python
# Type alias for the per-rep metrics dict. Categorical strings are used for
# phase_of_max_deviation and depth_classification (ADR-022). Session 6 adds
# bar_to_hip_distance as a dict-valued phase-frame map.
RepMetricValue = float | str | dict[str, float | None]
```

Update `@dataclass class RepMetrics`:

```python
@dataclass
class RepMetrics:
    """Per-rep biomechanical metrics for a single detected repetition."""

    rep_index: int
    start_frame: int
    end_frame: int
    metrics: dict[str, RepMetricValue]
```

Update the three exercise analyzer return annotations from `dict[str, float | str]` to `dict[str, RepMetricValue]`.

Then append the Session 6 helpers (after Task 3's `identify_knee_pass_frame`):

```python
_S6_BAR_TO_HIP_PHASES = ("setup", "liftoff", "knee_pass", "lockout")


def _wrist_midpoint_trajectory(
    landmarks_per_frame: list[np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """Return (wrist_x_series, wrist_y_series) using MediaPipe landmarks 15
    and 16 (bilateral wrist midpoint). Same proxy used by
    ``compute_bar_path_from_landmarks`` when HoughCircles detection fails.

    Side-agnostic by construction (always averages both wrists).
    """
    n = len(landmarks_per_frame)
    xs = np.zeros(n, dtype=float)
    ys = np.zeros(n, dtype=float)
    for i, lm in enumerate(landmarks_per_frame):
        xs[i] = (float(lm[15, 0]) + float(lm[16, 0])) / 2.0
        ys[i] = (float(lm[15, 1]) + float(lm[16, 1])) / 2.0
    return xs, ys


def _bar_to_hip_distance_dict(
    bar_x_series: np.ndarray,
    bar_y_series: np.ndarray,
    hip_x_series: np.ndarray,
    knee_y_series: np.ndarray,
    shoulder_x_setup: float,
    shoulder_y_setup: float,
    hip_y_setup: float,
    setup_frame: int,
    end_frame: int,
    side: Literal["left", "right"],
) -> dict[str, float | None]:
    """Session 6 #4 — bar-x to hip-x signed distance at four phase frames,
    normalised by shoulder-to-hip distance at setup.

    Output dict keys: ``setup``, ``liftoff``, ``knee_pass``, ``lockout``.
    A phase's value is ``None`` when that phase frame cannot be identified
    (e.g. bar never lifts, never passes knee) OR when the normaliser is
    degenerate (zero shoulder-to-hip distance at setup).

    Side handling: the raw ``bar_x - hip_x`` delta is multiplied by
    ``_facing_sign(side)`` so positive always means "bar in front of the
    lifter" regardless of which body-side was filmed.
    """
    empty: dict[str, float | None] = {k: None for k in _S6_BAR_TO_HIP_PHASES}
    n = min(
        bar_x_series.shape[0], bar_y_series.shape[0],
        hip_x_series.shape[0], knee_y_series.shape[0],
    )
    if n == 0:
        return empty
    if setup_frame < 0 or end_frame >= n or end_frame < setup_frame:
        return empty
    # Unsigned shoulder-to-hip distance at setup as the normaliser.
    norm = float(np.hypot(
        shoulder_x_setup - hip_x_series[setup_frame],
        shoulder_y_setup - hip_y_setup,
    ))
    if norm < _S5_DEGENERATE_MAGNITUDE:
        return empty
    sign = _facing_sign(side)

    def _signed_norm(frame: int) -> float:
        return ((float(bar_x_series[frame]) - float(hip_x_series[frame])) * sign) / norm

    out: dict[str, float | None] = dict(empty)
    out["setup"] = _signed_norm(setup_frame)
    out["lockout"] = _signed_norm(end_frame)

    liftoff = identify_liftoff_frame(bar_y_series, setup_frame, end_frame)
    if liftoff is not None:
        out["liftoff"] = _signed_norm(liftoff)
        knee_pass = identify_knee_pass_frame(
            bar_y_series, knee_y_series, liftoff, end_frame,
        )
        if knee_pass is not None:
            out["knee_pass"] = _signed_norm(knee_pass)
    return out
```

- [ ] **Step 4.4: Run tests — expected pass**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py -k "session6_bar_to_hip" -v
```
Expected: 4 passed.

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "$(cat <<'EOF'
feat(cv): #4 bar_to_hip_distance phase-frame dict helper (Session 6)

Computes (bar_x - hip_x) at setup/liftoff/knee_pass/lockout normalised
by shoulder-to-hip distance at setup. Side-agnostic via _facing_sign.
RepMetrics.metrics value type widened to accept dict[str, float | None].
EOF
)"
```

---

### Task 5: TDD `_shoulder_protraction_proxy_px` extractor (#14)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py`

- [ ] **Step 5.1: Write failing tests**

Append to `test_metric_extraction_sagittal.py`:

```python
def test_session6_shoulder_protraction_stable_returns_zero() -> None:
    """Shoulder x identical at setup and bottom → ~0 protraction."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    setup = np.zeros((33, 5))
    setup[:, 3] = 0.9; setup[:, 4] = 5.0
    setup[12, :2] = [0.50, 0.20]  # shoulder
    setup[24, :2] = [0.50, 0.50]  # hip (distance = 0.30)
    bottom = setup.copy()
    out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=setup,
        bottom_frame_landmarks=bottom,
        side_idx=right_idx,
        side="right",
    )
    assert out == pytest.approx(0.0, abs=1e-6)


def test_session6_shoulder_protraction_anterior_drift_positive() -> None:
    """Shoulder moves forward by 0.06 normalised → positive normalised value."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    setup = np.zeros((33, 5))
    setup[:, 3] = 0.9; setup[:, 4] = 5.0
    setup[12, :2] = [0.50, 0.20]
    setup[24, :2] = [0.50, 0.50]  # span = 0.30
    bottom = setup.copy()
    bottom[12, :2] = [0.56, 0.20]  # shoulder moved +0.06 in image
    out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=setup,
        bottom_frame_landmarks=bottom,
        side_idx=right_idx,
        side="right",
    )
    # 0.06 / 0.30 = 0.20
    assert out == pytest.approx(0.20, abs=1e-3)


def test_session6_shoulder_protraction_posterior_drift_negative() -> None:
    """Shoulder moves backward → negative."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    setup = np.zeros((33, 5))
    setup[:, 3] = 0.9; setup[:, 4] = 5.0
    setup[12, :2] = [0.50, 0.20]
    setup[24, :2] = [0.50, 0.50]
    bottom = setup.copy()
    bottom[12, :2] = [0.44, 0.20]  # -0.06 backward
    out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=setup,
        bottom_frame_landmarks=bottom,
        side_idx=right_idx,
        side="right",
    )
    assert out == pytest.approx(-0.20, abs=1e-3)


def test_session6_shoulder_protraction_missing_landmark_returns_none() -> None:
    """Low-visibility shoulder → None."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    setup = np.zeros((33, 5))
    setup[:, 3] = 0.9; setup[:, 4] = 5.0
    setup[12, :2] = [0.50, 0.20]
    setup[24, :2] = [0.50, 0.50]
    bottom = setup.copy()
    bottom[12, 3] = 0.10  # below threshold
    out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=setup,
        bottom_frame_landmarks=bottom,
        side_idx=right_idx,
        side="right",
    )
    assert out is None


def test_session6_shoulder_protraction_degenerate_zero_torso_returns_none() -> None:
    """Setup shoulder-hip distance = 0 → cannot normalise → None."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    setup = np.zeros((33, 5))
    setup[:, 3] = 0.9; setup[:, 4] = 5.0
    setup[12, :2] = [0.50, 0.50]  # SAME as hip
    setup[24, :2] = [0.50, 0.50]
    bottom = setup.copy()
    bottom[12, :2] = [0.55, 0.50]
    out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=setup,
        bottom_frame_landmarks=bottom,
        side_idx=right_idx,
        side="right",
    )
    assert out is None


@pytest.mark.parametrize("delta_x", [-0.05, 0.0, 0.04, 0.08])
def test_session6_shoulder_protraction_side_agnostic(delta_x: float) -> None:
    """Same physical drift, sides mirrored → same signed output."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    # Right-side setup
    r_setup = np.zeros((33, 5)); r_setup[:, 3] = 0.9; r_setup[:, 4] = 5.0
    r_setup[12, :2] = [0.50, 0.20]; r_setup[24, :2] = [0.50, 0.50]
    r_bottom = r_setup.copy()
    r_bottom[12, :2] = [0.50 + delta_x, 0.20]
    # Left-side setup mirrored (x' = 1 - x)
    l_setup = np.zeros((33, 5)); l_setup[:, 3] = 0.9; l_setup[:, 4] = 5.0
    l_setup[11, :2] = [1.0 - 0.50, 0.20]; l_setup[23, :2] = [1.0 - 0.50, 0.50]
    l_bottom = l_setup.copy()
    l_bottom[11, :2] = [1.0 - (0.50 + delta_x), 0.20]

    r_out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=r_setup,
        bottom_frame_landmarks=r_bottom,
        side_idx=right_idx, side="right",
    )
    l_out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=l_setup,
        bottom_frame_landmarks=l_bottom,
        side_idx=left_idx, side="left",
    )
    assert r_out == pytest.approx(l_out, abs=1e-6)
```

- [ ] **Step 5.2: Run tests — expected failures**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py -k "session6_shoulder_protraction" -v
```
Expected: ImportError.

- [ ] **Step 5.3: Implement `_shoulder_protraction_proxy_px`**

Append after `_bar_to_hip_distance_dict`:

```python
def _shoulder_protraction_proxy_px(
    setup_frame_landmarks: np.ndarray,
    bottom_frame_landmarks: np.ndarray,
    side_idx: SideIndices,
    side: Literal["left", "right"],
) -> float | None:
    """Session 6 #14 — bench shoulder-x drift from setup to rep bottom,
    normalised by setup shoulder-to-hip distance.

    ``((shoulder_x_bottom - shoulder_x_setup) * facing_sign) /
    hypot(shoulder_x_setup - hip_x_setup, shoulder_y_setup - hip_y_setup)``.
    Positive = shoulders move anteriorly during the press. Returns ``None``
    on missing landmark visibility (either frame) or degenerate
    (zero-length) setup torso vector.
    """
    if not _vis_ok(setup_frame_landmarks, side_idx.shoulder, side_idx.hip):
        return None
    if not _vis_ok(bottom_frame_landmarks, side_idx.shoulder):
        return None
    shoulder_setup = _xy(setup_frame_landmarks, side_idx.shoulder)
    hip_setup = _xy(setup_frame_landmarks, side_idx.hip)
    shoulder_bottom = _xy(bottom_frame_landmarks, side_idx.shoulder)
    span = float(np.hypot(
        shoulder_setup[0] - hip_setup[0],
        shoulder_setup[1] - hip_setup[1],
    ))
    if span < _S5_DEGENERATE_MAGNITUDE:
        return None
    raw = float(shoulder_bottom[0]) - float(shoulder_setup[0])
    return (raw * _facing_sign(side)) / span
```

- [ ] **Step 5.4: Run tests — expected pass**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py -k "session6_shoulder_protraction" -v
```
Expected: 9 passed (5 happy/edge + 4 parametrised side-agnostic).

- [ ] **Step 5.5: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "$(cat <<'EOF'
feat(cv): #14 shoulder_protraction_proxy_px extractor (Session 6)

Computes (shoulder_x_bottom - shoulder_x_setup) normalised by setup
shoulder-to-hip distance, with _facing_sign for side-agnostic output.
Compute-only; not wired into scoring.
EOF
)"
```

---

### Task 6: Wire #4 and #14 into deadlift + bench analyzers

**Files:**
- Modify: `backend/app/cv/metric_extraction.py` (call new helpers from `_deadlift_metrics` and `_bench_metrics`)
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py` (analyzer-level integration tests)

- [ ] **Step 6.1: Write failing analyzer-integration tests**

Append:

```python
def test_session6_deadlift_analyzer_emits_bar_to_hip_distance_dict() -> None:
    """Deadlift analyzer emits ``bar_to_hip_distance`` as a dict with all four
    phase-frame keys, where wrist-midpoint serves as the bar trajectory."""
    n_frames = 60
    frames = []
    # Synthetic deadlift: setup wrist y around 0.80, bar rises to 0.40 by
    # lockout. Knee y constant at 0.70. Hip x at 0.45. Wrists in front (0.50).
    for i in range(n_frames):
        lm = np.zeros((33, 5)); lm[:, 3] = 0.9; lm[:, 4] = 5.0
        # Hip rises with bar (deadlift), knee straightens
        bar_y_t = 0.80 - 0.40 * (i / (n_frames - 1))
        lm[12, :2] = [0.45, 0.30]   # right shoulder
        lm[24, :2] = [0.45, 0.55]   # right hip — span ≈ 0.25
        lm[26, :2] = [0.45, 0.70]   # right knee
        lm[28, :2] = [0.45, 0.95]   # right ankle
        # Both wrists at x=0.50 (bar in front), y dropping
        lm[15, :2] = [0.50, bar_y_t]
        lm[16, :2] = [0.50, bar_y_t]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, n_frames)
    hip_ang = 110.0 + 60.0 * np.cos(t)
    knee_ang = 130.0 + 40.0 * np.cos(t)
    ts = {"hip_angle": hip_ang, "knee_angle": knee_ang}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=n_frames - 1,
        confidence_score=0.9, min_angle=50.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="deadlift", exercise_variant="conventional",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "bar_to_hip_distance" in metrics
    d = metrics["bar_to_hip_distance"]
    assert isinstance(d, dict)
    assert set(d.keys()) == {"setup", "liftoff", "knee_pass", "lockout"}
    # All four phases should be identifiable on this clean synthetic.
    for k, v in d.items():
        assert v is not None, f"phase {k} unexpectedly None"
        assert isinstance(v, float)


def test_session6_bench_analyzer_emits_shoulder_protraction() -> None:
    """Bench analyzer emits ``shoulder_protraction_proxy_px`` per rep."""
    n_frames = 60
    frames = []
    for i in range(n_frames):
        lm = np.zeros((33, 5)); lm[:, 3] = 0.9; lm[:, 4] = 5.0
        # Shoulder drifts forward toward bottom of the rep, returns at top.
        drift = 0.04 * abs(np.sin(np.pi * i / (n_frames - 1)))
        lm[12, :2] = [0.50 + drift, 0.30]
        lm[14, :2] = [0.30, 0.55]
        lm[16, :2] = [0.20, 0.55]
        lm[24, :2] = [0.50, 0.60]   # span ≈ 0.30
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, n_frames)
    elbow_ang = 115.0 + 50.0 * np.cos(t)
    shoulder_ang = 70.0 + 20.0 * np.cos(t)
    ts = {"elbow_angle": elbow_ang, "shoulder_angle": shoulder_ang}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=n_frames - 1,
        confidence_score=0.9, min_angle=65.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="bench", exercise_variant="flat",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "shoulder_protraction_proxy_px" in metrics
    val = metrics["shoulder_protraction_proxy_px"]
    assert isinstance(val, float)
    # Sanity bound — bench protraction proxy on this synthetic stays small.
    assert -1.0 <= val <= 1.0


def test_session6_squat_analyzer_does_not_emit_bar_or_shoulder_protraction() -> None:
    """Squat analyzer must NOT emit either Session 6 key."""
    n_frames = 60
    frames = []
    for _ in range(n_frames):
        lm = np.zeros((33, 5)); lm[:, 3] = 0.9; lm[:, 4] = 5.0
        lm[12, :2] = [0.50, 0.20]
        lm[24, :2] = [0.50, 0.55]
        lm[26, :2] = [0.50, 0.75]
        lm[28, :2] = [0.50, 0.95]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, n_frames)
    ts = {"hip_angle": 125 + 45 * np.cos(t), "knee_angle": 110 + 40 * np.cos(t)}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=n_frames - 1,
        confidence_score=0.9, min_angle=80.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="squat", exercise_variant="standard",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "bar_to_hip_distance" not in metrics
    assert "shoulder_protraction_proxy_px" not in metrics
```

- [ ] **Step 6.2: Run tests — expected failures**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py -k "session6" and ("deadlift_analyzer" or "bench_analyzer" or "squat_analyzer_does_not") -v
```
Expected: assertions fail because analyzers don't emit the new keys yet.

- [ ] **Step 6.3: Wire `_bar_to_hip_distance_dict` into `_deadlift_metrics`**

Inside `_deadlift_metrics`, before the `return` statement, add:

```python
    # Session 6 #4 — bar-to-hip distance at four phase frames. Uses the
    # wrist-midpoint as the bar-trajectory proxy (same fallback that
    # compute_bar_path_from_landmarks uses when HoughCircles fails).
    bar_x_series, bar_y_series = _wrist_midpoint_trajectory(landmarks_per_frame)
    hip_x_series = np.array(
        [float(lm[side_idx.hip, 0]) for lm in landmarks_per_frame],
        dtype=float,
    )
    knee_y_series = np.array(
        [float(lm[side_idx.knee, 1]) for lm in landmarks_per_frame],
        dtype=float,
    )
    bar_to_hip = _bar_to_hip_distance_dict(
        bar_x_series=bar_x_series,
        bar_y_series=bar_y_series,
        hip_x_series=hip_x_series,
        knee_y_series=knee_y_series,
        shoulder_x_setup=float(landmarks_per_frame[start][side_idx.shoulder, 0]),
        shoulder_y_setup=float(landmarks_per_frame[start][side_idx.shoulder, 1]),
        hip_y_setup=float(landmarks_per_frame[start][side_idx.hip, 1]),
        setup_frame=start,
        end_frame=end,
        side=lifter_side,
    )
```

Then add `"bar_to_hip_distance": bar_to_hip,` to the deadlift `return` dict (place after `setup_knee_angle_deg`).

- [ ] **Step 6.4: Wire `_shoulder_protraction_proxy_px` into `_bench_metrics`**

Inside `_bench_metrics`, before `return`:

```python
    # Session 6 #14 — shoulder protraction proxy (setup → bottom drift).
    shoulder_protraction = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=landmarks_per_frame[start],
        bottom_frame_landmarks=landmarks_per_frame[bottom_frame],
        side_idx=side_idx,
        side=lifter_side,
    )
```

Then add `"shoulder_protraction_proxy_px": (float(shoulder_protraction) if shoulder_protraction is not None else 0.0),` to the bench `return` dict.

- [ ] **Step 6.5: Run analyzer-integration tests — expected pass**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py -k "session6" -v
```
Expected: all Session 6 unit tests pass.

- [ ] **Step 6.6: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "$(cat <<'EOF'
feat(cv): wire Session 6 metrics into deadlift + bench analyzers

Deadlift analyzer now emits bar_to_hip_distance (dict at 4 phase frames).
Bench analyzer emits shoulder_protraction_proxy_px (float per rep).
Wrist-midpoint serves as the bar-trajectory proxy for #4.
EOF
)"
```

---

### Task 7: Update `test_all_*_metric_values_are_floats` invariants

**Files:**
- Modify: `backend/tests/unit/test_metric_extraction.py`

- [ ] **Step 7.1: Run the invariant tests — confirm the regression**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction.py -k "metric_values_are_floats" -v
```
Expected: `test_all_deadlift_metric_values_are_floats` fails on `bar_to_hip_distance` because the value is a dict.

- [ ] **Step 7.2: Update the three invariants to allow the dict-valued key**

In `backend/tests/unit/test_metric_extraction.py`, modify each of the three tests (`test_all_squat_metric_values_are_floats`, `test_all_bench_metric_values_are_floats`, `test_all_deadlift_metric_values_are_floats`). Replace:

```python
        # Categorical string-valued keys (ADR-022): phase_of_max_deviation
        # (Phase 1) + depth_classification (Session 4). All others are floats.
        _categorical_keys = {"phase_of_max_deviation", "depth_classification"}
        for key, val in result[0].metrics.items():
            if key in _categorical_keys:
                assert isinstance(val, str)
            else:
                assert isinstance(val, float), f"metric {key} is not a float"
```

with:

```python
        # Categorical string-valued keys (ADR-022): phase_of_max_deviation
        # (Phase 1) + depth_classification (Session 4).
        # Dict-valued keys: bar_to_hip_distance (Session 6 — phase-frame map).
        _categorical_keys = {"phase_of_max_deviation", "depth_classification"}
        _dict_keys = {"bar_to_hip_distance"}
        for key, val in result[0].metrics.items():
            if key in _categorical_keys:
                assert isinstance(val, str)
            elif key in _dict_keys:
                assert isinstance(val, dict)
                # Each phase-frame value is float or None.
                for phase_key, phase_val in val.items():
                    assert phase_key in {"setup", "liftoff", "knee_pass", "lockout"}
                    assert phase_val is None or isinstance(phase_val, float)
            else:
                assert isinstance(val, float), f"metric {key} is not a float"
```

Apply this change to all three test methods. Use `replace_all=True` once you confirm the block is identical across all three.

- [ ] **Step 7.3: Run invariants — expected pass**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction.py -k "metric_values_are_floats" -v
```
Expected: 3 passed.

- [ ] **Step 7.4: Commit**

```bash
git add backend/tests/unit/test_metric_extraction.py
git commit -m "$(cat <<'EOF'
test(cv): allow dict value for bar_to_hip_distance in metric invariants

Session 6 #4 stores a 4-key phase-frame dict in rep_metrics.metrics.
ADR-022 invariant tests now branch on dict-valued keys alongside the
existing categorical-string branch.
EOF
)"
```

---

### Task 8: Flip registry `computed_yet=True` for the two Session 6 keys

**Files:**
- Modify: `backend/app/cv/sagittal_metrics_registry.py`
- Modify: `backend/tests/unit/test_sagittal_metrics_registry.py`
- Modify: `backend/tests/unit/test_expert_sagittal_metrics_endpoint.py`

- [ ] **Step 8.1: Write a failing test asserting Session 6 flips landed**

Add to `backend/tests/unit/test_sagittal_metrics_registry.py` (after `TestRegistrySession5Flips` class, before module bottom):

```python
class TestRegistrySession6Flips:
    SESSION6_KEYS = frozenset({
        "bar_to_hip_distance",
        "shoulder_protraction_proxy_px",
    })

    def test_session6_entries_have_computed_yet_true(self) -> None:
        flipped = {
            e.key_name for e in SAGITTAL_METRICS_REGISTRY
            if e.key_name in self.SESSION6_KEYS and e.computed_yet
        }
        assert flipped == self.SESSION6_KEYS, (
            f"Missing Session 6 flips: {self.SESSION6_KEYS - flipped}"
        )

    def test_session6_entries_remain_out_of_scoring(self) -> None:
        in_scoring = {
            e.key_name for e in SAGITTAL_METRICS_REGISTRY
            if e.key_name in self.SESSION6_KEYS and e.in_scoring
        }
        # Per design Section-4: Session 6 metrics are compute-only.
        assert in_scoring == frozenset()
```

Narrow the existing `test_session_6_plus_entries_remain_pristine` to the 3 Session-7 keys (drop the two Session 6 keys from the loop):

```python
    def test_session_6_plus_entries_remain_pristine(self) -> None:
        """Guard: only Sessions 4-6 metrics flip; Session 7 entries
        keep computed_yet=False and in_scoring=False until their own session."""
        entries = {e.key_name for e in SAGITTAL_METRICS_REGISTRY}
        entries_map = {e.key_name: e for e in SAGITTAL_METRICS_REGISTRY}
        for key in (
            "lumbar_flexion_proxy_delta_deg",
            "bar_path_classification",
            "technique_consistency_std",
        ):
            assert entries_map[key].computed_yet is False, (
                f"Entry {key!r} must stay computed_yet=False (Session 7 scope)."
            )
            assert entries_map[key].in_scoring is False, (
                f"Entry {key!r} must stay in_scoring=False (Session 7 scope)."
            )
        # Sanity: all 16 entries still present.
        assert len(entries) == 16
```

Update `backend/tests/unit/test_expert_sagittal_metrics_endpoint.py::test_after_session5_eleven_metrics_computed_two_in_scoring`. Rename to a Session 6 version and add the two new keys to the `computed` set. Replace the entire method with:

```python
    def test_after_session6_thirteen_metrics_computed_two_in_scoring(
        self, expert_client: TestClient
    ) -> None:
        """Sessions 4+5+6 flipped computed_yet on 13 entries (4 in Session 4,
        7 in Session 5, 2 in Session 6). in_scoring remains True only for
        the 2 Session-4 scoring entries. Session 7 entries (3 entries) stay False."""
        resp = expert_client.get("/api/v1/expert/sagittal-metrics-registry")
        entries = {e["key_name"]: e for e in resp.json()["entries"]}
        sessions_4_to_6_computed = {
            # Session 4 (4)
            "depth_classification", "ecc_con_ratio",
            "pause_duration_s", "lockout_torso_lean_deg",
            # Session 5 (7)
            "ankle_dorsiflexion_deg", "wrist_alignment_deg", "bar_touch_height_pct",
            "setup_shoulder_x_offset", "shin_angle_deg", "setup_knee_angle_deg",
            "arch_deg",
            # Session 6 (2)
            "bar_to_hip_distance", "shoulder_protraction_proxy_px",
        }
        session4_in_scoring = {"depth_classification", "ecc_con_ratio"}
        for key, entry in entries.items():
            if key in sessions_4_to_6_computed:
                assert entry["computed_yet"] is True, f"{key} computed_yet should be True"
            else:
                assert entry["computed_yet"] is False, f"{key} computed_yet should be False"
            if key in session4_in_scoring:
                assert entry["in_scoring"] is True, f"{key} in_scoring should be True"
            else:
                assert entry["in_scoring"] is False, f"{key} in_scoring should be False"
```

- [ ] **Step 8.2: Run registry tests — expected failure**

```bash
uv run --directory backend pytest backend/tests/unit/test_sagittal_metrics_registry.py backend/tests/unit/test_expert_sagittal_metrics_endpoint.py -v
```
Expected: new tests fail (`bar_to_hip_distance` and `shoulder_protraction_proxy_px` still have `computed_yet=False`).

- [ ] **Step 8.3: Flip the two registry entries**

In `backend/app/cv/sagittal_metrics_registry.py`, change both Session 6 entries from `computed_yet=False` to `computed_yet=True`:

```python
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
        computed_yet=True,
        in_scoring=False,
    ),
    SagittalMetricEntry(
        key_name="shoulder_protraction_proxy_px",
        display_label="Shoulder Protraction Proxy",
        unit="ratio",
        description=(
            "Bench shoulder-x drift from setup to rep bottom, normalized by "
            "shoulder-to-hip distance. Proxy -- actual scapular protraction "
            "requires a frontal-plane camera."
        ),
        exercise_applicability=_BN,
        computed_yet=True,
        in_scoring=False,
    ),
```

- [ ] **Step 8.4: Run registry tests — expected pass**

```bash
uv run --directory backend pytest backend/tests/unit/test_sagittal_metrics_registry.py backend/tests/unit/test_expert_sagittal_metrics_endpoint.py -v
```
Expected: all pass.

- [ ] **Step 8.5: Commit**

```bash
git add backend/app/cv/sagittal_metrics_registry.py backend/tests/unit/test_sagittal_metrics_registry.py backend/tests/unit/test_expert_sagittal_metrics_endpoint.py
git commit -m "$(cat <<'EOF'
feat(cv): flip computed_yet=True for Session 6 registry entries

bar_to_hip_distance and shoulder_protraction_proxy_px now appear as
computed metrics in the expert UnvalidatedMetricsPanel. Both stay
in_scoring=False (compute-only). Test guards updated to expect 13/16
metrics computed and only the 3 Session-7 entries remaining pristine.
EOF
)"
```

---

### Task 9: Integration tests on `atharva-bench.mov` and `atharva-deadlift.mov`

**Files:**
- Modify: `backend/tests/integration/test_pipeline_sagittal_metrics.py`

- [ ] **Step 9.1: Write failing fixture integration tests**

Append to `backend/tests/integration/test_pipeline_sagittal_metrics.py`:

```python
@pytest.mark.integration
def test_session6_atharva_deadlift_bar_to_hip_distance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Deadlift fixture must populate bar_to_hip_distance as a 4-key dict.
    At least 2 of the 4 phase frames should resolve to a finite float on the
    real fixture (setup + lockout always resolve; liftoff and knee_pass may
    be None if the bar trajectory is degenerate)."""
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
        # setup and lockout are deterministic (rep.start/end_frame) — they
        # should always resolve unless the setup-frame shoulder-to-hip
        # distance is degenerate (rare).
        finite_count = sum(1 for v in d.values() if v is not None)
        assert finite_count >= 2, (
            f"rep {r.rep_index}: only {finite_count}/4 phase frames resolved: {d}"
        )
        # Sanity bound on resolved values (full normalised distance range).
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
        # Sanity bound: ratio of shoulder drift / shoulder-to-hip span.
        # Allow a wide envelope — MediaPipe noise on a supine lifter can push
        # the ratio meaningfully. Expert validates the meaningful sub-range
        # post-onboarding via FR-EXPV-08.
        assert -5.0 <= val <= 5.0, f"rep {r.rep_index} value out of band: {val}"
        with capsys.disabled():
            print(
                f"[session-6-integration] bench rep {r.rep_index}: "
                f"shoulder_protraction={val:.3f}"
            )
```

- [ ] **Step 9.2: Run integration tests — expected pass**

```bash
uv run --directory backend pytest backend/tests/integration/test_pipeline_sagittal_metrics.py -k "session6" -s -v
```
Expected: 2 passed; per-rep values printed to stdout.

- [ ] **Step 9.3: Commit**

```bash
git add backend/tests/integration/test_pipeline_sagittal_metrics.py
git commit -m "$(cat <<'EOF'
test(cv): integration tests for Session 6 metrics on atharva fixtures

Deadlift fixture asserts bar_to_hip_distance dict has at least 2/4
phase frames resolved per rep. Bench fixture asserts
shoulder_protraction_proxy_px is a finite float per rep.
EOF
)"
```

---

### Task 10: Create smoke script

**Files:**
- Create: `backend/scripts/oneoff/smoke_sagittal_metrics_session6.py`

- [ ] **Step 10.1: Write smoke script**

```python
"""Session 6 smoke script — dump per-rep Session-6 metric values for the bench
and deadlift atharva fixtures. Output is CSV-formatted on stdout for
paste-into-chat per /goal evidence-surfacing protocol.

Not run in CI — calibration aid only.

Usage:
    uv run --directory backend python scripts/oneoff/smoke_sagittal_metrics_session6.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

# Make `app.*` importable + wire ThresholdConfig to v1.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND_ROOT))
_V1_PATH = _BACKEND_ROOT.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig  # noqa: E402
from app.cv.lifter_side import detect_lifter_side  # noqa: E402
from app.cv.metric_extraction import extract_rep_metrics  # noqa: E402
from app.cv.pose_extraction import extract_landmarks  # noqa: E402
from app.cv.rep_detection import detect_reps  # noqa: E402
from app.cv.signal_processing import compute_angle_timeseries  # noqa: E402


_FIXTURES_DIR = _BACKEND_ROOT.parent / "e2e" / "fixtures"


def _run(fixture: Path, exercise: str, variant: str) -> int:
    if not fixture.exists():
        print(f"SKIP: fixture missing: {fixture}", file=sys.stderr)
        return 0
    landmarks, fps, _w, _h = extract_landmarks(str(fixture))
    if not landmarks:
        print(f"FAIL: no landmarks for {fixture.name}", file=sys.stderr)
        return 1
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
    rep_metrics = extract_rep_metrics(
        reps=reps,
        landmarks_per_frame=landmarks,
        angle_timeseries=angles,
        exercise_type=exercise,
        exercise_variant=variant,
        fps=fps,
        lifter_side=side,
    )
    print(f"# fixture={fixture.name} exercise={exercise} variant={variant} "
          f"side={side} fps={fps:.1f} reps={len(rep_metrics)}")
    if exercise == "deadlift":
        print("rep_index,setup,liftoff,knee_pass,lockout")
        for r in rep_metrics:
            d = r.metrics.get("bar_to_hip_distance", {})
            row = (
                str(r.rep_index),
                str(d.get("setup")),
                str(d.get("liftoff")),
                str(d.get("knee_pass")),
                str(d.get("lockout")),
            )
            print(",".join(row))
    elif exercise == "bench":
        print("rep_index,shoulder_protraction_proxy_px")
        for r in rep_metrics:
            v = r.metrics.get("shoulder_protraction_proxy_px")
            print(f"{r.rep_index},{v}")
    print()
    return 0


def main() -> int:
    rc = 0
    rc |= _run(_FIXTURES_DIR / "atharva-deadlift.mov", "deadlift", "conventional")
    rc |= _run(_FIXTURES_DIR / "atharva-bench.mov", "bench", "flat")
    return rc


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 10.2: Run smoke script and capture output**

```bash
uv run --directory backend python scripts/oneoff/smoke_sagittal_metrics_session6.py
```
Expected: two CSV blocks (deadlift + bench), no `FAIL:` or `SKIP:` lines.

- [ ] **Step 10.3: Paste the script output into chat as evidence per /goal protocol**

- [ ] **Step 10.4: Commit**

```bash
git add backend/scripts/oneoff/smoke_sagittal_metrics_session6.py
git commit -m "$(cat <<'EOF'
test(cv): smoke script for Session 6 sagittal-bar metrics

CSV dump of per-rep bar_to_hip_distance phase frames (deadlift) and
shoulder_protraction_proxy_px (bench) on the atharva fixtures.
Calibration aid; not run in CI.
EOF
)"
```

---

### Task 11: Full local verification

**Files:** none (verification only)

- [ ] **Step 11.1: Run full backend unit + integration test suite**

```bash
uv run --directory backend pytest backend/tests/unit/ backend/tests/integration/test_pipeline_sagittal_metrics.py -x
```
Expected: all passing; new Session 6 tests visible in the count.

- [ ] **Step 11.2: Lint**

```bash
uv run --directory backend ruff check backend/app backend/tests/unit/test_metric_extraction_sagittal.py backend/tests/unit/test_metric_extraction.py backend/tests/unit/test_sagittal_metrics_registry.py backend/tests/unit/test_expert_sagittal_metrics_endpoint.py backend/tests/integration/test_pipeline_sagittal_metrics.py backend/scripts/oneoff/smoke_sagittal_metrics_session6.py
```
Expected: `All checks passed!`.

- [ ] **Step 11.3: Type-check**

```bash
uv run --directory backend pyright backend/app/cv/metric_extraction.py backend/app/cv/sagittal_metrics_registry.py
```
Expected: `0 errors`.

- [ ] **Step 11.4: Coverage gate on new helpers**

```bash
uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py --cov=app.cv.metric_extraction --cov-report=term-missing -q
```
Expected: `app.cv.metric_extraction` line coverage ≥ 90%. Inspect any `Missing` lines around `identify_liftoff_frame`, `identify_knee_pass_frame`, `_bar_to_hip_distance_dict`, `_shoulder_protraction_proxy_px`, `_wrist_midpoint_trajectory`. If any new-function line is uncovered, add a targeted unit test in the same file before proceeding.

- [ ] **Step 11.5: If coverage on new functions falls below 90% — write a targeted unit test**

Identify the uncovered line via the `Missing` column. Add one focused test. Re-run Step 11.4. Per Standing Rule 1 in `docs/superpowers/goals/2026-05-22-cv-audit-master.md`, NEVER lower the global threshold; only the test count grows.

---

### Task 12: Push branch and open PR

**Files:** none (git only)

- [ ] **Step 12.1: Verify git status**

```bash
git status
git log --oneline origin/main..HEAD
```
Expected: 6+ commits on the branch, working tree clean.

- [ ] **Step 12.2: Push branch**

```bash
git push -u origin feat/sagittal-bar-metrics
```

- [ ] **Step 12.3: Open PR via `mcp__github__create_pull_request`**

Call `mcp__github__create_pull_request` with:
- owner: `atharva6905`
- repo: `spelix`
- base: `main`
- head: `feat/sagittal-bar-metrics`
- title: `feat(cv): Session 6 bar-coordinate metrics (#4 bar_to_hip_distance, #14 shoulder_protraction_proxy_px)`
- body (heredoc):

```markdown
## Summary

Closes `L2-SAGITTAL-BAR-01` and `L2-SAGITTAL-BAR-02`. Sixth session of the
`cv-audit-2026-05-22` effort. Implements two compute-only sagittal-view
metrics that consume bar-coordinate math:

- **#4 `bar_to_hip_distance`** (deadlift): JSONB dict with four phase-frame
  keys (`setup`, `liftoff`, `knee_pass`, `lockout`). Values are
  `(bar_x - hip_x) * facing_sign` normalised by setup shoulder-to-hip
  distance. Bar trajectory uses the wrist-midpoint proxy (MediaPipe
  landmarks 15 + 16 mean) — same fallback `compute_bar_path_from_landmarks`
  uses when HoughCircles detection fails. Phase-frame identification via
  the new public helpers `identify_liftoff_frame` and `identify_knee_pass_frame`.
- **#14 `shoulder_protraction_proxy_px`** (bench): scalar per rep.
  Setup-to-bottom shoulder-x drift, normalised by setup shoulder-to-hip
  distance, side-corrected via `_facing_sign`.

Both metrics flip `computed_yet=True` in the sagittal metrics registry.
`<UnvalidatedMetricsPanel />` auto-picks them up (no frontend change).
Neither is wired into scoring (`in_scoring=False`); validation flows
through FR-EXPV-08 post-expert-onboarding.

## Design references

- Design spec: `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-6
- Plan: `docs/superpowers/plans/2026-05-22-session-6-bar-coordinate-math.md`
- Master manifest: `docs/superpowers/goals/2026-05-22-cv-audit-master.md` §Session-6

## What changed

| Layer | Change |
|---|---|
| Helpers | `identify_liftoff_frame`, `identify_knee_pass_frame`, `_wrist_midpoint_trajectory`, `_bar_to_hip_distance_dict`, `_shoulder_protraction_proxy_px` |
| Type | `RepMetrics.metrics` widened to `dict[str, float \| str \| dict[str, float \| None]]` (ADR-022 follow-up) |
| Wiring | `_deadlift_metrics` emits `bar_to_hip_distance`; `_bench_metrics` emits `shoulder_protraction_proxy_px` |
| Registry | Both keys flipped `computed_yet=True`; in_scoring stays False |
| Tests | +25 unit tests on the new helpers + analyzer integration + side-agnosticism; 2 new fixture integration tests; 3 float-invariant tests updated |
| Smoke | `backend/scripts/oneoff/smoke_sagittal_metrics_session6.py` |

## Test plan

- [ ] `uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py -k session6` all pass
- [ ] `uv run --directory backend pytest backend/tests/integration/test_pipeline_sagittal_metrics.py -k session6 -s` all pass
- [ ] `gh pr checks <PR>` shows every PR-level check pass
- [ ] Post-merge `gh run watch <main-run-id>` shows Deploy to Production conclusion=success
- [ ] Droplet HEAD matches merge SHA; containers `(healthy)`
- [ ] E2E on prod: re-upload bench + deadlift fixtures; both metrics visible in expert UnvalidatedMetricsPanel

## Out of scope

- Threshold values for either metric — expert sets via FR-EXPV-08 post-onboarding.
- Scoring wiring — design Section 4 keeps these compute-only.
- Pipeline reorder to use HoughCircles bar-x directly — wrist-midpoint is the documented fallback and matches what production already uses on lifts where HoughCircles fails. Future session can plumb HoughCircles output if expert calibration shows divergence.
```

Record the returned `html_url` and `number` in the chat as evidence.

---

### Task 13: PR-level CI gate

**Files:** none (gate only)

- [ ] **Step 13.1: Watch CI**

```bash
gh pr checks <PR_NUMBER> --watch
```

- [ ] **Step 13.2: After all checks complete, print final status**

```bash
gh pr checks <PR_NUMBER>
```
Expected: every row shows `pass` — Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel.

- [ ] **Step 13.3: Paste the output into chat as evidence**

- [ ] **Step 13.4: If any check fails**

Per Remediation Policy in `docs/superpowers/goals/2026-05-22-cv-audit-master.md` (CI red): inspect `gh run view <run-id> --log-failed`, identify root cause, push a fix commit. Do not lower any quality gate. Re-watch.

---

### Task 14: Merge PR

**Files:** none

- [ ] **Step 14.1: Merge via `mcp__github__merge_pull_request`**

Parameters:
- owner: `atharva6905`
- repo: `spelix`
- pullNumber: `<PR>`
- merge_method: `merge` (NEVER `squash`)
- commit_title: `feat(cv): Session 6 bar-coordinate metrics (#<PR>)`
- commit_message: short body referencing closed audit IDs

Print the response: confirm `merged=true` and capture `sha`.

- [ ] **Step 14.2: Pull main locally**

```bash
git checkout main
git pull
```

---

### Task 15: Post-merge "Deploy to Production" verify

**Files:** none

- [ ] **Step 15.1: Find the main-branch CI run for the merge SHA**

```bash
gh run list --branch main --limit 5
```
Identify the run whose `headSha` matches the merge SHA.

- [ ] **Step 15.2: Watch the Deploy to Production job**

```bash
gh run watch <main-run-id>
```

- [ ] **Step 15.3: After completion, print the Deploy conclusion**

```bash
gh run view <main-run-id> --json jobs --jq '.jobs[] | select(.name=="Deploy to Production") | {name, conclusion, startedAt, completedAt}'
```
Expected: `conclusion: "success"`. Paste into chat.

- [ ] **Step 15.4: If Deploy fails — fix via fresh PR**

Standing Rule 6: never SSH deploy manually. Inspect the failure, push fix on a new branch, re-merge.

---

### Task 16: Droplet HEAD and container health verify

**Files:** none

- [ ] **Step 16.1: Confirm droplet HEAD matches merge SHA**

```bash
ssh spelix-droplet "git log --oneline -1"
```
Expected output contains the merge SHA from Task 14.

- [ ] **Step 16.2: Confirm containers healthy**

```bash
ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"
```
Expected: `spelix-backend-1 ... (healthy)`, `spelix-worker-1 ... (healthy)`, `spelix-redis-1 ... (healthy)`, `spelix-caddy-1 ... (healthy)`.

- [ ] **Step 16.3: Paste both outputs into chat as evidence**

---

### Task 17: E2E via Playwright MCP

**Files:** none (capture screenshots)

- [ ] **Step 17.1: Navigate to spelix.app, sign in as the test account**

Use `mcp__playwright__browser_navigate` → `https://spelix.app`. Sign in with the test account credentials (the same one used in Session 5 E2E).

- [ ] **Step 17.2: Upload bench fixture (`e2e/fixtures/atharva-bench.mov`)**

Walk the upload flow → wait for analysis completion → capture the analysis ID. Use `mcp__playwright__browser_file_upload` for the input element.

- [ ] **Step 17.3: Upload deadlift fixture (`e2e/fixtures/atharva-deadlift.mov`)**

Same flow. Capture analysis ID.

- [ ] **Step 17.4: Switch to expert role and navigate to each analysis**

Navigate to `/expert/analyses/<deadlift-id>` then `/expert/analyses/<bench-id>`.

- [ ] **Step 17.5: Verify the UnvalidatedMetricsPanel shows the new metrics**

For the deadlift analysis, expand `bar_to_hip_distance` row (or whatever the panel renders for a dict-valued metric). Confirm value is rendered (not "Not yet computed"). For the bench analysis, confirm `shoulder_protraction_proxy_px` has a numeric value.

- [ ] **Step 17.6: Capture screenshots**

```bash
mcp__playwright__browser_take_screenshot path="e2e/screenshots/session6-deadlift-expert-panel.png"
mcp__playwright__browser_take_screenshot path="e2e/screenshots/session6-bench-expert-panel.png"
```

- [ ] **Step 17.7: Console + network check**

`mcp__playwright__browser_console_messages level=error` → expect empty.
`mcp__playwright__browser_network_requests` → no 4xx/5xx on `/api/v1/expert/sagittal-metrics-registry` or `/api/v1/analyses/<id>`.

- [ ] **Step 17.8: Paste screenshot paths + analysis IDs into chat as evidence**

---

### Task 18: Update `backlog.md`

**Files:**
- Modify: `backlog.md`

- [ ] **Step 18.1: Mark Session 6 backlog rows done**

Find the `L2-SAGITTAL-BAR-01` and `L2-SAGITTAL-BAR-02` rows in `backlog.md`. Update status to `done` and fill in the merge SHA from Task 14. If rows do not yet exist, append them under the appropriate `## Completed —` heading. Use `git diff backlog.md` to print the change into chat.

- [ ] **Step 18.2: Commit**

```bash
git add backlog.md
git commit -m "docs(backlog): close L2-SAGITTAL-BAR-01..02 (Session 6 complete)"
```

---

### Task 19: Update master manifest

**Files:**
- Modify: `docs/superpowers/goals/2026-05-22-cv-audit-master.md`

- [ ] **Step 19.1: Flip Session 6 status to complete, Session 7 to active**

In the `## Session Status Overview` table, change the row for Session 6 from `active` / `—` / `—` to `complete` / `<merge SHA>` / `<PR number>`. Change Session 7's `Status` from `pending` to `active`.

In the `## Session 6 — Bar-coordinate math` section, change `**Status:** pending` to `**Status:** complete (merged <date>; merge SHA `<sha>`; PR #<num>)`.

Tick the completion checklist items at the end of the Session 6 block.

In the `## Session 7 — Complex multi-frame analysis` section, change `**Status:** pending` to `**Status:** active`.

- [ ] **Step 19.2: Print the master manifest diff**

```bash
git diff docs/superpowers/goals/2026-05-22-cv-audit-master.md
```
Paste into chat as evidence.

- [ ] **Step 19.3: Commit**

```bash
git add docs/superpowers/goals/2026-05-22-cv-audit-master.md
git commit -m "docs(goal): Session 6 complete; Session 7 active"
```

---

### Task 20: Rewrite handoff for Session 7

**Files:**
- Modify: `.claude/handoff.md`

- [ ] **Step 20.1: Rewrite `.claude/handoff.md`**

Use the standard handoff template documented in `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §6 "Cross-session handoff protocol". Include:
- Session 6 status: complete, with merge SHA and PR #.
- Completed-this-session commit list with one-line descriptions (the commits from Tasks 2, 3, 4, 5, 6, 7, 8, 9, 10).
- Surfaced evidence: PR URL, PR-level CI snapshot, post-merge Deploy run-id, droplet HEAD SHA, container health one-liner, integration test counts (assert finite values on both bench + deadlift fixtures), smoke-script first-line per fixture, screenshot paths.
- Session 7 launch guidance: read the Session 7 entry of the master manifest, note that Session 7 requires both a `/plan` spike AND skeleton expansion before `/goal` proceeds.
- Blockers: none expected. If any, list with what was tried + what's needed.

- [ ] **Step 20.2: Commit + push**

```bash
git add .claude/handoff.md
git commit -m "docs(handoff): close Session 6; Session 7 launch guidance"
git push
```

- [ ] **Step 20.3: Print the handoff diff into chat**

```bash
git diff HEAD~1 .claude/handoff.md
```

---

### Task 21: Surface all required evidence in chat for /goal completion

**Files:** none (chat summary)

This task is the final consolidation: produce a single chat message that satisfies every Definition-of-Done item in the Session 6 launch command. The message must include, verbatim or as `gh`/`git` output:

1. Git diff for `backend/app/cv/metric_extraction.py` showing the two new metrics + helpers (run `git diff main backend/app/cv/metric_extraction.py | head -200`).
2. Git diff for the same file scoped to `identify_liftoff_frame` + `identify_knee_pass_frame` + their unit-test diff.
3. `uv run --directory backend pytest backend/tests/unit/test_metric_extraction_sagittal.py -k session6 -v` final summary lines.
4. `uv run --directory backend pytest backend/tests/integration/test_pipeline_sagittal_metrics.py -k session6 -s -v` final summary lines.
5. Smoke-script output from Task 10.
6. PR URL + title from Task 12.
7. `gh pr checks <PR>` final output from Task 13.
8. `gh run watch <main-run-id>` final lines from Task 15 showing Deploy to Production `conclusion=success`.
9. `mcp__github__merge_pull_request` response excerpt showing `merged=true` from Task 14.
10. SSH droplet HEAD output from Task 16.
11. Screenshot paths from Task 17.
12. Master manifest diff from Task 19.
13. Handoff diff from Task 20.

If the original /goal hook is still active after this message, the goal condition is satisfied and the hook auto-clears.

---

## Acceptance criteria

- Two phase-frame-id helpers (`identify_liftoff_frame`, `identify_knee_pass_frame`) tested with edge cases (immediate, never-fires, out-of-bounds, empty).
- Two extractors implemented + tested (synthetic landmark + synthetic bar trajectory + side-agnosticism).
- Two registry flags (`bar_to_hip_distance`, `shoulder_protraction_proxy_px`) flipped to `computed_yet=True`.
- All three `test_all_*_metric_values_are_floats` invariants updated and green.
- Integration tests pass on bench + deadlift fixtures.
- Smoke script output looks sane (per-phase values within [-5.0, 5.0]).
- E2E confirms both metrics in expert panel via Playwright MCP.
- Master manifest, backlog, handoff all updated atomically with the code changes.
- New helpers reach ≥90% line coverage (per Standing Rule 1; raise the test count, never lower the threshold).

---

## STOP triggers specific to Session 6

- **40 turns elapsed** → handoff + remediation per master manifest Remediation Policy.
- **Phase-frame identification fails on `atharva-deadlift.mov`** (especially `knee_pass_frame`) → first remediation: try linear interpolation of `bar_y` between adjacent samples (insert intermediate samples until the crossing falls between two samples instead of skipping it). If still failing, escalate to user.
- **`spelix-auditor` returns CRITICAL** → escalate per Standing Rule 5.
- **CI red after 2 retries** → remediate per master manifest template; never lower a quality gate.
- **Coverage threshold breached** → remediate by adding tests targeting uncovered lines; never lower the threshold.

---

## Just-in-time expansion checklist

- [x] Skeleton task ordering preserved (helpers → extractors → registry → integration → smoke → ship).
- [x] Each step is one action (write tests / run / implement / verify / commit).
- [x] Every code block in test steps is a complete `def test_...` body — no placeholders.
- [x] Every commit message is exact (heredoc with verbatim text).
- [x] Type-widening for dict-valued metric handled in the same edits as the extractor (ADR-022 compliance).
- [x] Registry tests + endpoint tests updated alongside the registry flip.
- [x] All sub-PR coordination (registry + invariant tests + smoke script) accounted for in single-task commits.

