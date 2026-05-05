"""Unit tests for post-generation agent nodes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.agents.nodes import (
    node_cove_verify,
    node_faithfulness_gate,
    node_safety_filter,
    node_validate_output,
)
from app.agents.state import make_initial_state
from app.schemas.coaching import CoachingOutput


def _make_output() -> CoachingOutput:
    return CoachingOutput(
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


@pytest.mark.asyncio
async def test_node_validate_output_no_op_when_no_contexts():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    state["coaching_output"] = _make_output()
    state["papers_contexts"] = []
    state["brain_contexts"] = []

    update = await node_validate_output(state)
    assert update == {}


@pytest.mark.asyncio
async def test_node_cove_verify_applies_service_result(monkeypatch):
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    state["coaching_output"] = _make_output()
    state["papers_contexts"] = [SimpleNamespace(collection="papers_rag")]

    @dataclass
    class _CoveResult:
        output: CoachingOutput
        cove_verified: bool
        iterations_run: int
        trace: list[dict[str, Any]] = field(default_factory=list)

    revised = _make_output().model_copy(update={"summary": "revised."})
    cove_result = _CoveResult(
        output=revised,
        cove_verified=True,
        iterations_run=1,
        trace=[{"iteration": 1, "converged": True}],
    )
    cove_svc = SimpleNamespace(verify=AsyncMock(return_value=cove_result))

    update = await node_cove_verify(state, cove_svc=cove_svc)

    assert update["coaching_output"].summary == "revised."
    assert update["cove_verified"] is True
    assert update["eval_scores"]["cove_verified"] is True
    assert update["eval_scores"]["cove_iterations"] == 1


@pytest.mark.asyncio
async def test_node_safety_filter_applies_result(monkeypatch):
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    state["coaching_output"] = _make_output()

    # Inject SafetyFilter result via monkeypatch.
    sf_result = SimpleNamespace(
        output=_make_output().model_copy(update={"summary": "filtered."}),
        injected_disclaimer=False,
        phrases_replaced=0,
    )

    def _fake_apply(output):
        return sf_result

    import app.agents.nodes as nodes_mod

    monkeypatch.setattr(nodes_mod.SafetyFilter, "apply", staticmethod(_fake_apply))

    update = await node_safety_filter(state)

    assert update["coaching_output"].summary == "filtered."


@pytest.mark.asyncio
async def test_node_faithfulness_gate_populates_eval_scores():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    state["coaching_output"] = _make_output()
    state["papers_contexts"] = [SimpleNamespace(collection="papers_rag")]

    fg_result = SimpleNamespace(
        score=0.92,
        passed=True,
        unsupported_claims=[],
    )
    fg_svc = SimpleNamespace(evaluate=AsyncMock(return_value=fg_result))

    update = await node_faithfulness_gate(state, fg_svc=fg_svc)

    assert update["eval_scores"]["faithfulness"] == 0.92
    assert update["eval_scores"]["faithfulness_passed"] is True
    assert update["eval_scores"]["unsupported_claims"] == []
    assert update["eval_scores"]["evaluator"] == "claude-sonnet-4-6-llm-judge"
    assert update["eval_scores"]["threshold"] == 0.8


# ---------------------------------------------------------------------------
# Exception handler branch coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_node_validate_output_logs_invalid_citations(monkeypatch):
    """When validate returns has_invalid_citations=True, warning is logged."""
    from types import SimpleNamespace
    from unittest.mock import patch

    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    state["coaching_output"] = _make_output()
    state["papers_contexts"] = [SimpleNamespace(collection="papers_rag")]

    validate_result = SimpleNamespace(
        has_invalid_citations=True,
        invalid_indices={9},
        output=_make_output(),
    )

    import app.agents.nodes as nodes_mod

    with patch("app.agents.nodes.build_citation_blocks", return_value=[]):
        with patch.object(
            nodes_mod.ValidateOutputTool, "validate", return_value=validate_result
        ):
            update = await node_validate_output(state)

    assert "coaching_output" in update


@pytest.mark.asyncio
async def test_node_validate_output_exception_returns_empty():
    """Exception in node_validate_output is swallowed — returns {}."""
    from unittest.mock import patch

    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    state["coaching_output"] = _make_output()
    state["papers_contexts"] = [SimpleNamespace(collection="papers_rag")]


    with patch("app.agents.nodes.build_citation_blocks", side_effect=RuntimeError("boom")):
        update = await node_validate_output(state)

    assert update == {}


@pytest.mark.asyncio
async def test_node_cove_verify_exception_returns_empty():
    """Exception in node_cove_verify is swallowed — returns {}."""
    from types import SimpleNamespace

    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    state["coaching_output"] = _make_output()
    state["papers_contexts"] = [SimpleNamespace(collection="papers_rag")]

    cove_svc = SimpleNamespace(verify=AsyncMock(side_effect=RuntimeError("cove exploded")))

    update = await node_cove_verify(state, cove_svc=cove_svc)

    assert update == {}


@pytest.mark.asyncio
async def test_node_safety_filter_logs_when_disclaimer_injected(monkeypatch):
    """When injected_disclaimer=True, warning is logged (covers line 103)."""
    from types import SimpleNamespace

    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    state["coaching_output"] = _make_output()

    sf_result = SimpleNamespace(
        output=_make_output(),
        injected_disclaimer=True,
        phrases_replaced=1,
    )

    import app.agents.nodes as nodes_mod

    monkeypatch.setattr(nodes_mod.SafetyFilter, "apply", staticmethod(lambda output: sf_result))

    update = await node_safety_filter(state)

    assert "coaching_output" in update


@pytest.mark.asyncio
async def test_node_safety_filter_exception_returns_empty(monkeypatch):
    """Exception in node_safety_filter is swallowed — returns {}."""
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    state["coaching_output"] = _make_output()

    import app.agents.nodes as nodes_mod

    def _raising_apply(output):
        raise RuntimeError("filter exploded")

    monkeypatch.setattr(nodes_mod.SafetyFilter, "apply", staticmethod(_raising_apply))

    update = await node_safety_filter(state)

    assert update == {}


@pytest.mark.asyncio
async def test_node_faithfulness_gate_exception_returns_empty():
    """Exception in node_faithfulness_gate is swallowed — returns {}."""
    from types import SimpleNamespace

    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    state["coaching_output"] = _make_output()
    state["papers_contexts"] = [SimpleNamespace(collection="papers_rag")]

    fg_svc = SimpleNamespace(evaluate=AsyncMock(side_effect=RuntimeError("fg exploded")))

    update = await node_faithfulness_gate(state, fg_svc=fg_svc)

    assert update == {}
