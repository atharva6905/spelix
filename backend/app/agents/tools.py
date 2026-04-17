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

# FR-BRAIN-05 thresholds for retrieval-source classification. Mirrors
# DualCollectionOrchestrator (Phase 2) so graph-path ordering matches
# imperative-path ordering.
_COACH_BRAIN_PRIMARY_THRESHOLD: float = 0.82
_HYBRID_FLOOR_THRESHOLD: float = 0.65


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

    Applies a ``status ∈ {'active','seed'}`` payload filter (FR-BRAIN-04 +
    FR-BRAIN-05 cold-start) and an ``exercise``-type payload filter
    (FR-AICP-12), running dense+BM25+RRF hybrid retrieval with Cohere
    reranking. Returns distilled coaching knowledge — cues, heuristics,
    compensation entries — curated by the kinesiology expert and/or
    produced by the Phase 3 distillation pipeline.

    Seed entries (``source=seed_manual_validated``, status='seed' in
    migration 004's enum) are the initial retrievable population; they
    remain first-class retrieval targets alongside `active` entries until
    explicit deprecation via `status='deprecated'`. Deprecated entries are
    excluded.

    Use this to source high-value coaching cues. Prefer Coach Brain when
    retrieval scores exceed 0.82 (FR-BRAIN-05 primary threshold); fall back
    to papers_rag otherwise. Returns empty list on true cold-start
    (``brain_contexts = []``, no seed match either) — callers must degrade
    gracefully.
    """
    from qdrant_client import models as qdrant_models

    # FR-BRAIN-05 cold-start: seeds are retrievable until distillation + expert
    # review produces `status='active'` entries. Including both values here
    # means the cold-start fallback path (`retrieval_source='papers_only_fallback'`)
    # is only taken when the seed corpus itself can't produce a hit — not when
    # all content is locked behind an unattainable `active` filter.
    status_filter = qdrant_models.FieldCondition(
        key="status",
        match=qdrant_models.MatchAny(any=["active", "seed"]),
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
        top_brain_score = max(
            (ctx.score for ctx in contexts),
            default=0.0,
        )
        if top_brain_score >= _COACH_BRAIN_PRIMARY_THRESHOLD:
            retrieval_source = "coach_brain_primary"
        elif top_brain_score >= _HYBRID_FLOOR_THRESHOLD:
            retrieval_source = "hybrid_brain_supplementary"
        else:
            retrieval_source = "papers_only_fallback"
        return {
            "brain_contexts": contexts,
            "retrieval_source": retrieval_source,
        }
    except Exception:
        logger.warning(
            "retrieve_coach_brain: error retrieving — returning empty",
            exc_info=True,
        )
        return {"brain_contexts": [], "retrieval_source": "papers_only_fallback"}


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


async def compare_to_user_history(
    state: AgentState,
    *,
    analysis_repo: Any,
    limit: int = 5,
) -> dict[str, str | None]:
    """Summarize the user's recent analyses for trend-aware coaching.

    Queries the user's last ``limit`` completed analyses of the SAME
    exercise type (``state['exercise_type']``) and returns a plain-English
    summary string describing: count, date range, mean overall score,
    mean Movement Quality score, and a simple trend label
    ("improving" / "steady" / "declining").

    Use this to add longitudinal context to coaching feedback — e.g.
    "this is your fifth squat session in two weeks; Movement Quality has
    climbed from 5.2 to 7.1, nice progression on braced-torso cue". When
    the user has no history, returns ``None`` and coaching proceeds
    session-only.
    """
    rows = await analysis_repo.list_recent_by_user(
        state["user_id"],
        limit=limit,
        exercise_type=state["exercise_type"],
    )
    if not rows:
        return {"user_history_summary": None}

    overall_scores = [
        float(r.form_score_overall)
        for r in rows
        if getattr(r, "form_score_overall", None) is not None
    ]
    safety_scores = [
        float(r.form_score_safety)
        for r in rows
        if getattr(r, "form_score_safety", None) is not None
    ]

    def _mean(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    mean_overall = _mean(overall_scores)
    mean_safety = _mean(safety_scores)

    trend = "steady"
    if len(overall_scores) >= 2:
        delta = overall_scores[0] - overall_scores[-1]
        if delta >= 0.5:
            trend = "improving"
        elif delta <= -0.5:
            trend = "declining"

    parts = [
        f"{len(rows)} recent {state['exercise_type']} sessions",
    ]
    if mean_overall is not None:
        parts.append(f"mean overall score {mean_overall:.1f}")
    if mean_safety is not None:
        parts.append(f"mean Movement Quality {mean_safety:.1f}")
    parts.append(f"trend: {trend}")

    return {"user_history_summary": "; ".join(parts)}


async def generate_correction_plan(
    state: AgentState,
    *,
    coaching_svc: Any,
    thresholds: Any,
    pubsub_redis: Any,
) -> dict[str, Any]:
    """Generate the initial structured coaching output via Claude Sonnet.

    Calls ``CoachingService.generate_coaching_streaming`` with every piece
    of context available in ``state`` — rep metrics, flagged deviations
    (via the user prompt), retrieved research and Coach Brain contexts,
    body stats, keyframe analysis, user history summary. Coach Brain
    contexts are ordered first when ``retrieval_source`` indicates
    ``coach_brain_primary``; otherwise papers-first.

    Streams text chunks to ``coaching:{analysis_id}`` via ``pubsub_redis``
    for the SSE endpoint (FR-AICP-07). When ``state['degraded_mode']`` is
    True, stamps that flag onto the returned CoachingOutput so the
    frontend can show the degraded-mode banner (FR-AICP-15). Returns the
    fully validated CoachingOutput on ``state['coaching_output']``.
    """
    # Merge papers + brain contexts with primary source first (matches
    # Phase 2 behavior from DualCollectionOrchestrator).
    papers = state.get("papers_contexts") or []
    brain = state.get("brain_contexts") or []
    retrieval_source = state.get("retrieval_source")

    if retrieval_source == "coach_brain_primary":
        merged = list(brain) + list(papers)
    else:
        merged = list(papers) + list(brain)

    contexts = merged or None  # None preserves Phase 0/1 prompt shape if empty

    coaching_output = await coaching_svc.generate_coaching_streaming(
        exercise_type=state["exercise_type"],
        exercise_variant=state["exercise_variant"],
        rep_metrics=state["rep_metrics"],
        confidence_score=state["confidence_score"],
        thresholds=thresholds,
        body_stats=state.get("body_stats"),
        keyframe_analysis_text=state.get("keyframe_analysis_text"),
        retrieved_contexts=contexts,
        retrieval_source=retrieval_source,
        analysis_id=state["analysis_id"],
        pubsub_redis=pubsub_redis,
    )

    if state.get("degraded_mode"):
        coaching_output = coaching_output.model_copy(
            update={"degraded_mode": True}
        )

    return {"coaching_output": coaching_output}
