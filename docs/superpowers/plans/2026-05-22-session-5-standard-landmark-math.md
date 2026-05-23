# Session 5 — Standard Single-Frame Landmark Math Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 7 sagittal-view metrics (8 JSONB keys) that compute an angle, ratio, or signed offset from a small set of landmarks at a specific phase frame. All compute-only — no scoring impact. Compute, persist into `rep_metrics.metrics`, display in the expert `<UnvalidatedMetricsPanel />`.

**Architecture:** Each metric is an additive helper in `backend/app/cv/metric_extraction.py`. All x-direction *signed* metrics are facing-aware via a single `_facing_sign(side)` helper (right→+1, left→−1) so that mirror-flipped left-side input produces equal output to right-side input. Joint-angle metrics are unsigned and naturally side-agnostic. Heel-rise / bar-touch-height / arch use y-only math and are also side-agnostic. The 3 exercise-specific analyzers (`_squat_metrics`, `_bench_metrics`, `_deadlift_metrics`) gain a `lifter_side: Literal["left","right"]` parameter and call the appropriate Session 5 helpers. The Session 3 `sagittal_metrics_registry.py` flips `computed_yet=True` for the 7 entries; `in_scoring` stays `False` (compute-only per design Section-4). No frontend code changes — the registry-driven `UnvalidatedMetricsPanel` already renders any key whose `computed_yet=True` and that exists in `metrics_json`.

**Tech Stack:** Python 3.12, NumPy, pytest, `uv`. No new dependencies. No alembic migration (additive JSONB keys, per design Section-2 "no migrations for Sessions 4-7").

---

## File Structure

### Files to modify

| File | Change | Rough LOC |
|---|---|---|
| `backend/app/cv/metric_extraction.py` | Add 7 pure helper functions + `_facing_sign(side)`; extend `_squat_metrics`/`_bench_metrics`/`_deadlift_metrics` to receive `lifter_side` + wire helpers into the returned dict; thread `lifter_side` through the dispatch loop in `extract_rep_metrics`. | +250 |
| `backend/app/cv/sagittal_metrics_registry.py` | Flip `computed_yet=True` on 7 entries (#1, #3, #5, #10, #11, #13, #15). | +7 |
| `backend/tests/unit/test_metric_extraction_sagittal.py` | Append `test_session5_*` tests: per-metric happy/edge/degenerate, side-agnosticism mirror tests, per-exercise analyzer integration. | +600 |
| `backend/tests/integration/test_pipeline_sagittal_metrics.py` (NEW) | Per-fixture integration: squat fixture for #1+#11, bench fixture for #3+#5+#15, deadlift fixture for #10+#13. | +300 |
| `backend/scripts/oneoff/smoke_sagittal_metrics_session5.py` (NEW) | Manual calibration helper — load each of the 3 atharva fixtures, run pose → rep detection → metric extraction, dump a CSV of per-rep Session-5 values. Not run in CI. | +120 |

### Files explicitly NOT touched

- `backend/app/cv/scoring.py` — no scoring branches this session.
- `config/thresholds_v1.json` — no threshold entries (post-onboarding decision per design Section-4 "Pattern notes").
- `frontend/` — registry-driven `UnvalidatedMetricsPanel` auto-renders new computed rows; no React changes required.
- `backend/app/services/pipeline.py::_aggregate_rep_metrics` — Session 5 keys are per-rep only and consumed by the expert panel via `metrics_json`, not by scoring. No aggregator changes.
- `decisions.md` — no new ADR (Session 5 is pure extension of patterns established in Sessions 2 + 4; the facing-sign convention is a one-line addition documented inline + in `backend/CLAUDE.md`).
- `backend/CLAUDE.md` — one-paragraph addendum to the existing "Side-agnostic landmark access" gotcha noting `_facing_sign` for x-signed metrics; not its own section.

---

## Standing Rules in force (from master manifest)

- Never lower a quality gate (coverage, lint, pyright, security audit). Use `# pragma: no cover` with a one-line justification for genuinely untestable lines.
- Never skip hooks (`--no-verify`, `--no-gpg-sign`).
- Never squash-merge — always `merge_method: "merge"`.
- Never auto-deploy via SSH — wait for the CI "Deploy to Production" step.

---

## Tasks

### Task 1: Create feature branch

**Files:** none (git only).

- [ ] **Step 1: Branch from `main`**

```bash
git checkout main && git pull
git checkout -b feat/sagittal-standard-metrics
```

- [ ] **Step 2: Verify clean state**

```bash
git status --short
```

Expected: empty output (or only untracked screenshots/graphify artifacts that are gitignored). If real working-tree changes exist, stash them first.

---

### Task 2: Add `_facing_sign` helper + extend analyzer signatures to receive `lifter_side` (TDD)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py`

The 4 signed Session-5 helpers (#3, #10, #11, #15) need to know which way the lifter faces so the mirror tests can assert equality across left/right. The simplest threading is to pass `lifter_side: Literal["left","right"]` as a new parameter on each `_*_metrics` analyzer and call the helpers from there.

- [ ] **Step 1: Write the failing test** — append to `backend/tests/unit/test_metric_extraction_sagittal.py`

```python
# ---------------------------------------------------------------------------
# Session 5 — facing-sign helper
# ---------------------------------------------------------------------------


def test_session5_facing_sign_right_is_positive_one() -> None:
    from app.cv.metric_extraction import _facing_sign
    assert _facing_sign("right") == 1.0


def test_session5_facing_sign_left_is_negative_one() -> None:
    from app.cv.metric_extraction import _facing_sign
    assert _facing_sign("left") == -1.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py::test_session5_facing_sign_right_is_positive_one -xvs
```

Expected: `ImportError` or `AttributeError: module 'app.cv.metric_extraction' has no attribute '_facing_sign'`.

- [ ] **Step 3: Add the helper** in `backend/app/cv/metric_extraction.py` (place immediately after `_xy` and before `_torso_lean_deg`):

```python
def _facing_sign(side: Literal["left", "right"]) -> float:
    """Return +1.0 if the lifter faces right in the image, -1.0 if left.

    Multiplies x-direction signed metrics (wrist_alignment_deg, shin_angle_deg,
    setup_shoulder_x_offset, arch_deg) so the same pose filmed from either side
    produces the same signed output. Without this, swapping side indices alone
    flips the sign of every x-derived value because anterior-posterior direction
    in image coordinates depends on which way the subject faces.

    See ADR-LIFTER-SIDE-DETECTION (Session 2) and design Section 5 mirror tests.
    """
    return 1.0 if side == "right" else -1.0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py::test_session5_facing_sign_right_is_positive_one tests/unit/test_metric_extraction_sagittal.py::test_session5_facing_sign_left_is_negative_one -xvs
```

Expected: 2 passed.

- [ ] **Step 5: Extend analyzer signatures to thread `lifter_side`** — replace the three analyzer signatures and the dispatch loop in `backend/app/cv/metric_extraction.py`:

```python
def _squat_metrics(
    rep: DetectedRep,
    landmarks_per_frame: list[np.ndarray],
    angle_timeseries: dict[str, np.ndarray],
    fps: float,
    side_idx: SideIndices,
    lifter_side: Literal["left", "right"] = "right",
) -> dict[str, float | str]:
```

Same change for `_bench_metrics` and `_deadlift_metrics`. Then in `extract_rep_metrics`:

```python
side_idx = landmark_indices_for_side(lifter_side)

result: list[RepMetrics] = []
for rep in reps:
    metrics = analyzer(
        rep, landmarks_per_frame, angle_timeseries, fps, side_idx, lifter_side,
    )
    result.append(...)
```

- [ ] **Step 6: Verify the existing Session 4 + earlier tests are still green** (no assertion modifications)

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction.py tests/unit/test_metric_extraction_sagittal.py -x
```

Expected: ALL existing tests pass (signatures default `lifter_side="right"` to preserve behaviour).

- [ ] **Step 7: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): _facing_sign helper + thread lifter_side through analyzers (Session 5 prelude)"
```

---

### Task 3: Implement #1 `ankle_dorsiflexion_deg` + `heel_rise_flag` (squat, TDD)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py`

Per design Section-4:
- `ankle_dorsiflexion_deg`: angle at `S_ankle` between the `S_knee` vector and the `S_foot_index` vector, at rep-bottom (min-hip-angle frame). Stored as the raw joint angle (per registry description "90 minus this is dorsiflexion magnitude"). Joint angles are unsigned → side-agnostic.
- `heel_rise_flag`: baseline = mean `S_heel-y` over the first 5 frames of the rep. Flag true if `S_heel-y < baseline - 0.02` for ≥3 **consecutive** frames during descent (`start` → `depth_frame`). In MediaPipe normalised space, y increases downward, so "heel rises in image" = "heel_y decreases" = "heel_y below baseline". Frame-height is 1.0 in normalised coords, so the threshold is literally `baseline - 0.02`.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------------------
# Session 5 #1 — ankle_dorsiflexion_deg + heel_rise_flag (squat)
# ---------------------------------------------------------------------------


def _make_squat_bottom_frame(
    *,
    knee_xy: tuple[float, float],
    ankle_xy: tuple[float, float],
    foot_index_xy: tuple[float, float],
    heel_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    """Build a single (33, 5) frame with the four squat-bottom landmarks set."""
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9    # visibility
    lm[:, 4] = 5.0    # presence pre-sigmoid → ~1.0 (col-4 gotcha)
    idx = landmark_indices_for_side(side)
    lm[idx.knee, :2] = knee_xy
    lm[idx.ankle, :2] = ankle_xy
    lm[idx.foot_index, :2] = foot_index_xy
    lm[idx.heel, :2] = heel_xy
    return lm


def test_session5_ankle_dorsiflexion_textbook_squat() -> None:
    """Vertical shin + horizontal foot → ankle joint angle ≈ 90°."""
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_squat_bottom_frame(
        knee_xy=(0.5, 0.55),         # knee directly above ankle
        ankle_xy=(0.5, 0.90),
        foot_index_xy=(0.65, 0.90),  # foot forward at same y
        heel_xy=(0.42, 0.90),
    )
    angle = _ankle_dorsiflexion_deg(frame, right_idx)
    assert angle == pytest.approx(90.0, abs=2.0)


def test_session5_ankle_dorsiflexion_forward_knee_travel() -> None:
    """Knee forward of ankle (deep squat dorsiflexion) → ankle angle < 90°."""
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_squat_bottom_frame(
        knee_xy=(0.65, 0.55),        # knee 0.15 forward of ankle
        ankle_xy=(0.5, 0.90),
        foot_index_xy=(0.65, 0.90),
        heel_xy=(0.42, 0.90),
    )
    angle = _ankle_dorsiflexion_deg(frame, right_idx)
    # Knee vector (0.15, -0.35) and foot vector (0.15, 0). Dot product positive,
    # smaller angle than the vertical-shin case.
    assert angle < 90.0
    assert angle > 0.0


def test_session5_ankle_dorsiflexion_low_visibility_returns_none() -> None:
    """Any required landmark below visibility 0.30 → None."""
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_squat_bottom_frame(
        knee_xy=(0.5, 0.55), ankle_xy=(0.5, 0.90),
        foot_index_xy=(0.65, 0.90), heel_xy=(0.42, 0.90),
    )
    frame[right_idx.ankle, 3] = 0.10  # ankle visibility crashed
    assert _ankle_dorsiflexion_deg(frame, right_idx) is None


def test_session5_ankle_dorsiflexion_degenerate_zero_vector_returns_none() -> None:
    """Zero-length knee vector (knee == ankle) → None, no exception."""
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_squat_bottom_frame(
        knee_xy=(0.5, 0.90),         # coincident with ankle
        ankle_xy=(0.5, 0.90),
        foot_index_xy=(0.65, 0.90),
        heel_xy=(0.42, 0.90),
    )
    assert _ankle_dorsiflexion_deg(frame, right_idx) is None


@pytest.mark.parametrize("knee_dx", [0.0, 0.10, 0.15, 0.20])
def test_session5_ankle_dorsiflexion_side_agnostic(knee_dx: float) -> None:
    """Same pose populated on either side (x mirrored on left) → same angle."""
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frame = _make_squat_bottom_frame(
        knee_xy=(0.5 + knee_dx, 0.55),
        ankle_xy=(0.5, 0.90),
        foot_index_xy=(0.65, 0.90),
        heel_xy=(0.42, 0.90),
        side="right",
    )
    left_frame = _make_squat_bottom_frame(
        knee_xy=(1.0 - (0.5 + knee_dx), 0.55),
        ankle_xy=(1.0 - 0.5, 0.90),
        foot_index_xy=(1.0 - 0.65, 0.90),
        heel_xy=(1.0 - 0.42, 0.90),
        side="left",
    )
    right_angle = _ankle_dorsiflexion_deg(right_frame, right_idx)
    left_angle = _ankle_dorsiflexion_deg(left_frame, left_idx)
    assert right_angle is not None and left_angle is not None
    assert right_angle == pytest.approx(left_angle, abs=0.5)


# heel_rise_flag tests ------------------------------------------------------


def _make_heel_y_series(
    n_frames: int,
    *,
    baseline_y: float = 0.90,
    rise_start: int | None = None,
    rise_amount: float = 0.05,
    rise_frames: int = 5,
) -> list[np.ndarray]:
    """Build n_frames worth of (33,5) arrays with right-heel y populated."""
    right_idx = landmark_indices_for_side("right")
    frames: list[np.ndarray] = []
    for i in range(n_frames):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        y = baseline_y
        if rise_start is not None and rise_start <= i < rise_start + rise_frames:
            y = baseline_y - rise_amount  # heel moved up in image
        lm[right_idx.heel, :2] = (0.42, y)
        frames.append(lm)
    return frames


def test_session5_heel_rise_textbook_squat_no_rise() -> None:
    """Heel stays at baseline → flag False."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    frames = _make_heel_y_series(20)
    assert _heel_rise_flag(frames, start=0, depth_frame=15, side_idx=right_idx) is False


def test_session5_heel_rise_sustained_rise_above_threshold() -> None:
    """Heel rises by 0.05 (> 0.02 threshold) for 5 consecutive frames → True."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    frames = _make_heel_y_series(
        20, rise_start=8, rise_amount=0.05, rise_frames=5,
    )
    assert _heel_rise_flag(frames, start=0, depth_frame=15, side_idx=right_idx) is True


def test_session5_heel_rise_noise_spike_under_three_frames() -> None:
    """Heel rises by 0.05 but for only 2 consecutive frames → False (noise)."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    frames = _make_heel_y_series(
        20, rise_start=8, rise_amount=0.05, rise_frames=2,
    )
    assert _heel_rise_flag(frames, start=0, depth_frame=15, side_idx=right_idx) is False


def test_session5_heel_rise_below_threshold_returns_false() -> None:
    """Heel rises by 0.01 (< 0.02 threshold) for many frames → False."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    frames = _make_heel_y_series(
        20, rise_start=8, rise_amount=0.01, rise_frames=6,
    )
    assert _heel_rise_flag(frames, start=0, depth_frame=15, side_idx=right_idx) is False


def test_session5_heel_rise_degenerate_short_rep() -> None:
    """start == depth_frame (rep too short for baseline) → False, no exception."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    frames = _make_heel_y_series(10)
    assert _heel_rise_flag(frames, start=5, depth_frame=5, side_idx=right_idx) is False


def test_session5_heel_rise_side_agnostic() -> None:
    """Same rise pattern on right-heel vs mirrored left-heel → same flag."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frames = _make_heel_y_series(
        20, rise_start=8, rise_amount=0.05, rise_frames=5,
    )
    # Build a mirrored left-side variant: same y dynamic, mirrored x, populated
    # at the left-heel index.
    left_frames: list[np.ndarray] = []
    for i, rf in enumerate(right_frames):
        lf = np.zeros((33, 5), dtype=float)
        lf[:, 3] = 0.9
        lf[:, 4] = 5.0
        rx, ry = rf[right_idx.heel, 0], rf[right_idx.heel, 1]
        lf[left_idx.heel, :2] = (1.0 - rx, ry)
        left_frames.append(lf)
    right_flag = _heel_rise_flag(right_frames, start=0, depth_frame=15, side_idx=right_idx)
    left_flag = _heel_rise_flag(left_frames, start=0, depth_frame=15, side_idx=left_idx)
    assert right_flag == left_flag is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and (ankle_dorsiflexion or heel_rise)" -xvs
```

Expected: all tests fail with `AttributeError` on `_ankle_dorsiflexion_deg` / `_heel_rise_flag`.

- [ ] **Step 3: Implement the helpers** — append to `backend/app/cv/metric_extraction.py`:

```python
# ---------------------------------------------------------------------------
# Session 5 helpers — sagittal-view single-frame landmark math
# ---------------------------------------------------------------------------

# Visibility threshold for required landmarks (matches the registry's
# "return None on missing landmark" convention).
_S5_MIN_VIS = 0.30
_S5_DEGENERATE_MAGNITUDE = 1e-6


def _vis_ok(landmarks: np.ndarray, *indices: int) -> bool:
    """Return True iff every named landmark has visibility >= _S5_MIN_VIS."""
    return all(float(landmarks[i, 3]) >= _S5_MIN_VIS for i in indices)


def _ankle_dorsiflexion_deg(
    landmarks: np.ndarray,
    side_idx: SideIndices,
) -> float | None:
    """Session 5 #1 — joint angle at S_ankle between S_knee and S_foot_index.

    Stored as the raw joint angle (registry description: "90 minus this is
    dorsiflexion magnitude"). Returns None on missing landmark or degenerate
    zero-length vector. Side-agnostic (joint-angle math).
    """
    if not _vis_ok(landmarks, side_idx.knee, side_idx.ankle, side_idx.foot_index):
        return None
    knee = _xy(landmarks, side_idx.knee)
    ankle = _xy(landmarks, side_idx.ankle)
    foot = _xy(landmarks, side_idx.foot_index)
    v_kn = knee - ankle
    v_ft = foot - ankle
    mag_kn = float(np.linalg.norm(v_kn))
    mag_ft = float(np.linalg.norm(v_ft))
    if mag_kn < _S5_DEGENERATE_MAGNITUDE or mag_ft < _S5_DEGENERATE_MAGNITUDE:
        return None
    cos_t = float(np.clip(np.dot(v_kn, v_ft) / (mag_kn * mag_ft), -1.0, 1.0))
    return float(np.degrees(np.arccos(cos_t)))


def _heel_rise_flag(
    landmarks_per_frame: list[np.ndarray],
    start: int,
    depth_frame: int,
    side_idx: SideIndices,
    baseline_frames: int = 5,
    rise_threshold: float = 0.02,
    consecutive_frames: int = 3,
) -> bool:
    """Session 5 #1 companion — True if S_heel-y stays below baseline by more
    than ``rise_threshold`` for ``consecutive_frames`` or more during descent.

    Baseline is the mean S_heel-y over the first ``baseline_frames`` of the rep
    (frames ``start`` .. ``start + baseline_frames - 1``). Descent is
    ``start + baseline_frames`` .. ``depth_frame`` inclusive. Frame height is
    1.0 in MediaPipe normalised space, so the threshold is literally
    ``baseline - rise_threshold`` (a heel rising in image = heel_y decreasing).

    Degenerate input (rep too short to span baseline + a descent window,
    out-of-bounds frames) returns False with no exception.
    """
    n = len(landmarks_per_frame)
    if start < 0 or depth_frame >= n or depth_frame <= start + baseline_frames:
        return False
    heel_idx = side_idx.heel
    baseline_ys: list[float] = []
    for k in range(start, start + baseline_frames):
        f = landmarks_per_frame[k]
        if float(f[heel_idx, 3]) < _S5_MIN_VIS:
            continue
        baseline_ys.append(float(f[heel_idx, 1]))
    if len(baseline_ys) == 0:
        return False
    baseline_y = float(np.mean(baseline_ys))
    triggered = 0
    for k in range(start + baseline_frames, depth_frame + 1):
        f = landmarks_per_frame[k]
        if float(f[heel_idx, 3]) < _S5_MIN_VIS:
            triggered = 0
            continue
        if float(f[heel_idx, 1]) < baseline_y - rise_threshold:
            triggered += 1
            if triggered >= consecutive_frames:
                return True
        else:
            triggered = 0
    return False
```

- [ ] **Step 4: Run the new tests**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and (ankle_dorsiflexion or heel_rise)" -xvs
```

Expected: all tests pass (11 cases).

- [ ] **Step 5: Wire into `_squat_metrics`** — inside the analyzer body, after `lockout_torso_lean` is computed:

```python
    ankle_dorsiflexion = _ankle_dorsiflexion_deg(landmarks_per_frame[depth_frame], side_idx)
    heel_rise = _heel_rise_flag(landmarks_per_frame, start, depth_frame, side_idx)
```

And add to the returned dict:

```python
        "ankle_dorsiflexion_deg": (
            float(ankle_dorsiflexion) if ankle_dorsiflexion is not None else 0.0
        ),
        "heel_rise_flag": float(heel_rise),
```

(Stored as a `float` 0.0/1.0 because `RepMetrics.metrics: dict[str, float | str]` — the JSONB key is `heel_rise_flag` and a 1.0 vs 0.0 value is read by the panel as boolean. We deliberately use 0.0 rather than `False` to stay within the existing widened type; ADR-022.)

When `ankle_dorsiflexion` is `None` (missing landmarks), we write `0.0` — consistent with the Session 4 "use 0.0 sentinel for missing key" approach in `ecc_con_ratio` and the panel reads "—" because the registry entry's display layer ignores 0.0 sentinels via `_extractValue`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): #1 ankle_dorsiflexion_deg + heel_rise_flag extractors (Session 5)"
```

---

### Task 4: Implement #3 `wrist_alignment_deg` (bench, TDD)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py`

Per design Section-4: `atan2(wrist_x - elbow_x, elbow_y - wrist_y)` in degrees. 0° = wrist stacked over elbow. Positive = wrist anterior to elbow. The "anterior" sign depends on which way the lifter faces in the image → multiply `dx` by `_facing_sign(side)` so left-side-filmed analyses produce the same signed value as right-side-filmed.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------------------
# Session 5 #3 — wrist_alignment_deg (bench)
# ---------------------------------------------------------------------------


def _make_bench_bottom_frame(
    *,
    wrist_xy: tuple[float, float],
    elbow_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.wrist, :2] = wrist_xy
    lm[idx.elbow, :2] = elbow_xy
    return lm


def test_session5_wrist_alignment_stacked() -> None:
    """Wrist directly above elbow → 0°."""
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_bottom_frame(wrist_xy=(0.50, 0.40), elbow_xy=(0.50, 0.55))
    assert _wrist_alignment_deg(frame, right_idx, "right") == pytest.approx(0.0, abs=0.5)


def test_session5_wrist_alignment_anterior() -> None:
    """Wrist forward of elbow (right-facing) → positive angle."""
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    dy = 0.15
    dx = dy * math.tan(math.radians(20.0))
    frame = _make_bench_bottom_frame(
        wrist_xy=(0.50 + dx, 0.40), elbow_xy=(0.50, 0.55),
    )
    assert _wrist_alignment_deg(frame, right_idx, "right") == pytest.approx(20.0, abs=0.5)


def test_session5_wrist_alignment_posterior_negative() -> None:
    """Wrist behind elbow (right-facing) → negative angle."""
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    dy = 0.15
    dx = dy * math.tan(math.radians(10.0))
    frame = _make_bench_bottom_frame(
        wrist_xy=(0.50 - dx, 0.40), elbow_xy=(0.50, 0.55),
    )
    assert _wrist_alignment_deg(frame, right_idx, "right") == pytest.approx(-10.0, abs=0.5)


def test_session5_wrist_alignment_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_bottom_frame(wrist_xy=(0.50, 0.40), elbow_xy=(0.50, 0.55))
    frame[right_idx.wrist, 3] = 0.05
    assert _wrist_alignment_deg(frame, right_idx, "right") is None


def test_session5_wrist_alignment_degenerate_coincident_returns_none() -> None:
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_bottom_frame(wrist_xy=(0.50, 0.55), elbow_xy=(0.50, 0.55))
    assert _wrist_alignment_deg(frame, right_idx, "right") is None


@pytest.mark.parametrize("anterior_deg", [-20.0, -5.0, 0.0, 5.0, 20.0])
def test_session5_wrist_alignment_side_agnostic(anterior_deg: float) -> None:
    """Same pose right-vs-mirrored-left → same signed angle (facing-sign applied)."""
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    dy = 0.15
    dx = dy * math.tan(math.radians(anterior_deg))
    right_frame = _make_bench_bottom_frame(
        wrist_xy=(0.50 + dx, 0.40), elbow_xy=(0.50, 0.55), side="right",
    )
    left_frame = _make_bench_bottom_frame(
        wrist_xy=(1.0 - (0.50 + dx), 0.40),
        elbow_xy=(1.0 - 0.50, 0.55),
        side="left",
    )
    r = _wrist_alignment_deg(right_frame, right_idx, "right")
    L = _wrist_alignment_deg(left_frame, left_idx, "left")
    assert r is not None and L is not None
    assert r == pytest.approx(L, abs=0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and wrist_alignment" -xvs
```

Expected: tests fail with `AttributeError: ... _wrist_alignment_deg`.

- [ ] **Step 3: Implement the helper** — append to `backend/app/cv/metric_extraction.py`:

```python
def _wrist_alignment_deg(
    landmarks: np.ndarray,
    side_idx: SideIndices,
    side: Literal["left", "right"],
) -> float | None:
    """Session 5 #3 — sagittal-plane wrist-elbow stacking angle at bench bottom.

    ``atan2((wrist_x - elbow_x) * facing_sign, elbow_y - wrist_y)`` in degrees.
    0° = wrist stacked vertically over elbow. Positive = wrist anterior to
    elbow (regardless of which side filmed the lifter). Returns None on missing
    landmark or degenerate (coincident wrist/elbow) input.
    """
    if not _vis_ok(landmarks, side_idx.wrist, side_idx.elbow):
        return None
    wrist = _xy(landmarks, side_idx.wrist)
    elbow = _xy(landmarks, side_idx.elbow)
    dx = (float(wrist[0]) - float(elbow[0])) * _facing_sign(side)
    dy = float(elbow[1]) - float(wrist[1])
    if abs(dx) < _S5_DEGENERATE_MAGNITUDE and abs(dy) < _S5_DEGENERATE_MAGNITUDE:
        return None
    return float(np.degrees(np.arctan2(dx, dy)))
```

- [ ] **Step 4: Run the new tests**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and wrist_alignment" -xvs
```

Expected: all 9 cases pass (5 parametrised side-agnostic + 4 happy/edge).

- [ ] **Step 5: Wire into `_bench_metrics`** — locate the bench analyzer; after `pause_duration`:

```python
    wrist_alignment = _wrist_alignment_deg(
        landmarks_per_frame[bottom_frame], side_idx, lifter_side,
    )
```

And in the returned dict:

```python
        "wrist_alignment_deg": (
            float(wrist_alignment) if wrist_alignment is not None else 0.0
        ),
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): #3 wrist_alignment_deg extractor (Session 5)"
```

---

### Task 5: Implement #5 `bar_touch_height_pct` (bench, TDD)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py`

Per design Section-4: `(wrist_y - shoulder_y) / (hip_y - shoulder_y)`. 0.0 = wrist at shoulder height, 1.0 = wrist at hip height. Y-only math → side-agnostic. Returns None on degenerate `shoulder_y == hip_y`.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------------------
# Session 5 #5 — bar_touch_height_pct (bench)
# ---------------------------------------------------------------------------


def _make_bench_touch_frame(
    *,
    wrist_y: float,
    shoulder_y: float,
    hip_y: float,
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.wrist, :2] = (0.30, wrist_y)
    lm[idx.shoulder, :2] = (0.50, shoulder_y)
    lm[idx.hip, :2] = (0.55, hip_y)
    return lm


def test_session5_bar_touch_height_at_shoulder() -> None:
    """wrist_y == shoulder_y → 0.0."""
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_touch_frame(wrist_y=0.40, shoulder_y=0.40, hip_y=0.60)
    assert _bar_touch_height_pct(frame, right_idx) == pytest.approx(0.0, abs=1e-6)


def test_session5_bar_touch_height_midway() -> None:
    """wrist halfway between shoulder and hip → 0.5."""
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_touch_frame(wrist_y=0.50, shoulder_y=0.40, hip_y=0.60)
    assert _bar_touch_height_pct(frame, right_idx) == pytest.approx(0.5, abs=1e-6)


def test_session5_bar_touch_height_at_hip() -> None:
    """wrist at hip level → 1.0."""
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_touch_frame(wrist_y=0.60, shoulder_y=0.40, hip_y=0.60)
    assert _bar_touch_height_pct(frame, right_idx) == pytest.approx(1.0, abs=1e-6)


def test_session5_bar_touch_height_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_touch_frame(wrist_y=0.50, shoulder_y=0.40, hip_y=0.60)
    frame[right_idx.hip, 3] = 0.10
    assert _bar_touch_height_pct(frame, right_idx) is None


def test_session5_bar_touch_height_degenerate_shoulder_eq_hip_returns_none() -> None:
    """shoulder_y == hip_y (zero span) → None, no division by zero."""
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_touch_frame(wrist_y=0.50, shoulder_y=0.50, hip_y=0.50)
    assert _bar_touch_height_pct(frame, right_idx) is None


def test_session5_bar_touch_height_side_agnostic() -> None:
    """Same y-coordinates on either side → same ratio (y-only math)."""
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frame = _make_bench_touch_frame(
        wrist_y=0.50, shoulder_y=0.40, hip_y=0.60, side="right",
    )
    left_frame = _make_bench_touch_frame(
        wrist_y=0.50, shoulder_y=0.40, hip_y=0.60, side="left",
    )
    r = _bar_touch_height_pct(right_frame, right_idx)
    L = _bar_touch_height_pct(left_frame, left_idx)
    assert r == pytest.approx(L, abs=1e-9)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and bar_touch_height" -xvs
```

Expected: fail with `AttributeError: ... _bar_touch_height_pct`.

- [ ] **Step 3: Implement the helper** — append to `backend/app/cv/metric_extraction.py`:

```python
def _bar_touch_height_pct(
    landmarks: np.ndarray,
    side_idx: SideIndices,
) -> float | None:
    """Session 5 #5 — bench bar-touch y relative to shoulder-hip span.

    ``(wrist_y - shoulder_y) / (hip_y - shoulder_y)``. 0.0 = touching at
    shoulder, 1.0 = at hip. Returns None on missing landmark or zero-span
    (``shoulder_y == hip_y``). Y-only math → side-agnostic.
    """
    if not _vis_ok(landmarks, side_idx.wrist, side_idx.shoulder, side_idx.hip):
        return None
    wrist_y = float(landmarks[side_idx.wrist, 1])
    shoulder_y = float(landmarks[side_idx.shoulder, 1])
    hip_y = float(landmarks[side_idx.hip, 1])
    span = hip_y - shoulder_y
    if abs(span) < _S5_DEGENERATE_MAGNITUDE:
        return None
    return float((wrist_y - shoulder_y) / span)
```

- [ ] **Step 4: Run the new tests**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and bar_touch_height" -xvs
```

Expected: 6 cases pass.

- [ ] **Step 5: Wire into `_bench_metrics`** — after `wrist_alignment`:

```python
    bar_touch_height = _bar_touch_height_pct(landmarks_per_frame[bottom_frame], side_idx)
```

And in the returned dict:

```python
        "bar_touch_height_pct": (
            float(bar_touch_height) if bar_touch_height is not None else 0.0
        ),
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): #5 bar_touch_height_pct extractor (Session 5)"
```

---

### Task 6: Implement #10 `setup_shoulder_x_offset` (deadlift, TDD)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py`

Per design Section-4: `(shoulder_x - wrist_x) * facing_sign / forearm_length` where `forearm_length = sqrt((wrist_x - elbow_x)² + (wrist_y - elbow_y)²)`. Single value per session, computed at the first frame of the lift (= rep[0].start_frame). Positive = shoulders forward of wrist (over the bar). Returns None on degenerate forearm length.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------------------
# Session 5 #10 — setup_shoulder_x_offset (deadlift)
# ---------------------------------------------------------------------------


def _make_dl_setup_frame(
    *,
    shoulder_xy: tuple[float, float],
    wrist_xy: tuple[float, float],
    elbow_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.shoulder, :2] = shoulder_xy
    lm[idx.wrist, :2] = wrist_xy
    lm[idx.elbow, :2] = elbow_xy
    return lm


def test_session5_setup_shoulder_offset_over_bar() -> None:
    """Shoulders directly above wrist → offset ≈ 0."""
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_setup_frame(
        shoulder_xy=(0.50, 0.30),
        wrist_xy=(0.50, 0.85),
        elbow_xy=(0.50, 0.60),  # forearm length ~0.25, vertical
    )
    val = _setup_shoulder_x_offset(frame, right_idx, "right")
    assert val == pytest.approx(0.0, abs=0.02)


def test_session5_setup_shoulder_offset_shoulders_ahead() -> None:
    """Shoulders 0.05 forward of wrist, forearm ≈ 0.25 → +0.20 normalised."""
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_setup_frame(
        shoulder_xy=(0.55, 0.30),     # 0.05 forward of wrist
        wrist_xy=(0.50, 0.85),
        elbow_xy=(0.50, 0.60),         # forearm length 0.25
    )
    val = _setup_shoulder_x_offset(frame, right_idx, "right")
    assert val == pytest.approx(0.05 / 0.25, abs=0.02)


def test_session5_setup_shoulder_offset_shoulders_behind_negative() -> None:
    """Shoulders behind wrist (right-facing) → negative offset."""
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_setup_frame(
        shoulder_xy=(0.45, 0.30),
        wrist_xy=(0.50, 0.85),
        elbow_xy=(0.50, 0.60),
    )
    val = _setup_shoulder_x_offset(frame, right_idx, "right")
    assert val < 0.0
    assert val == pytest.approx(-0.05 / 0.25, abs=0.02)


def test_session5_setup_shoulder_offset_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_setup_frame(
        shoulder_xy=(0.55, 0.30), wrist_xy=(0.50, 0.85), elbow_xy=(0.50, 0.60),
    )
    frame[right_idx.elbow, 3] = 0.10
    assert _setup_shoulder_x_offset(frame, right_idx, "right") is None


def test_session5_setup_shoulder_offset_zero_forearm_returns_none() -> None:
    """elbow == wrist → forearm length 0 → None."""
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_setup_frame(
        shoulder_xy=(0.55, 0.30),
        wrist_xy=(0.50, 0.85),
        elbow_xy=(0.50, 0.85),  # coincident with wrist
    )
    assert _setup_shoulder_x_offset(frame, right_idx, "right") is None


@pytest.mark.parametrize("shoulder_dx", [-0.05, -0.02, 0.0, 0.02, 0.05])
def test_session5_setup_shoulder_offset_side_agnostic(shoulder_dx: float) -> None:
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frame = _make_dl_setup_frame(
        shoulder_xy=(0.50 + shoulder_dx, 0.30),
        wrist_xy=(0.50, 0.85),
        elbow_xy=(0.50, 0.60),
        side="right",
    )
    left_frame = _make_dl_setup_frame(
        shoulder_xy=(1.0 - (0.50 + shoulder_dx), 0.30),
        wrist_xy=(1.0 - 0.50, 0.85),
        elbow_xy=(1.0 - 0.50, 0.60),
        side="left",
    )
    r = _setup_shoulder_x_offset(right_frame, right_idx, "right")
    L = _setup_shoulder_x_offset(left_frame, left_idx, "left")
    assert r is not None and L is not None
    assert r == pytest.approx(L, abs=0.02)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and setup_shoulder" -xvs
```

Expected: 10 cases fail with `AttributeError: ... _setup_shoulder_x_offset`.

- [ ] **Step 3: Implement the helper** — append:

```python
def _setup_shoulder_x_offset(
    landmarks: np.ndarray,
    side_idx: SideIndices,
    side: Literal["left", "right"],
) -> float | None:
    """Session 5 #10 — deadlift shoulder-x offset from wrist-x at the first
    lift frame, normalised by forearm length.

    ``((shoulder_x - wrist_x) * facing_sign) / forearm_length`` where forearm
    length is ``hypot(wrist_x - elbow_x, wrist_y - elbow_y)``. Positive =
    shoulders over the bar (anterior of the wrist) regardless of filmed side.
    Returns None on missing landmark or zero-length forearm.
    """
    if not _vis_ok(landmarks, side_idx.shoulder, side_idx.wrist, side_idx.elbow):
        return None
    shoulder = _xy(landmarks, side_idx.shoulder)
    wrist = _xy(landmarks, side_idx.wrist)
    elbow = _xy(landmarks, side_idx.elbow)
    forearm_len = float(np.hypot(wrist[0] - elbow[0], wrist[1] - elbow[1]))
    if forearm_len < _S5_DEGENERATE_MAGNITUDE:
        return None
    raw_offset = float(shoulder[0]) - float(wrist[0])
    return (raw_offset * _facing_sign(side)) / forearm_len
```

- [ ] **Step 4: Run the new tests**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and setup_shoulder" -xvs
```

Expected: 10 cases pass.

- [ ] **Step 5: Wire into `_deadlift_metrics`** — after `lockout_torso_lean`:

```python
    setup_shoulder_offset = _setup_shoulder_x_offset(
        landmarks_per_frame[start], side_idx, lifter_side,
    )
```

And in the returned dict:

```python
        "setup_shoulder_x_offset": (
            float(setup_shoulder_offset) if setup_shoulder_offset is not None else 0.0
        ),
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): #10 setup_shoulder_x_offset extractor (Session 5)"
```

---

### Task 7: Implement #11 `shin_angle_deg` (squat, TDD)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py`

Per design Section-4: `atan2((knee_x - ankle_x) * facing_sign, ankle_y - knee_y)`. 0° = vertical shin; positive = forward lean. Returns None on degenerate input.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------------------
# Session 5 #11 — shin_angle_deg (squat)
# ---------------------------------------------------------------------------


def _make_shin_frame(
    *,
    knee_xy: tuple[float, float],
    ankle_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.knee, :2] = knee_xy
    lm[idx.ankle, :2] = ankle_xy
    return lm


def test_session5_shin_angle_vertical() -> None:
    """Knee directly above ankle → 0°."""
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_shin_frame(knee_xy=(0.50, 0.55), ankle_xy=(0.50, 0.90))
    assert _shin_angle_deg(frame, right_idx, "right") == pytest.approx(0.0, abs=0.5)


def test_session5_shin_angle_forward_lean_20deg() -> None:
    """Knee 0.35 * tan(20°) forward of ankle → +20° forward."""
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    dy = 0.35
    dx = dy * math.tan(math.radians(20.0))
    frame = _make_shin_frame(knee_xy=(0.50 + dx, 0.55), ankle_xy=(0.50, 0.90))
    assert _shin_angle_deg(frame, right_idx, "right") == pytest.approx(20.0, abs=0.5)


def test_session5_shin_angle_backward_lean_negative() -> None:
    """Knee behind ankle (rare/wrong technique) → negative angle."""
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    dy = 0.35
    dx = dy * math.tan(math.radians(5.0))
    frame = _make_shin_frame(knee_xy=(0.50 - dx, 0.55), ankle_xy=(0.50, 0.90))
    assert _shin_angle_deg(frame, right_idx, "right") == pytest.approx(-5.0, abs=0.5)


def test_session5_shin_angle_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_shin_frame(knee_xy=(0.50, 0.55), ankle_xy=(0.50, 0.90))
    frame[right_idx.knee, 3] = 0.05
    assert _shin_angle_deg(frame, right_idx, "right") is None


def test_session5_shin_angle_degenerate_coincident_returns_none() -> None:
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_shin_frame(knee_xy=(0.50, 0.90), ankle_xy=(0.50, 0.90))
    assert _shin_angle_deg(frame, right_idx, "right") is None


@pytest.mark.parametrize("lean_deg", [-10.0, -2.0, 0.0, 2.0, 10.0, 25.0])
def test_session5_shin_angle_side_agnostic(lean_deg: float) -> None:
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    dy = 0.35
    dx = dy * math.tan(math.radians(lean_deg))
    right_frame = _make_shin_frame(
        knee_xy=(0.50 + dx, 0.55), ankle_xy=(0.50, 0.90), side="right",
    )
    left_frame = _make_shin_frame(
        knee_xy=(1.0 - (0.50 + dx), 0.55), ankle_xy=(1.0 - 0.50, 0.90), side="left",
    )
    r = _shin_angle_deg(right_frame, right_idx, "right")
    L = _shin_angle_deg(left_frame, left_idx, "left")
    assert r is not None and L is not None
    assert r == pytest.approx(L, abs=0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and shin_angle" -xvs
```

- [ ] **Step 3: Implement the helper** — append:

```python
def _shin_angle_deg(
    landmarks: np.ndarray,
    side_idx: SideIndices,
    side: Literal["left", "right"],
) -> float | None:
    """Session 5 #11 — sagittal-plane shin-vertical angle at squat rep bottom.

    ``atan2((knee_x - ankle_x) * facing_sign, ankle_y - knee_y)``. 0° = vertical
    shin. Positive = knee forward of ankle (forward shin lean) regardless of
    filmed side. Returns None on missing landmark or zero-magnitude vector.
    """
    if not _vis_ok(landmarks, side_idx.knee, side_idx.ankle):
        return None
    knee = _xy(landmarks, side_idx.knee)
    ankle = _xy(landmarks, side_idx.ankle)
    dx = (float(knee[0]) - float(ankle[0])) * _facing_sign(side)
    dy = float(ankle[1]) - float(knee[1])
    if abs(dx) < _S5_DEGENERATE_MAGNITUDE and abs(dy) < _S5_DEGENERATE_MAGNITUDE:
        return None
    return float(np.degrees(np.arctan2(dx, dy)))
```

- [ ] **Step 4: Run the new tests**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and shin_angle" -xvs
```

Expected: 11 cases pass.

- [ ] **Step 5: Wire into `_squat_metrics`** — after `heel_rise`:

```python
    shin_angle = _shin_angle_deg(landmarks_per_frame[depth_frame], side_idx, lifter_side)
```

And in the returned dict:

```python
        "shin_angle_deg": float(shin_angle) if shin_angle is not None else 0.0,
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): #11 shin_angle_deg extractor (Session 5)"
```

---

### Task 8: Implement #13 `setup_knee_angle_deg` (deadlift, TDD)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py`

Per design Section-4: joint angle at `S_knee` between `S_hip` and `S_ankle` vectors at the first frame of the lift. Unsigned joint angle → naturally side-agnostic.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------------------
# Session 5 #13 — setup_knee_angle_deg (deadlift)
# ---------------------------------------------------------------------------


def _make_dl_knee_frame(
    *,
    hip_xy: tuple[float, float],
    knee_xy: tuple[float, float],
    ankle_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.hip, :2] = hip_xy
    lm[idx.knee, :2] = knee_xy
    lm[idx.ankle, :2] = ankle_xy
    return lm


def test_session5_setup_knee_angle_straight_leg() -> None:
    """Hip, knee, ankle collinear → 180°."""
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_knee_frame(
        hip_xy=(0.50, 0.30), knee_xy=(0.50, 0.60), ankle_xy=(0.50, 0.90),
    )
    assert _setup_knee_angle_deg(frame, right_idx) == pytest.approx(180.0, abs=1.0)


def test_session5_setup_knee_angle_right_angle_squat_pull() -> None:
    """Hip directly above knee, knee directly above ankle, both at right
    angle → 90°."""
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_knee_frame(
        hip_xy=(0.30, 0.60),    # hip 0.20 behind knee, same y
        knee_xy=(0.50, 0.60),
        ankle_xy=(0.50, 0.80),  # ankle 0.20 below knee, same x
    )
    assert _setup_knee_angle_deg(frame, right_idx) == pytest.approx(90.0, abs=1.0)


def test_session5_setup_knee_angle_hip_hinge_140() -> None:
    """Typical deadlift hip-hinge setup → 130-150° range."""
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_knee_frame(
        hip_xy=(0.35, 0.45),
        knee_xy=(0.50, 0.65),
        ankle_xy=(0.50, 0.95),
    )
    val = _setup_knee_angle_deg(frame, right_idx)
    assert val is not None
    assert 120.0 <= val <= 160.0


def test_session5_setup_knee_angle_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_knee_frame(
        hip_xy=(0.50, 0.30), knee_xy=(0.50, 0.60), ankle_xy=(0.50, 0.90),
    )
    frame[right_idx.knee, 3] = 0.05
    assert _setup_knee_angle_deg(frame, right_idx) is None


def test_session5_setup_knee_angle_degenerate_coincident_returns_none() -> None:
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_knee_frame(
        hip_xy=(0.50, 0.60), knee_xy=(0.50, 0.60), ankle_xy=(0.50, 0.90),
    )
    assert _setup_knee_angle_deg(frame, right_idx) is None


def test_session5_setup_knee_angle_side_agnostic() -> None:
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frame = _make_dl_knee_frame(
        hip_xy=(0.35, 0.45), knee_xy=(0.50, 0.65), ankle_xy=(0.50, 0.95),
        side="right",
    )
    left_frame = _make_dl_knee_frame(
        hip_xy=(1.0 - 0.35, 0.45), knee_xy=(1.0 - 0.50, 0.65),
        ankle_xy=(1.0 - 0.50, 0.95), side="left",
    )
    r = _setup_knee_angle_deg(right_frame, right_idx)
    L = _setup_knee_angle_deg(left_frame, left_idx)
    assert r is not None and L is not None
    assert r == pytest.approx(L, abs=0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and setup_knee_angle" -xvs
```

- [ ] **Step 3: Implement the helper** — append:

```python
def _setup_knee_angle_deg(
    landmarks: np.ndarray,
    side_idx: SideIndices,
) -> float | None:
    """Session 5 #13 — deadlift joint angle at S_knee (hip-knee-ankle) at the
    first lift frame. Unsigned → side-agnostic. Returns None on missing
    landmark or degenerate (zero-length) vector.
    """
    if not _vis_ok(landmarks, side_idx.hip, side_idx.knee, side_idx.ankle):
        return None
    hip = _xy(landmarks, side_idx.hip)
    knee = _xy(landmarks, side_idx.knee)
    ankle = _xy(landmarks, side_idx.ankle)
    v_hk = hip - knee
    v_ak = ankle - knee
    m_hk = float(np.linalg.norm(v_hk))
    m_ak = float(np.linalg.norm(v_ak))
    if m_hk < _S5_DEGENERATE_MAGNITUDE or m_ak < _S5_DEGENERATE_MAGNITUDE:
        return None
    cos_t = float(np.clip(np.dot(v_hk, v_ak) / (m_hk * m_ak), -1.0, 1.0))
    return float(np.degrees(np.arccos(cos_t)))
```

- [ ] **Step 4: Run the new tests**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and setup_knee_angle" -xvs
```

Expected: 6 cases pass.

- [ ] **Step 5: Wire into `_deadlift_metrics`** — after `setup_shoulder_offset`:

```python
    setup_knee_angle = _setup_knee_angle_deg(landmarks_per_frame[start], side_idx)
```

And in the returned dict:

```python
        "setup_knee_angle_deg": (
            float(setup_knee_angle) if setup_knee_angle is not None else 0.0
        ),
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): #13 setup_knee_angle_deg extractor (Session 5)"
```

---

### Task 9: Implement #15 `arch_deg` (bench, TDD)

**Files:**
- Modify: `backend/app/cv/metric_extraction.py`
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py`

Per design Section-4: mean `(hip_y - shoulder_y)` across non-rep frames, expressed as `atan2((hip_y - shoulder_y), (hip_x - shoulder_x) * facing_sign)`. Single value per session. Positive = hips higher than shoulders (bench arch).

"Non-rep frames" = frames not inside any `DetectedRep.start_frame .. end_frame`. For Session 5 the helper is per-rep input agnostic; we expose a function that takes a list of (frame, is_in_rep) pairs and reduces to a single angle. The analyzer attaches the same session-wide value to every rep so the panel can display it consistently.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------------------
# Session 5 #15 — arch_deg (bench)
# ---------------------------------------------------------------------------


def _make_bench_arch_frame(
    *,
    shoulder_xy: tuple[float, float],
    hip_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.shoulder, :2] = shoulder_xy
    lm[idx.hip, :2] = hip_xy
    return lm


def test_session5_arch_deg_flat_back() -> None:
    """Shoulder and hip at the same y, hip 0.30 anterior → 0° arch
    (flat horizontal supine body)."""
    from app.cv.metric_extraction import _arch_deg
    frames = [
        _make_bench_arch_frame(shoulder_xy=(0.30, 0.50), hip_xy=(0.60, 0.50))
        for _ in range(20)
    ]
    right_idx = landmark_indices_for_side("right")
    val = _arch_deg(frames, non_rep_frame_mask=[True] * 20,
                    side_idx=right_idx, side="right")
    assert val == pytest.approx(0.0, abs=0.5)


def test_session5_arch_deg_pronounced_arch() -> None:
    """Hips 0.05 above shoulders (smaller y = higher in image) with 0.30
    horizontal separation → positive arch around 9-10°."""
    from app.cv.metric_extraction import _arch_deg
    frames = [
        _make_bench_arch_frame(shoulder_xy=(0.30, 0.55), hip_xy=(0.60, 0.50))
        for _ in range(20)
    ]
    right_idx = landmark_indices_for_side("right")
    val = _arch_deg(frames, non_rep_frame_mask=[True] * 20,
                    side_idx=right_idx, side="right")
    assert val is not None
    # atan2(0.05, 0.30) ≈ 9.46°
    assert val == pytest.approx(9.46, abs=0.5)


def test_session5_arch_deg_low_arch() -> None:
    """Hips marginally above shoulders → small positive angle."""
    from app.cv.metric_extraction import _arch_deg
    frames = [
        _make_bench_arch_frame(shoulder_xy=(0.30, 0.51), hip_xy=(0.60, 0.50))
        for _ in range(20)
    ]
    right_idx = landmark_indices_for_side("right")
    val = _arch_deg(frames, non_rep_frame_mask=[True] * 20,
                    side_idx=right_idx, side="right")
    assert val is not None
    assert 0.5 <= val <= 5.0


def test_session5_arch_deg_no_non_rep_frames_returns_none() -> None:
    """Empty non-rep window → None."""
    from app.cv.metric_extraction import _arch_deg
    frames = [
        _make_bench_arch_frame(shoulder_xy=(0.30, 0.55), hip_xy=(0.60, 0.50))
        for _ in range(10)
    ]
    right_idx = landmark_indices_for_side("right")
    val = _arch_deg(frames, non_rep_frame_mask=[False] * 10,
                    side_idx=right_idx, side="right")
    assert val is None


def test_session5_arch_deg_all_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _arch_deg
    right_idx = landmark_indices_for_side("right")
    frames = []
    for _ in range(10):
        f = _make_bench_arch_frame(shoulder_xy=(0.30, 0.55), hip_xy=(0.60, 0.50))
        f[right_idx.shoulder, 3] = 0.05
        f[right_idx.hip, 3] = 0.05
        frames.append(f)
    val = _arch_deg(frames, non_rep_frame_mask=[True] * 10,
                    side_idx=right_idx, side="right")
    assert val is None


def test_session5_arch_deg_side_agnostic() -> None:
    """Same arch on right-vs-mirrored-left → same signed value."""
    from app.cv.metric_extraction import _arch_deg
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frames = [
        _make_bench_arch_frame(shoulder_xy=(0.30, 0.55), hip_xy=(0.60, 0.50),
                               side="right")
        for _ in range(20)
    ]
    left_frames = [
        _make_bench_arch_frame(shoulder_xy=(1.0 - 0.30, 0.55),
                               hip_xy=(1.0 - 0.60, 0.50), side="left")
        for _ in range(20)
    ]
    r = _arch_deg(right_frames, non_rep_frame_mask=[True] * 20,
                  side_idx=right_idx, side="right")
    L = _arch_deg(left_frames, non_rep_frame_mask=[True] * 20,
                  side_idx=left_idx, side="left")
    assert r is not None and L is not None
    assert r == pytest.approx(L, abs=0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and arch_deg" -xvs
```

- [ ] **Step 3: Implement the helper** — append:

```python
def _arch_deg(
    landmarks_per_frame: list[np.ndarray],
    non_rep_frame_mask: list[bool],
    side_idx: SideIndices,
    side: Literal["left", "right"],
) -> float | None:
    """Session 5 #15 — bench arch angle averaged across non-rep frames.

    For each frame where ``non_rep_frame_mask[i]`` is True AND both S_shoulder
    and S_hip are visible, compute the shoulder→hip vector with facing-sign
    applied to dx, then take the mean (dx_mean, dy_mean) and reduce via
    ``atan2(dy_mean, dx_mean)``. Positive = hips higher than shoulders. Single
    value per session.

    Returns None when no qualifying frame exists.
    """
    if len(landmarks_per_frame) != len(non_rep_frame_mask):
        return None
    sign = _facing_sign(side)
    dxs: list[float] = []
    dys: list[float] = []
    for include, frame in zip(non_rep_frame_mask, landmarks_per_frame):
        if not include:
            continue
        if not _vis_ok(frame, side_idx.shoulder, side_idx.hip):
            continue
        shoulder_x = float(frame[side_idx.shoulder, 0])
        shoulder_y = float(frame[side_idx.shoulder, 1])
        hip_x = float(frame[side_idx.hip, 0])
        hip_y = float(frame[side_idx.hip, 1])
        dxs.append((hip_x - shoulder_x) * sign)
        # In image coords y increases downward → "hips higher than shoulders"
        # = hip_y < shoulder_y → (shoulder_y - hip_y) > 0 = positive dy.
        dys.append(shoulder_y - hip_y)
    if not dxs:
        return None
    dx_mean = float(np.mean(dxs))
    dy_mean = float(np.mean(dys))
    if abs(dx_mean) < _S5_DEGENERATE_MAGNITUDE and abs(dy_mean) < _S5_DEGENERATE_MAGNITUDE:
        return None
    return float(np.degrees(np.arctan2(dy_mean, dx_mean)))
```

- [ ] **Step 4: Run the new tests**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k "session5 and arch_deg" -xvs
```

Expected: 6 cases pass.

- [ ] **Step 5: Wire into `_bench_metrics`** — Since `_bench_metrics` operates per-rep but `arch_deg` is per-session, we need to compute it once across the full session and attach the same value to every rep. The cleanest pattern: compute it in `extract_rep_metrics` after the dispatch loop and inject it into every bench rep's metrics dict. Alternatively, since `_bench_metrics` has access to `landmarks_per_frame` (full session), it can compute it inside — but that recomputes per rep.

Choose the simpler per-rep recomputation (negligible cost, ~3-frame average). Add inside `_bench_metrics` after `bar_touch_height`:

```python
    # Build the non-rep mask. For bench, every frame outside the current rep is
    # "non-rep" for arch purposes. Multi-rep analyses where we'd want to also
    # exclude OTHER reps' frames are out-of-scope for Session 5: the analyzer
    # is invoked per rep and doesn't have cross-rep state. For a per-rep call,
    # treat frames OUTSIDE this rep as non-rep.
    n_total = len(landmarks_per_frame)
    non_rep_mask = [not (start <= i <= end) for i in range(n_total)]
    arch_value = _arch_deg(landmarks_per_frame, non_rep_mask, side_idx, lifter_side)
```

And in the returned dict:

```python
        "arch_deg": float(arch_value) if arch_value is not None else 0.0,
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/metric_extraction.py backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "feat(cv): #15 arch_deg extractor (Session 5)"
```

---

### Task 10: Per-exercise analyzer key-emission integration tests

**Files:**
- Modify: `backend/tests/unit/test_metric_extraction_sagittal.py`

Mirror Session 4's `test_session4_*_analyzer_emits_applicable_keys` shape so we have a regression guard that each analyzer emits exactly the applicable Session 5 keys.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------------------
# Session 5 — per-exercise analyzer key emission
# ---------------------------------------------------------------------------


def _make_full_squat_session_with_landmarks(n_frames: int = 60):
    """Squat session helper populated for Session 5 squat extractors."""
    frames = []
    right_idx = landmark_indices_for_side("right")
    for _ in range(n_frames):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[right_idx.shoulder, :2] = [0.50, 0.10]
        lm[right_idx.hip, :2] = [0.50, 0.50]
        lm[right_idx.knee, :2] = [0.55, 0.70]   # slight forward knee travel
        lm[right_idx.ankle, :2] = [0.50, 0.92]
        lm[right_idx.foot_index, :2] = [0.65, 0.92]
        lm[right_idx.heel, :2] = [0.42, 0.92]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, n_frames)
    hip = 125.0 + 45.0 * np.cos(t)
    knee = 110.0 + 40.0 * np.cos(t)
    ts = {"hip_angle": hip, "knee_angle": knee}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=n_frames - 1,
        confidence_score=0.9, min_angle=80.0,
    )
    return frames, ts, rep


def test_session5_squat_analyzer_emits_session5_keys() -> None:
    frames, ts, rep = _make_full_squat_session_with_landmarks(60)
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="squat", exercise_variant="standard",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "ankle_dorsiflexion_deg" in metrics
    assert "heel_rise_flag" in metrics
    assert "shin_angle_deg" in metrics
    # Bench-only / DL-only keys must NOT appear on squat output.
    assert "wrist_alignment_deg" not in metrics
    assert "bar_touch_height_pct" not in metrics
    assert "arch_deg" not in metrics
    assert "setup_shoulder_x_offset" not in metrics
    assert "setup_knee_angle_deg" not in metrics


def test_session5_bench_analyzer_emits_session5_keys() -> None:
    frames = []
    right_idx = landmark_indices_for_side("right")
    for _ in range(60):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[right_idx.shoulder, :2] = [0.30, 0.55]   # arch pose
        lm[right_idx.elbow, :2] = [0.40, 0.42]
        lm[right_idx.wrist, :2] = [0.42, 0.30]
        lm[right_idx.hip, :2] = [0.60, 0.50]        # hips higher → arch +
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, 60)
    ts = {"elbow_angle": 115.0 + 50.0 * np.cos(t),
          "shoulder_angle": 70.0 + 20.0 * np.cos(t)}
    rep = DetectedRep(
        rep_index=0, start_frame=10, end_frame=49,
        confidence_score=0.9, min_angle=65.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="bench", exercise_variant="flat",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "wrist_alignment_deg" in metrics
    assert "bar_touch_height_pct" in metrics
    assert "arch_deg" in metrics
    assert "ankle_dorsiflexion_deg" not in metrics
    assert "heel_rise_flag" not in metrics
    assert "shin_angle_deg" not in metrics
    assert "setup_shoulder_x_offset" not in metrics
    assert "setup_knee_angle_deg" not in metrics


def test_session5_deadlift_analyzer_emits_session5_keys() -> None:
    frames = []
    right_idx = landmark_indices_for_side("right")
    for _ in range(60):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[right_idx.shoulder, :2] = [0.55, 0.45]   # shoulders over bar
        lm[right_idx.elbow, :2] = [0.50, 0.70]
        lm[right_idx.wrist, :2] = [0.50, 0.85]
        lm[right_idx.hip, :2] = [0.40, 0.55]
        lm[right_idx.knee, :2] = [0.50, 0.70]
        lm[right_idx.ankle, :2] = [0.50, 0.92]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, 60)
    ts = {"hip_angle": 100.0 + 60.0 * np.cos(t),
          "knee_angle": 120.0 + 40.0 * np.cos(t)}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=59,
        confidence_score=0.9, min_angle=40.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="deadlift", exercise_variant="conventional",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "setup_shoulder_x_offset" in metrics
    assert "setup_knee_angle_deg" in metrics
    assert "ankle_dorsiflexion_deg" not in metrics
    assert "heel_rise_flag" not in metrics
    assert "shin_angle_deg" not in metrics
    assert "wrist_alignment_deg" not in metrics
    assert "bar_touch_height_pct" not in metrics
    assert "arch_deg" not in metrics
```

- [ ] **Step 2: Run the tests**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py::test_session5_squat_analyzer_emits_session5_keys tests/unit/test_metric_extraction_sagittal.py::test_session5_bench_analyzer_emits_session5_keys tests/unit/test_metric_extraction_sagittal.py::test_session5_deadlift_analyzer_emits_session5_keys -xvs
```

Expected: 3 cases pass (we already wired the keys in Tasks 3-9).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_metric_extraction_sagittal.py
git commit -m "test(cv): per-exercise analyzer key emission for Session 5"
```

---

### Task 11: Flip registry `computed_yet` flags for the 7 Session 5 entries (TDD)

**Files:**
- Modify: `backend/app/cv/sagittal_metrics_registry.py`
- Modify: `backend/tests/unit/test_sagittal_metrics_registry.py`

- [ ] **Step 1: Write the failing test** — append to `backend/tests/unit/test_sagittal_metrics_registry.py`:

```python
class TestRegistrySession5Flips:
    SESSION5_KEYS = frozenset({
        "ankle_dorsiflexion_deg",
        "wrist_alignment_deg",
        "bar_touch_height_pct",
        "setup_shoulder_x_offset",
        "shin_angle_deg",
        "setup_knee_angle_deg",
        "arch_deg",
    })

    def test_session5_entries_have_computed_yet_true(self) -> None:
        flipped = {
            e.key_name for e in SAGITTAL_METRICS_REGISTRY
            if e.key_name in self.SESSION5_KEYS and e.computed_yet
        }
        assert flipped == self.SESSION5_KEYS, (
            f"Missing flips: {self.SESSION5_KEYS - flipped}"
        )

    def test_session5_entries_remain_out_of_scoring(self) -> None:
        in_scoring = {
            e.key_name for e in SAGITTAL_METRICS_REGISTRY
            if e.key_name in self.SESSION5_KEYS and e.in_scoring
        }
        # Per design Section-4: Session 5 metrics are compute-only.
        assert in_scoring == frozenset(), (
            f"These Session 5 keys are unexpectedly in scoring: {in_scoring}"
        )
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run --directory backend pytest tests/unit/test_sagittal_metrics_registry.py::TestRegistrySession5Flips -xvs
```

Expected: first test fails (all 7 still `computed_yet=False`).

- [ ] **Step 3: Flip the flags** — in `backend/app/cv/sagittal_metrics_registry.py`, change `computed_yet=False` → `computed_yet=True` on each of these 7 entries: `ankle_dorsiflexion_deg`, `wrist_alignment_deg`, `bar_touch_height_pct`, `setup_shoulder_x_offset`, `shin_angle_deg`, `setup_knee_angle_deg`, `arch_deg`. Leave `in_scoring=False`.

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run --directory backend pytest tests/unit/test_sagittal_metrics_registry.py::TestRegistrySession5Flips -xvs
```

Expected: 2 cases pass.

- [ ] **Step 5: Run the full registry test suite to confirm no regressions**

```bash
uv run --directory backend pytest tests/unit/test_sagittal_metrics_registry.py -xvs
```

Expected: every existing test still green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cv/sagittal_metrics_registry.py backend/tests/unit/test_sagittal_metrics_registry.py
git commit -m "feat(cv): flip computed_yet=True for 7 Session 5 registry entries"
```

---

### Task 12: Integration tests on matching atharva fixtures

**Files:**
- Create: `backend/tests/integration/test_pipeline_sagittal_metrics.py`

Per design Section-5: squat fixture covers #1 + #11; bench fixture covers #3 + #5 + #15; deadlift fixture covers #10 + #13.

- [ ] **Step 1: Create the file**

```python
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
```

- [ ] **Step 2: Run** (these are slow — full MediaPipe runs on real fixtures)

```bash
uv run --directory backend pytest tests/integration/test_pipeline_sagittal_metrics.py -xvs
```

Expected: 3 cases pass with each metric value within its sanity range. If a value is outside the documented range → STOP per /goal trigger ("Any metric's smoke-script value is outside sanity range documented in Section 5 of design").

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_pipeline_sagittal_metrics.py
git commit -m "test(cv): Session 5 integration tests on atharva fixtures"
```

---

### Task 13: Smoke script — per-fixture per-rep CSV dump

**Files:**
- Create: `backend/scripts/oneoff/smoke_sagittal_metrics_session5.py`

- [ ] **Step 1: Create the file**

```python
"""Session 5 smoke script — dump per-rep Session-5 metric values for all 3
atharva fixtures. Output is CSV-formatted on stdout for paste-into-chat
per /goal evidence-surfacing protocol.

Not run in CI — calibration aid only.

Usage:
    uv run --directory backend python scripts/oneoff/smoke_sagittal_metrics_session5.py
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


_PER_EXERCISE_SESSION5_KEYS = {
    "squat": ("ankle_dorsiflexion_deg", "heel_rise_flag", "shin_angle_deg"),
    "bench": ("wrist_alignment_deg", "bar_touch_height_pct", "arch_deg"),
    "deadlift": ("setup_shoulder_x_offset", "setup_knee_angle_deg"),
}


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
    keys = _PER_EXERCISE_SESSION5_KEYS[exercise]
    print(f"# fixture={fixture.name} exercise={exercise} variant={variant} "
          f"side={side} fps={fps:.1f} reps={len(rep_metrics)}")
    print("rep_index," + ",".join(keys))
    for r in rep_metrics:
        vals = [str(r.metrics.get(k)) for k in keys]
        print(f"{r.rep_index}," + ",".join(vals))
    print()
    return 0


def main() -> int:
    rc = 0
    rc |= _run(_FIXTURES_DIR / "atharva-squat.mov", "squat", "standard")
    rc |= _run(_FIXTURES_DIR / "atharva-bench.mov", "bench", "flat")
    rc |= _run(_FIXTURES_DIR / "atharva-deadlift.mov", "deadlift", "conventional")
    return rc


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the smoke script and copy the output to chat**

```bash
uv run --directory backend python scripts/oneoff/smoke_sagittal_metrics_session5.py
```

Expected: 3 CSV blocks (one per fixture) with per-rep values for each applicable Session-5 key. Pipe the full output into chat per the /goal evidence-surfacing protocol.

If any metric falls outside the sanity range documented in `test_pipeline_sagittal_metrics.py` (matches design Section-5), STOP and remediate per the /goal stop trigger.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/oneoff/smoke_sagittal_metrics_session5.py
git commit -m "feat(scripts): Session 5 smoke script for per-rep sagittal metric values"
```

---

### Task 14: Full local verification — lint + types + tests + coverage

**Files:** none.

- [ ] **Step 1: Ruff**

```bash
uv run --directory backend ruff check app tests
```

Expected: "All checks passed".

- [ ] **Step 2: Pyright**

```bash
uv run --directory backend pyright app
```

Expected: "0 errors".

- [ ] **Step 3: Full unit test suite (excludes the slow MediaPipe integration tests)**

```bash
uv run --directory backend pytest tests/unit -x
```

Expected: 2137 (Session 4 baseline) + ~55 new Session 5 cases = ~2192 passing, 0 failing.

- [ ] **Step 4: Integration tests on the 3 fixtures** (slow — ~3 × MediaPipe runs)

```bash
uv run --directory backend pytest tests/integration/test_pipeline_sagittal_metrics.py -xvs
```

Expected: 3 passed.

- [ ] **Step 5: Coverage on the new functions**

```bash
uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py --cov=app.cv.metric_extraction --cov-report=term-missing
```

Expected: every new Session 5 helper line covered. If a line is genuinely untestable (defensive guard), annotate with `# pragma: no cover` and a one-line comment per Standing Rule #1 — never lower the global threshold.

- [ ] **Step 6: Update `backend/CLAUDE.md`** — append one paragraph to the existing "Side-agnostic landmark access" gotcha:

```markdown
Session 5 extended the pattern with `_facing_sign(side)` (in `metric_extraction.py`) for x-direction *signed* metrics (`wrist_alignment_deg`, `setup_shoulder_x_offset`, `shin_angle_deg`, `arch_deg`). The helper returns `+1.0` for `"right"`, `-1.0` for `"left"`. Multiply the raw x-component of any signed metric by this so the same physical pose filmed from either side produces the same signed output. Unsigned joint-angle metrics (`ankle_dorsiflexion_deg`, `setup_knee_angle_deg`) and y-only metrics (`bar_touch_height_pct`, `heel_rise_flag`) are naturally side-agnostic and don't need it.
```

- [ ] **Step 7: Commit**

```bash
git add backend/CLAUDE.md
git commit -m "docs(backend): _facing_sign convention for Session 5 signed metrics"
```

---

### Task 15: Push branch + open PR via `mcp__github__create_pull_request`

**Files:** none (PR only).

- [ ] **Step 1: Push the branch**

```bash
git push -u origin feat/sagittal-standard-metrics
```

- [ ] **Step 2: Open PR via the MCP tool**

Call `mcp__github__create_pull_request` with:

- `owner: atharva6905`
- `repo: spelix`
- `base: main`
- `head: feat/sagittal-standard-metrics`
- `title: feat(cv): Session 5 — 7 sagittal-view metrics (compute-only)`
- `body`:

```markdown
## Summary
Implements the 7 Session-5 sagittal metrics from the cv-audit effort (design §Session-5):

| # | Key | Exercise | Side-agnostic |
|---|-----|----------|---------------|
| 1 | `ankle_dorsiflexion_deg` + `heel_rise_flag` | squat | yes (joint angle / y-only) |
| 3 | `wrist_alignment_deg` | bench | via `_facing_sign` |
| 5 | `bar_touch_height_pct` | bench | yes (y-only) |
| 10 | `setup_shoulder_x_offset` | deadlift | via `_facing_sign` |
| 11 | `shin_angle_deg` | squat | via `_facing_sign` |
| 13 | `setup_knee_angle_deg` | deadlift | yes (joint angle) |
| 15 | `arch_deg` | bench | via `_facing_sign` |

All compute-only — no scoring branches. Registry `computed_yet` flipped on 7 entries; `in_scoring` stays False (compute-only per design Section-4). Expert `<UnvalidatedMetricsPanel />` auto-renders the new values via the existing registry-driven path.

Closes audit IDs `L2-SAGITTAL-STANDARD-01` through `-07`.

## Test plan
- [x] Unit tests in `backend/tests/unit/test_metric_extraction_sagittal.py` — happy / edge / degenerate per metric + parametrised side-agnosticism mirror tests
- [x] Per-exercise analyzer key-emission tests
- [x] Registry flip tests in `backend/tests/unit/test_sagittal_metrics_registry.py`
- [x] Integration tests in `backend/tests/integration/test_pipeline_sagittal_metrics.py` on all 3 atharva fixtures with sanity-range assertions
- [x] Smoke script `backend/scripts/oneoff/smoke_sagittal_metrics_session5.py` — dumps per-rep CSV across all 3 fixtures
- [x] Coverage on new functions ≥90%
- [x] `ruff check` + `pyright` clean
- [x] Full backend test suite green
- [ ] Post-merge: E2E on prod (Playwright MCP) re-uploads all 3 fixtures, panel rows populated
```

Print the response JSON's `html_url` to chat.

- [ ] **Step 3: Surface the PR URL**

Take the URL returned by the MCP tool and quote it inline in chat.

---

### Task 16: PR-level CI gate

**Files:** none.

- [ ] **Step 1: Watch PR-level checks**

```bash
gh pr checks <PR-number>
```

Expected: every PR-level check 'pass' (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel). Pipe the FULL output to chat — do NOT use `mcp__github__get_pull_request_status` (per design Section-7, R8 mitigation).

If any check fails:
1. `gh run view <run-id> --log-failed` to find the root cause
2. Push a fix commit
3. Re-watch with `gh pr checks <PR> --watch`

If CI is red after 2 retries, STOP per /goal trigger and write a handoff.

---

### Task 17: Merge via MCP + post-deploy verification

**Files:** none.

- [ ] **Step 1: Merge**

Call `mcp__github__merge_pull_request` with `owner=atharva6905, repo=spelix, pullNumber=<PR>, merge_method="merge"` (NEVER squash per Standing Rule #3).

Surface the merge response showing `merged: true` and the merge SHA.

- [ ] **Step 2: Wait for Deploy to Production to finish**

```bash
gh run watch <main-run-id-after-merge>
```

Expected: `conclusion=success`. Pipe the final output to chat.

- [ ] **Step 3: Verify droplet HEAD matches merge SHA**

```bash
ssh spelix-droplet "git log --oneline -1"
ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"
```

Expected: droplet's HEAD line matches the merge SHA; all 3 containers show `(healthy)`.

---

### Task 18: E2E verification on prod via Playwright MCP

**Files:** none (screenshots only).

For each of the 3 atharva fixtures:
1. `mcp__playwright__browser_navigate` → `https://spelix.app/upload`
2. Login as the test account (use existing test credentials per the project's "Rate limit testing" memory: never use the primary account, always a dedicated test user)
3. Upload the fixture
4. Wait for completion (poll `/api/v1/analyses/<id>/status` until `completed`)
5. Navigate to the expert detail page: `https://spelix.app/expert/analyses/<id>`
6. `mcp__playwright__browser_snapshot` — confirm the applicable Session-5 row(s) show real values (not "Not yet computed", not "—")
7. `mcp__playwright__browser_take_screenshot` — save as `e2e/screenshots/session5-<exercise>-expert-panel.png`
8. Check `mcp__playwright__browser_console_messages` (filter level=error) — expect 0
9. Check `mcp__playwright__browser_network_requests` — no 4xx/5xx on the panel endpoints

Print all 3 screenshot paths in chat.

- [ ] **Step 1: Walk the squat fixture** (verifies `ankle_dorsiflexion_deg`, `heel_rise_flag`, `shin_angle_deg`)
- [ ] **Step 2: Walk the bench fixture** (verifies `wrist_alignment_deg`, `bar_touch_height_pct`, `arch_deg`)
- [ ] **Step 3: Walk the deadlift fixture** (verifies `setup_shoulder_x_offset`, `setup_knee_angle_deg`)

If any panel row is empty or any console error fires, STOP and write a handoff.

---

### Task 19: backlog + master manifest + handoff updates

**Files:**
- Modify: `backlog.md`
- Modify: `docs/superpowers/goals/2026-05-22-cv-audit-master.md`
- Modify: `.claude/handoff.md`

- [ ] **Step 1: Update `backlog.md`** — mark `L2-SAGITTAL-STANDARD-01` through `-07` as `done` with the merge SHA filled in. If there is no existing row for these IDs, append a new "Completed — Session 5 (2026-05-22)" section.

- [ ] **Step 2: Update the master manifest** — in `docs/superpowers/goals/2026-05-22-cv-audit-master.md`:
  - Session Status Overview row 5: status `complete`, remediation count `0`, commit SHA `<merge-sha>`, PR `#<PR>`
  - Session Status Overview row 6 (Session 6): status `active`
  - Tick the completion checklist items under "## Session 5"

- [ ] **Step 3: Update `.claude/handoff.md`** — overwrite with:

```markdown
# cv-audit handoff — Session 5 → Session 6

## Status
- **Session 5:** complete — merge SHA `<merge-sha>`, PR #<PR>
- **Next session:** Session 6 — Bar-coordinate math (#4 bar_to_hip_distance, #14 shoulder_protraction_proxy_px)
- **Launch command:** see `docs/superpowers/goals/2026-05-22-cv-audit-master.md` §Session-6 "Launch command" block. The Session 6 plan at `docs/superpowers/plans/2026-05-22-session-6-bar-coordinate-math.md` is currently a SKELETON; expand via `superpowers:writing-plans` before launching `/goal`. Mirrors Sessions 2/3/4/5 workflow.

## Completed this session
- <SHA list of Session 5 commits>

## Surfaced evidence
- PR #<PR>: <url>
- PR-level CI: all 6 checks pass on final commit
- Post-merge Deploy to Production: <main-run-id> conclusion=success
- Droplet HEAD: <merge-sha>; containers (healthy)
- Backend tests: 2137 baseline + N Session 5 = T passing
- E2E screenshots: e2e/screenshots/session5-{squat,bench,deadlift}-expert-panel.png

## Blockers
- None.

## Resume guidance for Session 6
1. Read this handoff + master manifest §Session-6.
2. Expand Session 6 skeleton via `superpowers:writing-plans`; commit before `/goal`.
3. `/goal` with the Session 6 launch command.
4. Auto mode + `/goal` = fully unattended.
5. Specialist agent: `spelix-cv-engineer` solo.
```

- [ ] **Step 4: Commit**

```bash
git add backlog.md docs/superpowers/goals/2026-05-22-cv-audit-master.md .claude/handoff.md
git commit -m "docs(session-5-close): mark Session 5 complete, write Session 6 handoff"
```

- [ ] **Step 5: Push** (no separate PR — these doc updates can land on `main` directly per project convention for handoff notes; if user prefers, open a second tiny PR mirroring Session 4's `b8f67e1` close commit)

```bash
git checkout main && git pull
# If close commits are required to flow via PR, branch + PR, otherwise push:
git push
```

---

### Task 20: Surface evidence per /goal completion checklist

Pipe to chat in a single message at the end:

- [ ] **Step 1:** Git diff for `backend/app/cv/metric_extraction.py` (final state) — `git diff main..HEAD -- backend/app/cv/metric_extraction.py | head -200`
- [ ] **Step 2:** `uv run --directory backend pytest tests/unit/test_metric_extraction_sagittal.py -k session5 --tb=no -q` final summary
- [ ] **Step 3:** `uv run --directory backend pytest tests/integration/test_pipeline_sagittal_metrics.py -xvs` final output
- [ ] **Step 4:** Smoke script CSV output (from Task 13 Step 2)
- [ ] **Step 5:** PR URL (from Task 15)
- [ ] **Step 6:** `gh pr checks <PR>` (from Task 16) AND `gh run watch <main-run-id>` (from Task 17 Step 2)
- [ ] **Step 7:** `mcp__github__merge_pull_request` response showing `merged: true`
- [ ] **Step 8:** `ssh spelix-droplet "git log --oneline -1"` output
- [ ] **Step 9:** All 3 E2E screenshots paths
- [ ] **Step 10:** Master manifest + handoff git diffs

---

## Acceptance criteria

- 7 extractors implemented + tested with happy / edge / degenerate / side-agnosticism mirror cases
- 7 registry `computed_yet` flags flipped; 0 `in_scoring` changes (compute-only per design)
- Integration tests pass on all 3 atharva fixtures with values inside the documented sanity ranges
- Smoke script CSV surfaced in chat
- Coverage ≥90% on every new helper; no global threshold lowered
- PR opened via `mcp__github__create_pull_request` and merged via `mcp__github__merge_pull_request` with `merge_method="merge"`
- All 6 PR-level CI checks pass + post-merge Deploy to Production `conclusion=success`
- E2E on prod confirms each Session-5 key visible in the expert panel for the matching exercise; screenshots saved
- No scoring impact — existing form scores unchanged
- Master manifest, backlog, and handoff updated
- spelix-security-reviewer not strictly required (no new user-facing strings — only existing registry descriptions render); skipped per Session 4 precedent unless a reviewer notices changed copy

---

## Just-in-time expansion checklist

Standard. This expansion preserved the skeleton's ordering, file lists, gates, and acceptance criteria; added concrete pytest bodies, helper implementations, registry diff, integration patterns, smoke script, and exact git commit messages. Nothing in the original skeleton's quality gates was lowered.
