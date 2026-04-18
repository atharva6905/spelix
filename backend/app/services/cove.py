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
    """Build the Step 1 user prompt for claim extraction.

    D-050 (ADR-COVE-02): instructs the extractor to pull principle-level
    biomechanics claims and SKIP lifter-specific measurement values.
    Research sources describe optimal ranges and targets; they cannot
    confirm or refute one lifter's measured value, so measurement claims
    always return Uncertain and block all-Yes convergence.

    D-052 (ADR-COVE-03): adds an inversion-guard and an extrapolation-
    guard to close the gap surfaced by D-050 prod E2E on bench analysis
    ``c46023c9``. The D-050 rule ("do not invent a principle that was
    not written") is too soft against paraphrases that invert polarity
    ("fast descent is bad" → "slow descent is bad") or extrapolate a
    stated optimal range into an invented minimum / maximum / alternative
    reference range. The D-052 additions name both failure modes
    explicitly and add one before/after worked example per guard.
    """
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
        "You are extracting falsifiable factual claims from AI-generated "
        "barbell coaching feedback so they can be verified against "
        "peer-reviewed biomechanics research.\n\n"
        "Extract ONLY PRINCIPLE-LEVEL claims — statements about what is "
        "biomechanically optimal, recommended, or correct for a barbell "
        "lift in general. These describe the SCIENCE of the lift, not the "
        "particular lifter's execution in the analysed session.\n\n"
        "DO NOT extract MEASUREMENT-LEVEL claims — statements about what "
        "THIS lifter's specific values were in the analysed session. "
        "Research sources describe optimal ranges and targets; they "
        "cannot confirm or refute a single lifter's measured value, so "
        "measurement-level claims will always return Uncertain and block "
        "verification convergence.\n\n"
        "When the coaching cites a measured value AND the principle "
        "behind it (e.g. 'your elbow was 38\u00b0, below the 45\u201375\u00b0 optimal'), "
        "extract ONLY the principle ('Optimal bench press elbow angle is "
        "45\u201375\u00b0 from torso') \u2014 never the measurement. If the coaching "
        "cites a measurement without stating any principle, SKIP it; do "
        "not invent a principle that was not written.\n\n"
        "DO NOT invert, reverse, or negate the direction of a principle. "
        "If the coaching says a rushed or fast eccentric descent reduces "
        "time under tension, extract that as-is \u2014 do NOT extract the "
        "opposite (slow descent reduces time under tension). DO NOT "
        "extrapolate beyond what the coaching states. If the coaching "
        "cites an optimal range (e.g. 45\u201375\u00b0 is optimal), extract only "
        "that range \u2014 do NOT invent a minimum, a maximum, or a separate "
        "reference range that the coaching does not state. The extractor "
        "must translate principles, never transform them.\n\n"
        "Worked examples:\n\n"
        "Coaching says: 'Your eccentric phase duration measured 5.16 "
        "seconds.'\n"
        "Extract: nothing (measurement-only; no principle stated).\n\n"
        "Coaching says: 'Your eccentric phase measured 5.16 seconds, "
        "above the 2-second hypertrophy target.'\n"
        "Extract: 'The recommended eccentric phase duration for "
        "hypertrophy training is approximately 2 seconds.'\n\n"
        "Coaching says: 'Elbow angle reached 38\u00b0 at the bottom, below "
        "the optimal 45\u201375\u00b0 range.'\n"
        "Extract: 'Optimal elbow angle at the bottom of the bench press "
        "is 45\u201375\u00b0 from torso.'\n\n"
        "Coaching says: 'A slight diagonal J-curve bar path optimizes "
        "lever arm through the bench press.'\n"
        "Extract: 'A slight diagonal J-curve bar path optimizes the "
        "lever arm through the bench press.'\n\n"
        "Coaching says: 'A rushed, fast eccentric descent reduces time "
        "under tension and compromises the touch point on the chest.'\n"
        "Extract: 'A rushed or fast eccentric descent reduces time under "
        "tension in the bench press.'\n"
        "Do NOT extract: 'A slow eccentric descent reduces time under "
        "tension' \u2014 that inverts the direction of the stated principle.\n\n"
        "Coaching says: 'Optimal elbow angle at the bottom of the bench "
        "press is 45\u201375\u00b0 from the torso.'\n"
        "Extract: 'Optimal elbow angle at the bottom of the bench press "
        "is 45\u201375\u00b0 from the torso.'\n"
        "Do NOT extract: 'Minimum elbow angle is 60\u00b0' or 'Reference "
        "range is 60\u2013100\u00b0' \u2014 the coaching did not state a minimum or "
        "an alternative range; inventing one is extrapolation.\n\n"
        "Return one claim per distinct principle. Do not duplicate the "
        "same principle across issues. Return an empty list if no "
        "principle-level claims are present.\n\n"
        f"Coaching feedback to analyse:\n{text_to_analyse}"
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
        # D-048: bumped 512→1024 for instructor structured-output retry headroom;
        # trivial cost delta for this short-list output (cf. Step 3 at 4096).
        claim_list = await self._instructor_client.chat.completions.create(
            model=HAIKU_MODEL,
            max_tokens=1024,
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
                # D-048: bumped 512→1024 for instructor structured-output retry headroom;
                # trivial cost delta for this short-list output (cf. Step 3 at 4096).
                claim_list = await self._instructor_client.chat.completions.create(
                    model=HAIKU_MODEL,
                    max_tokens=1024,
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
            # D-048: bumped 512→1024 for instructor structured-output retry headroom;
            # trivial cost delta for this short-list output (cf. Step 3 at 4096).
            verification_questions = await self._instructor_client.chat.completions.create(
                model=HAIKU_MODEL,
                max_tokens=1024,
                response_model=VerificationQuestions,
                messages=[
                    {
                        "role": "user",
                        "content": _build_question_generation_prompt(claim_list.claims),
                    }
                ],
            )

            # --- Step 3: independent verification ----------------------------
            # D-048: session 46 + 47 observed truncation at 1024, 2048, and 3072. 4096 is below Haiku 4.5's 8192 cap.
            verification_answers = await self._instructor_client.chat.completions.create(
                model=HAIKU_MODEL,
                max_tokens=4096,
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
                # D-048: 3072 lets Sonnet regenerate a full CoachingOutput without mid-field truncation.
                revised_output = await self._instructor_client.chat.completions.create(
                    model=SONNET_MODEL,
                    max_tokens=3072,
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
                # D-048: 3072 lets Sonnet regenerate a full CoachingOutput without mid-field truncation.
                revised_output = await self._instructor_client.chat.completions.create(
                    model=SONNET_MODEL,
                    max_tokens=3072,
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
