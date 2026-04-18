# D-040 + D-041: Peak/Valley Rep Detection + Degenerate Scoring Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Spelix's fixed-threshold rep-detection state machine with a signal-relative peak/valley extractor (D-040), and make form scoring return `None` on degenerate input (empty reps or Very-Low session confidence) instead of defaulting to 10.0 (D-041). Both changes ship in one PR.

**Architecture:**
- **D-040** rewrites `backend/app/cv/rep_detection.py::detect_reps` to use `scipy.signal.find_peaks` on the inverted primary-angle timeseries. Valleys (rep bottoms) are identified by a `prominence_deg` tuning knob; adjacent local maxima become each rep's `start_frame` / `end_frame`. All per-exercise `_STANDING_THRESHOLD` / `_DEPTH_THRESHOLD` / `_HYSTERESIS_DEG` dicts and the `RepState` enum are deleted. The `detect_reps(angle_timeseries, landmarks_per_frame, exercise_type, exercise_variant, fps)` signature is preserved so no call-sites change (`exercise_variant` becomes unused — documented in the docstring).
- **D-041** adds a pure guard `_is_degenerate_scoring_input(rep_metrics, session_confidence) -> bool` in `pipeline.py` that returns `True` when `rep_metrics == []` OR `session_confidence < 0.50` (the confidence-label "Very Low" boundary from `confidence.py::confidence_label`). Step 9b in `run_cv_pipeline` checks this guard; when True it sets all five `analysis.form_score_*` columns to `None` and skips `OverallFormScore.compute` entirely. Frontend already renders `None` as "Not available" cards and hides the overall rating (see `frontend/src/pages/ResultsPage.tsx:123-132` and `:191-203`) so no frontend change is required.

**Tech Stack:** Python 3.12, scipy ≥1.17.1 (already in `backend/pyproject.toml`), numpy, pytest, SQLAlchemy 2.0 async. Agent: `spelix-cv-engineer` owns all backend/app/cv/ changes per root `CLAUDE.md` delegation rules.

**Scope boundary:** This plan does NOT touch `scoring.py::ScoreComponent` subclasses, does NOT add per-dimension degeneracy handling inside `SafetyScore` / `TechniqueScore` / `PathBalanceScore` / `ControlScore` (the pipeline-level guard is the single chokepoint — cleaner than mutating four scorers). The `form_score_*` columns are already `Nullable` in `models/analysis.py:40-44` — no migration needed.

**Related:** ADR-REPDET-01 (decisions.md), FR-CVPL-15, FR-REPM-01, FR-REPM-05, FR-SCOR-02, FR-SCOR-04, FR-SCOR-07. Session 44 handoff §1 "Rep-detection root-cause investigation".

---

## Pre-flight — branch + worktree

- [ ] **Step 0a: Create a feature branch off fresh main**

```bash
cd C:/Users/athar/projects/spelix
git checkout main
git pull
git push origin main   # push session-45 docs commit 02a6207 (unpushed per handoff §5)
git checkout -b fix/d040-d041-rep-detection-and-degenerate-scoring
```

- [ ] **Step 0b: Confirm baseline test counts**

Run: `cd backend && uv run pytest -x -q --ignore=tests/e2e 2>&1 | tail -5`
Expected: `1690 passed, 25 skipped, 0 failed` (baseline from session 44 handoff §3).

Run: `cd frontend && npx vitest run 2>&1 | tail -5`
Expected: `333 passed, 0 failed`.

If any pre-existing failures, STOP and escalate — do NOT start this work on a broken baseline.

---

## File Structure

**Modified:**
- `backend/app/cv/rep_detection.py` — complete rewrite of `detect_reps` + module-level constants. Single responsibility: peak/valley extraction.
- `backend/app/cv/signal_processing.py` — clarifying comment on `_BENCH_*_L` naming (the `_L` suffix is misleading; landmarks 12/14/16/24 are subject's RIGHT per MediaPipe convention). No code change — comment only.
- `backend/app/services/pipeline.py` — add `_is_degenerate_scoring_input` helper (~15 LOC) and conditional short-circuit in Step 9b (~8 LOC).
- `backend/tests/unit/test_rep_detection.py` — delete 8 obsolete state-machine tests (listed in Task 2), update 3 tests whose outcome changes under peak/valley, add 4 new tests for partial-lockout/prominence/distance.
- `backend/tests/unit/test_pipeline.py` — add 2 tests for the degenerate-scoring short-circuit (empty rep_metrics, Very-Low confidence).

**Unchanged but relevant (read before editing):**
- `backend/app/cv/confidence.py:82-108` — `confidence_label` ("Very Low" = `< 0.50`) defines the D-041 threshold boundary.
- `backend/app/cv/scoring.py` — `ScoreComponent` Protocol and four scorers. Do NOT modify.
- `backend/app/models/analysis.py:40-44` — `form_score_*` columns already `Nullable`. No migration.
- `frontend/src/pages/ResultsPage.tsx:108-224` — `FormScoreCards` already handles `null` correctly. No frontend change.

---

## Task 1: Rewrite rep detection with scipy.signal.find_peaks (D-040)

**Files:**
- Modify: `backend/app/cv/rep_detection.py` (full rewrite of `detect_reps` + constants)
- Test: `backend/tests/unit/test_rep_detection.py` (partial rewrite, see Task 2 for test changes)

### Design

- Use `scipy.signal.find_peaks(-angle_timeseries, prominence=P, distance=D)` to find valley indices (rep bottoms). The `-` inverts the signal so valleys become peaks that `find_peaks` can locate.
- For each valley, derive bracketing local maxima:
  - `start_frame = argmax(angle_timeseries[prev_end_frame : valley_idx + 1])` (highest angle between previous rep end and this valley)
  - `end_frame = valley_idx + argmax(angle_timeseries[valley_idx : next_valley_or_end])` (highest angle between this valley and the next valley / signal end)
- Filter reps where `end_frame - start_frame < min_rep_frames` (post-filter for minimum duration, since `find_peaks(distance=...)` enforces distance *between valleys*, not between rep boundaries).
- Per-exercise prominence constants live in `_PROMINENCE_DEG` dict (tuning knob; initial value 20° for all three — calibrate on fixtures in Task 5 Step 6).

- [ ] **Step 1: Replace rep_detection.py module body with peak/valley implementation**

Replace the ENTIRE contents of `backend/app/cv/rep_detection.py` with:

```python
"""
Rep detection via peak/valley extraction for the Spelix CV pipeline.

Implements FR-CVPL-15, FR-REPM-01, FR-REPM-05.

Approach: `scipy.signal.find_peaks` on the inverted primary angle
time-series. Valleys (rep bottoms) are located by a signal-relative
prominence threshold; `start_frame` and `end_frame` are the surrounding
local maxima. No absolute angle thresholds are used — this correctly
handles partial-lockout lifts (bodyweight bench, fatigued reps, RDLs)
that the previous fixed-threshold state machine silently failed on.

All functions are pure — no side effects, no DB, no IO.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks


# ---------------------------------------------------------------------------
# Public types (unchanged API)
# ---------------------------------------------------------------------------


@dataclass
class DetectedRep:
    rep_index: int
    start_frame: int
    end_frame: int
    confidence_score: float
    min_angle: float


# ---------------------------------------------------------------------------
# Tuning knobs
# ---------------------------------------------------------------------------

# Minimum peak prominence (degrees) on the inverted signal — i.e. the
# minimum depth of a valley below its bracketing peaks. Tuned against the
# in-repo fixture library (see plan Task 5 Step 6). Signal-relative, so
# it handles partial-lockout lifts that never reach absolute standing.
# Unknown exercise_type values fall back to 20.0 via dict.get default.
_PROMINENCE_DEG: dict[str, float] = {
    "squat": 20.0,
    "bench": 20.0,
    "deadlift": 20.0,
}

# Minimum rep duration in seconds — applied after peak/valley extraction
# as `end_frame - start_frame >= min_rep_frames`. Prevents spurious
# reps from single-frame noise spikes that slipped through prominence.
_MIN_REP_DURATION_S = 0.5


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------


def detect_reps(
    angle_timeseries: np.ndarray,
    landmarks_per_frame: list[np.ndarray],
    exercise_type: str,
    exercise_variant: str,
    fps: float,
) -> list[DetectedRep]:
    """
    Detect reps from smoothed angle time-series via peak/valley extraction.

    Parameters
    ----------
    angle_timeseries:
        1-D array of smoothed primary angle per frame (degrees).
        For squat/deadlift this is the hip angle; for bench it is the
        elbow angle.
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame. Retained for API compat;
        confidence is computed by pipeline Step 7 (Tier 5).
    exercise_type:
        One of "squat", "bench", "deadlift". Selects the prominence knob.
    exercise_variant:
        Retained for API compat — the peak/valley approach is variant-
        agnostic (old per-variant depth thresholds are gone). Kept in
        the signature so callers in `app/services/pipeline.py` need no
        change.
    fps:
        Frames per second — used for min rep duration filter.

    Returns
    -------
    list[DetectedRep]
        Detected reps with frame ranges, 0.0 placeholder confidence
        (pipeline Step 7 backfills Tier 5), and min_angle at the valley.
    """
    n = len(angle_timeseries)
    if n < 3:
        return []

    prominence = _PROMINENCE_DEG.get(exercise_type.lower(), 20.0)
    min_rep_frames = max(1, int(_MIN_REP_DURATION_S * fps))

    # find_peaks on -angle: peaks of inverted signal = valleys of original
    inverted = -np.asarray(angle_timeseries, dtype=float)
    valley_indices, _ = find_peaks(
        inverted,
        prominence=prominence,
        distance=min_rep_frames,
    )

    if len(valley_indices) == 0:
        return []

    reps: list[DetectedRep] = []
    prev_end = 0
    for i, v_idx in enumerate(valley_indices):
        v_idx_int = int(v_idx)

        # start_frame: argmax in [prev_end, valley]
        start_lo = prev_end
        start_hi = v_idx_int
        if start_hi <= start_lo:
            start_frame = start_lo
        else:
            start_frame = start_lo + int(np.argmax(angle_timeseries[start_lo : start_hi + 1]))

        # end_frame: argmax in [valley, next_valley_or_signal_end]
        if i + 1 < len(valley_indices):
            end_hi = int(valley_indices[i + 1])
        else:
            end_hi = n - 1
        if end_hi <= v_idx_int:
            end_frame = v_idx_int
        else:
            end_frame = v_idx_int + int(
                np.argmax(angle_timeseries[v_idx_int : end_hi + 1])
            )

        # Min-duration post-filter. Advance prev_end ONLY on kept reps —
        # if a valley is filtered here, the next rep's start-frame search
        # window correctly extends back across the filtered region and
        # argmax still lands on the highest intermediate peak (or earlier).
        if end_frame - start_frame >= min_rep_frames:
            reps.append(
                DetectedRep(
                    rep_index=len(reps),
                    start_frame=start_frame,
                    end_frame=end_frame,
                    confidence_score=0.0,
                    min_angle=float(angle_timeseries[v_idx_int]),
                )
            )
            prev_end = end_frame

    return reps
```

- [ ] **Step 2: Run the test file to confirm expected failures/passes against the new implementation**

Run: `cd backend && uv run pytest tests/unit/test_rep_detection.py -v 2>&1 | tail -60`

Expected: the majority of tests will pass because large-amplitude synthetic reps (170°→75° = 95° drop) easily exceed the 20° prominence knob. A handful will FAIL because they encoded the old state-machine behavior. Record the failing test names — those are the ones Task 2 must surgically update. Do NOT mass-delete.

- [ ] **Step 3: Commit Task 1**

```bash
cd C:/Users/athar/projects/spelix
git add backend/app/cv/rep_detection.py
git commit -m "$(cat <<'EOF'
refactor(cv): replace rep-detection state machine with scipy.signal.find_peaks

Peak/valley extraction via find_peaks on the inverted primary-angle
timeseries. Signal-relative prominence knob (20°) handles partial-lockout
lifts (bodyweight bench, fatigued reps, RDLs) that the fixed-threshold
state machine silently failed on — see session 44 E2E cea2312b which
returned 0 reps despite ~3 clean rep cycles at peak 152.97° never
crossing the 160° STANDING threshold.

Removes _STANDING_THRESHOLD, _DEPTH_THRESHOLD, _HYSTERESIS_DEG dicts
and the RepState enum. Preserves detect_reps() signature so no call-
site changes; exercise_variant becomes unused (documented).

Tests updated in follow-up commit.

Refs: ADR-REPDET-01, FR-CVPL-15, FR-REPM-01, FR-REPM-05, D-040.
EOF
)"
```

---

## Task 2: Update test_rep_detection.py for the new semantics

**Files:**
- Modify: `backend/tests/unit/test_rep_detection.py`

### Test-level changes

The state-machine tests use synthetic trapezoid signals (170°→75°→170°) that produce ~95° prominence under peak/valley detection, so most still pass. Only tests that encoded specific *threshold* behavior (partial depth not counted, per-variant thresholds, hysteresis near threshold) need updating.

**Obsolete tests to DELETE** (encoded the old state machine's absolute-threshold behavior — these are the bug, not the spec):

1. `TestBenchStateCycle::test_insufficient_depth_not_counted` — 170°→95° is a 75° prominence rep under new algorithm.
2. `TestDeadliftStateCycle::test_rdl_vs_conventional_same_data_different_counts` — no more per-variant depth thresholds.
3. `TestDeadliftStateCycle::test_conventional_angle_70_to_90_not_counted` — 170°→75° is now a rep.
4. `TestHysteresis::test_chatter_near_depth_threshold_squat` — tightly bound to old hysteresis semantics.
5. `TestZeroRepAndPartialRep::test_zero_rep_never_reaches_depth` — 170°→120° is a 50° prominence rep now.
6. `TestZeroRepAndPartialRep::test_zero_rep_signal_aborted_before_depth` — 170°→130°→175° is a 45° prominence rep now.
7. `TestSquatThresholdFix::test_quarter_squat_not_detected` — quarter squats ARE reps under peak/valley; form scoring (TechniqueScore) catches insufficient depth, not rep detection.
8. `TestSquatThresholdFix::test_bench_and_deadlift_thresholds_unchanged` — no more thresholds to test.

**Tests whose outcome changes** (must be updated):

9. `TestHysteresis::test_chatter_near_standing_threshold_squat` — rename to `test_low_amplitude_noise_no_reps`, change base from `160.0` → `120.0` (base is arbitrary under peak/valley — 120° reads cleanly as mid-range noise rather than carrying vestigial "near STANDING threshold" context), keep amplitude `6.0` (total peak-to-trough 12° < 20° prominence → still 0 reps). Reword docstring to describe prominence filtering, not hysteresis. Concrete edit:

```python
def test_low_amplitude_noise_no_reps(self):
    """
    ±6° sinusoidal noise (total peak-to-trough 12°) around an arbitrary
    mid-range base is below the 20° prominence knob → 0 reps. Replaces
    the legacy "chatter near STANDING threshold" test — thresholds no
    longer exist under peak/valley detection.
    """
    angles = self._chattering_signal(base=120.0, amplitude=6.0)
    landmarks = _make_landmarks(len(angles))
    reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
    assert len(reps) == 0
```
10. `TestZeroRepAndPartialRep::test_partial_rep_descent_only_no_return` — 170°→70°→100° (video ends mid-ascent). find_peaks with prominence=20° WILL detect this valley (right-side prominence is 30°). Update expected count from `0` to `1`, and update the docstring to note that peak/valley counts any valley with sufficient prominence regardless of whether lockout was reached.
11. `TestZeroRepAndPartialRep::test_partial_rep_does_not_corrupt_subsequent_full_rep` — the first "partial" attempt (170°→130°→175°) now has 45° prominence and IS detected. Update expected count from `1` to `2`, and update the docstring.

**Tests to KEEP unchanged** (all verified compatible):
- All `TestSquatStateCycle` tests (large-amplitude trapezoids)
- All other `TestBenchStateCycle`, `TestDeadliftStateCycle` tests (using 170°→75°)
- `TestHysteresis::test_clear_depth_after_hysteresis_band` — 170°→80° is clearly detectable
- `TestMinRepDuration::*` (post-filter still enforced)
- `TestEdgeCases::*` (empty / flat signals)
- `TestConfidenceScore::*` (confidence is still a 0.0 placeholder backfilled by Step 7)
- `TestDetectedRepFields::*`
- `TestZeroRepAndPartialRep` tests that remain: `test_zero_rep_constant_standing_angle`, `test_zero_rep_single_frame_at_standing`, `test_zero_rep_two_frames`, `test_zero_rep_empty_signal`, `test_zero_rep_all_exercises_no_movement`, `test_partial_rep_reaches_bottom_but_signal_ends` (no ascent → prominence on right side is ≤0 → 0 reps), `test_partial_rep_too_short_duration_not_counted` (caught by min-duration post-filter)
- `TestSquatThresholdFix::test_parallel_depth_squat_detected` — 165°→95° = 70° prominence → keeps passing
- `TestSquatThresholdFix::test_six_parallel_depth_reps_all_detected` — same
- `TestSquatThresholdFix::test_incomplete_lockout_rep_still_counted` — 160°→80°→147° has large prominence → keeps passing

**New tests to ADD:**

12. `test_partial_lockout_bench_rep_detected` — the regression fixture from the session 44 E2E. Signal: synthetic bench signal where elbow peaks at 153° (not 170°) and drops to 37°. Must count ≥ 1 rep.
13. `test_prominence_filters_low_amplitude_noise` — a large-baseline signal with ±8° sinusoidal noise must yield 0 reps.
14. `test_min_distance_merges_adjacent_valleys` — two valleys 10 frames apart (< 15-frame minimum at 30fps) must not double-count.
15. `test_start_end_frames_bracket_valley` — for any detected rep, assert `start_frame <= valley_frame <= end_frame` AND `angle[start_frame] >= angle[valley_frame]` AND `angle[end_frame] >= angle[valley_frame]`.

- [ ] **Step 1: Apply test-file edits**

For each of the 8 "delete" tests above, REMOVE the test function from the class. For each of the 3 "update" tests, apply the edit described. Keep class-level structure so test discovery doesn't shuffle.

Then append a new top-level class to the bottom of the file:

```python
# ---------------------------------------------------------------------------
# 11. D-040 peak/valley regression coverage
# ---------------------------------------------------------------------------


class TestPeakValleyDetection:
    """New tests for signal-relative rep detection (D-040, ADR-REPDET-01)."""

    def test_partial_lockout_bench_rep_detected(self):
        """
        Bench signal where elbow peaks at 153° (not full 170°+ lockout)
        and descends to 37° must count as a rep — this is the session 44
        cea2312b regression (0 reps under old 160° STANDING threshold).
        """
        # 30 fps synthetic: 45-frame standing at 153°, 30-frame descent
        # to 37°, 30-frame ascent back to 153°.
        stand1 = np.full(45, 153.0)
        descend = np.linspace(153.0, 37.0, 30)
        ascend = np.linspace(37.0, 153.0, 30)
        stand2 = np.full(45, 153.0)
        angles = np.concatenate([stand1, descend, ascend, stand2])
        landmarks = _make_landmarks(len(angles))

        reps = detect_reps(angles, landmarks, "bench", "flat", FPS)

        assert len(reps) == 1, (
            f"Partial-lockout bench rep (peak 153°, valley 37°) must be "
            f"detected. Got {len(reps)} reps."
        )
        # Min angle should be at / near the valley
        assert reps[0].min_angle < 40.0

    def test_prominence_filters_low_amplitude_noise(self):
        """
        A baseline-90° signal with ±8° sinusoidal noise (total amplitude
        16°) must yield 0 reps — below the 20° prominence knob.
        """
        t = np.arange(120)
        angles = 90.0 + 8.0 * np.sin(2 * np.pi * t / 20)
        landmarks = _make_landmarks(len(angles))

        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)

        assert reps == [], (
            f"Low-amplitude noise (±8°) must not produce reps. "
            f"Got {len(reps)}."
        )

    def test_min_distance_merges_adjacent_valleys(self):
        """
        Two valleys 10 frames apart at 30 fps (= 0.33 s, below the
        0.5 s / 15-frame minimum) must be treated as at most one rep.
        """
        # Two sharp valleys at frames 20 and 30 (10 apart)
        angles = np.full(60, 170.0)
        angles[20] = 80.0
        angles[30] = 80.0
        # Smooth a bit so find_peaks sees them as distinct valleys
        angles[19:22] = [140.0, 80.0, 140.0]
        angles[29:32] = [140.0, 80.0, 140.0]
        landmarks = _make_landmarks(len(angles))

        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)

        assert len(reps) <= 1, (
            f"Two valleys 10 frames apart must not yield 2 reps "
            f"(distance filter = 15 frames at 30 fps). Got {len(reps)}."
        )

    def test_start_end_frames_bracket_valley(self):
        """
        For any detected rep, start_frame and end_frame must bracket a
        local maximum surrounding the valley — angle at start and end
        must be >= angle at the valley-ish midpoint.
        """
        angles = _squat_rep_angles(n_reps=2)
        landmarks = _make_landmarks(len(angles))

        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert len(reps) == 2

        for rep in reps:
            # Min angle within the rep window should equal rep.min_angle
            window = angles[rep.start_frame : rep.end_frame + 1]
            assert float(window.min()) <= rep.min_angle + 0.5
            # Bracketing peaks: start and end angles must exceed min_angle
            assert angles[rep.start_frame] > rep.min_angle
            assert angles[rep.end_frame] > rep.min_angle
```

- [ ] **Step 2: Run the full test file to confirm all tests pass**

Run: `cd backend && uv run pytest tests/unit/test_rep_detection.py -v 2>&1 | tail -40`
Expected: all tests in the file PASS. Record the new count (should be baseline − 8 deleted + 4 added = baseline − 4 net).

If ANY test fails: STOP, re-read the failing test's assertion against the new algorithm semantics. If the test encodes a genuine bug in the new implementation, fix `rep_detection.py`. If the test encodes obsolete behavior, delete it (only after confirming ADR-REPDET-01 covers the case).

- [ ] **Step 3: Commit Task 2**

```bash
cd C:/Users/athar/projects/spelix
git add backend/tests/unit/test_rep_detection.py
git commit -m "$(cat <<'EOF'
test(cv): update rep-detection tests for peak/valley semantics

- Delete 8 tests that encoded absolute-threshold / per-variant-depth
  state-machine behavior (the bug, not the spec).
- Update 3 tests whose correct outcome changes under peak/valley
  (partial-rep descent-only now counts; chatter test re-scoped to
  prominence filtering).
- Add 4 new tests for D-040: partial-lockout bench regression
  (session 44 cea2312b at peak 153°), prominence filters low-amplitude
  noise, distance filter merges adjacent valleys, start/end frames
  bracket the valley.

Refs: ADR-REPDET-01, D-040.
EOF
)"
```

---

## Task 3: Clarifying comment on `_BENCH_*_L` landmark names

**Files:**
- Modify: `backend/app/cv/signal_processing.py` (comment only, no code change)

The `_BENCH_*_L` naming was confusing during session 44's root-cause investigation — the `_L` suffix comes from the task spec's "even indices" convention but refers to MediaPipe landmark *index* parity, not body side. MediaPipe's `14 = right_elbow`, `12 = right_shoulder`, `16 = right_wrist`, `24 = right_hip` — all subject's RIGHT.

A full rename (`_L` → `_RIGHT`) would touch many call sites and add diff risk; per CLAUDE.md "A bug fix doesn't need surrounding cleanup" we keep the names and add a clarifying comment only.

- [ ] **Step 1: Add clarifying comment above the bench landmark constants**

Edit `backend/app/cv/signal_processing.py` to replace the comment block just above `_BENCH_SHOULDER_L = 12` (currently line 42) with:

```python
# Bench — subject's RIGHT side (task spec "even indices" convention).
# MediaPipe BlazePose indices 12/14/16/24 correspond to the subject's
# right shoulder/elbow/wrist/hip. The `_L` suffix is a spec-convention
# artefact, NOT a body-side indicator. Session 44 ADR-REPDET-01
# investigation hit this confusion — leaving the names for minimal
# diff risk; DO NOT assume "_L" means the subject's left.
_BENCH_SHOULDER_L = 12
_BENCH_ELBOW_L = 14
_BENCH_WRIST_L = 16
_BENCH_HIP_L = 24  # for shoulder_angle: shoulder–hip vector
```

- [ ] **Step 2: No test required (comment-only change). Run ruff + pyright to confirm no accidental syntax break**

Run: `cd backend && uv run ruff check app/cv/signal_processing.py && uv run pyright app/cv/signal_processing.py 2>&1 | tail -5`
Expected: `All checks passed` from ruff and `0 errors` from pyright.

- [ ] **Step 3: Commit Task 3**

```bash
cd C:/Users/athar/projects/spelix
git add backend/app/cv/signal_processing.py
git commit -m "$(cat <<'EOF'
docs(cv): clarify _BENCH_*_L landmark names are subject-right

The `_L` suffix comes from the task spec's "even indices" convention
and does NOT indicate body side — MediaPipe's 12/14/16/24 are the
subject's right shoulder/elbow/wrist/hip. Session 44 ADR-REPDET-01
root-cause investigation hit this confusion.

Comment-only; no code change.
EOF
)"
```

---

## Task 4: Degenerate scoring short-circuit (D-041)

**Files:**
- Modify: `backend/app/services/pipeline.py` — add `_is_degenerate_scoring_input` helper + conditional branch in Step 9b
- Test: `backend/tests/unit/test_pipeline.py` — add 2 integration tests for the guard

### Design

- Threshold: `session_confidence < 0.50` matches the `Very Low` boundary in `backend/app/cv/confidence.py::confidence_label` (line 107-108). Using the same numeric constant keeps UI and scoring aligned — if users see "Very Low confidence" they see "Not available" scores, and the contradiction from session 44 (Technique 10.0 + "Very Low / Unable to score reliably") disappears.
- Empty `rep_metrics` always triggers degeneracy regardless of session_confidence (there's literally nothing to score).
- `analysis.form_score_*` nullable columns mean `None` is a valid DB value; no migration needed.
- `OverallFormScore.compute` is skipped entirely (not called with empty dict) — avoids any downstream expectation that a `ScoreResult` was produced.
- `result.score_result` on `PipelineResult` stays at its default `None` (confirmed at `pipeline.py:120 self.score_result: Any = None`). Verified via grep (`rg "\.score_result" backend/app`): the ONLY writers/readers live inside `pipeline.py` itself — no summary service, PDF generator, or schema layer consumes it externally. The degenerate branch safely leaves it `None`.
- `_aggregate_rep_metrics` is also skipped inside the `else` branch — when degenerate we never compute means-of-nothing.

- [ ] **Step 1: Write failing tests first**

Open `backend/tests/unit/test_pipeline.py` and append these two test functions at the end of the file (keep the existing test patterns — `patch(f"{_PKG}.detect_reps", ...)`, AsyncMock repos, etc. — see lines 174-200 for the canonical harness):

```python
# ---------------------------------------------------------------------------
# D-041: Degenerate scoring short-circuit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_form_scores_set_to_none_when_rep_metrics_empty():
    """
    When detect_reps returns [] and therefore rep_metrics is [], all five
    analysis.form_score_* columns must be set to None — NOT defaulted to
    10.0 by scoring components on empty input (D-041).
    """
    landmarks = _make_landmarks()
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=[]),
        patch(f"{_PKG}.extract_rep_metrics", return_value=[]),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.0),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=None),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    assert analysis.form_score_safety is None
    assert analysis.form_score_technique is None
    assert analysis.form_score_path_balance is None
    assert analysis.form_score_control is None
    assert analysis.form_score_overall is None


@pytest.mark.asyncio
async def test_form_scores_set_to_none_when_session_confidence_below_050():
    """
    When session confidence is below the Very-Low boundary (0.50), form
    scores must be None — prevents the session 44 contradiction where
    "Very Low confidence" banner rendered alongside Technique 10.0 (D-041).
    """
    landmarks = _make_landmarks()
    angle_ts = _make_angle_timeseries()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.35),  # Very Low
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=None),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    assert analysis.form_score_safety is None
    assert analysis.form_score_technique is None
    assert analysis.form_score_path_balance is None
    assert analysis.form_score_control is None
    assert analysis.form_score_overall is None
```

Also add a pure-function unit test for the guard itself, independent of the full pipeline:

```python
# ---------------------------------------------------------------------------
# D-041: Pure-function guard
# ---------------------------------------------------------------------------


def test_is_degenerate_scoring_input_empty_metrics():
    from app.services.pipeline import _is_degenerate_scoring_input
    assert _is_degenerate_scoring_input([], 0.9) is True


def test_is_degenerate_scoring_input_very_low_confidence():
    from app.services.pipeline import _is_degenerate_scoring_input
    # Non-empty list content doesn't matter — the guard is list emptiness + threshold
    assert _is_degenerate_scoring_input([object()], 0.49) is True


def test_is_degenerate_scoring_input_boundary_050_not_degenerate():
    """0.50 is the Low boundary — at-or-above Low is NOT degenerate."""
    from app.services.pipeline import _is_degenerate_scoring_input
    assert _is_degenerate_scoring_input([object()], 0.50) is False


def test_is_degenerate_scoring_input_good_input():
    from app.services.pipeline import _is_degenerate_scoring_input
    assert _is_degenerate_scoring_input([object()], 0.85) is False
```

- [ ] **Step 2: Run the new tests to verify they fail against current pipeline**

Run: `cd backend && uv run pytest tests/unit/test_pipeline.py::test_form_scores_set_to_none_when_rep_metrics_empty tests/unit/test_pipeline.py::test_form_scores_set_to_none_when_session_confidence_below_050 tests/unit/test_pipeline.py::test_is_degenerate_scoring_input_empty_metrics -v 2>&1 | tail -20`

Expected: ALL four new tests FAIL. The pure-function tests fail with `ImportError: cannot import name '_is_degenerate_scoring_input'`. The pipeline tests fail because current code sets `analysis.form_score_safety` etc. from `score_result.get_dimension(...)` which returns numeric scores (10.0 defaults) regardless of empty input.

- [ ] **Step 3: Implement the guard + short-circuit in pipeline.py**

Edit `backend/app/services/pipeline.py`. Add the guard helper directly above `_aggregate_rep_metrics` (around line 169):

```python
# ---------------------------------------------------------------------------
# D-041: Degenerate scoring-input guard
# ---------------------------------------------------------------------------

# Matches the "Very Low" boundary in app.cv.confidence.confidence_label —
# below this the UI already tells the user scores are unreliable, so
# returning numeric scores (which otherwise default to 10.0 on empty or
# low-quality input) is a trust-violating contradiction.
_DEGENERATE_CONFIDENCE_THRESHOLD = 0.50


def _is_degenerate_scoring_input(
    rep_metrics: list,
    session_confidence: float,
) -> bool:
    """
    Return True when the scoring pipeline has no useful signal.

    Degenerate when:
    - `rep_metrics` is empty (nothing to score), OR
    - `session_confidence < 0.50` (per-rep Tier 5 aggregation below
      the "Very Low" UI boundary — scores would be unreliable).

    Callers set `analysis.form_score_*` to None and skip
    `OverallFormScore.compute` entirely. Frontend FormScoreCards
    already renders None as "Not available" (ResultsPage.tsx:191).
    """
    if not rep_metrics:
        return True
    if session_confidence < _DEGENERATE_CONFIDENCE_THRESHOLD:
        return True
    return False
```

Then modify Step 9b (currently at `backend/app/services/pipeline.py:677-699`). Replace the block:

```python
    # ------------------------------------------------------------------ #
    # Step 9b: Form scoring (FR-SCOR-01–08) — needs bar_path from Step 9
    # ------------------------------------------------------------------ #
    from app.cv.scoring import OverallFormScore

    with timer.stage("form_scoring"):
        scorer = OverallFormScore()
        # Aggregate per-rep metrics into a single dict (mean across reps)
        agg_metrics = _aggregate_rep_metrics(rep_metrics, reps, session_confidence)
        score_result = scorer.compute(agg_metrics, bar_path, cfg, exercise_type)
    result.score_result = score_result

    # Write form scores to analysis row
    safety_dim = score_result.get_dimension("safety")
    technique_dim = score_result.get_dimension("technique")
    path_dim = score_result.get_dimension("path_balance")
    control_dim = score_result.get_dimension("control")

    analysis.form_score_safety = safety_dim.score if safety_dim else None
    analysis.form_score_technique = technique_dim.score if technique_dim else None
    analysis.form_score_path_balance = path_dim.score if path_dim else None
    analysis.form_score_control = control_dim.score if control_dim else None
    analysis.form_score_overall = score_result.overall
```

with:

```python
    # ------------------------------------------------------------------ #
    # Step 9b: Form scoring (FR-SCOR-01–08) — needs bar_path from Step 9
    #
    # D-041: Short-circuit on degenerate input (no reps OR session
    # confidence below the "Very Low" boundary). Writes None to all
    # five form_score_* columns instead of letting scorers default to
    # 10.0 on empty input. Frontend renders None as "Not available".
    # ------------------------------------------------------------------ #
    if _is_degenerate_scoring_input(rep_metrics, session_confidence):
        analysis.form_score_safety = None
        analysis.form_score_technique = None
        analysis.form_score_path_balance = None
        analysis.form_score_control = None
        analysis.form_score_overall = None
    else:
        from app.cv.scoring import OverallFormScore

        with timer.stage("form_scoring"):
            scorer = OverallFormScore()
            # Aggregate per-rep metrics into a single dict (mean across reps)
            agg_metrics = _aggregate_rep_metrics(rep_metrics, reps, session_confidence)
            score_result = scorer.compute(agg_metrics, bar_path, cfg, exercise_type)
        result.score_result = score_result

        # Write form scores to analysis row
        safety_dim = score_result.get_dimension("safety")
        technique_dim = score_result.get_dimension("technique")
        path_dim = score_result.get_dimension("path_balance")
        control_dim = score_result.get_dimension("control")

        analysis.form_score_safety = safety_dim.score if safety_dim else None
        analysis.form_score_technique = technique_dim.score if technique_dim else None
        analysis.form_score_path_balance = path_dim.score if path_dim else None
        analysis.form_score_control = control_dim.score if control_dim else None
        analysis.form_score_overall = score_result.overall
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_pipeline.py -k "degenerate or form_scores_set_to_none" -v 2>&1 | tail -20`
Expected: all 6 new tests PASS (2 integration + 4 pure-function).

- [ ] **Step 5: Run the full test_pipeline.py to verify no regressions**

Run: `cd backend && uv run pytest tests/unit/test_pipeline.py -v 2>&1 | tail -15`
Expected: all tests pass. The existing `test_no_reps_skips_batch_insert` should still pass (it already asserts `rep_metrics == []` doesn't crash; our change makes that path write None to form_score_* which is additive, not regressive).

- [ ] **Step 6: Commit Task 4**

```bash
cd C:/Users/athar/projects/spelix
git add backend/app/services/pipeline.py backend/tests/unit/test_pipeline.py
git commit -m "$(cat <<'EOF'
fix(cv): write None form-scores on degenerate scoring input

Adds _is_degenerate_scoring_input() guard in pipeline Step 9b: when
rep_metrics is empty OR session_confidence < 0.50 (the "Very Low" UI
boundary per confidence_label), all five analysis.form_score_* columns
are set to None and OverallFormScore.compute is skipped entirely.

Fixes the session 44 cea2312b trust-violating contradiction where
"Very Low confidence / Unable to score reliably" rendered alongside
Technique 10.0 / Control 10.0 (scorers defaulted to max on empty
input). Frontend FormScoreCards (ResultsPage.tsx) already renders
None as "Not available" cards and hides the overall rating — no
frontend change needed.

Refs: ADR-REPDET-01, D-041, FR-SCOR-02, FR-SCOR-04, FR-SCOR-07.
EOF
)"
```

---

## Task 5: Full local verification sweep

- [ ] **Step 1: Run entire backend test suite**

Run: `cd backend && uv run pytest -x -q --ignore=tests/e2e 2>&1 | tail -5`
Expected: `1692 passed` — baseline 1690 − 8 deleted rep-detection tests + 4 new rep-detection tests + 6 new pipeline tests (2 integration + 4 pure-function). Allow ±2 for edge cases. 0 failures.

If failures: the prime suspects are downstream tests that asserted specific rep counts or specific form scores on fixtures — update those to reflect the new counts (rep counts will INCREASE for partial-lockout fixtures; form scores will become None for degenerate cases).

- [ ] **Step 2: Run ruff + pyright**

Run: `cd backend && uv run ruff check . && uv run pyright app/ 2>&1 | tail -5`
Expected: ruff clean; pyright `0 errors, 0 warnings, 0 informations`.

- [ ] **Step 3: Run frontend test suite (no changes expected but verify no indirect breakage)**

Run: `cd frontend && npx vitest run 2>&1 | tail -5 && npx tsc --noEmit`
Expected: `333 passed` (unchanged). tsc: 0 errors.

- [ ] **Step 4: Local pipeline smoke test against the cea2312b regression fixture**

This is the critical behavioral validation. Re-run the CV pipeline against `e2e/fixtures/atharva-bench-nw-10s-720p.mp4` (the fixture from session 44 E2E that returned 0 reps on prod) using the local worker.

There is no existing script to do this end-to-end locally without a full DB/Redis stack. Two options:

**Option A (simpler) — pure-function smoke:** write a throwaway script that loads the fixture, runs pose extraction + `compute_angle_timeseries` + `detect_reps`, and prints the rep count. This validates the D-040 fix deterministically.

Create `backend/scripts/oneoff/smoke_rep_detection_d040.py`:

```python
"""D-040 smoke test: verify rep count on partial-lockout bench fixture.

Deletable after the D-040/D-041 PR merges. Runs pose extraction and
rep detection against the session 44 regression fixture and prints
the rep count — must be > 0 after D-040 (was 0 before).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure `app.*` is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.cv.pose_extraction import extract_landmarks  # noqa: E402
from app.cv.rep_detection import detect_reps  # noqa: E402
from app.cv.signal_processing import compute_angle_timeseries  # noqa: E402


FIXTURE = Path(__file__).parent.parent.parent.parent / "e2e" / "fixtures" / "atharva-bench-nw-10s-720p.mp4"


def main() -> int:
    if not FIXTURE.exists():
        print(f"Fixture not found: {FIXTURE}")
        return 1

    # extract_landmarks returns (landmarks_per_frame, fps, width, height)
    landmarks_per_frame, fps, _, _ = extract_landmarks(str(FIXTURE))
    print(f"Frames: {len(landmarks_per_frame)}, FPS: {fps:.1f}")

    angle_ts = compute_angle_timeseries(landmarks_per_frame, "bench")
    elbow = angle_ts["elbow_angle"]
    print(f"Elbow angle min/max/mean: {elbow.min():.1f} / {elbow.max():.1f} / {elbow.mean():.1f}")

    reps = detect_reps(elbow, landmarks_per_frame, "bench", "flat", fps)
    print(f"Detected reps: {len(reps)}")
    for rep in reps:
        print(
            f"  rep {rep.rep_index}: frames {rep.start_frame}..{rep.end_frame}, "
            f"min_angle {rep.min_angle:.1f}"
        )

    if len(reps) == 0:
        print("FAIL: D-040 fix ineffective — got 0 reps on partial-lockout fixture")
        return 1
    print("PASS: rep count > 0 on partial-lockout bench fixture")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Run: `cd backend && uv run python scripts/oneoff/smoke_rep_detection_d040.py`

Expected output: a `Detected reps: N` line with N ≥ 2 (fixture has ~3 rep cycles per session 44 handoff). Elbow min/max line should roughly match session 44's measured 37.7°/152.97°/106.8°. If N == 0: the D-040 fix is ineffective — debug prominence or distance.

**Option B (tedious) — full local pipeline:** requires running Redis, the FastAPI app, and the streaq worker locally, then uploading through the frontend. Skip unless Option A raises unexpected issues.

- [ ] **Step 5: Commit the smoke script**

```bash
cd C:/Users/athar/projects/spelix
git add backend/scripts/oneoff/smoke_rep_detection_d040.py
git commit -m "$(cat <<'EOF'
chore(cv): add D-040 smoke script for partial-lockout bench fixture

Runs pose extraction + rep detection against the session 44 cea2312b
regression fixture. Prints rep count — must be > 0 post-D-040.
Deletable after the D-040/D-041 PR merges.
EOF
)"
```

- [ ] **Step 6: Hand-count fixtures and note any test-expectation drift**

For each fixture below, inspect the video in a media player, hand-count reps, then run the smoke script adapted for that fixture (change FIXTURE + exercise_type + primary angle key):

| Fixture | Exercise | Hand count | Script count |
|---|---|---|---|
| `atharva-bench-nw-10s-720p.mp4` | bench | (read from media player) | (script output) |
| `atharva-bench-no-weight.mov` | bench | _ | _ |
| `atharva-bench.mov` | bench (loaded) | _ | _ |
| `atharva-squat.mov` | squat | _ | _ |
| `atharva-deadlift.mov` | deadlift | _ | _ |

Record hand vs. script counts in the PR description. If script over-counts (e.g. noise spikes → phantom reps), increase the `_PROMINENCE_DEG` value for that exercise. If script under-counts real reps, decrease prominence OR increase the `_MIN_REP_DURATION_S`. Commit the final prominence values as an amendment to the Task 1 commit (or a separate calibration commit) — document in the PR description that these values came from hand-counted ground truth.

- [ ] **Step 7: If prominence tuning required, amend**

If Step 6 shows miscount on any fixture, adjust `_PROMINENCE_DEG` in `rep_detection.py` and re-run the smoke script + full test suite. Commit as:

```bash
git commit -m "tune(cv): calibrate _PROMINENCE_DEG against hand-counted fixtures (D-040)"
```

---

## Task 6: PR + CI + Merge + Prod Verification

- [ ] **Step 1: Push the branch**

```bash
cd C:/Users/athar/projects/spelix
git push -u origin fix/d040-d041-rep-detection-and-degenerate-scoring
```

- [ ] **Step 2: Open PR via GitHub MCP**

Use `mcp__github__create_pull_request` with:
- Title: `fix(cv): peak/valley rep detection + degenerate scoring fix (D-040, D-041)`
- Base: `main`
- Head: `fix/d040-d041-rep-detection-and-degenerate-scoring`
- Body: include ADR-REPDET-01 reference, the fixture hand-count table from Task 5 Step 6, and the screenshot-link placeholder for prod E2E.

- [ ] **Step 3: Wait for CI to be green**

Use `mcp__github__get_pull_request_status` until all 5 checks pass (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning) + Vercel preview green. Do NOT merge before all green.

- [ ] **Step 4: Run spelix-auditor and spelix-security-reviewer**

Launch both specialists against the PR diff. Any HIGH findings must be fixed before merge; MEDIUM findings captured as D-### follow-ups if non-blocking.

Specifically check: (a) no banned SaMD language introduced (D-041 doesn't touch user-facing strings but re-verify), (b) no new dangling secrets, (c) no regression in ownership guards.

- [ ] **Step 5: Merge via MCP (merge commit, NOT squash)**

Use `mcp__github__merge_pull_request` with `merge_method: "merge"`. CLAUDE.md rule: never squash — squash causes main divergence that requires recovery.

- [ ] **Step 6: Wait for "Deploy to Production" CI step**

```bash
gh pr checks --watch  # stream until Deploy to Production is green
ssh spelix-droplet "git log --oneline -1 && docker ps --format '{{.Names}} {{.Status}}'"
```

Expected: droplet HEAD matches merge commit; all containers `(healthy)`.

- [ ] **Step 7: E2E verification against prod**

This is the authoritative D-040/D-041 fix confirmation.

1. `mcp__playwright__browser_navigate` → `https://spelix.app`
2. Log in as admin: `atharva6905+admin-p3006@gmail.com` / `SpelixAdmin-P3006-Test-2026!`
3. Upload `e2e/fixtures/atharva-bench-nw-10s-720p.mp4` with exercise_type=bench, variant=flat
4. Wait for pipeline completion (~3 minutes)
5. On ResultsPage, verify:
   - **Rep count ≥ 1** (was 0 in session 44) — visible in the summary header and/or rep metrics table
   - **Form scores either all populated with realistic values OR all showing "Not available"** — never 10.0/10.0 alongside "Very Low confidence"
   - If confidence label is "Very Low": FormScoreCards shows "Not available" for all four dimensions (D-041 verified)
   - If confidence label is Low/Moderate/High: scores are numeric and reasonable (D-041 passthrough)
6. Take screenshot → save to `e2e/screenshots/d040-d041-post-fix-verified.png`
7. `browser_console_messages` level=error: 0 errors
8. `browser_network_requests` filter 4xx/5xx: 0 failures

If any check fails: do NOT mark task complete. Open a new branch, investigate (prominence calibration? confidence threshold off?), fix, ship in follow-up PR.

- [ ] **Step 8: Update handoff + backlog + decisions**

- Append a "Completed — 2026-04-18" section to `backlog.md` with D-040 and D-041 marked `done` + merge SHA.
- Write session 45 handoff to `.claude/handoff.md` covering: commits, test counts, E2E screenshot link, any calibration notes from Task 5 Step 6, next priority (Priority 2 non-code blockers or Priority 3 M-04/M-05).
- No new ADR needed (ADR-REPDET-01 already covers the decision).

- [ ] **Step 9: Delete the smoke script if prominence calibration produced stable results**

`backend/scripts/oneoff/smoke_rep_detection_d040.py` is a dev aid — if fixture counts were stable and prominence required no tuning, delete it in a follow-up commit. If prominence needed tuning, keep the script around for future re-calibration and move it to `backend/scripts/` (non-oneoff).

---

## Self-Review Notes

**Spec coverage:**
- FR-CVPL-15 (rep detection): Task 1 implements via `find_peaks`. Tests in Task 2.
- FR-REPM-01 (rep-by-rep metrics): signature preserved; call-sites in `pipeline.py::Step 6` unchanged.
- FR-REPM-05 (single-rep videos): explicitly tested (`TestSquatStateCycle::test_single_rep_detected`, new `test_partial_lockout_bench_rep_detected`).
- FR-SCOR-02 / FR-SCOR-04 / FR-SCOR-07 (technique/control/descriptor): Task 4 guards against degenerate input at the pipeline level, leaving the scorers untouched (no spec violation).
- ADR-REPDET-01 rationale: peak/valley replaces absolute thresholds — covered by Tasks 1–2.

**Placeholder scan:** no `TBD`/`TODO`/`fill in`/"handle edge cases" — every step contains code or commands.

**Type consistency:** `DetectedRep` fields (`rep_index`, `start_frame`, `end_frame`, `confidence_score`, `min_angle`) unchanged from current implementation. `_is_degenerate_scoring_input(rep_metrics: list, session_confidence: float) -> bool` — type spelled the same in the implementation (Step 3 of Task 4) and the pure-function test (Step 1 of Task 4).

**Known non-trivial risk:** prominence knob default of 20° is an educated initial guess. Task 5 Step 6's hand-counted fixture calibration is mandatory — ship with whatever value produces correct counts on the ground-truth library, not 20° by fiat. If no fixture exposes a miscount at 20°, ship 20° and document that it held on N fixtures.

**Frontend impact check:** `ResultsPage.tsx:108-224` FormScoreCards already handles null per-dimension ("Not available" card, line 191-203) AND hides the overall rating block when all five are null (lines 123-132). No frontend change needed. Verified manually in `/results/cea2312b-...` flow plan is what the code actually does — see `frontend/src/pages/ResultsPage.tsx` path references in File Structure.

**Rollback path:** if post-merge prod verification reveals false positives (over-counting phantom reps), increase `_PROMINENCE_DEG` values and ship a follow-up calibration commit. The state-machine code is gone from the branch but recoverable from git history if a full revert is needed (`git revert <merge-commit>`).
