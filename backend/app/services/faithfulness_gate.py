"""FaithfulnessGateService — LLM-as-judge faithfulness gate (P2-015, FR-AICP-08 Stage 3).

Evaluates whether the claims in a CoachingOutput are supported by the
retrieved source documents. Uses Claude Sonnet 4.6 as the judge via the
instructor library for structured output extraction.

Design notes:
- This service MUST NEVER raise an exception. Any failure returns a safe
  default FaithfulnessResult with score=0.0 and flagged_for_review=True.
- Guard clause: empty retrieved_contexts skips the LLM call entirely and
  returns score=0.0 immediately.
- Prompt caching applied to the system prompt (cache_control ephemeral)
  because the same system prompt is reused across analyses.
- Temperature 0.1 for near-deterministic evaluation.
- Phase 3 will swap this LLM judge for a dedicated HHEM T5 inference
  endpoint (2GB droplet cannot host a T5 model alongside MediaPipe).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import anthropic
import instructor
from pydantic import BaseModel, Field

from app.schemas.coaching import CoachingOutput
from app.schemas.rag import RetrievedContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAITHFULNESS_THRESHOLD = 0.8
_MODEL = "claude-sonnet-4-6"
_TEMPERATURE = 0.1
_MAX_TOKENS = 1024

# ---------------------------------------------------------------------------
# Pydantic model for instructor structured output
# ---------------------------------------------------------------------------


class FaithfulnessScore(BaseModel):
    """Structured faithfulness score extracted by instructor from the LLM response."""

    score: float = Field(ge=0.0, le=1.0, description="Faithfulness score 0.0-1.0")
    reasoning: str = Field(description="Explanation of the faithfulness assessment")
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description="Claims not supported by evidence",
    )


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class FaithfulnessResult:
    """Result of a faithfulness evaluation."""

    score: float
    passed: bool
    reasoning: str
    unsupported_claims: list[str] = field(default_factory=list)
    flagged_for_review: bool = False


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a faithfulness evaluator for AI-generated coaching feedback. Your task is to evaluate whether the claims and recommendations in the coaching output are supported by the provided source documents.

Score from 0.0 to 1.0 where:
- 1.0 = every factual claim and recommendation is directly supported by the sources
- 0.5 = some claims are supported, others are not
- 0.0 = no claims are supported by the sources

List any specific claims that are NOT supported by the provided evidence.\
"""


def _build_user_prompt(
    coaching_output: CoachingOutput,
    retrieved_contexts: list[RetrievedContext],
) -> str:
    """Build the user prompt with numbered source chunks and coaching output."""
    lines: list[str] = ["## Source Documents\n"]
    for idx, ctx in enumerate(retrieved_contexts, start=1):
        lines.append(f"[{idx}] {ctx.chunk.text}\n")

    lines.append("\n## Coaching Output\n")
    lines.append(f"**Summary:** {coaching_output.summary}\n")

    if coaching_output.issues:
        lines.append("\n**Issues Identified:**")
        for issue in coaching_output.issues:
            lines.append(f"- Rep {issue.rep_number} ({issue.joint}): {issue.description} [Severity: {issue.severity}]")

    lines.append("\n**Correction Plan:**")
    for cue in coaching_output.correction_plan:
        lines.append(f"- {cue}")

    if coaching_output.recommended_cues:
        lines.append("\n**Recommended Cues:**")
        for cue in coaching_output.recommended_cues:
            lines.append(f"- {cue}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class FaithfulnessGateService:
    """Evaluates coaching output faithfulness against retrieved source documents.

    Uses Claude Sonnet 4.6 as an LLM judge via the instructor library.
    Never raises — always returns a FaithfulnessResult.
    """

    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        model: str = _MODEL,
    ) -> None:
        self._model = model
        self._instructor_client = instructor.from_anthropic(anthropic_client)

    async def evaluate(
        self,
        coaching_output: CoachingOutput,
        retrieved_contexts: list[RetrievedContext],
    ) -> FaithfulnessResult:
        """Evaluate faithfulness of coaching_output against retrieved_contexts.

        Guard clause: empty contexts → score=0 without LLM call.
        Any exception → safe default with flagged_for_review=True.
        """
        # Guard clause — no contexts means we cannot evaluate faithfulness
        if not retrieved_contexts:
            return FaithfulnessResult(
                score=0.0,
                passed=False,
                reasoning="no_retrieved_contexts",
                unsupported_claims=[],
                flagged_for_review=True,
            )

        try:
            user_prompt = _build_user_prompt(coaching_output, retrieved_contexts)

            llm_result: FaithfulnessScore = await self._instructor_client.chat.completions.create(
                model=self._model,
                response_model=FaithfulnessScore,
                temperature=_TEMPERATURE,
                max_tokens=_MAX_TOKENS,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            )

            return FaithfulnessResult(
                score=llm_result.score,
                passed=llm_result.score >= FAITHFULNESS_THRESHOLD,
                reasoning=llm_result.reasoning,
                unsupported_claims=llm_result.unsupported_claims,
                flagged_for_review=llm_result.score < FAITHFULNESS_THRESHOLD,
            )

        except Exception as e:
            logger.warning(
                "FaithfulnessGateService.evaluate failed — returning safe default. "
                "error=%s: %s",
                type(e).__name__,
                e,
            )
            return FaithfulnessResult(
                score=0.0,
                passed=False,
                reasoning=f"evaluation_failed: {type(e).__name__}: {e}",
                unsupported_claims=[],
                flagged_for_review=True,
            )
