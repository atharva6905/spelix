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

import asyncio  # noqa: F401 — used at runtime in wait_for()
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
            logger.exception(
                "node %s raised after %.1fms: %s",
                node_name, duration_ms, exc,
            )
            # Mutate the state dict in-place so LangGraph's post-exception
            # state reflects the failed-node record. State is a plain dict —
            # mutation survives the raise.
            state["trace"] = [*(state.get("trace") or []), event.model_dump()]
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
# Adaptive graph (FR-AICP-19)
# ---------------------------------------------------------------------------


def build_adaptive_graph(
    *,
    rep_metric_repo: Any,
    retrieval_svc: Any,
    thresholds: Any,
    analysis_repo: Any,
    coaching_svc: Any,
    cove_svc: Any,
    fg_svc: Any,
    pubsub_redis: Any,
    reasoner_llm: Any,
) -> Any:
    """Build + compile the adaptive-reasoning graph (FR-AICP-19).

    A single ``reasoner`` node calls an LLM (Claude Sonnet 4.6 bound to the
    six composable tools) in a loop. The LLM reads tool docstrings to
    decide which tool to invoke next; when it emits a response with no
    tool calls, the graph exits. Post-generation nodes (validate, cove,
    safety, faithfulness) run unconditionally after the reasoner loop.

    ``reasoner_llm`` is injected for testability — production callers
    pass ``ChatAnthropic(model="claude-sonnet-4-6", temperature=0)``.
    """
    from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel

    # Per-tool arg schemas: no LLM-facing args — the state is the
    # Blackboard. Tools read from state, write partial updates.
    class _NoArgs(BaseModel):
        pass

    # Shared mutable handle so the tool closures see the latest state.
    state_box: dict[str, Any] = {"state": None}

    async def _tool_get_rep_metrics() -> str:
        update = await get_rep_metrics(state_box["state"], rep_metric_repo=rep_metric_repo)
        state_box["state"] = {**state_box["state"], **update}
        return f"rep_metrics populated: {len(update['rep_metrics'])} reps"

    async def _tool_retrieve_papers() -> str:
        update = await retrieve_papers(state_box["state"], retrieval_svc=retrieval_svc)
        state_box["state"] = {**state_box["state"], **update}
        return f"papers_contexts populated: {len(update['papers_contexts'])} passages"

    async def _tool_retrieve_coach_brain() -> str:
        update = await retrieve_coach_brain(state_box["state"], retrieval_svc=retrieval_svc)
        state_box["state"] = {**state_box["state"], **update}
        return f"brain_contexts populated: {len(update['brain_contexts'])} entries"

    async def _tool_flag_form_deviation() -> str:
        update = await flag_form_deviation(state_box["state"], thresholds=thresholds)
        state_box["state"] = {**state_box["state"], **update}
        return f"flagged_deviations: {len(update['flagged_deviations'])} flags"

    async def _tool_compare_to_user_history() -> str:
        update = await compare_to_user_history(state_box["state"], analysis_repo=analysis_repo)
        state_box["state"] = {**state_box["state"], **update}
        return f"user_history_summary: {update['user_history_summary'] or 'none'}"

    async def _tool_generate_correction_plan() -> str:
        update = await generate_correction_plan(
            state_box["state"],
            coaching_svc=coaching_svc,
            thresholds=thresholds,
            pubsub_redis=pubsub_redis,
        )
        state_box["state"] = {**state_box["state"], **update}
        return "coaching_output populated"

    tools_for_llm = [
        StructuredTool.from_function(
            coroutine=_tool_get_rep_metrics,
            name="get_rep_metrics",
            description=(get_rep_metrics.__doc__ or "").strip(),
            args_schema=_NoArgs,
        ),
        StructuredTool.from_function(
            coroutine=_tool_retrieve_papers,
            name="retrieve_papers",
            description=(retrieve_papers.__doc__ or "").strip(),
            args_schema=_NoArgs,
        ),
        StructuredTool.from_function(
            coroutine=_tool_retrieve_coach_brain,
            name="retrieve_coach_brain",
            description=(retrieve_coach_brain.__doc__ or "").strip(),
            args_schema=_NoArgs,
        ),
        StructuredTool.from_function(
            coroutine=_tool_flag_form_deviation,
            name="flag_form_deviation",
            description=(flag_form_deviation.__doc__ or "").strip(),
            args_schema=_NoArgs,
        ),
        StructuredTool.from_function(
            coroutine=_tool_compare_to_user_history,
            name="compare_to_user_history",
            description=(compare_to_user_history.__doc__ or "").strip(),
            args_schema=_NoArgs,
        ),
        StructuredTool.from_function(
            coroutine=_tool_generate_correction_plan,
            name="generate_correction_plan",
            description=(generate_correction_plan.__doc__ or "").strip(),
            args_schema=_NoArgs,
        ),
    ]

    llm_bound = reasoner_llm.bind_tools(tools_for_llm)

    async def reasoner(state: AgentState) -> dict[str, Any]:
        state_box["state"] = dict(state)  # snapshot for tools

        messages: list[BaseMessage] = list(state.get("messages") or [])
        if not messages:
            # Seed conversation with the task description.
            task_prompt = _build_adaptive_task_prompt(state)
            messages = [HumanMessage(content=task_prompt)]

        response = await llm_bound.ainvoke(messages)
        messages.append(response)

        # If the LLM chose tools, invoke them in order, append ToolMessages.
        tool_calls = getattr(response, "tool_calls", None) or []
        for tc in tool_calls:
            tool_name = tc["name"] if isinstance(tc, dict) else tc.name
            tool_fn = next((t for t in tools_for_llm if t.name == tool_name), None)
            if tool_fn is None:
                messages.append(
                    ToolMessage(
                        content=f"unknown tool: {tool_name}",
                        tool_call_id=tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", ""),
                    )
                )
                continue
            try:
                # ainvoke dispatches to the bound coroutine with JSON args.
                # Our _NoArgs schema has no fields, so {} is the correct payload.
                result = await tool_fn.ainvoke({})
            except Exception as exc:
                result = f"tool error: {exc}"
            messages.append(
                ToolMessage(
                    content=str(result),
                    tool_call_id=tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", ""),
                )
            )

        # Merge any state updates produced by tools back into return.
        return {
            "messages": messages,
            **{k: v for k, v in state_box["state"].items() if k not in state},
        }

    def _router(state: AgentState) -> str:
        """If the last AI message has no tool calls OR we have a coaching_output, proceed to post-gen. Else loop."""
        if state.get("coaching_output") is not None:
            return "validate_output"
        messages = state.get("messages") or []
        if messages:
            last = messages[-1]
            tool_calls = getattr(last, "tool_calls", None)
            if not tool_calls:
                # LLM emitted a plain response — coaching_output was not set,
                # treat as end. Guard against infinite loop.
                return "validate_output"
        return "reasoner"

    async def _node_cove(state: AgentState) -> dict[str, Any]:
        return await node_cove_verify(state, cove_svc=cove_svc)

    async def _node_fg(state: AgentState) -> dict[str, Any]:
        return await node_faithfulness_gate(state, fg_svc=fg_svc)

    builder = StateGraph(AgentState)
    builder.add_node("reasoner", _wrap_trace("reasoner", reasoner))
    builder.add_node("validate_output", _wrap_trace("validate_output", node_validate_output))
    builder.add_node("cove_verify", _wrap_trace("cove_verify", _node_cove))
    builder.add_node("safety_filter", _wrap_trace("safety_filter", node_safety_filter))
    builder.add_node("faithfulness_gate", _wrap_trace("faithfulness_gate", _node_fg))

    builder.add_edge(START, "reasoner")
    builder.add_conditional_edges(
        "reasoner",
        _router,
        {"reasoner": "reasoner", "validate_output": "validate_output"},
    )
    builder.add_edge("validate_output", "cove_verify")
    builder.add_edge("cove_verify", "safety_filter")
    builder.add_edge("safety_filter", "faithfulness_gate")
    builder.add_edge("faithfulness_gate", END)

    return builder.compile()


async def run_coaching_graph(
    *,
    analysis_id: Any,
    user_id: Any,
    exercise_type: str,
    exercise_variant: str,
    confidence_score: float,
    body_stats: dict[str, Any] | None,
    keyframe_analysis_text: str | None,
    mode: str,
    rep_metric_repo: Any,
    retrieval_svc: Any,
    thresholds: Any,
    analysis_repo: Any,
    coaching_svc: Any,
    cove_svc: Any,
    fg_svc: Any,
    pubsub_redis: Any,
    reasoner_llm: Any | None = None,
) -> tuple[AgentState, dict[str, Any], Any]:
    """Entry-point called from the worker.

    Builds the requested graph mode (``deterministic`` or ``adaptive``),
    invokes it with an initial state, and returns
    ``(final_state, trace_payload_for_jsonb, coaching_output)`` where
    ``trace_payload_for_jsonb`` is the shape persisted to
    ``coaching_results.agent_trace_json``.
    """
    from app.agents.state import make_initial_state
    from app.agents.tracing import run_config_for_analysis, serialize_trace_for_storage

    initial = make_initial_state(
        analysis_id=analysis_id,
        user_id=user_id,
        exercise_type=exercise_type,
        exercise_variant=exercise_variant,
        confidence_score=confidence_score,
        mode=mode,  # type: ignore[arg-type]
        body_stats=body_stats,
        keyframe_analysis_text=keyframe_analysis_text,
    )

    if mode == "adaptive":
        if reasoner_llm is None:
            raise ValueError("adaptive mode requires reasoner_llm")
        graph = build_adaptive_graph(
            rep_metric_repo=rep_metric_repo,
            retrieval_svc=retrieval_svc,
            thresholds=thresholds,
            analysis_repo=analysis_repo,
            coaching_svc=coaching_svc,
            cove_svc=cove_svc,
            fg_svc=fg_svc,
            pubsub_redis=pubsub_redis,
            reasoner_llm=reasoner_llm,
        )
    else:
        graph = build_deterministic_graph(
            rep_metric_repo=rep_metric_repo,
            retrieval_svc=retrieval_svc,
            thresholds=thresholds,
            analysis_repo=analysis_repo,
            coaching_svc=coaching_svc,
            cove_svc=cove_svc,
            fg_svc=fg_svc,
            pubsub_redis=pubsub_redis,
        )

    config = run_config_for_analysis(
        analysis_id=str(analysis_id),
        user_id=str(user_id),
        mode=mode,
    )
    # NFR-RELI-09: recursion_limit=15, with asyncio.wait_for(timeout=60.0).
    config["recursion_limit"] = 15

    final_state = await asyncio.wait_for(
        graph.ainvoke(initial, config), timeout=60.0
    )

    serialized_nodes = serialize_trace_for_storage(final_state.get("trace") or [])

    trace_payload: dict[str, Any] = {
        "mode": mode,
        "nodes_executed": serialized_nodes,
        "eval_scores": final_state.get("eval_scores") or {},
        "cove_iterations": (final_state.get("eval_scores") or {}).get(
            "cove_trace", []
        ),
        "converged": bool(final_state.get("cove_verified")),
        "retrieval_source": final_state.get("retrieval_source"),
        "degraded_mode": bool(final_state.get("degraded_mode")),
    }

    return final_state, trace_payload, final_state.get("coaching_output")


def _build_adaptive_task_prompt(state: AgentState) -> str:
    """Return the seed instruction for the adaptive reasoner."""
    return (
        "You are the Spelix coaching agent. Your task: produce a complete "
        "coaching analysis for the user's barbell session.\n\n"
        f"Exercise: {state['exercise_type']} — {state['exercise_variant']}\n"
        f"Confidence: {state['confidence_score']:.2f}\n\n"
        "You have access to six tools. Call them in the order you judge "
        "most useful given the data you have seen. You MUST call "
        "generate_correction_plan exactly once as your final step. When "
        "coaching_output is populated, stop calling tools and respond "
        "with a brief plain-text acknowledgement.\n\n"
        "Priority order for coaching focus (Movement Quality → Technique "
        "→ Path & Balance → Control) is enforced inside "
        "generate_correction_plan."
    )
