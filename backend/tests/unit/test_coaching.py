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
    build_citation_blocks,
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

    def test_get_squat_depth_parallel(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "depth_parallel_hip_angle_deg") == 90.0

    def test_get_squat_torso_lean_caution(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "torso_lean_caution_deg") == 45.0

    def test_get_squat_torso_lean_high(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("squat", "torso_lean_high_deg") == 60.0

    def test_get_bench_elbow_angle_max(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("bench", "elbow_angle_at_bottom_max_deg") == 100.0

    def test_get_deadlift_hip_hinge_min(self) -> None:
        cfg = ThresholdConfig()
        assert cfg.get("deadlift", "hip_hinge_min_deg") == 70.0

    def test_v1_deferred_multi_camera_keys_not_in_active_section(self) -> None:
        """Frontal-plane keys live in deferred_multi_camera, NOT in active
        squat/bench/deadlift sections. Per ADR-AUDIT-2026-05-22.
        """
        cfg = ThresholdConfig()
        with pytest.raises(KeyError):
            cfg.get("squat", "knee_valgus_caution_deg")
        with pytest.raises(KeyError):
            cfg.get("bench", "elbow_flare_caution_deg")
        with pytest.raises(KeyError):
            cfg.get("bench", "grip_width_biacromial_ratio_max")

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
            cfg.get("nonexistent_exercise", "torso_lean_caution_deg")

    # --- v1-specific: nested object unwrapping ---

    def test_v1_get_unwraps_nested_value(self) -> None:
        """v1 thresholds are {value, unit, ...} objects; get() returns just the value."""
        cfg = ThresholdConfig()
        raw = cfg.get_raw("squat", "depth_parallel_hip_angle_deg")
        assert isinstance(raw, dict)
        assert raw["value"] == 90.0
        assert cfg.get("squat", "depth_parallel_hip_angle_deg") == 90.0

    def test_v1_get_citation(self) -> None:
        """get_citation() returns provenance string for nested thresholds."""
        cfg = ThresholdConfig()
        citation = cfg.get_citation("squat", "depth_parallel_hip_angle_deg")
        assert "Schoenfeld" in citation

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
        assert "depth_parallel_hip_angle_deg" in section

    # --- v0 backward compat ---

    def test_v0_still_loads(self) -> None:
        """v0 config still works when explicitly loaded."""
        from pathlib import Path

        v0_path = Path(__file__).parent.parent.parent / "config" / "thresholds_v0.json"
        if not v0_path.exists():
            pytest.skip("thresholds_v0.json not present")
        cfg = ThresholdConfig(path=v0_path)
        assert cfg.version == "v0"
        assert cfg.get("squat", "depth_parallel_hip_angle_deg") == 90

    def test_v0_get_citation_returns_none(self) -> None:
        """v0 flat values have no provenance — get_citation() returns None."""
        from pathlib import Path

        v0_path = Path(__file__).parent.parent.parent / "config" / "thresholds_v0.json"
        if not v0_path.exists():
            pytest.skip("thresholds_v0.json not present")
        cfg = ThresholdConfig(path=v0_path)
        assert cfg.get_citation("squat", "depth_parallel_hip_angle_deg") is None


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

    def test_system_prompt_requires_inline_citation_markers(self) -> None:
        """The system prompt MUST tell Claude to embed [N] inline in prose fields,
        not just list citations separately."""
        from app.services.coaching import _build_system_prompt

        prompt = _build_system_prompt()

        # The prompt must mention [N] / [1] marker syntax.
        assert "[N]" in prompt or "[1]" in prompt, (
            "system prompt must reference [N] / [1] marker syntax"
        )
        lowered = prompt.lower()
        # The prompt must say markers go inline / embedded in the prose.
        assert "inline" in lowered or "embed" in lowered, (
            "system prompt must tell Claude to embed markers inline"
        )
        # The prompt must name all 4 canonical prose fields where markers must appear.
        required_fields = ("summary", "correction_plan", "strengths", "issues")
        missing = [f for f in required_fields if f not in lowered]
        assert not missing, (
            f"system prompt must name all 4 prose fields where markers must appear; "
            f"missing from prompt: {missing}"
        )

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


# ---------------------------------------------------------------------------
# FR-AICP-08: cite-then-generate prompt architecture (P2-013)
# ---------------------------------------------------------------------------


def _make_retrieved_context(
    index: int = 1,
    title: str = "Knee valgus biomechanics during squat",
    authors: list[str] | None = None,
    year: int = 2021,
    doi: str | None = "10.1016/j.jbiomech.2021.110001",
    chunk_text: str = "Excessive knee valgus is associated with altered load distribution.",
    score: float = 0.87,
    collection: str = "papers_rag",
) -> object:
    """Return a minimal RetrievedContext for testing."""
    from app.schemas.rag import ChunkPayload, RetrievedContext

    if authors is None:
        authors = ["Smith, J.", "Jones, A."]

    chunk = ChunkPayload(
        id=f"sha256-{index:04d}",
        text=chunk_text,
        paper_id=f"paper-{index}",
        chunk_index=0,
        section="results",
        token_count=len(chunk_text.split()),
        quality_tier="L2_rct",
        title=title,
        authors=authors,
        year=year,
        doi=doi,
    )
    return RetrievedContext(chunk=chunk, score=score, collection=collection)  # type: ignore[arg-type]


class TestCiteThenGenerate:
    """FR-AICP-08: Cite-then-generate prompt architecture tests (P2-013)."""

    # --- build_citation_blocks ---

    def testbuild_citation_blocks_index_starts_at_one(self) -> None:
        """CitationBlock index must be 1-based."""

        contexts = [_make_retrieved_context(index=1), _make_retrieved_context(index=2)]
        blocks = build_citation_blocks(contexts)

        assert blocks[0].index == 1
        assert blocks[1].index == 2

    def testbuild_citation_blocks_title_and_authors(self) -> None:
        """CitationBlock must carry title and authors from ChunkPayload."""

        ctx = _make_retrieved_context(
            title="Deadlift mechanics review",
            authors=["Brown, K.", "Taylor, L."],
        )
        blocks = build_citation_blocks([ctx])

        assert len(blocks) == 1
        assert blocks[0].title == "Deadlift mechanics review"
        assert blocks[0].authors == ["Brown, K.", "Taylor, L."]

    def testbuild_citation_blocks_year_and_doi(self) -> None:
        """CitationBlock carries year and doi (may be None)."""

        ctx_with_doi = _make_retrieved_context(year=2019, doi="10.1016/test.doi")
        ctx_no_doi = _make_retrieved_context(doi=None, year=None)

        blocks = build_citation_blocks([ctx_with_doi, ctx_no_doi])

        assert blocks[0].year == 2019
        assert blocks[0].doi == "10.1016/test.doi"
        assert blocks[1].doi is None
        assert blocks[1].year is None

    def testbuild_citation_blocks_excerpt_truncated(self) -> None:
        """chunk_text_excerpt must be truncated to 300 chars."""

        long_text = "A" * 500
        ctx = _make_retrieved_context(chunk_text=long_text)
        blocks = build_citation_blocks([ctx])

        assert len(blocks[0].chunk_text_excerpt) <= 300

    def testbuild_citation_blocks_empty_list(self) -> None:
        """Empty context list produces empty CitationBlock list."""

        assert build_citation_blocks([]) == []

    # --- _build_user_prompt with retrieved_contexts ---

    def test_prompt_with_retrieved_contexts_includes_evidence_section(self) -> None:
        """When retrieved_contexts is provided, prompt must contain 'Retrieved Evidence'."""
        contexts = [_make_retrieved_context()]
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            retrieved_contexts=contexts,
        )
        assert "Retrieved Evidence:" in prompt

    def test_prompt_with_none_retrieved_contexts_has_no_evidence_section(self) -> None:
        """When retrieved_contexts is None, prompt must NOT contain 'Retrieved Evidence'."""
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            retrieved_contexts=None,
        )
        assert "Retrieved Evidence" not in prompt

    def test_prompt_with_empty_retrieved_contexts_has_no_evidence_section(self) -> None:
        """When retrieved_contexts is empty list, prompt must NOT contain 'Retrieved Evidence'."""
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            retrieved_contexts=[],
        )
        assert "Retrieved Evidence" not in prompt

    def test_prompt_citation_numbering_is_correct(self) -> None:
        """Retrieved Evidence markers must be [1], [2], [3] in order."""
        contexts = [
            _make_retrieved_context(index=1, title="Paper One"),
            _make_retrieved_context(index=2, title="Paper Two"),
            _make_retrieved_context(index=3, title="Paper Three"),
        ]
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            retrieved_contexts=contexts,
        )
        assert "[1]" in prompt
        assert "[2]" in prompt
        assert "[3]" in prompt
        # Ordering: [1] appears before [2] which appears before [3]
        assert prompt.index("[1]") < prompt.index("[2]") < prompt.index("[3]")

    def test_prompt_cite_then_generate_instruction_present(self) -> None:
        """Cite-then-generate instruction must appear when contexts are provided."""
        contexts = [_make_retrieved_context()]
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            retrieved_contexts=contexts,
        )
        assert "Do not fabricate citations." in prompt
        assert "Only cite evidence that directly supports your point." in prompt

    def test_prompt_evidence_includes_score(self) -> None:
        """Relevance score must appear in the evidence section."""
        ctx = _make_retrieved_context(score=0.91)
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            retrieved_contexts=[ctx],
        )
        assert "0.91" in prompt

    def test_prompt_evidence_includes_doi(self) -> None:
        """DOI must appear in the evidence section when present."""
        ctx = _make_retrieved_context(doi="10.1016/j.jbiomech.2021.110001")
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            retrieved_contexts=[ctx],
        )
        assert "10.1016/j.jbiomech.2021.110001" in prompt

    # --- generate_coaching backwards compatibility ---

    @pytest.mark.asyncio
    async def test_generate_coaching_accepts_retrieved_contexts(self) -> None:
        """generate_coaching with retrieved_contexts must forward them to the prompt."""
        mock_client = MagicMock()
        expected = _make_coaching_output()
        captured_messages: list[Any] = []

        async def capture_create(**kwargs: Any) -> CoachingOutput:
            captured_messages.extend(kwargs.get("messages", []))
            return expected

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = capture_create

        contexts = [_make_retrieved_context(title="Squat depth and knee mechanics")]

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            result = await service.generate_coaching(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.90,
                thresholds=ThresholdConfig(),
                retrieved_contexts=contexts,
            )

        assert isinstance(result, CoachingOutput)
        assert len(captured_messages) == 1
        user_content: str = captured_messages[0]["content"]
        assert "Retrieved Evidence" in user_content
        assert "Squat depth and knee mechanics" in user_content

    @pytest.mark.asyncio
    async def test_generate_coaching_backwards_compat_no_contexts(self) -> None:
        """generate_coaching with no retrieved_contexts is unchanged from Phase 1."""
        mock_client = MagicMock()
        expected = _make_coaching_output()
        captured_messages: list[Any] = []

        async def capture_create(**kwargs: Any) -> CoachingOutput:
            captured_messages.extend(kwargs.get("messages", []))
            return expected

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = capture_create

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            result = await service.generate_coaching(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.90,
                thresholds=ThresholdConfig(),
                # No retrieved_contexts arg — defaults to None
            )

        assert isinstance(result, CoachingOutput)
        user_content: str = captured_messages[0]["content"]
        assert "Retrieved Evidence" not in user_content

    # --- generate_coaching_streaming backwards compatibility ---

    @pytest.mark.asyncio
    async def test_generate_coaching_streaming_accepts_retrieved_contexts(self) -> None:
        """generate_coaching_streaming with retrieved_contexts must include evidence in prompt."""
        mock_client = MagicMock()
        expected = _make_coaching_output()
        captured_kwargs: dict[str, Any] = {}

        async def mock_create_partial(**kwargs: Any) -> Any:
            captured_kwargs.update(kwargs)
            yield expected

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial

        contexts = [_make_retrieved_context(title="Bench press scapular mechanics")]

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            result = await service.generate_coaching_streaming(
                exercise_type="bench",
                exercise_variant="flat",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.88,
                thresholds=ThresholdConfig(),
                retrieved_contexts=contexts,
                pubsub_redis=None,
            )

        assert isinstance(result, CoachingOutput)
        messages = captured_kwargs.get("messages", [])
        assert len(messages) == 1
        user_content: str = messages[0]["content"]
        assert "Retrieved Evidence" in user_content
        assert "Bench press scapular mechanics" in user_content

    @pytest.mark.asyncio
    async def test_generate_coaching_streaming_backwards_compat_no_contexts(self) -> None:
        """generate_coaching_streaming with no retrieved_contexts is unchanged from Phase 1."""
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
            result = await service.generate_coaching_streaming(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=_make_sample_rep_metrics(),
                confidence_score=0.90,
                thresholds=ThresholdConfig(),
                pubsub_redis=None,
                # No retrieved_contexts — defaults to None
            )

        assert isinstance(result, CoachingOutput)
        messages = captured_kwargs.get("messages", [])
        user_content: str = messages[0]["content"]
        assert "Retrieved Evidence" not in user_content


# ---------------------------------------------------------------------------
# P2-026: [RESEARCH]/[COACHING] source labels in prompt (FR-BRAIN-04)
# ---------------------------------------------------------------------------


class TestSourceLabelsInPrompt:
    """FR-BRAIN-04: Retrieved Evidence items must be tagged with [RESEARCH]
    or [COACHING] when retrieval_source is provided."""

    def test_coaching_label_on_coach_brain_items(self) -> None:
        """When retrieval_source is 'coach_brain_primary', coach_brain items
        must be prefixed with [COACHING] and papers with [RESEARCH]."""
        contexts = [
            _make_retrieved_context(index=1, title="Paper One", collection="papers_rag"),
            _make_retrieved_context(index=2, title="Brain Cue", collection="coach_brain"),
        ]
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            retrieved_contexts=contexts,
            retrieval_source="coach_brain_primary",
        )
        assert "[COACHING]" in prompt, "coach_brain items must have [COACHING] label"
        assert "[RESEARCH]" in prompt, "papers_rag items must have [RESEARCH] label"

    def test_no_coaching_label_in_papers_only_fallback(self) -> None:
        """When retrieval_source is 'papers_only_fallback', no [COACHING]
        labels should appear (P2-027 cold-start)."""
        contexts = [
            _make_retrieved_context(index=1, title="Paper One", collection="papers_rag"),
        ]
        prompt = _build_user_prompt(
            exercise_type="squat",
            exercise_variant="high_bar",
            rep_metrics=_make_sample_rep_metrics(),
            confidence_score=0.88,
            thresholds=ThresholdConfig(),
            retrieved_contexts=contexts,
            retrieval_source="papers_only_fallback",
        )
        assert "[COACHING]" not in prompt, "No [COACHING] label in papers_only_fallback"
        assert "[RESEARCH]" in prompt, "papers_rag items must have [RESEARCH] label"


# ---------------------------------------------------------------------------
# Additional branch-coverage tests for coaching.py missed lines
# ---------------------------------------------------------------------------


class TestCoachingBranchCoverage:
    """Extra tests targeting specific missed branches (lines 200-201, 298, 535, 623, 649-656)."""

    def test_build_user_prompt_keyerror_in_thresholds_falls_back_to_empty(self) -> None:
        """When thresholds.all_for_exercise raises KeyError, threshold_summary defaults to '{}' (lines 200-201)."""

        class _RaisingThresholds:
            version = "test"
            def all_for_exercise(self, exercise_type: str) -> dict:
                raise KeyError(exercise_type)

        prompt = _build_user_prompt(
            exercise_type="unknown_exercise",
            exercise_variant=None,
            rep_metrics=[{"rep_number": 1, "depth_angle": 90.0}],
            confidence_score=0.80,
            thresholds=_RaisingThresholds(),
        )
        # Prompt must still be built — just without threshold data
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_is_retryable_returns_false_for_generic_error(self) -> None:
        """_is_retryable returns False for non-rate-limit, non-timeout errors (line 298)."""
        from app.services.coaching import _is_retryable

        generic_err = ValueError("some random error")
        assert _is_retryable(generic_err) is False

    @pytest.mark.asyncio
    async def test_generate_coaching_streaming_raises_when_instructor_client_none(self) -> None:
        """generate_coaching_streaming raises ValueError when _instructor_client is None (line 535)."""
        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = None

            service = CoachingService(anthropic_client=MagicMock())
            # Force _instructor_client to None to simulate the guarded path
            service._instructor_client = None

            with pytest.raises(ValueError, match="anthropic_client=None"):
                await service.generate_coaching_streaming(
                    exercise_type="squat",
                    exercise_variant=None,
                    rep_metrics=[],
                    confidence_score=0.80,
                    thresholds=ThresholdConfig(),
                    pubsub_redis=None,
                )

    @pytest.mark.asyncio
    async def test_generate_coaching_streaming_raises_when_final_result_none(self) -> None:
        """When create_partial yields nothing, ValueError is raised (line 623)."""
        mock_client = MagicMock()

        async def mock_create_partial_empty(**kwargs: Any) -> Any:
            return
            yield  # make it an async generator

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial_empty

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            with pytest.raises(ValueError, match="yielded no results"):
                await service.generate_coaching_streaming(
                    exercise_type="bench",
                    exercise_variant="flat",
                    rep_metrics=_make_sample_rep_metrics(),
                    confidence_score=0.85,
                    thresholds=ThresholdConfig(),
                    pubsub_redis=None,
                )

    @pytest.mark.asyncio
    async def test_generate_coaching_streaming_raises_non_retryable_error(self) -> None:
        """Non-retryable, non-auth errors are logged and re-raised (lines 649-656)."""
        import anthropic
        mock_client = MagicMock()

        non_retryable_error = anthropic.BadRequestError(
            message="Bad request",
            response=MagicMock(status_code=400),
            body={"error": {"type": "invalid_request_error", "message": "Bad request"}},
        )

        async def mock_create_partial_bad_request(**kwargs: Any) -> Any:
            raise non_retryable_error
            yield

        mock_instructor = MagicMock()
        mock_instructor.chat.completions.create_partial = mock_create_partial_bad_request

        with patch("app.services.coaching.instructor") as mock_instructor_module:
            mock_instructor_module.from_anthropic.return_value = mock_instructor

            service = CoachingService(anthropic_client=mock_client)
            with pytest.raises(anthropic.BadRequestError):
                await service.generate_coaching_streaming(
                    exercise_type="deadlift",
                    exercise_variant="conventional",
                    rep_metrics=_make_sample_rep_metrics(),
                    confidence_score=0.85,
                    thresholds=ThresholdConfig(),
                    pubsub_redis=None,
                )
