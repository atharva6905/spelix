"""Post-generation verification nodes for the coaching graph.

These wrap existing Phase 2 services (ValidateOutputTool, CoveVerificationService,
SafetyFilter, FaithfulnessGateService) as graph nodes that take ``AgentState``
and return a partial state update. Each node is error-swallowing: any
exception is logged and the node returns an empty update so the graph
completes.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.state import AgentState
from app.services.coaching import build_citation_blocks
from app.services.safety_filter import SafetyFilter
from app.services.validate_output import ValidateOutputTool

logger = logging.getLogger(__name__)


def _combined_contexts(state: AgentState) -> list[Any]:
    return list(state.get("papers_contexts") or []) + list(state.get("brain_contexts") or [])


async def node_validate_output(state: AgentState) -> dict[str, Any]:
    """Cross-reference citation indices against retrieved contexts (FR-AICP-10).

    Calls ``ValidateOutputTool.validate`` and returns an updated
    ``coaching_output`` with invalid citation indices stripped. When no
    retrieval contexts are present, returns an empty update (no-op).
    """
    output = state.get("coaching_output")
    if output is None:
        return {}
    contexts = _combined_contexts(state)
    if not contexts:
        return {}

    try:
        citation_blocks = build_citation_blocks(contexts)
        result = ValidateOutputTool.validate(output, citation_blocks)
        if result.has_invalid_citations:
            logger.warning(
                "node_validate_output: invalid citation indices %s",
                result.invalid_indices,
            )
        return {"coaching_output": result.output}
    except Exception:
        logger.warning("node_validate_output failed — continuing", exc_info=True)
        return {}


async def node_cove_verify(
    state: AgentState,
    *,
    cove_svc: Any,
) -> dict[str, Any]:
    """Run Chain-of-Verification on the coaching output (FR-BRAIN-14).

    No-ops when no retrieval contexts are present. Merges CoVe trace and
    ``cove_verified`` flag into ``state['eval_scores']``.
    """
    output = state.get("coaching_output")
    if output is None:
        return {}
    contexts = _combined_contexts(state)
    if not contexts:
        return {}

    try:
        result = await cove_svc.verify(
            initial_output=output,
            retrieved_contexts=contexts,
            max_iterations=2,
        )
        new_eval_scores = dict(state.get("eval_scores") or {})
        new_eval_scores["cove_verified"] = result.cove_verified
        new_eval_scores["cove_iterations"] = result.iterations_run
        new_eval_scores["cove_trace"] = result.trace
        return {
            "coaching_output": result.output,
            "cove_verified": result.cove_verified,
            "eval_scores": new_eval_scores,
        }
    except Exception:
        logger.warning("node_cove_verify failed — continuing", exc_info=True)
        return {}


async def node_safety_filter(state: AgentState) -> dict[str, Any]:
    """Apply Phase 2 safety language post-filter (FR-AICP-14).

    Always runs (RAG-grounded or not). Replaces SaMD-triggering language.
    """
    output = state.get("coaching_output")
    if output is None:
        return {}
    try:
        result = SafetyFilter.apply(output)
        if result.injected_disclaimer or result.phrases_replaced > 0:
            logger.info(
                "node_safety_filter: injected=%s replaced=%d",
                result.injected_disclaimer,
                result.phrases_replaced,
            )
        return {"coaching_output": result.output}
    except Exception:
        logger.warning("node_safety_filter failed — continuing", exc_info=True)
        return {}


async def node_faithfulness_gate(
    state: AgentState,
    *,
    fg_svc: Any,
) -> dict[str, Any]:
    """RAGAS-style faithfulness evaluation (FR-AICP-08 Stage 3).

    Populates ``eval_scores.faithfulness`` and flags analyses that fall
    below the 0.8 threshold. No-op when no retrieval contexts exist.
    """
    output = state.get("coaching_output")
    if output is None:
        return {}
    contexts = _combined_contexts(state)
    if not contexts:
        return {}

    try:
        result = await fg_svc.evaluate(output, contexts)
        new_eval_scores = dict(state.get("eval_scores") or {})
        new_eval_scores["faithfulness"] = result.score
        new_eval_scores["faithfulness_passed"] = result.passed
        new_eval_scores["unsupported_claims"] = result.unsupported_claims
        new_eval_scores["evaluator"] = "claude-sonnet-4-6-llm-judge"
        new_eval_scores["threshold"] = 0.8
        return {"eval_scores": new_eval_scores}
    except Exception:
        logger.warning("node_faithfulness_gate failed — continuing", exc_info=True)
        return {}
