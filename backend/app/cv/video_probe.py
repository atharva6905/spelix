"""Lightweight ffprobe wrapper for clip-duration validation (D-035).

Used by the analysis pipeline as defense-in-depth before pose extraction —
a too-long clip is rejected at the quality-gate boundary instead of hitting
the 1800 s task timeout. Frontend already enforces the same cap via the
HTML5 ``<video>.duration`` API at upload time.

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
        stderr_preview = result.stderr[:200] if result.stderr else b""
        logger.warning(
            "ffprobe returncode=%s for %s: %s",
            result.returncode, video_path, stderr_preview,
        )
        return 0.0

    try:
        payload = json.loads(result.stdout)
        duration = float(payload["format"]["duration"])
        return duration
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        logger.warning("ffprobe output unparseable for %s", video_path, exc_info=True)
        return 0.0
