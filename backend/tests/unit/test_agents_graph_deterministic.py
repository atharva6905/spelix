"""Unit tests for the deterministic coaching StateGraph."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.graph import build_deterministic_graph, run_coaching_graph
from app.agents.state import make_initial_state
from app.schemas.coaching import CoachingOutput


def _make_output() -> CoachingOutput:
    return CoachingOutput(
        summary="summary text.",
        strengths=["good form"],
        correction_plan=["spread the floor"],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=100,
        raw_completion_tokens=50,
    )


class _FakeCoveResult:
    def __init__(self, output):
        self.output = output
        self.cove_verified = True
        self.iterations_run = 1
        self.trace = [{"iteration": 1, "converged": True}]


def _make_deps():
    rep_row = SimpleNamespace(rep_index=0, metrics_json={"depth_angle": 92.0})
    rep_metric_repo = SimpleNamespace(get_by_analysis=AsyncMock(return_value=[rep_row]))

    papers_ctx = SimpleNamespace(
        collection="papers_rag",
        score=0.9,
        chunk=SimpleNamespace(id="p1", text="research", title="t", authors=[], year=2024, doi=None),
    )
    retrieval_svc = SimpleNamespace(hybrid_search=AsyncMock(return_value=[papers_ctx]))

    thresholds = SimpleNamespace(all_for_exercise=lambda e: {})

    analysis_repo = SimpleNamespace(list_recent_by_user=AsyncMock(return_value=[]))

    output = _make_output()
    coaching_svc = SimpleNamespace(
        generate_coaching_streaming=AsyncMock(return_value=output),
    )
    cove_svc = SimpleNamespace(verify=AsyncMock(return_value=_FakeCoveResult(output)))
    fg_svc = SimpleNamespace(
        evaluate=AsyncMock(
            return_value=SimpleNamespace(score=0.91, passed=True, unsupported_claims=[])
        )
    )

    return {
        "rep_metric_repo": rep_metric_repo,
        "retrieval_svc": retrieval_svc,
        "thresholds": thresholds,
        "analysis_repo": analysis_repo,
        "coaching_svc": coaching_svc,
        "cove_svc": cove_svc,
        "fg_svc": fg_svc,
        "pubsub_redis": SimpleNamespace(publish=AsyncMock()),
    }


@pytest.mark.asyncio
async def test_deterministic_graph_runs_full_flow_end_to_end():
    deps = _make_deps()
    graph = build_deterministic_graph(**deps)

    initial = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
    )

    final_state = await graph.ainvoke(initial)

    # Every expected tool ran
    assert len(final_state["rep_metrics"]) == 1
    assert len(final_state["papers_contexts"]) == 1
    assert final_state["coaching_output"] is not None
    # CoVe ran + eval scores populated
    assert final_state["cove_verified"] is True
    assert final_state["eval_scores"]["faithfulness"] == 0.91
    # Trace has one NodeEvent per executed node
    assert len(final_state["trace"]) >= 7  # tools + gen + validate + cove + safety + fg


@pytest.mark.asyncio
async def test_deterministic_graph_marks_degraded_when_retrieval_returns_empty():
    deps = _make_deps()
    # Wipe retrieval results.
    deps["retrieval_svc"].hybrid_search = AsyncMock(return_value=[])
    graph = build_deterministic_graph(**deps)

    initial = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
    )

    final_state = await graph.ainvoke(initial)

    # Coaching still ran but without contexts.
    assert final_state["coaching_output"] is not None
    # CoVe + faithfulness were skipped (no contexts).
    assert "faithfulness" not in final_state["eval_scores"]




@pytest.mark.asyncio
async def test_run_coaching_graph_returns_enriched_trace_payload():
    deps = _make_deps()

    final = await run_coaching_graph(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        body_stats={"height_cm": 180},
        keyframe_analysis_text="kf notes",
        mode="deterministic",
        **deps,
    )

    # Returns (state, trace_for_storage, coaching_output).
    state, trace_payload, coaching_output = final

    assert state["coaching_output"] is coaching_output
    assert coaching_output is not None
    assert trace_payload["mode"] == "deterministic"
    assert trace_payload["converged"] is True
    assert len(trace_payload["nodes_executed"]) >= 7
    # All required fields present.
    assert "cove_iterations" in trace_payload
    assert "eval_scores" in trace_payload
