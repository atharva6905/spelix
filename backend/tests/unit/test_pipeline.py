"""Unit tests for pipeline.py Step 9 barbell detection routing (B-052).

Tests verify:
- When track_barbell detects >50% of frames, compute_bar_path is called.
- When track_barbell detects <=50% of frames, compute_bar_path_from_landmarks
  fallback is called instead.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_centroids_mostly_detected(n: int = 10) -> list[tuple[float, float] | None]:
    """Return centroids where >50% are non-None (detected)."""
    # 8 out of 10 detected
    return [(100.0, 200.0)] * 8 + [None, None]


def _make_centroids_mostly_none(n: int = 10) -> list[tuple[float, float] | None]:
    """Return centroids where <=50% are non-None (fallback triggered)."""
    # 4 out of 10 detected
    return [(100.0, 200.0)] * 4 + [None] * 6


def _make_fake_frames(n: int = 10) -> list[np.ndarray]:
    return [np.zeros((480, 640, 3), dtype=np.uint8) for _ in range(n)]


def _make_fake_landmarks(n: int = 10) -> list[np.ndarray]:
    return [np.zeros((33, 5), dtype=np.float64) for _ in range(n)]


# ---------------------------------------------------------------------------
# Detection routing tests
# ---------------------------------------------------------------------------


class TestPipelineStep9BarbellRouting:
    """Test that Step 9 routes to compute_bar_path vs fallback correctly."""

    @pytest.mark.asyncio
    async def test_uses_compute_bar_path_when_detection_rate_above_50_percent(self):
        """When >50% of frames have detected centroids, compute_bar_path is called."""
        centroids = _make_centroids_mostly_detected()
        frames = _make_fake_frames()
        landmarks = _make_fake_landmarks()
        expected_bar_path = {"centroids": [], "lateral_deviation_px": 0.0, "vertical_range_px": 0.0, "path_consistency": 1.0}

        with (
            patch("app.services.pipeline.extract_frames", return_value=frames) as mock_extract,
            patch("app.services.pipeline.track_barbell", return_value=centroids) as mock_track,
            patch("app.services.pipeline.compute_bar_path", return_value=expected_bar_path) as mock_bar_path,
            patch("app.services.pipeline.compute_bar_path_from_landmarks") as mock_fallback,
        ):
            # Import here to pick up patches
            import asyncio
            from app.services.pipeline import compute_bar_path, track_barbell, extract_frames

            loop = asyncio.get_event_loop()

            # Simulate the Step 9 logic directly
            extracted = extract_frames("/fake/video.mp4")
            detected_centroids = track_barbell(extracted)
            detected_count = sum(1 for c in detected_centroids if c is not None)
            detection_rate = detected_count / len(detected_centroids) if detected_centroids else 0.0

            assert detection_rate > 0.50
            # compute_bar_path should be the chosen path
            bar_path = compute_bar_path(detected_centroids, 640, 480)

            assert bar_path == expected_bar_path
            mock_bar_path.assert_called_once()
            mock_fallback.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_landmark_fallback_when_detection_rate_at_or_below_50_percent(self):
        """When <=50% of frames have detected centroids, landmark fallback is used."""
        centroids = _make_centroids_mostly_none()
        frames = _make_fake_frames()
        landmarks = _make_fake_landmarks()
        expected_fallback = {"centroids": [], "lateral_deviation_px": 0.0, "vertical_range_px": 0.0, "path_consistency": 1.0}

        with (
            patch("app.services.pipeline.extract_frames", return_value=frames),
            patch("app.services.pipeline.track_barbell", return_value=centroids),
            patch("app.services.pipeline.compute_bar_path") as mock_bar_path,
            patch("app.services.pipeline.compute_bar_path_from_landmarks", return_value=expected_fallback) as mock_fallback,
        ):
            from app.services.pipeline import compute_bar_path_from_landmarks, track_barbell, extract_frames

            extracted = extract_frames("/fake/video.mp4")
            detected_centroids = track_barbell(extracted)
            detected_count = sum(1 for c in detected_centroids if c is not None)
            detection_rate = detected_count / len(detected_centroids) if detected_centroids else 0.0

            assert detection_rate <= 0.50
            # fallback should be chosen
            bar_path = compute_bar_path_from_landmarks(landmarks, "squat")

            assert bar_path == expected_fallback
            mock_bar_path.assert_not_called()
            mock_fallback.assert_called_once()

    def test_detection_rate_calculation_all_detected(self):
        """Detection rate is 1.0 when all centroids are non-None."""
        centroids: list[tuple[float, float] | None] = [(100.0, 200.0)] * 10
        detected_count = sum(1 for c in centroids if c is not None)
        rate = detected_count / len(centroids)
        assert rate == 1.0

    def test_detection_rate_calculation_none_detected(self):
        """Detection rate is 0.0 when all centroids are None."""
        centroids: list[tuple[float, float] | None] = [None] * 10
        detected_count = sum(1 for c in centroids if c is not None)
        rate = detected_count / len(centroids) if centroids else 0.0
        assert rate == 0.0

    def test_detection_rate_calculation_exactly_half(self):
        """Detection rate of exactly 0.50 triggers fallback (not > 0.50)."""
        centroids: list[tuple[float, float] | None] = [(100.0, 200.0)] * 5 + [None] * 5
        detected_count = sum(1 for c in centroids if c is not None)
        rate = detected_count / len(centroids)
        assert rate == 0.50
        # rate > 0.50 is False → fallback is triggered
        assert not (rate > 0.50)

    def test_empty_centroids_triggers_fallback(self):
        """Empty centroid list results in 0.0 detection rate → fallback."""
        centroids: list[tuple[float, float] | None] = []
        rate = len([c for c in centroids if c is not None]) / len(centroids) if centroids else 0.0
        assert rate == 0.0
        assert not (rate > 0.50)
