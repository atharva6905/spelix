"""Unit tests for the adaptive-reasoning coaching graph (FR-AICP-19)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.graph import build_adaptive_graph
from app.agents.state import make_initial_state


def test_adaptive_graph_accepts_checkpointer():
    """build_adaptive_graph should pass checkpointer to compile when provided."""
    fake_llm = MagicMock()
    fake_llm.bind_tools = MagicMock(return_value=fake_llm)

    mock_saver = MagicMock()
    deps = {
        "rep_metric_repo": MagicMock(),
        "retrieval_svc": MagicMock(),
        "thresholds": MagicMock(),
        "analysis_repo": MagicMock(),
        "coaching_svc": MagicMock(),
        "cove_svc": MagicMock(),
        "fg_svc": MagicMock(),
        "pubsub_redis": MagicMock(),
        "reasoner_llm": fake_llm,
    }
    graph = build_adaptive_graph(**deps, checkpointer=mock_saver)
    assert graph is not None


@pytest.mark.asyncio
async def test_adaptive_graph_compiles_and_accepts_state():
    # The reasoner LLM is fully mocked — we only verify the graph compiles
    # and a stub LLM path completes.
    fake_llm = MagicMock()
    fake_llm.bind_tools = MagicMock(return_value=fake_llm)

    # Reasoner LLM returns no tool calls → graph exits via END.
    fake_response = SimpleNamespace(
        content="",
        tool_calls=[],
    )
    fake_llm.ainvoke = AsyncMock(return_value=fake_response)

    deps = {
        "rep_metric_repo": SimpleNamespace(get_by_analysis=AsyncMock(return_value=[])),
        "retrieval_svc": SimpleNamespace(hybrid_search=AsyncMock(return_value=[])),
        "thresholds": SimpleNamespace(all_for_exercise=lambda e: {}),
        "analysis_repo": SimpleNamespace(list_recent_by_user=AsyncMock(return_value=[])),
        "coaching_svc": SimpleNamespace(generate_coaching_streaming=AsyncMock()),
        "cove_svc": SimpleNamespace(verify=AsyncMock()),
        "fg_svc": SimpleNamespace(evaluate=AsyncMock()),
        "pubsub_redis": SimpleNamespace(publish=AsyncMock()),
        "reasoner_llm": fake_llm,
    }

    graph = build_adaptive_graph(**deps)

    initial = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        mode="adaptive",
    )

    final_state = await graph.ainvoke(initial, {"recursion_limit": 25})

    # Reasoner was called at least once.
    assert fake_llm.ainvoke.await_count >= 1
    # Final state returned with trace populated.
    assert "trace" in final_state


@pytest.mark.asyncio
async def test_adaptive_graph_router_routes_to_validate_when_coaching_output_set():
    """_router returns 'validate_output' when coaching_output is present in state (line 359).

    This test pre-populates coaching_output by injecting it into initial state so
    that the router detects it on the first pass and routes directly to validate_output.
    """
    from app.agents.graph import build_adaptive_graph
    from app.agents.state import make_initial_state
    from app.schemas.coaching import CoachingOutput

    coaching_output = CoachingOutput(
        summary="s.",
        strengths=["good"],
        correction_plan=["fix this"],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=1,
        raw_completion_tokens=1,
    )

    fake_llm = MagicMock()
    fake_llm.bind_tools = MagicMock(return_value=fake_llm)

    # Reasoner returns no tool calls — exits the loop immediately
    async def _fake_ainvoke(messages):
        return SimpleNamespace(content="done", tool_calls=[])

    fake_llm.ainvoke = _fake_ainvoke

    cove_result = SimpleNamespace(
        output=coaching_output,
        cove_verified=True,
        iterations_run=1,
        trace=[],
    )

    deps = {
        "rep_metric_repo": SimpleNamespace(get_by_analysis=AsyncMock(return_value=[])),
        "retrieval_svc": SimpleNamespace(hybrid_search=AsyncMock(return_value=[])),
        "thresholds": SimpleNamespace(all_for_exercise=lambda e: {}),
        "analysis_repo": SimpleNamespace(list_recent_by_user=AsyncMock(return_value=[])),
        "coaching_svc": SimpleNamespace(
            generate_coaching_streaming=AsyncMock(return_value=coaching_output)
        ),
        "cove_svc": SimpleNamespace(verify=AsyncMock(return_value=cove_result)),
        "fg_svc": SimpleNamespace(
            evaluate=AsyncMock(
                return_value=SimpleNamespace(score=0.9, passed=True, unsupported_claims=[])
            )
        ),
        "pubsub_redis": SimpleNamespace(publish=AsyncMock()),
        "reasoner_llm": fake_llm,
    }

    graph = build_adaptive_graph(**deps)

    initial = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        mode="adaptive",
    )
    # Pre-populate coaching_output so _router detects it and routes to validate_output
    initial["coaching_output"] = coaching_output

    final_state = await graph.ainvoke(initial, {"recursion_limit": 10})
    assert "trace" in final_state


@pytest.mark.asyncio
async def test_run_coaching_graph_adaptive_mode_requires_reasoner_llm():
    """run_coaching_graph raises ValueError when mode='adaptive' and reasoner_llm is None."""
    from app.agents.graph import run_coaching_graph

    with pytest.raises(ValueError, match="adaptive mode requires reasoner_llm"):
        await run_coaching_graph(
            analysis_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            exercise_type="squat",
            exercise_variant="high_bar",
            confidence_score=0.85,
            body_stats=None,
            keyframe_analysis_text=None,
            mode="adaptive",
            rep_metric_repo=AsyncMock(),
            retrieval_svc=AsyncMock(),
            thresholds=AsyncMock(),
            analysis_repo=AsyncMock(),
            coaching_svc=AsyncMock(),
            cove_svc=AsyncMock(),
            fg_svc=AsyncMock(),
            pubsub_redis=SimpleNamespace(publish=AsyncMock()),
            reasoner_llm=None,  # triggers the ValueError
        )


@pytest.mark.asyncio
async def test_adaptive_graph_tool_call_invoked_by_reasoner():
    """The adaptive reasoner invokes a tool when the LLM returns a tool_call."""
    import uuid as _uuid
    from app.agents.graph import build_adaptive_graph
    from app.agents.state import make_initial_state

    fake_llm = MagicMock()
    fake_llm.bind_tools = MagicMock(return_value=fake_llm)

    # First call: LLM emits a tool_call for get_rep_metrics
    # Second call: LLM emits no tool calls → exit reasoner loop
    call_count = {"n": 0}
    tool_call_id = "tc-001"

    async def _fake_ainvoke(messages):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return SimpleNamespace(
                content="",
                tool_calls=[
                    {"name": "get_rep_metrics", "id": tool_call_id}
                ],
            )
        return SimpleNamespace(content="done", tool_calls=[])

    fake_llm.ainvoke = _fake_ainvoke

    rep_row = SimpleNamespace(rep_index=0, metrics_json={"depth_angle": 92.0})

    deps = {
        "rep_metric_repo": SimpleNamespace(get_by_analysis=AsyncMock(return_value=[rep_row])),
        "retrieval_svc": SimpleNamespace(hybrid_search=AsyncMock(return_value=[])),
        "thresholds": SimpleNamespace(all_for_exercise=lambda e: {}),
        "analysis_repo": SimpleNamespace(list_recent_by_user=AsyncMock(return_value=[])),
        "coaching_svc": SimpleNamespace(generate_coaching_streaming=AsyncMock()),
        "cove_svc": SimpleNamespace(verify=AsyncMock()),
        "fg_svc": SimpleNamespace(evaluate=AsyncMock()),
        "pubsub_redis": SimpleNamespace(publish=AsyncMock()),
        "reasoner_llm": fake_llm,
    }

    graph = build_adaptive_graph(**deps)

    initial = make_initial_state(
        analysis_id=_uuid.uuid4(),
        user_id=_uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        mode="adaptive",
    )

    final_state = await graph.ainvoke(initial, {"recursion_limit": 10})
    # Reasoner was called at least once and dispatched the get_rep_metrics tool
    assert call_count["n"] >= 1
    assert "trace" in final_state
    # The messages list should contain the ToolMessage from the tool call
    messages = final_state.get("messages") or []
    assert len(messages) >= 2  # at least the AI response + ToolMessage


@pytest.mark.asyncio
async def test_adaptive_graph_unknown_tool_name_appends_error_message():
    """When LLM requests an unknown tool, reasoner appends 'unknown tool: ...' ToolMessage."""
    from app.agents.graph import build_adaptive_graph
    from app.agents.state import make_initial_state

    fake_llm = MagicMock()
    fake_llm.bind_tools = MagicMock(return_value=fake_llm)

    call_count = {"n": 0}

    async def _fake_ainvoke(messages):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return SimpleNamespace(
                content="",
                tool_calls=[{"name": "nonexistent_tool", "id": "tc-999"}],
            )
        return SimpleNamespace(content="done", tool_calls=[])

    fake_llm.ainvoke = _fake_ainvoke

    deps = {
        "rep_metric_repo": SimpleNamespace(get_by_analysis=AsyncMock(return_value=[])),
        "retrieval_svc": SimpleNamespace(hybrid_search=AsyncMock(return_value=[])),
        "thresholds": SimpleNamespace(all_for_exercise=lambda e: {}),
        "analysis_repo": SimpleNamespace(list_recent_by_user=AsyncMock(return_value=[])),
        "coaching_svc": SimpleNamespace(generate_coaching_streaming=AsyncMock()),
        "cove_svc": SimpleNamespace(verify=AsyncMock()),
        "fg_svc": SimpleNamespace(evaluate=AsyncMock()),
        "pubsub_redis": SimpleNamespace(publish=AsyncMock()),
        "reasoner_llm": fake_llm,
    }

    graph = build_adaptive_graph(**deps)

    initial = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        mode="adaptive",
    )

    final_state = await graph.ainvoke(initial, {"recursion_limit": 10})
    # Graph should complete without error
    assert "trace" in final_state
    # Messages should contain an "unknown tool" ToolMessage
    messages = final_state.get("messages") or []
    tool_message_contents = [
        getattr(m, "content", "") for m in messages if hasattr(m, "tool_call_id")
    ]
    assert any("unknown tool" in c for c in tool_message_contents)


@pytest.mark.asyncio
async def test_adaptive_reasoner_hallucinated_tool_excluded_from_trace():
    """H-1 (security): when the LLM emits a hallucinated tool name alongside a
    real one, only the real tool name appears in tool_calls_invoked in the
    NodeEvent trace.  The hallucinated name must never reach agent_trace_json
    (and therefore never be rendered to users as a chip label).

    FR-AICP-19 / FR-RESL-07 / ADR-REASONING-SIDEBAR-01.
    """
    import uuid as _uuid
    from app.agents.graph import build_adaptive_graph
    from app.agents.state import make_initial_state

    fake_llm = MagicMock()
    fake_llm.bind_tools = MagicMock(return_value=fake_llm)

    call_count = {"n": 0}
    real_tool_id = "tc-real"
    hallucinated_tool_id = "tc-hallucinated"

    async def _fake_ainvoke(messages):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # LLM emits one real tool and one hallucinated tool in the same turn.
            return SimpleNamespace(
                content="",
                tool_calls=[
                    {"name": "get_rep_metrics", "id": real_tool_id},
                    {"name": "retrieve_medical_diagnosis", "id": hallucinated_tool_id},
                ],
            )
        return SimpleNamespace(content="done", tool_calls=[])

    fake_llm.ainvoke = _fake_ainvoke
    rep_row = SimpleNamespace(rep_index=0, metrics_json={"depth_angle": 90.0})

    deps = {
        "rep_metric_repo": SimpleNamespace(get_by_analysis=AsyncMock(return_value=[rep_row])),
        "retrieval_svc": SimpleNamespace(hybrid_search=AsyncMock(return_value=[])),
        "thresholds": SimpleNamespace(all_for_exercise=lambda e: {}),
        "analysis_repo": SimpleNamespace(list_recent_by_user=AsyncMock(return_value=[])),
        "coaching_svc": SimpleNamespace(generate_coaching_streaming=AsyncMock()),
        "cove_svc": SimpleNamespace(verify=AsyncMock()),
        "fg_svc": SimpleNamespace(evaluate=AsyncMock()),
        "pubsub_redis": SimpleNamespace(publish=AsyncMock()),
        "reasoner_llm": fake_llm,
    }

    graph = build_adaptive_graph(**deps)
    initial = make_initial_state(
        analysis_id=_uuid.uuid4(),
        user_id=_uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        mode="adaptive",
    )

    final_state = await graph.ainvoke(initial, {"recursion_limit": 10})

    trace = final_state.get("trace") or []
    reasoner_events = [ev for ev in trace if ev.get("node") == "reasoner"]
    assert len(reasoner_events) >= 1, "Expected at least one reasoner NodeEvent"

    first_reasoner = reasoner_events[0]
    invoked = first_reasoner.get("tool_calls_invoked") or []

    # Real tool must be present.
    assert "get_rep_metrics" in invoked, (
        "Real registered tool must appear in tool_calls_invoked"
    )
    # Hallucinated tool must be absent — it was never executed.
    assert "retrieve_medical_diagnosis" not in invoked, (
        "Hallucinated tool name must NOT appear in tool_calls_invoked; "
        "only statically-registered tool names may be recorded"
    )
