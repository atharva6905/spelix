"""Artifact generation — annotated video, angle plot, Storage upload (B-021).

Orchestrates: annotate video frames → write annotated MP4 → generate angle
time-series plot (PNG) → upload both to Supabase Storage → write paths to
analyses row → delete local temp files.

Requirements: FR-CVPL-19, FR-UPLD-15, FR-XPRT-01

CPU-bound work: designed for ``loop.run_in_executor(None, fn)`` in the ARQ worker.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

import cv2
import numpy as np

from app.cv.rep_detection import DetectedRep
from app.cv.video_annotator import annotate_frame

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLOT_DPI = 100
_PLOT_WIDTH_INCHES = 10
_PLOT_HEIGHT_INCHES = 6

_STORAGE_ARTIFACT_PREFIX = "artifacts"


# ---------------------------------------------------------------------------
# Annotated video generation (CPU-bound, sync)
# ---------------------------------------------------------------------------


def generate_annotated_video(
    video_path: str,
    landmarks_per_frame: list[np.ndarray],
    reps: list[DetectedRep],
    exercise_type: str,
    angle_timeseries: dict[str, np.ndarray],
    output_path: str,
) -> str:
    """Create annotated MP4 with skeleton overlay, angle labels, rep counter.

    Parameters
    ----------
    video_path:
        Path to the source video file.
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame.
    reps:
        Detected reps from ``detect_reps()``.
    exercise_type:
        One of ``"squat"``, ``"bench"``, ``"deadlift"``.
    angle_timeseries:
        Dict of joint_name -> smoothed 1-D angle array.
    output_path:
        Where to write the annotated video.

    Returns
    -------
    str
        The *output_path* (for chaining convenience).
    """
    cap = cv2.VideoCapture(video_path)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter.fourcc(*"mp4v")

        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        try:
            total_reps = len(reps)

            # Build a sorted list of rep end frames for cumulative count
            rep_end_frames = sorted(r.end_frame for r in reps)

            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx < len(landmarks_per_frame):
                    landmarks = landmarks_per_frame[frame_idx]

                    # Per-frame angles from timeseries
                    angles: dict[str, float] = {}
                    for joint_name, series in angle_timeseries.items():
                        if frame_idx < len(series):
                            angles[joint_name] = float(series[frame_idx])

                    # Cumulative completed reps at this frame
                    completed = sum(1 for ef in rep_end_frames if ef <= frame_idx)

                    annotate_frame(
                        frame, landmarks, exercise_type,
                        angles, completed, total_reps,
                    )

                writer.write(frame)
                frame_idx += 1
        finally:
            writer.release()
    finally:
        cap.release()

    return output_path


# ---------------------------------------------------------------------------
# Angle time-series plot (CPU-bound, sync)
# ---------------------------------------------------------------------------


def generate_angle_plot(
    angle_timeseries: dict[str, np.ndarray],
    fps: float,
    exercise_type: str,
    output_path: str,
) -> str:
    """Generate angle time-series plot as PNG.

    Parameters
    ----------
    angle_timeseries:
        Dict of joint_name -> smoothed 1-D angle array.
    fps:
        Video frames per second (for time axis).
    exercise_type:
        Exercise type for the plot title.
    output_path:
        Where to write the PNG file.

    Returns
    -------
    str
        The *output_path*.
    """
    # Lazy import matplotlib to avoid startup cost
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(_PLOT_WIDTH_INCHES, _PLOT_HEIGHT_INCHES))

    for joint_name, series in angle_timeseries.items():
        time_s = np.arange(len(series)) / fps
        label = joint_name.replace("_", " ").title()
        ax.plot(time_s, series, label=label, linewidth=1.5)

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Angle (degrees)")
    ax.set_title(f"{exercise_type.title()} — Joint Angles Over Time")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=_PLOT_DPI, bbox_inches="tight")
    plt.close(fig)

    return output_path


# ---------------------------------------------------------------------------
# Storage upload helpers
# ---------------------------------------------------------------------------


def get_artifact_storage_path(analysis_id: UUID, filename: str) -> str:
    """Return the canonical Storage path for an artifact.

    ``artifacts/{analysis_id}/{filename}``
    """
    return f"{_STORAGE_ARTIFACT_PREFIX}/{analysis_id}/{filename}"


async def upload_artifact(
    storage_client: Any,
    bucket: str,
    local_path: str,
    storage_path: str,
) -> str:
    """Upload a local file to Supabase Storage.

    Parameters
    ----------
    storage_client:
        Supabase client (``supabase.AsyncClient``).
    bucket:
        Storage bucket name.
    local_path:
        Path to the local file.
    storage_path:
        Target path in Storage.

    Returns
    -------
    str
        The *storage_path* that was uploaded.
    """
    with open(local_path, "rb") as f:
        data = f.read()

    await storage_client.storage.from_(bucket).upload(
        storage_path,
        data,
        file_options={"content-type": _guess_content_type(local_path)},
    )

    return storage_path


def _guess_content_type(path: str) -> str:
    """Guess MIME type from file extension."""
    ext = Path(path).suffix.lower()
    return {
        ".mp4": "video/mp4",
        ".png": "image/png",
        ".pdf": "application/pdf",
        ".csv": "text/csv",
    }.get(ext, "application/octet-stream")


# ---------------------------------------------------------------------------
# Temp file management
# ---------------------------------------------------------------------------


def get_temp_dir(analysis_id: UUID) -> str:
    """Return (and create) the temp directory for an analysis."""
    tmp = os.path.join(tempfile.gettempdir(), "spelix", str(analysis_id))
    os.makedirs(tmp, exist_ok=True)
    return tmp


def cleanup_temp_files(analysis_id: UUID) -> None:
    """Delete all temp files for an analysis."""
    tmp = os.path.join(tempfile.gettempdir(), "spelix", str(analysis_id))
    if os.path.isdir(tmp):
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
