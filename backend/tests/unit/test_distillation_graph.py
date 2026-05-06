"""M-14: distillation graph must pass RunnableConfig, not bare untyped dict.

Also covers _wrap_trace success and error branches, and build_distillation_graph
node wiring (coverage uplift).
"""

from unittest.mock import AsyncMock, patch
import uuid

import pytest


@pytest.mark.asyncio
async def test_distillation_ainvoke_receives_runnable_config_fields():
    """The config passed to ainvoke must carry run_name and tags for LangSmith tracing."""
    captured_configs: list = []

    async def fake_ainvoke(state, config):
        captured_configs.append(config)
        return {
            "stored_ids": [],
            "formatted": [],
            "trace": [],
            "validation_decision": "pass",
            "decisions": [],
            "candidates": [],
        }

    mock_graph = AsyncMock()
    mock_graph.ainvoke.side_effect = fake_ainvoke

    with patch(
        "app.distillation.graph.build_distillation_graph", return_value=mock_graph
    ):
        from app.distillation.graph import run_distillation_graph
        from app.schemas.coaching import CoachingOutput

        coaching_output = CoachingOutput(
            summary="Test summary",
            strengths=["Good depth"],
            issues=[],
            correction_plan=["Keep chest up"],
            disclaimer=(
                "This feedback is for educational purposes only and is not a "
                "substitute for in-person coaching or medical advice."
            ),
            raw_prompt_tokens=0,
            raw_completion_tokens=0,
        )

        analysis_id = uuid.uuid4()

        await run_distillation_graph(
            analysis_id=analysis_id,
            exercise_type="squat",
            coaching_output=coaching_output,
            retrieved_papers_contexts=[],
            eval_scores={"overall": 0.8},
            anthropic_client=AsyncMock(),
            instructor_client=AsyncMock(),
            cohere_client=AsyncMock(),
            qdrant_client=AsyncMock(),
            brain_embedding_svc=AsyncMock(),
            cove_service_factory=AsyncMock,
            db_session=AsyncMock(),
        )

    assert len(captured_configs) == 1
    config = captured_configs[0]
    assert "run_name" in config, "RunnableConfig must include run_name for LangSmith"
    assert config["run_name"] == "spelix-distillation"
    assert "tags" in config, "RunnableConfig must include tags for LangSmith"
    assert "distillation" in config["tags"]
    assert f"analysis:{analysis_id}" in config["tags"]
    assert "recursion_limit" in config


# ---------------------------------------------------------------------------
# _wrap_trace — success and error branches (coverage uplift)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wrap_trace_success_appends_event_to_trace():
    """_wrap_trace wraps a coroutine and appends a NodeEvent with error=None on success."""
    from app.distillation.graph import _wrap_trace

    async def _inner(state):
        return {"result_key": "ok"}

    wrapped = _wrap_trace("test_node", _inner)
    state = {"trace": []}

    result = await wrapped(state)

    assert "trace" in result
    assert len(result["trace"]) == 1
    event = result["trace"][0]
    assert event["node"] == "test_node"
    assert event["error"] is None
    assert "result_key" in event["output_keys"]
    assert result["result_key"] == "ok"


@pytest.mark.asyncio
async def test_wrap_trace_error_appends_event_and_reraises():
    """_wrap_trace catches exceptions, records them in trace, then re-raises."""
    from app.distillation.graph import _wrap_trace

    async def _failing(state):
        raise RuntimeError("node exploded")

    wrapped = _wrap_trace("failing_node", _failing)
    state = {"trace": []}

    with pytest.raises(RuntimeError, match="node exploded"):
        await wrapped(state)

    # Even though it raised, the trace was mutated on state before the re-raise
    assert len(state["trace"]) == 1
    event = state["trace"][0]
    assert event["node"] == "failing_node"
    assert "node exploded" in event["error"]


@pytest.mark.asyncio
async def test_wrap_trace_handles_none_trace():
    """_wrap_trace initialises trace from None correctly."""
    from app.distillation.graph import _wrap_trace

    async def _inner(state):
        return {"key": "value"}

    wrapped = _wrap_trace("node_x", _inner)
    state = {}  # no "trace" key

    result = await wrapped(state)

    assert len(result["trace"]) == 1
    assert result["trace"][0]["node"] == "node_x"


# ---------------------------------------------------------------------------
# build_distillation_graph — verifies the graph compiles without error
# ---------------------------------------------------------------------------


def test_build_distillation_graph_compiles():
    """build_distillation_graph must return a compiled graph without raising."""
    from app.distillation.graph import build_distillation_graph

    graph = build_distillation_graph(
        anthropic_client=AsyncMock(),
        instructor_client=AsyncMock(),
        cohere_client=AsyncMock(),
        qdrant_client=AsyncMock(),
        brain_embedding_svc=AsyncMock(),
        cove_service=AsyncMock(),
        db_session=AsyncMock(),
    )

    assert graph is not None


@pytest.mark.asyncio
async def test_build_distillation_graph_executes_all_nodes_on_pass():
    """build_distillation_graph's inner node closures are invoked when ainvoke runs."""
    from unittest.mock import patch

    from app.distillation.graph import build_distillation_graph
    from app.distillation.state import make_initial_distillation_state
    from app.schemas.coaching import CoachingOutput

    coaching_output = CoachingOutput(
        summary="ok",
        strengths=["Good form"],
        issues=[],
        correction_plan=["Keep chest up"],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )

    initial = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=coaching_output,
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.8},
    )

    with (
        patch(
            "app.distillation.graph.extract_insights",
            new=AsyncMock(return_value={"extracted_cues": []}),
        ),
        patch(
            "app.distillation.graph.validate_quality",
            new=AsyncMock(return_value={"validation_decision": "pass"}),
        ),
        patch(
            "app.distillation.graph.lifecycle_decision",
            new=AsyncMock(return_value={"decisions": []}),
        ),
        patch(
            "app.distillation.graph.cove_verify",
            new=AsyncMock(return_value={"cove_verified": True}),
        ),
        patch(
            "app.distillation.graph.format_entry",
            new=AsyncMock(return_value={"formatted": []}),
        ),
        patch(
            "app.distillation.graph.store_entry",
            new=AsyncMock(return_value={"stored_ids": []}),
        ),
    ):
        graph = build_distillation_graph(
            anthropic_client=AsyncMock(),
            instructor_client=AsyncMock(),
            cohere_client=AsyncMock(),
            qdrant_client=AsyncMock(),
            brain_embedding_svc=AsyncMock(),
            cove_service=AsyncMock(),
            db_session=AsyncMock(),
        )
        from app.config_constants import DISTILLATION_RECURSION_LIMIT

        final = await graph.ainvoke(
            initial, {"recursion_limit": DISTILLATION_RECURSION_LIMIT}
        )

    assert final is not None


@pytest.mark.asyncio
async def test_build_distillation_graph_reject_path():
    """When validate_quality returns reject, the graph routes to END via the reject edge."""
    from unittest.mock import patch

    from app.distillation.graph import build_distillation_graph
    from app.distillation.state import make_initial_distillation_state
    from app.schemas.coaching import CoachingOutput

    coaching_output = CoachingOutput(
        summary="ok",
        strengths=["Good form"],
        issues=[],
        correction_plan=["Keep chest up"],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )

    initial = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="bench",
        coaching_output=coaching_output,
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.3},
    )

    with (
        patch(
            "app.distillation.graph.extract_insights",
            new=AsyncMock(return_value={"extracted_cues": []}),
        ),
        patch(
            "app.distillation.graph.validate_quality",
            new=AsyncMock(return_value={"validation_decision": "reject"}),
        ),
    ):
        graph = build_distillation_graph(
            anthropic_client=AsyncMock(),
            instructor_client=AsyncMock(),
            cohere_client=AsyncMock(),
            qdrant_client=AsyncMock(),
            brain_embedding_svc=AsyncMock(),
            cove_service=AsyncMock(),
            db_session=AsyncMock(),
        )
        from app.config_constants import DISTILLATION_RECURSION_LIMIT

        final = await graph.ainvoke(
            initial, {"recursion_limit": DISTILLATION_RECURSION_LIMIT}
        )

    # On reject path, lifecycle/cove/format/store are never called
    assert final.get("validation_decision") == "reject"
