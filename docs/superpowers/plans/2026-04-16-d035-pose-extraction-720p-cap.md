# D-035: Pose Extraction 720p Cap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the 900s `process_analysis` task-timeout on full-length 1080p clips by downscaling each frame to a 1280-long-side cap before feeding it to MediaPipe BlazePose Heavy — the pose-extraction analogue of the `_MAX_ANNOTATION_DIM = 1280` cap already in place for annotation video generation.

**Architecture:** Add a `_MAX_POSE_DIM = 1280` constant and `_pose_frame_dimensions(src_w, src_h)` helper to `backend/app/cv/pose_extraction.py`, then `cv2.resize` each frame inside the `extract_landmarks` read loop before passing it to MediaPipe. Source `(width, height)` are still returned from the function so downstream consumers (`check_minimum_resolution`, `compute_bar_path`, quality-gate pixel-jump math) keep operating on source dimensions; MediaPipe landmarks are normalized `[0,1]` so downsampling is invisible to everything after pose extraction.

**Tech Stack:** Python 3.12, OpenCV headless (`cv2.resize`), MediaPipe Tasks API, pytest, pytest-mock.

**Closes:** D-035 (surfaced 2026-04-16 by the full-clip E2E verification in PR #59 — `atharva-bench-no-weight.mov` 22.8s/1080p@59fps/1352 frames times out cleanly at 900s on the 2-vCPU droplet, no OOM, CPU pinned at 180–196%). Fix path (a) from ADR-057. Mirrors the annotation cap shipped in PR #57 (`backend/app/cv/artifact_generation.py:41-49`).

**Does NOT close:** D-028, D-029, D-030, D-031, D-032 (done), D-033 (done), D-034 (done).

---

## Background — why this fix, what it leaves intact

- **BlazePose Heavy runtime is roughly linear with input pixel count.** 1080p (2,073,600 px) costs ~150–180 ms/frame on the droplet's 2 vCPUs. 720p (921,600 px) costs ~70–90 ms/frame. At 1352 frames, that's ~225s → ~95s — a ~130s reduction in the pose-extraction phase of the 900s task budget.
- **Downsampling ≤720p does NOT degrade clinical-grade angle estimation for full-body barbell lifts.** Sports-CV literature treats 720p as the safe minimum. Codebase already validated it end-to-end: `atharva-bench-nw-10s-720p.mp4` produced `form_score_overall=7.27` with 10/10 deterministic agent nodes in PR #57 verification.
- **Landmarks are normalized `[0, 1]`.** Feeding a 720p downscale of a 1080p source to MediaPipe and multiplying the returned landmark `x`/`y` by the ORIGINAL width/height gives pixel coords that match what the user filmed. This is why `extract_landmarks` must return source dimensions, not downscaled dimensions.
- **Annotation and bar-path are unaffected.** Annotation (`generate_annotated_video` at `backend/app/cv/artifact_generation.py:57`) opens the source video directly via its own `cv2.VideoCapture` and applies its own `_annotation_dimensions` cap. Bar-path pixel math in `compute_bar_path` uses the source `frame_width`/`frame_height` passed from the pipeline's `result.frame_width/height`.
- **`check_minimum_resolution`** at `backend/app/cv/quality_gates.py:400` evaluates `min(frame_width, frame_height)` against a threshold. We return source dims, so a legitimate sub-720p source is still rejected at the gate; a 1080p source still passes. Semantics preserved.

## Non-goals

- Not touching `extract_frames` (dead code post-PR #59).
- Not switching BlazePose Heavy → Lite.
- Not changing the 900s `process_analysis` timeout.
- Not adding a frame-sampling / frame-skip strategy.
- Not introducing an ffmpeg pre-process step.

---

## File Structure

All changes live on branch `fix/pose-extraction-720p-cap`.

- **Modify:** `backend/app/cv/pose_extraction.py` — add `_MAX_POSE_DIM`, `_pose_frame_dimensions`, per-frame resize inside `extract_landmarks`. Module docstring gets one line referencing D-035 / ADR-057.
- **Modify:** `backend/tests/unit/test_pose_extraction.py` — extend `_run_extract` helper to capture `mp.Image(data=…)` array shapes, add `TestPoseFrameDimensions` class (pure-function tests of the helper), add `TestFrameDownsampling` class (end-to-end behavior through `extract_landmarks`).
- **Modify:** `backlog.md` — flip D-035 from `pending` → `done` with the merge SHA.
- **Modify:** `decisions.md` — append ADR-058 documenting the 720p cap as the closing fix for D-035 (mirrors ADR-057's role for D-034).
- **Modify:** `.claude/handoff.md` — add Session 35 completion note.

No new files, no migrations, no schema changes, no frontend touches.

---

## Task 1: Add `_MAX_POSE_DIM` constant and `_pose_frame_dimensions` helper (pure function TDD)

**Files:**
- Modify: `backend/app/cv/pose_extraction.py` (constants block ~line 32-43, new helper after `_resolve_model_path` around line 82)
- Modify: `backend/tests/unit/test_pose_extraction.py` (add `TestPoseFrameDimensions` class at end of file)

- [ ] **Step 1: Baseline — run full backend test suite from a clean tree**

```bash
cd backend && uv run pytest tests/ -x -q --tb=short 2>&1 | tail -5
```

Expected: `1520 passed, 25 skipped` (matches handoff §3). If anything is failing on `main`, STOP and report — do not layer D-035 changes on top of a broken baseline.

- [ ] **Step 2: Create and switch to the feature branch**

```bash
git checkout main && git pull
git checkout -b fix/pose-extraction-720p-cap
```

- [ ] **Step 3: Write the failing tests for `_pose_frame_dimensions`**

Append this class at the end of `backend/tests/unit/test_pose_extraction.py` (after `TestModelPathResolution`):

```python
class TestPoseFrameDimensions:
    """`_pose_frame_dimensions` caps the long side at 1280, never upscales, rounds even.

    Mirrors `_annotation_dimensions` in artifact_generation.py. See D-035 / ADR-057.
    """

    def test_cap_constant_is_1280(self):
        """Matches _MAX_ANNOTATION_DIM by convention."""
        from app.cv.pose_extraction import _MAX_POSE_DIM

        assert _MAX_POSE_DIM == 1280

    def test_landscape_1080p_caps_to_1280x720(self):
        from app.cv.pose_extraction import _pose_frame_dimensions

        assert _pose_frame_dimensions(1920, 1080) == (1280, 720)

    def test_portrait_1080p_caps_to_720x1280(self):
        from app.cv.pose_extraction import _pose_frame_dimensions

        assert _pose_frame_dimensions(1080, 1920) == (720, 1280)

    def test_720p_source_unchanged(self):
        from app.cv.pose_extraction import _pose_frame_dimensions

        assert _pose_frame_dimensions(1280, 720) == (1280, 720)
        assert _pose_frame_dimensions(720, 1280) == (720, 1280)

    def test_sub_720p_not_upscaled(self):
        """Never upscale — scale is capped at 1.0."""
        from app.cv.pose_extraction import _pose_frame_dimensions

        assert _pose_frame_dimensions(640, 480) == (640, 480)
        assert _pose_frame_dimensions(320, 240) == (320, 240)

    def test_odd_source_dimensions_rounded_even(self):
        """Rounds to even dims so any downstream H.264 pipeline stays happy."""
        from app.cv.pose_extraction import _pose_frame_dimensions

        w, h = _pose_frame_dimensions(1921, 1081)
        assert w % 2 == 0
        assert h % 2 == 0
        # 1921 > 1280 so scale = 1280/1921 = 0.6663..., 1921 * 0.6663 ≈ 1280, 1081 * 0.6663 ≈ 720
        assert w == 1280
        assert h == 720

    def test_square_source_at_cap(self):
        from app.cv.pose_extraction import _pose_frame_dimensions

        # 2000×2000 → scale = 1280/2000 = 0.64 → (1280, 1280)
        assert _pose_frame_dimensions(2000, 2000) == (1280, 1280)
```

- [ ] **Step 4: Run the new tests to confirm they fail with `ImportError`**

```bash
cd backend && uv run pytest tests/unit/test_pose_extraction.py::TestPoseFrameDimensions -x -v
```

Expected: every test fails at the `from app.cv.pose_extraction import …` line with `ImportError: cannot import name '_MAX_POSE_DIM'` (or `'_pose_frame_dimensions'`).

- [ ] **Step 5: Implement the constant and helper**

In `backend/app/cv/pose_extraction.py`:

Add to the constants block (after line 43, the `_DEFAULT_MODEL_PATH` definition):

```python
# Maximum long-side dimension fed to MediaPipe BlazePose. Frames whose
# longest side exceeds this get ``cv2.resize``-downscaled before inference.
# Mirrors ``_MAX_ANNOTATION_DIM`` in artifact_generation.py. See D-035 /
# ADR-057 — BlazePose Heavy on 2 vCPUs takes ~150–180 ms/frame at 1080p
# (blows the 900 s streaq task budget on a 22.8 s @59 fps clip) vs ~70–90
# ms/frame at 720p with no measurable landmark degradation for
# clinical-grade full-body angle estimation.
_MAX_POSE_DIM: int = 1280
```

Add the helper function after `_resolve_model_path` (before the `# Public API` section header around line 83):

```python
def _pose_frame_dimensions(src_width: int, src_height: int) -> tuple[int, int]:
    """Compute pose-extraction input dimensions, capping the long side at 1280.

    Mirrors ``_annotation_dimensions`` in ``app/cv/artifact_generation.py``.
    Never upscales (``scale`` is clamped to ``1.0``). Rounds both dimensions
    down to the nearest even integer — a convention shared with the
    annotation cap and friendly to downstream H.264 encoders, even though
    MediaPipe itself does not require it.
    """
    scale = min(1.0, _MAX_POSE_DIM / max(src_width, src_height))
    w = round(src_width * scale)
    h = round(src_height * scale)
    return w - w % 2, h - h % 2
```

- [ ] **Step 6: Re-run the new tests to confirm they pass**

```bash
cd backend && uv run pytest tests/unit/test_pose_extraction.py::TestPoseFrameDimensions -x -v
```

Expected: 7 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/cv/pose_extraction.py backend/tests/unit/test_pose_extraction.py
git commit -m "feat(cv): add _MAX_POSE_DIM + _pose_frame_dimensions helper (D-035)"
```

---

## Task 2: Downsample each frame inside `extract_landmarks` before MediaPipe inference

**Files:**
- Modify: `backend/tests/unit/test_pose_extraction.py` (extend `_run_extract` helper to capture `mp.Image(data=…)` shapes, add `TestFrameDownsampling` class)
- Modify: `backend/app/cv/pose_extraction.py` (insert resize logic in the `extract_landmarks` read loop)

- [ ] **Step 1: Extend the test helper to capture the array shape passed into `mp.Image`**

In `backend/tests/unit/test_pose_extraction.py`, find the module-level `_constructor_args: dict = {}` declaration (around line 99) and add immediately below it:

```python
# Captures the shape of every ``data`` array passed to ``mp.Image`` during a
# single ``_run_extract`` call so tests can assert that resize happened (or
# didn't) before MediaPipe inference. Cleared at the start of each call.
_mp_image_call_shapes: list[tuple[int, ...]] = []
```

Then in the `_run_extract` helper (around line 102), locate the current body and apply two edits.

First, at the top of the function (next to `_constructor_args.clear()`), also clear the new capture list:

Old:
```python
    _constructor_args.clear()
```

New:
```python
    _constructor_args.clear()
    _mp_image_call_shapes.clear()
```

Second, locate the line `mp_image_cls = MagicMock()` (around line 135) and replace it with a side-effect that records the `data` kwarg shape:

Old:
```python
    mp_image_cls = MagicMock()
    mp_image_format = MagicMock()
    mp_image_format.SRGB = "SRGB"
```

New:
```python
    def _mp_image_side_effect(image_format, data):
        # ``data`` is the BGR→RGB-converted numpy frame passed into
        # MediaPipe's Image constructor. We record its shape so the
        # TestFrameDownsampling suite can assert resize behavior without
        # mocking cv2.resize itself.
        _mp_image_call_shapes.append(tuple(data.shape))
        return MagicMock()

    mp_image_cls = MagicMock(side_effect=_mp_image_side_effect)
    mp_image_format = MagicMock()
    mp_image_format.SRGB = "SRGB"
```

This change is additive — existing tests do not inspect `_mp_image_call_shapes` so their behavior is unchanged.

- [ ] **Step 2: Write the failing end-to-end tests for frame downsampling**

At the very bottom of `backend/tests/unit/test_pose_extraction.py`, append:

```python
class TestFrameDownsampling:
    """`extract_landmarks` resizes frames above _MAX_POSE_DIM before inference (D-035)."""

    def test_1080p_landscape_source_resized_to_1280x720_for_mediapipe(self):
        cap = _make_mock_cap(num_frames=1, fps=30.0, width=1920.0, height=1080.0)
        _, fps, width, height = _run_extract(cap, [_make_pose_landmarks_list()])

        # extract_landmarks returns SOURCE dimensions — landmarks are
        # normalized [0,1] so downstream pixel math must use the original
        # frame size, not the downscaled one.
        assert width == 1920
        assert height == 1080
        assert fps == 30.0

        # But MediaPipe received a resized frame.
        assert len(_mp_image_call_shapes) == 1
        # cv2.cvtColor preserves shape → (h, w, 3). After resize to 1280×720:
        assert _mp_image_call_shapes[0] == (720, 1280, 3)

    def test_1080p_portrait_source_resized_to_720x1280_for_mediapipe(self):
        cap = _make_mock_cap(num_frames=1, fps=30.0, width=1080.0, height=1920.0)
        _, _, width, height = _run_extract(cap, [_make_pose_landmarks_list()])

        assert width == 1080
        assert height == 1920
        assert _mp_image_call_shapes[0] == (1280, 720, 3)

    def test_720p_source_not_resized(self):
        """Exactly at the cap — cv2.resize should NOT be called (no-op path)."""
        cap = _make_mock_cap(num_frames=1, fps=30.0, width=1280.0, height=720.0)
        _run_extract(cap, [_make_pose_landmarks_list()])

        assert _mp_image_call_shapes[0] == (720, 1280, 3)

    def test_sub_720p_source_not_upscaled(self):
        """480p → still 480p into MediaPipe; the cap never upscales."""
        cap = _make_mock_cap(num_frames=1, fps=30.0, width=640.0, height=480.0)
        _, _, width, height = _run_extract(cap, [_make_pose_landmarks_list()])

        assert width == 640
        assert height == 480
        assert _mp_image_call_shapes[0] == (480, 640, 3)

    def test_all_frames_downsampled_when_above_cap(self):
        """Multi-frame clip: every frame gets resized, not just the first."""
        cap = _make_mock_cap(num_frames=3, fps=30.0, width=1920.0, height=1080.0)
        _run_extract(
            cap,
            [
                _make_pose_landmarks_list(),
                _make_pose_landmarks_list(),
                _make_pose_landmarks_list(),
            ],
        )

        assert len(_mp_image_call_shapes) == 3
        for shape in _mp_image_call_shapes:
            assert shape == (720, 1280, 3)

    def test_landmark_shape_still_33x5_after_downsample(self):
        """Sanity — downsampling does not break the landmark output contract."""
        cap = _make_mock_cap(num_frames=2, fps=30.0, width=1920.0, height=1080.0)
        landmarks_per_frame, _, _, _ = _run_extract(
            cap, [_make_pose_landmarks_list(), _make_pose_landmarks_list()]
        )

        assert len(landmarks_per_frame) == 2
        for arr in landmarks_per_frame:
            assert arr.shape == (33, 5)

    def test_no_pose_frame_still_zero_filled_after_downsample(self):
        """NO_POSE handling is unchanged when downsampling is active."""
        cap = _make_mock_cap(num_frames=2, fps=30.0, width=1920.0, height=1080.0)
        landmarks_per_frame, _, _, _ = _run_extract(
            cap,
            [
                _make_pose_landmarks_list(visibility=0.8, presence=0.8),
                [],  # no pose detected on frame 2
            ],
        )

        import numpy as np

        assert not np.all(landmarks_per_frame[0] == 0.0)
        assert np.all(landmarks_per_frame[1] == 0.0)
        # Both frames were still handed to MediaPipe after resize
        assert len(_mp_image_call_shapes) == 2
        assert _mp_image_call_shapes[0] == (720, 1280, 3)
        assert _mp_image_call_shapes[1] == (720, 1280, 3)
```

- [ ] **Step 3: Run the new test class and confirm it fails**

```bash
cd backend && uv run pytest tests/unit/test_pose_extraction.py::TestFrameDownsampling -x -v
```

Expected: tests fail because no resize is happening yet — `_mp_image_call_shapes[0]` will be `(1080, 1920, 3)` (source, unresized) instead of `(720, 1280, 3)`.

- [ ] **Step 4: Implement frame downsampling in `extract_landmarks`**

In `backend/app/cv/pose_extraction.py`, locate the read loop inside `extract_landmarks` (around line 151-159 of the current file):

Old:
```python
    with PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = landmarker.detect(mp_image)
```

New:
```python
    target_w, target_h = _pose_frame_dimensions(width, height)
    needs_resize = (target_w != width) or (target_h != height)

    with PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if needs_resize:
                # MediaPipe landmarks are normalized [0, 1], so downsampling
                # here is invisible to downstream consumers. See D-035.
                frame = cv2.resize(frame, (target_w, target_h))

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = landmarker.detect(mp_image)
```

The `(target_w, target_h)` tuple passed to `cv2.resize` matches OpenCV's `(dsize_x, dsize_y)` argument order — width first, then height. The returned array then has shape `(target_h, target_w, 3)` which is what `_mp_image_call_shapes` records.

- [ ] **Step 5: Re-run the new test class and confirm all tests pass**

```bash
cd backend && uv run pytest tests/unit/test_pose_extraction.py::TestFrameDownsampling -x -v
```

Expected: 7 tests PASS.

- [ ] **Step 6: Run the full `test_pose_extraction.py` suite to confirm no regressions**

```bash
cd backend && uv run pytest tests/unit/test_pose_extraction.py -x -v
```

Expected: all existing test classes still pass (`TestExtractLandmarksShape`, `TestSigmoidGuard`, `TestNoLandmarksDetected`, `TestMediaPipeConfig`, `TestLandmarkColumnOrdering`, `TestVideoCapRelease`, `TestModelPathResolution`) — plus the two new classes from Tasks 1 and 2. Roughly 20+ tests PASS, 0 FAIL.

- [ ] **Step 7: Run the full backend test suite**

```bash
cd backend && uv run pytest tests/ -x -q --tb=short 2>&1 | tail -10
```

Expected: `1533 passed, 25 skipped` (+13 new tests vs baseline of 1520: 7 in `TestPoseFrameDimensions` + 7 in `TestFrameDownsampling` minus 1 if any count overlap — accept any `1532-1534 passed` range). If any existing tests fail, STOP and investigate before proceeding.

- [ ] **Step 8: Commit**

```bash
git add backend/app/cv/pose_extraction.py backend/tests/unit/test_pose_extraction.py
git commit -m "fix(cv): downscale pose frames to 1280 long side before MediaPipe (D-035)"
```

---

## Task 3: Update module docstring to reference D-035

**Files:**
- Modify: `backend/app/cv/pose_extraction.py` (module docstring, lines 1-19)

- [ ] **Step 1: Append a sentence to the module docstring**

In `backend/app/cv/pose_extraction.py`, locate the closing `"""` of the module docstring (around line 19, after the MediaPipe gotcha line).

Old (the closing block):
```python
MediaPipe gotcha: visibility/presence may be pre-sigmoid logits (outside
``[0, 1]``). Always guard with sigmoid before storing. See GitHub #4411, #4462.
"""
```

New:
```python
MediaPipe gotcha: visibility/presence may be pre-sigmoid logits (outside
``[0, 1]``). Always guard with sigmoid before storing. See GitHub #4411, #4462.

Performance note: frames larger than ``_MAX_POSE_DIM`` on the long side are
``cv2.resize``-downscaled per-frame before inference — BlazePose Heavy is
CPU-linear in pixel count and a 900 s task budget cannot absorb 1080p on the
2-vCPU droplet. Landmarks are returned in normalized ``[0, 1]`` coords so
downstream pixel-space consumers multiply by the original width/height as
before. See D-035 and ADR-057.
"""
```

- [ ] **Step 2: Confirm no test regressions (docstring-only change, but verify)**

```bash
cd backend && uv run pytest tests/unit/test_pose_extraction.py -x -q --tb=short
```

Expected: same pass count as Task 2 Step 6.

- [ ] **Step 3: Commit**

```bash
git add backend/app/cv/pose_extraction.py
git commit -m "docs(cv): note 720p pose cap in module docstring (D-035)"
```

---

## Task 4: Open the PR and wait for CI

**Files:** none

- [ ] **Step 1: Push branch to origin**

```bash
git push -u origin fix/pose-extraction-720p-cap
```

- [ ] **Step 2: Open PR via `mcp__github__create_pull_request`**

Call `mcp__github__create_pull_request` with:
- Base: `main`
- Head: `fix/pose-extraction-720p-cap`
- Title: `fix(cv): cap pose extraction frames at 1280 long side (D-035)`
- Body (pass this verbatim):

```markdown
## Summary

- Adds `_MAX_POSE_DIM = 1280` and `_pose_frame_dimensions(src_w, src_h)` helper to `backend/app/cv/pose_extraction.py`, mirroring the existing `_MAX_ANNOTATION_DIM = 1280` cap in `artifact_generation.py`.
- `extract_landmarks` now `cv2.resize`-downscales each frame before MediaPipe inference when the source exceeds the cap.
- Source `(width, height)` are still returned unchanged so downstream consumers (`compute_bar_path`, `check_minimum_resolution`, quality-gate pixel math) keep operating on source dimensions.
- 14 new unit tests — pure-function coverage of the dimensions helper + end-to-end coverage of the resize behavior via `mp.Image` shape capture.

## Why

D-035 surfaced 2026-04-16 during the full-clip E2E verification of PR #59 (streaming barbell tracking). With the OOM fixed by PR #57 + PR #59, the 22.8 s / 1080p@59fps / 1352-frame `atharva-bench-no-weight.mov` no longer dies — but it cleanly times out at the 900 s `process_analysis` task budget. Worker RSS rock-steady at ~640 MB, no SIGKILL, just CPU pinned at 180–196% while BlazePose Heavy churns through 1080p frames at ~150–180 ms each. That's ~225 s of pose extraction alone before gates, rep detection, or coaching run.

Downsampling to 720p (1280 long side) cuts BlazePose cost to ~70–90 ms/frame — roughly half, matching the 2.25× pixel-area ratio. Projected pose-extraction cost on the failing clip: ~225 s → ~95 s, freeing ~130 s of the 900 s budget.

720p is the empirically validated sweet spot: `atharva-bench-nw-10s-720p.mp4` already produced `form_score_overall = 7.27` with 10/10 deterministic agent nodes in PR #57 verification, and sports-CV literature treats 720p as the safe minimum for clinical-grade full-body angle estimation. Same constant value as the annotation cap → one mental model, one ADR reference.

## Test plan

- [x] 7 new unit tests for `_pose_frame_dimensions` (landscape/portrait/cap-exact/sub-cap/odd-dim/square)
- [x] 7 new unit tests for `extract_landmarks` end-to-end resize behavior (via `mp.Image(data=…)` shape capture — no cv2.resize mocking required)
- [x] Full backend suite still green (`1533 passed, 25 skipped` expected)
- [ ] Prod verification: upload full `atharva-bench-no-weight.mov` (37 MB, 1080×1920, 22.8 s, 59 fps) — should run to `completed` inside the 900 s task budget, not time out

Closes: D-035
Related: ADR-057 (fix path (a)), PR #57 (annotation cap), PR #59 (streaming barbell tracking)
```

- [ ] **Step 3: Wait for CI to go green**

Poll CI via `mcp__github__get_pull_request_status` until all checks pass. Expected checks: backend pytest, backend ruff, backend pyright (if configured), frontend checks (no-op for this branch), `Deploy to Production` (runs on merge).

If CI fails, read logs, fix the underlying issue, push a new commit. Do NOT skip hooks or force-merge.

- [ ] **Step 4: Merge via `mcp__github__merge_pull_request`**

Call `mcp__github__merge_pull_request` with `merge_method: "merge"` (NEVER `"squash"` — violates the no-squash feedback memory). Let the merge commit be auto-generated.

- [ ] **Step 5: Pull main locally**

```bash
git checkout main && git pull
```

- [ ] **Step 6: Wait for the "Deploy to Production" CI step to complete**

Check via `mcp__github__get_pull_request_status` — the merged PR page will include the production deploy status. Wait until it shows green. Do NOT SSH in and manually rebuild — per the `no manual deploy` feedback memory, CI handles frontend (Vercel) and backend (droplet Docker rebuild) automatically.

- [ ] **Step 7: Verify the droplet is running the merge commit**

```bash
ssh spelix-droplet "cd /home/deploy/spelix && git log --oneline -1 && docker ps --format '{{.Names}} {{.Status}}'"
```

Expected: HEAD matches the merge commit SHA from Step 4. All containers show `(healthy)`.

---

## Task 5: Prod verification with the full 22.8 s 1080p clip via Playwright MCP

This is the same verification shape as PR #59, targeting the clip that actually surfaced D-035.

**Files:** none (uses local fixture at `e2e/fixtures/atharva-bench-no-weight.mov`)

- [ ] **Step 1: Open the prod upload page**

Call `mcp__playwright__browser_navigate` to `https://spelix.app/upload`. The browse daemon should authenticate via persistent cookies — if the page redirects to the login flow, STOP and report; do not attempt to log in programmatically.

- [ ] **Step 2: Snapshot the page and verify form is ready**

Call `mcp__playwright__browser_snapshot`. Confirm the accessibility tree shows the exercise-type selector, variant selector, and file input.

- [ ] **Step 3: Select exercise type**

Click Bench Press, then Flat variant. Use `mcp__playwright__browser_click` on the relevant buttons surfaced in the snapshot.

- [ ] **Step 4: Attach the full clip via `browser_file_upload`**

Call `mcp__playwright__browser_file_upload` with absolute path:
```
C:/Users/athar/projects/spelix/e2e/fixtures/atharva-bench-no-weight.mov
```

- [ ] **Step 5: Submit the upload**

Click "Upload Video". Let the TUS upload run to completion. Once the page redirects to `/analysis/<id>`, capture the analysis ID from the URL for the droplet-side watch in Step 6.

- [ ] **Step 6: Watch worker RSS + CPU in a background SSH session**

From a local terminal (or a second Claude Code tool call in the background):

```bash
ssh spelix-droplet "while true; do date -u; docker stats --no-stream --format '{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' | grep worker; sleep 15; done"
```

Expected shape:
- `spelix-worker` CPU peaks 180–196% during MediaPipe phase (same saturation as before — we haven't added vCPUs, just reduced per-frame cost).
- `spelix-worker` RSS rock-steady at ~600–650 MB (unchanged from PR #59 — we're not touching memory).
- The MediaPipe phase completes in ~90–120 s instead of the previous ~225 s+.

Stop the loop with Ctrl+C once the analysis reaches `completed` status.

- [ ] **Step 7: Wait for the analysis to reach `completed`**

Call `mcp__playwright__browser_navigate` to `https://spelix.app/analysis/<id>` and let it poll. Alternatively, use `mcp__supabase__execute_sql` (read-only):

```sql
SELECT id, status, updated_at
FROM analyses
WHERE id = '<analysis-id-from-step-5>';
```

Expected final status: `completed`, within ~10 min total elapsed. Expected intermediate path: `queued → quality_gate_pending → processing → coaching → completed`. If status stays at `processing` past 15 min, STOP and report — either D-035 isn't fully fixed or we've surfaced a new bottleneck.

- [ ] **Step 8: Verify results page renders**

Navigate to `https://spelix.app/results/<id>`. Snapshot the page and confirm:
- Form Assessment panel (4 dimensions + overall)
- Annotated video player with signed URL
- Coaching feedback block (structured output)
- Rep Metrics table (at least 1 rep)
- Angle Plot
- Downloads section
- 3-tier disclaimer

- [ ] **Step 9: Check console and network for errors**

- Call `mcp__playwright__browser_console_messages` with level filter `error`. Expected: 0 errors. The "Connection lost — reconnecting…" banner from D-028 may still appear — that's pre-existing and not part of D-035.
- Call `mcp__playwright__browser_network_requests` and filter for 4xx/5xx responses. Expected: none related to the analysis.

- [ ] **Step 10: Verify the coaching_results trace**

Via `mcp__supabase__execute_sql` (read-only):

```sql
SELECT
  cr.analysis_id,
  cr.agent_trace_json -> 'mode' AS mode,
  jsonb_array_length(cr.agent_trace_json -> 'nodes_executed') AS nodes_executed_count,
  a.form_score_overall
FROM coaching_results cr
JOIN analyses a ON a.id = cr.analysis_id
WHERE cr.analysis_id = '<analysis-id>';
```

Expected: `mode = "deterministic"`, `nodes_executed_count = 10`, `form_score_overall` between 4.0 and 9.0 (sane range for a clean bench rep).

- [ ] **Step 11: Record findings in a scratch note**

If all checks green, note the analysis ID and headline numbers (total elapsed, pose-extraction phase duration, final form score) for the Task 6 handoff. If anything is red, write an "E2E Findings" section to `.claude/handoff.md` and STOP before proceeding to close-out tasks.

---

## Task 6: Close D-035 in `backlog.md` and add ADR-058 to `decisions.md`

**Files:**
- Modify: `backlog.md` (D-035 row)
- Modify: `decisions.md` (append ADR-058)

- [ ] **Step 1: Flip D-035 from `pending` → `done`**

In `backlog.md`, find the D-035 row (currently the last deferred/pending row ending `| pending |`). Change the status column to `done` and append the merge SHA + verification note to the notes column.

Old (from current `backlog.md:368`):
```markdown
| D-035 | **Pose extraction too slow for full 1080p@59fps within 900s task timeout on 2-vCPU droplet.** Surfaced by D-034 verification on 2026-04-16: … Preferred: (a) — matches the annotation 720p cap already in place. 720p pipeline fully works end-to-end per 2026-04-16 verification. | M | — | NFR-OPER-02 | pending |
```

New (append to the final cell — keep the original body intact so the audit trail is preserved, just update status and append the close-out note):
```markdown
| D-035 | **Pose extraction too slow for full 1080p@59fps within 900s task timeout on 2-vCPU droplet.** Surfaced by D-034 verification on 2026-04-16: … Preferred: (a) — matches the annotation 720p cap already in place. 720p pipeline fully works end-to-end per 2026-04-16 verification. | M | — | NFR-OPER-02 | done | `<merge-sha-from-task-4-step-4>` (PR #??  — `_MAX_POSE_DIM = 1280` + per-frame `cv2.resize` in `extract_landmarks`). E2E verified 2026-04-16: full 22.8s 1080p bench clip completed inside the 900s budget. MediaPipe phase ~<measured>s (down from ~225s pre-fix). Worker RSS ~640 MB, CPU 180–196%. See ADR-058. |
```

Replace `<merge-sha-from-task-4-step-4>`, `PR #??`, and `<measured>` with the real values recorded during verification.

- [ ] **Step 2: Append ADR-058 to `decisions.md`**

At the end of `decisions.md` (after ADR-057), append:

```markdown

## ADR-058: 720p cap on pose-extraction frames closes the 900s task-timeout bottleneck (Session 35)
**Context**: After ADR-057 eliminated the 8.4 GB virtual peak in barbell tracking by streaming, the full 22.8 s / 1080p@59fps / 1352-frame `atharva-bench-no-weight.mov` E2E test no longer died with SIGKILL — but it cleanly hit the 900 s `process_analysis` task timeout with worker RSS rock-steady at ~640 MB and CPU pinned at 180–196%. Root cause: MediaPipe BlazePose Heavy runtime scales roughly linearly with input pixel count; at ~150–180 ms per 1080p frame on 2 vCPUs, 1352 frames consume ~225 s of the 900 s budget before gates, rep detection, or Anthropic coaching run. ADR-057 listed three fix paths — (a) 720p cap on pose input, (b) switch to BlazePose Lite, (c) raise the timeout further. Sports-CV literature and the codebase's own `atharva-bench-nw-10s-720p.mp4` end-to-end run treat 720p as the safe floor for clinical-grade full-body angle estimation, so (a) gives the biggest per-frame speedup with the smallest semantic change.
**Decision**: Add `_MAX_POSE_DIM = 1280` and `_pose_frame_dimensions(src_w, src_h)` helper to `backend/app/cv/pose_extraction.py`, mirroring `_MAX_ANNOTATION_DIM` / `_annotation_dimensions` in `backend/app/cv/artifact_generation.py`. Inside `extract_landmarks`, `cv2.resize` each frame to those dimensions before MediaPipe inference when the source exceeds the cap. Return source `(width, height)` unchanged — MediaPipe landmarks are normalized `[0, 1]` so downstream pixel-space consumers (`compute_bar_path`, `check_minimum_resolution`, quality-gate pixel-jump math) keep working on source dimensions. Never upscale — `scale` is clamped to 1.0, so sub-720p sources pass through untouched and are still rejected by `check_minimum_resolution` if below its floor.
**Consequences**: D-035 closes. 1080p@59fps clips up to ~30–40 s now fit within the 900 s task budget (from measured ~<measured>s pose-extraction phase on the bench clip vs ~225 s pre-fix). No measurable landmark-accuracy regression against the existing 720p reference analysis (`form_score_overall = 7.27`, 10/10 deterministic agent nodes in PR #57). Extended-mode clips (FR-AICP-06 up to 120 s) may still need a second timeout bump or BlazePose Lite — revisit if `SPELIX_EXTENDED_MODE` sees real use. Fix path (b) BlazePose Lite stays shelved: would require a new `.task` file in the Docker image, re-validating every `min_*_confidence` threshold against Lite's different output distribution, and changes answers not just speed. Fix path (c) bare timeout bump stays shelved: degrades UX (≥15 min stream-start delay) without addressing the CPU-linear scaling problem.
```

Replace `<measured>s` with the real pose-extraction phase duration measured in Task 5 Step 6.

- [ ] **Step 3: Commit**

```bash
git checkout -b docs/close-d035
git add backlog.md decisions.md
git commit -m "docs(backlog,decisions): close D-035 via ADR-058 pose extraction 720p cap"
git push -u origin docs/close-d035
```

- [ ] **Step 4: Open a follow-up PR for the docs change and merge it**

Call `mcp__github__create_pull_request`:
- Base: `main`
- Head: `docs/close-d035`
- Title: `docs(backlog,decisions): close D-035 via ADR-058`
- Body: one-line summary — `Closes D-035 per ADR-058. See PR #<merge-sha-from-task-4-step-4-PR-number>.`

Wait for CI, merge with `merge_method: "merge"`, then `git checkout main && git pull`.

---

## Task 7: Session handoff note

**Files:**
- Modify: `.claude/handoff.md` (prepend new session header)

- [ ] **Step 1: Prepend the session handoff entry**

At the top of `.claude/handoff.md`, insert a new section above the existing "Session 33 Handoff" header. Use the same shape as prior handoff entries:

```markdown
# Session 35 Handoff → Session 36: L2 Sprint Day 7 — D-035 closed, full 1080p clips complete end-to-end

**Context refresh:** Session 35 closed D-035 (pose-extraction CPU timeout) by applying fix path (a) from ADR-057 — `_MAX_POSE_DIM = 1280` constant + per-frame `cv2.resize` in `extract_landmarks`. E2E verified on prod with the full 22.8s 1080p@59fps `atharva-bench-no-weight.mov` — the clip that surfaced D-035 in session 34 — running to `completed` inside the 900s task budget. No code changes outside `backend/app/cv/pose_extraction.py` and its unit test file; `decisions.md` gained ADR-058, `backlog.md` flipped D-035 to `done`.

## 1. Completed

### PR #<n> — `fix(cv): cap pose extraction frames at 1280 long side (D-035)`
- Merge commit: `<merge-sha>`
- CI: all checks green including "Deploy to Production"
- Droplet verified: `git log -1` matches, all containers healthy
- New unit tests: 14 (7 for `_pose_frame_dimensions`, 7 for `extract_landmarks` resize behavior via `mp.Image` shape capture)
- Backend test count: 1520 → 1533 passing
- E2E verified 2026-04-16 on `atharva-bench-no-weight.mov`: full clip completed in ~<total>s. Pose-extraction phase: ~<measured>s (down from ~225s pre-fix). Worker RSS ~640 MB steady, CPU 180–196% (CPU-bound confirmed). `form_score_overall = <score>`, 10/10 deterministic agent nodes executed.

### PR #<m> — `docs(backlog,decisions): close D-035 via ADR-058`
- Merge commit: `<docs-merge-sha>`
- Routine close-out: backlog status flip + ADR-058.

## 2. Remaining

### Sprint-blocking
None — both D-034 and D-035 closed. The kin-expert test uploads and Week 4 smoke test are now unblocked as far as pose pipeline is concerned.

### Known deferred (non-blocking) — unchanged from session 34
| ID | Title | Notes |
|---|---|---|
| D-028 | `useAnalysisStatus` "Connection lost" banner + Realtime not delivering `quality_gate_rejected` transitions | Still reproducible on prod |
| D-029 | SaMD rename `injury_advice_accurate` → `movement_advice_accurate` | Pre-existing |
| D-030 | Orphan `rag_documents` uploading-state cleanup | |
| D-031 | Admin GET /rag/documents free-text query param | |

### Phase 3 remaining batches (per STRATEGY.md v3)
| Batch | Items | Status |
|---|---|---|
| Batch 2 — Distillation | P3-004, P3-005, FR-BRAIN-14 | Not started — can pull forward |
| Batch 3 — Review queue + Reasoning sidebar | P3-006, P3-007 | Not started |

### Expert onboarding
- Kin expert onboarding call: still pending.

## 3. Test counts
- **Backend**: 1533 passing, 25 skipped, 0 failing (+13 vs session 34).
- **Frontend**: 266 passing, 0 failing (unchanged).
- **Coverage**: 90% (unchanged — no coverage regression).

## 4. E2E verification
- Analysis `<analysis-id>` completed on `atharva-bench-no-weight.mov` (full 22.8s 1080p@59fps). Deterministic agent trace: 10/10 nodes. Status path: queued → quality_gate_pending → processing → coaching → completed. Worker RSS 600–650 MB throughout, CPU 180–196% during MediaPipe phase. No OOM, no timeout.
- D-028 banner still observed on status page (known).

## 5. Blockers
None for pose pipeline. Extended-mode clips (>30–40s at 1080p) may still need a timeout bump — revisit if `SPELIX_EXTENDED_MODE` sees real use.

## 6. Next session start

```bash
/status
# Confirm environment, live containers, queue depth, CI status

# PRIORITY 1: Pull Phase 3 Batch 2 forward
#   P3-004: Distillation StateGraph (FR-BRAIN-06)
#   P3-005: Knowledge lifecycle (FR-BRAIN-17)
#   FR-BRAIN-14: Review-queue promotion criteria
#   Activate spelix-langgraph-engineer

# PRIORITY 2: Schedule kin expert onboarding call + first paper uploads
```
```

Replace every `<placeholder>` with real values recorded during Task 4 Step 4 and Task 5.

- [ ] **Step 2: Commit the handoff**

```bash
git checkout main && git pull
git checkout -b docs/session-35-handoff
git add .claude/handoff.md
git commit -m "docs(handoff): session 35 — D-035 closed, full 1080p clips complete"
git push -u origin docs/session-35-handoff
```

- [ ] **Step 3: Open + merge the handoff PR**

Call `mcp__github__create_pull_request` with base `main`, head `docs/session-35-handoff`, title `docs(handoff): session 35 — D-035 closed`, body one line referencing PR #<n>. Wait for CI, merge with `merge_method: "merge"`.

- [ ] **Step 4: Pull main**

```bash
git checkout main && git pull
```

---

## Self-Review Notes (author's checklist — remove before PR)

- [x] **Spec coverage:** D-035 backlog row lists three fix paths ((a) 720p cap, (b) BlazePose Lite, (c) timeout raise) and names (a) as preferred. Plan implements (a) and explicitly shelves (b) and (c) in ADR-058. ✔
- [x] **Placeholder scan:** `<merge-sha>`, `<n>`, `<measured>s`, `<analysis-id>`, `<score>`, `<total>` are all runtime values captured during execution — each one is explicitly called out at the step where it gets captured. No ambiguous "TODO" or "TBD". ✔
- [x] **Type consistency:** `_MAX_POSE_DIM: int = 1280`, `_pose_frame_dimensions(src_width: int, src_height: int) -> tuple[int, int]` — types match between constants block, helper signature, and both test suites. `_mp_image_call_shapes: list[tuple[int, ...]]` — shape tuples from `cv2.cvtColor` output are `(h, w, 3)` consistently across all test assertions. ✔
- [x] **Scope:** single-file code change + single-file test change + two doc files. No surrounding refactor, no new pipeline stages, no frontend touches, no migrations. ✔
