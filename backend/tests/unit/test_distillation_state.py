"""Unit tests for distillation state scaffolding."""

import uuid

from app.distillation.state import (
    BrainCoveResult,
    CandidateInsight,
    LifecycleDecision,
    make_initial_distillation_state,
)


def test_make_initial_state_defaults() -> None:
    analysis_id = uuid.uuid4()
    state = make_initial_distillation_state(
        analysis_id=analysis_id,
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.9, "correctness": 0.85},
    )
    assert state["analysis_id"] == analysis_id
    assert state["candidates"] == []
    assert state["decisions"] == []
    assert state["cove_results"] == []
    assert state["formatted"] == []
    assert state["stored_ids"] == []
    assert state["trace"] == []
    assert state["validation_decision"] == "pass"  # placeholder until validate_quality runs
    assert state["eval_scores"] == {"overall": 0.9, "correctness": 0.85}


def test_candidate_insight_shape() -> None:
    ci = CandidateInsight(
        content="Drive knees out as you descend.",
        exercise="squat",
        phase="descent",
        entry_type="cue",
        trigger_tags=["knee_cave"],
        confidence_score=0.9,
    )
    assert ci.content.startswith("Drive")
    assert ci.trigger_tags == ["knee_cave"]


def test_lifecycle_decision_shape() -> None:
    d = LifecycleDecision(
        decision="UPDATE", nearest_entry_id=uuid.uuid4(), cosine_sim=0.81
    )
    assert d.decision == "UPDATE"


def test_brain_cove_result_shape() -> None:
    r = BrainCoveResult(verified=True, explanation="supported by [1]", trace=[])
    assert r.verified is True


def _stub_coaching_output():
    from app.schemas.coaching import CoachingOutput

    return CoachingOutput(
        summary="Good session overall.",
        strengths=["Solid depth achieved."],
        issues=[],
        correction_plan=["Drive knees out as you descend."],
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
