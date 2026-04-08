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


def _confidence_label(score: float) -> str:
    """Map a numeric confidence score to a human-readable label."""
    if score >= 0.90:
        return "High"
    if score >= 0.70:
        return "Moderate"
    if score >= 0.50:
        return "Low"
    return "Very Low"


def _build_system_prompt() -> str:
    """Return the stable system prompt (candidate for caching in Phase 1)."""
    return (
        "You are an expert barbell strength coach providing objective, "
        "evidence-based technique feedback. You are NOT a medical professional. "
        "All feedback is for educational and performance purposes only.\n\n"
        "Prioritise safety issues above all else. Address: "
        "(1) movement quality / form breakdown patterns first, "
        "(2) technical position issues second, "
        "(3) bar path and balance third, "
        "(4) consistency and control fourth.\n\n"
        "Be specific and actionable. Reference the exact rep number, joint, "
        "and movement phase. Do not give generic advice.\n\n"
        "Tone: direct, supportive, non-judgmental. Avoid clinical or medical "
        "language. Never use 'injury risk score,' 'injury prevention,' or "
        "'prevents injuries.' Use 'movement quality,' 'form breakdown,' "
        "'technique deviation,' 'loading concern' instead.\n\n"
        f'End every response with: "{MANDATORY_DISCLAIMER}"'
    )


def _build_user_prompt(
    exercise_type: str,
    exercise_variant: str,
    rep_metrics: list[dict[str, Any]],
    confidence_score: float,
    thresholds: ThresholdConfig,
) -> str:
    """Build the per-analysis user turn (fresh context, not cached)."""
    rep_count = len(rep_metrics)
    confidence_label = _confidence_label(confidence_score)

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
        f"Analysis results: {rep_count} reps detected. Confidence: {confidence_label}.",
        "",
        f"Per-rep metrics:\n{metrics_summary}",
        "",
        f"Relevant thresholds (reference values for this exercise):\n{threshold_summary}",
        "",
        "Provide structured feedback in this exact format:",
        "SUMMARY (2 sentences), STRENGTHS (2–3 bullets), ISSUES (one entry per issue: "
        "rep#, joint, description, severity: High/Medium/Low), "
        "CORRECTION PLAN (3–5 specific actionable cues), DISCLAIMER (mandatory).",
    ]

    if confidence_label in ("Low", "Very Low"):
        lines.insert(
            2,
            "Note: analysis confidence was low for this session — results should "
            "be interpreted with caution.",
        )

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
            Mean landmark visibility across all reps (0–1).
        thresholds:
            Loaded ThresholdConfig instance.

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
