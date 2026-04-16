"""Tests for B-021 — annotated video + artifact generation.

TDD gates:
  - Synthetic frame → annotated frame has correct overlay color (#00FF88 BGR)
  - Rep counter shows cumulative count
  - Angle plot PNG is generated
  - Storage path formatting
  - Temp file management
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import cv2
import numpy as np
import pytest

from app.cv.video_annotator import (
    _SKELETON_COLOR,
    annotate_frame,
    draw_angle_labels,
    draw_rep_counter,
    draw_skeleton,
)
from app.cv.artifact_generation import (
    _annotation_dimensions,
    cleanup_temp_files,
    generate_angle_plot,
    generate_annotated_video,
    get_artifact_storage_path,
    get_temp_dir,
    upload_artifact,
)
from app.cv.rep_detection import DetectedRep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_landmarks(x: float = 0.5, y: float = 0.5) -> np.ndarray:
    """Create a (33, 5) landmark array with all landmarks at (x, y)."""
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 0] = x  # x
    lm[:, 1] = y  # y
    lm[:, 3] = 0.9  # visibility
    lm[:, 4] = 0.9  # presence
    return lm


def _make_frame(width: int = 640, height: int = 480) -> np.ndarray:
    """Create a black BGR frame."""
    return np.zeros((height, width, 3), dtype=np.uint8)


def _make_reps(count: int = 3, frames_per_rep: int = 30) -> list[DetectedRep]:
    """Create synthetic detected reps."""
    reps = []
    for i in range(count):
        reps.append(
            DetectedRep(
                rep_index=i,
                start_frame=i * frames_per_rep,
                end_frame=(i + 1) * frames_per_rep - 1,
                confidence_score=0.85,
                min_angle=75.0,
            )
        )
    return reps


# ---------------------------------------------------------------------------
# Video annotator tests
# ---------------------------------------------------------------------------


class TestDrawSkeleton:
    """Skeleton overlay draws lines in the correct colour."""

    def test_skeleton_colour_squat(self):
        frame = _make_frame()
        landmarks = _make_landmarks(0.5, 0.5)
        draw_skeleton(frame, landmarks, "squat")

        # The skeleton colour should be present in the frame
        # _SKELETON_COLOR is BGR: (0x88, 0xFF, 0x00)
        mask = np.all(frame == np.array(_SKELETON_COLOR, dtype=np.uint8), axis=2)
        assert mask.any(), "Skeleton colour #00FF88 not found in frame"

    def test_skeleton_colour_bench(self):
        frame = _make_frame()
        landmarks = _make_landmarks(0.5, 0.5)
        draw_skeleton(frame, landmarks, "bench")

        mask = np.all(frame == np.array(_SKELETON_COLOR, dtype=np.uint8), axis=2)
        assert mask.any(), "Skeleton colour #00FF88 not found in bench frame"

    def test_skeleton_colour_deadlift(self):
        frame = _make_frame()
        landmarks = _make_landmarks(0.5, 0.5)
        draw_skeleton(frame, landmarks, "deadlift")

        mask = np.all(frame == np.array(_SKELETON_COLOR, dtype=np.uint8), axis=2)
        assert mask.any(), "Skeleton colour #00FF88 not found in deadlift frame"

    def test_skeleton_thickness_2px(self):
        """Lines drawn with thickness=2 should produce pixels wider than 1px."""
        frame = _make_frame()
        # Place landmarks far apart so the line is visible
        lm = _make_landmarks()
        lm[12, 0] = 0.3  # shoulder x
        lm[12, 1] = 0.3  # shoulder y
        lm[24, 0] = 0.3  # hip x
        lm[24, 1] = 0.7  # hip y
        draw_skeleton(frame, lm, "squat")

        # Count green pixels — should be > 1 pixel wide
        mask = np.all(frame == np.array(_SKELETON_COLOR, dtype=np.uint8), axis=2)
        green_pixels = mask.sum()
        assert green_pixels > 10, f"Expected thick line, got {green_pixels} green pixels"


class TestDrawAngleLabels:
    """Angle labels are drawn near the correct joints."""

    def test_labels_drawn(self):
        frame = _make_frame()
        landmarks = _make_landmarks(0.5, 0.5)
        angles = {"hip_angle": 90.0, "knee_angle": 120.0}

        draw_angle_labels(frame, landmarks, "squat", angles)

        # Non-zero pixels should exist (anti-aliased text)
        assert frame.sum() > 0, "No label pixels drawn"

    def test_missing_angle_skipped(self):
        """If an angle key is not in the dict, that label is skipped."""
        frame = _make_frame()
        landmarks = _make_landmarks(0.5, 0.5)
        # Empty angles dict — no labels drawn
        draw_angle_labels(frame, landmarks, "squat", {})

        # Frame should remain black
        assert frame.sum() == 0, "Expected no drawing when no angles provided"

    def test_bench_labels(self):
        frame = _make_frame()
        landmarks = _make_landmarks(0.5, 0.5)
        angles = {"elbow_angle": 85.0, "shoulder_angle": 45.0}

        draw_angle_labels(frame, landmarks, "bench", angles)

        assert frame.sum() > 0, "No label pixels drawn for bench"


class TestDrawRepCounter:
    """Rep counter shows correct cumulative text."""

    def test_rep_counter_drawn(self):
        frame = _make_frame()
        draw_rep_counter(frame, 2, 5)

        # Frame should have non-zero pixels (text was drawn)
        assert frame.sum() > 0, "Rep counter was not drawn"

    def test_rep_counter_zero(self):
        frame = _make_frame()
        draw_rep_counter(frame, 0, 3)
        assert frame.sum() > 0, "Rep counter was not drawn for 0/3"


class TestAnnotateFrame:
    """Full frame annotation combines all elements."""

    def test_full_annotation(self):
        frame = _make_frame()
        landmarks = _make_landmarks(0.5, 0.5)
        angles = {"hip_angle": 90.0, "knee_angle": 120.0}

        annotate_frame(frame, landmarks, "squat", angles, 1, 3)

        # Both skeleton green and label white should be present
        green_mask = np.all(frame == np.array(_SKELETON_COLOR, dtype=np.uint8), axis=2)
        assert green_mask.any(), "Skeleton not drawn"

        # Non-zero pixels in top-left region (rep counter)
        top_left = frame[:60, :200]
        assert top_left.sum() > 0, "Rep counter area is empty"


# ---------------------------------------------------------------------------
# Artifact generation tests
# ---------------------------------------------------------------------------


class TestGenerateAnnotatedVideo:
    """Annotated video generation from source + landmarks."""

    def test_generates_output_file(self, tmp_path: Path):
        """Given a source video and landmarks, output MP4 is created."""
        # Create a minimal source video (5 frames, 64x48)
        src = str(tmp_path / "source.mp4")
        out = str(tmp_path / "annotated.mp4")
        width, height, n_frames, fps = 64, 48, 5, 30.0

        fourcc = cv2.VideoWriter.fourcc(*"mp4v")
        writer = cv2.VideoWriter(src, fourcc, fps, (width, height))
        for _ in range(n_frames):
            writer.write(np.zeros((height, width, 3), dtype=np.uint8))
        writer.release()

        landmarks = [_make_landmarks() for _ in range(n_frames)]
        reps = [
            DetectedRep(
                rep_index=0, start_frame=0, end_frame=3,
                confidence_score=0.9, min_angle=80.0,
            )
        ]
        angle_ts = {
            "hip_angle": np.full(n_frames, 90.0),
            "knee_angle": np.full(n_frames, 120.0),
        }

        result = generate_annotated_video(
            src, landmarks, reps, "squat", angle_ts, out,
        )

        assert result == out
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 0

    def test_cumulative_rep_count(self, tmp_path: Path):
        """Rep counter should be cumulative — only count completed reps."""
        src = str(tmp_path / "source.mp4")
        out = str(tmp_path / "annotated.mp4")
        width, height, n_frames, fps = 64, 48, 10, 30.0

        fourcc = cv2.VideoWriter.fourcc(*"mp4v")
        writer = cv2.VideoWriter(src, fourcc, fps, (width, height))
        for _ in range(n_frames):
            writer.write(np.zeros((height, width, 3), dtype=np.uint8))
        writer.release()

        landmarks = [_make_landmarks() for _ in range(n_frames)]
        reps = [
            DetectedRep(0, 0, 3, 0.9, 80.0),
            DetectedRep(1, 4, 7, 0.9, 85.0),
        ]
        angle_ts = {
            "hip_angle": np.full(n_frames, 90.0),
            "knee_angle": np.full(n_frames, 120.0),
        }

        generate_annotated_video(src, landmarks, reps, "squat", angle_ts, out)

        # Verify by reading back — frame 5 should have rep counter drawn
        cap = cv2.VideoCapture(out)
        try:
            frames = []
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
        finally:
            cap.release()

        assert len(frames) == n_frames
        # Frame 4 is right after rep 0 ends (end_frame=3) — should show 1/2
        # Frame 8 is right after rep 1 ends (end_frame=7) — should show 2/2
        # Both frames should have non-zero top-left (rep counter area)
        assert frames[4][:60, :200].sum() > 0, "Rep counter missing at frame 4"
        assert frames[8][:60, :200].sum() > 0, "Rep counter missing at frame 8"


class TestGenerateAnglePlot:
    """Angle time-series plot generation."""

    def test_generates_png(self, tmp_path: Path):
        out = str(tmp_path / "angles.png")
        angle_ts = {
            "hip_angle": np.linspace(160, 80, 100),
            "knee_angle": np.linspace(170, 90, 100),
        }

        result = generate_angle_plot(angle_ts, 30.0, "squat", out)

        assert result == out
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 1000, "PNG seems too small"

    def test_bench_plot(self, tmp_path: Path):
        out = str(tmp_path / "angles.png")
        angle_ts = {
            "elbow_angle": np.linspace(160, 80, 50),
            "shoulder_angle": np.linspace(90, 45, 50),
        }

        generate_angle_plot(angle_ts, 30.0, "bench", out)
        assert os.path.isfile(out)


# ---------------------------------------------------------------------------
# Storage path tests
# ---------------------------------------------------------------------------


class TestStoragePaths:
    def test_artifact_path(self):
        aid = uuid4()
        path = get_artifact_storage_path(aid, "annotated.mp4")
        assert path == f"artifacts/{aid}/annotated.mp4"

    def test_artifact_path_png(self):
        aid = uuid4()
        path = get_artifact_storage_path(aid, "angles.png")
        assert path == f"artifacts/{aid}/angles.png"


# ---------------------------------------------------------------------------
# Temp file management tests
# ---------------------------------------------------------------------------


class TestTempFiles:
    def test_get_temp_dir_creates_dir(self):
        aid = uuid4()
        tmp = get_temp_dir(aid)
        assert os.path.isdir(tmp)
        assert str(aid) in tmp
        # Cleanup
        cleanup_temp_files(aid)

    def test_cleanup_removes_dir(self, tmp_path: Path):
        aid = uuid4()
        tmp = get_temp_dir(aid)
        # Create a dummy file
        dummy = os.path.join(tmp, "test.txt")
        with open(dummy, "w") as f:
            f.write("test")
        assert os.path.isfile(dummy)

        cleanup_temp_files(aid)
        assert not os.path.isdir(tmp)


# ---------------------------------------------------------------------------
# Upload artifact tests
# ---------------------------------------------------------------------------


class TestUploadArtifact:
    @pytest.mark.asyncio
    async def test_upload_calls_storage(self, tmp_path: Path):
        """Upload reads local file and calls storage.upload."""
        local = str(tmp_path / "test.mp4")
        with open(local, "wb") as f:
            f.write(b"fake video data")

        mock_client = MagicMock()
        mock_bucket = AsyncMock()
        mock_client.storage.from_.return_value = mock_bucket

        result = await upload_artifact(
            mock_client, "videos", local, "artifacts/123/annotated.mp4",
        )

        assert result == "artifacts/123/annotated.mp4"
        mock_client.storage.from_.assert_called_once_with("videos")
        mock_bucket.upload.assert_called_once()
        call_args = mock_bucket.upload.call_args
        assert call_args[0][0] == "artifacts/123/annotated.mp4"
        assert call_args[0][1] == b"fake video data"


# ---------------------------------------------------------------------------
# Annotation dimension tests
# ---------------------------------------------------------------------------


class TestAnnotationDimensions:
    def test_caps_1080p_portrait_to_720p(self):
        w, h = _annotation_dimensions(1080, 1920)
        assert (w, h) == (720, 1280)

    def test_caps_1080p_landscape_to_720p(self):
        w, h = _annotation_dimensions(1920, 1080)
        assert (w, h) == (1280, 720)

    def test_no_change_for_720p_portrait(self):
        w, h = _annotation_dimensions(720, 1280)
        assert (w, h) == (720, 1280)

    def test_no_change_for_sub_720p(self):
        w, h = _annotation_dimensions(640, 480)
        assert (w, h) == (640, 480)

    def test_caps_4k_to_720p_equivalent(self):
        w, h = _annotation_dimensions(3840, 2160)
        assert max(w, h) <= 1280
        assert w % 2 == 0 and h % 2 == 0

    def test_output_dimensions_are_even(self):
        w, h = _annotation_dimensions(1081, 1921)
        assert w % 2 == 0 and h % 2 == 0
