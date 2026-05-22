# Session 2 — Lifter-Side Detection + Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add side-agnostic landmark access. All existing metrics and all future Part 2 metrics route through a single helper that detects the lifter's filmed side per analysis and picks the correct MediaPipe landmark indices.

**Architecture:** New `backend/app/cv/lifter_side.py` exports `detect_lifter_side()` + `landmark_indices_for_side()`. `pipeline.py` calls the detector once after quality gates and threads `lifter_side` through to `metric_extraction.py` and `signal_processing.py`. Existing hardcoded even-index constants deleted. New nullable `lifter_side` column on `analyses` table.

**Tech Stack:** Python 3.12, NumPy, Alembic, pytest, SQLAlchemy 2.0 async. No frontend changes (Session 3 surfaces detected side in expert portal).

---

## File Structure

### Files to create

| File | Purpose |
|---|---|
| `backend/app/cv/lifter_side.py` | `detect_lifter_side(landmarks_session, frame_width=None) -> Literal["left","right"]` + `landmark_indices_for_side(side) -> SideIndices` NamedTuple. Pure functions, no IO. |
| `backend/tests/unit/test_lifter_side.py` | Unit tests covering right-dominant visibility, left-dominant, ambiguous-defaults-to-right, ambiguous-logs-WARNING, anchor-based robustness, NamedTuple lookup. |
| `backend/tests/integration/test_lifter_side_fixtures.py` | Integration: run detection on the 3 atharva fixtures, document detected side, assert detection is stable across re-runs. |
| `backend/alembic/versions/<timestamp>_add_lifter_side_to_analyses.py` | Add `lifter_side VARCHAR(10) CHECK (lifter_side IN ('left','right'))` to `analyses`. Nullable; reversible. |

### Files to modify

| File | Change |
|---|---|
| `backend/app/cv/metric_extraction.py` | Delete `_SHOULDER=12 / _HIP=24 / _KNEE=26 / _ANKLE=28 / _ELBOW=14 / _WRIST=16`. Take `lifter_side` as input (default `"right"`). Replace every landmark-index reference with the corresponding field of `landmark_indices_for_side(side)`. |
| `backend/app/cv/signal_processing.py` | Delete `_SQUAT_*_L` and `_BENCH_*_L` constants and the per-exercise hardcoded blocks. Replace with side-aware lookup. Drop the misleading `_L` suffix. |
| `backend/app/services/pipeline.py` | Insert call to `detect_lifter_side()` between Step 3 (quality gates pass) and Step 4 (angle timeseries). Persist detected side to the `analyses` row. Thread `lifter_side` into `compute_angle_timeseries`, `extract_rep_metrics`, and `detect_reps` entry points (where they touch landmarks). |
| `backend/app/models/analysis.py` | Add `lifter_side: Mapped[Optional[str]]` column + CHECK constraint mirrored. |
| `backend/app/schemas/analysis.py` | Add `lifter_side: Literal["left","right"] \| None = None` to `AnalysisDetail` (read-only — backend-populated). |
| `backend/CLAUDE.md` | Add gotcha block: "Landmark indices are no longer hardcoded — always use `landmark_indices_for_side(lifter_side)`. Subject-right is the default-on-ambiguity fallback only. See ADR-LIFTER-SIDE-DETECTION." |

### Files explicitly NOT changed

- `backend/app/cv/barbell_detection.py` wrist-midpoint fallback — uses BOTH wrists (15 + 16) by design; design Section 2 keeps this special case unchanged.
- Existing `test_metric_extraction.py` / `test_signal_processing.py` assertions — Session 2 invariant: assertion strings/values stay green WITHOUT modification. Test FIXTURES may add a `lifter_side` kwarg only if a function signature requires it; the assertions themselves do not change.

---

## Tasks

### Task 1: Create branch + verify clean tree

- [ ] **Step 1: Confirm current branch + status**

Run: `git status`
Expected: working tree clean OR only docs/skeleton modifications staged for the plan-expansion PR (commit those separately first if so).

- [ ] **Step 2: Sync main and branch**

Run: `git checkout main && git pull --ff-only && git checkout -b feat/lifter-side-detection`
Expected: `Switched to a new branch 'feat/lifter-side-detection'`.

- [ ] **Step 3: Confirm no migration drift before refactor**

Run (from `backend/`): `uv run alembic current`
Expected: head matches `2371965f8072` (last Session 1 migration).

---

### Task 2: Write `detect_lifter_side()` core algorithm (TDD)

**Files:**
- Create: `backend/app/cv/lifter_side.py`
- Test: `backend/tests/unit/test_lifter_side.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/test_lifter_side.py`:

```python
"""Unit tests for lifter-side detection (Session 2, L2-LIFTER-SIDE-01).

All tests use synthetic (n_frames, 33, 5) landmark arrays.
"""
from __future__ import annotations

import logging

import numpy as np
import pytest

from app.cv.lifter_side import (
    SideIndices,
    detect_lifter_side,
    landmark_indices_for_side,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LEFT_INDICES = (11, 13, 15, 23, 25, 27, 29, 31)
RIGHT_INDICES = (12, 14, 16, 24, 26, 28, 30, 32)


def _make_session(
    n_frames: int = 30,
    right_visibility: float = 0.9,
    left_visibility: float = 0.3,
    centroid_x: float = 0.5,
) -> np.ndarray:
    """Build a (n_frames, 33, 5) synthetic landmark session.

    Every landmark gets a sensible position so anchor centroid is computable.
    Visibility (col 3) and presence (col 4) are set per side.
    """
    session = np.zeros((n_frames, 33, 5), dtype=float)
    for f in range(n_frames):
        # Position all landmarks near the centroid_x with a vertical spread.
        # Hips (23, 24) define the anchor centroid.
        for idx in range(33):
            session[f, idx, 0] = centroid_x  # x
            session[f, idx, 1] = 0.4 + (idx % 10) * 0.05  # y spread
            session[f, idx, 4] = 1.0  # presence
        # Right side: high visibility
        for idx in RIGHT_INDICES:
            session[f, idx, 3] = right_visibility
        # Left side: lower visibility
        for idx in LEFT_INDICES:
            session[f, idx, 3] = left_visibility
    return session


# ---------------------------------------------------------------------------
# detect_lifter_side
# ---------------------------------------------------------------------------


class TestDetectLifterSide:
    def test_right_dominant_visibility_returns_right(self) -> None:
        session = _make_session(right_visibility=0.95, left_visibility=0.20)
        assert detect_lifter_side(session) == "right"

    def test_left_dominant_visibility_returns_left(self) -> None:
        session = _make_session(right_visibility=0.20, left_visibility=0.95)
        assert detect_lifter_side(session) == "left"

    def test_tie_defaults_to_right(self) -> None:
        # Exact tie: both sides at 0.7 visibility.
        session = _make_session(right_visibility=0.7, left_visibility=0.7)
        assert detect_lifter_side(session) == "right"

    def test_near_tie_within_5pct_defaults_to_right(self) -> None:
        # 0.70 vs 0.72 → relative diff 0.0278 < 0.05 → ambiguous → "right".
        session = _make_session(right_visibility=0.70, left_visibility=0.72)
        assert detect_lifter_side(session) == "right"

    def test_clear_left_dominance_above_5pct_returns_left(self) -> None:
        # 0.70 vs 0.80 → relative diff 0.125 > 0.05 → unambiguous → "left".
        session = _make_session(right_visibility=0.70, left_visibility=0.80)
        assert detect_lifter_side(session) == "left"

    def test_only_uses_first_three_seconds_when_fps_provided(self) -> None:
        # First 90 frames left-dominant, later frames right-dominant.
        # With fps=30 the algorithm should only look at frames [0:90].
        left = _make_session(n_frames=90, right_visibility=0.10, left_visibility=0.95)
        right = _make_session(n_frames=210, right_visibility=0.95, left_visibility=0.10)
        session = np.concatenate([left, right], axis=0)
        assert detect_lifter_side(session, fps=30.0) == "left"

    def test_handles_empty_session_returns_right(self) -> None:
        # No frames → safe default.
        empty = np.zeros((0, 33, 5), dtype=float)
        assert detect_lifter_side(empty) == "right"

    def test_returns_literal_left_or_right_only(self) -> None:
        session = _make_session()
        result = detect_lifter_side(session)
        assert result in ("left", "right")


# ---------------------------------------------------------------------------
# Ambiguous detection logs WARNING (Task 5 — combined here for cohesion)
# ---------------------------------------------------------------------------


class TestDetectLifterSideLogging:
    def test_ambiguous_detection_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        session = _make_session(right_visibility=0.70, left_visibility=0.72)
        with caplog.at_level(logging.WARNING, logger="app.cv.lifter_side"):
            detect_lifter_side(session)
        assert any(
            "ambiguous lifter-side detection" in rec.message.lower()
            for rec in caplog.records
        ), f"Expected WARNING for ambiguous case; got: {[r.message for r in caplog.records]}"

    def test_clear_dominance_does_not_log_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        session = _make_session(right_visibility=0.95, left_visibility=0.20)
        with caplog.at_level(logging.WARNING, logger="app.cv.lifter_side"):
            detect_lifter_side(session)
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert warnings == [], (
            f"Did not expect WARNING for clear-dominance case; got: "
            f"{[r.message for r in warnings]}"
        )


# ---------------------------------------------------------------------------
# landmark_indices_for_side
# ---------------------------------------------------------------------------


class TestLandmarkIndicesForSide:
    def test_right_side_returns_even_indices(self) -> None:
        idx = landmark_indices_for_side("right")
        assert isinstance(idx, SideIndices)
        assert idx.shoulder == 12
        assert idx.elbow == 14
        assert idx.wrist == 16
        assert idx.hip == 24
        assert idx.knee == 26
        assert idx.ankle == 28
        assert idx.heel == 30
        assert idx.foot_index == 32

    def test_left_side_returns_odd_indices(self) -> None:
        idx = landmark_indices_for_side("left")
        assert idx.shoulder == 11
        assert idx.elbow == 13
        assert idx.wrist == 15
        assert idx.hip == 23
        assert idx.knee == 25
        assert idx.ankle == 27
        assert idx.heel == 29
        assert idx.foot_index == 31

    def test_rejects_unknown_side(self) -> None:
        with pytest.raises(ValueError, match="side must be"):
            landmark_indices_for_side("unknown")  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/unit/test_lifter_side.py -x`
Expected: `ImportError` / `ModuleNotFoundError` for `app.cv.lifter_side` — confirms TDD red.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/cv/lifter_side.py`:

```python
"""Lifter-side detection for sagittal-view CV pipeline (Session 2).

Provides a single source of truth for "which side of the lifter is facing
the camera" and the corresponding MediaPipe BlazePose landmark indices.

Replaces hardcoded even-index constants in metric_extraction.py and
signal_processing.py. See ADR-LIFTER-SIDE-DETECTION.

MediaPipe BlazePose 33-landmark naming (subject perspective):
  Left  (subject's left): 11, 13, 15, 23, 25, 27, 29, 31
  Right (subject's right): 12, 14, 16, 24, 26, 28, 30, 32

All functions are pure — no IO, no DB, no side effects.
"""
from __future__ import annotations

import logging
from typing import Literal, NamedTuple

import numpy as np

logger = logging.getLogger(__name__)

# MediaPipe BlazePose 33-landmark indices.
_LEFT_LANDMARKS: tuple[int, ...] = (11, 13, 15, 23, 25, 27, 29, 31)
_RIGHT_LANDMARKS: tuple[int, ...] = (12, 14, 16, 24, 26, 28, 30, 32)

# Anchor-based robustness (R1 mitigation, ADR-QGATE-COMMERCIAL-GYM analogue).
_ANCHOR_FROM_FIRST_N_SAMPLES = 3
_OFF_ANCHOR_DISTANCE_FRAC = 0.25

# Ambiguous-detection threshold (relative difference between side visibilities).
_AMBIGUOUS_RELATIVE_DIFF = 0.05

# Default window for visibility comparison.
_DEFAULT_WINDOW_SECONDS = 3.0


class SideIndices(NamedTuple):
    """MediaPipe landmark indices for one side of the body."""

    shoulder: int
    elbow: int
    wrist: int
    hip: int
    knee: int
    ankle: int
    heel: int
    foot_index: int


_RIGHT_SIDE = SideIndices(
    shoulder=12, elbow=14, wrist=16, hip=24,
    knee=26, ankle=28, heel=30, foot_index=32,
)
_LEFT_SIDE = SideIndices(
    shoulder=11, elbow=13, wrist=15, hip=23,
    knee=25, ankle=27, heel=29, foot_index=31,
)


def landmark_indices_for_side(side: Literal["left", "right"]) -> SideIndices:
    """Return MediaPipe landmark indices for the lifter's filmed side.

    Parameters
    ----------
    side:
        Either ``"left"`` or ``"right"`` (subject-perspective).

    Returns
    -------
    SideIndices
        NamedTuple with fields shoulder/elbow/wrist/hip/knee/ankle/heel/foot_index.

    Raises
    ------
    ValueError
        If ``side`` is not one of ``"left"`` or ``"right"``.
    """
    if side == "right":
        return _RIGHT_SIDE
    if side == "left":
        return _LEFT_SIDE
    raise ValueError(
        f"side must be 'left' or 'right'; got {side!r}"
    )


def _compute_anchor_centroid(
    landmarks_session: np.ndarray,
) -> tuple[float, float] | None:
    """Compute lifter-centroid x from first N high-visibility hip samples.

    Mirrors the ``check_single_person`` anchor pattern in
    ``backend/app/cv/quality_gates.py``: take the first
    ``_ANCHOR_FROM_FIRST_N_SAMPLES`` frames where BOTH hips have
    visibility >= 0.5, and use the median hip-midpoint (x, y) as the anchor.

    Returns ``None`` if no qualifying frames are found.
    """
    if landmarks_session.shape[0] == 0:
        return None
    midpoints: list[tuple[float, float]] = []
    for frame in landmarks_session:
        hip_l = frame[23]
        hip_r = frame[24]
        if hip_l[3] >= 0.5 and hip_r[3] >= 0.5:
            mid_x = float((hip_l[0] + hip_r[0]) / 2.0)
            mid_y = float((hip_l[1] + hip_r[1]) / 2.0)
            midpoints.append((mid_x, mid_y))
            if len(midpoints) >= _ANCHOR_FROM_FIRST_N_SAMPLES:
                break
    if not midpoints:
        return None
    xs = np.array([m[0] for m in midpoints])
    ys = np.array([m[1] for m in midpoints])
    return float(np.median(xs)), float(np.median(ys))


def _mean_visibility_for_indices(
    frames: np.ndarray,
    indices: tuple[int, ...],
    anchor: tuple[float, float] | None,
) -> float:
    """Mean visibility of *indices* across *frames*, restricted to landmarks
    near the lifter anchor when an anchor is available.

    Restriction (R1 mitigation): a landmark is included only if its x is
    within ``_OFF_ANCHOR_DISTANCE_FRAC`` of the anchor x in normalised
    [0, 1] space. This prevents bystander landmarks (which MediaPipe may
    re-acquire) from flipping the visibility tally.
    """
    if frames.shape[0] == 0:
        return 0.0
    selection = frames[:, list(indices), :]  # (n_frames, len(indices), 5)
    visibilities = selection[..., 3]
    if anchor is not None:
        anchor_x = anchor[0]
        xs = selection[..., 0]
        mask = np.abs(xs - anchor_x) <= _OFF_ANCHOR_DISTANCE_FRAC
        if not bool(np.any(mask)):
            # No landmarks survived the anchor restriction — fall back to
            # the un-restricted mean rather than reporting 0.
            return float(np.mean(visibilities))
        return float(np.mean(visibilities[mask]))
    return float(np.mean(visibilities))


def detect_lifter_side(
    landmarks_session: np.ndarray,
    fps: float | None = None,
) -> Literal["left", "right"]:
    """Detect which side of the lifter is facing the camera.

    Algorithm:
      1. Compute the lifter anchor centroid from the first 3 high-visibility
         hip-midpoint samples (R1 mitigation against bystander interference).
      2. Restrict comparison to the first ``fps * 3`` frames if ``fps`` is
         given, else use the full session.
      3. For each side (left = odd indices, right = even), compute the mean
         visibility over frames-and-landmarks, excluding landmarks whose x
         is more than ``_OFF_ANCHOR_DISTANCE_FRAC`` from the anchor x.
      4. Whichever side has the higher mean wins. On exact tie, return
         ``"right"`` (matches the pre-refactor hardcoded default).
      5. If the relative difference is below ``_AMBIGUOUS_RELATIVE_DIFF``,
         log WARNING and still default to ``"right"``.

    Parameters
    ----------
    landmarks_session:
        ``(n_frames, 33, 5)`` ndarray. Column 3 is visibility, column 4
        is presence; both may be pre-sigmoid logits per MediaPipe.
    fps:
        Optional frames-per-second. When given, restricts the analysis
        window to the first ``fps * _DEFAULT_WINDOW_SECONDS`` frames.

    Returns
    -------
    Literal["left", "right"]
        Detected subject-side. Always returns a concrete string; never None.
    """
    if landmarks_session.ndim != 3 or landmarks_session.shape[0] == 0:
        return "right"

    # Restrict to the first ~3 seconds when fps is known.
    if fps is not None and fps > 0:
        max_frames = int(fps * _DEFAULT_WINDOW_SECONDS)
        frames = landmarks_session[:max_frames]
    else:
        frames = landmarks_session

    if frames.shape[0] == 0:
        return "right"

    anchor = _compute_anchor_centroid(landmarks_session)
    left_vis = _mean_visibility_for_indices(frames, _LEFT_LANDMARKS, anchor)
    right_vis = _mean_visibility_for_indices(frames, _RIGHT_LANDMARKS, anchor)

    higher = max(left_vis, right_vis)
    if higher <= 0.0:
        return "right"

    rel_diff = abs(left_vis - right_vis) / higher
    if rel_diff < _AMBIGUOUS_RELATIVE_DIFF:
        logger.warning(
            "Ambiguous lifter-side detection: left_vis=%.3f right_vis=%.3f "
            "(relative diff %.3f < %.3f); defaulting to 'right'",
            left_vis, right_vis, rel_diff, _AMBIGUOUS_RELATIVE_DIFF,
        )
        return "right"

    return "left" if left_vis > right_vis else "right"


__all__ = [
    "SideIndices",
    "detect_lifter_side",
    "landmark_indices_for_side",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_lifter_side.py -x -v`
Expected: every test under `TestDetectLifterSide`, `TestDetectLifterSideLogging`, and `TestLandmarkIndicesForSide` passes.

- [ ] **Step 5: Coverage check**

Run: `uv run pytest tests/unit/test_lifter_side.py --cov=app.cv.lifter_side --cov-report=term-missing`
Expected: ≥90% coverage on `app/cv/lifter_side.py` per Standing Rule #1.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/lifter_side.py backend/tests/unit/test_lifter_side.py
git commit -m "feat(cv): add lifter-side detection helper (L2-LIFTER-SIDE-01)"
```

---

### Task 3: Anchor-based robustness against bystander interference (R1 mitigation)

Implementation already lives in Task 2's `_compute_anchor_centroid` + `_mean_visibility_for_indices`. This task adds the dedicated regression test.

- [ ] **Step 1: Add the failing bystander-interference test**

Append to `backend/tests/unit/test_lifter_side.py`:

```python
class TestAnchorRobustness:
    def test_bystander_on_opposite_side_does_not_flip_detection(self) -> None:
        """A bystander whose visible body-side is OPPOSITE the lifter must
        not flip detection. Without the anchor restriction the naive mean
        flips; with the anchor, the lifter's side still wins.
        """
        # Lifter occupies x ~ 0.5 with right-side dominance.
        lifter_session = _make_session(
            n_frames=30,
            right_visibility=0.90,
            left_visibility=0.30,
            centroid_x=0.5,
        )
        # Bystander overlay on the far edge (x = 0.9) with LEFT-dominant
        # visibility values overwritten on the SAME landmark indices.
        # We simulate this by adding very high left-side visibility scores
        # at landmarks whose x is far from the lifter centroid.
        for f in range(30):
            for idx in LEFT_INDICES:
                # Move SOME of these landmarks far from the lifter and crank
                # their visibility, simulating MediaPipe locking onto a
                # second person briefly.
                lifter_session[f, idx, 0] = 0.9  # far from centroid 0.5
                lifter_session[f, idx, 3] = 0.99
        # Without anchor: left mean would dominate (0.99 >> 0.90).
        # With anchor (centroid ~0.5, threshold 0.25 → window [0.25, 0.75]):
        # bystander left landmarks at x=0.9 are excluded → lifter's right wins.
        assert detect_lifter_side(lifter_session) == "right"

    def test_no_anchor_available_falls_back_to_naive_mean(self) -> None:
        """If no hip samples meet the visibility floor, anchor is None and
        the function still returns a valid side without raising.
        """
        session = _make_session(right_visibility=0.95, left_visibility=0.20)
        # Zero out hip visibility so the anchor cannot be computed.
        session[:, 23, 3] = 0.0
        session[:, 24, 3] = 0.0
        result = detect_lifter_side(session)
        assert result in ("left", "right")
```

- [ ] **Step 2: Run the new tests**

Run: `uv run pytest tests/unit/test_lifter_side.py::TestAnchorRobustness -x -v`
Expected: both tests pass (implementation already supports this).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_lifter_side.py
git commit -m "test(cv): add anchor-based bystander-robustness regression for lifter-side detection"
```

---

### Task 4: Confirm `landmark_indices_for_side()` lookup correctness

Covered by `TestLandmarkIndicesForSide` in Task 2. No additional code; this task is the explicit checkpoint.

- [ ] **Step 1: Verify the lookup tests pass alone**

Run: `uv run pytest tests/unit/test_lifter_side.py::TestLandmarkIndicesForSide -x -v`
Expected: 3 tests pass (`test_right_side_returns_even_indices`, `test_left_side_returns_odd_indices`, `test_rejects_unknown_side`).

---

### Task 5: WARNING-log ambiguous detection

Covered by `TestDetectLifterSideLogging` in Task 2.

- [ ] **Step 1: Verify the logging tests pass alone**

Run: `uv run pytest tests/unit/test_lifter_side.py::TestDetectLifterSideLogging -x -v`
Expected: 2 tests pass.

---

### Task 6: Alembic migration adding `lifter_side` column

**Files:**
- Create: `backend/alembic/versions/<timestamp>_add_lifter_side_to_analyses.py`
- Modify (after migration generation): `backend/app/models/analysis.py`

**Use the `spelix-migration` agent for this task** (project rule for all migrations).

- [ ] **Step 1: Generate the migration via spelix-migration agent**

Dispatch the agent with:

> Use the spelix-migration agent. Add a nullable column `lifter_side VARCHAR(10)` to the `analyses` table with a CHECK constraint enforcing `lifter_side IN ('left', 'right')`. Reversible. Down: drop column. Name the constraint `ck_analyses_lifter_side`. Down-revision: `2371965f8072`. Generate the migration file under `backend/alembic/versions/` and print its file path.

- [ ] **Step 2: Verify migration file structure**

Read the generated file. It must contain:

```python
def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("lifter_side", sa.String(length=10), nullable=True),
    )
    op.create_check_constraint(
        "ck_analyses_lifter_side",
        "analyses",
        "lifter_side IS NULL OR lifter_side IN ('left', 'right')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_analyses_lifter_side", "analyses", type_="check")
    op.drop_column("analyses", "lifter_side")
```

- [ ] **Step 3: Apply migration locally**

Run: `uv run alembic upgrade head`
Expected: `Running upgrade 2371965f8072 -> <new_head>, add lifter_side to analyses`.

- [ ] **Step 4: Confirm head moved**

Run: `uv run alembic current`
Expected: prints the new head SHA (not `2371965f8072`).

- [ ] **Step 5: Test reversibility**

Run: `uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: downgrade succeeds (column dropped), then upgrade re-applies cleanly. End at the new head.

- [ ] **Step 6: Update the SQLAlchemy model**

Modify `backend/app/models/analysis.py`:

- Extend `__table_args__` tuple to include a second `CheckConstraint` for `lifter_side`:

```python
__table_args__ = (
    CheckConstraint(
        "status IN ('queued','quality_gate_pending','quality_gate_rejected',"
        "'processing','coaching','completed','failed')",
        name="ck_analyses_status",
    ),
    CheckConstraint(
        "lifter_side IS NULL OR lifter_side IN ('left','right')",
        name="ck_analyses_lifter_side",
    ),
    Index("ix_analyses_user_created", "user_id", desc("created_at")),
)
```

- Add the column declaration (after `weight_kg`, before `flagged_for_review`):

```python
lifter_side: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
```

- [ ] **Step 7: Add migration-shape test**

Append to `backend/tests/unit/test_migrations.py` (or create a small new file `backend/tests/unit/test_lifter_side_column.py` if `test_migrations.py` does not exist):

```python
"""Verify the lifter_side column is present on the Analysis model with the
correct nullable + CHECK constraint."""
from sqlalchemy import inspect

from app.models.analysis import Analysis


def test_analysis_model_has_lifter_side_column() -> None:
    cols = {c.name: c for c in inspect(Analysis).columns}
    assert "lifter_side" in cols
    col = cols["lifter_side"]
    assert col.nullable is True
    assert col.type.length == 10


def test_analysis_model_has_lifter_side_check_constraint() -> None:
    constraints = {
        c.name for c in Analysis.__table__.constraints if c.name is not None
    }
    assert "ck_analyses_lifter_side" in constraints
```

- [ ] **Step 8: Run model tests**

Run: `uv run pytest tests/unit/test_lifter_side_column.py -x -v`
Expected: both tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/alembic/versions/ backend/app/models/analysis.py backend/tests/unit/test_lifter_side_column.py
git commit -m "feat(models): add lifter_side column to analyses with CHECK constraint (L2-LIFTER-SIDE-02)"
```

---

### Task 7: Refactor `metric_extraction.py` to side-aware

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Run unchanged: `backend/tests/unit/test_metric_extraction.py`

**Invariant:** existing test assertions must stay green WITHOUT modification. Achieved by defaulting `lifter_side="right"` everywhere — the previous hardcoded constants WERE the right-side indices.

- [ ] **Step 1: Refactor `metric_extraction.py` top-of-file**

Replace the constants block (`_SHOULDER = 12` through `_WRIST = 16`) with:

```python
from app.cv.lifter_side import SideIndices, landmark_indices_for_side
```

Remove the docstring sentence "Landmark indices used (left/even side per task spec)" and replace with:

```
Landmark indices are resolved per-analysis via
``landmark_indices_for_side(lifter_side)`` (Session 2,
ADR-LIFTER-SIDE-DETECTION).
```

- [ ] **Step 2: Thread `lifter_side` through analyzer signatures**

Change every `_squat_metrics`, `_bench_metrics`, `_deadlift_metrics` to accept a `side_idx: SideIndices` parameter. Replace `_SHOULDER` / `_HIP` / `_KNEE` / `_ANKLE` / `_ELBOW` / `_WRIST` references with `side_idx.shoulder`, `side_idx.hip`, etc.

`_torso_lean_deg` becomes:

```python
def _torso_lean_deg(landmarks: np.ndarray, side_idx: SideIndices) -> float:
    shoulder = _xy(landmarks, side_idx.shoulder)
    hip = _xy(landmarks, side_idx.hip)
    # ... unchanged math below ...
```

`_assess_lockout_quality` becomes:

```python
def _assess_lockout_quality(
    exercise_type: str,
    end_frame: int,
    landmarks_per_frame: list[np.ndarray],
    angle_timeseries: dict[str, np.ndarray],
    side_idx: SideIndices,
) -> tuple[bool, float]:
    # ... replace _HIP → side_idx.hip, _KNEE → side_idx.knee,
    # _ELBOW → side_idx.elbow, _SHOULDER → side_idx.shoulder
```

`_ANALYZER_MAP` stays unchanged but the callers are updated to pass `side_idx`.

- [ ] **Step 3: Update the public entry point**

`extract_rep_metrics` signature becomes:

```python
def extract_rep_metrics(
    reps: list[DetectedRep],
    landmarks_per_frame: list[np.ndarray],
    angle_timeseries: dict[str, np.ndarray],
    exercise_type: str,
    exercise_variant: str,
    fps: float,
    lifter_side: Literal["left", "right"] = "right",
) -> list[RepMetrics]:
    ...
    side_idx = landmark_indices_for_side(lifter_side)
    ...
    for rep in reps:
        metrics = analyzer(rep, landmarks_per_frame, angle_timeseries, fps, side_idx)
```

Add the import at the top:

```python
from typing import Literal
```

- [ ] **Step 4: Run the existing metric-extraction tests unmodified**

Run: `uv run pytest tests/unit/test_metric_extraction.py -x -v`
Expected: all tests pass with **zero modifications** to assertion text or expected values. If anything fails, the refactor changed observable behavior — STOP and investigate (signals broken invariant per the goal's STOP clauses).

- [ ] **Step 5: Confirm zero diff in test file**

Run: `git diff backend/tests/unit/test_metric_extraction.py`
Expected: empty output. If non-empty: STOP.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/metric_extraction.py
git commit -m "refactor(cv): route metric_extraction through landmark_indices_for_side (L2-LIFTER-SIDE-03)"
```

---

### Task 8: Refactor `signal_processing.py` analogously

**Files:**
- Modify: `backend/app/cv/signal_processing.py`
- Run unchanged: `backend/tests/unit/test_signal_processing.py`

- [ ] **Step 1: Replace landmark constant block**

Delete the entire block from line 21 ("Landmark index definitions") through line 48 (after `_BENCH_HIP_L = 24`). Replace with:

```python
from app.cv.lifter_side import SideIndices, landmark_indices_for_side
```

- [ ] **Step 2: Refactor `calculate_joint_angles`**

```python
def calculate_joint_angles(
    landmarks: np.ndarray,
    exercise_type: str,
    lifter_side: Literal["left", "right"] = "right",
) -> dict[str, float]:
    ex = exercise_type.lower()
    side_idx = landmark_indices_for_side(lifter_side)

    def xy(idx: int) -> np.ndarray:
        return landmarks[idx, :2]

    if ex in ("squat", "deadlift"):
        hip_angle = calculate_angle(
            xy(side_idx.shoulder), xy(side_idx.hip), xy(side_idx.knee),
        )
        knee_angle = calculate_angle(
            xy(side_idx.hip), xy(side_idx.knee), xy(side_idx.ankle),
        )
        return {"hip_angle": hip_angle, "knee_angle": knee_angle}

    if ex == "bench":
        elbow_angle = calculate_angle(
            xy(side_idx.shoulder), xy(side_idx.elbow), xy(side_idx.wrist),
        )
        shoulder_angle = calculate_angle(
            xy(side_idx.elbow), xy(side_idx.shoulder), xy(side_idx.hip),
        )
        return {"elbow_angle": elbow_angle, "shoulder_angle": shoulder_angle}

    raise ValueError(
        f"Unknown exercise type: {exercise_type!r}. "
        "Expected one of: 'squat', 'deadlift', 'bench'."
    )
```

Add the `from typing import Literal` import at the top.

- [ ] **Step 3: Refactor `compute_angle_timeseries`**

```python
def compute_angle_timeseries(
    landmarks_per_frame: list[np.ndarray],
    exercise_type: str,
    lifter_side: Literal["left", "right"] = "right",
) -> dict[str, np.ndarray]:
    raw: dict[str, list[float]] = {}
    for frame in landmarks_per_frame:
        angles = calculate_joint_angles(frame, exercise_type, lifter_side)
        for joint, angle in angles.items():
            raw.setdefault(joint, []).append(angle)
    return {
        joint: smooth_signal(np.array(series, dtype=float))
        for joint, series in raw.items()
    }
```

- [ ] **Step 4: Run the existing signal-processing tests unmodified**

Run: `uv run pytest tests/unit/test_signal_processing.py -x -v`
Expected: all tests pass with **zero modifications** to assertion text/values.

- [ ] **Step 5: Confirm zero diff in test file**

Run: `git diff backend/tests/unit/test_signal_processing.py`
Expected: empty output. If non-empty: STOP.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/signal_processing.py
git commit -m "refactor(cv): route signal_processing through landmark_indices_for_side (L2-LIFTER-SIDE-04)"
```

---

### Task 9: Wire `pipeline.py` to call `detect_lifter_side()`

**Files:**
- Modify: `backend/app/services/pipeline.py`

- [ ] **Step 1: Add the import**

Add near the other CV imports (around line 40):

```python
from app.cv.lifter_side import detect_lifter_side
```

- [ ] **Step 2: Insert detection after the quality-gate-pass branch**

After the `analysis.status = transition(analysis.status, "processing")` line (around line 540) and BEFORE Step 4 angle timeseries, add:

```python
    # ------------------------------------------------------------------ #
    # Step 3.5: Lifter-side detection (Session 2, ADR-LIFTER-SIDE-DETECTION)
    # ------------------------------------------------------------------ #
    with timer.stage("lifter_side_detection"):
        landmarks_arr = np.stack(landmarks_per_frame) if landmarks_per_frame else np.zeros((0, 33, 5))
        lifter_side = await loop.run_in_executor(
            None, detect_lifter_side, landmarks_arr, fps,
        )
    result.lifter_side = lifter_side
    analysis.lifter_side = lifter_side
    logger.info(
        "analysis %s detected lifter_side=%s", analysis_id, lifter_side,
    )
    await repo.update(analysis)
    await repo.db.commit()
    await _persist_timing_telemetry(analysis.id, timer.as_dict())
```

- [ ] **Step 3: Thread `lifter_side` into downstream CV calls**

Update the `compute_angle_timeseries` call (around line 552) to pass `lifter_side`:

```python
    with timer.stage("angle_timeseries"):
        angle_timeseries = await loop.run_in_executor(
            None, compute_angle_timeseries, landmarks_per_frame, exercise_type, lifter_side,
        )
```

Update the `extract_rep_metrics` call (around line 594):

```python
    with timer.stage("metric_extraction"):
        rep_metrics = await loop.run_in_executor(
            None,
            extract_rep_metrics,
            reps,
            landmarks_per_frame,
            angle_timeseries,
            exercise_type,
            exercise_variant,
            fps,
            lifter_side,
        )
```

- [ ] **Step 4: Add `lifter_side` to `PipelineResult` dataclass**

In the same file (`backend/app/services/pipeline.py`), locate the `PipelineResult` dataclass. Add:

```python
    lifter_side: Literal["left", "right"] | None = None
```

(Add `from typing import Literal` if not already imported.)

- [ ] **Step 5: Run the full pipeline-related unit suite**

Run: `uv run pytest tests/unit/test_pipeline.py tests/unit/test_metric_extraction.py tests/unit/test_signal_processing.py tests/unit/test_lifter_side.py -x`
Expected: all pass. Any new failure under `test_pipeline.py` is acceptable ONLY if it stems from a `MagicMock` analysis missing the new `lifter_side` attribute — fix the mock factory (per backend/CLAUDE.md "MagicMock + Pydantic" gotcha), not the production code.

- [ ] **Step 6: Update mock factories if needed**

If `test_pipeline.py` fails because mocks lack `lifter_side`, add to `_make_mock_analysis` (in `backend/tests/unit/test_analysis_crud.py`) and `_make_detail_analysis` (in `backend/tests/unit/test_analysis_api.py`):

```python
mock.lifter_side = None
```

Re-run the failing tests; verify they pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/pipeline.py backend/tests/unit/test_analysis_crud.py backend/tests/unit/test_analysis_api.py
git commit -m "feat(pipeline): detect lifter_side once per analysis and thread through CV stages (L2-LIFTER-SIDE-05)"
```

---

### Task 10: Update `AnalysisDetail` Pydantic schema

**Files:**
- Modify: `backend/app/schemas/analysis.py`

- [ ] **Step 1: Add the field**

In `class AnalysisDetail(BaseModel)`, add after `confidence_score`:

```python
    lifter_side: Literal["left", "right"] | None = None
```

(Add `from typing import Literal` to the imports if not present.)

- [ ] **Step 2: Add API contract test**

Append to `backend/tests/unit/test_analysis_api.py`:

```python
def test_analysis_detail_response_includes_lifter_side(
    test_client, mock_user, mock_analysis_repo
) -> None:
    """FR-LIFTER-SIDE: detected side appears in the AnalysisDetail JSON."""
    mock_analysis = _make_detail_analysis()
    mock_analysis.lifter_side = "right"
    mock_analysis_repo.get_by_id.return_value = mock_analysis
    response = test_client.get(f"/api/v1/analyses/{mock_analysis.id}")
    assert response.status_code == 200
    assert response.json()["lifter_side"] == "right"
```

- [ ] **Step 3: Run the analysis-API tests**

Run: `uv run pytest tests/unit/test_analysis_api.py -x -v -k lifter`
Expected: the new test passes; no other tests regress.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/analysis.py backend/tests/unit/test_analysis_api.py
git commit -m "feat(schema): expose lifter_side on AnalysisDetail response (FR-LIFTER-SIDE)"
```

---

### Task 11: Integration test on the 3 atharva fixtures

**Files:**
- Create: `backend/tests/integration/test_lifter_side_fixtures.py`

- [ ] **Step 1: Write the failing fixture test**

```python
"""Integration test — lifter-side detection on the 3 atharva fixtures
(Session 2, L2-LIFTER-SIDE-05).

Runs detection against real pose data extracted from each fixture. Documents
the detected side per fixture in the docstring of each test — this becomes
ground truth for the calibration check in Task 13.

Ground-truth verification: open each fixture video and eyeball which side
of the lifter faces the camera. If detection disagrees, that is a STOP
trigger per the goal's STOP clauses.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.cv.lifter_side import detect_lifter_side
from app.cv.pose_extraction import extract_landmarks

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "e2e" / "fixtures"

FIXTURES = [
    ("atharva-squat.mov", "squat"),
    ("atharva-bench.mov", "bench"),
    ("atharva-deadlift.mov", "deadlift"),
]


@pytest.mark.integration
@pytest.mark.parametrize("filename,exercise", FIXTURES)
def test_detect_lifter_side_on_atharva_fixture(
    filename: str, exercise: str
) -> None:
    """Detected side is recorded in the captured-stdout block of the test
    output. Whatever value the function returns becomes the ground-truth
    expectation; subsequent runs assert stability.
    """
    fixture_path = FIXTURE_DIR / filename
    if not fixture_path.exists():
        pytest.skip(f"Fixture not available: {fixture_path}")

    landmarks, fps, _w, _h = extract_landmarks(str(fixture_path))
    if not landmarks:
        pytest.skip(f"No landmarks extracted from {filename}")

    session = np.stack(landmarks)
    side = detect_lifter_side(session, fps=fps)

    assert side in ("left", "right"), f"unexpected side {side!r}"
    print(f"[lifter-side] {filename} ({exercise}) detected: {side}")


@pytest.mark.integration
def test_detect_lifter_side_is_stable_on_repeat_invocations() -> None:
    """Same input → same output across N calls (no randomness)."""
    fixture_path = FIXTURE_DIR / "atharva-squat.mov"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not available: {fixture_path}")
    landmarks, fps, _w, _h = extract_landmarks(str(fixture_path))
    session = np.stack(landmarks)
    sides = {detect_lifter_side(session, fps=fps) for _ in range(5)}
    assert len(sides) == 1, f"detection unstable across runs: {sides}"
```

- [ ] **Step 2: Run the integration tests**

Run: `uv run pytest tests/integration/test_lifter_side_fixtures.py -x -v -s`
Expected: 4 tests pass (3 parametrized + 1 stability). The `[lifter-side]` print lines reveal the detected side for each fixture.

- [ ] **Step 3: Record detected sides in the PR description draft**

Capture the printed output. The Session 2 PR description (Task 18) must list:
- `atharva-squat.mov` → detected `<right|left>`
- `atharva-bench.mov` → detected `<right|left>`
- `atharva-deadlift.mov` → detected `<right|left>`

- [ ] **Step 4: Eyeball ground-truth check**

Open each fixture in a player. For each, confirm whether the lifter's left or right side faces the camera. If any detection disagrees with eyeball ground truth: STOP and escalate per the goal's STOP clauses (this signals broken anchor logic or insufficient visibility threshold).

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration/test_lifter_side_fixtures.py
git commit -m "test(cv): integration tests for lifter-side detection on atharva fixtures"
```

---

### Task 12: Existing-test-invariant verification

- [ ] **Step 1: Run the full backend unit + integration suite**

Run: `uv run pytest tests/unit/ tests/integration/ tests/mcdc/ -x`
Expected: all tests pass.

- [ ] **Step 2: Compute pre-refactor vs post-refactor counts**

Run: `uv run pytest tests/unit/ tests/integration/ tests/mcdc/ --collect-only -q | tail -1`
Expected: same total test count as before the refactor (no tests removed; new tests added).

- [ ] **Step 3: Confirm no assertion-text mutations on pre-existing tests**

Run: `git diff main -- backend/tests/unit/test_metric_extraction.py backend/tests/unit/test_signal_processing.py`
Expected: empty output. **If non-empty → STOP** (signals broken invariant per goal STOP clauses).

---

### Task 13: Score-delta calibration on the 3 atharva fixtures

- [ ] **Step 1: Pre-refactor baseline (skip if already captured)**

If the user has not captured pre-refactor scores in `.claude/handoff.md`, run on `main`:

```bash
git stash
git checkout main
uv run python backend/scripts/oneoff/dump_scores_for_fixtures.py \
    --fixtures e2e/fixtures/atharva-squat.mov e2e/fixtures/atharva-bench.mov e2e/fixtures/atharva-deadlift.mov \
    --out /tmp/spelix-baseline-scores.json
git checkout feat/lifter-side-detection
git stash pop
```

If `dump_scores_for_fixtures.py` does not exist, write a minimal smoke script that runs `run_cv_pipeline` against each fixture and dumps `form_score_overall / safety / technique / path_balance / control` per fixture.

- [ ] **Step 2: Post-refactor scores**

```bash
uv run python backend/scripts/oneoff/dump_scores_for_fixtures.py \
    --fixtures e2e/fixtures/atharva-squat.mov e2e/fixtures/atharva-bench.mov e2e/fixtures/atharva-deadlift.mov \
    --out /tmp/spelix-postrefactor-scores.json
```

- [ ] **Step 3: Compute deltas per fixture**

For each fixture: `delta = abs(post - pre) / max(pre, 1e-9) * 100` (percent).

- [ ] **Step 4: Apply the gate**

For each fixture whose detected side is `"right"`: delta MUST be ≤0.5% on every form_score_* field.
For fixtures detected `"left"`: any delta is acceptable (these are corrections) — document the magnitude + direction in the PR description.
Any right-side fixture exceeding 5% on ANY field is a hard STOP per goal STOP clauses.

- [ ] **Step 5: Record deltas in the PR description draft**

Per fixture: `Δ Overall: 0.0%, Δ Safety: 0.0%, Δ Technique: 0.0%, Δ P&B: 0.0%, Δ Control: 0.0%` (or whatever the measured values are; right-side fixtures should be within ±0.5%).

---

### Task 14: Update `backend/CLAUDE.md`

- [ ] **Step 1: Append the gotcha**

Append under `## Backend Gotchas`:

```markdown
### Side-agnostic landmark access (Session 2, ADR-LIFTER-SIDE-DETECTION)
Landmark indices are no longer hardcoded in `metric_extraction.py` or
`signal_processing.py`. Every entry point that touches MediaPipe landmark
indices takes a `lifter_side: Literal["left","right"]` parameter (default
`"right"` for backward compatibility), then resolves indices via
`landmark_indices_for_side(side)` from `app/cv/lifter_side.py`. The
pipeline computes the side once per analysis between Step 3 (quality
gates) and Step 4 (angle timeseries) and threads it through. Subject's
right (even indices 12/14/16/24/26/28/30/32) is the fallback on tied or
ambiguous detections — it matches the pre-refactor hardcoded default.
`barbell_detection.py` wrist-midpoint averaging is intentionally
side-agnostic and stays unchanged.
```

- [ ] **Step 2: Commit**

```bash
git add backend/CLAUDE.md
git commit -m "docs(claude.md): add side-agnostic landmark access gotcha (Session 2)"
```

---

### Task 15: Add `ADR-LIFTER-SIDE-DETECTION` to `decisions.md`

- [ ] **Step 1: Invoke `/adr` skill or write the ADR directly**

Append to `decisions.md`:

```markdown
## ADR-LIFTER-SIDE-DETECTION — Visibility-weighted lifter-side detection with anchor robustness

**Date:** 2026-05-22
**Status:** Accepted
**Cross-references:** ADR-AUDIT-2026-05-22, ADR-QGATE-COMMERCIAL-GYM

### Context

Before Session 2, every metric extractor and angle calculator in
`backend/app/cv/` hardcoded even-numbered MediaPipe landmark indices
(12, 14, 16, 24, 26, 28). MediaPipe BlazePose names odd = subject left,
even = subject right; the codebase silently assumed every video was
filmed from the lifter's right side. Fixtures filmed from the left
returned subtly wrong angles because we read the offside body landmarks.

The CV audit (`docs/audit/cv-dimension-audit-2026-05-11.md` E-1) called
for a single side-detection helper to drive all current and Part-2
sagittal metrics.

### Decision

1. **Detection algorithm — visibility-weighted, anchor-restricted.**
   Compute mean visibility for the 8 left-side landmarks (11/13/15/23/
   25/27/29/31) vs the 8 right-side landmarks (12/14/16/24/26/28/30/32)
   across the first ~3 seconds of pose data (or full session when fps
   is unknown). Higher mean wins. Visibility samples are restricted to
   landmarks within ±0.25 of the lifter centroid x to suppress
   bystander interference (re-uses the `check_single_person` anchor
   pattern from ADR-QGATE-COMMERCIAL-GYM).

2. **Tie-break and ambiguous-default to `"right"`.** When relative
   visibility difference is <5%, log a WARNING with both means and
   return `"right"`. This matches the pre-refactor hardcoded default,
   so right-side fixtures see zero behavioural change.

3. **Persist detected side on `analyses.lifter_side`.** Nullable
   `VARCHAR(10) CHECK (lifter_side IN ('left','right'))`. Expert
   portal (Session 3) surfaces this; users do not see it.

4. **`barbell_detection.py` wrist-midpoint fallback stays unchanged.**
   That function averages both wrists (15 + 16) by design; it is
   already side-agnostic.

5. **Public entry points accept `lifter_side: Literal["left","right"]`
   with default `"right"`.** Default preserves all pre-existing test
   assertions verbatim; the pipeline supplies the detected value at
   runtime.

### Consequences

- Fixtures filmed from the lifter's left now read the correct landmarks
  and yield correct angles. Right-side fixtures see ≤0.5% drift per
  the calibration gate in Session 2 (any larger drift is a hard STOP).
- Adding any Part-2 sagittal metric (Sessions 4–7) requires no
  side-handling code in the new extractor — it just takes a
  `SideIndices` and reads the requested landmarks.
- Ambiguous-detection WARNING logs surface during routine pipeline
  runs in worker logs; pipeline never blocks on ambiguity.

### Alternatives considered

- **Always trust the higher-indexed-landmark visibility.** Rejected:
  encodes the same hardcoded-right assumption we are removing.
- **Ask the user at upload time which side they are filming.** Rejected:
  every other CV feature is fully automatic; this would add a UX
  burden for a piece of metadata that the system can infer reliably.
- **Use only the first frame.** Rejected: MediaPipe needs several
  frames to stabilise pose tracking; a single-frame visibility check
  is noisier than the 3-second mean.
```

- [ ] **Step 2: Print the diff**

Run: `git diff decisions.md`
Expected: shows the new ADR block.

- [ ] **Step 3: Commit**

```bash
git add decisions.md
git commit -m "docs(adr): add ADR-LIFTER-SIDE-DETECTION (Session 2)"
```

---

### Task 16: Update `backlog.md`

- [ ] **Step 1: Add Session 2 rows**

Locate the cv-audit backlog section in `backlog.md` (under "Active backlog" or similar). Append rows for L2-LIFTER-SIDE-01 through -05 with status `done` and commit SHAs once the PR merges. For now (pre-merge) status is `in_progress` and commit cells stay blank.

- [ ] **Step 2: Commit**

```bash
git add backlog.md
git commit -m "chore(backlog): add Session 2 lifter-side-detection rows"
```

---

### Task 17: Full local verification

- [ ] **Step 1: ruff**

Run: `uv run ruff check backend/app backend/tests`
Expected: `All checks passed!`

- [ ] **Step 2: pyright**

Run: `uv run pyright backend/app`
Expected: `0 errors, 0 warnings, 0 informations`.

- [ ] **Step 3: full pytest with coverage**

Run: `uv run pytest --cov=app --cov-report=term-missing -x`
Expected: every test passes; coverage stays at or above the existing project-wide threshold (Standing Rule #1: never lower).

- [ ] **Step 4: New-file coverage check**

Run: `uv run pytest tests/unit/test_lifter_side.py --cov=app.cv.lifter_side --cov-report=term-missing`
Expected: ≥90% line coverage on `app/cv/lifter_side.py` per Standing Rule #1.

- [ ] **Step 5: Print head-1 lines of all three checks to chat as evidence**

Run separately and pipe the last 5 lines of each into the chat: `ruff`, `pyright`, `pytest`. These satisfy Goal items 4 + 5.

---

### Task 18: Push branch + open PR

- [ ] **Step 1: Push the branch**

Run: `git push -u origin feat/lifter-side-detection`
Expected: branch published to origin.

- [ ] **Step 2: Open PR via GitHub MCP**

Use `mcp__github__create_pull_request` with:

- `title`: `feat(cv): lifter-side detection + landmark-index refactor (Session 2)`
- `head`: `feat/lifter-side-detection`
- `base`: `main`
- `body` (HEREDOC structure):

```
## Summary

- Adds `backend/app/cv/lifter_side.py` with `detect_lifter_side()` and `landmark_indices_for_side()`.
- Refactors `metric_extraction.py` and `signal_processing.py` to look up indices via the new helper. Hardcoded even-index constants removed.
- Adds nullable `analyses.lifter_side VARCHAR(10) CHECK` column (Alembic migration).
- `services/pipeline.py` detects side once per analysis and threads it through Steps 4–6.
- Exposes `lifter_side` on `AnalysisDetail` schema (read-only).

## Detected side per fixture
- `atharva-squat.mov`    → `<DETECTED>`
- `atharva-bench.mov`    → `<DETECTED>`
- `atharva-deadlift.mov` → `<DETECTED>`

## Pre/post-refactor score deltas (calibration gate)
- atharva-squat: ΔOverall <X.X>%, ΔSafety <X.X>%, ΔTechnique <X.X>%, ΔP&B <X.X>%, ΔControl <X.X>%
- atharva-bench: …
- atharva-deadlift: …

Right-side fixtures must stay within ±0.5%. Larger deltas on left-side fixtures are corrections (the old code read offside landmarks); direction documented above.

## Test plan
- [x] `uv run pytest tests/unit/test_lifter_side.py` (new file) all-passing including right/left/ambiguous/anchor cases
- [x] `uv run pytest tests/integration/test_lifter_side_fixtures.py` all-passing across the 3 atharva fixtures
- [x] `uv run pytest tests/unit/test_metric_extraction.py` (UNCHANGED — invariant)
- [x] `uv run pytest tests/unit/test_signal_processing.py` (UNCHANGED — invariant)
- [x] `uv run alembic upgrade head` + `downgrade -1` + `upgrade head` reversible
- [x] `ruff check`, `pyright` clean, coverage ≥ project threshold

## Audit closure
Closes L2-LIFTER-SIDE-01 through -05 per master manifest
`docs/superpowers/goals/2026-05-22-cv-audit-master.md` §Session-2.

## ADR
`ADR-LIFTER-SIDE-DETECTION` appended to `decisions.md`.
```

- [ ] **Step 3: Print the PR URL**

The `html_url` from the MCP response is the evidence required by Goal item 7.

---

### Task 19: CI gate + spelix-auditor

- [ ] **Step 1: Wait for PR-level CI to finish**

Run: `gh pr checks <PR_NUMBER> --watch`
Expected: every line shows `pass`: Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel. Pipe the final `gh pr checks <PR_NUMBER>` output (without `--watch`) into chat as evidence for Goal item 8(a).

- [ ] **Step 2: Dispatch spelix-auditor**

> Use the spelix-auditor agent. Audit PR <PR_NUMBER> diff against FR-CVPL-* (CV pipeline functional requirements). Report CRITICAL / HIGH / MEDIUM with file paths.

Expected: PASS or PASS_WITH_FINDINGS with no CRITICAL.

- [ ] **Step 3: Address any HIGH findings inline**

Per project remediation policy: fix HIGHs in the current branch; commit; push; re-watch CI.

---

### Task 20: Merge + post-deploy verification

- [ ] **Step 1: Merge via GitHub MCP**

Use `mcp__github__merge_pull_request` with:
- `owner`: `atharva6905`
- `repo`: `spelix`
- `pullNumber`: `<PR_NUMBER>`
- `merge_method`: `"merge"` (NEVER `"squash"` — Standing Rule #3)

Expected response: `merged: true`. Print this — it satisfies Goal item 9.

- [ ] **Step 2: Watch the main-branch Deploy to Production**

Run: `gh run list --branch main --workflow="ci" --limit 1`
Capture the run ID, then:

```bash
gh run watch <RUN_ID>
```

Expected: every job concludes `success`, including `Deploy to Production`.

If `--watch` isn't available, use:
```bash
gh run view <RUN_ID> --json jobs --jq '.jobs[] | select(.name=="Deploy to Production") | .conclusion'
```
Expected output: `success`. Pipe this into chat as evidence for Goal item 8(b).

- [ ] **Step 3: SSH verify droplet HEAD**

Run: `ssh spelix-droplet "cd /home/deploy/spelix && git log --oneline -1"`
Expected: matches the merge SHA. Pipe into chat (Goal item 10).

- [ ] **Step 4: Container health**

Run: `ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"`
Expected: `spelix-backend-1 ... (healthy)`, `spelix-worker-1 ... (healthy)`, `spelix-redis-1 ... (healthy)`. Pipe into chat (Goal item 10).

- [ ] **Step 5: Pull main + alembic head**

Run: `git checkout main && git pull --ff-only && uv run alembic current`
Expected: head is the new lifter_side migration revision. Pipe into chat (Goal item 3).

- [ ] **Step 6: E2E pipeline run on prod via Playwright MCP**

Pick `atharva-squat.mov` (well-tested by Session 1). Use Playwright MCP:

```
mcp__playwright__browser_navigate to https://spelix.app
mcp__playwright__browser_snapshot to confirm logged-in state
mcp__playwright__browser_file_upload with the squat fixture
mcp__playwright__browser_wait_for "Analysis complete" (or polling on a known selector)
mcp__playwright__browser_snapshot the results page
mcp__playwright__browser_console_messages level=error to confirm none
mcp__playwright__browser_network_requests to confirm no 4xx/5xx
```

Capture a screenshot to `e2e/screenshots/session-2-lifter-side-e2e-squat.png`.

Compare the rendered form_score_overall (and the 4 sub-scores) on the prod results page against the pre-refactor baseline captured in Task 13 Step 1. Confirm the right-side fixture scores remain within ±0.5%. This satisfies Goal item 11.

---

### Task 21: Update master manifest + handoff for Session 3

- [ ] **Step 1: Update master manifest**

Edit `docs/superpowers/goals/2026-05-22-cv-audit-master.md`:

- In the Session Status Overview table, change Session 2 row to `complete`, fill in the merge SHA and PR number.
- Change Session 3 row to `active`.
- In the Session 2 completion checklist, tick every box.

Run: `git diff docs/superpowers/goals/2026-05-22-cv-audit-master.md`
Expected: shows the updates. Pipe into chat (Goal item 14).

- [ ] **Step 2: Update `.claude/handoff.md`**

Replace the file's contents with a Session 2 → Session 3 handoff per the template in design Section 6:

```markdown
# cv-audit handoff — Session 2 → Session 3

## Status
- **Session 2:** complete — merge SHA `<MERGE_SHA>`, PR #<PR_NUMBER>
- **Next session:** Session 3 — Infrastructure scaffold
- **Launch command:** copy verbatim from `docs/superpowers/goals/2026-05-22-cv-audit-master.md` §Session-3 "Launch command" block into `/goal`.

## Completed this session
- `<SHA>` feat(cv): add lifter-side detection helper (L2-LIFTER-SIDE-01)
- `<SHA>` test(cv): add anchor-based bystander-robustness regression
- `<SHA>` feat(models): add lifter_side column with CHECK constraint (L2-LIFTER-SIDE-02)
- `<SHA>` refactor(cv): route metric_extraction through landmark_indices_for_side (L2-LIFTER-SIDE-03)
- `<SHA>` refactor(cv): route signal_processing through landmark_indices_for_side (L2-LIFTER-SIDE-04)
- `<SHA>` feat(pipeline): detect lifter_side once and thread through CV stages (L2-LIFTER-SIDE-05)
- `<SHA>` feat(schema): expose lifter_side on AnalysisDetail response
- `<SHA>` docs(adr): add ADR-LIFTER-SIDE-DETECTION
- `<SHA>` docs(claude.md): add side-agnostic landmark access gotcha
- `<SHA>` chore(backlog): add Session 2 rows

## Detected sides per fixture
- atharva-squat.mov: <SIDE>
- atharva-bench.mov: <SIDE>
- atharva-deadlift.mov: <SIDE>

## Score deltas (calibration gate)
- All right-side fixtures within ±0.5% (gate met).
- Left-side fixtures (if any): direction + magnitude documented in PR.

## Surfaced evidence
- PR URL: <PR_URL>
- PR-level CI: all 6 checks pass
- Post-merge: Deploy to Production conclusion=success on main run <RUN_ID>
- Droplet HEAD: <merge SHA verified via spelix-droplet>
- Containers: all (healthy)
- Migration head: <new head> (applied locally + via CI deploy)

## Blockers
- None.

## Resume guidance for Session 3
1. Read `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-3.
2. Session 3 plan at `docs/superpowers/plans/2026-05-22-session-3-infrastructure-scaffold.md` is a SKELETON; invoke `superpowers:writing-plans` to expand before launching `/goal`.
3. Issue `/goal` with the Session 3 launch command from the master manifest.
```

- [ ] **Step 3: Commit + push the manifest + handoff**

```bash
git checkout -b docs/session-2-close
git add docs/superpowers/goals/2026-05-22-cv-audit-master.md .claude/handoff.md
git commit -m "docs(session-2-close): mark Session 2 complete, write Session 3 handoff"
git push -u origin docs/session-2-close
```

Open a small follow-up PR via `mcp__github__create_pull_request` and merge it (Standing Rules apply: `merge_method='merge'`, never push direct to `main`).

(Alternative: include the manifest + handoff updates in the main Session 2 PR before merging. Either form satisfies Goal items 14 + 15; the small follow-up PR mirrors Session 1's handoff workflow.)

---

### Task 22: Surface final evidence in chat for /goal verification

The Haiku evaluator checks chat-visible evidence. After every other task is done, ensure the following are all visible in this chat:

- [ ] `git diff backend/app/cv/lifter_side.py` (Goal item 1)
- [ ] `git diff backend/app/cv/metric_extraction.py backend/app/cv/signal_processing.py` (Goal item 2 — shows constants removed)
- [ ] migration file path + `uv run alembic current` output (Goal item 3)
- [ ] `uv run pytest backend/tests/unit/test_metric_extraction.py` + `test_signal_processing.py` outputs showing "passed" with zero assertion diffs (Goal item 4)
- [ ] `uv run pytest backend/tests/unit/test_lifter_side.py` output (Goal item 5)
- [ ] `uv run pytest backend/tests/integration/test_lifter_side_fixtures.py` output + detected sides (Goal item 6)
- [ ] PR URL from `mcp__github__create_pull_request` response (Goal item 7)
- [ ] `gh pr checks <PR>` output (Goal item 8a)
- [ ] `gh run watch <main-run-id>` output OR `gh run view ... --jq` showing Deploy to Production success (Goal item 8b)
- [ ] `mcp__github__merge_pull_request` response with `merged: true` (Goal item 9)
- [ ] SSH `git log --oneline -1` + `docker ps --format` (Goal item 10)
- [ ] Playwright MCP screenshot path (Goal item 11)
- [ ] `git diff decisions.md` (Goal item 12)
- [ ] `git diff backend/CLAUDE.md` (Goal item 13)
- [ ] `git diff docs/superpowers/goals/2026-05-22-cv-audit-master.md` (Goal item 14)
- [ ] `git diff .claude/handoff.md` (Goal item 15)

Any omitted item is treated as not done by the evaluator. Surface them all.

---

## Acceptance criteria

- `backend/app/cv/lifter_side.py` exists, exports `detect_lifter_side()` and `landmark_indices_for_side()`, has ≥90% line coverage.
- `metric_extraction.py` and `signal_processing.py` contain no even-indexed integer literal landmark references; all access goes through `landmark_indices_for_side(side)`.
- New migration adds `analyses.lifter_side VARCHAR(10) CHECK (lifter_side IN ('left','right'))`; reversible.
- All existing tests pass without assertion modifications.
- New unit tests cover right/left/tie/ambiguous-WARN/anchor-robustness/empty/stability.
- Integration tests on 3 atharva fixtures pass; detected sides recorded.
- Right-side fixtures: score deltas ≤ 0.5% on every form_score_* field. Left-side fixtures: deltas documented as corrections in PR.
- `ADR-LIFTER-SIDE-DETECTION` in `decisions.md`.
- `backend/CLAUDE.md` "Side-agnostic landmark access" gotcha block added.
- Master manifest: Session 2 status `complete`; Session 3 status `active`.
- `.claude/handoff.md` rewritten for Session 3 launch.
- PR-level CI all `pass`; post-merge Deploy to Production `success`; droplet HEAD matches merge SHA; containers `(healthy)`; E2E on prod confirms scores stable on a right-side fixture.

---

## Self-Review Notes

- **Spec coverage:** every Session-2 acceptance bullet from design §Session-2 has a matching Task or Step above (detection helper, landmark lookup, refactor, migration, persistence, pipeline plumbing, logging, anchor robustness, fixture integration, score calibration, ADR, CLAUDE.md, manifest, handoff).
- **Placeholder scan:** no TBDs. Every code block contains complete, copy-pasteable code. Commit messages are exact. Expected outputs are concrete.
- **Type consistency:** `SideIndices` NamedTuple fields (`shoulder/elbow/wrist/hip/knee/ankle/heel/foot_index`) used identically in lifter_side.py, metric_extraction.py refactor, signal_processing.py refactor. `lifter_side: Literal["left","right"]` consistent across schema, model, pipeline result, and entry-point signatures. Anchor constant names (`_OFF_ANCHOR_DISTANCE_FRAC=0.25`, `_ANCHOR_FROM_FIRST_N_SAMPLES=3`) match the project pattern from `quality_gates.py` per ADR-QGATE-COMMERCIAL-GYM.
- **Standing-rule compliance:** every test addition is *additive*. No coverage threshold is lowered. No assertion text is mutated on existing tests (Task 7 + 8 explicitly forbid it; Task 12 verifies via `git diff`). `merge_method='merge'` enforced in Task 20. No `--no-verify`, no force-push, no SSH-deploy.
