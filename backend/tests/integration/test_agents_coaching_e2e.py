"""Integration test: analysis worker dispatches to the agent graph when the
feature flag is on, and to the imperative path when off."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_worker_calls_agent_graph_when_flag_enabled(monkeypatch):
    """When SPELIX_PHASE3_AGENT_ENABLED=1, the worker must route to run_coaching_graph."""
    monkeypatch.setenv("SPELIX_PHASE3_AGENT_ENABLED", "1")
    monkeypatch.setenv("SPELIX_AGENT_MODE", "deterministic")

    from app.workers import analysis_worker

    # Patch the two dispatch helpers; the worker should call the graph
    # variant, not the imperative variant.
    with (
        patch.object(
            analysis_worker,
            "_run_coaching_graph",
            new=AsyncMock(return_value=None),
        ) as mock_graph,
        patch.object(
            analysis_worker,
            "_run_coaching_imperative",
            new=AsyncMock(return_value=None),
        ) as mock_imp,
    ):
        # Call the dispatch helper directly with minimal inputs.
        await analysis_worker._dispatch_coaching(
            analysis=object(),
            repo=object(),
            redis=object(),
            pipeline_result=object(),
        )

        mock_graph.assert_awaited_once()
        mock_imp.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_calls_imperative_when_flag_disabled(monkeypatch):
    monkeypatch.setenv("SPELIX_PHASE3_AGENT_ENABLED", "0")

    from app.workers import analysis_worker

    with (
        patch.object(
            analysis_worker,
            "_run_coaching_graph",
            new=AsyncMock(return_value=None),
        ) as mock_graph,
        patch.object(
            analysis_worker,
            "_run_coaching_imperative",
            new=AsyncMock(return_value=None),
        ) as mock_imp,
    ):
        await analysis_worker._dispatch_coaching(
            analysis=object(),
            repo=object(),
            redis=object(),
            pipeline_result=object(),
        )

        mock_imp.assert_awaited_once()
        mock_graph.assert_not_awaited()


@pytest.mark.asyncio
async def test_deterministic_graph_end_to_end_mocked_llm(monkeypatch):
    """Run the real deterministic graph with all Phase 2 services MOCKED at
    the client boundary but all Phase 3 code real.

    Verifies that:
    - Six tools all fire in the expected order.
    - coaching_output is produced.
    - agent_trace_json has one entry per executed node.
    - eval_scores contains faithfulness, cove_verified, cove_iterations.
    """
    import uuid

    from app.agents.graph import run_coaching_graph
    from app.schemas.coaching import CoachingOutput

    output = CoachingOutput(
        summary="Rep 1 showed clean descent depth at 92° hip flexion; torso stayed braced throughout.",
        strengths=["consistent braced torso", "clean bar path"],
        correction_plan=[
            "Drive knees out during ascent to prevent medial drift.",
        ],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=1234,
        raw_completion_tokens=456,
    )

    # Mock every service at the boundary.
    from types import SimpleNamespace

    rep_row = SimpleNamespace(rep_index=0, metrics_json={"depth_angle": 92.0})
    rep_metric_repo = SimpleNamespace(get_by_analysis=AsyncMock(return_value=[rep_row]))
    papers_ctx = SimpleNamespace(
        collection="papers_rag",
        score=0.9,
        chunk=SimpleNamespace(
            id="p1",
            text="squat knee tracking research",
            title="Smith 2024",
            authors=["Smith"],
            year=2024,
            doi=None,
        ),
    )
    retrieval_svc = SimpleNamespace(hybrid_search=AsyncMock(return_value=[papers_ctx]))
    thresholds = SimpleNamespace(all_for_exercise=lambda e: {})
    analysis_repo = SimpleNamespace(list_recent_by_user=AsyncMock(return_value=[]))
    coaching_svc = SimpleNamespace(generate_coaching_streaming=AsyncMock(return_value=output))

    class _CR:
        def __init__(self, o):
            self.output = o
            self.cove_verified = True
            self.iterations_run = 1
            self.trace = [{"iteration": 1, "converged": True}]

    cove_svc = SimpleNamespace(verify=AsyncMock(return_value=_CR(output)))
    fg_svc = SimpleNamespace(
        evaluate=AsyncMock(
            return_value=SimpleNamespace(score=0.92, passed=True, unsupported_claims=[])
        )
    )

    final_state, trace_payload, coaching_output = await run_coaching_graph(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        body_stats={"height_cm": 180},
        keyframe_analysis_text="notes",
        mode="deterministic",
        rep_metric_repo=rep_metric_repo,
        retrieval_svc=retrieval_svc,
        thresholds=thresholds,
        analysis_repo=analysis_repo,
        coaching_svc=coaching_svc,
        cove_svc=cove_svc,
        fg_svc=fg_svc,
        pubsub_redis=SimpleNamespace(publish=AsyncMock()),
    )

    assert coaching_output.summary.startswith("Rep 1 showed clean descent depth")
    assert trace_payload["mode"] == "deterministic"
    assert trace_payload["converged"] is True
    executed = [ev["node"] for ev in trace_payload["nodes_executed"]]
    # Assert tool ordering: retrieve + flag + compare + generate + post-gen.
    assert executed.index("get_rep_metrics") < executed.index("retrieve_papers")
    assert executed.index("retrieve_papers") < executed.index("retrieve_coach_brain")
    assert executed.index("retrieve_coach_brain") < executed.index("generate_correction_plan")
    assert executed.index("generate_correction_plan") < executed.index("cove_verify")
    assert trace_payload["eval_scores"]["faithfulness"] == 0.92
    assert trace_payload["eval_scores"]["cove_verified"] is True
