"""BrainCoveService — single-claim CoVe verifier for distillation candidates.

Slim variant of app/services/cove.py's CoveVerificationService. Skips
claim extraction (the candidate content IS the claim), generates one
verification question, and verifies against retrieved papers_rag
contexts. Never raises — any failure returns BrainCoveResult(verified=
false, explanation=<detail>).

Cites FR-BRAIN-14. The full CoachingOutput-oriented CoveVerificationService
remains untouched for the Phase 2 coaching path.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel

from app.distillation.state import BrainCoveResult
from app.schemas.rag import RetrievedContext

logger = logging.getLogger(__name__)

_HAIKU_MODEL = "claude-haiku-4-5-20251001"


class _VerificationQuestion(BaseModel):
    question: str


class _VerificationAnswerOut(BaseModel):
    answer: Literal["Yes", "No", "Uncertain"]
    reasoning: str


def _build_question_prompt(claim: str) -> str:
    return (
        "Generate exactly ONE yes/no verification question that can be answered "
        "using peer-reviewed biomechanics evidence to test the following "
        "coaching claim. The question must be specific, concrete, and testable.\n\n"
        f"Claim: {claim}"
    )


def _build_verify_prompt(question: str, contexts: list[RetrievedContext]) -> str:
    evidence_text = "\n\n".join(
        f"[Source {i + 1}] {ctx.chunk.title} ({ctx.chunk.year or 'n.d.'}):\n{ctx.chunk.text}"
        for i, ctx in enumerate(contexts)
    )
    return (
        "You are an independent verifier. Using ONLY the retrieved evidence "
        "below, answer the question with Yes, No, or Uncertain. Do NOT rely "
        "on any external knowledge — only the provided sources.\n\n"
        f"Retrieved evidence:\n{evidence_text}\n\n"
        f"Question: {question}\n\n"
        "Provide answer (Yes/No/Uncertain) and a one-sentence reasoning "
        "citing the source number."
    )


class BrainCoveService:
    """Single-claim Chain-of-Verification service for distillation."""

    def __init__(self, *, anthropic_client: Any, instructor_client: Any) -> None:
        self._anthropic_client = anthropic_client
        self._instructor_client = instructor_client

    async def verify_claim(
        self,
        *,
        claim: str,
        contexts: list[RetrievedContext],
    ) -> BrainCoveResult:
        """Verify one coaching claim against retrieved papers_rag contexts."""
        if not contexts:
            return BrainCoveResult(
                verified=False,
                explanation="no_papers_evidence",
                trace=[{"claim": claim, "skipped_reason": "no_papers_evidence"}],
            )

        try:
            question_out: _VerificationQuestion = (
                await self._instructor_client.chat.completions.create(
                    model=_HAIKU_MODEL,
                    max_tokens=256,
                    response_model=_VerificationQuestion,
                    messages=[{"role": "user", "content": _build_question_prompt(claim)}],
                )
            )
            answer_out: _VerificationAnswerOut = (
                await self._instructor_client.chat.completions.create(
                    model=_HAIKU_MODEL,
                    max_tokens=512,
                    response_model=_VerificationAnswerOut,
                    messages=[
                        {
                            "role": "user",
                            "content": _build_verify_prompt(question_out.question, contexts),
                        }
                    ],
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "BrainCoveService.verify_claim failed (%s: %s)",
                type(exc).__name__,
                exc,
            )
            return BrainCoveResult(
                verified=False,
                explanation=f"evaluation_failed: {type(exc).__name__}: {exc}",
                trace=[{"claim": claim, "error": str(exc)}],
            )

        verified = answer_out.answer == "Yes"
        return BrainCoveResult(
            verified=verified,
            explanation=answer_out.reasoning,
            trace=[
                {
                    "claim": claim,
                    "question": question_out.question,
                    "answer": answer_out.answer,
                    "reasoning": answer_out.reasoning,
                }
            ],
        )
