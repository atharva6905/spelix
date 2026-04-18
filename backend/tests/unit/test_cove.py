"""Unit tests for CoveVerificationService — P2-014.

Requirements: FR-AICP-08 Stage 2

Tests verify the 4-step CoVe loop: claim extraction → question generation →
independent verification → revision. All LLM calls are mocked via
instructor.from_anthropic. Never calls the real Anthropic API.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.coaching import CoachingOutput, Issue
from app.schemas.rag import ChunkPayload, RetrievedContext
from app.services.cove import (
    HAIKU_MODEL,
    SONNET_MODEL,
    ClaimList,
    CoveResult,
    CoveVerificationService,
    VerificationAnswer,
    VerificationAnswers,
    VerificationQuestions,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MANDATORY_DISCLAIMER = (
    "This feedback is for educational purposes only and is not a substitute "
    "for in-person coaching or medical advice."
)


def _make_coaching_output(summary: str = "Good overall form.") -> CoachingOutput:
    """Return a minimal valid CoachingOutput for testing."""
    return CoachingOutput(
        summary=summary,
        strengths=["Neutral spine maintained throughout."],
        issues=[
            Issue(
                rep_number=1,
                joint="Left knee",
                description="Slight forward knee tracking during descent phase.",
                severity="Low",
            )
        ],
        correction_plan=["Focus on driving knees out during descent."],
        disclaimer=MANDATORY_DISCLAIMER,
        raw_prompt_tokens=100,
        raw_completion_tokens=200,
    )


def _make_retrieved_context() -> RetrievedContext:
    """Return a minimal valid RetrievedContext for testing."""
    return RetrievedContext(
        chunk=ChunkPayload(
            id="abc123",
            text="Knee tracking in the sagittal plane is critical for squat mechanics.",
            paper_id="paper-001",
            chunk_index=0,
            section="methods",
            token_count=20,
            quality_tier="L1_systematic_review",
            title="Squat Mechanics Review",
            authors=["Smith J", "Doe A"],
            year=2022,
            doi="10.1234/example",
        ),
        score=0.92,
        collection="papers_rag",
    )


def _make_mock_instructor_client(side_effects: list[Any]) -> MagicMock:
    """Build a mock instructor client whose create method returns side_effects in order."""
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=side_effects)
    return mock_client


# ---------------------------------------------------------------------------
# Test 1: all "Yes" answers → cove_verified=True, no revision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cove_all_yes_verified_true() -> None:
    """When all verification answers are Yes, cove_verified is True.

    Revision (step 4) must NOT be called — only 3 LLM calls total.
    """
    initial_output = _make_coaching_output()
    contexts = [_make_retrieved_context()]

    claims_response = ClaimList(claims=["Knee tracking is observable.", "Depth achieved."])
    questions_response = VerificationQuestions(
        questions=[
            "Does the retrieved evidence support knee tracking claims?",
            "Does the evidence support depth assessment?",
        ]
    )
    answers_response = VerificationAnswers(
        answers=[
            VerificationAnswer(
                question="Does the retrieved evidence support knee tracking claims?",
                answer="Yes",
                reasoning="The cited paper confirms knee tracking methodology.",
            ),
            VerificationAnswer(
                question="Does the evidence support depth assessment?",
                answer="Yes",
                reasoning="Depth criteria are documented in retrieved source.",
            ),
        ]
    )

    mock_instructor = _make_mock_instructor_client(
        [claims_response, questions_response, answers_response]
    )

    anthropic_client = MagicMock()

    with patch("app.services.cove.instructor") as mock_instructor_module:
        mock_instructor_module.from_anthropic.return_value = mock_instructor
        service = CoveVerificationService(anthropic_client=anthropic_client)
        result = await service.verify(
            initial_output=initial_output,
            retrieved_contexts=contexts,
            max_iterations=2,
        )

    assert result.cove_verified is True
    assert result.iterations_run == 1
    # Only 3 calls: claim extraction, question generation, answer verification
    assert mock_instructor.chat.completions.create.call_count == 3
    assert result.output.summary == initial_output.summary


# ---------------------------------------------------------------------------
# Test 2: "No" answer triggers revision; second iteration all "Yes"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cove_no_answer_triggers_revision() -> None:
    """A No answer in iteration 1 triggers revision; iteration 2 converges."""
    initial_output = _make_coaching_output()
    revised_output = _make_coaching_output(summary="Revised: improved movement quality.")
    contexts = [_make_retrieved_context()]

    # Iteration 1
    claims_1 = ClaimList(claims=["Knee tracking observable."])
    questions_1 = VerificationQuestions(questions=["Is knee tracking supported by evidence?"])
    answers_1 = VerificationAnswers(
        answers=[
            VerificationAnswer(
                question="Is knee tracking supported by evidence?",
                answer="No",
                reasoning="Retrieved context does not directly support this claim.",
            )
        ]
    )
    # Step 4: revision returns revised_output

    # Iteration 2
    claims_2 = ClaimList(claims=["Revised claim about movement quality."])
    questions_2 = VerificationQuestions(questions=["Is movement quality claim supported?"])
    answers_2 = VerificationAnswers(
        answers=[
            VerificationAnswer(
                question="Is movement quality claim supported?",
                answer="Yes",
                reasoning="Evidence aligns with the revised claim.",
            )
        ]
    )

    mock_instructor = _make_mock_instructor_client(
        [claims_1, questions_1, answers_1, revised_output, claims_2, questions_2, answers_2]
    )

    anthropic_client = MagicMock()

    with patch("app.services.cove.instructor") as mock_instructor_module:
        mock_instructor_module.from_anthropic.return_value = mock_instructor
        service = CoveVerificationService(anthropic_client=anthropic_client)
        result = await service.verify(
            initial_output=initial_output,
            retrieved_contexts=contexts,
            max_iterations=2,
        )

    assert result.cove_verified is True
    assert result.iterations_run == 2
    assert result.output.summary == "Revised: improved movement quality."


# ---------------------------------------------------------------------------
# Test 3: max iterations exhausted → cove_verified=False, no exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cove_max_iterations_returns_false() -> None:
    """When max iterations are exhausted with persistent No answers, cove_verified is False."""
    initial_output = _make_coaching_output()
    revised_output = _make_coaching_output(summary="Still unverified after revision.")
    contexts = [_make_retrieved_context()]

    def _make_no_iteration(revision_output: CoachingOutput) -> list[Any]:
        """Produce one failing iteration: claims → questions → No answers → revision."""
        claims = ClaimList(claims=["Unverifiable claim."])
        questions = VerificationQuestions(questions=["Is the claim verifiable?"])
        answers = VerificationAnswers(
            answers=[
                VerificationAnswer(
                    question="Is the claim verifiable?",
                    answer="No",
                    reasoning="No supporting evidence found.",
                )
            ]
        )
        return [claims, questions, answers, revision_output]

    # Both iterations fail; revision_output feeds into iteration 2
    side_effects = _make_no_iteration(revised_output) + _make_no_iteration(revised_output)

    mock_instructor = _make_mock_instructor_client(side_effects)

    anthropic_client = MagicMock()

    with patch("app.services.cove.instructor") as mock_instructor_module:
        mock_instructor_module.from_anthropic.return_value = mock_instructor
        service = CoveVerificationService(anthropic_client=anthropic_client)
        result = await service.verify(
            initial_output=initial_output,
            retrieved_contexts=contexts,
            max_iterations=2,
        )

    assert result.cove_verified is False
    assert result.iterations_run == 2
    # No exception — method must always return a CoveResult
    assert isinstance(result, CoveResult)


# ---------------------------------------------------------------------------
# Test 4: empty claims → cove_verified=True immediately, no further calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cove_empty_claims_verified_true() -> None:
    """Empty claim list skips the verification loop entirely."""
    initial_output = _make_coaching_output()
    contexts = [_make_retrieved_context()]

    empty_claims = ClaimList(claims=[])

    mock_instructor = _make_mock_instructor_client([empty_claims])

    anthropic_client = MagicMock()

    with patch("app.services.cove.instructor") as mock_instructor_module:
        mock_instructor_module.from_anthropic.return_value = mock_instructor
        service = CoveVerificationService(anthropic_client=anthropic_client)
        result = await service.verify(
            initial_output=initial_output,
            retrieved_contexts=contexts,
            max_iterations=2,
        )

    assert result.cove_verified is True
    assert result.iterations_run == 0
    # Only the initial claim extraction call, nothing else
    assert mock_instructor.chat.completions.create.call_count == 1


# ---------------------------------------------------------------------------
# Test 5: trace structure contains expected keys per iteration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cove_trace_structure() -> None:
    """Trace must be a list of dicts with keys: iteration, claims, questions, answers, converged."""
    initial_output = _make_coaching_output()
    contexts = [_make_retrieved_context()]

    claims_response = ClaimList(claims=["One verifiable claim."])
    questions_response = VerificationQuestions(questions=["Is the claim verifiable?"])
    answers_response = VerificationAnswers(
        answers=[
            VerificationAnswer(
                question="Is the claim verifiable?",
                answer="Yes",
                reasoning="Evidence supports the claim.",
            )
        ]
    )

    mock_instructor = _make_mock_instructor_client(
        [claims_response, questions_response, answers_response]
    )

    anthropic_client = MagicMock()

    with patch("app.services.cove.instructor") as mock_instructor_module:
        mock_instructor_module.from_anthropic.return_value = mock_instructor
        service = CoveVerificationService(anthropic_client=anthropic_client)
        result = await service.verify(
            initial_output=initial_output,
            retrieved_contexts=contexts,
            max_iterations=2,
        )

    assert isinstance(result.trace, list)
    assert len(result.trace) == 1
    trace_entry = result.trace[0]
    assert "iteration" in trace_entry
    assert "claims" in trace_entry
    assert "questions" in trace_entry
    assert "answers" in trace_entry
    assert "converged" in trace_entry
    assert trace_entry["iteration"] == 1
    assert trace_entry["converged"] is True


# ---------------------------------------------------------------------------
# Test 6: Haiku used for steps 1-3, Sonnet for step 4
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cove_uses_haiku_for_extraction() -> None:
    """Steps 1-3 must use Haiku; step 4 (revision) must use Sonnet."""
    initial_output = _make_coaching_output()
    revised_output = _make_coaching_output(summary="Revised after No answer.")
    contexts = [_make_retrieved_context()]

    # One failing iteration so revision (step 4) is called
    claims = ClaimList(claims=["A claim that fails verification."])
    questions = VerificationQuestions(questions=["Is the claim supported?"])
    answers = VerificationAnswers(
        answers=[
            VerificationAnswer(
                question="Is the claim supported?",
                answer="No",
                reasoning="No supporting evidence.",
            )
        ]
    )

    # Iteration 2: all Yes, so we can check model usage for step 4
    claims_2 = ClaimList(claims=["Revised claim."])
    questions_2 = VerificationQuestions(questions=["Is revised claim supported?"])
    answers_2 = VerificationAnswers(
        answers=[
            VerificationAnswer(
                question="Is revised claim supported?",
                answer="Yes",
                reasoning="Evidence supports the revised claim.",
            )
        ]
    )

    side_effects = [claims, questions, answers, revised_output, claims_2, questions_2, answers_2]
    mock_instructor = _make_mock_instructor_client(side_effects)

    anthropic_client = MagicMock()
    captured_models: list[str] = []

    original_create = mock_instructor.chat.completions.create

    async def capture_create(**kwargs: Any) -> Any:
        captured_models.append(kwargs.get("model", ""))
        return await original_create(**kwargs)

    mock_instructor.chat.completions.create = capture_create

    with patch("app.services.cove.instructor") as mock_instructor_module:
        mock_instructor_module.from_anthropic.return_value = mock_instructor
        service = CoveVerificationService(anthropic_client=anthropic_client)
        result = await service.verify(
            initial_output=initial_output,
            retrieved_contexts=contexts,
            max_iterations=2,
        )

    # 7 calls total: iter1(claim, question, answer, revision) + iter2(claim, question, answer)
    assert len(captured_models) == 7

    # Steps 1, 2, 3 of iteration 1 → indices 0, 1, 2 → Haiku
    assert captured_models[0] == HAIKU_MODEL
    assert captured_models[1] == HAIKU_MODEL
    assert captured_models[2] == HAIKU_MODEL

    # Step 4 → index 3 → Sonnet
    assert captured_models[3] == SONNET_MODEL

    # Iteration 2: steps 1, 2, 3 → indices 4, 5, 6 → Haiku
    assert captured_models[4] == HAIKU_MODEL
    assert captured_models[5] == HAIKU_MODEL
    assert captured_models[6] == HAIKU_MODEL

    assert result.cove_verified is True


# ---------------------------------------------------------------------------
# D-048: max_tokens headroom tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cove_max_tokens_meets_headroom_happy_path() -> None:
    """D-048: Steps 1-3 max_tokens give Haiku 4.5 headroom against truncation.

    Session 46 + 47 prod E2E on bench-fixture analyses (6aa7b42b, de316a7a)
    both observed VerificationAnswers truncation at max_tokens 1024, 2048,
    and 3072. 4096 sits comfortably below Haiku 4.5's 8192 hard cap and
    leaves room for N=5 claims x ~60-token reasoning with source citations.
    Claim extraction and question generation are short-list outputs but are
    bumped 512 -> 1024 as cheap headroom against instructor's structured-output
    retry loop.
    """
    initial_output = _make_coaching_output()
    contexts = [_make_retrieved_context()]

    claims_response = ClaimList(claims=["c1", "c2"])
    questions_response = VerificationQuestions(questions=["q1?", "q2?"])
    answers_response = VerificationAnswers(
        answers=[
            VerificationAnswer(question="q1?", answer="Yes", reasoning="r1"),
            VerificationAnswer(question="q2?", answer="Yes", reasoning="r2"),
        ]
    )
    mock_client = _make_mock_instructor_client(
        [claims_response, questions_response, answers_response]
    )

    with patch("app.services.cove.instructor.from_anthropic", return_value=mock_client):
        anthropic_client = MagicMock()
        svc = CoveVerificationService(anthropic_client=anthropic_client)
        result: CoveResult = await svc.verify(
            initial_output=initial_output,
            retrieved_contexts=contexts,
            max_iterations=2,
        )

    assert result.cove_verified is True, "happy path must converge on first iter"

    calls = mock_client.chat.completions.create.await_args_list
    assert len(calls) == 3, f"expected 3 calls (claim, question, answer); got {len(calls)}"

    # Step 1: claim extraction
    claim_kwargs = calls[0].kwargs
    assert claim_kwargs["response_model"] is ClaimList
    assert claim_kwargs["max_tokens"] >= 1024, (
        f"claim-extraction max_tokens {claim_kwargs['max_tokens']} < 1024 "
        "-- cheap headroom against instructor structured-output retries (D-048)."
    )

    # Step 2: question generation
    question_kwargs = calls[1].kwargs
    assert question_kwargs["response_model"] is VerificationQuestions
    assert question_kwargs["max_tokens"] >= 1024, (
        f"question-generation max_tokens {question_kwargs['max_tokens']} < 1024 "
        "-- cheap headroom against instructor structured-output retries (D-048)."
    )

    # Step 3: verification answers
    answer_kwargs = calls[2].kwargs
    assert answer_kwargs["response_model"] is VerificationAnswers
    assert answer_kwargs["max_tokens"] >= 4096, (
        f"verification-answer max_tokens {answer_kwargs['max_tokens']} < 4096 "
        "-- session 46 + 47 observed truncation at 1024, 2048, and 3072 on prod "
        "aggregated N-claim VerificationAnswers output (D-048)."
    )


@pytest.mark.asyncio
async def test_cove_max_tokens_meets_headroom_revision_path() -> None:
    """D-048: Step 4 revision max_tokens >= 3072 so Sonnet can regenerate a
    full CoachingOutput (summary + issues + correction_plan + cues + citations
    + disclaimer) without mid-field truncation.
    """
    initial_output = _make_coaching_output()
    contexts = [_make_retrieved_context()]

    claims_response = ClaimList(claims=["c1"])
    questions_response = VerificationQuestions(questions=["q1?"])
    # First verification answer is "No" -> triggers revision.
    failed_answers = VerificationAnswers(
        answers=[
            VerificationAnswer(
                question="q1?",
                answer="No",
                reasoning="Evidence does not support this claim.",
            )
        ]
    )
    # After revision, second iteration's claim extraction returns no claims -> converge.
    revised_output = _make_coaching_output(summary="Revised summary.")
    converged_claims = ClaimList(claims=[])

    mock_client = _make_mock_instructor_client(
        [
            claims_response,         # Step 1 pre-loop
            questions_response,      # Step 2 iter 1
            failed_answers,          # Step 3 iter 1 (No -> revise)
            revised_output,          # Step 4 revision (Sonnet)
            converged_claims,        # Step 1 iter 2 -> empty -> converge
        ]
    )

    with patch("app.services.cove.instructor.from_anthropic", return_value=mock_client):
        anthropic_client = MagicMock()
        svc = CoveVerificationService(anthropic_client=anthropic_client)
        result: CoveResult = await svc.verify(
            initial_output=initial_output,
            retrieved_contexts=contexts,
            max_iterations=2,
        )

    assert result.cove_verified is True, (
        "revision + re-extract with empty claims must converge on iter 2"
    )

    calls = mock_client.chat.completions.create.await_args_list
    assert len(calls) == 5, (
        f"expected 5 calls (pre-loop claim, question, answer, revise, iter2 claim); "
        f"got {len(calls)}"
    )

    # Step 3 answer call (defensive — happy-path test covers this too).
    answer_kwargs = calls[2].kwargs
    assert answer_kwargs["response_model"] is VerificationAnswers
    assert answer_kwargs["max_tokens"] >= 4096, (
        f"verification-answer max_tokens {answer_kwargs['max_tokens']} < 4096 "
        "— defensive regression guard against Step 3 budget drift (D-048)."
    )

    # Step 4 revision is the 4th call
    revision_kwargs = calls[3].kwargs
    assert revision_kwargs["model"] == SONNET_MODEL, (
        f"Step 4 revision must use Sonnet, got {revision_kwargs['model']}"
    )
    assert revision_kwargs["response_model"] is CoachingOutput
    assert revision_kwargs["max_tokens"] >= 3072, (
        f"revision max_tokens {revision_kwargs['max_tokens']} < 3072 "
        "-- Sonnet needs room to regenerate a full CoachingOutput (D-048)."
    )


# ---------------------------------------------------------------------------
# D-050: claim extraction — principle-level only, skip measurements
# ---------------------------------------------------------------------------


def test_claim_extraction_prompt_emphasises_principle_level() -> None:
    """D-050: prompt must explicitly instruct the extractor to pull
    principle-level claims and SKIP lifter-specific measurement claims.

    Session 48 prod E2E on bench analysis ``bfbed270`` observed 26
    VerificationAnswers across 2 iterations. Every principle-claim
    answered Yes with source citation; every measurement-claim answered
    Uncertain ("no specific performance data for any lifter in the
    retrieved evidence"). All-Yes convergence (``cove_verified=true``)
    is structurally unreachable as long as measurement claims are
    extracted. See ADR-COVE-02.
    """
    from app.services.cove import _build_claim_extraction_prompt

    output = _make_coaching_output()
    prompt = _build_claim_extraction_prompt(output)

    lowered = prompt.lower()

    # Must use the words "principle" and "measurement" explicitly so
    # the instruction lands unambiguously for Haiku 4.5.
    assert "principle" in lowered, (
        "Refined prompt must name the PRINCIPLE-level concept explicitly "
        "(D-050 ADR-COVE-02)."
    )
    assert "measurement" in lowered, (
        "Refined prompt must name the MEASUREMENT-level concept explicitly "
        "(D-050 ADR-COVE-02)."
    )

    # Must instruct the extractor to skip / exclude measurement-level
    # claims. Accept several synonyms so the phrasing isn't over-pinned.
    skip_markers = ("skip", "do not extract", "exclude", "not extract")
    assert any(marker in lowered for marker in skip_markers), (
        "Refined prompt must explicitly instruct the extractor to skip "
        "measurement-level claims (any of: skip / do not extract / exclude). "
        "Without this, Haiku 4.5 defaults to extracting measurements and "
        "blocks cove_verified=true (D-050)."
    )


def test_claim_extraction_prompt_includes_worked_examples() -> None:
    """D-050: prompt must contain at least two worked examples so the
    model has concrete anchors, not just abstract rules.

    Pure rule-based instructions are fragile. Concrete examples match
    the observed shape of session 48's coaching output (measurement-only,
    measurement + principle pair, measurement-embedded principle, and
    bare principle).
    """
    from app.services.cove import _build_claim_extraction_prompt

    output = _make_coaching_output()
    prompt = _build_claim_extraction_prompt(output)

    lowered = prompt.lower()

    # "Coaching says" (or equivalent) signals a worked example.
    example_markers = ("coaching says", "example", "e.g.")
    marker_hits = sum(lowered.count(m) for m in example_markers)
    assert marker_hits >= 2, (
        f"Refined prompt must include at least 2 worked examples; "
        f"found {marker_hits} (markers: 'coaching says', 'example', 'e.g.'). "
        "See ADR-COVE-02 for the required example shape."
    )

    # "Extract:" and a skip/empty counterpart should appear at least once
    # each to anchor both the positive and negative pattern.
    assert "extract" in lowered, (
        "Refined prompt must contain an 'Extract:' example line (D-050)."
    )


def test_claim_extraction_prompt_still_references_falsifiability() -> None:
    """D-050 regression guard: the refined prompt must preserve the
    existing falsifiability / testability framing so the extractor
    stays grounded in evidence-based claims rather than drifting into
    motivational or subjective extraction.
    """
    from app.services.cove import _build_claim_extraction_prompt

    output = _make_coaching_output()
    prompt = _build_claim_extraction_prompt(output)

    lowered = prompt.lower()

    falsifiability_markers = (
        "falsifiable",
        "testable",
        "verifiable",
        "peer-reviewed",
        "research",
    )
    assert any(marker in lowered for marker in falsifiability_markers), (
        "Refined prompt must preserve the falsifiability framing; otherwise "
        "the extractor drifts into subjective or motivational claims "
        "(regression guard, D-050)."
    )
