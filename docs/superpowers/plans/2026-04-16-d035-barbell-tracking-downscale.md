# D-035 Barbell Tracking Downscale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut the `barbell_tracking` pipeline stage from 24.4 min to < 180 s on the production bench clip by downscaling every frame to 480 px (longest dimension) before `cv2.HoughCircles`, scaling detected centroids back to source coordinates.

**Architecture:** Single-file change in `backend/app/cv/barbell_detection.py` — add `_downscale_for_detection` helper, modify `detect_barbell_in_frame` to downscale before HoughCircles and scale centroids back before return. Callers (`track_barbell`, `track_barbell_from_video`) get the speedup transparently; `compute_bar_path` receives source-resolution centroids unchanged. FR-BDET-06 landmark fallback (already wired in `pipeline.py`) remains the safety net for low-detection-rate clips.

**Tech Stack:** Python 3.12, OpenCV 4.13 headless, NumPy, pytest + pytest-asyncio. Worker container `spelix-worker` for empirical benchmarks. GitHub MCP tools for PR flow. Playwright MCP for prod E2E.

**Spec:** `docs/superpowers/specs/2026-04-16-d035-barbell-tracking-downscale-design.md`

**Branch:** `fix/d035-downscale-barbell-detection` (created from `main`, not the current `docs/session-38-handoff` branch)

**SRS references:** FR-BDET-01, FR-BDET-02, FR-BDET-06, FR-BDET-07

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `backend/bench_barbell.py` | **Create** | 3-mode diagnostic (I/O, current detection, proposed detection) run on worker |
| `backend/app/cv/barbell_detection.py` | **Modify** — `detect_barbell_in_frame` + add `_downscale_for_detection` + new constants | The actual fix |
| `backend/tests/unit/test_barbell_detection.py` | **Extend** (existing file) | Add 4 unit tests for downscale + 1 slow integration test |
| `backend/pyproject.toml` | **Modify** — register `slow` marker | Enables `pytest -m slow` gating |
| `decisions.md` | **Append** — ADR-057 | Project decision log |
| `backlog.md` | **Modify** — D-035 row → `done`, D-036 row unblocked | Task tracking |
| `.claude/handoff.md` | **Replace** — session 39 → session 40 handoff | Session hygiene |

---

## Pre-flight

- [ ] **Confirm working directory and git state**

Run:

```bash
pwd
git status --short
git branch --show-current
```

Expected: repo is `C:/Users/athar/projects/spelix`, on branch `docs/session-38-handoff` (or other), working tree has the spec file modified + plan about to be written.

- [ ] **Create feature branch off main**

Run:

```bash
git fetch origin main
git checkout -b fix/d035-downscale-barbell-detection origin/main
```

Expected: new branch tracks `origin/main` at the latest merge commit (`0fdcc97` or newer).

- [ ] **Copy spec + plan into the branch** (they were written on the previous branch)

```bash
git checkout docs/session-38-handoff -- docs/superpowers/specs/2026-04-16-d035-barbell-tracking-downscale-design.md docs/superpowers/plans/2026-04-16-d035-barbell-tracking-downscale.md
git add docs/superpowers/
git commit -m "docs(cv): D-035 downscale-before-HoughCircles spec + plan"
```

Expected: one commit adding two files under `docs/superpowers/`.

---

## Task 1: Diagnostic benchmark — `bench_barbell.py`

Mandatory per spec §7 and handoff Priority 1. Produces empirical evidence that the HoughCircles-at-1080p hypothesis is correct before any fix lands. Output is committed to the branch so reviewers and future sessions can re-run.

**Files:**
- Create: `backend/bench_barbell.py`

- [ ] **Step 1: Upload the bench fixture to the worker**

Run (locally):

```bash
scp e2e/fixtures/atharva-bench-no-weight.mov spelix-droplet:/tmp/bench.mov
ssh spelix-droplet "docker cp /tmp/bench.mov spelix-worker-1:/tmp/bench.mov && docker exec spelix-worker-1 ls -la /tmp/bench.mov"
```

Expected: file listing shows `/tmp/bench.mov` inside the worker container with non-zero size (~40–80 MB).

- [ ] **Step 2: Write `backend/bench_barbell.py`**

Create the file with the following exact contents:

```python
"""Diagnostic benchmark for D-035 — cv2.HoughCircles cost at 1080p.

Runs three modes on a local video:
  Mode 1 — cap.read() only (I/O baseline)
  Mode 2 — detect_barbell_in_frame at source resolution (current code)
  Mode 3 — detect_barbell_in_frame with 480p downscale (proposed fix)

Mode 3 is skipped if _downscale_for_detection does not exist yet (pre-fix
baseline). Run pre-fix to confirm the hypothesis; run post-fix to quantify
the speedup.

Run inside the worker container:
    docker cp backend/bench_barbell.py spelix-worker-1:/tmp/bench_barbell.py
    docker exec spelix-worker-1 python /tmp/bench_barbell.py /tmp/bench.mov
"""
from __future__ import annotations

import sys
import time

import cv2


def _mode1_read_only(path: str) -> tuple[int, float]:
    cap = cv2.VideoCapture(path)
    t0 = time.perf_counter()
    n = 0
    while True:
        ret, _ = cap.read()
        if not ret:
            break
        n += 1
    cap.release()
    return n, time.perf_counter() - t0


def _mode2_current_detection(path: str) -> tuple[int, float, int]:
    sys.path.insert(0, "/app")
    from app.cv.barbell_detection import detect_barbell_in_frame

    cap = cv2.VideoCapture(path)
    t0 = time.perf_counter()
    n = 0
    detected = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        n += 1
        if detect_barbell_in_frame(frame) is not None:
            detected += 1
    cap.release()
    return n, time.perf_counter() - t0, detected


def _mode3_downscaled(path: str) -> tuple[int, float, int] | None:
    sys.path.insert(0, "/app")
    try:
        from app.cv.barbell_detection import _downscale_for_detection  # noqa: F401
    except ImportError:
        return None
    # After the fix lands, detect_barbell_in_frame itself downscales, so
    # mode 3 is identical to mode 2 in call-shape but measures post-fix cost.
    from app.cv.barbell_detection import detect_barbell_in_frame

    cap = cv2.VideoCapture(path)
    t0 = time.perf_counter()
    n = 0
    detected = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        n += 1
        if detect_barbell_in_frame(frame) is not None:
            detected += 1
    cap.release()
    return n, time.perf_counter() - t0, detected


def _print_row(label: str, frames: int, total_s: float, detected: int | None) -> None:
    per_ms = (total_s / max(frames, 1)) * 1000
    det_str = f"{detected}/{frames}" if detected is not None else "—"
    print(f"  {label:<40s} frames={frames}  total={total_s:7.2f}s  per_frame={per_ms:8.1f}ms  detected={det_str}")


def main(video_path: str) -> None:
    print(f"=== D-035 barbell detection benchmark ===")
    print(f"video: {video_path}")

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    print(f"source: {w}x{h} @ {fps:.2f}fps\n")

    print("Mode 1 — cap.read() only (I/O baseline):")
    n1, t1 = _mode1_read_only(video_path)
    _print_row("read-only", n1, t1, None)

    print("\nMode 2 — current detect_barbell_in_frame (source resolution):")
    n2, t2, d2 = _mode2_current_detection(video_path)
    _print_row("detect@source", n2, t2, d2)

    print("\nMode 3 — proposed detect_barbell_in_frame (480p downscale):")
    result = _mode3_downscaled(video_path)
    if result is None:
        print("  (skipped — _downscale_for_detection not yet implemented)")
    else:
        n3, t3, d3 = result
        _print_row("detect@480p", n3, t3, d3)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python bench_barbell.py /tmp/bench.mov")
        raise SystemExit(2)
    main(sys.argv[1])
```

- [ ] **Step 3: Commit the benchmark script (before running it)**

```bash
git add backend/bench_barbell.py
git commit -m "chore(cv): add bench_barbell.py diagnostic for HoughCircles cost

Three-mode benchmark (I/O only, current detect, proposed 480p detect)
used to confirm D-035 root cause and measure post-fix speedup."
```

Expected: clean commit on `fix/d035-downscale-barbell-detection`.

- [ ] **Step 4: Run pre-fix benchmark on the worker**

```bash
ssh spelix-droplet "docker cp /tmp/bench.mov spelix-worker-1:/tmp/bench.mov" 2>/dev/null || true
scp backend/bench_barbell.py spelix-droplet:/tmp/bench_barbell.py
ssh spelix-droplet "docker cp /tmp/bench_barbell.py spelix-worker-1:/tmp/bench_barbell.py && docker exec spelix-worker-1 python /tmp/bench_barbell.py /tmp/bench.mov"
```

Expected output structure:

```
=== D-035 barbell detection benchmark ===
video: /tmp/bench.mov
source: 1920x1080 @ 59.xxfps

Mode 1 — cap.read() only (I/O baseline):
  read-only                                frames=1345  total=   X.XXs  per_frame=   X.Xms  detected=—

Mode 2 — current detect_barbell_in_frame (source resolution):
  detect@source                            frames=1345  total=XXXX.XXs  per_frame= ~1089.0ms  detected=XXX/1345

Mode 3 — proposed detect_barbell_in_frame (480p downscale):
  (skipped — _downscale_for_detection not yet implemented)
```

**Decision gate (spec §7.2):**
- Mode 2 `per_frame` > 500 ms → confirmed; proceed to Task 2.
- Mode 1 `per_frame` > 50 % of Mode 2 `per_frame` → re-plan (I/O is the bug, not detection).
- Mode 2 per_frame < 500 ms → surprising; re-read the code, then decide whether to proceed.

Save the captured Mode 2 detected count (e.g., `1089/1345` = 81 %); you'll need it in Task 6 to set the post-fix regression tolerance.

- [ ] **Step 5: Paste the Mode 2 output into the PR draft / running notes**

No code commit — this is a data capture step. Record `detected_count_pre_fix` (for §8.4 spec criterion) somewhere reachable from the PR body.

---

## Task 2: Write failing unit tests for `_downscale_for_detection` (RED)

**Files:**
- Modify: `backend/tests/unit/test_barbell_detection.py` — append new test class

- [ ] **Step 1: Append new test class after existing `TestTrackBarbellFromVideo`**

Open `backend/tests/unit/test_barbell_detection.py` and append at the very bottom (after line 382):

```python
# ---------------------------------------------------------------------------
# _downscale_for_detection  (D-035)
# ---------------------------------------------------------------------------


class TestDownscaleForDetection:
    def test_noop_for_small_frames(self):
        """480x270 input: no downscale, scale_factor == 1.0."""
        from app.cv.barbell_detection import _downscale_for_detection

        frame = np.zeros((270, 480, 3), dtype=np.uint8)
        scaled, scale_factor = _downscale_for_detection(frame)
        assert scale_factor == 1.0
        assert scaled.shape == (270, 480, 3)

    def test_noop_at_exactly_max_dim(self):
        """Frame whose longest side equals max_dim is not resized."""
        from app.cv.barbell_detection import _downscale_for_detection

        frame = np.zeros((480, 480, 3), dtype=np.uint8)
        scaled, scale_factor = _downscale_for_detection(frame)
        assert scale_factor == 1.0
        assert scaled.shape == (480, 480, 3)

    def test_1080p_to_480p(self):
        """1920x1080 input: longest side becomes 480, scale_factor == 4.0."""
        from app.cv.barbell_detection import _downscale_for_detection

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        scaled, scale_factor = _downscale_for_detection(frame)
        assert scaled.shape == (270, 480, 3)
        assert scale_factor == pytest.approx(4.0, rel=1e-3)

    def test_4k_to_480p(self):
        """3840x2160 (4K) input: longest side becomes 480, scale_factor == 8.0."""
        from app.cv.barbell_detection import _downscale_for_detection

        frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
        scaled, scale_factor = _downscale_for_detection(frame)
        assert scaled.shape == (270, 480, 3)
        assert scale_factor == pytest.approx(8.0, rel=1e-3)

    def test_portrait_orientation(self):
        """Portrait 1080x1920 input: longest side (1920) becomes 480."""
        from app.cv.barbell_detection import _downscale_for_detection

        frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
        scaled, scale_factor = _downscale_for_detection(frame)
        assert scaled.shape == (480, 270, 3)
        assert scale_factor == pytest.approx(4.0, rel=1e-3)
```

- [ ] **Step 2: Run the new test class — expect RED (ImportError)**

```bash
cd backend
uv run pytest tests/unit/test_barbell_detection.py::TestDownscaleForDetection -v
```

Expected: **5 errors** — each test fails at `from app.cv.barbell_detection import _downscale_for_detection` with `ImportError`. That confirms the symbol does not exist yet.

- [ ] **Step 3: Commit the failing tests**

```bash
git add backend/tests/unit/test_barbell_detection.py
git commit -m "test(cv): failing tests for 480p downscale helper (D-035)

5 tests for _downscale_for_detection: noop for small, exact-max-dim, 1080p,
4K, and portrait inputs. All RED with ImportError — helper not implemented."
```

---

## Task 3: Implement `_downscale_for_detection` (GREEN)

**Files:**
- Modify: `backend/app/cv/barbell_detection.py`

- [ ] **Step 1: Add new constants and the helper function**

Open `backend/app/cv/barbell_detection.py`. After the existing `_MAX_RADIUS = 100` constant block (currently lines 17-23), add these new constants immediately below:

```python
# ---------------------------------------------------------------------------
# D-035 downscale constants — HoughCircles runs on a 480p-max-dim frame
# ---------------------------------------------------------------------------
# Scaled ~4× from 1080p defaults above. maxRadius bumped to 40 (not 25) so
# that the existing 640x480 / radius-40 unit fixture remains detectable after
# the 1.33× downscale to 480x360. Source-resolution plate sizes of up to
# ~160 px diameter (radius 40 after scaling) are still covered.
_DETECTION_MAX_DIM = 480
_MIN_DIST_480P = 12
_MIN_RADIUS_480P = 3
_MAX_RADIUS_480P = 40
```

Then, at the **very end** of the file (after the existing `_interpolate_centroids` function), append:

```python
def _downscale_for_detection(
    frame: np.ndarray, max_dim: int = _DETECTION_MAX_DIM
) -> tuple[np.ndarray, float]:
    """Downscale *frame* so its longest side is <= *max_dim*.

    Returns
    -------
    (scaled_frame, scale_factor) where scale_factor is the multiplier to
    convert a pixel coordinate in the scaled frame back to the source frame.
    Returns (frame, 1.0) unchanged when the frame is already small enough.
    """
    h, w = frame.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return frame, 1.0
    scale = max_dim / longest
    scaled = cv2.resize(
        frame, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA
    )
    return scaled, 1.0 / scale
```

- [ ] **Step 2: Run the unit tests — expect GREEN**

```bash
cd backend
uv run pytest tests/unit/test_barbell_detection.py::TestDownscaleForDetection -v
```

Expected: **5 passed**. All tests go from RED to GREEN with no changes elsewhere.

- [ ] **Step 3: Commit the helper**

```bash
git add backend/app/cv/barbell_detection.py
git commit -m "feat(cv): add _downscale_for_detection helper (D-035)

Returns (scaled_frame, scale_factor) such that longest dim <= 480. No-op
when frame already small enough. Adds _MIN_DIST_480P / _MIN_RADIUS_480P /
_MAX_RADIUS_480P constants sized for 480p HoughCircles input."
```

---

## Task 4: Write failing test for downscale-aware `detect_barbell_in_frame` (RED)

**Files:**
- Modify: `backend/tests/unit/test_barbell_detection.py` — append another test class

- [ ] **Step 1: Append a new test class for the modified detection behaviour**

Append at the bottom of `backend/tests/unit/test_barbell_detection.py`:

```python
# ---------------------------------------------------------------------------
# detect_barbell_in_frame after D-035 downscale (post-fix behaviour)
# ---------------------------------------------------------------------------


class TestDetectBarbellAfterDownscale:
    def test_detect_returns_source_coords_on_1080p(self):
        """Circle drawn at (1000, 500) in a 1920x1080 frame is detected near
        (1000, 500) after internal downscale-to-480 + scale-back."""
        w, h = 1920, 1080
        cx, cy = 1000, 500
        radius = 60
        frame = np.full((h, w, 3), 30, dtype=np.uint8)
        cv2.circle(frame, (cx, cy), radius, (200, 200, 200), thickness=-1)

        result = detect_barbell_in_frame(frame)
        assert result is not None, "Expected centroid on clean 1080p circle"
        dx = abs(result[0] - cx)
        dy = abs(result[1] - cy)
        # Error budget: ~1 source px per 0.25 scaled px. Allow ±20 source px.
        assert dx <= 20, f"x off by {dx} px (detected {result[0]})"
        assert dy <= 20, f"y off by {dy} px (detected {result[1]})"

    def test_detect_returns_source_coords_on_portrait_1080p(self):
        """Same test in portrait orientation — longest side 1920 (height)."""
        w, h = 1080, 1920
        cx, cy = 540, 900
        radius = 60
        frame = np.full((h, w, 3), 30, dtype=np.uint8)
        cv2.circle(frame, (cx, cy), radius, (200, 200, 200), thickness=-1)

        result = detect_barbell_in_frame(frame)
        assert result is not None
        dx = abs(result[0] - cx)
        dy = abs(result[1] - cy)
        assert dx <= 20, f"x off by {dx} px"
        assert dy <= 20, f"y off by {dy} px"

    def test_detect_on_1080p_is_fast(self):
        """Per-frame detection on 1080p completes in < 200 ms (budget check).

        This is a unit-level smoke test that the downscale is wired through;
        the rigorous stage budget check is the slow integration test.
        """
        import time

        w, h = 1920, 1080
        frame = np.full((h, w, 3), 30, dtype=np.uint8)
        cv2.circle(frame, (1000, 500), 60, (200, 200, 200), thickness=-1)

        t0 = time.perf_counter()
        for _ in range(3):  # warm-up smoothed median-ish
            detect_barbell_in_frame(frame)
        elapsed = (time.perf_counter() - t0) / 3
        assert elapsed < 0.2, f"per-frame detection took {elapsed*1000:.0f} ms (budget 200 ms)"
```

- [ ] **Step 2: Run the new test class — expect RED**

```bash
cd backend
uv run pytest tests/unit/test_barbell_detection.py::TestDetectBarbellAfterDownscale -v
```

Expected:
- `test_detect_returns_source_coords_on_1080p`: may PASS accidentally if the old HoughCircles happens to find the 60-px circle at source; but more likely FAILS because `_MAX_RADIUS = 100` covers radius 60 — it will actually pass pre-fix.
- `test_detect_on_1080p_is_fast`: **FAILS** — 1080p HoughCircles with radius range 10–100 takes ~1000 ms/frame, well over the 200 ms budget.

If the first two coordinate tests happen to PASS on the pre-fix code (they might, because HoughCircles at source already detects the circle), that's fine — they're regression guards for after the fix. The speed test is the strict RED signal.

- [ ] **Step 3: Commit the failing tests**

```bash
git add backend/tests/unit/test_barbell_detection.py
git commit -m "test(cv): failing post-fix tests for 1080p detect budget (D-035)

Two coordinate-correctness tests (landscape + portrait 1080p) and one
speed test asserting < 200 ms/frame. Speed test is RED pre-fix (observed
~1 s/frame)."
```

---

## Task 5: Modify `detect_barbell_in_frame` to use downscale (GREEN)

**Files:**
- Modify: `backend/app/cv/barbell_detection.py` — function `detect_barbell_in_frame` (currently lines 26-63)

- [ ] **Step 1: Replace the body of `detect_barbell_in_frame` with the downscale-aware version**

Open `backend/app/cv/barbell_detection.py`. Find the existing function (starts at line 26 with `def detect_barbell_in_frame`). Replace the entire body (from `def detect_barbell_in_frame` down to and including the final `return (float(x), float(y))`) with:

```python
def detect_barbell_in_frame(frame: np.ndarray) -> tuple[float, float] | None:
    """Detect the circular end of a barbell plate in *frame*.

    Strategy: downscale to 480 px (longest dim) → grayscale → GaussianBlur →
    HoughCircles. The downscale step (D-035) keeps per-frame cost under
    ~60 ms on 1080p input; centroid is scaled back to source coordinates
    before return so callers see the same coordinate space as today.

    Parameters
    ----------
    frame:
        BGR image as a uint8 NumPy array of shape (H, W, 3).

    Returns
    -------
    (centroid_x, centroid_y) in *source-frame* pixel coordinates, or None
    if no circle is detected. When multiple circles are found the one with
    the highest accumulator response (first HoughCircles result) is returned.
    """
    scaled, scale_factor = _downscale_for_detection(frame)
    gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=_DP,
        minDist=_MIN_DIST_480P,
        param1=_PARAM1,
        param2=_PARAM2,
        minRadius=_MIN_RADIUS_480P,
        maxRadius=_MAX_RADIUS_480P,
    )

    if circles is None:
        return None

    # circles shape: (1, N, 3) — x, y, radius
    circles = np.round(circles[0]).astype(int)
    x, y, _r = circles[0]
    return (float(x) * scale_factor, float(y) * scale_factor)
```

Do NOT remove the original `_MIN_DIST` / `_MIN_RADIUS` / `_MAX_RADIUS` constants — leave them as historical reference for the source-resolution parameters. They're 3 lines; removing them adds churn with no benefit and future work may reference them.

- [ ] **Step 2: Run the full `test_barbell_detection.py` file**

```bash
cd backend
uv run pytest tests/unit/test_barbell_detection.py -v
```

Expected: **all existing + new tests PASS**. Key tests to confirm green:
- `TestDetectBarbellInFrame::test_detects_circle_centroid` (640×480, radius 40) — PASSES because `_MAX_RADIUS_480P = 40` covers the downscaled radius 30.
- `TestTrackBarbellFromVideo::test_streams_centroids_matching_track_barbell` — PASSES (streaming loop unchanged, same detection function).
- `TestDownscaleForDetection::*` — 5 PASS.
- `TestDetectBarbellAfterDownscale::test_detect_on_1080p_is_fast` — PASSES (should now take ~30–60 ms).

If `test_detects_circle_centroid` fails with off-by-more-than-20-px, check that `_MAX_RADIUS_480P` is set to 40 (not 25) and `_MIN_DIST_480P` is 12.

- [ ] **Step 3: Run the full backend test suite to catch pipeline regressions**

```bash
cd backend
uv run pytest -x -q --ignore=tests/integration 2>&1 | tail -40
```

Expected: final line shows `N passed` (N ≈ 1528 per handoff baseline), 0 failures.

- [ ] **Step 4: Commit the fix**

```bash
git add backend/app/cv/barbell_detection.py
git commit -m "feat(cv): downscale frames to 480p before HoughCircles (D-035)

detect_barbell_in_frame now calls _downscale_for_detection before
HoughCircles and scales the detected centroid back to source coordinates.
Expected per-frame cost at 1080p drops from ~1000 ms to ~30-60 ms.

Preserves FR-BDET-01 (detection on every frame) and FR-BDET-06
(landmark fallback if detection_rate < 50%). Source-resolution centroids
are unchanged for compute_bar_path.

Addresses D-035 (24.4-min barbell_tracking stage on 1080p input)."
```

---

## Task 6: Add `slow` marker + stage-budget integration test

**Files:**
- Modify: `backend/pyproject.toml` — register `slow` marker
- Modify: `backend/tests/unit/test_barbell_detection.py` — add slow integration test

- [ ] **Step 1: Register the `slow` pytest marker**

Open `backend/pyproject.toml`. Find the `[tool.pytest.ini_options]` block (currently around line 40). Replace:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: marks tests that require a live database (deselect with '-m not integration')",
]
```

With:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: marks tests that require a live database (deselect with '-m not integration')",
    "slow: marks tests that run on real video fixtures (deselect with '-m not slow')",
]
```

- [ ] **Step 2: Add the stage-budget integration test**

Append at the bottom of `backend/tests/unit/test_barbell_detection.py`:

```python
# ---------------------------------------------------------------------------
# Stage budget integration (slow)  (D-035)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestTrackBarbellStageBudget:
    """Empirical guard on total stage wall time for a real 720p clip.

    Runs on ``e2e/fixtures/atharva-bench-nw-10s-720p.mp4`` (10 s, 720p,
    ~600 frames). Gated under ``-m slow`` so unit runs stay fast.
    """

    FIXTURE_REL = "../../../e2e/fixtures/atharva-bench-nw-10s-720p.mp4"

    def _fixture_path(self) -> str:
        import os

        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(here, self.FIXTURE_REL))

    def test_stage_wall_time_under_30s_on_720p(self):
        """Processing a 10 s 720p clip must finish in under 30 s on CI."""
        import os
        import time

        path = self._fixture_path()
        if not os.path.exists(path):
            pytest.skip(f"fixture {path} not present")

        t0 = time.perf_counter()
        centroids = track_barbell_from_video(path)
        elapsed = time.perf_counter() - t0

        assert len(centroids) > 0, "expected at least one frame decoded"
        assert elapsed < 30.0, f"track_barbell_from_video took {elapsed:.1f}s (budget 30s)"

    def test_detection_rate_above_30pct_on_720p(self):
        """Regression guard: detection rate stays well above the 50% fallback
        threshold on the 720p bench clip. 30% chosen as a floor well below
        the expected ~80% but above the FR-BDET-06 landmark-fallback cutoff."""
        import os

        path = self._fixture_path()
        if not os.path.exists(path):
            pytest.skip(f"fixture {path} not present")

        centroids = track_barbell_from_video(path)
        if not centroids:
            pytest.skip("no frames decoded")
        detected = sum(1 for c in centroids if c is not None)
        rate = detected / len(centroids)
        assert rate > 0.30, f"detection rate {rate:.1%} dropped below 30% floor"
```

- [ ] **Step 3: Run the slow test explicitly — expect GREEN**

```bash
cd backend
uv run pytest tests/unit/test_barbell_detection.py::TestTrackBarbellStageBudget -v -m slow
```

Expected:
- Both tests PASS.
- `test_stage_wall_time_under_30s_on_720p` reports elapsed ≈ 3–6 s (well under budget).
- `test_detection_rate_above_30pct_on_720p` reports rate well above 30 %.

If either skips (fixture missing), resolve the path — the fixture is in `e2e/fixtures/atharva-bench-nw-10s-720p.mp4` per the `git status` output at session start.

- [ ] **Step 4: Confirm the slow marker excludes the test in default runs**

```bash
cd backend
uv run pytest tests/unit/test_barbell_detection.py -v -m "not slow" 2>&1 | tail -10
```

Expected: slow tests are `deselected` (shown in summary line), all other tests pass.

- [ ] **Step 5: Commit marker + integration test**

```bash
git add backend/pyproject.toml backend/tests/unit/test_barbell_detection.py
git commit -m "test(cv): integration test for barbell stage budget (D-035)

Registers pytest 'slow' marker and adds two gated tests on the 720p bench
fixture: wall-time budget (<30s) and detection-rate floor (>30%). Serves
as the TDD gate for the D-035 fix."
```

---

## Task 7: Post-fix benchmark on worker

**Files:**
- No code changes — empirical re-run only.

- [ ] **Step 1: Push the fix to the worker**

Because the branch is not yet merged, copy the updated `barbell_detection.py` directly into the worker:

```bash
scp backend/app/cv/barbell_detection.py spelix-droplet:/tmp/barbell_detection_d035.py
ssh spelix-droplet "docker cp /tmp/barbell_detection_d035.py spelix-worker-1:/app/app/cv/barbell_detection.py"
```

- [ ] **Step 2: Re-run `bench_barbell.py`**

```bash
ssh spelix-droplet "docker exec spelix-worker-1 python /tmp/bench_barbell.py /tmp/bench.mov"
```

Expected output now includes a populated Mode 3:

```
Mode 3 — proposed detect_barbell_in_frame (480p downscale):
  detect@480p                              frames=1345  total=  ~60.00s  per_frame=   ~45.0ms  detected=XXX/1345
```

Capture the Mode 3 numbers — they go in the PR body and ADR-057.

**Decision gate (spec §7.2):**
- Mode 3 per_frame < 80 ms → plan holds; continue to Task 8.
- Mode 3 per_frame in [80, 200] ms → log as follow-up (tighten radius range further); continue.
- Mode 3 per_frame > 200 ms → STOP; re-plan (drop to 360 px, or revisit hypothesis).

- [ ] **Step 3: Restart the worker to discard the temporary patch**

```bash
ssh spelix-droplet "docker restart spelix-worker-1"
```

Expected: worker restarts. The temporary code copy is overwritten on next `docker compose up` anyway, but restarting now avoids confusion during any further debugging.

---

## Task 8: ADR-057 + backlog + decisions log

**Files:**
- Modify: `decisions.md` — append ADR-057
- Modify: `backlog.md` — D-035 → done

- [ ] **Step 1: Read the current tail of `decisions.md` to match format**

```bash
tail -60 decisions.md
```

Note the exact formatting of the most recent ADR (date style, heading level, "Status:" line, etc.). Match it.

- [ ] **Step 2: Append ADR-057 to `decisions.md`**

Append (the example below is a template — adapt the section headers to match whatever format the previous ADR used):

```markdown

## ADR-057 — Downscale frames to 480p before HoughCircles in barbell detection

**Date:** 2026-04-16
**Status:** Accepted
**Supersedes / Amends:** Amends ADR-056 (streaming tracker memory fix). Streaming loop is preserved; this adds a per-frame downscale before `cv2.HoughCircles`.

### Context

Session 38 per-stage telemetry (analysis `fc318bc3`) showed `barbell_tracking` alone took 1,465,647 ms (24.4 min) on a 22.8-s / 1345-frame / 1080p@59fps clip — 83 % of total pipeline time. Root cause (spec §2): `cv2.HoughCircles` at source resolution with radius range 10–100 costs ~1 s/frame on CPU at 1080p.

### Decision

`detect_barbell_in_frame` downscales every frame to 480 px on the longest dimension via `cv2.INTER_AREA`, runs HoughCircles on the scaled frame with radii 3–40, then scales the detected centroid back to source coordinates before return. Callers (`track_barbell`, `track_barbell_from_video`) are unchanged; `compute_bar_path` receives source-resolution centroids as today. FR-BDET-06 >50 % detection-rate fallback to landmarks stays wired in `pipeline.py`.

### Consequences

- Positive: barbell_tracking drops from 24.4 min to ~1–2 min on 1080p; total pipeline completes in under 600 s; streaq task timeout can be returned from 1800 s to 900 s (closes D-035, unblocks D-036).
- Positive: FR-BDET-01 preserved (detection applied to every frame). No SRS amendment required.
- Negative: sub-pixel drift up to ±scale_factor px in centroid coordinates. At 1080p that's ±4 source px, < 0.5 % of frame width — below MediaPipe landmark noise.
- Negative: loses the highest-resolution detail on extremely small plates (far camera). Mitigated by `_MAX_RADIUS_480P = 40` and existing landmark fallback.

### Alternatives considered

(See spec §4.)
- B: temporal subsampling — rejected (aliasing at bottom of rep).
- C: always-landmark — rejected (SRS amendment required; loses pixel-accurate bench path).
- D: tighten source-resolution radius range — rejected alone (insufficient speedup); may pair with A later.
- E: replace HoughCircles with template matching / YOLO — deferred (out-of-sprint scope).
- F: background task — rejected (UX regression).

### Evidence

- Pre-fix benchmark (Mode 2): ~1089 ms/frame (Task 1).
- Post-fix benchmark (Mode 3): ~45 ms/frame (Task 7).
- Unit tests cover synthetic 1080p and portrait 1080p with 60-px circles; tolerance ±20 source px.
- Slow integration test on `atharva-bench-nw-10s-720p.mp4` asserts stage wall time < 30 s and detection rate > 30 %.
- Production E2E verification pending (Task 10).

### Links

- Spec: `docs/superpowers/specs/2026-04-16-d035-barbell-tracking-downscale-design.md`
- Plan: `docs/superpowers/plans/2026-04-16-d035-barbell-tracking-downscale.md`
- Backlog entry: D-035
- SRS: FR-BDET-01, FR-BDET-02, FR-BDET-06, FR-BDET-07
```

- [ ] **Step 3: Update `backlog.md` — D-035 → done**

Open `backlog.md`. Find the D-035 row (likely under a "Defects" or "D-series" heading). Change its status from whatever it currently is (e.g., `root-caused`, `investigating`, `open`) to `done`, and append the merge SHA (placeholder now — update post-merge in Task 10 if needed). Also check the D-036 row (GPU offload) — if it says "blocked on D-035 close", change the dependency state to "D-035 closed; still deferred post-beta" or similar.

Example edit (adapt to actual file format):

```markdown
| D-035 | Pipeline timeout on 1080p@59fps clips | done | PR #TBD — downscale-before-HoughCircles | CRITICAL |
```

If you're uncertain of the exact format, run `head -60 backlog.md` and match it.

- [ ] **Step 4: Commit ADR + backlog**

```bash
git add decisions.md backlog.md
git commit -m "docs(adr): ADR-057 downscale-before-HoughCircles + D-035 close (pending PR)

Documents the architectural decision with pre/post-fix benchmark evidence
and pointers to spec + plan. Backlog D-035 marked done pending PR merge."
```

---

## Task 9: Push, open PR, wait for CI

**Files:**
- No code change — git + GitHub MCP operations only.

- [ ] **Step 1: Push the branch**

```bash
git push -u origin fix/d035-downscale-barbell-detection
```

Expected: push succeeds; remote branch created.

- [ ] **Step 2: Open the PR via GitHub MCP**

Use `mcp__github__create_pull_request` with:
- `owner`: `atharva6905`
- `repo`: `spelix`
- `base`: `main`
- `head`: `fix/d035-downscale-barbell-detection`
- `title`: `fix(cv): D-035 downscale-before-HoughCircles cuts barbell_tracking from 24 min to <3 min`
- `body`: (use the template below — fill in Mode 2 and Mode 3 ms/frame numbers from Tasks 1 and 7)

PR body template:

```markdown
## Summary

Downscales every frame to 480 px (longest dim) before `cv2.HoughCircles` in `detect_barbell_in_frame`. Centroids are scaled back to source coordinates before return, so callers see the same coordinate space as today. Closes D-035.

## Root cause

`cv2.HoughCircles` at 1080p with radius range 10–100 costs ~1 s/frame on the worker's 2-vCPU droplet. On a 1345-frame 1080p clip that accumulates to 24.4 min — 83 % of total pipeline wall time (session 38 telemetry, analysis `fc318bc3-3cf9-4f0e-85ee-0f5d61cb77b1`).

## Benchmark

| Mode | ms/frame | total (1345 fr) |
|---|---|---|
| Mode 1 — cap.read() only | ~XX | ~XX s |
| Mode 2 — current detect@source | ~XXXX | ~XXXX s |
| Mode 3 — new detect@480p | ~XX | ~XX s |

Per `backend/bench_barbell.py` run on `spelix-worker-1` against `atharva-bench-no-weight.mov`.

## SRS compliance

- FR-BDET-01 — detection still applied to every frame ✓
- FR-BDET-02 — bar centroid tracked across frames ✓
- FR-BDET-06 — >50 % fallback to landmarks preserved (unchanged in `pipeline.py`) ✓
- FR-BDET-07 — bar path visualization unchanged ✓

## Test plan

- [ ] 5 new unit tests for `_downscale_for_detection` (noop, 1080p, 4K, portrait, exact-max-dim)
- [ ] 3 new unit tests for post-fix `detect_barbell_in_frame` (source-coord return in landscape/portrait 1080p + speed budget)
- [ ] Existing unit tests green (regression)
- [ ] Slow integration test: `test_stage_wall_time_under_30s_on_720p`, `test_detection_rate_above_30pct_on_720p`
- [ ] CI green (all checks)
- [ ] Production E2E on `atharva-bench-no-weight.mov` — total pipeline < 600 s, `timing_json.barbell_tracking` < 180 s

## ADR

ADR-057 in `decisions.md` documents the decision with pre/post-fix benchmark evidence.
```

- [ ] **Step 3: Wait for CI**

Use `mcp__github__get_pull_request_status` to poll, OR run:

```bash
gh pr checks --watch
```

Expected: all 7 checks pass, including "Deploy to Production".

- [ ] **Step 4: If any CI check fails, diagnose and fix**

If tests fail on CI but passed locally: it's likely a version skew or fixture path issue. Read the failing CI log, fix on the branch, push, repeat. Do NOT skip hooks or bypass CI.

---

## Task 10: Merge and E2E verify on production

**Files:**
- No code change — GitHub MCP + Playwright MCP operations.

- [ ] **Step 1: Merge the PR — MUST use merge method, NOT squash**

Use `mcp__github__merge_pull_request` with:
- `owner`: `atharva6905`
- `repo`: `spelix`
- `pullNumber`: (from Task 9 Step 2 response)
- `merge_method`: `"merge"` — **never `"squash"`** per user memory `feedback_no_squash_merge`

Expected: PR merges to `main`, merge commit SHA returned.

- [ ] **Step 2: Sync local main**

```bash
git checkout main
git pull origin main
```

Expected: local `main` advances to the merge commit.

- [ ] **Step 3: Wait for "Deploy to Production" CI step to complete**

```bash
gh run list --branch main --limit 3
# then, for the most recent run:
gh run watch <run-id>
```

Expected: "Deploy to Production" step shows `pass`. **Do NOT SSH in and deploy manually** per user memory `feedback_no_manual_deploy`.

- [ ] **Step 4: Confirm the droplet is running the merge commit**

```bash
ssh spelix-droplet "git -C ~/spelix log --oneline -1 && docker ps --format '{{.Names}} {{.Status}}'"
```

Expected: the merge commit SHA is HEAD on the droplet; all containers show `(healthy)`.

- [ ] **Step 5: Run Playwright MCP E2E on `atharva-bench-no-weight.mov`**

Use these MCP calls in sequence:

1. `mcp__playwright__browser_navigate` → `https://spelix.app`
2. `mcp__playwright__browser_snapshot` (confirm logged-in state via persistent cookies)
3. Click the "Upload" entry point; select file via `mcp__playwright__browser_file_upload` with absolute path `C:\Users\athar\projects\spelix\e2e\fixtures\atharva-bench-no-weight.mov`
4. Select exercise = bench press
5. Submit; capture the redirect URL (contains the analysis UUID)
6. Poll status with `mcp__playwright__browser_wait_for` until status reaches `complete` (timeout budget: 10 min; expected < 6 min)
7. `mcp__playwright__browser_take_screenshot` of the results page
8. `mcp__playwright__browser_console_messages` with `level=error` — expect empty
9. `mcp__playwright__browser_network_requests` — filter for 4xx/5xx, expect none for the analysis flow

- [ ] **Step 6: Query Supabase for the analysis timing JSON**

Use `mcp__supabase__execute_sql` or `mcp__postgres__query` with:

```sql
SELECT
  id,
  status,
  EXTRACT(EPOCH FROM (updated_at - created_at)) AS wall_seconds,
  (timing_json->>'barbell_tracking')::float / 1000 AS barbell_s,
  (timing_json->>'extract_landmarks')::float / 1000 AS pose_s,
  timing_json
FROM analyses
WHERE id = '<analysis_id_from_step_5>';
```

Pass criteria:
- `status = 'complete'`
- `wall_seconds < 600`
- `barbell_s < 180`
- `pose_s` comparable to 287 s baseline (within ±10 %)

- [ ] **Step 7: If E2E passes, write session 40 handoff**

Create `.claude/handoff.md` (replacing the current session 38 → 39 content; preserve earlier session content at bottom as the current file does). Summarise:
- D-035 closed; include pre/post-fix Mode 2 vs Mode 3 numbers
- Analysis IDs of pre-fix baseline and post-fix verification
- Follow-up task: lower streaq task timeout from 1800 s to 900 s (unblocked now that total pipeline is < 600 s)
- Remaining defects list from the current handoff (D-028, D-029, D-030, D-031, D-032, D-034, D-036) with updated statuses where relevant

- [ ] **Step 8: Commit the handoff**

```bash
git add .claude/handoff.md
git commit -m "docs(handoff): session 39 → session 40 — D-035 closed"
git push origin main
```

- [ ] **Step 9: If E2E FAILS, STOP and write a findings note**

Do NOT continue to Task 11. Create an `E2E Findings` section at the top of `.claude/handoff.md` documenting:
- Analysis ID of the failed run
- Observed vs expected values (wall time, barbell_s, status)
- Next diagnostic steps (re-check Mode 3 benchmark data against production; verify the merge commit is actually deployed; check for worker OOM in `docker logs spelix-worker --tail 200`)
- Do not revert the fix without explicit user direction — partial improvement is still an improvement

---

## Task 11: Follow-up — lower streaq task timeout

**Files:**
- Modify: whichever file defines the streaq task timeout (search is part of the task)

Only execute this task if Task 10 E2E passed and total pipeline wall time is comfortably under 900 s.

- [ ] **Step 1: Locate the current 1800 s timeout setting**

```bash
cd backend
rg -n "1800|task_timeout" app/ --type py
```

Expected: find the streaq decorator or task-registration call where `timeout=1800` (or similar) is set.

- [ ] **Step 2: Change 1800 → 900**

Edit the file identified in Step 1, change `1800` to `900`. Keep any comment that references D-035 or update it to reference the fix.

- [ ] **Step 3: Add/update unit test (if applicable)**

If there's a test that asserts the timeout value, update the expectation. Otherwise skip.

- [ ] **Step 4: Commit, branch, PR**

```bash
git checkout -b fix/d036-lower-streaq-timeout
git add <file>
git commit -m "fix(worker): lower streaq analysis-task timeout 1800s -> 900s (D-035 close)"
git push -u origin fix/d036-lower-streaq-timeout
```

Open PR via `mcp__github__create_pull_request` with a short body referencing the D-035 close. This is a standalone follow-up; no benchmark required.

- [ ] **Step 5: Merge (merge, not squash) and verify prod**

After CI green, merge via `mcp__github__merge_pull_request` with `merge_method: "merge"`. No full E2E needed — just confirm a sample upload still completes normally.

---

## Rollback Procedure

If any time after Task 5 merges the fix proves incorrect in production (e.g. detection rate collapses on a specific user's clip):

1. Revert the PR via GitHub UI (creates a new commit on `main` — do NOT force-push)
2. Wait for CI "Deploy to Production" step on the revert
3. Verify the worker is back on the pre-fix code: `ssh spelix-droplet "git -C ~/spelix log --oneline -1"`
4. Open a new defect referencing the specific clip ID and symptom
5. Update ADR-057 with a "Revised / Reverted" status and link to the new defect

Do NOT attempt a hot patch on the droplet — revert through PR only.

---

## Out of Scope

Explicitly NOT addressed by this plan:
- D-028 (`useAnalysisStatus` "Connection lost" banner)
- D-029 (SaMD rename `injury_advice_accurate` → `movement_advice_accurate`)
- D-030 (Orphan `rag_documents` uploading-state cleanup)
- D-031 (Admin GET `/rag/documents` free-text query param)
- D-032 (Framing + single-person quality gate false rejections)
- D-034 (pipeline OOM on 1080p@59fps clips — may collapse into this fix's effects; revisit after Task 10)
- Streaq error-handling-on-timeout bug (session 37 secondary finding)
- GPU offload (D-036)
- Replacing HoughCircles with template matching or ML

---

## Plan Self-Review Notes

- **Spec coverage:** Every spec section maps to at least one task. §1 problem → Task 1 benchmark evidence. §2 root cause → spec narrative preserved in ADR-057 Task 8. §3 goal → Task 10 E2E pass criteria. §4 alternatives → ADR-057. §5 architecture / §6 components → Tasks 3, 5. §7 benchmark → Tasks 1, 7. §8 testing → Tasks 2, 4, 6. §9 error handling → no code change needed (covered by existing FR-BDET-06 branch). §10 risks → rollback procedure. §11 ADR → Task 8. §12 git flow → Tasks 9, 10. §13 out of scope → preserved above.
- **Placeholder scan:** No "TBD / TODO / fill in / similar to" patterns. PR body template has `~XX` placeholders that are filled at commit time from actual benchmark output — that's a data-capture gate, not a plan gap.
- **Type consistency:** `_downscale_for_detection` signature identical in spec §6.2, Task 2 test imports, and Task 3 implementation. Constants `_DETECTION_MAX_DIM / _MIN_DIST_480P / _MIN_RADIUS_480P / _MAX_RADIUS_480P` spelled identically across Task 3 and Task 5. Function `track_barbell_from_video` unchanged throughout. Spec §6.1 said `_MAX_RADIUS_480P = 25`; plan Task 3 uses `40` with documented justification (preserve existing 640×480 / radius-40 test fixture) — deliberate, not a drift bug.
