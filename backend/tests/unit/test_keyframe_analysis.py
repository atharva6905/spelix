"""
Unit tests for KeyframeAnalysisService (FR-AICP-02).

All OpenAI calls are mocked — never call real API.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cv.keyframe_extraction import RepKeyframes
from app.services.keyframe_analysis import (
    KeyframeAnalysis,
    KeyframeAnalysisResult,
    KeyframeAnalysisService,
    _build_image_content,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal valid JPEG: 1x1 pixel white, base64-encoded
_TINY_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAs"
    "LDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zND"
    "L/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAx"
    "EB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAw"
    "IEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAk"
    "M2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZW"
    "ZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2"
    "t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8"
    "QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQD"
    "BAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYn"
    "LRChYkNOEl8RcYI4Q/RFhHRUYnJCk4N0kxY0ZIJygpOjU2Nzg5OkNERUZH"
    "SElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJ"
    "maoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn"
    "6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+gD/2Q=="
)


def _make_keyframes(n_reps: int = 3) -> list[RepKeyframes]:
    return [
        RepKeyframes(
            rep_index=i,
            start_frame_idx=i * 30,
            depth_frame_idx=i * 30 + 15,
            end_frame_idx=i * 30 + 29,
            start_image_b64=_TINY_JPEG_B64,
            depth_image_b64=_TINY_JPEG_B64,
            end_image_b64=_TINY_JPEG_B64,
        )
        for i in range(n_reps)
    ]


def _make_rep_metrics(n_reps: int = 3) -> list[dict[str, Any]]:
    return [
        {"rep_number": i + 1, "hip_angle_min_deg": 85.0 + i}
        for i in range(n_reps)
    ]


def _make_analysis_result(n_reps: int = 3) -> KeyframeAnalysisResult:
    return KeyframeAnalysisResult(
        per_rep=[
            KeyframeAnalysis(
                rep_index=i,
                observations=["Good depth observed"],
                form_deviations=[],
                phase_assessment="Solid bottom position",
            )
            for i in range(n_reps)
        ],
        overall_notes="Consistent form across all reps.",
    )


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestKeyframeAnalysisSchema:
    def test_analysis_result_valid(self) -> None:
        result = _make_analysis_result(2)
        assert len(result.per_rep) == 2
        assert result.overall_notes

    def test_empty_reps_result(self) -> None:
        result = KeyframeAnalysisResult(per_rep=[], overall_notes="No reps.")
        assert result.per_rep == []


# ---------------------------------------------------------------------------
# Image content builder tests
# ---------------------------------------------------------------------------


class TestImageContent:
    def test_full_reps_send_3_images_each(self) -> None:
        """≤6 reps: each rep sends 3 image blocks (start, depth, end)."""
        keyframes = _make_keyframes(3)
        content = _build_image_content(keyframes)

        image_blocks = [c for c in content if c.get("type") == "image_url"]
        assert len(image_blocks) == 9  # 3 reps × 3 images

    def test_max_image_cap_beyond_6_reps(self) -> None:
        """Beyond 6 reps, only depth frames are sent for extra reps."""
        keyframes = _make_keyframes(8)
        content = _build_image_content(keyframes)

        image_blocks = [c for c in content if c.get("type") == "image_url"]
        # 6 full reps × 3 + 2 extra reps × 1 = 20
        assert len(image_blocks) == 20

    def test_images_use_low_detail(self) -> None:
        """All images must use detail: 'low' to minimize token cost."""
        keyframes = _make_keyframes(2)
        content = _build_image_content(keyframes)

        for block in content:
            if block.get("type") == "image_url":
                assert block["image_url"]["detail"] == "low"

    def test_images_are_data_uri(self) -> None:
        """Image URLs must be base64 data URIs."""
        keyframes = _make_keyframes(1)
        content = _build_image_content(keyframes)

        for block in content:
            if block.get("type") == "image_url":
                assert block["image_url"]["url"].startswith("data:image/jpeg;base64,")


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestKeyframeAnalysisService:
    @pytest.mark.asyncio
    async def test_analyze_returns_structured_result(self) -> None:
        """Mocked GPT-4o → valid KeyframeAnalysisResult."""
        mock_client = MagicMock()
        expected = _make_analysis_result(3)

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(return_value=expected)

        with patch("app.services.keyframe_analysis.instructor") as mock_mod:
            mock_mod.from_openai.return_value = mock_instructor

            svc = KeyframeAnalysisService(openai_client=mock_client)
            result = await svc.analyze_keyframes(
                keyframes=_make_keyframes(3),
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_rep_metrics(3),
            )

        assert isinstance(result, KeyframeAnalysisResult)
        assert len(result.per_rep) == 3
        assert result.overall_notes

    @pytest.mark.asyncio
    async def test_analyze_sends_image_content(self) -> None:
        """Verify user message contains image_url blocks."""
        mock_client = MagicMock()
        expected = _make_analysis_result(2)

        captured_kwargs: dict[str, Any] = {}

        async def capture_create(**kwargs: Any) -> KeyframeAnalysisResult:
            captured_kwargs.update(kwargs)
            return expected

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = capture_create

        with patch("app.services.keyframe_analysis.instructor") as mock_mod:
            mock_mod.from_openai.return_value = mock_instructor

            svc = KeyframeAnalysisService(openai_client=mock_client)
            await svc.analyze_keyframes(
                keyframes=_make_keyframes(2),
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_rep_metrics(2),
            )

        messages = captured_kwargs["messages"]
        user_msg = messages[1]
        assert user_msg["role"] == "user"

        image_blocks = [
            c for c in user_msg["content"] if c.get("type") == "image_url"
        ]
        assert len(image_blocks) == 6  # 2 reps × 3 images

    @pytest.mark.asyncio
    async def test_empty_keyframes_returns_empty_result(self) -> None:
        """No keyframes → empty result without calling API."""
        mock_client = MagicMock()

        mock_instructor = AsyncMock()

        with patch("app.services.keyframe_analysis.instructor") as mock_mod:
            mock_mod.from_openai.return_value = mock_instructor

            svc = KeyframeAnalysisService(openai_client=mock_client)
            result = await svc.analyze_keyframes(
                keyframes=[],
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=[],
            )

        assert result.per_rep == []
        # Should NOT have called the API
        mock_instructor.chat.completions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_client_raises_value_error(self) -> None:
        svc = KeyframeAnalysisService(openai_client=None)
        with pytest.raises(ValueError):
            await svc.analyze_keyframes(
                keyframes=_make_keyframes(1),
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_rep_metrics(1),
            )

    @pytest.mark.asyncio
    async def test_429_retries_with_backoff(self) -> None:
        """429 rate limit → retries 3 times then raises."""
        import openai

        mock_client = MagicMock()

        rate_limit_error = openai.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}},
        )

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(
            side_effect=rate_limit_error
        )

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("app.services.keyframe_analysis.instructor") as mock_mod:
            mock_mod.from_openai.return_value = mock_instructor
            with patch(
                "app.services.keyframe_analysis.asyncio.sleep",
                side_effect=mock_sleep,
            ):
                svc = KeyframeAnalysisService(openai_client=mock_client)
                with pytest.raises(openai.RateLimitError):
                    await svc.analyze_keyframes(
                        keyframes=_make_keyframes(1),
                        exercise_type="squat",
                        exercise_variant="high_bar",
                        rep_metrics=_make_rep_metrics(1),
                    )

        assert sleep_calls == [1.0, 2.0, 4.0]
        assert mock_instructor.chat.completions.create.call_count == 4

    @pytest.mark.asyncio
    async def test_401_fails_immediately(self) -> None:
        """401 auth error → no retries."""
        import openai

        mock_client = MagicMock()

        auth_error = openai.AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body={"error": {"message": "Invalid API key"}},
        )

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(
            side_effect=auth_error
        )

        sleep_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal sleep_count
            sleep_count += 1

        with patch("app.services.keyframe_analysis.instructor") as mock_mod:
            mock_mod.from_openai.return_value = mock_instructor
            with patch(
                "app.services.keyframe_analysis.asyncio.sleep",
                side_effect=mock_sleep,
            ):
                svc = KeyframeAnalysisService(openai_client=mock_client)
                with pytest.raises(openai.AuthenticationError):
                    await svc.analyze_keyframes(
                        keyframes=_make_keyframes(1),
                        exercise_type="squat",
                        exercise_variant="high_bar",
                        rep_metrics=_make_rep_metrics(1),
                    )

        assert sleep_count == 0
        assert mock_instructor.chat.completions.create.call_count == 1
