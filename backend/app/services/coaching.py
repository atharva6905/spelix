"""CoachingService — Phase 0 LLM coaching pipeline.

Calls Claude Sonnet 4.6 via the instructor library to produce a structured
CoachingOutput validated by Pydantic v2.

Requirements: FR-RESL-03, Appendix D (B-023)

Error handling (per Appendix D.2):
    - 429 / 529 (rate limit / overload): exponential backoff 1s → 2s → 4s,
      max 3 retries. Raises the final exception if all retries exhaust.
    - 401 (auth error): fail immediately, CRITICAL log, no retries.
    - 400 (bad request): fail immediately, log full context.
    - Network timeout: 60s total; on timeout treat as 529 (apply backoff).

Notes:
    - Never use "injury risk" or "injury prevention" in prompts or output.
    - This service is called from the ARQ worker (wired in B-024).
    - Never call the real Anthropic API in tests — always mock.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import anthropic
import instructor

from app.config import ThresholdConfig
from app.cv.confidence import confidence_label
from app.schemas.coaching import CoachingOutput

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (Appendix D)
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
TEMPERATURE = 0.3
MAX_TOKENS = 2048
NETWORK_TIMEOUT_S = 60.0

MANDATORY_DISCLAIMER = (
    "This feedback is for educational purposes only and is not a substitute "
    "for in-person coaching or medical advice."
)

# Retry schedule for 429 / 529 / timeout (Appendix D.2)
_BACKOFF_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)

# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_system_prompt() -> str:
    """Return the stable system prompt (candidate for prompt caching in Phase 1).

    Priority enforcement per FR-AICP-04:
      1. Movement Quality — breakdown patterns and motor control
      2. Technique — positional deviations from optimal mechanics
      3. Path & Balance — bar path, weight distribution, lateral drift
      4. Control — tempo, consistency, fatigue effects
    """
    return (
        "You are an expert barbell strength coach providing objective, "
        "evidence-based technique feedback. You are NOT a medical professional. "
        "All feedback is for educational and performance purposes only.\n\n"
        "This analysis evaluates Movement Quality, Technique, Path & Balance, "
        "and Control — grounded in peer-reviewed biomechanics research.\n\n"
        "PRIORITY ORDER — always address dimensions in this exact sequence:\n"
        "  1. Movement Quality: identify form breakdown patterns and motor control "
        "deviations across the full range of motion.\n"
        "  2. Technique: identify positional deviations from optimal joint mechanics "
        "(e.g. knee tracking, spinal alignment, elbow position).\n"
        "  3. Path & Balance: assess bar path deviation, lateral drift, and "
        "centre-of-mass balance across the base of support.\n"
        "  4. Control: evaluate tempo consistency, rep-to-rep variability, and "
        "any fatigue-related form degradation.\n\n"
        "For each identified deviation:\n"
        "  - Reference the exact rep number, joint, and movement phase.\n"
        "  - Provide a 'Recommended Cues' list with specific verbal or tactile cues "
        "the coach can use with the lifter.\n"
        "  - When referencing research, include a citation (title, authors, year, "
        "and DOI if available).\n\n"
        "Tone: direct, supportive, non-judgmental. Be specific — never give generic "
        "advice.\n\n"
        "PROHIBITED LANGUAGE — never use any of these phrases:\n"
        "  - phrases combining the word 'injury' with 'risk' or 'prevention'\n"
        "  - 'prevent injury', 'diagnose', 'treat', 'medical', 'clinical'\n"
        "USE INSTEAD:\n"
        "  - 'Movement Quality', 'movement pattern', 'form breakdown', "
        "'technique deviation', 'loading concern'\n\n"
        f'End every response with the mandatory disclaimer: "{MANDATORY_DISCLAIMER}"'
    )


def _build_user_prompt(
    exercise_type: str,
    exercise_variant: str,
    rep_metrics: list[dict[str, Any]],
    confidence_score: float,
    thresholds: ThresholdConfig,
    body_stats: dict[str, Any] | None = None,
    keyframe_analysis_text: str | None = None,
) -> str:
    """Build the per-analysis user turn (fresh context, not cached).

    Parameters
    ----------
    exercise_type:
        One of "squat", "bench", "deadlift".
    exercise_variant:
        Exercise-specific variant string (e.g. "high_bar", "conventional").
    rep_metrics:
        List of per-rep metric dicts from the CV pipeline.
    confidence_score:
        Mean landmark visibility / Tier 5 score (0–1).
    thresholds:
        Loaded ThresholdConfig instance.
    body_stats:
        Optional athlete profile dict (e.g. height, weight, limb ratios).
        When None, general population coaching standards are applied.
    keyframe_analysis_text:
        Optional GPT-4o keyframe analysis text (Phase 1 visual analysis).
        When provided, prepended as a "Visual Analysis" section.
    """
    rep_count = len(rep_metrics)
    confidence_label_str = confidence_label(confidence_score)

    # Summarise rep metrics as compact JSON for the model
    metrics_summary = json.dumps(rep_metrics, indent=2)

    # Pull relevant thresholds for the exercise
    try:
        exercise_thresholds = thresholds.all_for_exercise(exercise_type)
        threshold_summary = json.dumps(exercise_thresholds, indent=2)
    except KeyError:
        threshold_summary = "{}"

    lines: list[str] = [
        f"Exercise: {exercise_type} — {exercise_variant}",
        f"Analysis results: {rep_count} reps detected. Confidence: {confidence_label_str}.",
    ]

    if confidence_label_str in ("Low", "Very Low"):
        lines.append(
            "Note: analysis confidence was low for this session — results should "
            "be interpreted with caution."
        )

    lines.append("")

    # Athlete profile section (FR-AICP-05)
    if body_stats is not None:
        athlete_profile_json = json.dumps(body_stats, indent=2)
        lines += [
            "Athlete Profile:",
            athlete_profile_json,
            "",
        ]
    else:
        lines += [
            "No athlete profile on file — apply general population coaching standards.",
            "",
        ]

    # Visual analysis section from GPT-4o keyframe analysis (Phase 1)
    if keyframe_analysis_text is not None:
        lines += [
            "Visual Analysis (keyframe):",
            keyframe_analysis_text,
            "",
        ]

    lines += [
        f"Per-rep metrics:\n{metrics_summary}",
        "",
        f"Relevant thresholds (reference values for this exercise):\n{threshold_summary}",
        "",
        "Provide structured feedback in the priority order defined in the system prompt:",
        "1. Movement Quality  2. Technique  3. Path & Balance  4. Control",
        "Include: SUMMARY (2 sentences), STRENGTHS (2–3 bullets), ISSUES (rep#, joint, "
        "description, severity: High/Medium/Low), CORRECTION PLAN (3–5 actionable cues), "
        "RECOMMENDED CUES (verbal/tactile cues for the lifter), "
        "CITATIONS (if referencing research), DISCLAIMER (mandatory).",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------


def _is_retryable(exc: Exception) -> bool:
    """Return True if the exception should trigger exponential backoff."""
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        # 529 = overload
        return exc.status_code == 529
    if isinstance(exc, (TimeoutError, anthropic.APITimeoutError)):
        return True
    return False


def _is_auth_error(exc: Exception) -> bool:
    """Return True if the exception is a non-retryable auth failure."""
    return isinstance(exc, anthropic.AuthenticationError)


# ---------------------------------------------------------------------------
# CoachingService
# ---------------------------------------------------------------------------


class CoachingService:
    """Phase 0 coaching service: structured LLM call via instructor.

    Parameters
    ----------
    anthropic_client:
        An ``anthropic.AsyncAnthropic`` instance (or sync ``anthropic.Anthropic``).
        Pass ``None`` only when the caller guarantees the instructor client will
        never be invoked (e.g., pure unit-test mocking of the entire class).
    model:
        Anthropic model ID. Defaults to ``claude-sonnet-4-6``.
    """

    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic | anthropic.Anthropic | None,
        model: str = MODEL,
    ) -> None:
        self._model = model
        if anthropic_client is None:
            # Defer instructor wrapping — will raise on use if not mocked
            self._instructor_client: Any = None
        else:
            self._instructor_client = instructor.from_anthropic(anthropic_client)

    async def generate_coaching(
        self,
        *,
        exercise_type: str,
        exercise_variant: str,
        rep_metrics: list[dict[str, Any]],
        confidence_score: float,
        thresholds: ThresholdConfig,
        body_stats: dict[str, Any] | None = None,
        keyframe_analysis_text: str | None = None,
    ) -> CoachingOutput:
        """Call Claude and return a validated CoachingOutput.

        Parameters
        ----------
        exercise_type:
            One of "squat", "bench", "deadlift".
        exercise_variant:
            Exercise-specific variant string (e.g. "high_bar", "conventional").
        rep_metrics:
            List of per-rep metric dicts extracted by the CV pipeline.
        confidence_score:
            Mean landmark visibility / Tier 5 score across all reps (0–1).
        thresholds:
            Loaded ThresholdConfig instance.
        body_stats:
            Optional athlete profile dict (height, weight, limb ratios).
            Passed through to the user prompt. When None, general population
            coaching standards are applied.
        keyframe_analysis_text:
            Optional GPT-4o keyframe analysis text for the Visual Analysis
            section of the prompt (Phase 1). When None, section is omitted.

        Returns
        -------
        CoachingOutput
            Fully validated Pydantic model ready to be stored as JSONB.

        Raises
        ------
        ValueError
            If ``anthropic_client`` was ``None`` and the instructor client is
            not available (misconfigured service with no mock).
        anthropic.AuthenticationError
            Immediately on 401 — no retries.
        anthropic.RateLimitError
            After all 3 retries are exhausted (for 429 / 529 / timeout).
        """
        if self._instructor_client is None:
            raise ValueError(
                "CoachingService was constructed with anthropic_client=None. "
                "Provide a valid client or patch the instructor client in tests."
            )

        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(
            exercise_type=exercise_type,
            exercise_variant=exercise_variant,
            rep_metrics=rep_metrics,
            confidence_score=confidence_score,
            thresholds=thresholds,
            body_stats=body_stats,
            keyframe_analysis_text=keyframe_analysis_text,
        )

        messages = [{"role": "user", "content": user_prompt}]

        last_exc: Exception | None = None

        for attempt, delay in enumerate(
            [None, *_BACKOFF_DELAYS]
        ):  # attempts: 0(initial) + 3 retries
            if delay is not None:
                await asyncio.sleep(delay)

            try:
                result: CoachingOutput = await self._instructor_client.chat.completions.create(
                    model=self._model,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    system=system_prompt,
                    messages=messages,
                    response_model=CoachingOutput,
                )
                return result

            except Exception as exc:
                if _is_auth_error(exc):
                    logger.critical(
                        "Anthropic 401 authentication error — check ANTHROPIC_API_KEY. "
                        "No retries. exercise_type=%s",
                        exercise_type,
                    )
                    raise

                if _is_retryable(exc):
                    last_exc = exc
                    attempt_num = (
                        0
                        if delay is None
                        else _BACKOFF_DELAYS.index(delay) + 1
                    )
                    logger.warning(
                        "Retryable Anthropic error (attempt %d/%d): %s",
                        attempt_num + 1,
                        len(_BACKOFF_DELAYS) + 1,
                        exc,
                    )
                    continue

                # Non-retryable, non-auth error (400, unexpected, etc.)
                logger.error(
                    "Non-retryable Anthropic error: %s. "
                    "exercise_type=%s exercise_variant=%s",
                    exc,
                    exercise_type,
                    exercise_variant,
                )
                raise

        # All retries exhausted
        assert last_exc is not None
        raise last_exc
