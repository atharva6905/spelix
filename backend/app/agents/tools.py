"""Composable async tools for the Phase 3 coaching agent (FR-AICP-18).

Each tool:
- Takes the current ``AgentState`` as its first positional arg.
- Accepts required service dependencies as keyword-only arguments (graph
  compile time binds them via closures — see ``graph.py::_bind_tools``).
- Returns a ``dict`` containing the partial state update to merge into
  ``AgentState``. LangGraph merges node return values shallowly.
- Has a rich docstring — the adaptive-mode reasoner (FR-AICP-19) selects
  tools by docstring content.

Tools are pure in the sense that they do not mutate ``state`` in-place;
they return a fresh update dict. LangGraph owns the merge.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.state import AgentState

logger = logging.getLogger(__name__)


async def get_rep_metrics(
    state: AgentState,
    *,
    rep_metric_repo: Any,
) -> dict[str, list[dict[str, Any]]]:
    """Load per-rep metrics from the database.

    Returns a list of flat dicts where each rep appears once, keyed by
    1-based ``rep_number``. Metrics include ``depth_angle``,
    ``knee_angle_at_depth``, ``torso_lean``, ``rep_duration_s``,
    ``descent_duration_s``, ``eccentric_duration_s``,
    ``ascent_duration_s``, ``lockout_passed``, ``lockout_confidence``, and
    ``phase_of_max_deviation`` (exercise-dependent; see
    `backend/CLAUDE.md::Per-Rep Metrics Schema`).

    Use this when you need to cite specific reps in coaching feedback,
    compute aggregate rep statistics, or compare observed angles against
    threshold references.
    """
    rows = await rep_metric_repo.get_by_analysis(state["analysis_id"])
    rep_metrics = [
        {"rep_number": r.rep_index + 1, **(r.metrics_json or {})}
        for r in rows
    ]
    logger.debug(
        "get_rep_metrics: analysis_id=%s rep_count=%d",
        state["analysis_id"],
        len(rep_metrics),
    )
    return {"rep_metrics": rep_metrics}


async def retrieve_papers(
    state: AgentState,
    *,
    retrieval_svc: Any,
    top_k: int = 10,
    rerank_top_n: int = 5,
) -> dict[str, Any]:
    """Retrieve biomechanics research passages from the ``papers_rag`` Qdrant collection.

    Builds a natural-language query from ``state['exercise_type']`` +
    ``state['exercise_variant']`` + common technique language, then runs
    dense+BM25+RRF hybrid retrieval, Cohere reranking, and returns the
    top-``rerank_top_n`` passages as ``RetrievedContext`` objects.

    Use this to ground coaching feedback in peer-reviewed biomechanics
    literature. Every coaching claim that cites [N] must trace to a
    passage returned here or by ``retrieve_coach_brain``. Falls back to
    empty list + ``degraded_mode=True`` if Qdrant is unavailable
    (FR-AICP-15).
    """
    query = (
        f"{state['exercise_type']} {state['exercise_variant']} "
        "technique coaching biomechanics"
    )
    try:
        contexts = await retrieval_svc.hybrid_search(
            query,
            collection="papers_rag",
            top_k=top_k,
            rerank_top_n=rerank_top_n,
            exercise_filter=state["exercise_type"],
            rerank=True,
        )
        return {"papers_contexts": contexts}
    except Exception:
        logger.warning(
            "retrieve_papers: error retrieving — degraded mode",
            exc_info=True,
        )
        return {"papers_contexts": [], "degraded_mode": True}
