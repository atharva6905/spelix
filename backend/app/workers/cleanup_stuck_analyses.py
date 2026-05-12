"""
streaq periodic cleanup job — auto-fail analyses stuck in non-terminal states.

Nightly hard-fail of ``analyses`` rows that have been stuck in a non-terminal,
non-rejected status for more than 2 hours.

An analysis is considered stuck when:
  - ``status IN ('queued', 'quality_gate_pending', 'processing')``
  - ``updated_at < NOW() - 2 hours``

For each stuck row:
  1. Issues an UPDATE setting ``status='failed'`` and an explanatory
     ``error_message`` that names the prior status.
  2. Commits per-row so a later failure cannot roll back an already-fixed row.

DB errors are caught and logged per-row; the job continues with remaining rows
so one failure cannot block the rest. On error the transaction is rolled back
and the row is left for the next nightly run.

Architecture notes:
  - 2-hour window matches the artifact cleanup cron and orphan-papers cron —
    any analysis that hasn't progressed in 2 hours is genuinely stuck (TUS
    uploads complete in <90 s; pose extraction takes <10 min on a typical clip).
  - All three transitions (queued→failed, quality_gate_pending→failed,
    processing→failed) are valid per ``app/services/status.py`` transition table.
  - No Storage client needed — DB-only operation.
  - Registered as a streaq cron in ``streaq_worker.py`` at 03:30 UTC (between
    the artifact cleanup at 03:00 and orphan-papers cleanup at 04:00).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select, update

from app.db import async_session
from app.models.analysis import Analysis

logger = logging.getLogger(__name__)

_STUCK_AGE_HOURS = 2
_STUCK_STATUSES = ("queued", "quality_gate_pending", "processing")


async def cleanup_stuck_analyses(ctx: dict) -> int:  # noqa: ARG001
    """streaq periodic job: auto-fail analyses stuck in non-terminal states.

    Finds all ``analyses`` rows with a non-terminal status whose ``updated_at``
    predates the 2-hour cutoff.  For each such row:

    1. UPDATEs ``status`` to ``'failed'`` and sets ``error_message`` to explain
       which status the row was stuck in.
    2. Commits per-row.

    DB errors for a single row are caught and logged; the job continues with
    the remaining rows.  On failure the transaction is rolled back and the row
    is left for the next nightly run.

    Parameters
    ----------
    ctx:
        ARQ-style context dict (unused but required by the job signature).

    Returns
    -------
    int
        Number of rows successfully auto-failed.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=_STUCK_AGE_HOURS)).replace(
        tzinfo=None
    )

    failed_count = 0

    async with async_session() as session:
        stmt = select(Analysis).where(
            and_(
                Analysis.status.in_(_STUCK_STATUSES),
                Analysis.updated_at < cutoff,
            )
        )
        result = await session.execute(stmt)
        stuck = result.scalars().all()

        logger.info(
            "cleanup_stuck_analyses: found %d stuck analyses (cutoff=%s)",
            len(stuck),
            cutoff.isoformat(),
        )

        for analysis in stuck:
            old_status = analysis.status
            try:
                await session.execute(
                    update(Analysis)
                    .where(Analysis.id == analysis.id)
                    .values(
                        status="failed",
                        error_message=(
                            f"Auto-failed: analysis stuck in '{old_status}' "
                            f"for over {_STUCK_AGE_HOURS} hours"
                        ),
                    )
                )
                await session.commit()
                failed_count += 1
                logger.info(
                    "cleanup_stuck_analyses: auto-failed %s (was '%s')",
                    analysis.id,
                    old_status,
                )
            except Exception:
                await session.rollback()
                logger.exception(
                    "cleanup_stuck_analyses: failed to update %s — skipping",
                    analysis.id,
                )

    logger.info(
        "cleanup_stuck_analyses: completed — %d auto-failed",
        failed_count,
    )
    return failed_count
