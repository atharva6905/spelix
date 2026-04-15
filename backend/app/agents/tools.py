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


async def retrieve_coach_brain(
    state: AgentState,
    *,
    retrieval_svc: Any,
    top_k: int = 10,
    rerank_top_n: int = 5,
) -> dict[str, Any]:
    """Retrieve curated coaching cues from the ``coach_brain`` Qdrant collection.

    Applies a ``status='active'`` payload filter (FR-BRAIN-04) and an
    ``exercise``-type payload filter (FR-AICP-12), running dense+BM25+RRF
    hybrid retrieval with Cohere reranking. Returns distilled coaching
    knowledge — cues, heuristics, compensation entries — curated by the
    kinesiology expert and/or produced by the Phase 3 distillation
    pipeline.

    Use this to source high-value coaching cues. Prefer Coach Brain when
    retrieval scores exceed 0.82 (FR-BRAIN-05 primary threshold); fall back
    to papers_rag otherwise. Returns empty list on cold-start
    (``brain_contexts = []``) — callers must degrade gracefully.
    """
    from qdrant_client import models as qdrant_models

    status_filter = qdrant_models.FieldCondition(
        key="status",
        match=qdrant_models.MatchValue(value="active"),
    )

    query = (
        f"{state['exercise_type']} {state['exercise_variant']} "
        "coaching cue correction"
    )
    try:
        contexts = await retrieval_svc.hybrid_search(
            query,
            collection="coach_brain",
            top_k=top_k,
            rerank_top_n=rerank_top_n,
            exercise_filter=state["exercise_type"],
            additional_filters=[status_filter],
            rerank=True,
        )
        return {"brain_contexts": contexts}
    except Exception:
        logger.warning(
            "retrieve_coach_brain: error retrieving — returning empty",
            exc_info=True,
        )
        return {"brain_contexts": []}


# Mapping from threshold-config key suffix → rep-metric field to compare.
# Each entry: (threshold_suffix, rep_metric_key, comparison, label)
# comparison: "max" means observed > threshold is a violation;
#             "min" means observed < threshold is a violation.
_DEVIATION_CHECKS: list[tuple[str, str, str]] = [
    ("depth_angle_max", "depth_angle", "max"),
    ("lockout_hip_knee_min", "hip_plus_knee_at_lockout", "min"),
    ("elbow_angle_at_bottom_max", "elbow_angle_at_bottom", "max"),
    ("torso_lean_max", "torso_lean", "max"),
]


async def flag_form_deviation(
    state: AgentState,
    *,
    thresholds: Any,
) -> dict[str, list[dict[str, Any]]]:
    """Flag reps whose observed metrics violate ThresholdConfig references.

    Iterates ``state['rep_metrics']`` against the exercise-specific
    thresholds loaded from ``config/thresholds_v1.json``. For each
    violating rep, emits a flag dict with ``rep_number``, ``metric``,
    ``observed``, ``threshold``, ``threshold_key``, and
    ``comparison`` ("max" = observed exceeded threshold; "min" =
    observed fell short of threshold).

    Use this to anchor coaching feedback in versioned biomechanics
    constants rather than the LLM's free judgement. Flagged deviations
    inform which reps + joints the correction plan must address.
    """
    exercise_type = state["exercise_type"]
    try:
        exercise_thresholds = thresholds.all_for_exercise(exercise_type)
    except KeyError:
        logger.warning(
            "flag_form_deviation: no thresholds for exercise=%s", exercise_type,
        )
        return {"flagged_deviations": []}

    flagged: list[dict[str, Any]] = []

    for suffix, metric_key, comparison in _DEVIATION_CHECKS:
        threshold_key = f"{exercise_type}.{suffix}"
        entry = exercise_thresholds.get(threshold_key)
        if entry is None:
            continue

        threshold_value = float(entry["value"])

        for rep in state["rep_metrics"]:
            observed = rep.get(metric_key)
            if observed is None:
                continue
            try:
                observed_f = float(observed)
            except (TypeError, ValueError):
                continue

            violated = (
                (comparison == "max" and observed_f > threshold_value)
                or (comparison == "min" and observed_f < threshold_value)
            )
            if violated:
                flagged.append({
                    "rep_number": rep["rep_number"],
                    "metric": metric_key,
                    "observed": observed_f,
                    "threshold": threshold_value,
                    "threshold_key": threshold_key,
                    "comparison": comparison,
                })

    return {"flagged_deviations": flagged}
