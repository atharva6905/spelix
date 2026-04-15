"""Unit tests for composable agent tools (FR-AICP-18)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.state import make_initial_state
from app.agents.tools import (
    compare_to_user_history,
    flag_form_deviation,
    generate_correction_plan,
    get_rep_metrics,
    retrieve_coach_brain,
    retrieve_papers,
)
from app.schemas.coaching import CoachingOutput


@pytest.mark.asyncio
async def test_get_rep_metrics_returns_flat_dicts_keyed_by_rep_number():
    analysis_id = uuid.uuid4()
    user_id = uuid.uuid4()
    state = make_initial_state(
        analysis_id=analysis_id,
        user_id=user_id,
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )

    # Mock the repo — RepMetric rows are SimpleNamespace for simplicity.
    rows = [
        SimpleNamespace(rep_index=0, metrics_json={"depth_angle": 92.0}),
        SimpleNamespace(rep_index=1, metrics_json={"depth_angle": 96.5}),
    ]
    rep_metric_repo = SimpleNamespace(get_by_analysis=AsyncMock(return_value=rows))

    update = await get_rep_metrics(state, rep_metric_repo=rep_metric_repo)

    assert update == {
        "rep_metrics": [
            {"rep_number": 1, "depth_angle": 92.0},
            {"rep_number": 2, "depth_angle": 96.5},
        ]
    }
    rep_metric_repo.get_by_analysis.assert_awaited_once_with(analysis_id)


@pytest.mark.asyncio
async def test_get_rep_metrics_handles_empty_result():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    rep_metric_repo = SimpleNamespace(get_by_analysis=AsyncMock(return_value=[]))

    update = await get_rep_metrics(state, rep_metric_repo=rep_metric_repo)

    assert update == {"rep_metrics": []}


@pytest.mark.asyncio
async def test_retrieve_papers_queries_papers_rag_with_exercise_filter():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.82,
    )

    # Mock retrieval service returns a list with `.collection == "papers_rag"`.
    fake_ctx = SimpleNamespace(
        collection="papers_rag",
        score=0.9,
        chunk=SimpleNamespace(
            id="c1",
            text="Squat depth and knee flexion...",
            title="Sample",
        ),
    )
    retrieval_svc = SimpleNamespace(hybrid_search=AsyncMock(return_value=[fake_ctx]))

    update = await retrieve_papers(state, retrieval_svc=retrieval_svc)

    assert update["papers_contexts"] == [fake_ctx]
    retrieval_svc.hybrid_search.assert_awaited_once()
    call = retrieval_svc.hybrid_search.await_args
    assert call.kwargs["collection"] == "papers_rag"
    assert call.kwargs["exercise_filter"] == "squat"
    assert call.kwargs["rerank"] is True


@pytest.mark.asyncio
async def test_retrieve_papers_returns_empty_on_service_error():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.82,
    )

    async def boom(*_a, **_kw):
        raise RuntimeError("qdrant unavailable")

    retrieval_svc = SimpleNamespace(hybrid_search=boom)

    update = await retrieve_papers(state, retrieval_svc=retrieval_svc)

    assert update == {"papers_contexts": [], "degraded_mode": True}


@pytest.mark.asyncio
async def test_retrieve_coach_brain_applies_status_active_filter():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )

    fake_ctx = SimpleNamespace(
        collection="coach_brain",
        score=0.88,
        chunk=SimpleNamespace(id="b1", text="Spread the floor cue", title="Cue"),
    )
    retrieval_svc = SimpleNamespace(hybrid_search=AsyncMock(return_value=[fake_ctx]))

    update = await retrieve_coach_brain(state, retrieval_svc=retrieval_svc)

    assert update["brain_contexts"] == [fake_ctx]
    call = retrieval_svc.hybrid_search.await_args
    assert call.kwargs["collection"] == "coach_brain"
    # Ensure the status=active filter is applied via additional_filters.
    assert call.kwargs["additional_filters"] is not None
    assert len(call.kwargs["additional_filters"]) == 1


@pytest.mark.asyncio
async def test_retrieve_coach_brain_empty_result_cold_start():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    retrieval_svc = SimpleNamespace(hybrid_search=AsyncMock(return_value=[]))

    update = await retrieve_coach_brain(state, retrieval_svc=retrieval_svc)

    assert update == {"brain_contexts": []}




class _FakeThresholds:
    """Minimal stand-in for ThresholdConfig used by flag_form_deviation."""

    def all_for_exercise(self, exercise_type: str) -> dict[str, dict[str, float]]:
        # Return squat depth + lockout angle thresholds.
        return {
            "squat.depth_angle_max": {"value": 95.0, "unit": "deg"},
            "squat.lockout_hip_knee_min": {"value": 165.0, "unit": "deg"},
        }


@pytest.mark.asyncio
async def test_flag_form_deviation_emits_reps_past_depth_threshold():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
    )
    # rep 1 has depth_angle 98 (past 95 threshold → flagged)
    # rep 2 has depth_angle 92 (within threshold → not flagged)
    state["rep_metrics"] = [
        {"rep_number": 1, "depth_angle": 98.0},
        {"rep_number": 2, "depth_angle": 92.0},
    ]

    update = await flag_form_deviation(state, thresholds=_FakeThresholds())

    flagged = update["flagged_deviations"]
    assert len(flagged) == 1
    assert flagged[0]["rep_number"] == 1
    assert flagged[0]["metric"] == "depth_angle"
    assert flagged[0]["observed"] == 98.0
    assert flagged[0]["threshold"] == 95.0
    assert flagged[0]["threshold_key"] == "squat.depth_angle_max"


@pytest.mark.asyncio
async def test_flag_form_deviation_no_flags_when_clean():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
    )
    state["rep_metrics"] = [{"rep_number": 1, "depth_angle": 92.0}]

    update = await flag_form_deviation(state, thresholds=_FakeThresholds())

    assert update == {"flagged_deviations": []}


@pytest.mark.asyncio
async def test_compare_to_user_history_summarizes_recent_analyses():
    user_id = uuid.uuid4()
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=user_id,
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
    )

    recent = [
        SimpleNamespace(
            id=uuid.uuid4(),
            exercise_type="squat",
            exercise_variant="high_bar",
            form_score_overall=6.5,
            form_score_safety=7.0,
            created_at="2026-04-10T12:00:00Z",
        ),
        SimpleNamespace(
            id=uuid.uuid4(),
            exercise_type="squat",
            exercise_variant="high_bar",
            form_score_overall=5.8,
            form_score_safety=6.2,
            created_at="2026-04-08T12:00:00Z",
        ),
    ]
    analysis_repo = SimpleNamespace(list_recent_by_user=AsyncMock(return_value=recent))

    update = await compare_to_user_history(state, analysis_repo=analysis_repo, limit=5)

    summary = update["user_history_summary"]
    assert summary is not None
    assert "2 recent" in summary
    assert "squat" in summary
    # Aggregate scores (mean 6.15 overall, 6.6 movement quality) surface in summary.
    assert "6.1" in summary or "6.2" in summary
    analysis_repo.list_recent_by_user.assert_awaited_once_with(
        user_id,
        limit=5,
        exercise_type="squat",
    )


@pytest.mark.asyncio
async def test_compare_to_user_history_no_history():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
    )
    analysis_repo = SimpleNamespace(list_recent_by_user=AsyncMock(return_value=[]))

    update = await compare_to_user_history(state, analysis_repo=analysis_repo, limit=5)

    assert update == {"user_history_summary": None}


@pytest.mark.asyncio
async def test_generate_correction_plan_invokes_streaming_with_state():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        body_stats={"height_cm": 180},
        keyframe_analysis_text="keyframe notes",
    )
    state["rep_metrics"] = [{"rep_number": 1, "depth_angle": 92}]
    papers_ctx = SimpleNamespace(collection="papers_rag")
    brain_ctx = SimpleNamespace(collection="coach_brain")
    state["papers_contexts"] = [papers_ctx]
    state["brain_contexts"] = [brain_ctx]
    state["retrieval_source"] = "coach_brain_primary"

    expected = CoachingOutput(
        summary="ok summary here.",
        strengths=["good"],
        correction_plan=["cue one"],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=1,
        raw_completion_tokens=1,
    )

    coaching_svc = SimpleNamespace(
        generate_coaching_streaming=AsyncMock(return_value=expected)
    )

    thresholds = SimpleNamespace()  # not used in this path — CoachingService owns
    pubsub_redis = SimpleNamespace()

    update = await generate_correction_plan(
        state,
        coaching_svc=coaching_svc,
        thresholds=thresholds,
        pubsub_redis=pubsub_redis,
    )

    assert update["coaching_output"] is expected
    call_kwargs = coaching_svc.generate_coaching_streaming.await_args.kwargs
    # Contexts are merged (primary first per routing).
    assert call_kwargs["retrieved_contexts"] == [brain_ctx, papers_ctx]
    assert call_kwargs["retrieval_source"] == "coach_brain_primary"
    assert call_kwargs["exercise_type"] == "squat"
    assert call_kwargs["analysis_id"] == state["analysis_id"]
    assert call_kwargs["pubsub_redis"] is pubsub_redis


@pytest.mark.asyncio
async def test_generate_correction_plan_stamps_degraded_mode_flag():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    state["degraded_mode"] = True

    expected = CoachingOutput(
        summary="s.",
        strengths=["g"],
        correction_plan=["c"],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=1,
        raw_completion_tokens=1,
    )
    coaching_svc = SimpleNamespace(
        generate_coaching_streaming=AsyncMock(return_value=expected)
    )

    update = await generate_correction_plan(
        state,
        coaching_svc=coaching_svc,
        thresholds=SimpleNamespace(),
        pubsub_redis=SimpleNamespace(),
    )

    assert update["coaching_output"].degraded_mode is True
