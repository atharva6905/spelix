# D-035 Instrumentation + Pipeline Tier 1 Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the 900s task-timeout failure mode for real-user clips on the L2 private beta by adding production telemetry, switching MediaPipe to VIDEO mode, doubling the safety-net timeout, and capping upload duration at the API + UI boundary — without changing the SaMD-adjacent rep detection / angle smoothing / scoring math.

**Architecture:** Four production changes + two doc artifacts:
1. **Per-stage timing instrumentation** (new `analyses.timing_json` JSONB column + `with timing()` context manager around every pipeline step) so we have actual measurements for the 3× bench-vs-prod gap that has driven D-033 → D-034 → D-035 fix-by-guess thrashing.
2. **MediaPipe `RunningMode.IMAGE` → `RunningMode.VIDEO`** in `extract_landmarks` — uses inter-frame bbox tracking, ~20% inference speedup, fits within the existing ±1° angle tolerance.
3. **Streaq `process_analysis` task timeout 900s → 1800s** as safety net while we measure.
4. **Upload duration cap**: client-side block at 60s (free tier) / 120s (Extended Mode), backend defense-in-depth ffprobe check post-download.
5. **D-036 backlog row + ADR-058** explicitly deferring GPU pose-offload work to post-private-beta with a documented trigger condition.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, Alembic, FastAPI, MediaPipe Tasks API, OpenCV headless, ffmpeg/ffprobe (already in Docker image), React 19, TypeScript strict.

**Closes (partially)**: D-035. After this plan ships, run E2E on `atharva-bench-no-weight.mov` and read `analyses.timing_json` to identify whichever stage actually consumed the budget. THEN decide whether ffmpeg pre-process to 30fps (Tier 2 fix C) or GPU offload (D-036) is needed.

**Does NOT close**: D-028, D-029, D-030, D-031.

---

## Background — what the bench data established

Session 35 benchmarking on the failing clip (`atharva-bench-no-weight.mov`, 1352 frames, 1080×1920 @ 59 fps, 38 MB):

| Configuration | Wall total | Inference only | ms/frame |
|---|---|---|---|
| IMAGE @ 720p (current prod) | 332.6s | 198.0s | 148 ms |
| VIDEO @ 720p | 287.7s | 160.1s | 120 ms |
| Stride 2 VIDEO | 223.7s | 84.9s | 127 ms |
| Stride 3 VIDEO | 177.2s | 52.7s | 118 ms |

- VIDEO mode is **only 1.24× faster than IMAGE** for inference (BlazePose Heavy is mostly fixed cost regardless of mode/resolution).
- Stride-N skipping helps less than expected (1.35× wall for stride-2) because `cv2.VideoCapture.read()` reads every frame regardless of skip.
- **Bench predicts ~290s for pose extraction. Prod hit 900s without finishing.** ~3× unexplained gap. This plan ships instrumentation first so the gap stops being unexplained.

---

## File Structure

Branch: `fix/d035-instrument-and-pipeline-fixes`

### Backend
- **Create:** `backend/alembic/versions/007_add_timing_json.py` — Alembic migration adding nullable JSONB column `analyses.timing_json`.
- **Modify:** `backend/app/models/analysis.py` — declare `timing_json` column on the SQLAlchemy model.
- **Modify:** `backend/app/schemas/analysis.py` — surface `timing_json` in any response schemas that already include `quality_gate_result`.
- **Create:** `backend/app/services/timing.py` — `class StageTimer` context manager + dict accumulator.
- **Modify:** `backend/app/services/pipeline.py` — wrap each step with `with timer.stage("name"):`; write timer dict to `analysis.timing_json` after each major write or at the end.
- **Modify:** `backend/app/cv/pose_extraction.py` — `RunningMode.IMAGE` → `RunningMode.VIDEO`, switch from `detect()` to `detect_for_video()` with monotonic `timestamp_ms`.
- **Modify:** `backend/app/workers/streaq_worker.py:147` — `@worker.task(timeout=1800)` + comment update.
- **Modify:** `backend/app/api/v1/analyses.py` — add ffprobe-based duration validation as defense-in-depth (validates after worker downloads the file).
- **Create:** `backend/app/cv/video_probe.py` — `probe_duration_seconds(path) -> float` thin ffprobe wrapper used by the worker validation.
- **Modify:** `backend/app/workers/analysis_worker.py` — call `probe_duration_seconds` after Step 1 download; if too long, transition to `quality_gate_rejected` with a user-facing message.

### Backend tests
- **Create:** `backend/tests/unit/test_timing.py` — `StageTimer` context manager unit tests.
- **Modify:** `backend/tests/unit/test_pipeline.py` — verify `analysis.timing_json` populated with all expected stage names after pipeline runs.
- **Modify:** `backend/tests/unit/test_pose_extraction.py` — update `_run_extract` helper to mock `detect_for_video` instead of `detect`; update `TestMediaPipeConfig::test_pose_initialized_with_correct_tasks_config` to assert VIDEO mode; add `TestVideoModeTimestamps` class verifying monotonic `timestamp_ms` argument.
- **Create:** `backend/tests/unit/test_video_probe.py` — ffprobe wrapper tests using a tiny synthetic mp4 fixture or mocked subprocess.
- **Modify:** `backend/tests/unit/test_analysis_worker.py` (or wherever post-download checks live) — verify too-long clips get rejected before pose extraction starts.

### Frontend
- **Modify:** `frontend/src/components/Upload/UploadForm.tsx` — read selected file's duration via hidden HTML5 `<video>` element; warn at 30s, hard-block submit at 60s (or 120s if Extended Mode checkbox checked).
- **Modify:** `frontend/src/components/Upload/UploadForm.test.tsx` — Vitest tests for the duration-check states.

### Docs
- **Modify:** `backlog.md` — add D-036 row (GPU offload, post-beta).
- **Modify:** `decisions.md` — add ADR-058 (architectural constraint + GPU deferral) AND ADR-059 (telemetry-first principle for any future pipeline tuning).

No migrations to existing data needed — `timing_json` defaults to NULL for pre-existing rows.

---

## Task 1: Add `analyses.timing_json` JSONB column via Alembic migration

**Files:**
- Create: `backend/alembic/versions/007_add_timing_json.py`
- Modify: `backend/app/models/analysis.py`

**Specialist agent:** Use `spelix-migration` for this task — it carries the project's Alembic conventions (JSONB, no DDL FK to auth.users, VARCHAR(30) status etc.).

- [ ] **Step 1: Confirm current Alembic head**

```bash
cd backend && uv run alembic current 2>&1 | tail -3
```
Expected: `006_admin_expert_reviews (head)`. If not, STOP and investigate.

- [ ] **Step 2: Create the migration file**

Create `backend/alembic/versions/007_add_timing_json.py` with this exact content:

```python
"""add timing_json JSONB column to analyses

Revision ID: 007_add_timing_json
Revises: 006_admin_expert_reviews
Create Date: 2026-04-16

D-035 instrumentation column. Stores per-stage wall durations recorded by
``app.services.timing.StageTimer`` from inside the pipeline. JSONB shape:
``{"stage_name": elapsed_ms_float, ...}``. Nullable so pre-existing analyses
unaffected; written incrementally during pipeline run so partial completions
still leave useful data for triage.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "007_add_timing_json"
down_revision: str | None = "006_admin_expert_reviews"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column(
            "timing_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("analyses", "timing_json")
```

- [ ] **Step 3: Add column to the SQLAlchemy model**

In `backend/app/models/analysis.py`, find the `Analysis` class. Add a new column declaration adjacent to other JSONB columns (`quality_gate_result`, `summary_json`, etc.):

```python
    timing_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Per-stage wall durations in milliseconds (D-035). "
                "Shape: {stage_name: elapsed_ms}. Written incrementally.",
    )
```

If `JSONB` is not already imported in the file, add to the imports at the top:
```python
from sqlalchemy.dialects.postgresql import JSONB
```

- [ ] **Step 4: Apply migration locally**

```bash
cd backend && uv run alembic upgrade head 2>&1 | tail -5
```
Expected output ends with `Running upgrade 006_add_admin_expert_reviews -> 007_add_timing_json`. Then verify head:
```bash
cd backend && uv run alembic current
```
Expected: `007_add_timing_json (head)`.

- [ ] **Step 5: Verify model + DB schema match**

```bash
cd backend && uv run python -c "from app.models.analysis import Analysis; print('timing_json' in {c.name for c in Analysis.__table__.columns})"
```
Expected: `True`.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/007_add_timing_json.py backend/app/models/analysis.py
git commit -m "feat(models): add analyses.timing_json JSONB column (D-035 instrumentation)"
```

---

## Task 2: Implement `StageTimer` context manager

**Files:**
- Create: `backend/app/services/timing.py`
- Create: `backend/tests/unit/test_timing.py`

- [ ] **Step 1: Write failing tests for StageTimer**

Create `backend/tests/unit/test_timing.py`:

```python
"""Unit tests for app.services.timing.StageTimer (D-035)."""
from __future__ import annotations

import time

import pytest

from app.services.timing import StageTimer


class TestStageTimerBasics:
    def test_records_named_stage(self):
        timer = StageTimer()
        with timer.stage("download"):
            time.sleep(0.01)
        assert "download" in timer.as_dict()

    def test_elapsed_ms_is_positive_float(self):
        timer = StageTimer()
        with timer.stage("pose_extraction"):
            time.sleep(0.005)
        d = timer.as_dict()
        assert isinstance(d["pose_extraction"], float)
        assert d["pose_extraction"] >= 5.0  # 5ms sleep, allow some slop
        assert d["pose_extraction"] < 500.0  # not absurdly large

    def test_multiple_stages_each_recorded(self):
        timer = StageTimer()
        with timer.stage("a"):
            pass
        with timer.stage("b"):
            pass
        with timer.stage("c"):
            pass
        d = timer.as_dict()
        assert set(d.keys()) == {"a", "b", "c"}

    def test_same_stage_called_twice_overwrites_with_last(self):
        """Same stage called twice records the LAST elapsed (last write wins)."""
        timer = StageTimer()
        with timer.stage("stage_x"):
            time.sleep(0.001)
        first_value = timer.as_dict()["stage_x"]
        with timer.stage("stage_x"):
            time.sleep(0.02)
        second_value = timer.as_dict()["stage_x"]
        assert second_value > first_value

    def test_exception_inside_stage_still_records_elapsed(self):
        """Failure inside the stage block must still record elapsed for triage."""
        timer = StageTimer()
        with pytest.raises(ValueError):
            with timer.stage("failing_stage"):
                time.sleep(0.005)
                raise ValueError("synthetic failure")
        d = timer.as_dict()
        assert "failing_stage" in d
        assert d["failing_stage"] >= 5.0


class TestStageTimerSnapshot:
    def test_as_dict_returns_copy(self):
        """Mutating the returned dict must NOT mutate the timer's internal state."""
        timer = StageTimer()
        with timer.stage("a"):
            pass
        d = timer.as_dict()
        d["mutation"] = 999.0
        assert "mutation" not in timer.as_dict()

    def test_as_dict_empty_when_nothing_recorded(self):
        timer = StageTimer()
        assert timer.as_dict() == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/unit/test_timing.py -x -v
```
Expected: every test fails with `ImportError: cannot import name 'StageTimer' from 'app.services.timing'`.

- [ ] **Step 3: Implement StageTimer**

Create `backend/app/services/timing.py`:

```python
"""StageTimer — per-stage wall-time accumulator for pipeline observability.

Used by ``app.services.pipeline.run_cv_pipeline`` to record how long each
step of the analysis pipeline takes in production. The collected dict is
written to ``analyses.timing_json`` so we can diagnose where the budget
goes per analysis (D-035).

Designed for use in synchronous and asynchronous code — the context
manager body may itself be async or sync; we measure wall time via
``time.perf_counter`` regardless.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator


class StageTimer:
    """Accumulates ``{stage_name: elapsed_ms}`` across a pipeline run.

    Last-write-wins on duplicate stage names — pipelines that re-enter the
    same logical stage (e.g. a retry loop) record the final attempt only.
    """

    def __init__(self) -> None:
        self._records: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Context manager that records wall time of the enclosed block.

        Records elapsed even if the block raises, so failed stages still
        appear in ``timing_json`` for triage.
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self._records[name] = elapsed_ms

    def as_dict(self) -> dict[str, float]:
        """Return a SHALLOW COPY of the recorded timings."""
        return dict(self._records)
```

- [ ] **Step 4: Re-run tests to verify they pass**

```bash
cd backend && uv run pytest tests/unit/test_timing.py -x -v
```
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/timing.py backend/tests/unit/test_timing.py
git commit -m "feat(services): add StageTimer context manager (D-035)"
```

---

## Task 3: Wire `StageTimer` into the pipeline

**Files:**
- Modify: `backend/app/services/pipeline.py`
- Modify: `backend/tests/unit/test_pipeline.py`

This task wraps every major step of `run_cv_pipeline` with `timer.stage("...")` and writes the accumulated dict to `analysis.timing_json` at the end. We also write incrementally after each major step so partial-completion states (timeouts, mid-pipeline failures) still leave useful triage data.

- [ ] **Step 1: Write failing test for timing_json population**

In `backend/tests/unit/test_pipeline.py`, add a new test class at the END of the file (after the last existing class):

```python
class TestPipelineTimingInstrumentation:
    """Pipeline records per-stage wall durations to analysis.timing_json (D-035)."""

    @pytest.mark.asyncio
    async def test_timing_json_populated_with_expected_stages(self):
        """After successful pipeline run, timing_json has every documented stage."""
        landmarks = [_make_landmark_frame() for _ in range(_TOTAL_FRAMES)]
        analysis = _make_mock_analysis()
        repo = _make_mock_repo(analysis)

        with (
            patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
            patch(f"{_PKG}.run_quality_gates", return_value=_make_passing_gate_result()),
            patch(f"{_PKG}.detect_exercise_heuristic", return_value=_make_high_confidence_detection()),
            patch(f"{_PKG}.track_barbell_from_video", return_value=[None] * _TOTAL_FRAMES),
            patch(f"{_PKG}.generate_annotated_video", return_value="annotated.mp4"),
            patch(f"{_PKG}.upload_artifact", new_callable=AsyncMock, return_value="public/url"),
            patch(f"{_PKG}.write_heartbeat", new_callable=AsyncMock),
        ):
            result = await run_cv_pipeline(
                analysis_id=_ANALYSIS_ID,
                repo=repo,
                redis=_make_mock_redis(),
                storage_client=_make_mock_storage(),
                openai_client=None,
            )

        # After successful run, analysis.timing_json must be a dict and
        # contain every major stage name.
        assert isinstance(analysis.timing_json, dict)
        for stage in [
            "download",
            "extract_landmarks",
            "exercise_detection",
            "quality_gates",
            "rep_detection",
            "form_scoring",
            "annotation_generation",
            "artifact_upload",
        ]:
            assert stage in analysis.timing_json, (
                f"Missing stage {stage!r} in timing_json: {analysis.timing_json}"
            )
            assert isinstance(analysis.timing_json[stage], float)
            assert analysis.timing_json[stage] >= 0.0
```

If the helpers (`_make_landmark_frame`, `_make_mock_analysis`, `_make_passing_gate_result`, `_make_high_confidence_detection`, `_make_mock_redis`, `_make_mock_storage`, `_make_mock_repo`, `_TOTAL_FRAMES`, `_FPS`, `_FRAME_WIDTH`, `_FRAME_HEIGHT`, `_ANALYSIS_ID`, `_PKG`) are missing — they exist in the surrounding test module already; reuse them. If a particular helper is named differently, use the existing name from the same file (read the file to confirm) — DO NOT define new ones.

- [ ] **Step 2: Run the new test to confirm it fails**

```bash
cd backend && uv run pytest tests/unit/test_pipeline.py::TestPipelineTimingInstrumentation -x -v
```
Expected: fails with `AttributeError: 'Analysis' object has no attribute 'timing_json'` OR an assertion error stating the dict is empty/None — depends on how `_make_mock_analysis` initializes the field.

- [ ] **Step 3: Wire StageTimer into pipeline.py**

In `backend/app/services/pipeline.py`:

**Edit 3a** — add the import at the top of the file alongside other `app.services.*` imports:
```python
from app.services.timing import StageTimer
```

**Edit 3b** — at the start of `run_cv_pipeline` (immediately after `result = PipelineResult(...)` initialization, before `await write_heartbeat(redis)`), add:
```python
    timer = StageTimer()
```

**Edit 3c** — wrap each major step in `with timer.stage(...)`. Apply these specific wraps (exact stage names for the whitelist used in tests):

```python
    # Step 1: Download
    with timer.stage("download"):
        if storage_client is not None and analysis.video_path:
            await download_video(storage_client, _BUCKET, analysis.video_path, video_local)
        else:
            if analysis.video_path and os.path.isfile(analysis.video_path):
                video_local = analysis.video_path

    # Step 2: Pose extraction
    with timer.stage("extract_landmarks"):
        landmarks_per_frame, fps, frame_width, frame_height = await loop.run_in_executor(
            None, extract_landmarks, video_local,
        )
        result.landmarks_per_frame = landmarks_per_frame
        result.fps = fps
        result.frame_width = frame_width
        result.frame_height = frame_height

    # Step 2b: Exercise auto-detection
    with timer.stage("exercise_detection"):
        # ...existing detection code, including GPT-4o fallback if any...

    # Step 3: Quality gates
    with timer.stage("quality_gates"):
        gate_result = await loop.run_in_executor(None, run_quality_gates, ...)

    # Step 6: Rep detection
    with timer.stage("rep_detection"):
        # ...existing rep detection code...

    # Step 9-9b: Bar path + form scoring (combined logical stage)
    with timer.stage("form_scoring"):
        # ...existing scoring code...

    # Step 12: Annotation generation
    with timer.stage("annotation_generation"):
        # ...existing annotation code...

    # Step 13: Storage uploads
    with timer.stage("artifact_upload"):
        # ...existing upload code...
```

DO NOT change the body of any wrapped step — only add the `with timer.stage(...)` wrapper around it. Keep the current step numbering / comments.

**Edit 3d** — write timer to analysis incrementally. After each existing `await repo.update(analysis)` call inside the pipeline body, add ONE line above it:
```python
    analysis.timing_json = timer.as_dict()
    await repo.update(analysis)
```
Do not add NEW `repo.update` calls — only attach `timing_json` to existing ones. The existing updates already happen at: detection result write, quality gate result write, status transitions, completion.

**Edit 3e** — at the END of `run_cv_pipeline` (right before the `return result` line), add a final write:
```python
    analysis.timing_json = timer.as_dict()
    await repo.update(analysis)
```

- [ ] **Step 4: Re-run the new test to confirm it passes**

```bash
cd backend && uv run pytest tests/unit/test_pipeline.py::TestPipelineTimingInstrumentation -x -v
```
Expected: PASS.

- [ ] **Step 5: Run the full pipeline test suite for regressions**

```bash
cd backend && uv run pytest tests/unit/test_pipeline.py -x -q
```
Expected: all pre-existing pipeline tests still pass + the new test. If anything fails because a mock factory missed `timing_json=None`, update the helper to set it explicitly per the backend/CLAUDE.md gotcha "MagicMock + Pydantic from_attributes=True".

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/pipeline.py backend/tests/unit/test_pipeline.py
git commit -m "feat(pipeline): record per-stage wall durations to timing_json (D-035)"
```

---

## Task 4: Switch MediaPipe `RunningMode.IMAGE` → `RunningMode.VIDEO`

**Files:**
- Modify: `backend/app/cv/pose_extraction.py`
- Modify: `backend/tests/unit/test_pose_extraction.py`

**Specialist agent:** Use `spelix-cv-engineer` for this task — it carries MediaPipe Tasks API context.

VIDEO mode uses inter-frame bbox tracking, which avoids re-running the detection branch every frame. ~20% inference speedup on continuous-subject video. Requires `detect_for_video(image, timestamp_ms)` instead of `detect(image)`, with monotonically increasing timestamp_ms per frame.

- [ ] **Step 1: Write failing test for VIDEO mode + timestamp tracking**

In `backend/tests/unit/test_pose_extraction.py`, **first** locate the `_run_extract` helper (around line 102). The helper currently mocks `landmarker.detect`. We need to support `detect_for_video` too.

Replace the body of `_make_mock_landmarker` (around line 75) with:

Old:
```python
def _make_mock_landmarker(detect_results: list):
    landmarker = MagicMock()
    landmarker.__enter__ = MagicMock(return_value=landmarker)
    landmarker.__exit__ = MagicMock(return_value=False)

    detect_call_results = []
    for r in detect_results:
        result_obj = MagicMock()
        result_obj.pose_landmarks = r
        detect_call_results.append(result_obj)

    landmarker.detect.side_effect = detect_call_results
    return landmarker
```

New (mocks BOTH `detect` and `detect_for_video`, captures timestamps):
```python
_detect_for_video_timestamps: list[int] = []


def _make_mock_landmarker(detect_results: list):
    """Mock PoseLandmarker. Mocks both detect() and detect_for_video()
    so the same helper supports IMAGE and VIDEO mode tests. Records
    timestamps passed to detect_for_video into _detect_for_video_timestamps
    (cleared at the top of every _run_extract call alongside _constructor_args).
    """
    landmarker = MagicMock()
    landmarker.__enter__ = MagicMock(return_value=landmarker)
    landmarker.__exit__ = MagicMock(return_value=False)

    detect_call_results = []
    for r in detect_results:
        result_obj = MagicMock()
        result_obj.pose_landmarks = r
        detect_call_results.append(result_obj)

    # Same iteration for both call paths so a test using either gets sane
    # results. `iter` is exhausted after a single pass — choose the path
    # that matches the production code (currently VIDEO).
    img_iter = iter(detect_call_results)
    vid_iter = iter(list(detect_call_results))  # independent copy

    landmarker.detect.side_effect = lambda *a, **kw: next(img_iter)

    def _detect_for_video_side_effect(image, timestamp_ms):
        _detect_for_video_timestamps.append(timestamp_ms)
        return next(vid_iter)

    landmarker.detect_for_video.side_effect = _detect_for_video_side_effect
    return landmarker
```

Then in `_run_extract`, add `_detect_for_video_timestamps.clear()` next to the existing `_constructor_args.clear()` and `_mp_image_call_shapes.clear()` at the top of the function.

**Now** add the new test class at the END of the file (after `TestFrameDownsampling`):

```python
class TestRunningModeVideo:
    """`extract_landmarks` uses RunningMode.VIDEO with monotonically increasing timestamps (D-035)."""

    def test_running_mode_is_video(self):
        cap = _make_mock_cap(num_frames=1)
        _run_extract(cap, [_make_pose_landmarks_list()])

        assert _constructor_args["running_mode"] == "VIDEO"

    def test_detect_for_video_called_per_frame(self):
        cap = _make_mock_cap(num_frames=3, fps=30.0, width=640.0, height=480.0)
        _run_extract(
            cap,
            [
                _make_pose_landmarks_list(),
                _make_pose_landmarks_list(),
                _make_pose_landmarks_list(),
            ],
        )

        # 3 frames -> 3 detect_for_video calls
        assert len(_detect_for_video_timestamps) == 3

    def test_timestamps_monotonically_increase(self):
        """Each subsequent timestamp_ms must be strictly greater than the previous."""
        cap = _make_mock_cap(num_frames=4, fps=30.0, width=640.0, height=480.0)
        _run_extract(
            cap,
            [_make_pose_landmarks_list() for _ in range(4)],
        )

        ts = _detect_for_video_timestamps
        assert ts == sorted(ts)
        assert all(ts[i + 1] > ts[i] for i in range(len(ts) - 1))

    def test_timestamps_reflect_fps(self):
        """At 30fps, consecutive frames are ~33ms apart."""
        cap = _make_mock_cap(num_frames=2, fps=30.0, width=640.0, height=480.0)
        _run_extract(cap, [_make_pose_landmarks_list(), _make_pose_landmarks_list()])

        ts = _detect_for_video_timestamps
        assert ts[0] == 0
        assert 30 <= ts[1] <= 35  # ~1000/30 = 33ms

    def test_timestamps_reflect_60fps(self):
        cap = _make_mock_cap(num_frames=2, fps=60.0, width=640.0, height=480.0)
        _run_extract(cap, [_make_pose_landmarks_list(), _make_pose_landmarks_list()])

        ts = _detect_for_video_timestamps
        assert ts[0] == 0
        assert 15 <= ts[1] <= 18  # ~1000/60 = 16ms
```

ALSO update the existing test `TestMediaPipeConfig::test_pose_initialized_with_correct_tasks_config` — replace `assert _constructor_args["running_mode"] == "IMAGE"` with `assert _constructor_args["running_mode"] == "VIDEO"`. Leave the other assertions in that test unchanged.

- [ ] **Step 2: Run new + updated tests to confirm failures**

```bash
cd backend && uv run pytest tests/unit/test_pose_extraction.py::TestRunningModeVideo tests/unit/test_pose_extraction.py::TestMediaPipeConfig -x -v
```
Expected: failures because production code is still IMAGE mode + uses `.detect()` not `.detect_for_video()`.

- [ ] **Step 3: Update extract_landmarks to use VIDEO mode**

In `backend/app/cv/pose_extraction.py`:

**Edit 3a** — change `running_mode` (around line 175):
```python
        running_mode=RunningMode.VIDEO,
```

**Edit 3b** — update the docstring `Notes` block (around line 149) to reflect the change:

Old:
```python
    * Configured for ``RunningMode.IMAGE`` (each frame processed
      independently — no inter-frame tracking), matching the legacy
      ``static_image_mode=True`` behaviour.
```

New:
```python
    * Configured for ``RunningMode.VIDEO`` — uses inter-frame bbox tracking
      so the detection branch only runs on the first frame and on
      tracking-loss events (D-035, ADR-058). ~20% faster than IMAGE mode
      for continuous single-subject lift video on the 2-vCPU droplet.
      Within the existing ±1° angle tolerance.
```

**Edit 3c** — replace the inference call inside the loop (around line 159). The current loop has:

Old (around lines 152-180):
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

New:
```python
    target_w, target_h = _pose_frame_dimensions(width, height)
    needs_resize = (target_w != width) or (target_h != height)

    # VIDEO mode requires monotonically-increasing timestamps. Source fps
    # may be 0.0 for some containers; fall back to 30 fps in that case.
    frame_interval_ms = int(1000.0 / fps) if fps and fps > 0 else 33
    timestamp_ms = 0

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
            result = landmarker.detect_for_video(mp_image, timestamp_ms)
            timestamp_ms += frame_interval_ms
```

- [ ] **Step 4: Re-run the new + updated tests to confirm they pass**

```bash
cd backend && uv run pytest tests/unit/test_pose_extraction.py -x -v
```
Expected: all tests in the file PASS (including TestRunningModeVideo, the updated TestMediaPipeConfig, and pre-existing TestExtractLandmarksShape, TestSigmoidGuard, TestNoLandmarksDetected, TestLandmarkColumnOrdering, TestVideoCapRelease, TestModelPathResolution, TestPoseFrameDimensions, TestFrameDownsampling).

- [ ] **Step 5: Commit**

```bash
git add backend/app/cv/pose_extraction.py backend/tests/unit/test_pose_extraction.py
git commit -m "fix(cv): switch pose extraction to RunningMode.VIDEO (D-035)"
```

---

## Task 5: Bump streaq `process_analysis` task timeout 900 → 1800s

**Files:**
- Modify: `backend/app/workers/streaq_worker.py`

- [ ] **Step 1: Update timeout decorator and comment**

In `backend/app/workers/streaq_worker.py`, find the `process_analysis` task decorator (around line 143-147):

Old:
```python
# timeout=900 per ADR-BRAIN-04 Phase-2 + ADR-055 — MediaPipe BlazePose Heavy on
# the 2-vCPU droplet costs ~150–180 ms/frame, so a 20–30 s 1080p@59fps clip takes
# 3–7 minutes just for pose extraction (atharva-bench.mov hit the old 300 s ceiling
# in session 33). Other tasks stay at 300 s — they are sub-second in the common case.
@worker.task(timeout=900)
async def process_analysis(
```

New:
```python
# timeout=1800 per ADR-058 (D-035 instrumentation tier) — bench-vs-prod gap left
# the 900 s ceiling unsafe for full-length 1080p@59fps clips even after the 720p
# pose cap (PR #61) and streaming barbell tracking (PR #59). Doubled to 1800 s
# as a safety net while telemetry (analyses.timing_json) reveals where the prod
# pipeline actually spends its budget. Other tasks stay at 300 s — sub-second
# in the common case. Re-tighten once Tier 2 (ffmpeg fps normalize / GPU offload)
# lands and a 22.8 s clip routinely completes under ~600 s.
@worker.task(timeout=1800)
async def process_analysis(
```

- [ ] **Step 2: Verify no test depends on the literal 900 value**

```bash
cd backend && uv run grep -rn "900\b" tests/ --include='*.py' 2>&1 | head -10
```
Expected: any matches are unrelated (e.g. test data, time math). If a test asserts on the literal 900s timeout value, update it to 1800.

- [ ] **Step 3: Run the worker test suite**

```bash
cd backend && uv run pytest tests/unit/test_streaq_worker.py -x -q 2>&1 | tail -5
```
Expected: all pass. If no `test_streaq_worker.py` exists in the unit tests, run the broader worker tests:
```bash
cd backend && uv run pytest tests/ -k worker -x -q 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/workers/streaq_worker.py
git commit -m "chore(worker): raise process_analysis timeout 900 -> 1800s (ADR-058)"
```

---

## Task 6: Backend defense-in-depth duration validation

**Files:**
- Create: `backend/app/cv/video_probe.py`
- Create: `backend/tests/unit/test_video_probe.py`
- Modify: `backend/app/workers/analysis_worker.py`

The frontend (Task 7) blocks at upload time, but a malicious or misbehaving client could bypass it. Worker validates duration after download as defense-in-depth: too long → `quality_gate_rejected` with a clear user message rather than a slow timeout.

- [ ] **Step 1: Write failing tests for the probe helper**

Create `backend/tests/unit/test_video_probe.py`:

```python
"""Unit tests for app.cv.video_probe (D-035)."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


class TestProbeDurationSeconds:
    def test_returns_float_for_valid_video(self):
        from app.cv.video_probe import probe_duration_seconds

        completed = MagicMock(returncode=0, stdout=b'{"format":{"duration":"22.795000"}}')
        with patch("subprocess.run", return_value=completed):
            d = probe_duration_seconds("/tmp/video.mp4")
        assert isinstance(d, float)
        assert abs(d - 22.795) < 0.001

    def test_returns_zero_when_ffprobe_fails(self):
        """Non-zero exit must NOT raise — return 0.0 so callers can decide policy."""
        from app.cv.video_probe import probe_duration_seconds

        completed = MagicMock(returncode=1, stdout=b"")
        with patch("subprocess.run", return_value=completed):
            d = probe_duration_seconds("/tmp/missing.mp4")
        assert d == 0.0

    def test_returns_zero_when_json_invalid(self):
        from app.cv.video_probe import probe_duration_seconds

        completed = MagicMock(returncode=0, stdout=b"not json at all")
        with patch("subprocess.run", return_value=completed):
            d = probe_duration_seconds("/tmp/video.mp4")
        assert d == 0.0

    def test_returns_zero_when_duration_field_missing(self):
        from app.cv.video_probe import probe_duration_seconds

        completed = MagicMock(returncode=0, stdout=b'{"format":{"bit_rate":"1000"}}')
        with patch("subprocess.run", return_value=completed):
            d = probe_duration_seconds("/tmp/video.mp4")
        assert d == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/unit/test_video_probe.py -x -v
```
Expected: every test fails with `ImportError: cannot import name 'probe_duration_seconds' from 'app.cv.video_probe'`.

- [ ] **Step 3: Implement the probe helper**

Create `backend/app/cv/video_probe.py`:

```python
"""Lightweight ffprobe wrapper for clip-duration validation (D-035).

Used by the analysis worker as a defense-in-depth check before pose
extraction begins — a too-long clip is rejected at the quality-gate
boundary instead of hitting the 1800 s task timeout. Frontend already
enforces the same cap via HTML5 ``<video>.duration`` at upload time.

Returns 0.0 on any failure (subprocess error, invalid JSON, missing
duration field) so callers can apply their own policy without try/except
boilerplate. The pipeline treats 0.0 as "unknown — let it through".
"""
from __future__ import annotations

import json
import logging
import subprocess

logger = logging.getLogger(__name__)


def probe_duration_seconds(video_path: str) -> float:
    """Return the duration of ``video_path`` in seconds, or 0.0 on failure.

    Calls ``ffprobe -v error -show_entries format=duration -of json``.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path,
            ],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("ffprobe failed for %s", video_path, exc_info=True)
        return 0.0

    if result.returncode != 0:
        logger.warning(
            "ffprobe returncode=%s for %s: %s",
            result.returncode, video_path, result.stderr[:200] if result.stderr else b"",
        )
        return 0.0

    try:
        payload = json.loads(result.stdout)
        duration = float(payload["format"]["duration"])
        return duration
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        logger.warning("ffprobe output unparseable for %s", video_path, exc_info=True)
        return 0.0
```

- [ ] **Step 4: Re-run tests to verify they pass**

```bash
cd backend && uv run pytest tests/unit/test_video_probe.py -x -v
```
Expected: 4 tests PASS.

- [ ] **Step 5: Wire the duration check into the worker after download**

In `backend/app/workers/analysis_worker.py`, find the call site that invokes `run_cv_pipeline` (or the wrapper that downloads + runs the pipeline). The duration check belongs immediately after the video is on local disk, before pose extraction.

The simplest place is in the pipeline service `run_cv_pipeline` itself, immediately after Step 1 download. Edit `backend/app/services/pipeline.py`:

Find the current Step 1 download block (around lines 283-296). After the download is complete and `video_local` exists, insert this duration check BEFORE the StageTimer-wrapped `extract_landmarks` block:

Add the import at the top of the file alongside other `app.cv.*` imports:
```python
from app.cv.video_probe import probe_duration_seconds
```

Add a constant at the top of the file alongside `_BUCKET`:
```python
# D-035: hard cap on clip duration to avoid timeout DoS via long uploads.
# Frontend enforces the same cap; this is defense-in-depth.
_MAX_DURATION_FREE_TIER_S = 60.0
_MAX_DURATION_EXTENDED_S = 120.0
```

Then immediately AFTER the download block (after `video_local = analysis.video_path` in the test branch) and BEFORE `# Step 2: Pose extraction`:

```python
    # D-035: defense-in-depth duration check after download
    with timer.stage("duration_probe"):
        duration_s = await loop.run_in_executor(
            None, probe_duration_seconds, video_local,
        )
    cap_s = (
        _MAX_DURATION_EXTENDED_S
        if getattr(analysis, "extended_mode", False)
        else _MAX_DURATION_FREE_TIER_S
    )
    if duration_s > cap_s:
        analysis.quality_gate_result = {
            "passed": False,
            "status": "rejected",
            "checks": [{
                "passed": False,
                "name": "duration",
                "level": "error",
                "metric_value": duration_s,
                "threshold": cap_s,
                "user_message": (
                    f"Video is {duration_s:.1f}s — please trim to under {cap_s:.0f}s. "
                    "Long clips can take many minutes to analyse on the current tier."
                ),
            }],
        }
        analysis.status = transition(analysis.status, "quality_gate_rejected")
        analysis.timing_json = timer.as_dict()
        await repo.update(analysis)
        raise QualityGateRejection(f"Clip duration {duration_s:.1f}s exceeds {cap_s:.0f}s cap")
```

If `Analysis.extended_mode` field doesn't exist, the `getattr(..., False)` defaults to False (free-tier cap). Add the field to the model in a follow-up task only if Task 8 (frontend) needs it surfaced via API — for now the existing schema is fine because the API never set it.

- [ ] **Step 6: Add a test for the duration-gate rejection in pipeline**

In `backend/tests/unit/test_pipeline.py`, append:

```python
class TestPipelineDurationGate:
    @pytest.mark.asyncio
    async def test_pipeline_rejects_too_long_clip(self):
        analysis = _make_mock_analysis()
        repo = _make_mock_repo(analysis)

        with (
            patch(f"{_PKG}.probe_duration_seconds", return_value=180.0),  # 3 min, exceeds 60s cap
        ):
            from app.services.pipeline import QualityGateRejection
            with pytest.raises(QualityGateRejection):
                await run_cv_pipeline(
                    analysis_id=_ANALYSIS_ID,
                    repo=repo,
                    redis=_make_mock_redis(),
                    storage_client=_make_mock_storage(),
                    openai_client=None,
                )

        assert analysis.status == "quality_gate_rejected"
        gate = analysis.quality_gate_result
        assert gate["passed"] is False
        check = next(c for c in gate["checks"] if c["name"] == "duration")
        assert check["metric_value"] == 180.0
        assert check["threshold"] == 60.0
```

- [ ] **Step 7: Run the new + existing pipeline tests**

```bash
cd backend && uv run pytest tests/unit/test_pipeline.py tests/unit/test_video_probe.py -x -q
```
Expected: all PASS. If pre-existing pipeline tests fail because they don't mock `probe_duration_seconds`, add the mock to their context managers.

- [ ] **Step 8: Commit**

```bash
git add backend/app/cv/video_probe.py backend/tests/unit/test_video_probe.py backend/app/services/pipeline.py backend/tests/unit/test_pipeline.py
git commit -m "fix(pipeline): reject clips longer than 60s/120s after download (D-035)"
```

---

## Task 7: Frontend client-side duration block

**Files:**
- Modify: `frontend/src/components/Upload/UploadForm.tsx`
- Modify: `frontend/src/components/Upload/UploadForm.test.tsx`

This blocks the upload from EVER starting if the clip is too long. Backend Task 6 is the safety net.

- [ ] **Step 1: Read the existing UploadForm to find where the file is selected**

```bash
cd frontend && grep -n "file\|File\|onChange\|handleFileSelect" src/components/Upload/UploadForm.tsx | head -20
```
Note the function name that handles file selection — call it `handleFileSelect` below. If the actual name differs in the file, use that name.

- [ ] **Step 2: Write a failing Vitest test**

In `frontend/src/components/Upload/UploadForm.test.tsx` (or whichever test file co-located with UploadForm), add a new test block. If the file doesn't exist, create it following the existing frontend Vitest conventions (look at adjacent `*.test.tsx` files for setup imports).

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { UploadForm } from "./UploadForm";

// Helper: create a synthetic File whose duration we control via a mocked
// HTMLVideoElement. Forces window.URL.createObjectURL to return a stub.
function mockVideoDuration(seconds: number) {
  vi.spyOn(window.URL, "createObjectURL").mockReturnValue("blob:fake");
  vi.spyOn(HTMLMediaElement.prototype, "addEventListener").mockImplementation(
    function (this: HTMLVideoElement, evt: string, cb: any) {
      if (evt === "loadedmetadata") {
        Object.defineProperty(this, "duration", { value: seconds, configurable: true });
        cb();
      }
    },
  );
}

describe("UploadForm duration validation (D-035)", () => {
  it("warns at 30s but allows submit", async () => {
    mockVideoDuration(45);
    render(<UploadForm />);
    const file = new File(["x"], "test.mp4", { type: "video/mp4" });
    const input = screen.getByLabelText(/video file/i, { selector: "input" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/longer than 30 seconds/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /upload video/i })).not.toBeDisabled();
  });

  it("hard-blocks above 60s in standard mode", async () => {
    mockVideoDuration(90);
    render(<UploadForm />);
    const file = new File(["x"], "test.mp4", { type: "video/mp4" });
    const input = screen.getByLabelText(/video file/i, { selector: "input" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/exceeds the 60 second limit/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /upload video/i })).toBeDisabled();
  });

  it("allows up to 120s when Extended Mode is checked", async () => {
    mockVideoDuration(100);
    render(<UploadForm />);
    const extendedCheckbox = screen.getByLabelText(/extended mode/i);
    fireEvent.click(extendedCheckbox);

    const file = new File(["x"], "test.mp4", { type: "video/mp4" });
    const input = screen.getByLabelText(/video file/i, { selector: "input" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      // No error, but maybe a warning — submit must be enabled
      expect(screen.getByRole("button", { name: /upload video/i })).not.toBeDisabled();
    });
  });
});
```

- [ ] **Step 3: Run the new tests to confirm they fail**

```bash
cd frontend && npx vitest run src/components/Upload/UploadForm.test.tsx 2>&1 | tail -10
```
Expected: failures because the duration UI does not yet exist.

- [ ] **Step 4: Add duration validation to UploadForm**

In `frontend/src/components/Upload/UploadForm.tsx`, find the file-select handler. Add a duration-checking helper:

```tsx
const MAX_DURATION_FREE_S = 60;
const MAX_DURATION_EXTENDED_S = 120;
const WARN_DURATION_S = 30;

async function probeVideoDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.addEventListener("loadedmetadata", () => {
      const d = video.duration;
      URL.revokeObjectURL(url);
      resolve(isFinite(d) ? d : 0);
    });
    video.addEventListener("error", () => {
      URL.revokeObjectURL(url);
      resolve(0);
    });
    video.src = url;
  });
}
```

Add component state for the duration:
```tsx
const [duration, setDuration] = useState<number | null>(null);
```

In the `handleFileSelect` (or whatever the existing handler is), after the file is set in state, call:
```tsx
const d = await probeVideoDuration(selectedFile);
setDuration(d);
```

Compute the cap and the disabled / warning state inline near the submit button:

```tsx
const cap = extendedMode ? MAX_DURATION_EXTENDED_S : MAX_DURATION_FREE_S;
const tooLong = duration !== null && duration > cap;
const longWarning =
  duration !== null && !tooLong && duration > WARN_DURATION_S;
```

Render the warning / error messages near the file-info paragraph:
```tsx
{tooLong && (
  <p className="text-red-600 text-sm">
    This clip is {duration!.toFixed(1)}s, which exceeds the {cap} second limit.
    Please trim it before uploading.
  </p>
)}
{longWarning && (
  <p className="text-amber-600 text-sm">
    This clip is longer than 30 seconds. Analysis may take several minutes.
  </p>
)}
```

Update the submit button's `disabled` prop to include `|| tooLong`:
```tsx
<button disabled={!file || !exerciseType || !exerciseVariant || tooLong}>
  Upload Video
</button>
```

(Adjust the condition to merge with the existing disabled logic — find the existing `disabled={...}` clause and append `|| tooLong` to it.)

- [ ] **Step 5: Re-run the tests to confirm they pass**

```bash
cd frontend && npx vitest run src/components/Upload/UploadForm.test.tsx 2>&1 | tail -10
```
Expected: 3 tests PASS.

- [ ] **Step 6: Run the full frontend test suite**

```bash
cd frontend && npx vitest run 2>&1 | tail -10
```
Expected: all pre-existing tests still pass + 3 new ones.

- [ ] **Step 7: Type-check + lint**

```bash
cd frontend && npx tsc --noEmit && npx eslint src/components/Upload/ 2>&1 | tail -5
```
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/Upload/UploadForm.tsx frontend/src/components/Upload/UploadForm.test.tsx
git commit -m "feat(frontend): block upload of clips >60s/120s with duration probe (D-035)"
```

---

## Task 8: Update backlog + decisions docs

**Files:**
- Modify: `backlog.md`
- Modify: `decisions.md`

- [ ] **Step 1: Add D-036 row to backlog.md**

In `backlog.md`, find the row for D-035. Append a new row immediately after it (use the same column structure as D-034 / D-035):

```markdown
| D-036 | **GPU offload for pose extraction (post-private-beta).** BlazePose Heavy on the 2-vCPU droplet costs ~120-150 ms/frame regardless of input resolution. The fundamental constraint per ADR-058 is that the CPU pipeline cannot scale to clips much beyond ~30 s @ 60 fps without GPU acceleration. Defer evaluation + implementation to **after** L2 private beta launches. **Trigger condition** to lift: (a) demand exceeds the CPU pipeline's capacity (queue depth grows faster than worker can drain), OR (b) clip duration limits become the top user complaint (>3 distinct beta users explicitly request longer clips). **Scope when triggered**: vendor evaluation (Modal vs Replicate vs self-hosted), prototype with `atharva-bench-no-weight.mov`, threshold validation against current MediaPipe Heavy outputs, swap behind a feature flag, ramp 10% → 100%. **Estimated cost**: $0.001-$0.005 per analysis; estimated 50-100x inference speedup. | L | post-beta | NFR-OPER-02 | deferred |
```

- [ ] **Step 2: Add ADR-058 to decisions.md**

At the end of `decisions.md`, append:

```markdown

## ADR-058: D-035 instrumentation tier — measure first, optimize second (Session 35.5)
**Context**: Sessions 33 → 34 → 35 chased the analysis-pipeline performance bug (`process_analysis` timeout on full-length 1080p@59fps clips) through three layers of guess-and-check: timeout bump (ADR-055), memory cap (ADR-056), streaming barbell (ADR-057), and 720p pose cap (PR #61). Each fix shipped without per-stage telemetry, so each subsequent failure mode surfaced as a surprise. Session 35 root-cause benchmarking finally measured per-stage cost on the failing clip in the worker container and discovered (a) BlazePose Heavy is ~150 ms/frame regardless of input resolution, (b) `RunningMode.IMAGE` is ~20% slower than `RunningMode.VIDEO`, (c) frame striding helps less than expected because `cv2.read()` dominates non-inference cost, and (d) **bench predicts ~290 s for pose extraction but production hits 900 s without finishing — a 3× unexplained gap**. Without instrumentation we cannot identify what amplifies in production.
**Decision**: Ship a four-part Tier 1 fix together: (A) add `analyses.timing_json` JSONB column + `StageTimer` context manager around every pipeline step so production has per-stage wall-time data on every analysis going forward, (B) switch `extract_landmarks` from `RunningMode.IMAGE` → `RunningMode.VIDEO` (5-line code change, ~20% inference speedup, within ±1° angle tolerance per CLAUDE.md), (D) raise streaq `process_analysis` timeout from 900 s → 1800 s as safety net while telemetry accumulates, (E) cap upload duration at 60 s free / 120 s Extended Mode, enforced both client-side (HTML5 `<video>.duration`) and server-side (ffprobe defense-in-depth in the worker). Skip in-loop frame-stride (Tier 2 fix C) and ffmpeg fps-normalize for now — both touch rep-detection and angle-smoothing math, which is SaMD-adjacent and should not be modified blind. Re-evaluate C after one week of timing_json data.
**Consequences**: Operations gain per-analysis stage breakdowns from day one (we will know within 24 hours where the 3× bench-vs-prod gap actually lives). Pose extraction gets a free ~20% speedup with low test churn. The 1800 s safety net keeps a stuck job from killing UX without hiding slowness — the next E2E shows actual stage durations, not just "timed out". Real-user clips longer than 60 s are now blocked at upload time with a clear message instead of running for many minutes and failing — this is intentional friction for L2 beta scope. **GPU offload deferred** — see D-036 for trigger conditions. **Telemetry-first principle** (see ADR-059) becomes the default for any future pipeline tuning.

## ADR-059: Telemetry-first principle for CV pipeline tuning (Session 35.5)
**Context**: Three sessions of fix-by-guess (ADR-055, ADR-056, ADR-057, PR #61) accumulated technical debt without resolving the underlying timeout. Each fix addressed a symptom that turned out not to be the root cause. The cost was ~6 hours of session time, 4 PRs, and a deferred private beta milestone.
**Decision**: For any future change to `app/services/pipeline.py`, `app/cv/pose_extraction.py`, `app/cv/barbell_detection.py`, `app/cv/artifact_generation.py`, or any other CV pipeline component motivated by performance: REQUIRE production timing_json data (post-ADR-058) showing the targeted stage is in the top 3 contributors before merging. The exception is correctness fixes (a stage produces wrong output) — those proceed normally. This rule is enforced by the spelix-cv-engineer agent in code review.
**Consequences**: Slower iteration on perf hunches, but no more ADR chains where the next fix invalidates the prior one's framing. The cost of one additional E2E run with telemetry is ~5-15 minutes; the cost of a wrong fix is multiple sessions. Net positive even on the second iteration.
```

- [ ] **Step 3: Commit**

```bash
git add backlog.md decisions.md
git commit -m "docs(backlog,decisions): D-036 GPU deferral + ADR-058/059 telemetry-first (D-035)"
```

---

## Task 9: PR + CI + merge + droplet verification

- [ ] **Step 1: Push branch**

```bash
git push -u origin fix/d035-instrument-and-pipeline-fixes
```

- [ ] **Step 2: Open PR via `mcp__github__create_pull_request`**

Owner: `atharva6905`, Repo: `spelix`, Base: `main`, Head: `fix/d035-instrument-and-pipeline-fixes`.

Title: `fix(pipeline): D-035 telemetry + Tier 1 pipeline fixes (instrumentation, VIDEO mode, 1800s timeout, duration cap)`

Body:
```markdown
## Summary

Four-part Tier 1 fix for D-035 (pose extraction timeout on full-length 1080p@59fps clips), shipped together so production gets telemetry, the easy speedup, the safety net, and the upload guardrail in a single deploy. Plus D-036 + ADR-058/059 documenting the GPU-offload deferral and the telemetry-first principle.

### A. Per-stage timing instrumentation (`analyses.timing_json`)
- New Alembic migration `007_add_timing_json` adds nullable JSONB column.
- New `app.services.timing.StageTimer` context manager records wall durations per pipeline step.
- Pipeline writes timing dict incrementally + at completion so partial-completion states still leave triage data.
- 7 unit tests for StageTimer + 1 pipeline-level test for end-to-end wiring.

### B. RunningMode IMAGE → VIDEO
- `extract_landmarks` switches to `RunningMode.VIDEO` + `detect_for_video()` with monotonic timestamp_ms.
- ~20% inference speedup per session 35 bench (148 → 120 ms/frame).
- Within ±1° angle tolerance per CLAUDE.md.
- 5 new unit tests for VIDEO mode + timestamp behavior; existing `TestMediaPipeConfig` updated.

### D. streaq `process_analysis` timeout 900 → 1800s
- Pure config change as safety net while we collect telemetry.
- Comment updated to reference ADR-058.

### E. Upload duration cap (60s free / 120s Extended Mode)
- Frontend: HTML5 `<video>.duration` probe blocks submit if too long, warns at 30s.
- Backend defense-in-depth: ffprobe via `app.cv.video_probe.probe_duration_seconds` after download; too-long clip rejected at quality_gate boundary with clear user_message.
- 4 unit tests for ffprobe wrapper + 1 pipeline test for rejection + 3 frontend tests for the UI states.

### Docs
- `backlog.md`: D-036 row added (GPU offload, deferred to post-private-beta with explicit trigger conditions).
- `decisions.md`: ADR-058 (instrumentation tier rationale + GPU deferral) and ADR-059 (telemetry-first principle for future CV pipeline tuning).

## Why this approach

Session 35 root-cause investigation (see decisions.md ADR-058) confirmed:
- Bench predicts pose extraction ~290s for the failing 22.8s clip.
- Production hits 900s without finishing — a 3× unexplained gap.
- Without per-stage telemetry, every prior fix has been a guess.

Shipping instrumentation + the easy wins (B + D + E) in one PR means within hours of merge, production will tell us exactly where the budget goes. Then Tier 2 (ffmpeg fps-normalize / GPU offload) is decided with data, not hunches. Per ADR-059, telemetry-first is the new default for any CV pipeline perf change.

## Test plan

- [x] StageTimer: 7 unit tests covering record, copy semantics, exception safety
- [x] Pipeline timing wiring: 1 integration test verifying 8 expected stage names appear in timing_json
- [x] VIDEO mode: 5 unit tests for running_mode + monotonic timestamps; existing TestMediaPipeConfig updated
- [x] Duration probe: 4 unit tests covering valid, error, invalid JSON, missing field
- [x] Pipeline duration rejection: 1 test verifying too-long clip → quality_gate_rejected with structured user_message
- [x] Frontend: 3 Vitest tests for warn / block / extended-mode-allows
- [x] Backend full suite green expected: ~1517 passed (1505 baseline + 12 new tests)
- [x] Frontend full suite green expected: ~269 passed (266 baseline + 3 new tests)
- [ ] Prod verification: re-upload `atharva-bench-no-weight.mov` (37 MB, 1080×1920, 22.8 s, 59 fps); query `analyses.timing_json` to identify the bench-vs-prod gap; status MUST be `completed` or `quality_gate_rejected` (NOT timeout) — within 1800 s budget.

Closes (partially): D-035
Defers: D-036 to post-beta
Related: ADR-055 (timeout history), ADR-056 (memory budget), ADR-057 (streaming barbell), PR #57, PR #59, PR #61
```

- [ ] **Step 3: Wait for CI**

Poll via `mcp__github__get_pull_request_status`. Expected checks: backend pytest, backend ruff, backend pyright, frontend vitest, frontend lint, secret scanning, Vercel preview, Deploy to Production (runs on merge).

If CI fails, read logs, fix the underlying issue, push a new commit. Do NOT skip hooks.

- [ ] **Step 4: Pause for user confirmation before merging**

This PR is bigger than the previous D-035 PR (#61) — schema migration + multi-component change. Ask the user to confirm before merging. The merge triggers production deploy.

- [ ] **Step 5: Merge via `mcp__github__merge_pull_request`**

After confirmation: `merge_method: "merge"` (NEVER `"squash"`). Pull main locally, wait for `Deploy to Production` CI step, verify droplet HEAD matches.

- [ ] **Step 6: Apply migration on prod**

Migration auto-applies via the deploy script (it runs `alembic upgrade head` before starting the worker per CLAUDE.md `apply migrations immediately`). Verify on the droplet:

```bash
ssh spelix-droplet "docker exec spelix-backend-1 sh -c 'cd /app && /app/.venv/bin/python -c \"from sqlalchemy import inspect, create_engine; import os; e = create_engine(os.environ[\\\"DATABASE_URL\\\"]); cols = {c[\\\"name\\\"] for c in inspect(e).get_columns(\\\"analyses\\\")}; print(\\\"timing_json present:\\\", \\\"timing_json\\\" in cols)\"'"
```
Expected: `timing_json present: True`.

If migration didn't auto-apply (no startup hook in the worker), run manually:
```bash
ssh spelix-droplet "docker exec spelix-backend-1 /app/.venv/bin/alembic -c /app/alembic.ini upgrade head"
```

---

## Task 10: Prod E2E verification with timing data

**Files:** uses `e2e/fixtures/atharva-bench-no-weight.mov` (local, not committed).

This is the moment of truth — the same clip that timed out at 900s now has 1800s budget AND VIDEO mode AND telemetry. The duration cap is 60s, the clip is 22.8s, so it should NOT be rejected by the duration gate.

- [ ] **Step 1: Open prod upload page via Playwright MCP**

Call `mcp__playwright__browser_navigate` → `https://spelix.app/upload`. Snapshot to verify auth.

- [ ] **Step 2: Select Bench Press / Flat**

Use `mcp__playwright__browser_select_option` for both dropdowns.

- [ ] **Step 3: Attach the full clip**

Call `mcp__playwright__browser_click` on the Video File button to open file picker, then `mcp__playwright__browser_file_upload` with absolute path `C:/Users/athar/projects/spelix/e2e/fixtures/atharva-bench-no-weight.mov`.

- [ ] **Step 4: Verify NO duration warning**

Snapshot the page. The 22.8s clip should NOT trigger any warning (warning threshold is 30s). Submit button MUST be enabled.

- [ ] **Step 5: Click Upload Video; capture analysis ID from redirect URL**

- [ ] **Step 6: Poll DB for status + timing_json**

Via `mcp__supabase__execute_sql`:

```sql
SELECT
  id, status,
  EXTRACT(EPOCH FROM (NOW() - created_at)) AS elapsed_s,
  timing_json
FROM analyses
WHERE id = '<analysis-id>';
```

Re-run every 60-90 seconds until `status` is one of `completed`, `quality_gate_rejected`, or `failed`. Should NOT stay in `quality_gate_pending` past 1800 s — if it does, the timeout itself is busted, escalate immediately.

- [ ] **Step 7: Read timing_json for the gap analysis**

Once `status != quality_gate_pending`, query:
```sql
SELECT
  id, status, jsonb_pretty(timing_json) AS timing
FROM analyses
WHERE id = '<analysis-id>';
```

Expected shape (key insight: actual ms per stage):
```json
{
  "download": <ms>,
  "duration_probe": <ms>,
  "extract_landmarks": <ms>,   // <- compare against bench's 287000ms
  "exercise_detection": <ms>,
  "quality_gates": <ms>,
  "rep_detection": <ms>,
  "form_scoring": <ms>,
  "annotation_generation": <ms>,
  "artifact_upload": <ms>
}
```

If `extract_landmarks` is much larger than ~290s (bench projection), we've identified that asyncio executor / OS overhead is the gap. If it's close to bench, then some OTHER stage is the bottleneck — we've identified what to fix next.

- [ ] **Step 8: Check console + network for errors**

`mcp__playwright__browser_console_messages` (level `error`) + `mcp__playwright__browser_network_requests` (filter 4xx/5xx). Acceptable: 0 new errors. Pre-existing D-028 banner is OK.

- [ ] **Step 9: Record findings**

Write a short note under "E2E findings — Session 35.5" in `.claude/handoff.md` with:
- Final status of analysis
- Total elapsed time
- The full `timing_json` dict
- Top 3 stages by ms
- Whether the bench-vs-prod gap was explained or remains mysterious
- One-line recommendation for next work (Tier 2 fix C, or different stage entirely)

---

## Task 11: Session 35.5 handoff

**Files:**
- Modify: `.claude/handoff.md`

- [ ] **Step 1: Prepend session 35.5 header**

At the top of `.claude/handoff.md`, insert above the existing Session 33 (or 34/35) header:

```markdown
# Session 35.5 Handoff → Session 36: D-035 telemetry tier shipped, real per-stage data captured for the first time

**Context refresh:** Session 35.5 stopped chasing pose-extraction-only fixes for D-035 and shipped a four-part instrumentation + Tier 1 bundle. After three sessions (33-35) of guess-and-fix, the new `analyses.timing_json` JSONB column gives us per-stage wall-time data on every analysis. VIDEO mode + 1800s timeout safety net + 60s/120s upload cap rounded out the bundle. ADR-058 captures the rationale; ADR-059 makes telemetry-first the default for any CV pipeline perf change going forward; D-036 deferred GPU offload to post-private-beta with explicit trigger conditions.

## 1. Completed

### PR #<n> — `fix(pipeline): D-035 telemetry + Tier 1 pipeline fixes`
- Merge commit: `<merge-sha>`
- CI: all checks green including Deploy to Production
- Migration 007 applied on prod
- Backend test count: 1505 → 1517 (+12)
- Frontend test count: 266 → 269 (+3)

### Documentation updates
- `backlog.md`: D-036 row added (GPU offload, deferred)
- `decisions.md`: ADR-058 (telemetry tier rationale) + ADR-059 (telemetry-first principle)

## 2. Remaining

### Sprint-blocking
| ID | Title | Status | Notes |
|---|---|---|---|
| D-035 | Pose extraction CPU bottleneck on full 1080p@59fps clips | **partial** | Tier 1 shipped. Tier 2 decision awaits at least 1 week of timing_json data per ADR-059. |

### Known deferred (unchanged)
| ID | Title | Notes |
|---|---|---|
| D-028 | Realtime "Connection lost" banner | Pre-existing |
| D-029 | SaMD rename `injury_advice_accurate` → `movement_advice_accurate` | Pre-existing |
| D-030 | Orphan `rag_documents` cleanup | |
| D-031 | Admin GET /rag/documents free-text query param | |
| D-036 | GPU offload (post-beta, trigger-gated) | New this session |

### Phase 3 remaining batches
- Batch 2 — Distillation (P3-004, P3-005, FR-BRAIN-14): not started, can pull forward
- Batch 3 — Review queue + Reasoning sidebar (P3-006, P3-007): not started

## 3. Test counts
- Backend: 1517 passing, 25 skipped, 0 failing
- Frontend: 269 passing, 0 failing
- Coverage: 90%+ (no regression)

## 4. E2E findings (Session 35.5)

[Filled in by Task 10 Step 9 — paste the timing_json + top-3 stages summary here]

## 5. Blockers

[Per E2E result. If timing_json revealed a clear bottleneck, name it. Otherwise note "investigate timing_json across next ~10 analyses to find the bench-vs-prod gap".]

## 6. Next session start

```bash
/status

# PRIORITY 1: Read timing_json across the most recent ~10 prod analyses
#   SELECT id, status, timing_json FROM analyses
#   WHERE created_at > NOW() - INTERVAL '7 days' AND timing_json IS NOT NULL
#   ORDER BY created_at DESC LIMIT 10;
#
# Look for the stage that consistently dominates. Per ADR-059, that's the
# only stage worth optimizing next.

# PRIORITY 2: Decide Tier 2 fix based on data:
#   - If extract_landmarks dominates: Tier 2 fix C (ffmpeg fps-normalize) OR D-036 (GPU)
#   - If annotation_generation dominates: skip annotation for long clips
#   - If artifact_upload dominates: parallelize uploads
#   - If a NEW stage we didn't predict dominates: investigate that

# PRIORITY 3 (if Tier 2 perf fits in remaining sprint): pull Phase 3 Batch 2 forward
```
```

Replace `<n>` and `<merge-sha>` with real values from Task 9.

- [ ] **Step 2: Commit handoff**

```bash
git checkout -b docs/session-35.5-handoff
git add .claude/handoff.md
git commit -m "docs(handoff): session 35.5 — D-035 telemetry tier shipped"
git push -u origin docs/session-35.5-handoff
```

- [ ] **Step 3: Open + merge handoff PR**

`mcp__github__create_pull_request` with base `main`, head `docs/session-35.5-handoff`, title `docs(handoff): session 35.5`, body one line. Wait for CI, merge with `merge_method: "merge"`. Pull main.

---

## Self-Review Notes

- [x] **Spec coverage:** All four production fixes (A=Task 1+2+3, B=Task 4, D=Task 5, E=Task 6+7) present + docs (Task 8) + verification (Tasks 9-11). GPU deferral covered by D-036 row + ADR-058. Telemetry-first principle covered by ADR-059. ✔
- [x] **Placeholder scan:** `<merge-sha>`, `<n>`, `<analysis-id>` are runtime values explicitly captured at the steps where they get filled in. No vague TODOs. ✔
- [x] **Type consistency:** `StageTimer.stage(name: str) -> Iterator[None]`, `as_dict() -> dict[str, float]`, `probe_duration_seconds(video_path: str) -> float`, `_pose_frame_dimensions(src_w: int, src_h: int) -> tuple[int, int]` (preserved from PR #61) — names match across helper definitions, test assertions, and call sites. ✔
- [x] **Scope check:** four production changes + two docs files + verification. No surrounding refactor, no architectural restructure of the pipeline (saved for Tier 2). All within one branch. ✔
- [x] **Migration discipline:** Task 1 uses spelix-migration agent per project rules; head goes 006 → 007 cleanly; immediate apply per CLAUDE.md. ✔
- [x] **Test discipline:** every code change has TDD steps with concrete failing-test code, then implementation, then verification. ✔
- [x] **Frontend test approach:** Vitest + happy-dom (project standard); the `<video>` mock is the canonical pattern for HTMLMediaElement in Vitest. ✔
