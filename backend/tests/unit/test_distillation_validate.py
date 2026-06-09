"""Unit tests for validate_quality — pure function, no LLM."""

import uuid

import pytest

from app.distillation.state import make_initial_distillation_state
from app.distillation.validate import validate_quality
from app.schemas.coaching import CoachingOutput


# ---------------------------------------------------------------------------
# Parametrized gate matrix — the single instrument for decision-routing logic
# (FR-BRAIN-06). Add a row here when thresholds change; do not add named tests
# for the same assertion.
#
# Columns: overall, correctness (None = key absent), expected decision
#
# Row IDs document the scenario so failures are self-describing.
#
# M-02 regression guards (security-review finding, Session 60): the pass path
# and its sub-gate routing are load-bearing — Phase 2 prod only populates
# faithfulness, so a silent regression in the Phase 4 overall/correctness path
# would not surface until Phase 4. The pass-band and sub-gate rows below ARE
# the M-02 guards; do not remove them without an equivalent replacement.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("overall", "correctness", "expected"),
    [
        # --- pass band (overall >= 0.85 AND correctness >= 0.8) ---
        pytest.param(0.9,  0.85, "pass",   id="pass-both-above-thresholds"),
        pytest.param(0.85, 0.8,  "pass",   id="pass-both-at-exact-boundary"),
        # --- review: correctness sub-gate fails while overall is in pass band ---
        pytest.param(0.85, 0.79, "review", id="review-correctness-just-below-gate"),
        pytest.param(0.90, 0.75, "review", id="review-high-overall-correctness-below-gate"),
        pytest.param(0.90, None, "review", id="review-pass-band-overall-correctness-key-absent"),
        # --- review: overall in review band (0.6 <= overall < 0.85), correctness varies ---
        pytest.param(0.7,  0.7,  "review", id="review-both-mid-band"),
        pytest.param(0.70, 0.85, "review", id="review-low-overall-high-correctness"),
        pytest.param(0.6,  0.6,  "review", id="review-both-at-lower-boundary"),
        # --- reject: overall below 0.6 floor ---
        pytest.param(0.59, 0.6,  "reject", id="reject-overall-just-below-floor"),
        pytest.param(0.3,  0.9,  "reject", id="reject-overall-well-below-floor-correctness-high"),
        # --- reject: overall present and below floor, correctness key absent ---
        pytest.param(0.40, None, "reject", id="reject-overall-below-floor-no-correctness-key"),
    ],
)
@pytest.mark.asyncio
async def test_validate_quality_gate_matrix(
    overall: float, correctness: float | None, expected: str
) -> None:
    scores: dict = {"overall": overall}
    if correctness is not None:
        scores["correctness"] = correctness
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores=scores,
    )
    update = await validate_quality(state)
    assert update["validation_decision"] == expected


# ---------------------------------------------------------------------------
# Edge-case tests — these test structural anomalies in eval_scores that the
# matrix cannot express as simple (overall, correctness) rows.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_quality_missing_scores_rejects() -> None:
    """Empty eval_scores dict — no keys at all — must reject."""
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={},
    )
    update = await validate_quality(state)
    assert update["validation_decision"] == "reject"


@pytest.mark.asyncio
async def test_validate_quality_falls_back_to_faithfulness_when_overall_absent() -> None:
    """Phase 2 only populates eval_scores.faithfulness (ADR-RAG-04). Until the
    Phase 4 RAGAS aggregate ships an `overall` key, validate_quality must
    fall back to `faithfulness` so distillation candidates are written instead
    of being silently rejected. Regression guard from prod 2026-04-17."""
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="bench",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        # Phase 2 prod shape — no `overall`, only `faithfulness`
        eval_scores={"faithfulness": 0.92, "faithfulness_passed": True},
    )
    update = await validate_quality(state)
    # 0.92 is above 0.6 floor but no `correctness` so route to review,
    # not pass — the candidates still flow through.
    assert update["validation_decision"] == "review"


@pytest.mark.asyncio
async def test_validate_quality_faithfulness_below_floor_rejects() -> None:
    """Faithfulness fallback also respects the 0.6 floor."""
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="bench",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"faithfulness": 0.4},
    )
    update = await validate_quality(state)
    assert update["validation_decision"] == "reject"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_coaching_output() -> CoachingOutput:
    return CoachingOutput(
        summary="s",
        strengths=["Consistent tempo"],
        issues=[],
        correction_plan=["Maintain neutral spine throughout the lift."],
        recommended_cues=[],
        citations=[],
        safety_warnings=[],
        confidence_level="High",
        dimension_addressed="Movement Quality",
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )


