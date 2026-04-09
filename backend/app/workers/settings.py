"""
ARQ WorkerSettings for the Spelix analysis pipeline.

Configuration per CLAUDE.md / backend/CLAUDE.md:
  queue_name  = "arq:queue"
  job_timeout = 300
  max_jobs    = 1   (MediaPipe peak ~350 MB on 2 GB droplet)
  keep_result = 0   (no result storage needed)
"""

from __future__ import annotations

import asyncio
import logging
import os

from arq.connections import RedisSettings
from arq.cron import cron

from app.workers.analysis_worker import process_analysis
from app.workers.cleanup import cleanup_expired_artifacts

logger = logging.getLogger(__name__)

_HEARTBEAT_KEY = "spelix:worker:heartbeat"
_HEARTBEAT_TTL = 90
_HEARTBEAT_INTERVAL = 30


async def _heartbeat_loop(redis: object) -> None:
    """Write heartbeat every 30s with 90s TTL (NFR-OPER-02)."""
    while True:
        try:
            await redis.set(_HEARTBEAT_KEY, "alive", ex=_HEARTBEAT_TTL)  # type: ignore[union-attr]
        except Exception:
            logger.warning("Failed to write worker heartbeat")
        await asyncio.sleep(_HEARTBEAT_INTERVAL)


async def on_startup(ctx: dict) -> None:
    """Start continuous heartbeat loop."""
    ctx["_heartbeat_task"] = asyncio.create_task(_heartbeat_loop(ctx["redis"]))
    logger.info("Worker started — heartbeat loop active")


async def on_shutdown(ctx: dict) -> None:
    """Cancel heartbeat task on worker shutdown."""
    task = ctx.get("_heartbeat_task")
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Worker shutdown — heartbeat loop stopped")


class WorkerSettings:
    """ARQ worker configuration (NFR-RELI-01 through NFR-RELI-04, NFR-OPER-02)."""

    queue_name: str = "arq:queue"
    job_timeout: int = 300
    max_jobs: int = 1
    keep_result: int = 0

    redis_settings: RedisSettings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379"))

    functions = [process_analysis]
    cron_jobs = [
        cron(cleanup_expired_artifacts, hour=3, minute=0),  # 03:00 UTC nightly
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
