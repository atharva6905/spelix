"""ARQ worker — analysis pipeline entry point.

Implements FR-UPLD-18 (async processing), NFR-RELI-01 through NFR-RELI-04
(reliability: idempotent, error handling, retry limit, heartbeat),
NFR-OPER-02 (operator heartbeat visibility).

Pipeline: download → quality gates → pose extraction → smoothing → rep
detection → metric extraction → confidence → barbell detection → artifacts
→ upload → cleanup → coaching → completed.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any


from app.config import ThresholdConfig
from app.cv.artifact_generation import (
    cleanup_temp_files,
)
from app.db import async_session
from app.repositories.analysis import AnalysisRepository
from app.repositories.rep_metric import RepMetricRepository
from app.services.pipeline import QualityGateRejection, run_cv_pipeline
from app.services.status import transition
from app.services.summary import SummaryService
from app.workers.streaq_worker import _HEARTBEAT_TTL

logger = logging.getLogger(__name__)

# Terminal states: if an analysis is in one of these, the worker is a no-op.
_TERMINAL_STATES = frozenset({"completed", "quality_gate_rejected"})

# Heartbeat key and TTL (seconds)
_HEARTBEAT_KEY = "spelix:worker:heartbeat"

# M-03: UserProfile body-stats fields surfaced to coaching prompts.
# Mirrored in the imperative path and the graph path.
# Adding a new column to UserProfile requires updating this set in one
# place and re-running the body_stats tests so coaching prompts pick it up.
_USER_PROFILE_BODY_STATS_FIELDS: frozenset[str] = frozenset(
    {
        "height_cm",
        "weight_kg",
        "age",
        "experience_level",
        "arm_span_cm",
        "femur_length_cm",
    }
)


# ---------------------------------------------------------------------------
# Internal pipeline
# ---------------------------------------------------------------------------


async def _build_supabase_client() -> Any | None:
    """Build an *async* Supabase client from env vars, or None if unconfigured.

    The CV pipeline awaits storage methods (``await storage_client.storage
    .from_(bucket).download(path)`` etc), so the client must be the async
    variant returned by ``acreate_client``. The sync ``create_client`` returns
    a ``Client`` whose storage methods return plain ``dict``s — awaiting those
    raises ``TypeError: object dict can't be used in 'await' expression``,
    which is the same dormant Phase 0 bug that took down the upload endpoint.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import acreate_client

        return await acreate_client(url, key)
    except Exception as e:
        logger.warning("Failed to create async Supabase client: %s", e)
        return None


async def _run_pipeline(
    analysis_id: uuid.UUID,
    repo: AnalysisRepository,
    redis: Any,
) -> None:
    """Execute the full analysis pipeline, updating status at each stage.

    Status transition sequence (SRS Section 5.2a):
      queued → quality_gate_pending → (quality_gate_rejected | processing)
      → coaching → completed
    """
    analysis = await repo.get_by_id(analysis_id)
    if analysis is None:
        raise ValueError(f"Analysis {analysis_id} not found in DB")

    # Build dependencies
    storage_client = await _build_supabase_client()
    rep_metric_repo = RepMetricRepository(repo.db)
    thresholds = ThresholdConfig()

    # OpenAI client for GPT-4o fallback (exercise detection + keyframe analysis)
    openai_client = None
    try:
        import openai as openai_mod

        openai_client = openai_mod.AsyncOpenAI()
    except Exception:
        logger.warning("OpenAI client unavailable — GPT-4o fallback disabled")

    try:
        # ------------------------------------------------------------------ #
        # CV Pipeline (B-022): quality gates → pose → reps → metrics → artifacts
        # ------------------------------------------------------------------ #
        pipeline_result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=storage_client,
            redis=redis,
            write_heartbeat=_write_heartbeat,
            openai_client=openai_client,
        )

        # ------------------------------------------------------------------ #
        # Transition: processing → coaching (B-024)
        # ------------------------------------------------------------------ #
        analysis = await repo.get_by_id(analysis_id)
        if analysis is None:
            raise ValueError(f"Analysis {analysis_id} disappeared during pipeline")

        analysis.status = transition(analysis.status, "coaching")

        # FR-SCOR-11: freeze threshold_version at analysis time
        analysis.threshold_version = thresholds.version

        await repo.update(analysis)
        await _write_heartbeat(redis)

        coaching_output, rep_metrics_dicts, body_stats = await _dispatch_coaching(
            analysis=analysis, repo=repo, redis=redis, pipeline_result=pipeline_result,
        )

        await _write_heartbeat(redis)

        # ------------------------------------------------------------------ #
        # Summary metrics (B-030): compute and store summary_json
        # ------------------------------------------------------------------ #
        summary_svc = SummaryService(repo, rep_metric_repo)
        await summary_svc.compute_and_store(analysis_id)
        await _write_heartbeat(redis)

        # ------------------------------------------------------------------ #
        # PDF generation (B-035): render report, upload to Storage
        # ------------------------------------------------------------------ #
        await _generate_and_upload_pdf(
            analysis_id=analysis_id,
            analysis=analysis,
            coaching_output=coaching_output,
            rep_metrics_dicts=rep_metrics_dicts,
            storage_client=storage_client,
            repo=repo,
            bar_path=pipeline_result.bar_path,
            keyframes=pipeline_result.keyframes,
            body_stats=body_stats,
        )
        await _write_heartbeat(redis)

        # ------------------------------------------------------------------ #
        # Transition: coaching → completed
        # ------------------------------------------------------------------ #
        analysis.status = transition(analysis.status, "completed")
        await repo.update(analysis)

    except QualityGateRejection:
        # Expected flow — analysis was already transitioned to
        # quality_gate_rejected inside run_cv_pipeline
        logger.info(
            "Analysis %s rejected by quality gates", analysis_id,
        )


# ---------------------------------------------------------------------------
# Coaching dispatch — feature-flag router (Task 15, FR-AICP-18/19/20)
# ---------------------------------------------------------------------------


async def _run_coaching_imperative(
    *,
    analysis: Any,
    repo: AnalysisRepository,
    redis: Any,
    pipeline_result: Any,
) -> tuple[Any, list[dict], dict | None]:
    """Original Phase 2 coaching orchestration (imperative).

    Moved verbatim from inline in _run_pipeline. Kept as a fallback for
    SPELIX_PHASE3_AGENT_ENABLED=0. Remove once agent traffic is stable
    for 7+ days on prod.

    Returns (coaching_output, rep_metrics_dicts, body_stats) so the caller
    can forward them to _generate_and_upload_pdf.
    """
    import anthropic
    import redis.asyncio as aioredis
    import json as _json

    from app.models.coaching_result import CoachingResult
    from app.repositories.coaching_result import CoachingResultRepository
    from app.schemas.rag import RetrievedContext
    from app.services.coaching import CoachingService
    from app.services.langfuse_client import get_langfuse_client

    analysis_id = analysis.id
    thresholds = ThresholdConfig()

    # OpenAI client for GPT-4o keyframe analysis — best-effort
    openai_client = None
    try:
        import openai as openai_mod

        openai_client = openai_mod.AsyncOpenAI()
    except Exception:
        logger.warning("OpenAI client init failed (imperative path); GPT-4o features disabled", exc_info=True)

    langfuse_client = await get_langfuse_client()

    # ------------------------------------------------------------------ #
    # GPT-4o keyframe analysis (FR-AICP-02) — best-effort
    # ------------------------------------------------------------------ #
    keyframe_analysis_text: str | None = None
    if pipeline_result.keyframes:
        try:
            from app.services.keyframe_analysis import KeyframeAnalysisService

            kf_svc = KeyframeAnalysisService(openai_client)

            # Build rep metrics dicts for keyframe analysis
            rep_metric_repo_kf = RepMetricRepository(repo.db)
            db_rep_metrics_kf = await rep_metric_repo_kf.get_by_analysis(analysis_id)
            rep_metrics_for_kf = [
                {"rep_number": rm.rep_index + 1, **(rm.metrics_json or {})}
                for rm in db_rep_metrics_kf
            ]

            kf_result = await kf_svc.analyze_keyframes(
                keyframes=pipeline_result.keyframes,
                exercise_type=analysis.exercise_type,
                exercise_variant=analysis.exercise_variant,
                rep_metrics=rep_metrics_for_kf,
            )
            # Serialize to text for coaching prompt
            keyframe_analysis_text = kf_result.model_dump_json(indent=2)
            logger.info("GPT-4o keyframe analysis completed for %s", analysis_id)
        except Exception:
            logger.warning(
                "GPT-4o keyframe analysis failed for %s — continuing without",
                analysis_id,
                exc_info=True,
            )

    await _write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Body stats (FR-AICP-05) — best-effort
    # ------------------------------------------------------------------ #
    body_stats: dict | None = None
    try:
        from app.repositories.user_profile import UserProfileRepository

        profile_repo = UserProfileRepository(repo.db)
        profile = await profile_repo.get_by_user_id(analysis.user_id)
        if profile:
            body_stats = {
                attr: getattr(profile, attr)
                for attr in _USER_PROFILE_BODY_STATS_FIELDS
                if getattr(profile, attr, None) is not None
            }
            if not body_stats:
                body_stats = None
    except Exception:
        logger.warning(
            "Failed to fetch user profile for %s — coaching without body stats",
            analysis_id,
        )

    # ------------------------------------------------------------------ #
    # Coaching: Claude Sonnet streaming via CoachingService (Phase 1/2)
    # ------------------------------------------------------------------ #
    coaching_repo = CoachingResultRepository(repo.db)

    rep_metric_repo = RepMetricRepository(repo.db)
    db_rep_metrics = await rep_metric_repo.get_by_analysis(analysis_id)
    rep_metrics_dicts = [
        {
            "rep_number": rm.rep_index + 1,
            **(rm.metrics_json or {}),
        }
        for rm in db_rep_metrics
    ]

    client = anthropic.AsyncAnthropic()
    coaching_svc = CoachingService(client, langfuse_client=langfuse_client)

    # Open dedicated Redis for pub/sub (not the ARQ ctx["redis"])
    # Opened early so phase events can be published during retrieval
    pubsub_redis = aioredis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True,
    )
    try:
        # -------------------------------------------------------------- #
        # RAG retrieval — FR-AICP-08 Stage 1 (cite-then-generate)
        # -------------------------------------------------------------- #
        retrieved_contexts: list[RetrievedContext] | None = None
        retrieval_source: str | None = None  # P2-026: routing mode
        degraded_mode = False  # P2-019: tracks Qdrant unavailability

        try:
            await pubsub_redis.publish(
                f"coaching:{analysis_id}",
                _json.dumps({"type": "phase", "phase": "retrieving"}),
            )

            from app.services.cohere_client import get_cohere_client
            from app.services.dual_collection import DualCollectionOrchestrator
            from app.services.qdrant import get_qdrant_client
            from app.services.retrieval import RetrievalService
            from app.services.retrieval_guard import RetrievalGuard
            from app.services.sparse_retrieval import SparseRetrievalService

            cohere_client = get_cohere_client()
            qdrant_wrapper = await get_qdrant_client()

            if qdrant_wrapper is not None:
                sparse_svc = SparseRetrievalService(qdrant_wrapper)
                retrieval_svc = RetrievalService(cohere_client, qdrant_wrapper, sparse_svc)
                orchestrator = DualCollectionOrchestrator(
                    retrieval_svc, cohere_client, langfuse_client=langfuse_client
                )

                retrieval_query = (
                    f"{analysis.exercise_type} {analysis.exercise_variant} technique coaching"
                )
                retrieval_result = await orchestrator.retrieve(
                    query=retrieval_query,
                    exercise_type=analysis.exercise_type,
                )

                guard_result = RetrievalGuard.check(retrieval_result.primary)
                if guard_result.passed:
                    retrieved_contexts = retrieval_result.primary
                    retrieval_source = retrieval_result.retrieval_source
                    logger.info(
                        "Retrieval: %d contexts (source=%s) for analysis %s",
                        len(retrieval_result.primary),
                        retrieval_source,
                        analysis_id,
                    )
                else:
                    logger.warning(
                        "Retrieval guard failed for %s: %s",
                        analysis_id,
                        guard_result.reason,
                    )
            else:
                degraded_mode = True
                logger.warning(
                    "Qdrant unavailable — coaching without RAG contexts for %s "
                    "(degraded mode).",
                    analysis_id,
                )
                if langfuse_client is not None:
                    try:
                        langfuse_client.trace(
                            name="retrieval_degraded",
                            input={
                                "analysis_id": str(analysis_id),
                                "reason": "qdrant_unavailable",
                            },
                        )
                    except Exception:
                        logger.warning("Langfuse trace failed (Qdrant-unavailable branch)", exc_info=True)
                await pubsub_redis.publish(
                    f"coaching:{analysis_id}",
                    _json.dumps({"type": "phase", "phase": "degraded"}),
                )
        except Exception:
            degraded_mode = True
            logger.warning(
                "Retrieval failed for %s — coaching without contexts (degraded mode).",
                analysis_id,
                exc_info=True,
            )
            if langfuse_client is not None:
                try:
                    langfuse_client.trace(
                        name="retrieval_degraded",
                        input={
                            "analysis_id": str(analysis_id),
                            "reason": "retrieval_exception",
                        },
                    )
                except Exception:
                    logger.warning("Langfuse trace failed (retrieval exception branch)", exc_info=True)
            try:
                await pubsub_redis.publish(
                    f"coaching:{analysis_id}",
                    _json.dumps({"type": "phase", "phase": "degraded"}),
                )
            except Exception:
                logger.warning("Redis pub/sub publish failed (best-effort)", exc_info=True)

        await _write_heartbeat(redis)

        # -------------------------------------------------------------- #
        # Generate coaching with retrieved contexts
        # -------------------------------------------------------------- #
        coaching_output = await coaching_svc.generate_coaching_streaming(
            exercise_type=analysis.exercise_type,
            exercise_variant=analysis.exercise_variant,
            rep_metrics=rep_metrics_dicts,
            confidence_score=analysis.confidence_score or 0.0,
            thresholds=thresholds,
            body_stats=body_stats,
            keyframe_analysis_text=keyframe_analysis_text,
            retrieved_contexts=retrieved_contexts,
            retrieval_source=retrieval_source,
            analysis_id=analysis_id,
            pubsub_redis=pubsub_redis,
        )

        # P2-019: stamp degraded_mode on coaching output if Qdrant was unavailable
        if degraded_mode:
            coaching_output = coaching_output.model_copy(update={"degraded_mode": True})

        await _write_heartbeat(redis)

        # -------------------------------------------------------------- #
        # P2-017: Citation cross-reference validation (FR-AICP-10)
        # -------------------------------------------------------------- #
        if retrieved_contexts:
            try:
                from app.services.coaching import build_citation_blocks
                from app.services.validate_output import ValidateOutputTool

                citation_blocks = build_citation_blocks(retrieved_contexts)
                validation_result = ValidateOutputTool.validate(coaching_output, citation_blocks)
                coaching_output = validation_result.output
                if validation_result.has_invalid_citations:
                    logger.warning(
                        "ValidateOutputTool: invalid citation indices %s for analysis %s"
                        " — CoVe will attempt revision",
                        validation_result.invalid_indices,
                        analysis_id,
                    )
            except Exception:
                logger.warning(
                    "Citation validation failed for %s — continuing",
                    analysis_id,
                    exc_info=True,
                )

        await _write_heartbeat(redis)

        # -------------------------------------------------------------- #
        # CoVe verification — FR-AICP-08 Stage 2 (best-effort)
        # -------------------------------------------------------------- #
        cove_verified = False
        agent_trace: dict | None = None

        if retrieved_contexts:
            try:
                await pubsub_redis.publish(
                    f"coaching:{analysis_id}",
                    _json.dumps({"type": "phase", "phase": "verifying"}),
                )

                from app.services.cove import CoveVerificationService

                cove_svc = CoveVerificationService(client)
                cove_result = await cove_svc.verify(
                    initial_output=coaching_output,
                    retrieved_contexts=retrieved_contexts,
                    max_iterations=2,
                )
                coaching_output = cove_result.output
                cove_verified = cove_result.cove_verified
                agent_trace = {
                    "cove_iterations": cove_result.trace,
                    "converged": cove_result.cove_verified,
                }
                logger.info(
                    "CoVe: verified=%s iterations=%d for analysis %s",
                    cove_verified,
                    cove_result.iterations_run,
                    analysis_id,
                )
            except Exception:
                logger.warning(
                    "CoVe failed for %s — continuing with unverified output",
                    analysis_id,
                    exc_info=True,
                )

        await _write_heartbeat(redis)

        # -------------------------------------------------------------- #
        # P2-018: Safety language post-filter (FR-AICP-14)
        # Runs on ALL coaching outputs (RAG-grounded or not)
        # -------------------------------------------------------------- #
        try:
            from app.services.safety_filter import SafetyFilter

            sf_result = SafetyFilter.apply(coaching_output)
            coaching_output = sf_result.output
            if sf_result.injected_disclaimer or sf_result.phrases_replaced > 0:
                logger.info(
                    "SafetyFilter: injected_disclaimer=%s phrases_replaced=%d for %s",
                    sf_result.injected_disclaimer,
                    sf_result.phrases_replaced,
                    analysis_id,
                )
        except Exception:
            logger.warning(
                "SafetyFilter failed for %s — continuing",
                analysis_id,
                exc_info=True,
            )

        await _write_heartbeat(redis)

        # -------------------------------------------------------------- #
        # Faithfulness gate — FR-AICP-08 Stage 3 (best-effort)
        # -------------------------------------------------------------- #
        if retrieved_contexts:
            try:
                from app.services.faithfulness_gate import FaithfulnessGateService

                fg_svc = FaithfulnessGateService(client)
                fg_result = await fg_svc.evaluate(coaching_output, retrieved_contexts)

                # P2-033 (FR-AICP-16): standardised eval_scores including CoVe fields.
                # cove_verified and agent_trace are set in scope above.
                analysis.eval_scores = {
                    "faithfulness": fg_result.score,
                    "faithfulness_passed": fg_result.passed,
                    "unsupported_claims": fg_result.unsupported_claims,
                    "evaluator": "claude-sonnet-4-6-llm-judge",
                    "threshold": 0.8,
                    "cove_verified": cove_verified,
                    "cove_iterations": (
                        len(agent_trace.get("cove_iterations", [])) if agent_trace else 0
                    ),
                }

                if not fg_result.passed:
                    logger.warning(
                        "Faithfulness gate FAILED for %s: score=%.2f — flagging",
                        analysis_id,
                        fg_result.score,
                    )
                    analysis.flagged_for_review = True

                await repo.update(analysis)

                # P2-034 (FR-BRAIN-13): log eval scores to Langfuse (best-effort)
                if langfuse_client is not None:
                    try:
                        langfuse_client.score(
                            trace_id=str(analysis_id),
                            name="faithfulness",
                            value=fg_result.score,
                        )
                        langfuse_client.score(
                            trace_id=str(analysis_id),
                            name="cove_verified",
                            value=1.0 if cove_verified else 0.0,
                        )
                    except Exception:
                        logger.warning("Langfuse score failed (faithfulness gate)", exc_info=True)
            except Exception:
                logger.warning(
                    "Faithfulness gate failed for %s — continuing",
                    analysis_id,
                    exc_info=True,
                )

        await _write_heartbeat(redis)

    finally:
        await pubsub_redis.aclose()

    # Store coaching result in DB
    coaching_result = CoachingResult(
        analysis_id=analysis_id,
        structured_output_json=coaching_output.model_dump(),
        stream_complete=True,
        cove_verified=cove_verified,
        retrieved_sources_json=(
            {
                "contexts": [ctx.model_dump() for ctx in retrieved_contexts],
                "retrieval_source": retrieval_source,
            }
            if retrieved_contexts
            else None
        ),
        agent_trace_json=agent_trace,
        eval_scores_json=analysis.eval_scores,
    )
    await coaching_repo.create(coaching_result)

    await _maybe_enqueue_distillation(
        analysis_id=analysis.id,
        eval_scores=analysis.eval_scores or {},
    )

    return coaching_output, rep_metrics_dicts, body_stats


async def _run_coaching_graph(
    *,
    analysis: Any,
    repo: AnalysisRepository,
    redis: Any,
    pipeline_result: Any,
) -> tuple[Any, list[dict], dict | None]:
    """Phase 3 coaching via LangGraph agent (FR-AICP-18/19/20).

    Returns (coaching_output, rep_metrics_dicts, body_stats) so the caller
    can forward them to _generate_and_upload_pdf.
    """
    import anthropic
    import redis.asyncio as aioredis

    from app.agents.graph import run_coaching_graph
    from app.config import ThresholdConfig as _ThresholdConfig
    from app.models.coaching_result import CoachingResult
    from app.repositories.coaching_result import CoachingResultRepository
    from app.repositories.rep_metric import RepMetricRepository as _RepMetricRepo
    from app.repositories.user_profile import UserProfileRepository
    from app.services.coaching import CoachingService
    from app.services.cohere_client import get_cohere_client
    from app.services.cove import CoveVerificationService
    from app.services.faithfulness_gate import FaithfulnessGateService
    from app.services.langfuse_client import get_langfuse_client
    from app.services.qdrant import get_qdrant_client
    from app.services.retrieval import RetrievalService
    from app.services.sparse_retrieval import SparseRetrievalService

    analysis_id = analysis.id
    mode = os.environ.get("SPELIX_AGENT_MODE", "deterministic")

    thresholds = _ThresholdConfig()

    # Fetch body stats (same logic as imperative path).
    profile_repo = UserProfileRepository(repo.db)
    profile = await profile_repo.get_by_user_id(analysis.user_id)
    body_stats: dict | None = None
    if profile:
        body_stats = {
            attr: getattr(profile, attr)
            for attr in _USER_PROFILE_BODY_STATS_FIELDS
            if getattr(profile, attr, None) is not None
        }
        body_stats = body_stats or None

    # Keyframe analysis — best-effort
    keyframe_analysis_text: str | None = None
    if pipeline_result.keyframes:
        try:
            from app.services.keyframe_analysis import KeyframeAnalysisService

            openai_client = None
            try:
                import openai as _openai

                openai_client = _openai.AsyncOpenAI()
            except Exception:
                logger.warning("OpenAI client init failed (graph path); GPT-4o features disabled", exc_info=True)

            kf_svc = KeyframeAnalysisService(openai_client)
            rep_metric_repo_kf = _RepMetricRepo(repo.db)
            db_rep_metrics_kf = await rep_metric_repo_kf.get_by_analysis(analysis_id)
            rep_metrics_for_kf = [
                {"rep_number": rm.rep_index + 1, **(rm.metrics_json or {})}
                for rm in db_rep_metrics_kf
            ]
            kf_result = await kf_svc.analyze_keyframes(
                keyframes=pipeline_result.keyframes,
                exercise_type=analysis.exercise_type,
                exercise_variant=analysis.exercise_variant,
                rep_metrics=rep_metrics_for_kf,
            )
            keyframe_analysis_text = kf_result.model_dump_json(indent=2)
        except Exception:
            logger.warning(
                "Graph path: keyframe analysis failed for %s — continuing",
                analysis_id,
                exc_info=True,
            )

    # Build rep_metrics_dicts for PDF (same shape as imperative path).
    rep_metric_repo = _RepMetricRepo(repo.db)
    db_rep_metrics = await rep_metric_repo.get_by_analysis(analysis_id)
    rep_metrics_dicts = [
        {"rep_number": rm.rep_index + 1, **(rm.metrics_json or {})}
        for rm in db_rep_metrics
    ]

    # Build dependencies.
    langfuse_client = await get_langfuse_client()
    cohere_client = get_cohere_client()
    qdrant_wrapper = await get_qdrant_client()

    if qdrant_wrapper is not None:
        sparse_svc = SparseRetrievalService(qdrant_wrapper)
        retrieval_svc = RetrievalService(cohere_client, qdrant_wrapper, sparse_svc)
    else:
        logger.warning(
            "Graph path: Qdrant unavailable for %s — degraded mode", analysis_id,
        )

        class _NullRetrieval:
            async def hybrid_search(self, *_a, **_kw):
                return []

        retrieval_svc = _NullRetrieval()  # type: ignore[assignment]

    anthropic_client = anthropic.AsyncAnthropic()
    coaching_svc = CoachingService(anthropic_client, langfuse_client=langfuse_client)
    cove_svc = CoveVerificationService(anthropic_client)
    fg_svc = FaithfulnessGateService(anthropic_client)

    pubsub_redis = aioredis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True,
    )

    reasoner_llm = None
    if mode == "adaptive":
        from langchain_anthropic import ChatAnthropic

        reasoner_llm = ChatAnthropic(
            model_name="claude-sonnet-4-6",
            temperature=0.0,
            max_tokens_to_sample=2048,
            timeout=60.0,
            stop=None,
        )

    try:
        final_state, trace_payload, coaching_output = await run_coaching_graph(
            analysis_id=analysis_id,
            user_id=analysis.user_id,
            exercise_type=analysis.exercise_type,
            exercise_variant=analysis.exercise_variant,
            confidence_score=analysis.confidence_score or 0.0,
            body_stats=body_stats,
            keyframe_analysis_text=keyframe_analysis_text,
            mode=mode,
            rep_metric_repo=rep_metric_repo,
            retrieval_svc=retrieval_svc,
            thresholds=thresholds,
            analysis_repo=repo,
            coaching_svc=coaching_svc,
            cove_svc=cove_svc,
            fg_svc=fg_svc,
            pubsub_redis=pubsub_redis,
            reasoner_llm=reasoner_llm,
        )
    finally:
        await pubsub_redis.aclose()

    if coaching_output is None:
        raise RuntimeError(
            f"graph completed without coaching_output for analysis {analysis_id}"
        )

    # Persist outputs — same shape as imperative path.
    coaching_repo = CoachingResultRepository(repo.db)
    coaching_result = CoachingResult(
        analysis_id=analysis_id,
        structured_output_json=coaching_output.model_dump(),
        stream_complete=True,
        cove_verified=bool(final_state.get("cove_verified")),
        retrieved_sources_json=(
            {
                "contexts": [
                    ctx.model_dump()
                    for ctx in (final_state.get("papers_contexts") or [])
                    + (final_state.get("brain_contexts") or [])
                    if hasattr(ctx, "model_dump")
                ],
                "retrieval_source": final_state.get("retrieval_source"),
            }
            if (
                final_state.get("papers_contexts") or final_state.get("brain_contexts")
            )
            else None
        ),
        agent_trace_json=trace_payload,
    )
    await coaching_repo.create(coaching_result)

    # Persist eval_scores + flagged_for_review to analyses row.
    eval_scores = final_state.get("eval_scores") or {}
    if eval_scores:
        analysis.eval_scores = eval_scores
        coaching_result.eval_scores_json = eval_scores
        if eval_scores.get("faithfulness_passed") is False:
            analysis.flagged_for_review = True
        await repo.update(analysis)

    await _maybe_enqueue_distillation(
        analysis_id=analysis.id,
        eval_scores=analysis.eval_scores or {},
    )

    return coaching_output, rep_metrics_dicts, body_stats


async def _dispatch_coaching(
    *,
    analysis: Any,
    repo: Any,
    redis: Any,
    pipeline_result: Any,
) -> tuple[Any, list[dict], dict | None]:
    """Route coaching to graph or imperative path based on env flag.

    Returns (coaching_output, rep_metrics_dicts, body_stats) for the PDF step.
    """
    if os.environ.get("SPELIX_PHASE3_AGENT_ENABLED", "0").lower() in (
        "1",
        "true",
        "yes",
    ):
        return await _run_coaching_graph(
            analysis=analysis,
            repo=repo,
            redis=redis,
            pipeline_result=pipeline_result,
        )
    else:
        return await _run_coaching_imperative(
            analysis=analysis,
            repo=repo,
            redis=redis,
            pipeline_result=pipeline_result,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _maybe_enqueue_distillation(
    *,
    analysis_id: uuid.UUID,
    eval_scores: dict[str, Any],
) -> None:
    """Phase 3 Batch 2: enqueue the distillation pipeline when gated.

    Gate: SPELIX_DISTILLATION_ENABLED env=1 AND quality score >= 0.6.
    Quality score is `eval_scores.overall` if present (Phase 4 RAGAS
    multi-component aggregate), else falls back to `eval_scores.faithfulness`
    (Phase 2 LLM-as-judge per ADR-RAG-04 — Phase 4 will add the full RAGAS
    suite). Failure is swallowed as a warning — distillation MUST NEVER fail
    the user-facing analysis.
    """
    flag = os.environ.get("SPELIX_DISTILLATION_ENABLED", "0").lower()
    if flag not in ("1", "true", "yes"):
        return
    scores = eval_scores or {}
    quality = scores.get("overall")
    if quality is None:
        quality = scores.get("faithfulness")
    if quality is None or quality < 0.6:
        return
    try:
        # Wrapper lives alongside other task wrappers in streaq_worker.py;
        # body lives in distillation_worker.py (same pattern as process_analysis).
        from app.workers.streaq_worker import distill_analysis as _task

        await _task.enqueue(analysis_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("distillation enqueue failed (%s: %s)", type(exc).__name__, exc)


async def _write_heartbeat(redis: Any) -> None:
    """Write the operator heartbeat key with a 90-second TTL (NFR-OPER-02)."""
    await redis.set(_HEARTBEAT_KEY, "alive", ex=_HEARTBEAT_TTL)


def _is_terminal(status: str, retry_count: int) -> bool:
    """Return True if the analysis is in a terminal state and must not be re-processed."""
    if status in _TERMINAL_STATES:
        return True
    if status == "failed" and retry_count >= 3:
        return True
    return False


_STORAGE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "videos")


async def _generate_and_upload_pdf(
    *,
    analysis_id: uuid.UUID,
    analysis: Any,
    coaching_output: Any,
    rep_metrics_dicts: list[dict],
    storage_client: Any,
    repo: AnalysisRepository,
    bar_path: dict | None = None,
    keyframes: list | None = None,
    body_stats: dict | None = None,
) -> None:
    """Generate PDF report, upload to Storage, and write pdf_path to DB."""
    import asyncio
    from datetime import UTC, datetime

    from app.cv.artifact_generation import (
        get_artifact_storage_path,
        get_temp_dir,
        upload_artifact,
    )
    from app.cv.confidence import confidence_label
    from app.services.pdf import PDFService, generate_bar_path_plot

    loop = asyncio.get_event_loop()
    tmp_dir = get_temp_dir(analysis_id)
    pdf_local = os.path.join(tmp_dir, "report.pdf")
    plot_local = os.path.join(tmp_dir, "angles.png")

    conf_score = analysis.confidence_score or 0.0
    conf_label = confidence_label(conf_score)

    coaching_dict = coaching_output.model_dump() if hasattr(coaching_output, "model_dump") else coaching_output

    # Build user_info string from body stats
    user_info = ""
    if body_stats:
        parts: list[str] = []
        if "experience_level" in body_stats:
            parts.append(body_stats["experience_level"].replace("_", " ").title())
        if "height_cm" in body_stats:
            parts.append(f"{body_stats['height_cm']}cm")
        if "weight_kg" in body_stats:
            parts.append(f"{body_stats['weight_kg']}kg")
        if parts:
            user_info = " · ".join(parts)

    # Generate bar path plot if centroid data available
    bar_path_plot_path: str | None = None
    if bar_path and bar_path.get("centroids"):
        bar_path_plot_local = os.path.join(tmp_dir, "bar_path.png")
        try:
            await loop.run_in_executor(
                None, generate_bar_path_plot, bar_path, bar_path_plot_local,
            )
            if os.path.isfile(bar_path_plot_local):
                bar_path_plot_path = bar_path_plot_local
        except Exception:
            logger.warning("Bar path plot generation failed — skipping")

    context = {
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "exercise_type": analysis.exercise_type,
        "exercise_variant": analysis.exercise_variant,
        "confidence_score": conf_score,
        "confidence_label": conf_label,
        "rep_count": len(rep_metrics_dicts),
        "rep_metrics": rep_metrics_dicts,
        "coaching": coaching_dict,
        "plot_path": plot_local if os.path.isfile(plot_local) else None,
        "bar_path_plot_path": bar_path_plot_path,
        "keyframes": keyframes or [],
        "user_info": user_info,
        "quality_gate_result": analysis.quality_gate_result,
        "scores": {
            "form_score_safety": analysis.form_score_safety,
            "form_score_technique": analysis.form_score_technique,
            "form_score_path_balance": analysis.form_score_path_balance,
            "form_score_control": analysis.form_score_control,
            "form_score_overall": analysis.form_score_overall,
        },
        "disclaimer": (
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
    }

    try:
        pdf_svc = PDFService()
        await loop.run_in_executor(None, pdf_svc.generate_pdf, context, pdf_local)

        if storage_client is not None:
            pdf_storage = get_artifact_storage_path(analysis_id, "report.pdf")
            await upload_artifact(storage_client, _STORAGE_BUCKET, pdf_local, pdf_storage)
            analysis.pdf_path = pdf_storage
            await repo.update(analysis)
            logger.info("PDF uploaded for analysis %s → %s", analysis_id, pdf_storage)
        else:
            analysis.pdf_path = pdf_local
            await repo.update(analysis)
    except Exception:
        logger.exception("PDF generation failed for analysis %s — continuing", analysis_id)


# ---------------------------------------------------------------------------
# ARQ job entry point
# ---------------------------------------------------------------------------


async def process_analysis(ctx: dict[str, Any], analysis_id: uuid.UUID) -> None:
    """ARQ job: run the full analysis pipeline for the given analysis_id.

    Idempotent — safe to enqueue multiple times. If the analysis is already
    in a terminal state (completed, quality_gate_rejected, or failed with
    retry_count >= 3), the job returns immediately without touching the DB.
    """
    redis = ctx["redis"]

    async with async_session() as session:
        repo = AnalysisRepository(session)

        # ---------------------------------------------------------------- #
        # Idempotency guard (NFR-RELI-01)
        # ---------------------------------------------------------------- #
        analysis = await repo.get_by_id(analysis_id)
        if analysis is None:
            logger.error("process_analysis: analysis %s not found — aborting", analysis_id)
            return

        if _is_terminal(analysis.status, analysis.retry_count):
            logger.info(
                "process_analysis: analysis %s is already terminal (status=%s, retries=%d) — no-op",
                analysis_id,
                analysis.status,
                analysis.retry_count,
            )
            return

        # ---------------------------------------------------------------- #
        # Write initial heartbeat before pipeline starts (NFR-OPER-02)
        # ---------------------------------------------------------------- #
        await _write_heartbeat(redis)

        # ---------------------------------------------------------------- #
        # Run pipeline with error handling (NFR-RELI-02 through NFR-RELI-04)
        #
        # Session lifecycle: SQLAlchemy AsyncSession's autocommit=False
        # default rolls back the implicit transaction when the session
        # closes. We MUST commit explicitly on success AND on the error
        # path (after writing the failed-state row), otherwise every
        # status transition the worker performs is silently discarded.
        # Same root cause as the get_db() bug fixed in db.py.
        # ---------------------------------------------------------------- #
        try:
            await _run_pipeline(analysis_id, repo, redis)
            await session.commit()

        except Exception as exc:
            logger.exception(
                "process_analysis: pipeline failed for analysis %s: %s",
                analysis_id,
                exc,
            )
            # Discard any partial in-flight writes from the failed pipeline,
            # then re-fetch and write the failed-state row in a clean txn.
            await session.rollback()

            analysis = await repo.get_by_id(analysis_id)
            if analysis is None:
                logger.error(
                    "process_analysis: analysis %s disappeared during error handling",
                    analysis_id,
                )
                return

            analysis.error_message = str(exc)
            analysis.retry_count = (analysis.retry_count or 0) + 1

            # Force status → failed unless the row is already in a state
            # that can't legally transition to ``failed``:
            #   - ``completed`` / ``quality_gate_rejected``: terminal soft
            #     success states; idempotency check at the top should have
            #     caught these, but defend against re-entry
            #   - ``failed``: already there, calling
            #     ``transition('failed', 'failed')`` would self-transition
            #     and the guard would reject it. We still need to update
            #     error_message + retry_count for the new failure context,
            #     so don't skip the whole branch — just skip the transition.
            if analysis.status not in _TERMINAL_STATES and analysis.status != "failed":
                analysis.status = transition(analysis.status, "failed")

            await repo.update(analysis)
            await session.commit()

        finally:
            # Always clean up temp files
            cleanup_temp_files(analysis_id)
