# D-035 Fix — Downscale-before-HoughCircles in `track_barbell_from_video`

**Status:** approved design — 2026-04-16
**Author:** session 39 planning
**Supersedes:** nothing (amends ADR-056 streaming tracker; new ADR-057 to be written with implementation)
**Related:** D-034 (pipeline OOM), D-035 (pipeline timeout), D-036 (GPU offload — deferred)
**SRS references:** FR-BDET-01, FR-BDET-02, FR-BDET-06, FR-BDET-07

## 1. Problem

Session 38 per-stage telemetry (analysis `fc318bc3-3cf9-4f0e-85ee-0f5d61cb77b1`) showed that on a 22.8 s / 1345-frame / 1080p @ 59 fps bench-press clip, the `barbell_tracking` stage alone took **1,465,647 ms (24.4 min)** — **83.4 %** of total pipeline wall time. Every other CV stage combined (pose extract, quality gates, angle series, rep detect, metric extract, confidence, form scoring) totals under 5 minutes. Pose extraction itself is 286 s — already within budget.

Cost breakdown, measured per frame: 1,465,647 ms ÷ 1345 frames = **1,089 ms/frame**. This is wall-time per frame, not detection cost; streaming `cv2.VideoCapture.read()` I/O is pipelined with the detection call inside the loop.

Consequence: every real-user 1080p upload exceeds the 1800 s streaq task timeout. D-035 is the hard blocker for the L2 sprint's ship gate (2026-05-03).

## 2. Root Cause

`backend/app/cv/barbell_detection.py::detect_barbell_in_frame` runs `cv2.HoughCircles` with these parameters at source resolution:

```python
_DP = 1.2
_MIN_DIST = 50
_PARAM1 = 100
_PARAM2 = 30
_MIN_RADIUS = 10
_MAX_RADIUS = 100
```

At 1080p (1920 × 1080 = 2.07 M pixels) with a radius range of 90 (10 → 100), `cv2.HoughCircles` performs a gradient-space vote across all candidate (x, y, r) triples. Empirical CPU cost at this resolution with this radius range is 0.5 – 1.5 s/frame — consistent with the observed 1.089 s/frame.

**Ruled out** by reading the code (`barbell_detection.py:84-118`):
- No per-frame `VideoCapture` reopen or seek — clean sequential `cap.read()`.
- No retry / duplication in the loop.
- No XNNPACK contention — MediaPipe is fully released by this stage.
- No color-space conversion cost dominance — `cvtColor` + `GaussianBlur` are O(pixels) and together are <5 % of HoughCircles cost.

## 3. Goal

Reduce the `barbell_tracking` stage to **≤ 180 s on the production bench clip** (`atharva-bench-no-weight.mov`, 22.8 s 1080p) without:
- Dropping below 50 % barbell detection rate on the same clip (triggers FR-BDET-06 landmark fallback — acceptable but a visible regression if the pixel-path was previously detecting).
- Regressing `compute_bar_path` metrics (`lateral_deviation_px`, `vertical_range_px`, `path_consistency`) by more than 1 % vs the pre-fix run on the same clip.
- Violating FR-BDET-01 ("OpenCV-based barbell detection applied to **each frame**").

Secondary outcome: total pipeline completes in under 600 s on the bench clip → restore `streaq` task timeout from its current 1800 s safety-net back to 900 s → D-035 closes.

## 4. Decision Matrix

| Option | Expected speedup | Quality risk | SRS fit | Sprint fit |
|---|---|---|---|---|
| A: Downscale frames to 480p max dim before HoughCircles (**chosen**) | 15 – 20× | Minor — plate ≈ 35 – 65 px at 480p, still a clear circle | FR-BDET-01 preserved (every frame still detected) | 1 day incl. TDD + E2E |
| B: Temporal subsampling (every Nth frame, interpolate) | 2 – 5× | High — temporal aliasing at bottom-of-rep | FR-BDET-01 weakened (not every frame) | 1 day |
| C: Skip pixel detection, always use landmarks | Removes stage entirely | Loses pixel-accurate bar path for bench (wrists ≠ bar) | FR-BDET-01/02 violated — requires SRS amendment | 0.5 day + amendment overhead |
| D: Tighten HoughCircles params at source resolution | 2 – 3× | Higher false-negative risk | Fine | 0.5 day |
| E: Replace HoughCircles with template match / YOLO | Potentially 50× | Unknown accuracy | Fine | > 3 days, out of L2 scope |
| F: Defer annotation & bar path to background task | Moves cost off critical path | UX regression, multi-write status state machine | Fine | > 2 days |

**Chosen: A.** Best speedup per risk per sprint-day. Compounds cleanly with D later if 480p isn't enough (shrink radius range further). C is a fallback escape valve post-merge via FR-BDET-06.

**Not chosen, with rationale:**
- **B**: temporal aliasing at the deepest point of the rep (velocity = 0, which is exactly where we want sample density) is unacceptable for a coaching product.
- **C**: the SRS is set in stone at v2.1; amendment is out-of-band for a 19-day sprint. FR-BDET-06 already exists as the degraded-mode exit; C would collapse always-on pixel detection into always-landmark — wrong default.
- **D alone**: insufficient speedup; paired with A it's a follow-up if bench shows 480p is inadequate.
- **E**: correct long-term answer, wrong tool for a sprint fix.
- **F**: architecturally invasive; re-introduces a class of "where did my annotated video go" UX bugs that D-031-era cleanup already wrestled with.

## 5. Architecture

One-file change: `backend/app/cv/barbell_detection.py`. Add downscale step inside `detect_barbell_in_frame`; scale centroid back to source coordinates before return. Callers (`track_barbell`, `track_barbell_from_video`) get the speedup transparently.

### 5.1 Data flow (per frame)

```
cap.read()                                     # BGR frame, source resolution (e.g. 1920×1080)
 → _downscale_for_detection(frame, 480)        # returns (scaled_frame, scale_factor)
 → cv2.HoughCircles on scaled_frame            # fast — ≤ 50 ms/frame expected
 → (cx, cy) in 480p coordinates
 → (cx * scale_factor, cy * scale_factor)      # back to source coordinates
 → centroids.append(...)                       # source-resolution centroids
```

### 5.2 `compute_bar_path` input unchanged

`compute_bar_path` receives source-resolution `centroids` + source-resolution `frame_width`/`frame_height` (as today). All downstream normalisation (`x/frame_width`) is identical. Sub-pixel error from scale-back is bounded by `scale_factor` ≈ 4 px at 1080p → < 0.5 % of frame width. Below the MediaPipe landmark noise floor.

### 5.3 What does not change

- `track_barbell_from_video` streaming `cap.read()` loop — stays as-is (D-034 / ADR-056 memory fix preserved).
- `compute_bar_path` / `compute_bar_path_from_landmarks` — signatures and math unchanged.
- `pipeline.py` barbell_tracking stage — unchanged; still dispatches via `loop.run_in_executor`.
- FR-BDET-06 >50 % detection-rate branch in `pipeline.py:654-672` — unchanged; still the safety net.

## 6. Components

### 6.1 New constants

```python
_DETECTION_MAX_DIM = 480           # longest dimension for HoughCircles input
_MIN_RADIUS_480P = 3               # scaled from 10 at 1080p (ratio 4.0)
_MAX_RADIUS_480P = 25              # scaled from 100 at 1080p
_MIN_DIST_480P = 12                # scaled from 50 at 1080p
```

Prior constants (`_MIN_DIST`, `_MIN_RADIUS`, `_MAX_RADIUS`) are retained for reference in a module docstring comment and removed from active use — the `_480P` variants are what HoughCircles receives.

### 6.2 New helper

```python
def _downscale_for_detection(
    frame: np.ndarray, max_dim: int = _DETECTION_MAX_DIM
) -> tuple[np.ndarray, float]:
    """Downscale *frame* so its longest side is ≤ *max_dim*.

    Returns (scaled_frame, scale_factor) where scale_factor is the
    multiplier to convert a coordinate in the scaled frame back to
    the source frame. No-op (scale_factor=1.0) when already small.
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

### 6.3 Modified `detect_barbell_in_frame`

```python
def detect_barbell_in_frame(frame: np.ndarray) -> tuple[float, float] | None:
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
    circles = np.round(circles[0]).astype(int)
    x, y, _r = circles[0]
    return (float(x) * scale_factor, float(y) * scale_factor)
```

## 7. Benchmark Task (mandatory, before code change)

Per decision (brainstorm Question 1, Option A), a diagnostic benchmark runs first and commits to the same branch as evidence for the ADR and future debugging.

### 7.1 Artifact: `backend/bench_barbell.py`

A short script that runs three modes on `/tmp/bench.mov` inside the worker container:

- **Mode 1 — I/O only:** `cv2.VideoCapture.read()` loop, no detection. Confirms per-frame read cost.
- **Mode 2 — Current detection at source:** run today's `detect_barbell_in_frame` unchanged. Establishes the baseline ms/frame on the target hardware.
- **Mode 3 — Proposed 480p path:** run the new `detect_barbell_in_frame` with downscale. Confirms ≤ 80 ms/frame target.

Output: printed table with `frames, total_s, ms_per_frame, detected_count` per mode.

### 7.2 Decision gate

- Mode 3 < 80 ms/frame → proceed with implementation plan as designed.
- Mode 3 in [80, 200] ms/frame → proceed, but add a follow-up task to tighten radius range (pair option D).
- Mode 3 > 200 ms/frame → re-plan; likely drop to 360 px max-dim.
- Mode 2 not dominant (if Mode 1 is > 50 % of Mode 2 cost) → re-plan; the bug is I/O, not detection.

The benchmark is committed before the fix so reviewers can re-run it post-merge as regression evidence.

## 8. Testing

### 8.1 Unit tests — `backend/tests/unit/test_barbell_detection.py`

| Test | Purpose |
|---|---|
| `test_downscale_noop_for_small_frames` | 480×270 input → returned frame is identity, scale_factor == 1.0 |
| `test_downscale_1080p_to_480p` | 1920×1080 synthetic frame → shape `(270, 480, 3)`, scale_factor ≈ 4.0 |
| `test_downscale_4k_to_480p` | 3840×2160 synthetic frame → shape `(270, 480, 3)`, scale_factor ≈ 8.0 |
| `test_detect_returns_source_coords_after_downscale` | draw a filled circle at (1000, 500) radius 40 px on 1920×1080 black frame → detected centroid within ±10 px of (1000, 500) |
| `test_detect_preserves_existing_720p_behaviour` | existing 1280×720 test case still passes with same tolerance — regression guard |
| `test_detect_returns_none_when_no_circle` | 480p black frame → None |

### 8.2 Integration test — slow marker

`test_track_barbell_from_video_stage_budget` (gated by `pytest -m slow`):
- Input: `e2e/fixtures/atharva-bench-nw-10s-720p.mp4` (10 s, 720p, already in repo)
- Asserts: wall time < 30 s on CI hardware
- Asserts: detection rate within ±5 % of today's rate on the same clip (capture pre-fix baseline in the same test as a constant)
- This test is the **TDD gate** for the implementation task

### 8.3 Existing tests to re-run unchanged

- `test_bar_path_computed_when_detection_rate_above_50pct`
- `test_landmark_fallback_when_detection_rate_below_50pct`
- All `test_pipeline_*` integration tests — verify pipeline wiring and FR-BDET-06 branch still work

### 8.4 Production E2E (post-merge)

On the same bench clip (`atharva-bench-no-weight.mov`) via Playwright MCP → `spelix.app` → upload → wait for completion. Success criteria:
- Total pipeline wall time < 600 s
- `timing_json.barbell_tracking` < 180 s
- `detection_rate` (derived from `centroids`) within ±5 % of the fc318bc3 baseline (if recoverable from logs) or > 50 % in absolute terms
- Status transitions reach `complete` (not `quality_gate_pending`)
- Annotated video and bar-path plot render on results page
- No console errors, no 4xx/5xx in network tab

If green → close D-035; open follow-up task to lower `streaq` task timeout from 1800 s to 900 s.

## 9. Error Handling

No new exceptions introduced.
- `_downscale_for_detection` is pure — takes a NumPy array, returns a NumPy array + float.
- The existing `circles is None` guard already handles the "no detection" case; unchanged.
- The existing >50 % detection-rate branch in `pipeline.py` still handles low-detection-rate clips via `compute_bar_path_from_landmarks`.
- `cv2.resize` on an empty / malformed frame would raise `cv2.error`; today the caller (`track_barbell_from_video`) breaks out of the loop on `ret=False` so this path is unreachable.

## 10. Risk Ledger

| Risk | Likelihood | Mitigation |
|---|---|---|
| Detection rate < 50 % at 480p on some real clips | Low (bumper plates are large) | FR-BDET-06 landmark fallback auto-engages; no UX break |
| Plate subtends < 3 px at 480p on far-camera shots | Very low | `minRadius=3` is floor; same video would fail at any scale |
| Sub-pixel drift distorts `compute_bar_path` metrics | Negligible | < 0.5 % of frame width at 1080p; below MediaPipe noise |
| 4K input edge case | Low | Scale factor becomes 8.0; detection still runs at 480p; math unchanged |
| Benchmark result surprises us (hypothesis wrong) | Low (code read is definitive) | Decision gate in §7.2 triggers re-plan |
| Post-merge CI flake on slow integration test | Medium | Gate under `pytest -m slow`; runs locally + in dedicated CI job, not every unit run |

## 11. ADR Obligations (with implementation)

- **New ADR-057**: "Downscale frames to 480p before HoughCircles to contain per-frame cost on 1080p+ inputs." Links to this spec, references D-035 close evidence, amends ADR-056 (streaming tracker memory fix remains in force — downscale is additive to streaming).
- `decisions.md` append.
- `backlog.md`: D-035 row → status `done` + merge SHA; D-036 row unblocked.
- `memory.md`: session state update at close.

## 12. Git + Ship Flow

- Branch: `fix/d035-downscale-barbell-detection`
- Base: `main`
- Commits (TDD order):
  1. `chore(cv): add bench_barbell.py diagnostic for HoughCircles cost`
  2. `test(cv): failing unit tests for 480p downscale detection`
  3. `feat(cv): downscale frames to 480p before HoughCircles`
  4. `test(cv): integration test for track_barbell stage budget`
  5. `docs(adr): ADR-057 downscale-before-HoughCircles + D-035 close`
- PR title: `fix(cv): D-035 downscale-before-HoughCircles cuts barbell_tracking from 24 min to <3 min`
- Merge: `mcp__github__merge_pull_request` with `merge_method: "merge"` (never squash — per user memory `feedback_no_squash_merge`)
- Post-merge: CI "Deploy to Production" runs automatically → do NOT SSH deploy manually (per user memory `feedback_no_manual_deploy`) → Playwright MCP E2E → close D-035

## 13. Out of Scope

- GPU offload for barbell tracking (D-036 — deferred post-beta).
- Replacing HoughCircles with template match or ML (post-L2).
- Per-analysis resolution tuning via `thresholds_v1.json` (not yet justified — YAGNI).
- Fixing the streaq error-handling bug (secondary finding from session 37; file as separate defect; not blocking D-035 close).
- Addressing D-028 / D-029 / D-030 / D-031 / D-032 / D-034 (separate defects; tracked in backlog).
