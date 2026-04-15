"""LangGraph StateGraph assembly for the Phase 3 coaching agent.

Two graph modes live here:
- ``build_deterministic_graph``: FR-AICP-18 conditional-edge flow.
  Executes tools in a fixed sequence: rep_metrics -> retrieve_papers ->
  retrieve_coach_brain -> flag_form_deviation -> compare_to_user_history
  -> generate_correction_plan -> validate_output -> cove_verify ->
  safety_filter -> faithfulness_gate -> END.
- ``build_adaptive_graph``: FR-AICP-19 tool-calling flow — single
  ``reasoner`` node with ``ChatAnthropic.bind_tools`` picks the next tool
  by docstring. Built in a later task.

``run_coaching_graph`` is the entry point the worker calls: builds the
requested graph, invokes it, and returns the final AgentState.
"""

from __future__ import annotations

import datetime as _dt
import logging
import time
from typing import Any, Awaitable, Callable

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    node_cove_verify,
    node_faithfulness_gate,
    node_safety_filter,
    node_validate_output,
)
from app.agents.state import AgentState, NodeEvent
from app.agents.tools import (
    compare_to_user_history,
    flag_form_deviation,
    generate_correction_plan,
    get_rep_metrics,
    retrieve_coach_brain,
    retrieve_papers,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tracing helper
# ---------------------------------------------------------------------------


def _wrap_trace(
    node_name: str,
    inner: Callable[[AgentState], Awaitable[dict[str, Any]]],
) -> Callable[[AgentState], Awaitable[dict[str, Any]]]:
    """Return a wrapper that appends a NodeEvent to ``state['trace']``."""

    async def _wrapped(state: AgentState) -> dict[str, Any]:
        started_at = _dt.datetime.now(_dt.UTC).isoformat()
        t0 = time.monotonic()
        try:
            update = await inner(state)
        except Exception as exc:
            duration_ms = (time.monotonic() - t0) * 1000.0
            event = NodeEvent(
                node=node_name,
                started_at=started_at,
                duration_ms=duration_ms,
                output_keys=[],
                error=str(exc),
            )
            logger.exception("node %s raised", node_name)
            # Append event + re-raise — graph catches at ainvoke level.
            trace = list(state.get("trace") or [])
            trace.append(event.model_dump())
            raise
        duration_ms = (time.monotonic() - t0) * 1000.0
        event = NodeEvent(
            node=node_name,
            started_at=started_at,
            duration_ms=duration_ms,
            output_keys=sorted(update.keys()),
            error=None,
        )
        # Append the new event to the existing trace list.
        trace = list(state.get("trace") or [])
        trace.append(event.model_dump())
        merged: dict[str, Any] = dict(update)
        merged["trace"] = trace
        return merged

    return _wrapped


# ---------------------------------------------------------------------------
# Deterministic graph (FR-AICP-18)
# ---------------------------------------------------------------------------


def build_deterministic_graph(
    *,
    rep_metric_repo: Any,
    retrieval_svc: Any,
    thresholds: Any,
    analysis_repo: Any,
    coaching_svc: Any,
    cove_svc: Any,
    fg_svc: Any,
    pubsub_redis: Any,
) -> Any:
    """Build + compile the deterministic coaching graph.

    Returns a compiled ``StateGraph`` instance whose ``.ainvoke(state)``
    runs the full coaching pipeline with conditional edges (no LLM-driven
    tool choice).
    """

    # Bind deps via closures.
    async def _get_rep_metrics(state: AgentState) -> dict[str, Any]:
        return await get_rep_metrics(state, rep_metric_repo=rep_metric_repo)

    async def _retrieve_papers(state: AgentState) -> dict[str, Any]:
        return await retrieve_papers(state, retrieval_svc=retrieval_svc)

    async def _retrieve_coach_brain(state: AgentState) -> dict[str, Any]:
        return await retrieve_coach_brain(state, retrieval_svc=retrieval_svc)

    async def _flag_form_deviation(state: AgentState) -> dict[str, Any]:
        return await flag_form_deviation(state, thresholds=thresholds)

    async def _compare_to_user_history(state: AgentState) -> dict[str, Any]:
        return await compare_to_user_history(state, analysis_repo=analysis_repo)

    async def _generate_correction_plan(state: AgentState) -> dict[str, Any]:
        return await generate_correction_plan(
            state,
            coaching_svc=coaching_svc,
            thresholds=thresholds,
            pubsub_redis=pubsub_redis,
        )

    async def _node_cove(state: AgentState) -> dict[str, Any]:
        return await node_cove_verify(state, cove_svc=cove_svc)

    async def _node_fg(state: AgentState) -> dict[str, Any]:
        return await node_faithfulness_gate(state, fg_svc=fg_svc)

    builder = StateGraph(AgentState)

    builder.add_node("get_rep_metrics", _wrap_trace("get_rep_metrics", _get_rep_metrics))
    builder.add_node("retrieve_papers", _wrap_trace("retrieve_papers", _retrieve_papers))
    builder.add_node(
        "retrieve_coach_brain", _wrap_trace("retrieve_coach_brain", _retrieve_coach_brain)
    )
    builder.add_node(
        "flag_form_deviation", _wrap_trace("flag_form_deviation", _flag_form_deviation)
    )
    builder.add_node(
        "compare_to_user_history",
        _wrap_trace("compare_to_user_history", _compare_to_user_history),
    )
    builder.add_node(
        "generate_correction_plan",
        _wrap_trace("generate_correction_plan", _generate_correction_plan),
    )
    builder.add_node("validate_output", _wrap_trace("validate_output", node_validate_output))
    builder.add_node("cove_verify", _wrap_trace("cove_verify", _node_cove))
    builder.add_node("safety_filter", _wrap_trace("safety_filter", node_safety_filter))
    builder.add_node("faithfulness_gate", _wrap_trace("faithfulness_gate", _node_fg))

    # Topology: sequential retrieve -> flag -> compare -> generate -> post-gen.
    # Parallel retrieval (papers + brain via two edges from the same source)
    # is NOT straightforward in LangGraph without Send-API fanout; we run
    # sequentially for the deterministic graph. The cost is ~1s extra for
    # the second rerank round-trip, acceptable for Batch 1.
    builder.add_edge(START, "get_rep_metrics")
    builder.add_edge("get_rep_metrics", "retrieve_papers")
    builder.add_edge("retrieve_papers", "retrieve_coach_brain")
    builder.add_edge("retrieve_coach_brain", "flag_form_deviation")
    builder.add_edge("flag_form_deviation", "compare_to_user_history")
    builder.add_edge("compare_to_user_history", "generate_correction_plan")
    builder.add_edge("generate_correction_plan", "validate_output")
    builder.add_edge("validate_output", "cove_verify")
    builder.add_edge("cove_verify", "safety_filter")
    builder.add_edge("safety_filter", "faithfulness_gate")
    builder.add_edge("faithfulness_gate", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Adaptive graph — placeholder; implemented in Task 13.
# ---------------------------------------------------------------------------


def build_adaptive_graph(**kwargs: Any) -> Any:
    """Adaptive graph (FR-AICP-19) — implemented in Task 13."""
    raise NotImplementedError("adaptive graph — see Task 13")
