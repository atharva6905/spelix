"""KeyframeAnalysisService — GPT-4o vision analysis of rep keyframes (FR-AICP-02).

Sends keyframe images + structured per-rep metrics to GPT-4o vision model.
Returns structured per-rep visual analysis via instructor + Pydantic v2.

Architecture:
    - GPT-4o handles VISION (keyframe images) → structured observations
    - Claude Sonnet 4.6 handles COACHING (text) → final coaching output
    These are separate concerns. This service is GPT-4o only.

Notes:
    - Never call real OpenAI API in tests — always mock.
    - Image detail: "low" (170 tokens per image, well within limits).
    - Cap at 18 images max (6 reps × 3 frames). For >6 reps, send
      depth frames only for reps beyond the first 6.
    - Never use "injury risk" — use "Movement Quality".
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import instructor
import openai
from pydantic import BaseModel, Field

from app.config_constants import LLM_MAX_TOKENS_KEYFRAME as MAX_TOKENS
from app.cv.keyframe_extraction import RepKeyframes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "gpt-4o"
TEMPERATURE = 0.2

# Max keyframe images to send (6 reps × 3 frames = 18).
# Beyond 6 reps, only depth frames are sent.
_MAX_FULL_REPS = 6
_MAX_IMAGES = 18

# Retry schedule for 429 / timeout
_BACKOFF_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)

# ---------------------------------------------------------------------------
# Pydantic schemas for structured output
# ---------------------------------------------------------------------------


class ExerciseClassification(BaseModel):
    """GPT-4o exercise classification result (FR-XDET-04)."""

    exercise_type: str = Field(
        description="Detected exercise: 'squat', 'bench', or 'deadlift'.",
    )
    exercise_variant: str = Field(
        description=(
            "Detected variant: 'high_bar', 'low_bar', 'flat', 'incline', "
            "'decline', 'conventional', 'sumo', or 'romanian'."
        ),
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Classification confidence from 0.0 to 1.0.",
    )
    reasoning: str = Field(
        description="Brief explanation of why this classification was chosen.",
    )


class KeyframeAnalysis(BaseModel):
    """Per-rep visual analysis from GPT-4o."""

    rep_index: int = Field(description="Zero-indexed rep number.")
    observations: list[str] = Field(
        description="What GPT-4o observes in the keyframe images for this rep.",
    )
    form_deviations: list[str] = Field(
        default_factory=list,
        description="Specific form deviations observed visually.",
    )
    phase_assessment: str = Field(
        description="Assessment of bottom/transition quality for this rep.",
    )


class KeyframeAnalysisResult(BaseModel):
    """Full keyframe analysis across all reps."""

    per_rep: list[KeyframeAnalysis] = Field(
        description="Per-rep visual analysis results.",
    )
    overall_notes: str = Field(
        description="Overall visual observations across all reps.",
    )


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_system_prompt() -> str:
    return (
        "You are a biomechanics vision analyst. You receive keyframe images "
        "from barbell exercise videos (start, bottom/depth, and end positions "
        "for each rep) alongside structured pose metrics.\n\n"
        "Your task: analyze the visual evidence in each keyframe and report:\n"
        "1. What you observe about body position, joint angles, and bar path.\n"
        "2. Any form deviations visible in the images.\n"
        "3. Assessment of the bottom/transition position quality.\n\n"
        "Be specific and reference exact visual evidence. Do not speculate "
        "beyond what is visible. Never use terms like 'injury risk' or "
        "'injury prevention' — use 'movement quality' and 'form deviation' instead."
    )


def _build_image_content(
    keyframes: list[RepKeyframes],
) -> list[dict[str, Any]]:
    """Build OpenAI content blocks with keyframe images.

    For ≤6 reps: send all 3 frames per rep (start, depth, end).
    For >6 reps: send all 3 for first 6, depth-only for the rest.
    """
    content: list[dict[str, Any]] = []
    for kf in keyframes:
        if kf.rep_index < _MAX_FULL_REPS:
            # Full set: start, depth, end
            for label, b64 in [
                ("start", kf.start_image_b64),
                ("depth", kf.depth_image_b64),
                ("end", kf.end_image_b64),
            ]:
                content.append(
                    {"type": "text", "text": f"Rep {kf.rep_index + 1} — {label}:"}
                )
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                            "detail": "low",
                        },
                    }
                )
        else:
            # Depth only for reps beyond 6
            content.append(
                {"type": "text", "text": f"Rep {kf.rep_index + 1} — depth:"}
            )
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{kf.depth_image_b64}",
                        "detail": "low",
                    },
                }
            )

    return content


def _build_user_content(
    keyframes: list[RepKeyframes],
    exercise_type: str,
    exercise_variant: str,
    rep_metrics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the full multimodal user message content."""
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f"Exercise: {exercise_type} — {exercise_variant}\n"
                f"Reps detected: {len(keyframes)}\n\n"
                f"Per-rep metrics:\n{json.dumps(rep_metrics, indent=2)}\n\n"
                "Analyze the following keyframe images:"
            ),
        }
    ]
    content.extend(_build_image_content(keyframes))
    return content


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, openai.RateLimitError):
        return True
    if isinstance(exc, openai.APIStatusError) and exc.status_code == 529:
        return True
    if isinstance(exc, (TimeoutError, openai.APITimeoutError)):
        return True
    return False


def _is_auth_error(exc: Exception) -> bool:
    return isinstance(exc, openai.AuthenticationError)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class KeyframeAnalysisService:
    """GPT-4o vision analysis of rep keyframe images (FR-AICP-02).

    Parameters
    ----------
    openai_client:
        An ``openai.AsyncOpenAI`` instance. Pass None only when the caller
        guarantees instructor will never be invoked (test mocking).
    model:
        OpenAI model ID. Defaults to ``gpt-4o``.
    """

    def __init__(
        self,
        openai_client: openai.AsyncOpenAI | None,
        model: str = MODEL,
    ) -> None:
        self._model = model
        if openai_client is None:
            self._instructor_client: Any = None
        else:
            self._instructor_client = instructor.from_openai(openai_client)

    async def analyze_keyframes(
        self,
        *,
        keyframes: list[RepKeyframes],
        exercise_type: str,
        exercise_variant: str,
        rep_metrics: list[dict[str, Any]],
    ) -> KeyframeAnalysisResult:
        """Send keyframe images + metrics to GPT-4o and return structured analysis.

        Parameters
        ----------
        keyframes:
            List of RepKeyframes with base64 JPEG images.
        exercise_type:
            One of "squat", "bench", "deadlift".
        exercise_variant:
            Exercise variant string.
        rep_metrics:
            List of per-rep metric dicts from the CV pipeline.

        Returns
        -------
        KeyframeAnalysisResult
            Structured per-rep visual analysis.

        Raises
        ------
        openai.AuthenticationError
            On 401 — no retries.
        openai.RateLimitError
            After all 3 retries exhausted.
        """
        if self._instructor_client is None:
            raise ValueError(
                "KeyframeAnalysisService constructed with openai_client=None."
            )

        if not keyframes:
            return KeyframeAnalysisResult(per_rep=[], overall_notes="No keyframes provided.")

        system_prompt = _build_system_prompt()
        user_content = _build_user_content(
            keyframes, exercise_type, exercise_variant, rep_metrics,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        last_exc: Exception | None = None

        for delay in [None, *_BACKOFF_DELAYS]:
            if delay is not None:
                await asyncio.sleep(delay)

            try:
                result: KeyframeAnalysisResult = (
                    await self._instructor_client.chat.completions.create(
                        model=self._model,
                        max_tokens=MAX_TOKENS,
                        temperature=TEMPERATURE,
                        messages=messages,
                        response_model=KeyframeAnalysisResult,
                    )
                )
                return result

            except Exception as exc:
                if _is_auth_error(exc):
                    logger.critical(
                        "OpenAI 401 authentication error — check OPENAI_API_KEY."
                    )
                    raise

                if _is_retryable(exc):
                    last_exc = exc
                    logger.warning("Retryable OpenAI error: %s", exc)
                    continue

                logger.error("Non-retryable OpenAI error: %s", exc)
                raise

        assert last_exc is not None
        raise last_exc

    async def classify_exercise(
        self,
        *,
        frame_images_b64: list[str],
    ) -> "ExerciseClassification":
        """GPT-4o exercise classification fallback (FR-XDET-04).

        Sends up to 3 keyframe images and asks GPT-4o to classify
        the exercise type and variant.

        Parameters
        ----------
        frame_images_b64:
            List of base64-encoded JPEG frames (first 3 from the video).

        Returns
        -------
        ExerciseClassification
            Detected exercise type, variant, and confidence.
        """
        if self._instructor_client is None:
            raise ValueError(
                "KeyframeAnalysisService constructed with openai_client=None."
            )

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Classify the barbell exercise shown in these frames.\n"
                    "Choose from: squat, bench, deadlift.\n"
                    "Also identify the variant if possible."
                ),
            },
        ]
        for i, b64 in enumerate(frame_images_b64[:3]):
            content.append({"type": "text", "text": f"Frame {i + 1}:"})
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"},
            })

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a barbell exercise classifier. Given video frames, "
                    "identify the exercise type (squat, bench, deadlift) and "
                    "variant. Be precise and confident."
                ),
            },
            {"role": "user", "content": content},
        ]

        last_exc: Exception | None = None
        for delay in [None, *_BACKOFF_DELAYS]:
            if delay is not None:
                await asyncio.sleep(delay)
            try:
                result: ExerciseClassification = (
                    await self._instructor_client.chat.completions.create(
                        model=self._model,
                        max_tokens=256,
                        temperature=0.1,
                        messages=messages,
                        response_model=ExerciseClassification,
                    )
                )
                return result
            except Exception as exc:
                if _is_auth_error(exc):
                    logger.critical("OpenAI 401 — check OPENAI_API_KEY.")
                    raise
                if _is_retryable(exc):
                    last_exc = exc
                    logger.warning("Retryable OpenAI error: %s", exc)
                    continue
                logger.error("Non-retryable OpenAI error: %s", exc)
                raise

        assert last_exc is not None
        raise last_exc
