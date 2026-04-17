"""Unit tests for validate_quality — pure function, no LLM."""

import uuid

import pytest

from app.distillation.state import make_initial_distillation_state
from app.distillation.validate import validate_quality
from app.schemas.coaching import CoachingOutput


@pytest.mark.parametrize(
    ("overall", "correctness", "expected"),
    [
        (0.9, 0.85, "pass"),
        (0.85, 0.8, "pass"),           # boundary
        (0.85, 0.79, "review"),        # correctness just below gate
        (0.7, 0.7, "review"),
        (0.6, 0.6, "review"),          # boundary
        (0.59, 0.6, "reject"),
        (0.3, 0.9, "reject"),
    ],
)
@pytest.mark.asyncio
async def test_validate_quality_gate_matrix(
    overall: float, correctness: float, expected: str
) -> None:
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"overall": overall, "correctness": correctness},
    )
    update = await validate_quality(state)
    assert update["validation_decision"] == expected


@pytest.mark.asyncio
async def test_validate_quality_missing_scores_rejects() -> None:
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={},
    )
    update = await validate_quality(state)
    assert update["validation_decision"] == "reject"


def _stub_coaching_output():
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
