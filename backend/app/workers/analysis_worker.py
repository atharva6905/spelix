"""
ARQ worker — analysis pipeline entry point (B-011 skeleton).

Implements FR-UPLD-18 (async processing), NFR-RELI-01 through NFR-RELI-04
(reliability: idempotent, error handling, retry limit, heartbeat),
NFR-OPER-02 (operator heartbeat visibility).

Each pipeline step is a stub with a comment; real logic wired in B-012–B-024.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.db import async_session
from app.repositories.analysis import AnalysisRepository
from app.services.status import transition

logger = logging.getLogger(__name__)

# Terminal states: if an analysis is in one of these, the worker is a no-op.
_TERMINAL_STATES = frozenset({"completed", "quality_gate_rejected"})

# Heartbeat key and TTL (seconds)
_HEARTBEAT_KEY = "spelix:worker:heartbeat"
_HEARTBEAT_TTL = 90  # seconds


# ---------------------------------------------------------------------------
# Internal pipeline stub — extracted so tests can patch it cleanly
# ---------------------------------------------------------------------------


async def _run_pipeline(
    analysis_id: uuid.UUID,
    repo: AnalysisRepository,
    redis: Any,
) -> None:
    """
    Execute the full analysis pipeline, updating status at each stage.

    Each step is a stub for B-011. Real implementations are wired in later tasks:
      B-012: quality gate (body visibility + framing)
      B-013: pose extraction (MediaPipe BlazePose Heavy)
      B-014: rep detection state machine
      B-015: metric extraction
      B-016: scoring
      B-017: artifact generation (annotated MP4, PNG plot)
      B-018: coaching (Claude Sonnet 4.6 via instructor)
      B-019: summary_json + confidence_score write-back

    Status transition sequence (SRS Section 5.2a):
      queued → quality_gate_pending → processing → coaching → completed
    """
    analysis = await repo.get_by_id(analysis_id)
    if analysis is None:
        raise ValueError(f"Analysis {analysis_id} not found in DB")

    # ------------------------------------------------------------------ #
    # Transition 1: queued → quality_gate_pending
    # ------------------------------------------------------------------ #
    analysis.status = transition(analysis.status, "quality_gate_pending")
    await repo.update(analysis)
    await _write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Step 1: Download video from Supabase Storage (stub)
    # Real: fetch signed URL, stream to /tmp/spelix/{analysis_id}.mp4
    # ------------------------------------------------------------------ #
    # TODO(B-012): download video
    # video_path = f"/tmp/spelix/{analysis_id}.mp4"

    # ------------------------------------------------------------------ #
    # Step 2: Run quality gates (stub — always passes for now)
    # Real: body visibility gate + framing gate (backend/CLAUDE.md)
    # On rejection: analysis.status = transition(analysis.status, "quality_gate_rejected")
    # ------------------------------------------------------------------ #
    # TODO(B-012): quality gates

    # ------------------------------------------------------------------ #
    # Transition 2: quality_gate_pending → processing
    # ------------------------------------------------------------------ #
    analysis.status = transition(analysis.status, "processing")
    await repo.update(analysis)
    await _write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Step 3: Run CV pipeline — pose extraction, rep detection, metrics (stub)
    # Real: await loop.run_in_executor(None, run_cv_pipeline, video_path, ...)
    # ------------------------------------------------------------------ #
    # TODO(B-013 through B-017): CV pipeline

    # ------------------------------------------------------------------ #
    # Transition 3: processing → coaching
    # ------------------------------------------------------------------ #
    analysis.status = transition(analysis.status, "coaching")
    await repo.update(analysis)
    await _write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Step 4: Run coaching via Claude Sonnet 4.6 (stub)
    # Real: instructor-wrapped anthropic call; result → coaching_results table
    # ------------------------------------------------------------------ #
    # TODO(B-018): LLM coaching

    # ------------------------------------------------------------------ #
    # Step 5: Cleanup temp files (stub)
    # Real: os.unlink(video_path); delete Storage copy (not after quality gate —
    #       only after CV pipeline completes per CLAUDE.md architecture notes)
    # ------------------------------------------------------------------ #
    # TODO(B-019): cleanup

    # ------------------------------------------------------------------ #
    # Transition 4: coaching → completed
    # ------------------------------------------------------------------ #
    analysis.status = transition(analysis.status, "completed")
    await repo.update(analysis)


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
    """
    ARQ job: run the full analysis pipeline for the given analysis_id.

    Idempotent — safe to enqueue multiple times. If the analysis is already
    in a terminal state (completed, quality_gate_rejected, or failed with
    retry_count >= 3), the job returns immediately without touching the DB.

    Args:
        ctx:         ARQ context dict, must contain 'redis' key.
        analysis_id: UUID of the analyses row to process.
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
            # transition() only allows processing/coaching → failed per SRS 5.2a, but
            # exceptions can fire before those transitions occur (e.g. during download).
            # Emergency error recovery bypasses the guard; terminal states are left as-is.
            if analysis.status not in _TERMINAL_STATES:
                analysis.status = "failed"

            await repo.update(analysis)
