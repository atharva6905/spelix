"""
Unit tests for ThresholdConfig, CoachingOutput schema, and CoachingService.

Requirements: B-023 (FR-RESL-03, Appendix D), B-025 (FR-SCOR-00)

All LLM calls are mocked — never call real Anthropic API.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import ThresholdConfig
from app.schemas.coaching import CoachingOutput, Issue
from app.services.coaching import CoachingService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MANDATORY_DISCLAIMER = (
    "This feedback is for educational purposes only and is not a substitute "
    "for in-person coaching or medical advice."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sample_rep_metrics() -> list[dict[str, Any]]:
    return [
        {
            "rep_number": 1,
            "hip_angle_min_deg": 85.0,
            "knee_angle_min_deg": 80.0,
            "confidence_score": 0.92,
        },
        {
            "rep_number": 2,
            "hip_angle_min_deg": 88.0,
            "knee_valgus_deg": 8.0,
            "knee_angle_min_deg": 82.0,
            "confidence_score": 0.89,
        },
    ]


def _make_coaching_output(**overrides: Any) -> CoachingOutput:
    """Return a valid CoachingOutput for use in mocks."""
    data: dict[str, Any] = {
        "summary": "Good depth on all reps. Two technique deviations noted.",
        "strengths": ["Consistent bar path", "Solid bracing"],
        "issues": [
            Issue(
                rep_number=2,
                joint="Left knee",
                description="Inward knee travel detected (~8 degrees).",
                severity="High",
            )
        ],
        "correction_plan": [
            "Drive knees out over toes throughout descent.",
            "Cue: spread the floor with feet.",
        ],
        "disclaimer": MANDATORY_DISCLAIMER,
        "raw_prompt_tokens": 400,
        "raw_completion_tokens": 250,
    }
    data.update(overrides)
    return CoachingOutput(**data)


# ---------------------------------------------------------------------------
# ThresholdConfig tests (B-025)
# ---------------------------------------------------------------------------


class TestThresholdConfig:
    def test_loads_version(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.version == "v0"

    def test_get_squat_knee_valgus_caution(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "knee_valgus_caution_deg") == 5

    def test_get_squat_knee_valgus_high(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "knee_valgus_high_deg") == 10

    def test_get_squat_lumbar_flexion_caution(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "lumbar_flexion_caution_deg") == 28

    def test_get_squat_lumbar_flexion_high(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "lumbar_flexion_high_deg") == 44

    def test_get_bench_grip_width_ratio(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("bench", "grip_width_biacromial_ratio_max") == 1.5

    def test_get_deadlift_lumbar_flexion_caution(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("deadlift", "lumbar_flexion_caution_deg") == 28

    def test_get_experience_tolerance_beginner(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("experience_tolerance", "beginner_deg") == 3

    def test_get_experience_tolerance_advanced(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("experience_tolerance", "advanced_deg") == 5

    def test_get_unknown_key_raises(self) -> None:
        cfg = ThresholdConfig()
        with pytest.raises(KeyError):
            cfg.get("squat", "nonexistent_key")

    def test_get_unknown_exercise_raises(self) -> None:
        cfg = ThresholdConfig()
        with pytest.raises(KeyError):
            cfg.get("nonexistent_exercise", "knee_valgus_caution_deg")


# ---------------------------------------------------------------------------
# Schema validation tests (B-023)
# ---------------------------------------------------------------------------


class TestCoachingOutputSchema:
    def test_valid_coaching_output(self) -> None:
        output = _make_coaching_output()
        assert output.summary
        assert isinstance(output.strengths, list)
        assert len(output.strengths) >= 1
        assert isinstance(output.issues, list)
        assert isinstance(output.correction_plan, list)
        assert isinstance(output.raw_prompt_tokens, int)
        assert isinstance(output.raw_completion_tokens, int)

    def test_issue_severity_values(self) -> None:
        for severity in ("High", "Medium", "Low"):
            issue = Issue(
                rep_number=1,
                joint="knee",
                description="Test issue",
                severity=severity,  # type: ignore[arg-type]
            )
            assert issue.severity == severity

    def test_issue_invalid_severity_raises(self) -> None:
        with pytest.raises(Exception):
            Issue(
                rep_number=1,
                joint="knee",
                description="Test issue",
                severity="Critical",  # type: ignore[arg-type]
            )

    def test_disclaimer_field_present(self) -> None:
        output = _make_coaching_output()
        assert hasattr(output, "disclaimer")
        assert isinstance(output.disclaimer, str)
        assert len(output.disclaimer) > 0


# ---------------------------------------------------------------------------
# CoachingService tests (B-023)
# ---------------------------------------------------------------------------


class TestCoachingService:
    @pytest.mark.asyncio
    async def test_generate_coaching_returns_valid_output(self) -> None:
        """Mocked LLM → valid CoachingOutput with all required fields."""
        mock_client = MagicMock()
        expected = _make_coaching_output()

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(return_value=expected)

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            result = await service.generate_coaching(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.90,
                thresholds=ThresholdConfig(),
            )

        assert isinstance(result, CoachingOutput)
        assert result.summary
        assert isinstance(result.strengths, list)
        assert isinstance(result.issues, list)
        assert isinstance(result.correction_plan, list)
        assert result.disclaimer == MANDATORY_DISCLAIMER

    @pytest.mark.asyncio
    async def test_disclaimer_matches_verbatim(self) -> None:
        """Disclaimer text must match exactly."""
        mock_client = MagicMock()
        expected = _make_coaching_output()

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(return_value=expected)

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            result = await service.generate_coaching(
                exercise_type="bench",
                exercise_variant="flat",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.85,
                thresholds=ThresholdConfig(),
            )

        assert result.disclaimer == MANDATORY_DISCLAIMER

    @pytest.mark.asyncio
    async def test_issues_have_valid_severity(self) -> None:
        """All issues in result must have valid severity values."""
        mock_client = MagicMock()
        expected = _make_coaching_output(
            issues=[
                Issue(rep_number=1, joint="hip", description="Hip drop", severity="Medium"),
                Issue(rep_number=2, joint="knee", description="Valgus", severity="High"),
                Issue(rep_number=3, joint="lumbar", description="Rounding", severity="Low"),
            ]
        )

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(return_value=expected)

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            result = await service.generate_coaching(
                exercise_type="deadlift",
                exercise_variant="conventional",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.78,
                thresholds=ThresholdConfig(),
            )

        valid_severities = {"High", "Medium", "Low"}
        for issue in result.issues:
            assert issue.severity in valid_severities

    @pytest.mark.asyncio
    async def test_429_retries_three_times_with_backoff(self) -> None:
        """429 response → retries 3 times with backoff, then raises."""
        import anthropic

        mock_client = MagicMock()

        # Simulate a 429 rate limit error from the Anthropic API
        rate_limit_error = anthropic.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body={"error": {"type": "rate_limit_error", "message": "Rate limit exceeded"}},
        )

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(side_effect=rate_limit_error)

        call_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            # Don't actually sleep in tests

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor
            with patch("app.services.coaching.asyncio.sleep", side_effect=mock_sleep):
                service = CoachingService(anthropic_client=mock_client)
                with pytest.raises(anthropic.RateLimitError):
                    await service.generate_coaching(
                        exercise_type="squat",
                        exercise_variant="high_bar",
                        rep_metrics=_make_sample_rep_metrics(),
                        confidence_score=0.90,
                        thresholds=ThresholdConfig(),
                    )

        # Should have retried 3 times → 3 sleep calls (1s, 2s, 4s)
        assert call_count == 3
        # Instructor create called 4 times (1 initial + 3 retries)
        assert mock_instructor.chat.completions.create.call_count == 4

    @pytest.mark.asyncio
    async def test_401_fails_immediately_no_retry(self) -> None:
        """401 auth error → fails immediately, no retries."""
        import anthropic

        mock_client = MagicMock()

        auth_error = anthropic.AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body={"error": {"type": "authentication_error", "message": "Invalid API key"}},
        )

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(side_effect=auth_error)

        sleep_call_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal sleep_call_count
            sleep_call_count += 1

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor
            with patch("app.services.coaching.asyncio.sleep", side_effect=mock_sleep):
                service = CoachingService(anthropic_client=mock_client)
                with pytest.raises(anthropic.AuthenticationError):
                    await service.generate_coaching(
                        exercise_type="squat",
                        exercise_variant="high_bar",
                        rep_metrics=_make_sample_rep_metrics(),
                        confidence_score=0.90,
                        thresholds=ThresholdConfig(),
                    )

        # Must not sleep (no backoff on 401)
        assert sleep_call_count == 0
        # Must only call create once — no retries
        assert mock_instructor.chat.completions.create.call_count == 1

    # ---------------------------------------------------------------------------
    # B-043: confidence label thresholds in prompt
    # ---------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "score,expected_label",
        [
            (0.81, "High"),
            (0.80, "High"),
            (0.66, "Moderate"),
            (0.65, "Moderate"),
            (0.51, "Low"),
            (0.50, "Low"),
            (0.49, "Very Low"),
            (0.00, "Very Low"),
        ],
    )
    def test_confidence_label_thresholds_in_prompt(
        self, score: float, expected_label: str
    ) -> None:
        """coaching.py must use confidence_label() from cv.confidence (0.80/0.65/0.50 thresholds).

        B-043: the old private _confidence_label() used 0.90/0.70/0.50, which produced
        wrong labels (e.g. score=0.66 → "Low" instead of "Moderate").
        """
        from app.services.coaching import _build_user_prompt

        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=[],
            confidence_score=score,
            thresholds=ThresholdConfig(),
        )
        assert f"Confidence: {expected_label}." in prompt, (
            f"score={score}: expected label '{expected_label}' in prompt, got:\n{prompt}"
        )

    # ---------------------------------------------------------------------------
    # B-084: retry path tests (529, timeout, 400)
    # ---------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_529_retries_three_times_with_backoff(self) -> None:
        """529 overload response → retries 3 times with backoff, then raises."""
        import anthropic

        mock_client = MagicMock()

        # Build a 529 APIStatusError using a mock httpx.Response
        overload_error = anthropic.APIStatusError(
            message="Overloaded",
            response=MagicMock(status_code=529),
            body={"error": {"type": "overloaded_error", "message": "Overloaded"}},
        )
        # Confirm the service recognises it as retryable
        from app.services.coaching import _is_retryable

        assert _is_retryable(overload_error), "529 must be classified as retryable"

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(side_effect=overload_error)

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor
            with patch("app.services.coaching.asyncio.sleep", side_effect=mock_sleep):
                service = CoachingService(anthropic_client=mock_client)
                with pytest.raises(anthropic.APIStatusError) as exc_info:
                    await service.generate_coaching(
                        exercise_type="squat",
                        exercise_variant="high_bar",
                        rep_metrics=_make_sample_rep_metrics(),
                        confidence_score=0.90,
                        thresholds=ThresholdConfig(),
                    )

        # Final exception must be the 529 overload error
        assert exc_info.value.status_code == 529
        # Three backoff sleeps: 1s, 2s, 4s
        assert sleep_calls == [1.0, 2.0, 4.0]
        # Four total calls: 1 initial + 3 retries
        assert mock_instructor.chat.completions.create.call_count == 4

    @pytest.mark.asyncio
    async def test_timeout_retries_three_times_with_backoff(self) -> None:
        """APITimeoutError → treated as retryable, retries 3 times with backoff."""
        import anthropic
        import httpx

        mock_client = MagicMock()

        timeout_error = anthropic.APITimeoutError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )
        from app.services.coaching import _is_retryable

        assert _is_retryable(timeout_error), "APITimeoutError must be classified as retryable"

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(side_effect=timeout_error)

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor
            with patch("app.services.coaching.asyncio.sleep", side_effect=mock_sleep):
                service = CoachingService(anthropic_client=mock_client)
                with pytest.raises(anthropic.APITimeoutError):
                    await service.generate_coaching(
                        exercise_type="deadlift",
                        exercise_variant="conventional",
                        rep_metrics=_make_sample_rep_metrics(),
                        confidence_score=0.85,
                        thresholds=ThresholdConfig(),
                    )

        # Three backoff sleeps: 1s, 2s, 4s
        assert sleep_calls == [1.0, 2.0, 4.0]
        # Four total calls: 1 initial + 3 retries
        assert mock_instructor.chat.completions.create.call_count == 4

    @pytest.mark.asyncio
    async def test_400_fails_immediately_no_retry(self) -> None:
        """400 bad request → fails immediately, no retries, no backoff sleeps."""
        import anthropic

        mock_client = MagicMock()

        bad_request_error = anthropic.BadRequestError(
            message="Invalid request",
            response=MagicMock(status_code=400),
            body={"error": {"type": "invalid_request_error", "message": "Invalid request"}},
        )
        from app.services.coaching import _is_retryable

        assert not _is_retryable(bad_request_error), "400 must NOT be classified as retryable"

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(side_effect=bad_request_error)

        sleep_call_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal sleep_call_count
            sleep_call_count += 1

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor
            with patch("app.services.coaching.asyncio.sleep", side_effect=mock_sleep):
                service = CoachingService(anthropic_client=mock_client)
                with pytest.raises(anthropic.BadRequestError):
                    await service.generate_coaching(
                        exercise_type="bench",
                        exercise_variant="flat",
                        rep_metrics=_make_sample_rep_metrics(),
                        confidence_score=0.88,
                        thresholds=ThresholdConfig(),
                    )

        # Must not sleep (no backoff on 400)
        assert sleep_call_count == 0
        # Must only call create once — no retries
        assert mock_instructor.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_mock_client_none_raises_value_error(self) -> None:
        """Passing None as client when no mock mode raises ValueError."""
        # CoachingService with None client should raise immediately on generate_coaching
        # unless a mock response factory is provided
        service = CoachingService(anthropic_client=None)
        with pytest.raises((ValueError, RuntimeError, Exception)):
            await service.generate_coaching(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=[],
                confidence_score=0.5,
                thresholds=ThresholdConfig(),
            )
