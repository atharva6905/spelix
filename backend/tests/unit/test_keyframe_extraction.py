"""
Unit tests for keyframe extraction (FR-AICP-01).

TDD gates:
1. test_extract_keyframes_count_matches_reps  — 3 reps → 3 RepKeyframes
2. test_depth_frame_is_argmin                 — depth_frame_idx == start + argmin(angles[start:end+1])
3. test_images_are_valid_b64_jpeg             — valid JPEG base64 strings
4. test_empty_reps_returns_empty              — 0 reps → []
5. test_single_frame_rep                      — start==end, all three images identical
"""

from __future__ import annotations

import base64

import cv2
import numpy as np

from app.cv.keyframe_extraction import RepKeyframes, extract_keyframes
from app.cv.rep_detection import DetectedRep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_test_video(path: str, n_frames: int = 30, width: int = 64, height: int = 48) -> None:
    """Write a synthetic video where each frame has a distinct solid colour."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, 30.0, (width, height))
    for i in range(n_frames):
        # Each frame is a distinct shade — guaranteed distinguishable
        value = (i * 8) % 256
        frame = np.full((height, width, 3), fill_value=value, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def _make_rep(rep_index: int, start: int, end: int) -> DetectedRep:
    return DetectedRep(
        rep_index=rep_index,
        start_frame=start,
        end_frame=end,
        confidence_score=0.9,
        min_angle=75.0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_extract_keyframes_count_matches_reps(tmp_path):
    """3 reps → 3 RepKeyframes, one per rep."""
    video_path = str(tmp_path / "test.mp4")
    _create_test_video(video_path, n_frames=30)

    # Three non-overlapping reps across 30 frames
    reps = [
        _make_rep(0, 0, 9),
        _make_rep(1, 10, 19),
        _make_rep(2, 20, 29),
    ]
    # Monotonically decreasing then increasing angle per rep
    angles = np.zeros(30, dtype=float)
    for rep in reps:
        mid = (rep.start_frame + rep.end_frame) // 2
        for i in range(rep.start_frame, rep.end_frame + 1):
            angles[i] = 160.0 - abs(i - mid) * 5

    result = extract_keyframes(video_path, reps, angles)

    assert len(result) == 3
    for kf in result:
        assert isinstance(kf, RepKeyframes)


def test_depth_frame_is_argmin(tmp_path):
    """depth_frame_idx == rep.start_frame + argmin(angles[start:end+1])."""
    video_path = str(tmp_path / "test.mp4")
    _create_test_video(video_path, n_frames=20)

    # One rep from frame 2 to frame 12
    rep = _make_rep(0, 2, 12)

    # Angle dips to minimum at frame 7 (index 5 within the rep slice)
    angles = np.full(20, 160.0)
    angles[2:13] = [155, 140, 120, 100, 80, 60, 70, 95, 115, 135, 155]
    # Minimum in angles[2:13] is 60 at index 5 → absolute frame 7
    expected_depth = 2 + int(np.argmin(angles[2:13]))  # == 7

    result = extract_keyframes(video_path, [rep], angles)

    assert len(result) == 1
    assert result[0].depth_frame_idx == expected_depth


def test_images_are_valid_b64_jpeg(tmp_path):
    """All image fields decode to valid JPEG bytes (start with \\xff\\xd8)."""
    video_path = str(tmp_path / "test.mp4")
    _create_test_video(video_path, n_frames=15)

    rep = _make_rep(0, 0, 14)
    angles = np.linspace(160, 60, 15)

    result = extract_keyframes(video_path, [rep], angles)
    assert len(result) == 1
    kf = result[0]

    for field_name, b64_str in [
        ("start_image_b64", kf.start_image_b64),
        ("depth_image_b64", kf.depth_image_b64),
        ("end_image_b64", kf.end_image_b64),
    ]:
        raw = base64.b64decode(b64_str)
        assert raw[:2] == b"\xff\xd8", (
            f"{field_name} does not start with JPEG magic bytes"
        )


def test_empty_reps_returns_empty(tmp_path):
    """Zero reps → empty list (no video I/O needed)."""
    video_path = str(tmp_path / "test.mp4")
    _create_test_video(video_path, n_frames=10)

    angles = np.linspace(160, 60, 10)
    result = extract_keyframes(video_path, [], angles)

    assert result == []


def test_single_frame_rep(tmp_path):
    """When start_frame == end_frame, all three images are identical base64 strings."""
    video_path = str(tmp_path / "test.mp4")
    _create_test_video(video_path, n_frames=10)

    # Rep spanning a single frame (frame 5)
    rep = _make_rep(0, 5, 5)
    angles = np.full(10, 90.0)

    result = extract_keyframes(video_path, [rep], angles)

    assert len(result) == 1
    kf = result[0]
    assert kf.start_frame_idx == 5
    assert kf.depth_frame_idx == 5
    assert kf.end_frame_idx == 5
    assert kf.start_image_b64 == kf.depth_image_b64 == kf.end_image_b64
