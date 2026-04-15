"""AgentState TypedDict — the Blackboard for the LangGraph coaching agent.

FR-AICP-18 (Phase 3): typed state shared across composable tools.

Design notes:
- TypedDict (not Pydantic) because LangGraph's StateGraph uses TypedDict
  introspection to wire node signatures. Pydantic state classes are supported
  but add boilerplate without providing more safety here.
- ``NodeEvent`` IS a Pydantic model — it serializes into ``agent_trace_json``
  JSONB and benefits from field validation.
- ``make_initial_state`` is the ONLY entry point for constructing state
  outside of LangGraph's internal update mechanics. Tests and graph callers
  must use it to ensure every optional field has a safe default.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class NodeEvent(BaseModel):
    """One entry per executed graph node, appended to ``state['trace']``."""

    node: str = Field(description="Node name (e.g. 'get_rep_metrics').")
    started_at: str = Field(description="ISO-8601 UTC timestamp when node started.")
    duration_ms: float = Field(ge=0.0, description="Wall-clock duration in milliseconds.")
    output_keys: list[str] = Field(
        default_factory=list,
        description="AgentState keys mutated by this node.",
    )
    error: str | None = Field(
        default=None,
        description="String representation of exception if the node failed.",
    )


class AgentState(TypedDict, total=False):
    """Shared state passed between graph nodes.

    ``total=False`` means individual updates can set a subset of keys; LangGraph
    merges them into the running state via shallow dict update.
    """

    # --- Inputs (populated by make_initial_state) -------------------------
    analysis_id: uuid.UUID
    user_id: uuid.UUID
    exercise_type: str
    exercise_variant: str
    confidence_score: float
    body_stats: dict[str, Any] | None
    keyframe_analysis_text: str | None
    mode: Literal["deterministic", "adaptive"]

    # --- Tool outputs ----------------------------------------------------
    rep_metrics: list[dict[str, Any]]
    papers_contexts: list[Any]          # list[RetrievedContext] at runtime
    brain_contexts: list[Any]
    retrieval_source: str | None
    flagged_deviations: list[dict[str, Any]]
    user_history_summary: str | None
    coaching_output: Any | None          # CoachingOutput at runtime
    cove_verified: bool
    eval_scores: dict[str, Any]
    degraded_mode: bool

    # --- Observability --------------------------------------------------
    trace: list[dict[str, Any]]          # NodeEvent.model_dump() entries


def make_initial_state(
    *,
    analysis_id: uuid.UUID,
    user_id: uuid.UUID,
    exercise_type: str,
    exercise_variant: str,
    confidence_score: float,
    mode: Literal["deterministic", "adaptive"] = "deterministic",
    body_stats: dict[str, Any] | None = None,
    keyframe_analysis_text: str | None = None,
) -> AgentState:
    """Construct a valid initial AgentState with safe defaults for every field."""
    return AgentState(
        analysis_id=analysis_id,
        user_id=user_id,
        exercise_type=exercise_type,
        exercise_variant=exercise_variant,
        confidence_score=confidence_score,
        body_stats=body_stats,
        keyframe_analysis_text=keyframe_analysis_text,
        mode=mode,
        rep_metrics=[],
        papers_contexts=[],
        brain_contexts=[],
        retrieval_source=None,
        flagged_deviations=[],
        user_history_summary=None,
        coaching_output=None,
        cove_verified=False,
        eval_scores={},
        degraded_mode=False,
        trace=[],
    )
