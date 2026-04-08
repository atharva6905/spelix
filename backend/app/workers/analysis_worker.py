"""ARQ worker — analysis pipeline entry point (B-011 skeleton, B-022 wired).

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


import anthropic  # noqa: F401 — used at runtime in _run_pipeline

from app.config import ThresholdConfig  # noqa: F401
from app.cv.artifact_generation import cleanup_temp_files
from app.db import async_session
from app.models.coaching_result import CoachingResult  # noqa: F401
from app.repositories.analysis import AnalysisRepository
from app.repositories.coaching_result import CoachingResultRepository  # noqa: F401
from app.repositories.rep_metric import RepMetricRepository
from app.services.coaching import CoachingService  # noqa: F401
from app.services.pipeline import QualityGateRejection, run_cv_pipeline
from app.services.status import transition

logger = logging.getLogger(__name__)

# Terminal states: if an analysis is in one of these, the worker is a no-op.
_TERMINAL_STATES = frozenset({"completed", "quality_gate_rejected"})

# Heartbeat key and TTL (seconds)
_HEARTBEAT_KEY = "spelix:worker:heartbeat"
_HEARTBEAT_TTL = 90  # seconds


# ---------------------------------------------------------------------------
# Internal pipeline — wired to real CV pipeline (B-022)
# ---------------------------------------------------------------------------


def _build_supabase_client() -> Any | None:
    """Build a Supabase client from env vars, or None if unconfigured."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
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
    rep_metric_repo = RepMetricRepository(repo._db)

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
        )

        # ------------------------------------------------------------------ #
        # Transition: processing → coaching (B-024)
        # ------------------------------------------------------------------ #
        analysis = await repo.get_by_id(analysis_id)
        if analysis is None:
            raise ValueError(f"Analysis {analysis_id} disappeared during pipeline")

        analysis.status = transition(analysis.status, "coaching")
        await repo.update(analysis)
        await _write_heartbeat(redis)

        # ------------------------------------------------------------------ #
        # Coaching: call Claude Sonnet via CoachingService (B-024)
        # ------------------------------------------------------------------ #
        coaching_repo = CoachingResultRepository(repo._db)
        thresholds = ThresholdConfig()

        # Build rep metrics dicts for coaching prompt
        rep_metric_repo = RepMetricRepository(repo._db)
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

        coaching_output = await coaching_svc.generate_coaching(
            exercise_type=analysis.exercise_type,
            exercise_variant=analysis.exercise_variant,
            rep_metrics=rep_metrics_dicts,
            confidence_score=analysis.confidence_score or 0.0,
            thresholds=thresholds,
        )

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
    await redis.set(_HEARTBEAT_KEY, "1", ex=_HEARTBEAT_TTL)


def _is_terminal(status: str, retry_count: int) -> bool:
    """Return True if the analysis is in a terminal state and must not be re-processed."""
    if status in _TERMINAL_STATES:
        return True
    if status == "failed" and retry_count >= 3:
        return True
    return False


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
                analysis.status = "failed"

            await repo.update(analysis)

        finally:
            # Always clean up temp files
            cleanup_temp_files(analysis_id)
