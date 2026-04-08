"""
ARQ WorkerSettings for the Spelix analysis pipeline.

Configuration per CLAUDE.md / backend/CLAUDE.md:
  queue_name  = "arq:queue"
  job_timeout = 300
  max_jobs    = 1   (MediaPipe peak ~350 MB on 2 GB droplet)
  keep_result = 0   (no result storage needed)
"""

from __future__ import annotations

import os

from arq.connections import RedisSettings

from app.workers.analysis_worker import process_analysis


async def on_startup(ctx: dict) -> None:  # noqa: ARG001
    """Initialise shared resources that worker jobs can read from ctx."""
    # DB session factory is imported directly in process_analysis via async_session.
    # No additional startup work needed for the skeleton — real steps (B-012+) may
    # add Supabase Storage client, threshold config load, etc. here.


async def on_shutdown(ctx: dict) -> None:  # noqa: ARG001
    """Tear down shared resources on worker shutdown."""
    # Placeholder — real cleanup (close HTTP clients, etc.) added in later tasks.


class WorkerSettings:
    """ARQ worker configuration (NFR-RELI-01 through NFR-RELI-04, NFR-OPER-02)."""

    queue_name: str = "arq:queue"
    job_timeout: int = 300
    max_jobs: int = 1
    keep_result: int = 0

    redis_settings: RedisSettings = RedisSettings.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))

    functions = [process_analysis]
    on_startup = on_startup
    on_shutdown = on_shutdown
