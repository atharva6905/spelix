"""distill_analysis task body.

Loads the completed analysis + coaching_result + retrieved sources,
constructs pipeline deps, invokes run_distillation_graph, and persists
the resulting candidate rows (the graph's store_entry node writes via
the provided session; the task manages transaction boundaries).

FR-BRAIN-06. Enqueued from analysis_worker._run_pipeline tail when
SPELIX_DISTILLATION_ENABLED=1 and eval_scores.overall >= 0.6.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.distillation.cove_brain import BrainCoveService
from app.distillation.graph import run_distillation_graph
from app.repositories.analysis import AnalysisRepository
from app.repositories.coaching_result import CoachingResultRepository
from app.schemas.coaching import CoachingOutput
from app.schemas.rag import RetrievedContext

logger = logging.getLogger(__name__)


async def _build_papers_contexts(coaching_result: Any) -> list[RetrievedContext]:
    """Rehydrate papers_rag contexts from coaching_results.retrieved_sources_json."""
    raw = coaching_result.retrieved_sources_json or {}
    ctxs_raw = raw.get("contexts") or []
    contexts: list[RetrievedContext] = []
    for c in ctxs_raw:
        try:
            ctx = RetrievedContext.model_validate(c)
            if ctx.collection == "papers_rag":
                contexts.append(ctx)
        except Exception:  # noqa: BLE001
            continue
    return contexts


async def distill_analysis_body(
    ctx: dict[str, Any],
    analysis_id: uuid.UUID,
) -> dict[str, Any]:
    """Body of the distill_analysis streaq task.

    Expects ctx to carry:
      - db_session_maker: async sessionmaker
      - anthropic_client, instructor_client
      - cohere_client, qdrant_client, brain_embedding_svc
    """
    db_session_maker = ctx["db_session_maker"]
    if db_session_maker is None:
        logger.warning("distill_analysis_body: db_session_maker is None — aborting")
        return {"status": "skipped_no_session"}

    async with db_session_maker() as db_session:
        analysis_repo = AnalysisRepository(db_session)
        coaching_repo = CoachingResultRepository(db_session)

        analysis = await analysis_repo.get_by_id(analysis_id)
        if analysis is None:
            logger.warning("distill_analysis_body: analysis %s not found", analysis_id)
            return {"status": "skipped_no_analysis"}

        coaching_result = await coaching_repo.get_by_analysis(analysis_id)
        if coaching_result is None or coaching_result.structured_output_json is None:
            logger.warning(
                "distill_analysis_body: no coaching_result for analysis %s", analysis_id
            )
            return {"status": "skipped_no_coaching"}

        coaching_output = CoachingOutput.model_validate(
            coaching_result.structured_output_json
        )
        papers_contexts = await _build_papers_contexts(coaching_result)
        eval_scores = analysis.eval_scores or {}

        cove_service = BrainCoveService(
            anthropic_client=ctx["anthropic_client"],
            instructor_client=ctx["instructor_client"],
        )

        final_state, trace_payload = await run_distillation_graph(
            analysis_id=analysis_id,
            exercise_type=analysis.exercise_type,
            coaching_output=coaching_output,
            retrieved_papers_contexts=papers_contexts,
            eval_scores=eval_scores,
            anthropic_client=ctx["anthropic_client"],
            instructor_client=ctx["instructor_client"],
            cohere_client=ctx["cohere_client"],
            qdrant_client=ctx["qdrant_client"],
            brain_embedding_svc=ctx["brain_embedding_svc"],
            cove_service_factory=lambda: cove_service,
            db_session=db_session,
        )

        await db_session.commit()

        logger.info(
            "distill_analysis: analysis=%s validation=%s stored=%d",
            analysis_id,
            final_state.get("validation_decision"),
            len(final_state.get("stored_ids") or []),
        )
        return {
            "status": "ok",
            "validation_decision": final_state.get("validation_decision"),
            "stored_ids": [str(i) for i in (final_state.get("stored_ids") or [])],
            "trace_summary": {
                "nodes_count": len(trace_payload.get("nodes_executed") or [])
            },
        }
