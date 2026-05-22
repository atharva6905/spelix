# Session 4 — Trivial Metrics (Auto-Flow Scoring) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship four sagittal-view metrics derived from already-computed pipeline data. Two of them (`depth_classification` for squat, `ecc_con_ratio` for all exercises) auto-flow into existing scoring dimensions; the other two (`pause_duration_s`, `lockout_torso_lean_deg`) are compute-only and surface only via the expert `UnvalidatedMetricsPanel`. First user-visible scoring impact of the cv-audit work.

**Architecture:** Each metric is a small pure function added to `backend/app/cv/metric_extraction.py` consuming existing per-rep inputs (angle timeseries, landmarks, fps). Two new scoring branches in `backend/app/cv/scoring.py` (`TechniqueScore._score_squat` gains `depth_classification` block; `ControlScore.compute` gains `ecc_con_ratio` block) emit `BadgeResult` items and dock the form score. Three new threshold entries in `config/thresholds_v1.json`. The four matching `SAGITTAL_METRICS_REGISTRY` entries get `computed_yet=True`; the two auto-flow ones additionally get `in_scoring=True` — the existing `<UnvalidatedMetricsPanel />` then renders values for them automatically (no panel code changes). Frontend `ResultsPage.tsx` gains a small "Auto-Flow Metrics" chip row derived directly from `analysis.rep_metrics[].metrics.depth_classification` and `.ecc_con_ratio` (no new backend persistence required — the values already ride through the existing JSONB `metrics` column on `rep_metrics`).

**Tech Stack:** Python 3.12, NumPy, pytest, instructor/Pydantic. React 19, vitest, React Testing Library. `/team` cross-stack PR.

**Branch:** `feat/sagittal-trivial-metrics`

---

## File Structure

### Files to modify

| File | Change |
|---|---|
| `backend/app/cv/metric_extraction.py` | (a) Module-level helpers: `_classify_depth(depth_angle, parallel_angle) -> str`, `_pause_duration_s(primary_series, start, end, depth_frame, fps) -> float`, `_lockout_torso_lean_deg(landmarks, end_frame, side_idx) -> float`. (b) `_squat_metrics` writes new keys `depth_classification`, `pause_duration_s`, `lockout_torso_lean_deg`, `ecc_con_ratio`. (c) `_bench_metrics` writes `pause_duration_s`, `ecc_con_ratio`. (d) `_deadlift_metrics` writes `pause_duration_s`, `lockout_torso_lean_deg`, `ecc_con_ratio`. `parallel_angle` for depth classification is sourced from the existing `ThresholdConfig` via a new optional `cfg` parameter on the analyzers; default fallback `90.0` matches existing rep-detection threshold so tests with no cfg stay green. |
| `backend/app/cv/scoring.py` | (a) `TechniqueScore._score_squat` gains a `depth_classification` block dispatched off `metrics.get("depth_classification")` and `cfg.get("squat", "depth_classification_min")`. (b) `ControlScore.compute` gains an `ecc_con_ratio` block dispatched off `metrics.get("ecc_con_ratio")` reading `cfg.get("control", "ecc_con_ratio_target_min")` and `..._target_max`. (c) New `BadgeResult` issue_keys: `squat_depth_classification_above`, `ecc_con_ratio_rushed`, `ecc_con_ratio_excessive`. |
| `backend/app/cv/sagittal_metrics_registry.py` | Flip `computed_yet=True` on the four entries (`depth_classification`, `ecc_con_ratio`, `pause_duration_s`, `lockout_torso_lean_deg`). Additionally flip `in_scoring=True` on `depth_classification` and `ecc_con_ratio`. No new entries; no key renames. |
| `config/thresholds_v1.json` | Add `squat.depth_classification_min` (default `"at_parallel"`, provenance "Schoenfeld 2010 — parallel depth marker") and `control.ecc_con_ratio_target_min` (1.0, provenance "Wilk et al. 1993 tempo prescription"), `control.ecc_con_ratio_target_max` (3.0, same citation). Categorical value stored under the same `{value, unit, provenance_citation, last_modified_by}` envelope; `unit=""` for the categorical. |
| `backend/app/services/pipeline.py` | Aggregator `_aggregate_rep_metrics` needs to forward `depth_classification` (a string, must preserve majority label) and `ecc_con_ratio` (float, take mean) into the aggregate dict passed to `OverallFormScore.compute`. Pattern matches existing `phase_of_max_deviation` aggregation. |
| `backend/app/cv/types.py` | No change — `BadgeResult` already handles arbitrary message strings. |
| `frontend/src/pages/ResultsPage.tsx` | Add a small `<AutoFlowMetricsChips />` sub-component rendered above the rep-metrics table when `analysis.rep_metrics` contains `depth_classification` or `ecc_con_ratio` keys. Two chips: depth (label "Depth: {classification}") and ecc/con (label "Ecc/Con: {value}"). Both display the session-aggregate value (modal for categorical, mean for numeric). |
| `frontend/src/components/UnvalidatedMetricsPanel.tsx` | No code changes — already registry-driven via `computed_yet` flag. |

### Files to create

| File | Purpose |
|---|---|
| `backend/tests/unit/test_metric_extraction_sagittal.py` | Synthetic-landmark unit tests for the four new extractors + side-agnosticism mirror tests per design §Section-5. |
| `backend/tests/integration/test_pipeline_session4_metrics.py` | Fixture-video integration test against `tests/fixtures/atharva_squat.mp4` (or equivalent in-tree fixture; see Task 12 for fallback). |
| `frontend/src/pages/__tests__/ResultsPage.autoFlowMetrics.test.tsx` | Vitest cases for `<AutoFlowMetricsChips />` happy path + missing-keys path + categorical-modal aggregation. |

### Files NOT touched

- `backend/app/cv/barbell_detection.py` — Session 6 scope.
- Existing `_squat_metrics` / `_bench_metrics` / `_deadlift_metrics` Phase-1 outputs — keys are additive only; no renames or removals.
- Any Alembic migration — no schema change; new keys ride through existing JSONB.
- `OverallFormScore` Protocol / `ScoreComponent` interface — no changes.
- Coaching service / coaching prompt — `BadgeResult` items continue to be produced but the existing badge→prompt path is unchanged (the LangGraph agent receives them via `score_result` reference; no template change needed, per design §Section-2 line 147).

### Test conventions referenced

- Pure-function tests in `backend/tests/unit/` use synthetic numpy arrays — no real video, no IO.
- Scoring tests set `THRESHOLD_CONFIG_PATH` env var before any `app.*` import (pattern in existing `test_scoring.py:21`).
- Frontend tests mock `@/lib/supabase` and the analyses API layer; no network.

---

## Tasks

### Task 1: Create branch + verify clean state

**Files:**
- N/A (git)

- [ ] **Step 1: Confirm on main and synced**

```bash
git status --short
git branch --show-current
git pull origin main
```
Expected: clean status, branch `main`, "Already up to date" or fast-forward.

- [ ] **Step 2: Create branch**

```bash
git checkout -b feat/sagittal-trivial-metrics
```
Expected: "Switched to a new branch 'feat/sagittal-trivial-metrics'".

- [ ] **Step 3: Confirm baseline tests pass**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction.py tests/unit/test_scoring.py tests/unit/test_sagittal_metrics_registry.py -x --tb=short 2>&1 | tail -20
```
Expected: every test passes; final line `==== N passed in Xs ====`. This is the regression baseline.

---

### Task 2: Threshold config — add three new entries

**Files:**
- Modify: `config/thresholds_v1.json` (squat section adds 1 key; control section adds 2 keys)
- Test: `backend/tests/unit/test_threshold_config.py` (existing file; new test only if file exists, otherwise add to `test_scoring.py`)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/test_scoring.py` (file already exports `cfg` fixture):

```python
def test_threshold_config_has_session4_entries(cfg: ThresholdConfig) -> None:
    """Session 4: thresholds_v1.json must expose depth_classification + ecc_con_ratio knobs."""
    # Categorical default for squat depth gate.
    assert cfg.get("squat", "depth_classification_min") == "at_parallel"
    # Ecc/con ratio scoring window (Wilk et al. 1993 tempo prescription).
    assert cfg.get("control", "ecc_con_ratio_target_min") == pytest.approx(1.0)
    assert cfg.get("control", "ecc_con_ratio_target_max") == pytest.approx(3.0)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/unit/test_scoring.py::test_threshold_config_has_session4_entries -xvs 2>&1 | tail -10
```
Expected: `KeyError` on `cfg.get("squat", "depth_classification_min")`.

- [ ] **Step 3: Add the three entries**

Edit `config/thresholds_v1.json`. Under the `"squat"` object (after `rep_detection_prominence_deg`), add:

```json
    "depth_classification_min": {
      "value": "at_parallel",
      "unit": "",
      "provenance_citation": "Schoenfeld 2010 — parallel depth marker (depth_classification gate; allowed values: above_parallel, at_parallel, below_parallel)",
      "last_modified_by": "cv_engineer"
    }
```

Under the `"control"` object (after `rep_duration_std_caution_s`), add:

```json
    "ecc_con_ratio_target_min": {
      "value": 1.0,
      "unit": "ratio",
      "provenance_citation": "Wilk et al. 1993 tempo prescription — minimum eccentric/concentric ratio for hypertrophy and motor control",
      "last_modified_by": "cv_engineer"
    },
    "ecc_con_ratio_target_max": {
      "value": 3.0,
      "unit": "ratio",
      "provenance_citation": "Wilk et al. 1993 tempo prescription — maximum eccentric/concentric ratio before tempo becomes excessive",
      "last_modified_by": "cv_engineer"
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/unit/test_scoring.py::test_threshold_config_has_session4_entries -xvs 2>&1 | tail -10
```
Expected: `PASS`.

- [ ] **Step 5: Run full scoring suite (regression)**

```bash
cd backend && uv run pytest tests/unit/test_scoring.py -x --tb=short 2>&1 | tail -10
```
Expected: every test passes (the new key doesn't disturb existing scorers).

- [ ] **Step 6: Commit**

```bash
git add config/thresholds_v1.json backend/tests/unit/test_scoring.py
git commit -m "feat(config): add Session 4 threshold entries (depth_classification, ecc_con_ratio)

Adds squat.depth_classification_min (categorical, default 'at_parallel') and
control.ecc_con_ratio_target_min/_max (1.0..3.0) per design §Session-4.
Provenance citations included.

Refs L2-SAGITTAL-TRIVIAL-01"
```

---

### Task 3: Extractor `_classify_depth` (depth_classification)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py` (add helper near `_torso_lean_deg`)
- Test: `backend/tests/unit/test_metric_extraction_sagittal.py` (create)

- [ ] **Step 1: Create the new test file with the first failing case**

Create `backend/tests/unit/test_metric_extraction_sagittal.py`:

```python
"""Session 4 — synthetic-landmark unit tests for the four trivial extractors.

Per design §Session-4 + §Section-5:
- Each extractor has a happy path, a boundary/edge case, and a side-agnosticism
  mirror test asserting equal output across left/right input.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.cv.lifter_side import landmark_indices_for_side
from app.cv.metric_extraction import (
    _classify_depth,
    _lockout_torso_lean_deg,
    _pause_duration_s,
)


# ---------------------------------------------------------------------------
# #7 depth_classification (categorical relabel of existing depth_angle)
# ---------------------------------------------------------------------------


def test_session4_depth_classification_above_parallel() -> None:
    """depth_angle > parallel + 5° → 'above_parallel'."""
    assert _classify_depth(depth_angle=100.0, parallel_angle=90.0) == "above_parallel"


def test_session4_depth_classification_at_parallel_upper_band() -> None:
    """depth_angle within ±5° of parallel → 'at_parallel'."""
    assert _classify_depth(depth_angle=95.0, parallel_angle=90.0) == "at_parallel"


def test_session4_depth_classification_at_parallel_lower_band() -> None:
    assert _classify_depth(depth_angle=85.0, parallel_angle=90.0) == "at_parallel"


def test_session4_depth_classification_below_parallel() -> None:
    """depth_angle < parallel - 5° → 'below_parallel'."""
    assert _classify_depth(depth_angle=80.0, parallel_angle=90.0) == "below_parallel"


def test_session4_depth_classification_boundary_exact_parallel() -> None:
    """At exactly parallel - 5° = 85°, classification is 'at_parallel' (inclusive lower band)."""
    assert _classify_depth(depth_angle=85.0, parallel_angle=90.0) == "at_parallel"
```

- [ ] **Step 2: Run the new tests to verify failure**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -xvs 2>&1 | tail -10
```
Expected: ImportError — `_classify_depth` not defined in `app.cv.metric_extraction`.

- [ ] **Step 3: Implement `_classify_depth`**

In `backend/app/cv/metric_extraction.py`, add this helper after `_torso_lean_deg` and before `_find_depth_frame`:

```python
def _classify_depth(depth_angle: float, parallel_angle: float) -> str:
    """Categorical relabel of squat depth (Session 4, design §Section-4 #7).

    Returns one of ``above_parallel``, ``at_parallel``, ``below_parallel``
    based on a ±5° band around ``parallel_angle``. ``depth_angle`` is the
    minimum hip angle for the rep (lower = deeper).

    Boundaries are inclusive on the lower band so a value exactly equal to
    ``parallel_angle - 5.0`` is classified ``at_parallel``.
    """
    upper = parallel_angle + 5.0
    lower = parallel_angle - 5.0
    if depth_angle > upper:
        return "above_parallel"
    if depth_angle < lower:
        return "below_parallel"
    return "at_parallel"
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -xvs 2>&1 | tail -10
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): add _classify_depth helper for depth_classification metric (Session 4)

Categorical relabel of squat depth_angle: above_parallel | at_parallel |
below_parallel within ±5° of the parallel hip angle (design §Session-4 #7).
Pure function, no IO, fully TDD-covered.

Refs L2-SAGITTAL-TRIVIAL-01"
```

---

### Task 4: Extractor `_pause_duration_s`

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Test: `backend/tests/unit/test_metric_extraction_sagittal.py` (append)

- [ ] **Step 1: Add failing tests**

Append to `backend/tests/unit/test_metric_extraction_sagittal.py`:

```python
# ---------------------------------------------------------------------------
# #9 pause_duration_s (frames within ±2° of rep bottom, divided by fps)
# ---------------------------------------------------------------------------


def test_session4_pause_duration_synthetic_pause() -> None:
    """A rep with an explicit pause of 15 frames at the depth angle, fps=30 → 0.5s."""
    n = 60
    angles = np.full(n, 170.0)
    # descent 0..20, pause 20..35 at depth 80°, ascent 35..60
    angles[10:20] = np.linspace(170.0, 80.0, 10)  # descent
    angles[20:35] = 80.0                          # plateau 15 frames
    angles[35:60] = np.linspace(80.0, 170.0, 25)  # ascent
    pause = _pause_duration_s(
        primary_series=angles, start=0, end=59, depth_frame=27, fps=30.0
    )
    assert pause == pytest.approx(15.0 / 30.0, abs=1e-2)


def test_session4_pause_duration_touch_and_go() -> None:
    """Touch-and-go rep: single bottom frame → ~1 frame / fps."""
    n = 60
    angles = np.full(n, 170.0)
    angles[10:30] = np.linspace(170.0, 80.0, 20)
    angles[30:60] = np.linspace(80.0, 170.0, 30)
    pause = _pause_duration_s(
        primary_series=angles, start=0, end=59, depth_frame=29, fps=30.0
    )
    # No plateau — only the depth frame itself (~1/30s); allow a small
    # tolerance for the ±2° window catching adjacent ramping samples.
    assert pause <= 0.20


def test_session4_pause_duration_degenerate_zero_length_rep() -> None:
    """Degenerate input (start == end) returns 0.0, no exception."""
    angles = np.full(10, 90.0)
    pause = _pause_duration_s(
        primary_series=angles, start=5, end=5, depth_frame=5, fps=30.0
    )
    assert pause == 0.0
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -xvs -k pause 2>&1 | tail -10
```
Expected: ImportError on `_pause_duration_s`.

- [ ] **Step 3: Implement `_pause_duration_s`**

Add to `backend/app/cv/metric_extraction.py` after `_find_descent_end_ascent_start`:

```python
def _pause_duration_s(
    primary_series: np.ndarray,
    start: int,
    end: int,
    depth_frame: int,
    fps: float,
    band_deg: float = 2.0,
) -> float:
    """Time spent within ``band_deg`` of the rep-bottom angle (Session 4 #9).

    Counts consecutive frames in ``primary_series[start:end+1]`` whose value
    is within ``band_deg`` of ``primary_series[depth_frame]`` and divides
    by ``fps``. Hysteresis is implicit — the band is symmetric around the
    measured bottom.

    Returns ``0.0`` on degenerate input (``end <= start`` or ``fps <= 0``).
    """
    if end <= start or fps <= 0.0:
        return 0.0
    if depth_frame < start or depth_frame > end:
        return 0.0
    if depth_frame >= primary_series.shape[0]:
        return 0.0

    bottom_angle = float(primary_series[depth_frame])
    segment = primary_series[start : end + 1]
    in_band = np.abs(segment - bottom_angle) <= band_deg
    n_frames = int(np.sum(in_band))
    return float(n_frames) / float(fps)
```

- [ ] **Step 4: Run pause tests to confirm pass**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -xvs -k pause 2>&1 | tail -10
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): add _pause_duration_s extractor (Session 4 #9)

Counts frames within ±2° of rep-bottom angle and divides by fps. Pure,
side-agnostic (operates on a 1-D angle signal). Handles degenerate
zero-length reps and out-of-bounds depth_frame.

Refs L2-SAGITTAL-TRIVIAL-03"
```

---

### Task 5: Extractor `_lockout_torso_lean_deg`

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Test: `backend/tests/unit/test_metric_extraction_sagittal.py` (append)

- [ ] **Step 1: Add failing tests**

Append to `backend/tests/unit/test_metric_extraction_sagittal.py`:

```python
# ---------------------------------------------------------------------------
# #12 lockout_torso_lean_deg (torso-vertical angle at rep peak-angle frame)
# ---------------------------------------------------------------------------


def _make_landmark_frame_right_side(
    shoulder_xy: tuple[float, float], hip_xy: tuple[float, float]
) -> np.ndarray:
    """Build a (33, 5) frame with right-side shoulder/hip set and visibility=0.9."""
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9   # visibility
    lm[:, 4] = 5.0   # presence pre-sigmoid → ~1.0 (avoids the col 4 gotcha)
    lm[12, :2] = shoulder_xy  # right shoulder
    lm[24, :2] = hip_xy       # right hip
    return lm


def _make_landmark_frame_left_side(
    shoulder_xy: tuple[float, float], hip_xy: tuple[float, float]
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    lm[11, :2] = shoulder_xy
    lm[23, :2] = hip_xy
    return lm


def test_session4_lockout_torso_lean_upright() -> None:
    """Shoulder directly above hip → 0° lean."""
    right_idx = landmark_indices_for_side("right")
    frame = _make_landmark_frame_right_side(
        shoulder_xy=(0.5, 0.1), hip_xy=(0.5, 0.5)
    )
    lean = _lockout_torso_lean_deg(
        landmarks_per_frame=[frame], end_frame=0, side_idx=right_idx
    )
    assert lean == pytest.approx(0.0, abs=0.5)


def test_session4_lockout_torso_lean_forward_15deg() -> None:
    """Shoulder forward of hip by tan(15°)*Δy → ~15° lean."""
    import math
    right_idx = landmark_indices_for_side("right")
    dy = 0.4
    dx = dy * math.tan(math.radians(15.0))
    frame = _make_landmark_frame_right_side(
        shoulder_xy=(0.5 + dx, 0.1), hip_xy=(0.5, 0.5)
    )
    lean = _lockout_torso_lean_deg(
        landmarks_per_frame=[frame], end_frame=0, side_idx=right_idx
    )
    assert lean == pytest.approx(15.0, abs=0.5)


def test_session4_lockout_torso_lean_backward_5deg() -> None:
    """Shoulder behind hip by tan(5°)*Δy → ~5° lean magnitude (unsigned)."""
    import math
    right_idx = landmark_indices_for_side("right")
    dy = 0.4
    dx = dy * math.tan(math.radians(5.0))
    frame = _make_landmark_frame_right_side(
        shoulder_xy=(0.5 - dx, 0.1), hip_xy=(0.5, 0.5)
    )
    lean = _lockout_torso_lean_deg(
        landmarks_per_frame=[frame], end_frame=0, side_idx=right_idx
    )
    assert lean == pytest.approx(5.0, abs=0.5)
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -xvs -k lockout_torso 2>&1 | tail -10
```
Expected: ImportError on `_lockout_torso_lean_deg`.

- [ ] **Step 3: Implement `_lockout_torso_lean_deg`**

Add to `backend/app/cv/metric_extraction.py` after `_pause_duration_s` (the existing `_torso_lean_deg` already gives the formula — this is a thin wrapper that picks the lockout frame):

```python
def _lockout_torso_lean_deg(
    landmarks_per_frame: list[np.ndarray],
    end_frame: int,
    side_idx: SideIndices,
) -> float:
    """Torso-vertical angle at rep peak-angle (lockout) frame (Session 4 #12).

    Wraps ``_torso_lean_deg`` at the rep's last frame. Returns ``0.0`` on
    out-of-bounds ``end_frame`` (degenerate-input safety).
    """
    if end_frame < 0 or end_frame >= len(landmarks_per_frame):
        return 0.0
    return _torso_lean_deg(landmarks_per_frame[end_frame], side_idx)
```

- [ ] **Step 4: Run lockout tests to confirm pass**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -xvs -k lockout_torso 2>&1 | tail -10
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): add _lockout_torso_lean_deg extractor (Session 4 #12)

Thin wrapper over _torso_lean_deg that picks the rep's peak-angle (lockout)
frame. Squat + deadlift applicability. Side-agnostic via SideIndices.

Refs L2-SAGITTAL-TRIVIAL-04"
```

---

### Task 6: Side-agnosticism mirror tests (all 3 extractors that consume landmarks)

**Files:**
- Test: `backend/tests/unit/test_metric_extraction_sagittal.py` (append)

`_classify_depth` and `_pause_duration_s` operate on 1-D angle signals (already side-agnostic by construction). `_lockout_torso_lean_deg` consumes landmarks and is the one to mirror-test. Two of the three Session 4 metrics that *will* be wired in Task 7 also consume landmarks indirectly via the analyzers — covered in Task 8.

- [ ] **Step 1: Add the mirror test**

Append to `backend/tests/unit/test_metric_extraction_sagittal.py`:

```python
# ---------------------------------------------------------------------------
# Side-agnosticism: mirror tests per design §Section-5 line 410
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lean_deg",
    [0.0, 5.0, 10.0, 15.0, 20.0],
)
def test_session4_lockout_torso_lean_side_agnostic(lean_deg: float) -> None:
    """The same pose populated on either side (with x flipped on the left
    side, per the design's mirror convention) must yield identical lean."""
    import math
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    dy = 0.4
    dx = dy * math.tan(math.radians(lean_deg))

    right_frame = _make_landmark_frame_right_side(
        shoulder_xy=(0.5 + dx, 0.1), hip_xy=(0.5, 0.5)
    )
    # Mirror convention: x' = 1.0 - x (normalised), pose remains the same.
    left_frame = _make_landmark_frame_left_side(
        shoulder_xy=(1.0 - (0.5 + dx), 0.1),
        hip_xy=(1.0 - 0.5, 0.5),
    )

    right_lean = _lockout_torso_lean_deg(
        landmarks_per_frame=[right_frame], end_frame=0, side_idx=right_idx
    )
    left_lean = _lockout_torso_lean_deg(
        landmarks_per_frame=[left_frame], end_frame=0, side_idx=left_idx
    )
    assert right_lean == pytest.approx(left_lean, abs=0.5)


def test_session4_classify_depth_is_signal_only_so_side_agnostic_by_construction() -> None:
    """Sanity check — _classify_depth operates only on the depth_angle scalar,
    which is itself computed via side-aware indices upstream."""
    # Same input → same output, irrespective of any landmark layout.
    assert _classify_depth(85.0, 90.0) == "at_parallel"


def test_session4_pause_duration_is_signal_only_so_side_agnostic_by_construction() -> None:
    """Sanity check — _pause_duration_s consumes only a 1-D angle signal."""
    angles = np.full(60, 90.0)
    pause = _pause_duration_s(angles, start=0, end=59, depth_frame=30, fps=30.0)
    assert pause == pytest.approx(60.0 / 30.0, abs=1e-2)
```

- [ ] **Step 2: Run mirror tests**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -xvs -k "side_agnostic or signal_only" 2>&1 | tail -15
```
Expected: 7 passed (5 parametrised + 2 sanity).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "test(cv): add side-agnosticism mirror tests for Session 4 extractors

Per design §Section-5 line 410, every landmark-consuming extractor is
verified to return equal output when the same pose is populated on either
side with x mirrored (x' = 1 - x). _classify_depth and _pause_duration_s
operate on 1-D signals and are side-agnostic by construction — confirmed
with sanity tests.

Refs L2-SAGITTAL-TRIVIAL-01..04"
```

---

### Task 7: Wire the four new keys into `_squat_metrics`, `_bench_metrics`, `_deadlift_metrics`

**Files:**
- Modify: `backend/app/cv/metric_extraction.py` (the three analyzer functions + signature for cfg)
- Test: `backend/tests/unit/test_metric_extraction_sagittal.py` (append integration-level cases)

The analyzers need a way to read `parallel_angle` for depth classification. To avoid widening the public `extract_rep_metrics` signature, we thread an optional `ThresholdConfig` via a module-level default loader.

- [ ] **Step 1: Add failing test for end-to-end key presence**

Append to `backend/tests/unit/test_metric_extraction_sagittal.py`:

```python
# ---------------------------------------------------------------------------
# Analyzer integration — all four keys present in extract_rep_metrics output
# ---------------------------------------------------------------------------


from app.cv.metric_extraction import extract_rep_metrics  # noqa: E402
from app.cv.rep_detection import DetectedRep  # noqa: E402


def _make_squat_session(n_frames: int = 60) -> tuple[list, dict[str, np.ndarray], DetectedRep]:
    """Reuses the helper shape from test_metric_extraction.py."""
    frames = []
    for _ in range(n_frames):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[12, :2] = [0.5, 0.1]   # shoulder
        lm[24, :2] = [0.5, 0.5]   # hip
        lm[26, :2] = [0.5, 0.75]  # knee
        lm[28, :2] = [0.5, 0.95]  # ankle
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, n_frames)
    hip = 125.0 + 45.0 * np.cos(t)
    knee = 110.0 + 40.0 * np.cos(t)
    ts = {"hip_angle": hip, "knee_angle": knee}
    rep = DetectedRep(rep_index=0, start_frame=0, end_frame=n_frames - 1)
    return frames, ts, rep


def test_session4_squat_analyzer_emits_all_four_new_keys() -> None:
    frames, ts, rep = _make_squat_session(60)
    out = extract_rep_metrics(
        reps=[rep],
        landmarks_per_frame=frames,
        angle_timeseries=ts,
        exercise_type="squat",
        exercise_variant="standard",
        fps=30.0,
        lifter_side="right",
    )
    metrics = out[0].metrics
    assert "depth_classification" in metrics
    assert metrics["depth_classification"] in {"above_parallel", "at_parallel", "below_parallel"}
    assert "ecc_con_ratio" in metrics
    assert isinstance(metrics["ecc_con_ratio"], float)
    assert "pause_duration_s" in metrics
    assert isinstance(metrics["pause_duration_s"], float)
    assert "lockout_torso_lean_deg" in metrics
    assert isinstance(metrics["lockout_torso_lean_deg"], float)


def test_session4_bench_analyzer_emits_applicable_keys() -> None:
    """Bench: ecc_con_ratio + pause_duration_s. NOT depth_classification (squat only)
    NOT lockout_torso_lean_deg (squat + DL only — bench torso is supine)."""
    frames = []
    for _ in range(60):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[12, :2] = [0.5, 0.1]
        lm[14, :2] = [0.3, 0.35]
        lm[16, :2] = [0.2, 0.35]
        lm[24, :2] = [0.5, 0.5]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, 60)
    ts = {"elbow_angle": 115.0 + 50.0 * np.cos(t), "shoulder_angle": 70.0 + 20.0 * np.cos(t)}
    rep = DetectedRep(rep_index=0, start_frame=0, end_frame=59)
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="bench", exercise_variant="flat", fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "ecc_con_ratio" in metrics
    assert "pause_duration_s" in metrics
    assert "depth_classification" not in metrics
    assert "lockout_torso_lean_deg" not in metrics


def test_session4_deadlift_analyzer_emits_applicable_keys() -> None:
    """Deadlift: ecc_con_ratio + pause_duration_s + lockout_torso_lean_deg. NOT depth_classification."""
    frames = []
    for _ in range(60):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[12, :2] = [0.5, 0.1]
        lm[24, :2] = [0.5, 0.5]
        lm[26, :2] = [0.5, 0.75]
        lm[28, :2] = [0.5, 0.95]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, 60)
    ts = {"hip_angle": 100.0 + 60.0 * np.cos(t), "knee_angle": 120.0 + 40.0 * np.cos(t)}
    rep = DetectedRep(rep_index=0, start_frame=0, end_frame=59)
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="deadlift", exercise_variant="conventional",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "ecc_con_ratio" in metrics
    assert "pause_duration_s" in metrics
    assert "lockout_torso_lean_deg" in metrics
    assert "depth_classification" not in metrics


def test_session4_ecc_con_ratio_value_correct() -> None:
    """Synthetic balanced rep (descent == ascent) → ratio == 1.0."""
    frames, ts, rep = _make_squat_session(60)
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="squat", exercise_variant="standard", fps=30.0,
        lifter_side="right",
    )
    # Cosine signal: bottom is at frame 30 (midpoint of 0..59 inclusive).
    # descent ≈ 30 frames, ascent ≈ 29 frames → ratio ≈ 1.03.
    ratio = out[0].metrics["ecc_con_ratio"]
    assert isinstance(ratio, float)
    assert ratio == pytest.approx(30.0 / 29.0, abs=0.05)
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -xvs -k "analyzer_emits or value_correct" 2>&1 | tail -20
```
Expected: KeyError on `metrics["depth_classification"]` (or similar) — the analyzers don't write the new keys yet.

- [ ] **Step 3: Implement — extend the three analyzers**

In `backend/app/cv/metric_extraction.py`:

(a) After the existing helpers, add the parallel-angle lookup helper (module-level, lazy-loaded so test-time config injection works):

```python
def _default_parallel_angle() -> float:
    """Load ``squat.depth_parallel_hip_angle_deg`` from ThresholdConfig.

    Lazy import + lazy load so that tests with no ThresholdConfig available
    still work (returns 90.0 fallback).
    """
    try:
        from app.config import ThresholdConfig
        return float(ThresholdConfig().get("squat", "depth_parallel_hip_angle_deg"))
    except Exception:
        return 90.0
```

(b) In `_squat_metrics`, after computing `ascent_duration_s` and before the `return` block (around line 263), insert:

```python
    # Session 4: depth_classification (auto-flow → Technique)
    parallel_angle = _default_parallel_angle()
    depth_classification = _classify_depth(depth_angle, parallel_angle)

    # Session 4: ecc_con_ratio (auto-flow → Control)
    if ascent_duration_s > 0.0:
        ecc_con_ratio = float(descent_duration_s / ascent_duration_s)
    else:
        ecc_con_ratio = 0.0

    # Session 4: pause_duration_s (compute-only)
    pause_duration_s = _pause_duration_s(
        hip_series, start, end, depth_frame, fps,
    )

    # Session 4: lockout_torso_lean_deg (compute-only)
    lockout_torso_lean = _lockout_torso_lean_deg(
        landmarks_per_frame, end, side_idx,
    )
```

Then in the return dict, add the four new keys after `phase_of_max_deviation`:

```python
        "depth_classification": depth_classification,
        "ecc_con_ratio": ecc_con_ratio,
        "pause_duration_s": pause_duration_s,
        "lockout_torso_lean_deg": lockout_torso_lean,
```

(c) In `_bench_metrics`, after `ascent_duration_s`, insert:

```python
    if ascent_duration_s > 0.0:
        ecc_con_ratio = float(descent_duration_s / ascent_duration_s)
    else:
        ecc_con_ratio = 0.0
    pause_duration_s = _pause_duration_s(
        elbow_series, start, end, bottom_frame, fps,
    )
```

And in the return dict (after `phase_of_max_deviation`):

```python
        "ecc_con_ratio": ecc_con_ratio,
        "pause_duration_s": pause_duration_s,
```

(d) In `_deadlift_metrics`, after `ascent_duration_s`, insert:

```python
    if ascent_duration_s > 0.0:
        ecc_con_ratio = float(descent_duration_s / ascent_duration_s)
    else:
        ecc_con_ratio = 0.0
    pause_duration_s = _pause_duration_s(
        hip_series, start, end, bottom_frame, fps,
    )
    lockout_torso_lean = _lockout_torso_lean_deg(
        landmarks_per_frame, end, side_idx,
    )
```

And in the return dict:

```python
        "ecc_con_ratio": ecc_con_ratio,
        "pause_duration_s": pause_duration_s,
        "lockout_torso_lean_deg": lockout_torso_lean,
```

- [ ] **Step 4: Run analyzer tests**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -xvs -k "analyzer_emits or value_correct" 2>&1 | tail -20
```
Expected: 4 passed.

- [ ] **Step 5: Run the full Session 4 test file**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -x --tb=short 2>&1 | tail -10
```
Expected: every `test_session4_*` passes.

- [ ] **Step 6: Run the regression suite for Phase-1 metric extraction**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction.py -x --tb=short 2>&1 | tail -10
```
Expected: all Phase-1 tests still green (keys are additive).

- [ ] **Step 7: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): wire Session 4 keys into _squat / _bench / _deadlift analyzers

Squat: depth_classification + ecc_con_ratio + pause_duration_s + lockout_torso_lean_deg
Bench: ecc_con_ratio + pause_duration_s
Deadlift: ecc_con_ratio + pause_duration_s + lockout_torso_lean_deg

Parallel-angle for depth classification is loaded lazily from
ThresholdConfig (squat.depth_parallel_hip_angle_deg), with a 90.0
fallback so unit tests with no config injection stay green.

Refs L2-SAGITTAL-TRIVIAL-01..04"
```

---

### Task 8: TechniqueScore.depth_classification scoring branch

**Files:**
- Modify: `backend/app/cv/scoring.py::TechniqueScore._score_squat`
- Test: `backend/tests/unit/test_scoring.py` (append)

- [ ] **Step 1: Add failing tests for the scoring branch**

Append to `backend/tests/unit/test_scoring.py` (after existing TechniqueScore tests):

```python
# ---------------------------------------------------------------------------
# Session 4 — TechniqueScore.depth_classification branch
# ---------------------------------------------------------------------------


def test_session4_technique_depth_classification_at_parallel_no_dock(cfg: ThresholdConfig) -> None:
    """depth_classification == 'at_parallel' and threshold 'at_parallel' → no dock."""
    metrics = {
        "depth_angle": 90.0,
        "depth_classification": "at_parallel",
    }
    score, badges = TechniqueScore().compute(metrics, None, cfg, "squat")
    # The legacy depth_angle == parallel branch also fires no-dock — assert
    # no NEW depth_classification badge appears.
    issue_keys = [b.issue_key for b in badges]
    assert "squat_depth_classification_above" not in issue_keys


def test_session4_technique_depth_classification_above_parallel_with_at_parallel_threshold_docks_1_5(
    cfg: ThresholdConfig,
) -> None:
    """above_parallel + threshold 'at_parallel' → -1.5 dock, severity Medium."""
    metrics = {
        # No legacy depth_angle present to isolate the new branch.
        "depth_classification": "above_parallel",
    }
    score, badges = TechniqueScore().compute(metrics, None, cfg, "squat")
    assert score == pytest.approx(10.0 - 1.5, abs=0.01)
    new_badges = [b for b in badges if b.issue_key == "squat_depth_classification_above"]
    assert len(new_badges) == 1
    assert new_badges[0].severity == "Medium"
    assert new_badges[0].dimension == "Technique"
    # Badge text references the user-facing classification and the target.
    assert "above parallel" in new_badges[0].message.lower()


def test_session4_technique_depth_classification_above_parallel_with_below_parallel_threshold_docks_2_5(
    cfg: ThresholdConfig, tmp_path,
) -> None:
    """Stricter threshold (below_parallel) → -2.5 dock instead of -1.5."""
    # Write a tweaked config that flips depth_classification_min to 'below_parallel'.
    import json
    base = json.loads((_V1_PATH).read_text(encoding="utf-8"))
    base["squat"]["depth_classification_min"]["value"] = "below_parallel"
    tweaked = tmp_path / "thresholds_strict.json"
    tweaked.write_text(json.dumps(base), encoding="utf-8")
    strict_cfg = ThresholdConfig(tweaked)

    metrics = {"depth_classification": "above_parallel"}
    score, badges = TechniqueScore().compute(metrics, None, strict_cfg, "squat")
    assert score == pytest.approx(10.0 - 2.5, abs=0.01)
    new_badges = [b for b in badges if b.issue_key == "squat_depth_classification_above"]
    assert len(new_badges) == 1
    assert new_badges[0].severity == "Medium"


def test_session4_technique_depth_classification_below_parallel_no_dock(cfg: ThresholdConfig) -> None:
    """Going below parallel with at_parallel threshold → no dock from the new branch."""
    metrics = {"depth_classification": "below_parallel"}
    score, badges = TechniqueScore().compute(metrics, None, cfg, "squat")
    new_badges = [b for b in badges if b.issue_key == "squat_depth_classification_above"]
    assert new_badges == []
    assert score == 10.0


def test_session4_technique_depth_classification_ignored_for_bench(cfg: ThresholdConfig) -> None:
    """Bench exercise must NOT read depth_classification — squat-only metric."""
    metrics = {"depth_classification": "above_parallel"}
    score, badges = TechniqueScore().compute(metrics, None, cfg, "bench")
    new_badges = [b for b in badges if b.issue_key == "squat_depth_classification_above"]
    assert new_badges == []
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/unit/test_scoring.py -xvs -k "session4_technique" 2>&1 | tail -15
```
Expected: assertion failures (score == 10.0 in all cases — no dock applied yet).

- [ ] **Step 3: Implement the branch**

In `backend/app/cv/scoring.py::TechniqueScore._score_squat`, after the existing `depth_angle` block (around line 353, just before the `torso_lean` block), insert:

```python
        # Session 4: depth_classification auto-flow (FR-SCOR-02 refinement)
        depth_classification = metrics.get("depth_classification")
        if depth_classification == "above_parallel":
            threshold = cfg.get("squat", "depth_classification_min")
            # Stricter threshold (below_parallel) costs more than at_parallel
            dock = 2.5 if threshold == "below_parallel" else 1.5
            score -= dock
            badges.append(
                BadgeResult(
                    dimension="Technique",
                    issue_key="squat_depth_classification_above",
                    severity="Medium",
                    message=(
                        f"Squat reached above parallel — aim for "
                        f"{threshold.replace('_', ' ')}."
                    ),
                )
            )
```

Note: `BadgeResult` must already be importable inside the function scope; it is — see imports at the top of `scoring.py`. No new import needed.

- [ ] **Step 4: Run to verify pass**

```bash
cd backend && uv run pytest tests/unit/test_scoring.py -xvs -k "session4_technique" 2>&1 | tail -15
```
Expected: 5 passed.

- [ ] **Step 5: Full scoring regression**

```bash
cd backend && uv run pytest tests/unit/test_scoring.py -x --tb=short 2>&1 | tail -10
```
Expected: every test passes — no regression on existing branches.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/scoring.py backend/tests/unit/test_scoring.py
git commit -m "feat(cv): TechniqueScore.depth_classification auto-flow branch (Session 4 #7)

When metrics['depth_classification'] == 'above_parallel', dock 1.5 for
the default 'at_parallel' threshold or 2.5 if the threshold is set to
'below_parallel'. Badge severity Medium. Squat-only. Co-exists with the
existing depth_angle branch (which docks via continuous penalty) — the
new branch's dock is additive.

Refs L2-SAGITTAL-TRIVIAL-01"
```

---

### Task 9: ControlScore.ecc_con_ratio scoring branch

**Files:**
- Modify: `backend/app/cv/scoring.py::ControlScore.compute`
- Test: `backend/tests/unit/test_scoring.py` (append)

The design specifies per-rep dock semantics (1.0/0.5 per rep with rushed/excessive ratio). Since `compute` receives session-aggregate metrics, we interpret the aggregate value:
- If the aggregate `ecc_con_ratio < target_min` → "rushed", dock 1.0, severity High.
- If the aggregate `ecc_con_ratio > target_max` → "excessive", dock 0.5, severity Medium.
- If within `[target_min, target_max]` → no dock.

(Per-rep granular docking is deferred to a post-onboarding refinement once expert thresholds are validated.)

- [ ] **Step 1: Add failing tests**

Append to `backend/tests/unit/test_scoring.py`:

```python
# ---------------------------------------------------------------------------
# Session 4 — ControlScore.ecc_con_ratio branch
# ---------------------------------------------------------------------------


def test_session4_control_ecc_con_balanced_no_dock(cfg: ThresholdConfig) -> None:
    """Aggregate ratio inside [1.0, 3.0] → no dock from ecc_con_ratio branch."""
    metrics = {"ecc_con_ratio": 1.8}
    score, badges = ControlScore().compute(metrics, None, cfg, "squat")
    keys = [b.issue_key for b in badges]
    assert "ecc_con_ratio_rushed" not in keys
    assert "ecc_con_ratio_excessive" not in keys
    assert score == 10.0


def test_session4_control_ecc_con_rushed_docks_1_0_high(cfg: ThresholdConfig) -> None:
    """ratio < target_min → dock 1.0, severity High."""
    metrics = {"ecc_con_ratio": 0.5}
    score, badges = ControlScore().compute(metrics, None, cfg, "squat")
    assert score == pytest.approx(10.0 - 1.0, abs=0.01)
    rushed = [b for b in badges if b.issue_key == "ecc_con_ratio_rushed"]
    assert len(rushed) == 1
    assert rushed[0].severity == "High"
    assert rushed[0].dimension == "Control"
    assert "eccentric" in rushed[0].message.lower()


def test_session4_control_ecc_con_excessive_docks_0_5_medium(cfg: ThresholdConfig) -> None:
    """ratio > target_max → dock 0.5, severity Medium."""
    metrics = {"ecc_con_ratio": 4.0}
    score, badges = ControlScore().compute(metrics, None, cfg, "squat")
    assert score == pytest.approx(10.0 - 0.5, abs=0.01)
    excessive = [b for b in badges if b.issue_key == "ecc_con_ratio_excessive"]
    assert len(excessive) == 1
    assert excessive[0].severity == "Medium"


def test_session4_control_ecc_con_works_for_all_three_exercises(cfg: ThresholdConfig) -> None:
    """ControlScore.ecc_con_ratio applies to squat / bench / deadlift identically."""
    for ex in ("squat", "bench", "deadlift"):
        metrics = {"ecc_con_ratio": 0.5}
        score, badges = ControlScore().compute(metrics, None, cfg, ex)
        rushed = [b for b in badges if b.issue_key == "ecc_con_ratio_rushed"]
        assert len(rushed) == 1, f"missing dock for exercise={ex}"


def test_session4_control_ecc_con_no_metric_no_dock(cfg: ThresholdConfig) -> None:
    """Missing key (analyses scored before Session 4) → no dock from new branch."""
    metrics = {}
    score, badges = ControlScore().compute(metrics, None, cfg, "squat")
    new = [b for b in badges if b.issue_key.startswith("ecc_con_ratio_")]
    assert new == []
    assert score == 10.0
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/unit/test_scoring.py -xvs -k "session4_control" 2>&1 | tail -15
```
Expected: 4 of 5 fail (score ≠ expected dock; no new badge).

- [ ] **Step 3: Implement the branch**

In `backend/app/cv/scoring.py::ControlScore.compute`, after the existing `rep_std` block (around line 580) and before the deadlift lockout block, insert:

```python
        # Session 4: ecc_con_ratio auto-flow (FR-SCOR-04 refinement)
        ecc_con = metrics.get("ecc_con_ratio")
        if ecc_con is not None and ecc_con > 0.0:
            target_min = cfg.get("control", "ecc_con_ratio_target_min")  # 1.0
            target_max = cfg.get("control", "ecc_con_ratio_target_max")  # 3.0
            if ecc_con < target_min:
                score -= 1.0
                badges.append(
                    BadgeResult(
                        dimension="Control",
                        issue_key="ecc_con_ratio_rushed",
                        severity="High",
                        message=(
                            f"Lower the bar with more control — eccentric phase "
                            f"was rushed (ratio {ecc_con:.2f}, target ≥ {target_min:.1f})."
                        ),
                    )
                )
            elif ecc_con > target_max:
                score -= 0.5
                badges.append(
                    BadgeResult(
                        dimension="Control",
                        issue_key="ecc_con_ratio_excessive",
                        severity="Medium",
                        message=(
                            f"Eccentric tempo is excessive (ratio {ecc_con:.2f}, "
                            f"target ≤ {target_max:.1f}). Consider a moderate descent."
                        ),
                    )
                )
```

- [ ] **Step 4: Run to verify pass**

```bash
cd backend && uv run pytest tests/unit/test_scoring.py -xvs -k "session4_control" 2>&1 | tail -15
```
Expected: 5 passed.

- [ ] **Step 5: Full scoring regression**

```bash
cd backend && uv run pytest tests/unit/test_scoring.py -x --tb=short 2>&1 | tail -10
```
Expected: every test passes.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/scoring.py backend/tests/unit/test_scoring.py
git commit -m "feat(cv): ControlScore.ecc_con_ratio auto-flow branch (Session 4 #8)

When session-aggregate ecc_con_ratio is outside the configured target
window (control.ecc_con_ratio_target_min..max in thresholds_v1.json),
dock 1.0 with severity High for rushed (<min) or 0.5 with severity
Medium for excessive (>max). Applies to all three exercises.

Refs L2-SAGITTAL-TRIVIAL-02"
```

---

### Task 10: Update `_aggregate_rep_metrics` in `pipeline.py` to forward Session 4 keys

**Files:**
- Modify: `backend/app/services/pipeline.py::_aggregate_rep_metrics`
- Test: `backend/tests/unit/test_pipeline_aggregation.py` (if exists; else inline test in pipeline test file — discover via Glob)

- [ ] **Step 1: Find the aggregator + existing test**

```bash
cd backend && grep -n "_aggregate_rep_metrics" app/services/pipeline.py 2>&1 | head -5
cd backend && grep -rn "_aggregate_rep_metrics" tests/ 2>&1 | head -10
```
Expected: function location identified; existing test file or inline asserts identified.

- [ ] **Step 2: Add failing test**

Append a test to whichever file covers `_aggregate_rep_metrics`. If no dedicated test exists, add to `backend/tests/unit/test_metric_extraction_sagittal.py`:

```python
def test_session4_pipeline_aggregate_passes_through_session4_keys() -> None:
    """The aggregator that feeds OverallFormScore must propagate
    depth_classification (modal string) and ecc_con_ratio (mean float)."""
    from app.services.pipeline import _aggregate_rep_metrics
    from app.cv.metric_extraction import RepMetrics
    from app.cv.rep_detection import DetectedRep

    rep_metrics = [
        RepMetrics(
            rep_index=0, start_frame=0, end_frame=29,
            metrics={
                "depth_classification": "above_parallel",
                "ecc_con_ratio": 0.6,
                "depth_angle": 95.0,
            },
        ),
        RepMetrics(
            rep_index=1, start_frame=30, end_frame=59,
            metrics={
                "depth_classification": "above_parallel",
                "ecc_con_ratio": 0.8,
                "depth_angle": 95.0,
            },
        ),
        RepMetrics(
            rep_index=2, start_frame=60, end_frame=89,
            metrics={
                "depth_classification": "at_parallel",
                "ecc_con_ratio": 1.0,
                "depth_angle": 90.0,
            },
        ),
    ]
    reps = [DetectedRep(rep_index=r.rep_index, start_frame=r.start_frame, end_frame=r.end_frame) for r in rep_metrics]
    agg = _aggregate_rep_metrics(rep_metrics, reps, session_confidence=0.9)
    # ecc_con_ratio is the mean across reps (0.6, 0.8, 1.0 → 0.8)
    assert agg["ecc_con_ratio"] == pytest.approx(0.8, abs=0.01)
    # depth_classification is the modal label (2× above_parallel, 1× at_parallel → above_parallel)
    assert agg["depth_classification"] == "above_parallel"
```

- [ ] **Step 3: Run to verify failure**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -xvs -k "aggregate" 2>&1 | tail -15
```
Expected: `KeyError: 'ecc_con_ratio'` or `KeyError: 'depth_classification'` on the aggregate dict.

- [ ] **Step 4: Read the existing aggregator implementation**

```bash
cd backend && sed -n '$(grep -n "def _aggregate_rep_metrics" app/services/pipeline.py | head -1 | cut -d: -f1),+80p' app/services/pipeline.py
```
(Use Read tool in agentic execution — sed snippet for shell readability.)

Identify how `phase_of_max_deviation` (the existing string-aggregated key) is handled; mirror that pattern.

- [ ] **Step 5: Extend the aggregator**

In `_aggregate_rep_metrics`, add to the per-rep iteration that builds the aggregate dict (mirror the existing pattern for numeric mean + string modal):

For numeric mean across reps:
```python
    ecc_con_ratios = [
        r.metrics["ecc_con_ratio"]
        for r in rep_metrics
        if "ecc_con_ratio" in r.metrics
        and isinstance(r.metrics["ecc_con_ratio"], (int, float))
        and r.metrics["ecc_con_ratio"] > 0.0
    ]
    if ecc_con_ratios:
        agg["ecc_con_ratio"] = float(sum(ecc_con_ratios) / len(ecc_con_ratios))
```

For modal string:
```python
    depth_labels = [
        r.metrics["depth_classification"]
        for r in rep_metrics
        if "depth_classification" in r.metrics
    ]
    if depth_labels:
        from collections import Counter
        agg["depth_classification"] = Counter(depth_labels).most_common(1)[0][0]
```

(Adjust local variable name `agg` if the existing function uses a different name — read it first.)

- [ ] **Step 6: Run aggregator test to confirm pass**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py -xvs -k "aggregate" 2>&1 | tail -10
```
Expected: 1 passed.

- [ ] **Step 7: Run full pipeline test suite (regression)**

```bash
cd backend && uv run pytest tests/unit/ -k "pipeline or aggregate or scoring" -x --tb=short 2>&1 | tail -15
```
Expected: every test passes.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/pipeline.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(pipeline): forward Session 4 keys through _aggregate_rep_metrics

ecc_con_ratio: numeric mean across reps (filters non-positive sentinels).
depth_classification: modal label across reps. Both keys appear in the
aggregate dict consumed by OverallFormScore.compute, enabling the
TechniqueScore and ControlScore auto-flow branches added in Tasks 8/9.

Refs L2-SAGITTAL-TRIVIAL-01..02"
```

---

### Task 11: Flip registry flags

**Files:**
- Modify: `backend/app/cv/sagittal_metrics_registry.py`
- Test: `backend/tests/unit/test_sagittal_metrics_registry.py` (existing) — append assertion

- [ ] **Step 1: Add failing test**

Append to `backend/tests/unit/test_sagittal_metrics_registry.py`:

```python
def test_session4_registry_flags_flipped():
    """Session 4 flips computed_yet for 4 metrics and in_scoring for 2."""
    from app.cv.sagittal_metrics_registry import SAGITTAL_METRICS_REGISTRY
    entries = {e.key_name: e for e in SAGITTAL_METRICS_REGISTRY}

    # All four become computed.
    for key in ("depth_classification", "ecc_con_ratio", "pause_duration_s", "lockout_torso_lean_deg"):
        assert entries[key].computed_yet is True, f"{key} should have computed_yet=True after Session 4"

    # Two auto-flow metrics also feed scoring.
    assert entries["depth_classification"].in_scoring is True
    assert entries["ecc_con_ratio"].in_scoring is True

    # The two compute-only ones stay out of scoring until expert validation.
    assert entries["pause_duration_s"].in_scoring is False
    assert entries["lockout_torso_lean_deg"].in_scoring is False

    # Session 5+ entries remain pristine — no accidental flips.
    for key in (
        "ankle_dorsiflexion_deg", "wrist_alignment_deg", "bar_touch_height_pct",
        "setup_shoulder_x_offset", "shin_angle_deg", "setup_knee_angle_deg",
        "arch_deg", "bar_to_hip_distance", "shoulder_protraction_proxy_px",
        "lumbar_flexion_proxy_delta_deg", "bar_path_classification",
        "technique_consistency_std",
    ):
        assert entries[key].computed_yet is False, f"{key} should stay computed_yet=False"
        assert entries[key].in_scoring is False
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/unit/test_sagittal_metrics_registry.py -xvs -k session4 2>&1 | tail -10
```
Expected: AssertionError on `computed_yet is True`.

- [ ] **Step 3: Flip the flags**

In `backend/app/cv/sagittal_metrics_registry.py`, change the four Session 4 entries (lines ~71-118):

- `depth_classification`: `computed_yet=True, in_scoring=True`
- `ecc_con_ratio`: `computed_yet=True, in_scoring=True`
- `pause_duration_s`: `computed_yet=True` (keep `in_scoring=False`)
- `lockout_torso_lean_deg`: `computed_yet=True` (keep `in_scoring=False`)

Leave Session 5/6/7 entries untouched.

- [ ] **Step 4: Run to confirm pass**

```bash
cd backend && uv run pytest tests/unit/test_sagittal_metrics_registry.py -x --tb=short 2>&1 | tail -10
```
Expected: every test passes.

- [ ] **Step 5: Run the registry-endpoint test for regression**

```bash
cd backend && uv run pytest tests/unit/test_expert_sagittal_metrics_endpoint.py -x --tb=short 2>&1 | tail -10
```
Expected: pass — the endpoint serializes whatever flags the registry has, so flipping flags is transparent.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/sagittal_metrics_registry.py backend/tests/unit/test_sagittal_metrics_registry.py
git commit -m "feat(cv): flip Session 4 registry flags (computed_yet + in_scoring)

depth_classification, ecc_con_ratio: computed_yet=True, in_scoring=True
pause_duration_s, lockout_torso_lean_deg: computed_yet=True only.

Session 5-7 entries remain pristine — guarded by a regression test
asserting they keep computed_yet=False until their own session lands.

Refs L2-SAGITTAL-TRIVIAL-01..04"
```

---

### Task 12: Integration test on `atharva-squat.mov`

**Files:**
- Create: `backend/tests/integration/test_pipeline_session4_metrics.py`

The design references `atharva-squat.mov` as the canonical squat fixture. Check `backend/tests/fixtures/` for the actual filename.

- [ ] **Step 1: Locate the squat fixture**

```bash
cd backend && ls tests/fixtures/ 2>&1 | grep -iE "squat|atharva"
```
Expected: one or more squat fixtures. Pick the highest-quality one (typically the largest by size). Use that path verbatim in the test.

- [ ] **Step 2: Write the integration test**

Create `backend/tests/integration/test_pipeline_session4_metrics.py`:

```python
"""Session 4 integration test — atharva-squat fixture must populate four
new sagittal metrics in rep_metrics, and two new scoring badges must
appear in OverallFormScore.compute output.

Per design §Section-5 — integration test fixture is the squat clip; bench
and deadlift fixtures get the same treatment in later sessions.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Wire ThresholdConfig to v1 before any app.* imports.
_V1_PATH = (
    Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
)
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

import numpy as np  # noqa: E402

from app.config import ThresholdConfig  # noqa: E402
from app.cv.metric_extraction import extract_rep_metrics  # noqa: E402
from app.cv.pose_extraction import extract_landmarks  # noqa: E402
from app.cv.rep_detection import detect_reps  # noqa: E402
from app.cv.scoring import OverallFormScore  # noqa: E402
from app.cv.signal_processing import compute_angle_timeseries  # noqa: E402
from app.cv.lifter_side import detect_lifter_side  # noqa: E402


_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "atharva_squat.mp4"


def _skip_if_fixture_missing():
    if not _FIXTURE_PATH.exists():
        pytest.skip(f"atharva-squat fixture not present at {_FIXTURE_PATH}")


@pytest.mark.integration
def test_session4_atharva_squat_populates_four_new_keys() -> None:
    _skip_if_fixture_missing()
    landmarks, fps = extract_landmarks(str(_FIXTURE_PATH))
    side = detect_lifter_side(landmarks, fps=fps)
    angles = compute_angle_timeseries(landmarks, exercise_type="squat", lifter_side=side)
    reps = detect_reps(angles["hip_angle"], fps=fps, exercise_type="squat", exercise_variant="standard")
    assert len(reps) >= 1, "fixture must contain at least one detected rep"
    rep_metrics = extract_rep_metrics(
        reps=reps, landmarks_per_frame=list(landmarks), angle_timeseries=angles,
        exercise_type="squat", exercise_variant="standard", fps=fps, lifter_side=side,
    )
    for r in rep_metrics:
        assert "depth_classification" in r.metrics
        assert r.metrics["depth_classification"] in {"above_parallel", "at_parallel", "below_parallel"}
        assert "ecc_con_ratio" in r.metrics
        assert isinstance(r.metrics["ecc_con_ratio"], float)
        assert r.metrics["ecc_con_ratio"] >= 0.0
        assert "pause_duration_s" in r.metrics
        assert r.metrics["pause_duration_s"] >= 0.0
        assert "lockout_torso_lean_deg" in r.metrics


@pytest.mark.integration
def test_session4_atharva_squat_scoring_produces_session4_badges() -> None:
    """If the fixture squat is shallow (above parallel) OR rushed (ratio<1),
    the new scoring branches must produce at least one new badge."""
    _skip_if_fixture_missing()
    landmarks, fps = extract_landmarks(str(_FIXTURE_PATH))
    side = detect_lifter_side(landmarks, fps=fps)
    angles = compute_angle_timeseries(landmarks, exercise_type="squat", lifter_side=side)
    reps = detect_reps(angles["hip_angle"], fps=fps, exercise_type="squat", exercise_variant="standard")
    rep_metrics = extract_rep_metrics(
        reps=reps, landmarks_per_frame=list(landmarks), angle_timeseries=angles,
        exercise_type="squat", exercise_variant="standard", fps=fps, lifter_side=side,
    )

    from app.services.pipeline import _aggregate_rep_metrics
    agg = _aggregate_rep_metrics(rep_metrics, reps, session_confidence=0.9)
    cfg = ThresholdConfig(_V1_PATH)
    scorer = OverallFormScore()
    result = scorer.compute(agg, bar_path=None, cfg=cfg, exercise_type="squat")

    # Print badges to stdout so the integration log shows the surface.
    all_badges = [b for dim in result.dimensions for b in dim.badges]
    print(f"\n[session-4-integration] new badges from atharva-squat:")
    for b in all_badges:
        if b.issue_key in ("squat_depth_classification_above", "ecc_con_ratio_rushed", "ecc_con_ratio_excessive"):
            print(f"  - {b.dimension}/{b.severity}/{b.issue_key}: {b.message}")

    # The fixture is real-world footage so we don't assert which badges fire,
    # only that the branches are wired correctly: scoring succeeded without
    # exceptions AND the aggregate carries the new keys.
    assert "depth_classification" in agg
    assert "ecc_con_ratio" in agg
    assert result.overall is not None
```

- [ ] **Step 3: Run the integration test**

```bash
cd backend && uv run pytest tests/integration/test_pipeline_session4_metrics.py -xvs 2>&1 | tail -40
```
Expected: 2 passed (or skipped with a clear reason if fixture is missing — in which case investigate before commit).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/test_pipeline_session4_metrics.py
git commit -m "test(cv): integration test for Session 4 metrics on atharva-squat fixture

Asserts all four new keys (depth_classification, ecc_con_ratio,
pause_duration_s, lockout_torso_lean_deg) appear in rep_metrics for every
detected rep. Also exercises the scoring path and surfaces the new
auto-flow badges for inspection (no hard assertion on which badges fire —
fixture is real-world footage).

Refs L2-SAGITTAL-TRIVIAL-01..04"
```

---

### Task 13: Frontend `<AutoFlowMetricsChips />` component + ResultsPage mount

**Files:**
- Modify: `frontend/src/pages/ResultsPage.tsx` (add sub-component + mount above rep-metrics table)
- Create: `frontend/src/pages/__tests__/ResultsPage.autoFlowMetrics.test.tsx`

- [ ] **Step 1: Add failing vitest case**

Create `frontend/src/pages/__tests__/ResultsPage.autoFlowMetrics.test.tsx`:

```tsx
/**
 * Session 4 — AutoFlowMetricsChips: shows depth_classification + ecc_con_ratio
 * as small chip badges on the regular user's ResultsPage. Reads directly from
 * analysis.rep_metrics[].metrics.{depth_classification, ecc_con_ratio}; no
 * new backend persistence required.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: { getSession: vi.fn().mockResolvedValue({ data: { session: null } }) },
    channel: vi.fn().mockReturnValue({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn(),
      unsubscribe: vi.fn(),
    }),
    removeChannel: vi.fn(),
  },
}));

vi.mock("@/hooks/useAnalysisDetail", () => ({
  useAnalysisDetail: () => ({
    data: {
      id: "abc",
      status: "completed",
      exercise_type: "squat",
      exercise_variant: "standard",
      rep_count: 2,
      confidence_score: 0.9,
      form_score_safety: 8.0,
      form_score_technique: 6.5,
      form_score_path_balance: 7.0,
      form_score_control: 7.5,
      form_score_overall: 7.4,
      rep_metrics: [
        {
          rep_index: 1,
          start_frame: 0,
          end_frame: 30,
          metrics: {
            depth_classification: "above_parallel",
            ecc_con_ratio: 0.7,
            depth_angle: 95.0,
          },
        },
        {
          rep_index: 2,
          start_frame: 31,
          end_frame: 60,
          metrics: {
            depth_classification: "at_parallel",
            ecc_con_ratio: 1.4,
            depth_angle: 90.0,
          },
        },
      ],
      coaching_result: null,
      created_at: "2026-05-22T12:00:00Z",
      detected_at: null,
      detection_result: null,
      annotated_video_url: null,
      plot_url: null,
      pdf_url: null,
    },
    loading: false,
    error: null,
  }),
}));

import ResultsPage from "@/pages/ResultsPage";

describe("ResultsPage AutoFlowMetricsChips (Session 4)", () => {
  it("renders depth_classification chip with modal label across reps", async () => {
    render(
      <MemoryRouter initialEntries={["/results/abc"]}>
        <ResultsPage />
      </MemoryRouter>,
    );
    // Modal of (above_parallel, at_parallel) deterministic via first-occurrence
    // tiebreak in implementation — assert the depth chip appears.
    const chip = await screen.findByTestId("auto-flow-depth-chip");
    expect(chip).toBeInTheDocument();
    // Human-readable label: "above parallel" or "at parallel".
    expect(chip.textContent).toMatch(/Depth: (above|at|below) parallel/i);
  });

  it("renders ecc_con_ratio chip with mean across reps to one decimal", async () => {
    render(
      <MemoryRouter initialEntries={["/results/abc"]}>
        <ResultsPage />
      </MemoryRouter>,
    );
    const chip = await screen.findByTestId("auto-flow-ecc-con-chip");
    expect(chip).toBeInTheDocument();
    // mean of 0.7 and 1.4 → 1.05 → displayed as "1.1"
    expect(chip.textContent).toMatch(/Ecc\/Con: 1\.\d/);
  });

  it("does not render chips when keys are absent (analyses scored before Session 4)", async () => {
    // Re-mock useAnalysisDetail with stripped metrics.
    vi.doMock("@/hooks/useAnalysisDetail", () => ({
      useAnalysisDetail: () => ({
        data: {
          id: "abc",
          status: "completed",
          exercise_type: "squat",
          rep_metrics: [
            { rep_index: 1, start_frame: 0, end_frame: 30, metrics: { depth_angle: 95.0 } },
          ],
          coaching_result: null,
          created_at: "2026-05-22T12:00:00Z",
        },
        loading: false,
        error: null,
      }),
    }));
    const ResultsPageFresh = (await import("@/pages/ResultsPage")).default;
    render(
      <MemoryRouter initialEntries={["/results/abc"]}>
        <ResultsPageFresh />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId("auto-flow-depth-chip")).not.toBeInTheDocument();
    expect(screen.queryByTestId("auto-flow-ecc-con-chip")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

```bash
cd frontend && npx vitest run src/pages/__tests__/ResultsPage.autoFlowMetrics.test.tsx 2>&1 | tail -25
```
Expected: failing — chip elements not rendered.

- [ ] **Step 3: Implement `<AutoFlowMetricsChips />`**

In `frontend/src/pages/ResultsPage.tsx`, add the sub-component near the top of the file (after other small sub-components — search for `function ConfidenceBadge` and insert after):

```tsx
// ---------------------------------------------------------------------------
// AutoFlowMetricsChips (Session 4, FR-SCOR-02/04 refinements)
// ---------------------------------------------------------------------------

interface AutoFlowMetricsChipsProps {
  repMetrics: RepMetricDetail[];
}

function AutoFlowMetricsChips({ repMetrics }: AutoFlowMetricsChipsProps) {
  // Depth classification — modal across reps; nullable if no rep has the key.
  const depthLabels = repMetrics
    .map((r) => r.metrics?.depth_classification)
    .filter((v): v is string => typeof v === "string");
  const modalDepth = depthLabels.length
    ? depthLabels.reduce<Record<string, number>>(
        (acc, v) => ({ ...acc, [v]: (acc[v] ?? 0) + 1 }),
        {},
      )
    : null;
  const depthLabel = modalDepth
    ? Object.entries(modalDepth).sort((a, b) => b[1] - a[1])[0][0]
    : null;

  // Ecc/Con ratio — mean across reps (positive values only).
  const ratios = repMetrics
    .map((r) => r.metrics?.ecc_con_ratio)
    .filter((v): v is number => typeof v === "number" && v > 0);
  const meanRatio = ratios.length
    ? ratios.reduce((a, b) => a + b, 0) / ratios.length
    : null;

  if (depthLabel === null && meanRatio === null) return null;

  return (
    <div className="mb-4 flex flex-wrap gap-2" data-testid="auto-flow-metrics-row">
      {depthLabel !== null && (
        <span
          className="inline-flex items-center rounded-full bg-indigo-50 px-3 py-1 text-sm font-medium text-indigo-800"
          data-testid="auto-flow-depth-chip"
        >
          Depth: {depthLabel.replace(/_/g, " ")}
        </span>
      )}
      {meanRatio !== null && (
        <span
          className="inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-800"
          data-testid="auto-flow-ecc-con-chip"
        >
          Ecc/Con: {meanRatio.toFixed(1)}
        </span>
      )}
    </div>
  );
}
```

Then mount `<AutoFlowMetricsChips repMetrics={analysis.rep_metrics ?? []} />` immediately above the `<RepMetricsTable />` in the JSX (search for `<RepMetricsTable` and add the chip row directly before it).

If `RepMetricDetail.metrics` is currently typed too narrowly, widen it in the import (or use a small `as` cast in the chip component) so `depth_classification` / `ecc_con_ratio` are reachable.

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx vitest run src/pages/__tests__/ResultsPage.autoFlowMetrics.test.tsx 2>&1 | tail -25
```
Expected: 3 passed.

- [ ] **Step 5: Run full frontend test suite (regression)**

```bash
cd frontend && npx vitest run 2>&1 | tail -10
```
Expected: every test passes (previous count was 746 + new tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ResultsPage.tsx frontend/src/pages/__tests__/ResultsPage.autoFlowMetrics.test.tsx
git commit -m "feat(frontend): AutoFlowMetricsChips on ResultsPage (Session 4)

Renders two small chips above the rep-metrics table:
- 'Depth: <classification>' from rep_metrics[].metrics.depth_classification
  (modal across reps)
- 'Ecc/Con: <ratio>' from rep_metrics[].metrics.ecc_con_ratio
  (mean across reps, one decimal place)

Backward compatible: when keys are absent (analyses scored before Session
4), the chip row is hidden entirely. No new backend persistence — chips
read directly from the existing rep_metrics JSONB.

Refs L2-SAGITTAL-TRIVIAL-01..02"
```

---

### Task 14: Full local verification gate

**Files:** N/A

- [ ] **Step 1: Backend lint + types**

```bash
cd backend && uv run ruff check app tests 2>&1 | tail -5
cd backend && uv run pyright app 2>&1 | tail -10
```
Expected: `All checks passed.` and `0 errors`.

- [ ] **Step 2: Backend full test suite**

```bash
cd backend && uv run pytest tests/unit/ tests/integration/ -x --tb=short 2>&1 | tail -25
```
Expected: every test passes; total count ≥ 2225 (Session-3 baseline) + the new Session 4 tests.

- [ ] **Step 3: Backend coverage check on new functions**

```bash
cd backend && uv run pytest tests/unit/test_metric_extraction_sagittal.py tests/unit/test_scoring.py --cov=app.cv.metric_extraction --cov=app.cv.scoring --cov-report=term-missing 2>&1 | tail -30
```
Expected: line coverage on the four new helpers (`_classify_depth`, `_pause_duration_s`, `_lockout_torso_lean_deg`, the new scoring branches) ≥ 90%. If any branch is uncovered, add a targeted test — NEVER lower the threshold.

- [ ] **Step 4: Frontend lint + typecheck**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -10
cd frontend && npm run lint 2>&1 | tail -10
```
Expected: 0 errors / 0 warnings.

- [ ] **Step 5: Frontend test suite**

```bash
cd frontend && npx vitest run 2>&1 | tail -10
```
Expected: every test passes; total ≥ 755 (Session-3 baseline) + the new chip tests.

- [ ] **Step 6: Smoke-only commit (no code; just a verification log)**

No commit at this gate — verification is local only.

---

### Task 15: Push branch + open `/team` cross-stack PR

**Files:** N/A (git + GitHub)

- [ ] **Step 1: Push branch**

```bash
git push -u origin feat/sagittal-trivial-metrics 2>&1 | tail -5
```
Expected: branch pushed.

- [ ] **Step 2: Open PR via MCP**

Use `mcp__github__create_pull_request` with:
- owner: `atharva6905`
- repo: `spelix`
- title: `feat(cv): Session 4 — trivial sagittal metrics + auto-flow scoring`
- head: `feat/sagittal-trivial-metrics`
- base: `main`
- body: structured per the master manifest pattern (Summary, Scope by Audit ID, Test plan, Migrations: none, ADRs added, Backlog rows closed).

Required body sections:
```
## Summary
Session 4 of cv-audit. Adds four sagittal-view extractors and wires two
of them into existing form-scoring dimensions. First user-visible scoring
impact of the audit work.

## Closed audit IDs
- L2-SAGITTAL-TRIVIAL-01 (depth_classification)
- L2-SAGITTAL-TRIVIAL-02 (ecc_con_ratio)
- L2-SAGITTAL-TRIVIAL-03 (pause_duration_s)
- L2-SAGITTAL-TRIVIAL-04 (lockout_torso_lean_deg)

## Test plan
- [ ] Backend unit: 4 extractor tests + 5 scoring tests + 1 aggregation test
- [ ] Backend integration: atharva_squat fixture populates all 4 keys + scoring branches surface badges
- [ ] Frontend: AutoFlowMetricsChips renders depth + ecc/con chips
- [ ] No migrations — JSONB-only addition

## Migrations
None — all four metrics ride through the existing rep_metrics.metrics
JSONB column. Existing analyses lack the keys; frontend handles gracefully
(chips hidden).

## ADRs added in this PR
- ADR-AUTO-FLOW-REFINEMENTS in decisions.md

## Surfaced evidence pending in PR description
- gh pr checks <PR> output (Tasks 16, 17)
- Post-merge gh run watch <main-run-id> (Task 18)
- E2E screenshot from spelix.app re-upload (Task 19)
```

Print the returned `html_url` to chat.

- [ ] **Step 3: Print PR URL**

```bash
echo "PR URL: <html_url from response>"
```

---

### Task 16: spelix-security-reviewer on new badge text + UnvalidatedMetricsPanel diff

**Files:** N/A (agent dispatch)

The new badge text in `scoring.py` is user-facing (flows through coaching prompt → coaching prose). Must be SaMD-compliant: no "injury risk", no "injury prevention", no "safety score" in user-facing strings.

- [ ] **Step 1: Dispatch the security-reviewer agent on the diff**

Use the `Agent` tool with `subagent_type: "spelix-security-reviewer"`. Prompt:

```
Review the diff on branch feat/sagittal-trivial-metrics for SaMD language
compliance and user-facing-string risks. Focus areas:

1. backend/app/cv/scoring.py — two new BadgeResult message strings:
   - "Squat reached above parallel — aim for {threshold}." (Technique branch)
   - "Lower the bar with more control — eccentric phase was rushed
     (ratio X, target ≥ Y)." (Control branch, rushed variant)
   - "Eccentric tempo is excessive (ratio X, target ≤ Y). Consider a
     moderate descent." (Control branch, excessive variant)
2. frontend/src/pages/ResultsPage.tsx — AutoFlowMetricsChips strings:
   - "Depth: <classification>" with values "above parallel" / "at parallel" /
     "below parallel"
   - "Ecc/Con: <ratio>"
3. config/thresholds_v1.json — provenance_citation strings (Schoenfeld 2010,
   Wilk et al. 1993).

Forbidden phrases project-wide: "injury risk", "injury prevention",
"safety score". The user-facing label for form_score_safety is
"Movement Quality" only.

Output: PASS, PASS_WITH_FINDINGS, or CRITICAL with file:line citations.
```

- [ ] **Step 2: Print the agent verdict to chat**

If CRITICAL — STOP per master manifest §Standing-Rules. Open a remediation /goal narrowed to fixing the cited text. Do NOT lower any other gate or rephrase any non-cited string.

If PASS or PASS_WITH_FINDINGS — record verdict and continue.

---

### Task 17: PR-level CI gate

**Files:** N/A

- [ ] **Step 1: Watch CI**

```bash
gh pr checks <PR-NUMBER> --watch 2>&1 | tail -20
```
Expected (final state): every PR-level check `pass`: Backend Lint & Type Check, Backend Tests, Frontend Lint & Type Check, Frontend Tests, Secret Scanning, Vercel. "Deploy to Production" shows `skipping` (it only fires post-merge).

- [ ] **Step 2: If any check is red, diagnose and re-push**

```bash
gh run view <FAILED-RUN-ID> --log-failed 2>&1 | tail -60
```
Fix root cause locally, re-run failing test or lint, commit, push. Hard limit: 2 retries per check (master manifest STOP clause).

- [ ] **Step 3: Print final CI status to chat**

```bash
gh pr checks <PR-NUMBER> 2>&1 | tail -20
```

---

### Task 18: Merge PR + post-merge "Deploy to Production"

**Files:** N/A

- [ ] **Step 1: Merge via MCP**

Use `mcp__github__merge_pull_request`:
- owner: `atharva6905`
- repo: `spelix`
- pull_number: `<PR-NUMBER>`
- merge_method: `merge` (NEVER `squash`)

Print `merged=true` and merge SHA to chat.

- [ ] **Step 2: Sync local main**

```bash
git checkout main && git pull origin main 2>&1 | tail -5
git log --oneline -3
```
Expected: HEAD is the merge commit.

- [ ] **Step 3: Watch the post-merge "Deploy to Production" workflow**

```bash
gh run list --branch main --limit 1 --json databaseId,name,conclusion 2>&1 | tail -10
gh run watch <MAIN-RUN-ID> 2>&1 | tail -20
```
Or, if `--watch` produces too much output:

```bash
gh run view <MAIN-RUN-ID> --json jobs --jq '.jobs[] | select(.name=="Deploy to Production") | {name, conclusion, status}'
```
Expected: `conclusion: success`.

- [ ] **Step 4: Verify droplet HEAD matches merge SHA**

```bash
ssh spelix-droplet "git log --oneline -1"
ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"
```
Expected: HEAD SHA matches the merge SHA; all containers `(healthy)`.

- [ ] **Step 5: Print all surfaced evidence to chat**

Required output (single message):
- Merge SHA
- `gh run view ... Deploy to Production` conclusion=success
- SSH HEAD log line
- Docker container health lines

---

### Task 19: E2E verification via Playwright MCP on spelix.app

**Files:** N/A (browser automation + screenshot)

- [ ] **Step 1: Navigate and log in (use existing test credentials)**

Use Playwright MCP:
- `browser_navigate` → `https://spelix.app`
- Take baseline `browser_snapshot`.

- [ ] **Step 2: Re-upload atharva-squat fixture**

Navigate to upload page; upload the fixture from `e2e/fixtures/atharva-squat.mov`. Wait for processing to complete (poll status page; timeout 5min).

- [ ] **Step 3: Verify regular ResultsPage shows new chips**

Navigate to results page for the new analysis. Take screenshot.

Assert (via `browser_snapshot` text content):
- `Depth:` chip present with one of `above parallel` / `at parallel` / `below parallel`.
- `Ecc/Con:` chip present with a decimal value.

Save screenshot as `e2e/screenshots/session4-results-autoflow-<short-sha>.png`.

- [ ] **Step 4: Verify expert UnvalidatedMetricsPanel shows the four new metrics with values**

Log in as expert (or use admin role-switch). Navigate to `/expert/analyses/<id>`. Take screenshot.

Assert:
- `depth_classification` row shows a value (not "Not yet computed").
- `ecc_con_ratio` row shows a value.
- `pause_duration_s` row shows a value.
- `lockout_torso_lean_deg` row shows a value.

Save screenshot as `e2e/screenshots/session4-expert-panel-<short-sha>.png`.

- [ ] **Step 5: Check console errors and network 4xx/5xx**

```
browser_console_messages level=error → expect []
browser_network_requests → filter status >= 400 → expect []
```

- [ ] **Step 6: Print screenshot paths to chat**

```
Screenshots:
- e2e/screenshots/session4-results-autoflow-<sha>.png
- e2e/screenshots/session4-expert-panel-<sha>.png
```

---

### Task 20: ADR-AUTO-FLOW-REFINEMENTS in `decisions.md`

**Files:**
- Modify: `decisions.md` (append, never edit existing ADRs)

- [ ] **Step 1: Read existing decisions.md tail for format**

```bash
tail -60 decisions.md
```
Note the canonical ADR template (header, Context, Decision, Consequences, Status, Date, Author).

- [ ] **Step 2: Append the ADR**

Add at the bottom of `decisions.md`:

```markdown
## ADR-AUTO-FLOW-REFINEMENTS — Two refinement metrics bypass the compute-only-until-validated rule

**Date:** 2026-05-22
**Status:** Accepted
**Context:** cv-audit Session 4. The master ADR (ADR-SAGITTAL-METRICS-REGISTRY)
established that the 14 newly-added sagittal-view metrics are compute-only
until an expert reviewer validates their threshold values via FR-EXPV-08.
Two of the 16 metrics, however, are refinements of measurements whose
underlying math is already validated and live in production scoring:
- `depth_classification` is a categorical relabel of the existing
  `depth_angle` (already used by `TechniqueScore._score_squat`). The
  expert validates the categorical *label* (above/at/below parallel) and
  the band width (currently ±5°), but the underlying angle math is
  unchanged.
- `ecc_con_ratio` is a derived ratio of the existing per-rep
  `descent_duration_s` / `ascent_duration_s` (already exposed in
  `RepMetrics.metrics`). The expert validates the *target window*
  (`control.ecc_con_ratio_target_min..max`, currently 1.0..3.0), but the
  ratio computation is unchanged.

**Decision:** These two metrics flip `in_scoring=True` on day one (Session
4) and dock the form score immediately via new branches in
`TechniqueScore` and `ControlScore`. The other 12 metrics remain
compute-only until per-metric expert validation.

**Consequences:**
- (+) First user-visible scoring impact of the cv-audit work — squats
  above parallel and rushed eccentrics are now reflected in form scores.
- (+) Establishes a precedent: refinements of already-validated metrics
  may auto-flow; new measurements stay compute-only.
- (−) If the expert reviewer disagrees with either band width (±5°) or
  the ecc/con target window (1.0..3.0), thresholds are flipped via
  FR-EXPV-08 without code changes — but form scores produced between
  Session-4 deploy and the expert's revision use the initial defaults.
- (−) Mitigated by conservative defaults and badge text written
  defensively ("aim for", "consider") per design §Section-5 R3.

**Stop condition (master manifest §Section-6):** if the expert validates
the panel surface but objects to auto-flow scoring, revert these two
branches and downgrade both metrics to compute-only. The plan path back
is a single-commit revert of the scoring branches + a flag flip on the
two registry entries.

**Author:** Atharva Kulkarni (with Claude in /goal-driven Session 4)
**Supersedes:** —
**Related:** ADR-SAGITTAL-METRICS-REGISTRY, ADR-AUDIT-2026-05-22
```

- [ ] **Step 3: Commit and amend the merged PR is NOT possible — append in a follow-up commit on main**

Actually: since the PR is already merged, the ADR + backlog + manifest updates can either be (a) added to the PR pre-merge (preferred), or (b) bundled in a small follow-up commit on main (acceptable because they're docs-only).

Choose (a) — Tasks 20/21/22 should happen BEFORE Task 18 (merge). Re-order if executing sequentially: add Task 20-22 between Task 14 (local verification) and Task 15 (push). If they're added post-merge by mistake, open a tiny follow-up PR for them.

```bash
git add decisions.md
git commit -m "docs(adr): ADR-AUTO-FLOW-REFINEMENTS — depth and ecc/con bypass compute-only

These two refinement metrics auto-flow into TechniqueScore and ControlScore
on Session-4 day one because their underlying math is already validated
in production. Expert validation in Session 4+ targets only the
categorical label band (±5°) and the ratio target window (1.0..3.0)."
```

---

### Task 21: backlog.md — add and close L2-SAGITTAL-TRIVIAL rows

**Files:**
- Modify: `backlog.md`

- [ ] **Step 1: Add the four rows under the active session header**

Append (or insert under appropriate header) in `backlog.md`:

```markdown
## Session 4 — Trivial Metrics (auto-flow scoring)

| ID | Description | Status | Commit |
|---|---|---|---|
| L2-SAGITTAL-TRIVIAL-01 | depth_classification extractor + TechniqueScore branch + threshold config + registry flip + frontend chip | done | <merge-SHA> |
| L2-SAGITTAL-TRIVIAL-02 | ecc_con_ratio extractor + ControlScore branch + threshold config + registry flip + frontend chip | done | <merge-SHA> |
| L2-SAGITTAL-TRIVIAL-03 | pause_duration_s extractor (compute-only) + registry flip | done | <merge-SHA> |
| L2-SAGITTAL-TRIVIAL-04 | lockout_torso_lean_deg extractor (compute-only) + registry flip | done | <merge-SHA> |
```

Replace `<merge-SHA>` with the actual merge commit SHA after Task 18 (or use a placeholder and finalise in the same docs follow-up commit).

- [ ] **Step 2: Commit**

```bash
git add backlog.md
git commit -m "docs(backlog): close L2-SAGITTAL-TRIVIAL-01..04 (Session 4 done)"
```

---

### Task 22: Master manifest update + handoff with draft expert-onboarding email

**Files:**
- Modify: `docs/superpowers/goals/2026-05-22-cv-audit-master.md`
- Modify: `.claude/handoff.md`

- [ ] **Step 1: Flip manifest Session 4 status to complete; Session 5 to active**

In `docs/superpowers/goals/2026-05-22-cv-audit-master.md`, find the session-status table or list and:
- Mark Session 4 as `complete` with merge SHA recorded.
- Mark Session 5 (Standard single-frame landmark math) as `active`.
- Record this session's surfaced evidence: PR URL, CI run ID, screenshots, ADR.

- [ ] **Step 2: Write the handoff**

Overwrite `.claude/handoff.md`:

```markdown
# cv-audit handoff — Session 4 → Session 5

## Status
- Session 4: **complete** — merge SHA `<sha>`, PR `<url>`.
- Next session: Session 5 — Standard single-frame landmark math.
- Launch command: see `docs/superpowers/goals/2026-05-22-cv-audit-master.md`
  §Session-5 "Launch command" block — copy verbatim into `/goal`.
- Plan: `docs/superpowers/plans/2026-05-22-session-5-standard-landmark-math.md`
  — at handoff write, this is a SKELETON. Expand via
  `superpowers:writing-plans` before launching `/goal` (mirrors Sessions 2/3/4).

## Completed this session
- <sha1> feat(config): add Session 4 threshold entries
- <sha2> feat(cv): add _classify_depth helper
- <sha3> feat(cv): add _pause_duration_s extractor
- <sha4> feat(cv): add _lockout_torso_lean_deg extractor
- <sha5> test(cv): side-agnosticism mirror tests
- <sha6> feat(cv): wire Session 4 keys into _squat / _bench / _deadlift analyzers
- <sha7> feat(cv): TechniqueScore.depth_classification branch
- <sha8> feat(cv): ControlScore.ecc_con_ratio branch
- <sha9> feat(pipeline): forward Session 4 keys through _aggregate_rep_metrics
- <sha10> feat(cv): flip Session 4 registry flags
- <sha11> test(cv): integration test on atharva-squat fixture
- <sha12> feat(frontend): AutoFlowMetricsChips on ResultsPage
- <sha13> docs(adr): ADR-AUTO-FLOW-REFINEMENTS
- <sha14> docs(backlog): close L2-SAGITTAL-TRIVIAL-01..04

## Surfaced evidence
- PR URL: <url>
- PR-level CI: all 6 checks pass (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel)
- Post-merge: main-branch run <id> — Deploy to Production conclusion=success
- Droplet HEAD: <sha> matches merge SHA; containers healthy
- E2E screenshots:
  - `e2e/screenshots/session4-results-autoflow-<sha>.png` (regular user)
  - `e2e/screenshots/session4-expert-panel-<sha>.png` (expert panel)
- spelix-security-reviewer: PASS — no CRITICAL on badge text or registry descriptions
- Backend: <N> unit tests pass; ruff clean; pyright 0 errors
- Frontend: <M> vitest tests pass (+ N over Session-3 baseline of 755)

## Draft expert-onboarding email

```
Subject: Spelix — early sagittal-view metrics ready for your review

Hi <Expert>,

Following our last conversation, Spelix is now surfacing 4 of the
16 planned sagittal-view metrics on every new squat / bench / deadlift
analysis. Two of them — squat depth_classification and ecc_con_ratio —
already adjust the form scores users see. The other two
(pause_duration_s, lockout_torso_lean_deg) are computed but not yet
scored — they live in the "Unvalidated Metrics" panel on the expert
analysis detail page.

A sample analysis with all four populated is here:
  https://spelix.app/expert/analyses/<one-real-id>

Where to flag thresholds:
- For the two auto-flow metrics, the threshold defaults are:
    squat.depth_classification_min = "at_parallel"
    control.ecc_con_ratio_target_min = 1.0
    control.ecc_con_ratio_target_max = 3.0
  (Provenance: Schoenfeld 2010, Wilk et al. 1993.) If you'd like to
  propose a different value, use the "Flag" button next to the metric on
  the expert panel — that opens the FR-EXPV-08 threshold-flag form. A PR
  from me follows once your change is captured.
- For the two compute-only metrics, no thresholds are wired yet —
  please validate the values against the annotated video first. We can
  then talk about what (if any) threshold to set.

Sessions 5–7 will populate the remaining 12 metrics over the next
~1–2 weeks. I will email again once the standard single-frame
landmark batch (Session 5: ankle dorsiflexion, wrist alignment, bar
touch height, etc.) lands.

Thanks again for taking this on.

— Atharva
```

## Blockers
- None.

## Deferred items
- Per-rep granular docking on ecc_con_ratio (currently uses the
  session-aggregate value; per-rep dock is deferred to a post-onboarding
  refinement once thresholds validate).

## Resume guidance for Session 5
1. Read `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md`
   §Session-5 (7 metrics — single-frame landmark math).
2. Read this handoff + the master manifest §Session-5.
3. Expand the Session 5 skeleton plan via `superpowers:writing-plans`.
4. `/goal` with the Session 5 launch command from the manifest.
```

- [ ] **Step 3: Commit and push the docs follow-up**

If the docs commits were bundled in the PR pre-merge (preferred path), they're already on main and there's nothing to push. Otherwise:

```bash
git checkout -b docs/session-4-close
git add decisions.md backlog.md docs/superpowers/goals/2026-05-22-cv-audit-master.md .claude/handoff.md
git commit -m "docs(session-4-close): mark Session 4 complete, ADR, backlog, handoff with expert email"
git push -u origin docs/session-4-close
```
Open a small follow-up PR via MCP and merge it (CI is docs-only, fast).

---

### Task 23: Surface evidence for /goal completion (single chat message)

**Files:** N/A

The Haiku evaluator checks for specific evidence in chat. Print a single consolidated summary at the end:

- [ ] **Step 1: Print the consolidated summary**

```
=== Session 4 — Definition of Done ===

1. metric_extraction.py extended:
   - _classify_depth (helper)
   - _pause_duration_s (helper)
   - _lockout_torso_lean_deg (helper)
   - _squat_metrics now emits 4 new keys
   - _bench_metrics now emits ecc_con_ratio + pause_duration_s
   - _deadlift_metrics now emits ecc_con_ratio + pause_duration_s + lockout_torso_lean_deg
   git diff snippet: <inline>

2. scoring.py extended:
   - TechniqueScore: squat depth_classification branch
   - ControlScore: ecc_con_ratio branch (rushed / excessive)
   git diff snippet showing badge text: <inline>

3. thresholds_v1.json updated:
   - squat.depth_classification_min = "at_parallel"
   - control.ecc_con_ratio_target_min = 1.0
   - control.ecc_con_ratio_target_max = 3.0
   git diff snippet: <inline>

4. uv run pytest backend/tests/unit/test_metric_extraction_sagittal.py::test_session4_*:
   <N passed lines>

5. uv run pytest backend/tests/unit/test_scoring.py::test_session4_*:
   <N passed lines>

6. uv run pytest backend/tests/integration/test_pipeline_session4_metrics.py:
   <N passed lines + printed badges from real fixture>

7. Frontend git diff (ResultsPage + new test): <inline>

8. npx vitest run src/pages/__tests__/ResultsPage.autoFlowMetrics.test.tsx:
   <N passed lines>

9. PR: <url>

10. PR-level CI: `gh pr checks <PR>` output → all pass:
    <inline>

11. Merge: mcp__github__merge_pull_request → merged=true, sha=<sha>

12. Post-merge CI: `gh run watch <main-run-id>` →
    Deploy to Production conclusion=success

13. Droplet HEAD: ssh spelix-droplet "git log --oneline -1" →
    <sha matches merge SHA>

14. E2E Playwright MCP:
    - Regular user: depth + ecc/con chips visible on ResultsPage
    - Expert: 4 new metrics show values in UnvalidatedMetricsPanel
    - Screenshots: <paths>

15. ADR-AUTO-FLOW-REFINEMENTS in decisions.md: <inline diff>

16. Master manifest: Session 4=complete, Session 5=active.
    handoff.md: Session 5 launch command + draft expert-onboarding email.

=== End of Definition of Done ===
```

---

## Acceptance criteria (Definition of Done — for /goal evaluator)

- All 23 task checkboxes ticked.
- PR merged via `mcp__github__merge_pull_request` with `merge_method='merge'`.
- "Deploy to Production" workflow conclusion=success on main.
- Droplet HEAD matches merge SHA; all containers `(healthy)`.
- spelix-security-reviewer returns PASS or PASS_WITH_FINDINGS (NO CRITICAL).
- Coverage threshold not lowered (Standing Rule §1).
- E2E screenshots saved to `e2e/screenshots/` and paths surfaced in chat.
- ADR-AUTO-FLOW-REFINEMENTS appended to `decisions.md`.
- Master manifest + `.claude/handoff.md` updated; handoff includes draft expert-onboarding email.

---

## STOP conditions (re-stated from /goal launch)

- 40 turns elapsed without completion → auto-handoff + remediation per master manifest.
- Same error 3 consecutive turns → STOP.
- External input required → STOP, escalate.
- CI red after 2 retries on the same commit → narrow remediation /goal per Remediation Policy.
- spelix-security-reviewer CRITICAL → STOP, escalate (NEVER bypass).
- Coverage threshold not reached → add tests, NEVER lower threshold.

Recursion cap: 2 remediation attempts per session.
