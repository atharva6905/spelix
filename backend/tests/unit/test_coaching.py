"""
Unit tests for ThresholdConfig, CoachingOutput schema, and CoachingService.

Requirements: B-023 (FR-RESL-03, Appendix D), B-025 (FR-SCOR-00),
              FR-AICP-03, FR-AICP-04, FR-AICP-05, FR-AICP-06, FR-AICP-07

All LLM calls are mocked — never call real Anthropic API.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import ThresholdConfig
from app.schemas.coaching import CoachingOutput, Issue
from app.services.coaching import (
    CoachingService,
    _build_user_prompt,
)

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
    """Tests for ThresholdConfig v1 (default) and v0 backward compat."""

    def test_loads_v1_version(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.version == "v1"

    def test_get_squat_knee_valgus_caution(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "knee_valgus_caution_deg") == 5.0

    def test_get_squat_knee_valgus_high(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "knee_valgus_high_deg") == 10.0

    def test_get_squat_lumbar_flexion_caution(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "lumbar_flexion_caution_deg") == 28.0

    def test_get_squat_lumbar_flexion_high(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "lumbar_flexion_high_deg") == 44.0

    def test_get_bench_grip_width_ratio(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("bench", "grip_width_biacromial_ratio_max") == 1.5

    def test_get_deadlift_lumbar_flexion_caution(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("deadlift", "lumbar_flexion_caution_deg") == 28.0

    def test_get_experience_tolerance_beginner(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("experience_tolerance", "beginner_deg") == 3.0

    def test_get_experience_tolerance_advanced(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("experience_tolerance", "advanced_deg") == 5.0

    def test_get_unknown_key_raises(self) -> None:
        cfg = ThresholdConfig()
        with pytest.raises(KeyError):
            cfg.get("squat", "nonexistent_key")

    def test_get_unknown_exercise_raises(self) -> None:
        cfg = ThresholdConfig()
        with pytest.raises(KeyError):
            cfg.get("nonexistent_exercise", "knee_valgus_caution_deg")

    # --- v1-specific: nested object unwrapping ---

    def test_v1_get_unwraps_nested_value(self) -> None:
        """v1 thresholds are {value, unit, ...} objects; get() returns just the value."""
        cfg = ThresholdConfig()
        raw = cfg.get_raw("squat", "knee_valgus_caution_deg")
        assert isinstance(raw, dict)
        assert raw["value"] == 5.0
        assert cfg.get("squat", "knee_valgus_caution_deg") == 5.0

    def test_v1_get_citation(self) -> None:
        """get_citation() returns provenance string for nested thresholds."""
        cfg = ThresholdConfig()
        citation = cfg.get_citation("squat", "knee_valgus_caution_deg")
        assert citation == "Myer et al. 2010"

    def test_v1_get_citation_returns_none_for_flat_value(self) -> None:
        """get_citation() returns None for non-nested values (e.g. scoring_weights)."""
        cfg = ThresholdConfig()
        citation = cfg.get_citation("scoring_weights", "movement_quality")
        assert citation is None

    def test_v1_scoring_weights(self) -> None:
        """FR-SCOR-05: scoring weights accessible via get()."""
        cfg = ThresholdConfig()
        assert cfg.get("scoring_weights", "movement_quality") == 0.40
        assert cfg.get("scoring_weights", "technique") == 0.30
        assert cfg.get("scoring_weights", "path_balance") == 0.20
        assert cfg.get("scoring_weights", "control") == 0.10

    def test_v1_score_descriptors(self) -> None:
        """FR-SCOR-07: score descriptor boundaries."""
        cfg = ThresholdConfig()
        assert cfg.get("score_descriptors", "elite_min") == 9.0
        assert cfg.get("score_descriptors", "advanced_min") == 7.5
        assert cfg.get("score_descriptors", "intermediate_min") == 5.0
        assert cfg.get("score_descriptors", "needs_work_min") == 3.0

    def test_v1_phase_multipliers(self) -> None:
        """FR-CVPL-23: phase multipliers for Tier 4 confidence."""
        cfg = ThresholdConfig()
        assert cfg.get("phase_multipliers", "static_peak") == 1.0
        assert cfg.get("phase_multipliers", "transition") == 0.90

    def test_v1_confidence_landmark_weights(self) -> None:
        """FR-CVPL-22: exercise-specific landmark weights for Tier 3."""
        cfg = ThresholdConfig()
        squat_weights = cfg.get_section("confidence_landmark_weights")["squat"]
        assert squat_weights["23"] == 1.0
        assert squat_weights["11"] == 0.5

    def test_v1_all_for_exercise_alias(self) -> None:
        """all_for_exercise() is backward-compat alias for get_section()."""
        cfg = ThresholdConfig()
        section = cfg.all_for_exercise("squat")
        assert "knee_valgus_caution_deg" in section

    # --- v0 backward compat ---

    def test_v0_still_loads(self) -> None:
        """v0 config still works when explicitly loaded."""
        from pathlib import Path

        v0_path = Path(__file__).parent.parent.parent / "config" / "thresholds_v0.json"
        if not v0_path.exists():
            pytest.skip("thresholds_v0.json not present")
        cfg = ThresholdConfig(path=v0_path)
        assert cfg.version == "v0"
        assert cfg.get("squat", "knee_valgus_caution_deg") == 5

    def test_v0_get_citation_returns_none(self) -> None:
        """v0 flat values have no provenance — get_citation() returns None."""
        from pathlib import Path

        v0_path = Path(__file__).parent.parent.parent / "config" / "thresholds_v0.json"
        if not v0_path.exists():
            pytest.skip("thresholds_v0.json not present")
        cfg = ThresholdConfig(path=v0_path)
        assert cfg.get_citation("squat", "knee_valgus_caution_deg") is None


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
    # Phase 1 schema tests (FR-AICP-03, FR-AICP-06)
    # ---------------------------------------------------------------------------

    def test_coaching_output_v1_backward_compat(self) -> None:
        """Phase 0 JSONB blobs (no Phase 1 fields) must still deserialise."""
        phase0_dict: dict[str, Any] = {
            "summary": "Good session.",
            "strengths": ["Solid depth"],
            "issues": [],
            "correction_plan": ["Keep knees tracking over toes."],
            "disclaimer": MANDATORY_DISCLAIMER,
            "raw_prompt_tokens": 300,
            "raw_completion_tokens": 180,
        }
        output = CoachingOutput.model_validate(phase0_dict)

        assert output.summary == "Good session."
        assert output.raw_prompt_tokens == 300
        assert output.recommended_cues == []
        assert output.citations == []
        assert output.confidence_level is None
        assert output.safety_warnings == []
        assert output.dimension_addressed is None

    def test_citation_schema_valid(self) -> None:
        """Citation model round-trips through Pydantic validation."""
        from app.schemas.coaching import Citation

        citation = Citation(
            title="Knee valgus during the squat: a biomechanical review",
            authors=["Smith, J.", "Jones, A."],
            year=2021,
            doi="10.1016/j.jbiomech.2021.110001",
        )
        assert citation.title.startswith("Knee")
        assert citation.year == 2021
        assert citation.doi is not None

        no_doi = Citation(
            title="Barbell deadlift mechanics",
            authors=["Brown, K."],
            year=2019,
        )
        assert no_doi.doi is None

    def test_coaching_output_dimension_literal_values(self) -> None:
        """dimension_addressed accepts only the 4 defined values plus None."""
        valid_values = [
            "Movement Quality",
            "Technique",
            "Path & Balance",
            "Control",
            None,
        ]
        for val in valid_values:
            output = _make_coaching_output(dimension_addressed=val)
            assert output.dimension_addressed == val

        with pytest.raises(Exception):
            _make_coaching_output(dimension_addressed="Injury Prevention")  # type: ignore[arg-type]


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
        service = CoachingService(anthropic_client=None)
        with pytest.raises((ValueError, RuntimeError, Exception)):
            await service.generate_coaching(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=[],
                confidence_score=0.5,
                thresholds=ThresholdConfig(),
            )

    # ---------------------------------------------------------------------------
    # Phase 1 prompt tests (FR-AICP-04, FR-AICP-05)
    # ---------------------------------------------------------------------------

    def test_body_stats_in_prompt(self) -> None:
        """When body_stats is provided, prompt must contain 'Athlete Profile' section."""
        body_stats = {"height_cm": 180, "weight_kg": 85, "femur_tibia_ratio": 1.1}
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            body_stats=body_stats,
        )
        assert "Athlete Profile" in prompt
        assert "180" in prompt

    def test_body_stats_includes_anthropometrics(self) -> None:
        """FR-PROF-06: arm_span_cm and femur_length_cm must appear in prompt when provided."""
        body_stats = {
            "height_cm": 180,
            "weight_kg": 85,
            "arm_span_cm": 183.5,
            "femur_length_cm": 47.2,
        }
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            body_stats=body_stats,
        )
        assert "arm_span_cm" in prompt
        assert "183.5" in prompt
        assert "femur_length_cm" in prompt
        assert "47.2" in prompt

    def test_body_stats_fallback(self) -> None:
        """When body_stats is None, prompt must apply general population standards."""
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            body_stats=None,
        )
        assert "general population" in prompt
        assert "Athlete Profile" not in prompt

    def test_keyframe_analysis_in_prompt(self) -> None:
        """When keyframe_analysis_text is provided, it must appear in the prompt."""
        keyframe_text = "Lifter shows forward lean exceeding 45 degrees at bottom position."
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            keyframe_analysis_text=keyframe_text,
        )
        assert "Visual Analysis" in prompt
        assert keyframe_text in prompt

    def test_keyframe_analysis_absent_when_none(self) -> None:
        """When keyframe_analysis_text is None, 'Visual Analysis' must not appear."""
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            keyframe_analysis_text=None,
        )
        assert "Visual Analysis" not in prompt

    def test_system_prompt_priority_order(self) -> None:
        """System prompt must enforce Movement Quality → Technique → Path → Control order."""
        from app.services.coaching import _build_system_prompt

        prompt = _build_system_prompt()
        mq_pos = prompt.index("Movement Quality")
        tech_pos = prompt.index("Technique")
        path_pos = prompt.index("Path")
        ctrl_pos = prompt.index("Control")
        assert mq_pos < tech_pos < path_pos < ctrl_pos

    def test_system_prompt_no_injury_risk(self) -> None:
        """System prompt must never contain banned language."""
        from app.services.coaching import _build_system_prompt

        prompt = _build_system_prompt()
        banned = ["injury risk", "injury prevention"]
        for phrase in banned:
            assert phrase not in prompt.lower()

    @pytest.mark.asyncio
    async def test_generate_coaching_passes_new_params(self) -> None:
        """generate_coaching must pass body_stats and keyframe_analysis_text to prompt."""
        mock_client = MagicMock()
        expected = _make_coaching_output()

        captured_messages: list[Any] = []

        async def capture_create(**kwargs: Any) -> CoachingOutput:
            captured_messages.extend(kwargs.get("messages", []))
            return expected

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = capture_create

        body_stats = {"height_cm": 175, "weight_kg": 80}
        keyframe_text = "Bar path drifts forward during ascent."

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            result = await service.generate_coaching(
                exercise_type="deadlift",
                exercise_variant="conventional",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.82,
                thresholds=ThresholdConfig(),
                body_stats=body_stats,
                keyframe_analysis_text=keyframe_text,
            )

        assert isinstance(result, CoachingOutput)
        assert len(captured_messages) == 1
        user_content: str = captured_messages[0]["content"]
        assert "Athlete Profile" in user_content
        assert "Visual Analysis" in user_content
        assert keyframe_text in user_content


# ---------------------------------------------------------------------------
# D-001: Native instructor streaming tests (FR-AICP-07)
# Replace stream-then-reparse with instructor create_partial (ADR-021)
# ---------------------------------------------------------------------------


class TestGenerateCoachingStreamingNative:
    """FR-AICP-07: generate_coaching_streaming uses instructor create_partial.

    These tests verify:
    - Native streaming produces a valid CoachingOutput without a second LLM call.
    - Redis pub/sub chunks are published during streaming.
    - Done sentinel is published after stream completes.
    - Retry logic still works for retryable errors.
    - Token usage is not double-counted (raw_client not used for a second parse).
    """

    @pytest.mark.asyncio
    async def test_streaming_returns_valid_coaching_output(self) -> None:
        """create_partial yields final CoachingOutput — no second instructor call."""
        mock_client = MagicMock()
        expected = _make_coaching_output()

        # Simulate create_partial yielding two partial snapshots and a final complete one
        async def mock_create_partial(**kwargs: Any) -> Any:
            # Yield a couple of intermediate partials then the final result
            partial1 = _make_coaching_output(summary="Good depth...")
            partial2 = expected
            for item in [partial1, partial2]:
                yield item

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            result = await service.generate_coaching_streaming(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.90,
                thresholds=ThresholdConfig(),
                pubsub_redis=None,
            )

        assert isinstance(result, CoachingOutput)
        assert result.summary == expected.summary
        assert result.disclaimer == MANDATORY_DISCLAIMER

    @pytest.mark.asyncio
    async def test_streaming_no_second_llm_call(self) -> None:
        """Verify only create_partial is called — create (the reparse call) is NOT called."""
        mock_client = MagicMock()
        expected = _make_coaching_output()
        create_call_count = 0

        async def mock_create_partial(**kwargs: Any) -> Any:
            yield expected

        async def mock_create(**kwargs: Any) -> CoachingOutput:
            nonlocal create_call_count
            create_call_count += 1
            return expected

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial
        mock_instructor.chat.completions.create = mock_create

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            await service.generate_coaching_streaming(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.90,
                thresholds=ThresholdConfig(),
                pubsub_redis=None,
            )

        # The old reparse call must NOT happen
        assert create_call_count == 0, (
            "generate_coaching_streaming made a second LLM call (reparse). "
            "This doubles token cost and must be eliminated."
        )

    @pytest.mark.asyncio
    async def test_streaming_publishes_chunks_to_redis(self) -> None:
        """Redis pub/sub receives chunk messages during streaming."""
        mock_client = MagicMock()
        expected = _make_coaching_output()
        published_messages: list[dict[str, Any]] = []

        async def mock_create_partial(**kwargs: Any) -> Any:
            partial1 = _make_coaching_output(summary="Good depth on all reps.")
            yield partial1
            yield expected

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial

        mock_redis = AsyncMock()

        async def capture_publish(channel: str, message: str) -> None:
            published_messages.append(json.loads(message))

        mock_redis.publish = capture_publish

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            await service.generate_coaching_streaming(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.90,
                thresholds=ThresholdConfig(),
                analysis_id="test-analysis-123",
                pubsub_redis=mock_redis,
            )

        # Must have published at least one chunk
        chunk_messages = [m for m in published_messages if m.get("type") == "chunk"]
        assert len(chunk_messages) >= 1, "No chunk messages published to Redis"
        # Every chunk must have a 'text' key
        for msg in chunk_messages:
            assert "text" in msg, f"Chunk message missing 'text' key: {msg}"

    @pytest.mark.asyncio
    async def test_streaming_publishes_done_sentinel(self) -> None:
        """Redis pub/sub receives done sentinel after stream completes."""
        mock_client = MagicMock()
        expected = _make_coaching_output()
        published_messages: list[dict[str, Any]] = []

        async def mock_create_partial(**kwargs: Any) -> Any:
            yield expected

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial

        mock_redis = AsyncMock()

        async def capture_publish(channel: str, message: str) -> None:
            published_messages.append(json.loads(message))

        mock_redis.publish = capture_publish

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            await service.generate_coaching_streaming(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.90,
                thresholds=ThresholdConfig(),
                analysis_id="test-analysis-456",
                pubsub_redis=mock_redis,
            )

        done_messages = [m for m in published_messages if m.get("type") == "done"]
        assert len(done_messages) == 1, "Done sentinel not published (or published more than once)"

    @pytest.mark.asyncio
    async def test_streaming_publishes_to_correct_channel(self) -> None:
        """Chunks and sentinel are published to coaching:{analysis_id} channel."""
        mock_client = MagicMock()
        expected = _make_coaching_output()
        published_channels: list[str] = []

        async def mock_create_partial(**kwargs: Any) -> Any:
            yield expected

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial

        mock_redis = AsyncMock()

        async def capture_publish(channel: str, message: str) -> None:
            published_channels.append(channel)

        mock_redis.publish = capture_publish

        analysis_id = "abc-789"

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            await service.generate_coaching_streaming(
                exercise_type="bench",
                exercise_variant="flat",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.85,
                thresholds=ThresholdConfig(),
                analysis_id=analysis_id,
                pubsub_redis=mock_redis,
            )

        expected_channel = f"coaching:{analysis_id}"
        assert all(ch == expected_channel for ch in published_channels), (
            f"Messages published to wrong channels: {set(published_channels)}"
        )

    @pytest.mark.asyncio
    async def test_streaming_skips_redis_when_pubsub_none(self) -> None:
        """When pubsub_redis=None, no Redis calls are made."""
        mock_client = MagicMock()
        expected = _make_coaching_output()

        async def mock_create_partial(**kwargs: Any) -> Any:
            yield expected

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            # Must not raise even without Redis
            result = await service.generate_coaching_streaming(
                exercise_type="deadlift",
                exercise_variant="conventional",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.80,
                thresholds=ThresholdConfig(),
                pubsub_redis=None,
            )

        assert isinstance(result, CoachingOutput)

    @pytest.mark.asyncio
    async def test_streaming_retry_on_529(self) -> None:
        """529 overload during streaming → retries with backoff, then raises."""
        import anthropic

        mock_client = MagicMock()
        overload_error = anthropic.APIStatusError(
            message="Overloaded",
            response=MagicMock(status_code=529),
            body={"error": {"type": "overloaded_error", "message": "Overloaded"}},
        )

        call_count = 0

        async def mock_create_partial_fail(**kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            raise overload_error
            yield  # make it an async generator

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial_fail

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor
            with patch("app.services.coaching.asyncio.sleep", side_effect=mock_sleep):
                service = CoachingService(anthropic_client=mock_client)
                with pytest.raises(anthropic.APIStatusError) as exc_info:
                    await service.generate_coaching_streaming(
                        exercise_type="squat",
                        exercise_variant="high_bar",
                        rep_metrics=_make_sample_rep_metrics(),
                        confidence_score=0.90,
                        thresholds=ThresholdConfig(),
                        pubsub_redis=None,
                    )

        assert exc_info.value.status_code == 529
        assert sleep_calls == [1.0, 2.0, 4.0]
        assert call_count == 4  # 1 initial + 3 retries

    @pytest.mark.asyncio
    async def test_streaming_retry_on_timeout(self) -> None:
        """APITimeoutError during streaming → retries with backoff."""
        import anthropic
        import httpx

        mock_client = MagicMock()
        timeout_error = anthropic.APITimeoutError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )

        async def mock_create_partial_timeout(**kwargs: Any) -> Any:
            raise timeout_error
            yield

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial_timeout

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor
            with patch("app.services.coaching.asyncio.sleep", side_effect=mock_sleep):
                service = CoachingService(anthropic_client=mock_client)
                with pytest.raises(anthropic.APITimeoutError):
                    await service.generate_coaching_streaming(
                        exercise_type="deadlift",
                        exercise_variant="conventional",
                        rep_metrics=_make_sample_rep_metrics(),
                        confidence_score=0.85,
                        thresholds=ThresholdConfig(),
                        pubsub_redis=None,
                    )

        assert sleep_calls == [1.0, 2.0, 4.0]

    @pytest.mark.asyncio
    async def test_streaming_401_fails_immediately(self) -> None:
        """401 auth error during streaming → fails immediately, no retries."""
        import anthropic

        mock_client = MagicMock()
        auth_error = anthropic.AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body={"error": {"type": "authentication_error", "message": "Invalid API key"}},
        )

        async def mock_create_partial_auth_fail(**kwargs: Any) -> Any:
            raise auth_error
            yield

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial_auth_fail

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor
            with patch("app.services.coaching.asyncio.sleep", side_effect=mock_sleep):
                service = CoachingService(anthropic_client=mock_client)
                with pytest.raises(anthropic.AuthenticationError):
                    await service.generate_coaching_streaming(
                        exercise_type="squat",
                        exercise_variant="high_bar",
                        rep_metrics=_make_sample_rep_metrics(),
                        confidence_score=0.90,
                        thresholds=ThresholdConfig(),
                        pubsub_redis=None,
                    )

        # Zero backoff sleeps on 401
        assert sleep_calls == []

    @pytest.mark.asyncio
    async def test_streaming_uses_cache_control_on_system_prompt(self) -> None:
        """FR-AICP-21: create_partial must be called with cache_control on system prompt."""
        mock_client = MagicMock()
        expected = _make_coaching_output()
        captured_kwargs: dict[str, Any] = {}

        async def mock_create_partial(**kwargs: Any) -> Any:
            captured_kwargs.update(kwargs)
            yield expected

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            await service.generate_coaching_streaming(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.90,
                thresholds=ThresholdConfig(),
                pubsub_redis=None,
            )

        system = captured_kwargs.get("system")
        assert system is not None, "system prompt not passed to create_partial"
        # Must be a list (Anthropic cache_control format)
        assert isinstance(system, list), (
            "system must be a list with cache_control, not a plain string"
        )
        assert len(system) == 1
        block = system[0]
        assert block.get("type") == "text"
        assert "cache_control" in block, "cache_control missing from system prompt block"
        assert block["cache_control"]["type"] == "ephemeral"

    @pytest.mark.asyncio
    async def test_streaming_output_no_injury_language(self) -> None:
        """Coaching output must never contain banned injury language."""
        mock_client = MagicMock()
        expected = _make_coaching_output()

        async def mock_create_partial(**kwargs: Any) -> Any:
            yield expected

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            result = await service.generate_coaching_streaming(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.90,
                thresholds=ThresholdConfig(),
                pubsub_redis=None,
            )

        output_text = result.model_dump_json().lower()
        banned_phrases = ["injury risk", "injury prevention"]
        for phrase in banned_phrases:
            assert phrase not in output_text, (
                f"Banned phrase '{phrase}' found in coaching output"
            )
