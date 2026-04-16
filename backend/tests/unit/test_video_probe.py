"""Unit tests for app.cv.video_probe (D-035)."""
from __future__ import annotations

from unittest.mock import patch, MagicMock


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

        completed = MagicMock(returncode=1, stdout=b"", stderr=b"")
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
