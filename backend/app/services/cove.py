"""CoveVerificationService — Chain-of-Verification for coaching output.

Implements a 4-step CoVe loop that extracts factual claims from a
CoachingOutput, generates verification questions, answers them against
retrieved evidence, and revises the output if any claims fail.

Requirements: FR-AICP-08 Stage 2 (P2-014)

Legal constraint: never write "injury", "diagnose", "treat", or any FDA
SaMD-triggering language in prompts or output strings.

Models:
    Steps 1-3 (claim extraction, question generation, verification):
        claude-haiku-4-5-20251001
    Step 4 (revision):
        claude-sonnet-4-6

Error handling:
    The verify() method never raises. All exceptions are caught and returned
    as CoveResult(cove_verified=False, iterations_run=0, trace=[{"error": ...}]).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import anthropic
import instructor
from pydantic import BaseModel

from app.schemas.coaching import CoachingOutput
from app.schemas.rag import RetrievedContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model constants
# ---------------------------------------------------------------------------

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Intermediate Pydantic models (internal to cove.py — not in schemas/)
# ---------------------------------------------------------------------------


class ClaimList(BaseModel):
    """Falsifiable factual claims extracted from coaching output (Step 1)."""

    claims: list[str]


class VerificationQuestions(BaseModel):
    """Yes/no questions generated for each claim (Step 2)."""

    questions: list[str]


class VerificationAnswer(BaseModel):
    """Answer to a single verification question (Step 3)."""

    question: str
    answer: Literal["Yes", "No", "Uncertain"]
    reasoning: str


class VerificationAnswers(BaseModel):
    """Collection of answers to all verification questions (Step 3)."""

    answers: list[VerificationAnswer]


# ---------------------------------------------------------------------------
# CoveResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class CoveResult:
    """Result returned by CoveVerificationService.verify().

    Attributes
    ----------
    output:
        Final (possibly revised) CoachingOutput.
    cove_verified:
        True if all claims passed verification in at least one iteration.
    iterations_run:
        Number of CoVe loop iterations that executed.
    trace:
        One dict per iteration (stored in agent_trace_json), plus an
        optional {"error": ...} dict on unexpected failure.
    """

    output: CoachingOutput
    cove_verified: bool
    iterations_run: int
    trace: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_claim_extraction_prompt(output: CoachingOutput) -> str:
    """Build the Step 1 user prompt for claim extraction."""
    text_to_analyse = "\n".join(
        [
            f"Summary: {output.summary}",
            "Issues:",
            *[f"  - {issue.description}" for issue in output.issues],
            "Correction plan:",
            *[f"  - {cue}" for cue in output.correction_plan],
        ]
    )
    return (
        "Extract all falsifiable factual claims from the following coaching "
        "feedback. A falsifiable claim is a specific, testable assertion about "
        "movement mechanics, technique, or biomechanics — not a general "
        "observation or subjective comment. Return only claims that could in "
        "principle be confirmed or refuted by peer-reviewed research.\n\n"
        f"{text_to_analyse}"
    )


def _build_question_generation_prompt(claims: list[str]) -> str:
    """Build the Step 2 user prompt for verification question generation."""
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims))
    return (
        "For each claim below, generate exactly one yes/no verification question "
        "that can be answered using only retrieved research evidence. The question "
        "must be specific and directly testable against the evidence.\n\n"
        f"Claims:\n{numbered}\n\n"
        "Return one question per claim in the same order."
    )


def _build_verification_prompt(questions: list[str], contexts: list[RetrievedContext]) -> str:
    """Build the Step 3 user prompt for independent verification."""
    evidence_text = "\n\n".join(
        f"[Source {i + 1}] {ctx.chunk.title} ({ctx.chunk.year or 'n.d.'}):\n{ctx.chunk.text}"
        for i, ctx in enumerate(contexts)
    )
    numbered_qs = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    return (
        "You are an independent verifier. Using ONLY the retrieved evidence "
        "below, answer each question with Yes, No, or Uncertain. You must NOT "
        "rely on any external knowledge — only the provided sources.\n\n"
        f"Retrieved evidence:\n{evidence_text}\n\n"
        f"Questions:\n{numbered_qs}\n\n"
        "For each question provide: the question text, your answer (Yes/No/Uncertain), "
        "and one-sentence reasoning citing the source."
    )


def _build_revision_prompt(
    original_output: CoachingOutput,
    failed_answers: list[VerificationAnswer],
    contexts: list[RetrievedContext],
) -> str:
    """Build the Step 4 user prompt for coaching output revision."""
    failed_claims_text = "\n".join(
        f"- Question: {a.question}\n  Answer: {a.answer}\n  Reasoning: {a.reasoning}"
        for a in failed_answers
    )
    evidence_text = "\n\n".join(
        f"[Source {i + 1}] {ctx.chunk.title} ({ctx.chunk.year or 'n.d.'}):\n{ctx.chunk.text}"
        for i, ctx in enumerate(contexts)
    )
    return (
        "You are a coaching output revisor. The following claims in the original "
        "coaching feedback could not be verified against the retrieved evidence. "
        "Revise the coaching output to remove or correct only those claims, while "
        "preserving all verified content.\n\n"
        "This analysis evaluates Movement Quality, Technique, Path & Balance, and "
        "Control — grounded in peer-reviewed biomechanics research.\n\n"
        f"Original summary: {original_output.summary}\n\n"
        f"Failed/uncertain claims:\n{failed_claims_text}\n\n"
        f"Retrieved evidence:\n{evidence_text}\n\n"
        "Return a complete, revised CoachingOutput. Preserve the mandatory disclaimer "
        "verbatim. Never use the words 'injury', 'diagnose', or 'treat'."
    )


# ---------------------------------------------------------------------------
# CoveVerificationService
# ---------------------------------------------------------------------------


class CoveVerificationService:
    """Chain-of-Verification service for coaching output.

    Extracts falsifiable claims, verifies them against retrieved research
    contexts, and revises the coaching output if any claims fail.

    Parameters
    ----------
    anthropic_client:
        An initialised ``anthropic.AsyncAnthropic`` instance. The service
        wraps it with ``instructor.from_anthropic`` to enable structured
        output extraction.
    """

    def __init__(self, anthropic_client: anthropic.AsyncAnthropic) -> None:
        self._anthropic_client = anthropic_client
        self._instructor_client = instructor.from_anthropic(anthropic_client)

    async def verify(
        self,
        initial_output: CoachingOutput,
        retrieved_contexts: list[RetrievedContext],
        max_iterations: int = 2,
    ) -> CoveResult:
        """Run the CoVe verification loop.

        Parameters
        ----------
        initial_output:
            The coaching output to verify.
        retrieved_contexts:
            Retrieved research chunks used as the evidence base.
        max_iterations:
            Maximum number of claim→question→verify→revise loops.

        Returns
        -------
        CoveResult
            Always returns a CoveResult — never raises.
        """
        try:
            return await self._run_cove_loop(
                initial_output=initial_output,
                retrieved_contexts=retrieved_contexts,
                max_iterations=max_iterations,
            )
        except Exception as exc:
            logger.exception("CoveVerificationService.verify failed unexpectedly")
            return CoveResult(
                output=initial_output,
                cove_verified=False,
                iterations_run=0,
                trace=[{"error": str(exc)}],
            )

    async def _run_cove_loop(
        self,
        initial_output: CoachingOutput,
        retrieved_contexts: list[RetrievedContext],
        max_iterations: int,
    ) -> CoveResult:
        """Internal implementation of the CoVe loop."""
        current_output = initial_output
        trace: list[dict[str, Any]] = []

        # --- Step 1: claim extraction (happens once before the loop) ----------
        claim_list = await self._instructor_client.chat.completions.create(
            model=HAIKU_MODEL,
            max_tokens=512,
            response_model=ClaimList,
            messages=[
                {
                    "role": "user",
                    "content": _build_claim_extraction_prompt(current_output),
                }
            ],
        )

        if not claim_list.claims:
            logger.info("CoveVerificationService: no claims extracted — skipping loop")
            return CoveResult(
                output=current_output,
                cove_verified=True,
                iterations_run=0,
                trace=trace,
            )

        for iteration in range(1, max_iterations + 1):
            # Step 1 on iterations > 1 uses the revised output's claims
            if iteration > 1:
                claim_list = await self._instructor_client.chat.completions.create(
                    model=HAIKU_MODEL,
                    max_tokens=512,
                    response_model=ClaimList,
                    messages=[
                        {
                            "role": "user",
                            "content": _build_claim_extraction_prompt(current_output),
                        }
                    ],
                )
                if not claim_list.claims:
                    trace.append(
                        {
                            "iteration": iteration,
                            "claims": [],
                            "questions": [],
                            "answers": [],
                            "converged": True,
                        }
                    )
                    return CoveResult(
                        output=current_output,
                        cove_verified=True,
                        iterations_run=iteration,
                        trace=trace,
                    )

            # --- Step 2: verification question generation --------------------
            verification_questions = await self._instructor_client.chat.completions.create(
                model=HAIKU_MODEL,
                max_tokens=512,
                response_model=VerificationQuestions,
                messages=[
                    {
                        "role": "user",
                        "content": _build_question_generation_prompt(claim_list.claims),
                    }
                ],
            )

            # --- Step 3: independent verification ----------------------------
            verification_answers = await self._instructor_client.chat.completions.create(
                model=HAIKU_MODEL,
                max_tokens=1024,
                response_model=VerificationAnswers,
                messages=[
                    {
                        "role": "user",
                        "content": _build_verification_prompt(
                            verification_questions.questions,
                            retrieved_contexts,
                        ),
                    }
                ],
            )

            # --- Convergence check -------------------------------------------
            failed = [
                a
                for a in verification_answers.answers
                if a.answer in ("No", "Uncertain")
            ]
            converged = len(failed) == 0

            trace.append(
                {
                    "iteration": iteration,
                    "claims": claim_list.claims,
                    "questions": verification_questions.questions,
                    "answers": [a.model_dump() for a in verification_answers.answers],
                    "converged": converged,
                }
            )

            if converged:
                return CoveResult(
                    output=current_output,
                    cove_verified=True,
                    iterations_run=iteration,
                    trace=trace,
                )

            # --- Step 4: revision (only when not converged and more iterations remain) ---
            if iteration < max_iterations:
                revised_output = await self._instructor_client.chat.completions.create(
                    model=SONNET_MODEL,
                    max_tokens=2048,
                    response_model=CoachingOutput,
                    messages=[
                        {
                            "role": "user",
                            "content": _build_revision_prompt(
                                current_output,
                                failed,
                                retrieved_contexts,
                            ),
                        }
                    ],
                )
                current_output = revised_output
            else:
                # Final iteration exhausted — run revision anyway for latest output
                revised_output = await self._instructor_client.chat.completions.create(
                    model=SONNET_MODEL,
                    max_tokens=2048,
                    response_model=CoachingOutput,
                    messages=[
                        {
                            "role": "user",
                            "content": _build_revision_prompt(
                                current_output,
                                failed,
                                retrieved_contexts,
                            ),
                        }
                    ],
                )
                current_output = revised_output

        # Max iterations exhausted without convergence
        return CoveResult(
            output=current_output,
            cove_verified=False,
            iterations_run=max_iterations,
            trace=trace,
        )
