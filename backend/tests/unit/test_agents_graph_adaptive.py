"""Unit tests for the adaptive-reasoning coaching graph (FR-AICP-19)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.graph import build_adaptive_graph
from app.agents.state import make_initial_state


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
