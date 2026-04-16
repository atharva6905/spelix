"""D-035 pose extraction diagnostic.

Runs MediaPipe pose extraction on a video in two variants to isolate
the bench-vs-prod gap observed in session 35.5 (`.claude/handoff.md` sections 2-3):

- ``executor``: ``extract_landmarks`` wrapped in ``loop.run_in_executor``,
  the same call path as ``app.services.pipeline.run_cv_pipeline`` line 348.
- ``inline``: ``extract_landmarks`` invoked directly inside the async
  function, blocking the event loop for the duration.

Compare both numbers against ``backend/bench_video_mode.py`` (bare-Python,
no asyncio, no streaq heartbeat) to triangulate whether the slowdown
lives in the executor, the event loop, or streaq's heartbeat task.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.cv.pose_extraction import extract_landmarks

log = logging.getLogger(__name__)


async def _run_pose_extraction_diagnostic(
    video_path: str,
) -> dict[str, dict[str, float]]:
    """Run extract_landmarks twice and return per-variant wall timings."""
    loop = asyncio.get_running_loop()

    # Variant 1: via run_in_executor (production path).
    start = time.perf_counter()
    landmarks_exec, fps_exec, _, _ = await loop.run_in_executor(
        None, extract_landmarks, video_path
    )
    wall_ms_exec = (time.perf_counter() - start) * 1000.0

    # Variant 2: inline — blocks the event loop while MediaPipe works.
    start = time.perf_counter()
    landmarks_inline, fps_inline, _, _ = extract_landmarks(video_path)
    wall_ms_inline = (time.perf_counter() - start) * 1000.0

    log.info(
        "D035_DIAG_RESULT video_path=%s executor_ms=%.1f inline_ms=%.1f "
        "frame_count=%d fps=%.1f",
        video_path,
        wall_ms_exec,
        wall_ms_inline,
        len(landmarks_exec),
        float(fps_exec),
    )

    return {
        "executor": {
            "wall_ms": wall_ms_exec,
            "frame_count": float(len(landmarks_exec)),
            "fps": float(fps_exec),
        },
        "inline": {
            "wall_ms": wall_ms_inline,
            "frame_count": float(len(landmarks_inline)),
            "fps": float(fps_inline),
        },
    }
