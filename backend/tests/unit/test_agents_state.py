"""Unit tests for AgentState TypedDict and NodeEvent model."""

from __future__ import annotations

import uuid
from typing import get_type_hints

from app.agents.state import AgentState, NodeEvent, make_initial_state


def test_make_initial_state_populates_required_fields():
    analysis_id = uuid.uuid4()
    user_id = uuid.uuid4()

    state = make_initial_state(
        analysis_id=analysis_id,
        user_id=user_id,
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.87,
        mode="deterministic",
    )

    assert state["analysis_id"] == analysis_id
    assert state["user_id"] == user_id
    assert state["exercise_type"] == "squat"
    assert state["exercise_variant"] == "high_bar"
    assert state["confidence_score"] == 0.87
    assert state["mode"] == "deterministic"
    assert state["trace"] == []
    assert state["rep_metrics"] == []
    assert state["papers_contexts"] == []
    assert state["brain_contexts"] == []
    assert state["flagged_deviations"] == []
    assert state["retrieval_source"] is None
    assert state["coaching_output"] is None
    assert state["cove_verified"] is False
    assert state["eval_scores"] == {}
    assert state["degraded_mode"] is False
    assert state["user_history_summary"] is None


def test_node_event_serializes_to_plain_dict():
    event = NodeEvent(
        node="get_rep_metrics",
        started_at="2026-04-15T12:00:00Z",
        duration_ms=12.5,
        output_keys=["rep_metrics"],
        error=None,
    )
    dumped = event.model_dump()
    assert dumped == {
        "node": "get_rep_metrics",
        "started_at": "2026-04-15T12:00:00Z",
        "duration_ms": 12.5,
        "output_keys": ["rep_metrics"],
        "error": None,
        "tool_calls_invoked": None,
    }


def test_agent_state_has_typed_mode_field():
    hints = get_type_hints(AgentState)
    # Confirms mode is a typed field — LangGraph relies on TypedDict introspection.
    assert "mode" in hints
