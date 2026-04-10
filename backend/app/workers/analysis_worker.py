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

import anthropic

from app.config import ThresholdConfig
from app.cv.artifact_generation import (
    cleanup_temp_files,
)
from app.db import async_session
from app.models.coaching_result import CoachingResult
from app.repositories.analysis import AnalysisRepository
from app.repositories.coaching_result import CoachingResultRepository
from app.repositories.rep_metric import RepMetricRepository
from app.services.coaching import CoachingService
from app.services.pipeline import QualityGateRejection, run_cv_pipeline
from app.services.status import transition
from app.services.summary import SummaryService

logger = logging.getLogger(__name__)

# Terminal states: if an analysis is in one of these, the worker is a no-op.
_TERMINAL_STATES = frozenset({"completed", "quality_gate_rejected"})

# Heartbeat key and TTL (seconds)
_HEARTBEAT_KEY = "spelix:worker:heartbeat"
_HEARTBEAT_TTL = 90  # seconds


# ---------------------------------------------------------------------------
# Internal pipeline
# ---------------------------------------------------------------------------


def _build_supabase_client() -> Any | None:
    """Build a Supabase client from env vars, or None if unconfigured."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception as e:
        logger.warning("Failed to create Supabase client: %s", e)
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
    storage_client = _build_supabase_client()
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
                body_stats = {}
                for attr in ("height_cm", "weight_kg", "age", "experience_level", "arm_span_cm", "femur_length_cm"):
                    val = getattr(profile, attr, None)
                    if val is not None:
                        body_stats[attr] = val
                if not body_stats:
                    body_stats = None
        except Exception:
            logger.warning(
                "Failed to fetch user profile for %s — coaching without body stats",
                analysis_id,
            )

        # ------------------------------------------------------------------ #
        # Coaching: Claude Sonnet streaming via CoachingService (Phase 1)
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
        coaching_svc = CoachingService(client)

        # Open dedicated Redis for pub/sub (not the ARQ ctx["redis"])
        import redis.asyncio as aioredis

        pubsub_redis = aioredis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
        )
        try:
            coaching_output = await coaching_svc.generate_coaching_streaming(
                exercise_type=analysis.exercise_type,
                exercise_variant=analysis.exercise_variant,
                rep_metrics=rep_metrics_dicts,
                confidence_score=analysis.confidence_score or 0.0,
                thresholds=thresholds,
                body_stats=body_stats,
                keyframe_analysis_text=keyframe_analysis_text,
                analysis_id=analysis_id,
                pubsub_redis=pubsub_redis,
            )
        finally:
            await pubsub_redis.aclose()

        # Store coaching result in DB
        coaching_result = CoachingResult(
            analysis_id=analysis_id,
            structured_output_json=coaching_output.model_dump(),
            stream_complete=True,
            cove_verified=False,
        )
        await coaching_repo.create(coaching_result)

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
# Helpers
# ---------------------------------------------------------------------------


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
    from app.services.pdf import PDFService

    loop = asyncio.get_event_loop()
    tmp_dir = get_temp_dir(analysis_id)
    pdf_local = os.path.join(tmp_dir, "report.pdf")
    plot_local = os.path.join(tmp_dir, "angles.png")

    conf_score = analysis.confidence_score or 0.0
    conf_label = confidence_label(conf_score)

    coaching_dict = coaching_output.model_dump() if hasattr(coaching_output, "model_dump") else coaching_output

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
        # ---------------------------------------------------------------- #
        try:
            await _run_pipeline(analysis_id, repo, redis)

        except Exception as exc:
            logger.exception(
                "process_analysis: pipeline failed for analysis %s: %s",
                analysis_id,
                exc,
            )
            # Re-fetch to get the latest state (in case transitions occurred)
            analysis = await repo.get_by_id(analysis_id)
            if analysis is None:
                logger.error(
                    "process_analysis: analysis %s disappeared during error handling",
                    analysis_id,
                )
                return

            analysis.error_message = str(exc)
            analysis.retry_count = (analysis.retry_count or 0) + 1

            # Force status → failed for any non-terminal state.
            if analysis.status not in _TERMINAL_STATES:
                analysis.status = transition(analysis.status, "failed")

            await repo.update(analysis)

        finally:
            # Always clean up temp files
            cleanup_temp_files(analysis_id)
