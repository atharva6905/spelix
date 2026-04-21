"""Standalone distillation StateGraph (FR-BRAIN-06).

Topology:
  START
    -> extract_insights
    -> validate_quality
         (reject) -> END
         (pass|review) -> lifecycle_decision
    -> cove_verify
    -> format_entry
    -> store_entry
    -> END

Each node is wrapped by `_wrap_trace` (same pattern as
app/agents/graph.py) so NodeEvent rows accumulate in state['trace'].
"""

from __future__ import annotations

import asyncio  # noqa: F401 — used at runtime in wait_for()
import datetime as _dt
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from langgraph.graph import END, START, StateGraph

from app.agents.state import NodeEvent
from app.distillation.cove_node import cove_verify
from app.distillation.extract import extract_insights
from app.distillation.format import format_entry
from app.distillation.lifecycle import lifecycle_decision
from app.distillation.state import DistillationState, make_initial_distillation_state
from app.distillation.store import store_entry
from app.distillation.validate import validate_quality
from app.schemas.coaching import CoachingOutput
from app.schemas.rag import RetrievedContext

logger = logging.getLogger(__name__)

_TRACE_NODE_CAP_BYTES = 8 * 1024


def _wrap_trace(
    node_name: str,
    inner: Callable[[DistillationState], Awaitable[dict[str, Any]]],
) -> Callable[[DistillationState], Awaitable[dict[str, Any]]]:
    async def _wrapped(state: DistillationState) -> dict[str, Any]:
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
        trace = list(state.get("trace") or [])
        trace.append(event.model_dump())
        merged: dict[str, Any] = dict(update)
        merged["trace"] = trace
        return merged

    return _wrapped


def build_distillation_graph(
    *,
    anthropic_client: Any,
    instructor_client: Any,
    cohere_client: Any,
    qdrant_client: Any,
    brain_embedding_svc: Any,
    cove_service: Any,
    db_session: Any,
) -> Any:
    """Wire the distillation nodes into a compiled StateGraph."""

    async def _extract(state: DistillationState) -> dict[str, Any]:
        return await extract_insights(
            state, anthropic_client=anthropic_client, instructor_client=instructor_client
        )

    async def _validate(state: DistillationState) -> dict[str, Any]:
        return await validate_quality(state)

    async def _lifecycle(state: DistillationState) -> dict[str, Any]:
        return await lifecycle_decision(
            state,
            cohere_client=cohere_client,
            qdrant_client=qdrant_client,
            brain_embedding_svc=brain_embedding_svc,
        )

    async def _cove(state: DistillationState) -> dict[str, Any]:
        return await cove_verify(state, cove_service=cove_service)

    async def _format(state: DistillationState) -> dict[str, Any]:
        return await format_entry(state)

    async def _store(state: DistillationState) -> dict[str, Any]:
        return await store_entry(state, db_session=db_session)

    def _after_validate(state: DistillationState) -> str:
        return "reject" if state.get("validation_decision") == "reject" else "continue"

    builder = StateGraph(DistillationState)
    builder.add_node("extract_insights", _wrap_trace("extract_insights", _extract))
    builder.add_node("validate_quality", _wrap_trace("validate_quality", _validate))
    builder.add_node("lifecycle_decision", _wrap_trace("lifecycle_decision", _lifecycle))
    builder.add_node("cove_verify", _wrap_trace("cove_verify", _cove))
    builder.add_node("format_entry", _wrap_trace("format_entry", _format))
    builder.add_node("store_entry", _wrap_trace("store_entry", _store))

    builder.add_edge(START, "extract_insights")
    builder.add_edge("extract_insights", "validate_quality")
    builder.add_conditional_edges(
        "validate_quality",
        _after_validate,
        {"reject": END, "continue": "lifecycle_decision"},
    )
    builder.add_edge("lifecycle_decision", "cove_verify")
    builder.add_edge("cove_verify", "format_entry")
    builder.add_edge("format_entry", "store_entry")
    builder.add_edge("store_entry", END)

    return builder.compile()


async def run_distillation_graph(
    *,
    analysis_id: uuid.UUID,
    exercise_type: str,
    coaching_output: CoachingOutput,
    retrieved_papers_contexts: list[RetrievedContext],
    eval_scores: dict[str, Any],
    anthropic_client: Any,
    instructor_client: Any,
    cohere_client: Any,
    qdrant_client: Any,
    brain_embedding_svc: Any,
    cove_service_factory: Callable[[], Any],
    db_session: Any,
) -> tuple[DistillationState, dict[str, Any]]:
    """Entry point called from the streaq task.

    Returns (final_state, trace_payload) where trace_payload is the
    shape suitable for future persistence / admin debugging.
    """
    initial = make_initial_distillation_state(
        analysis_id=analysis_id,
        exercise_type=exercise_type,
        coaching_output=coaching_output,
        retrieved_papers_contexts=retrieved_papers_contexts,
        eval_scores=eval_scores,
    )

    graph = build_distillation_graph(
        anthropic_client=anthropic_client,
        instructor_client=instructor_client,
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
        brain_embedding_svc=brain_embedding_svc,
        cove_service=cove_service_factory(),
        db_session=db_session,
    )
    from app.config_constants import DISTILLATION_RECURSION_LIMIT, DISTILLATION_TIMEOUT_SECONDS
    from langchain_core.runnables import RunnableConfig

    config: RunnableConfig = {
        "recursion_limit": DISTILLATION_RECURSION_LIMIT,
        "run_name": "spelix-distillation",
        "tags": ["distillation", f"analysis:{analysis_id}"],
    }
    final_state = await asyncio.wait_for(
        graph.ainvoke(initial, config), timeout=DISTILLATION_TIMEOUT_SECONDS
    )

    trace_payload: dict[str, Any] = {
        "nodes_executed": final_state.get("trace") or [],
        "validation_decision": final_state.get("validation_decision"),
        "stored_ids": [str(i) for i in (final_state.get("stored_ids") or [])],
        "candidates_count": len(final_state.get("candidates") or []),
        "decisions": [d.model_dump() for d in (final_state.get("decisions") or [])],
    }
    return final_state, trace_payload
