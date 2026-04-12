"""Nightly Qdrant keepalive cron for ADR-P2-001.

Free-tier Qdrant Cloud clusters pause after ~1 week of inactivity.
This cron job pings the cluster every night so it stays warm.

Requirements: ADR-P2-001 (Qdrant Cloud free tier — nightly keepalive required).

The job is registered in WorkerSettings.cron_jobs as a daily ping at 02:00 UTC,
distinct from the 03:00 artifact cleanup to avoid overlap.
"""

from __future__ import annotations

import logging

from app.services.qdrant import get_qdrant_client

logger = logging.getLogger(__name__)


async def ping_qdrant_health(ctx: dict) -> None:  # noqa: ARG001
    """Ping Qdrant to prevent free-tier cluster from pausing (ADR-P2-001).

    Steps:
    1. Get the cached QdrantClientWrapper from the factory.
    2. Call wrapper.ping() — returns True on success, False on failure.
    3. Log a WARNING if unavailable (missing config or ping failed) but
       NEVER raise — a failed keepalive must not abort the worker.

    Parameters
    ----------
    ctx:
        ARQ job context (unused — all state is fetched via the factory).
    """
    try:
        wrapper = await get_qdrant_client()
    except Exception as exc:
        logger.warning("ping_qdrant_health: failed to get Qdrant client: %s", exc)
        return

    if wrapper is None:
        logger.warning(
            "ping_qdrant_health: Qdrant client unavailable (QDRANT_URL not set) — skipping"
        )
        return

    try:
        healthy = await wrapper.ping()
    except Exception as exc:
        logger.warning("ping_qdrant_health: ping raised unexpectedly: %s", exc)
        return

    if not healthy:
        logger.warning(
            "ping_qdrant_health: Qdrant cluster did not respond — cluster may be paused or unreachable"
        )
    else:
        logger.info("ping_qdrant_health: Qdrant cluster is healthy")
