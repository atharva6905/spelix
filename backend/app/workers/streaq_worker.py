"""streaq Worker for the Spelix background job queue.

Replaces ARQ (ADR-BRAIN-04-reversal). Drop-in scope only — no task graphs,
no middleware, no priority tiers during the L2 sprint.

Shape:
  - `worker`: the streaq.Worker instance. `streaq app.workers.streaq_worker:worker`
    launches the worker process.
  - `WorkerContext`: deps dataclass supplied via the lifespan context manager.
    Fields mirror the ARQ ctx dict keys the task bodies already read, plus a
    redis client (streaq 6.4.0 does NOT expose redis via task context; it
    must be carried on the deps dataclass).
  - Task wrappers: `process_analysis`, `cascade_consent_withdrawal`,
    `ingest_paper` — thin decorators around the existing task functions
    (which still accept the ARQ-style `ctx: dict`).
  - Cron wrappers: `cleanup_expired_artifacts_cron`, `ping_qdrant_health_cron`.

streaq 6.4.0 DI pattern (verified from installed source):
  - Task signature uses `WorkerDepends()` marker as a parameter default:
      `async def my_task(arg: T, context: WorkerContext = WorkerDepends()) -> R:`
  - `lifespan()` takes zero args and yields the deps dataclass.
  - `TaskContext` is separate metadata (fn_name, task_id, tries) injected via
    `TaskDepends()` — we don't use it in this drop-in.

The FastAPI web process imports the task references (e.g. `process_analysis`)
to call `.enqueue()` on them. See `backend/app/api/v1/analyses.py::_get_streaq_worker`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from uuid import UUID

import redis.asyncio as aioredis
from streaq import Worker, WorkerDepends

logger = logging.getLogger(__name__)

_HEARTBEAT_KEY = "spelix:worker:heartbeat"
_HEARTBEAT_TTL = 90  # seconds
_HEARTBEAT_INTERVAL = 30  # seconds

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


@dataclass
class WorkerContext:
    """Deps injected into every task via `WorkerDepends()`.

    `redis` is the live async redis client created in `lifespan()` — task
    bodies read it via the adapter for mid-pipeline heartbeat writes.
    `paper_storage` and `db_session_maker` stay None in this migration —
    P2-005 will wire them when Docling ingestion lands.
    """

    redis: Any
    paper_storage: Any = None
    db_session_maker: Any = None
    heartbeat_task: asyncio.Task | None = field(default=None, repr=False)


async def _heartbeat_loop(redis: Any) -> None:
    """Write `spelix:worker:heartbeat` with 90s TTL every 30s (NFR-OPER-02)."""
    while True:
        try:
            await redis.set(_HEARTBEAT_KEY, "alive", ex=_HEARTBEAT_TTL)
        except Exception:
            logger.warning("Failed to write worker heartbeat")
        await asyncio.sleep(_HEARTBEAT_INTERVAL)


@asynccontextmanager
async def lifespan() -> AsyncIterator[WorkerContext]:
    """Startup/teardown: open redis, launch heartbeat loop, expose deps.

    streaq 6.4.0 expects a zero-arg async context manager that yields the
    deps dataclass. The Worker uses the yielded value as the injection
    target for every parameter defaulting to `WorkerDepends()`.
    """
    redis_client = aioredis.from_url(_REDIS_URL, decode_responses=False)
    heartbeat = asyncio.create_task(_heartbeat_loop(redis_client))
    ctx = WorkerContext(redis=redis_client, heartbeat_task=heartbeat)
    logger.info("streaq worker started — heartbeat loop active")
    try:
        yield ctx
    finally:
        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass
        await redis_client.aclose()
        logger.info("streaq worker shutdown — heartbeat loop stopped")


worker: Worker = Worker(
    redis_url=_REDIS_URL,
    queue_name="spelix",
    lifespan=lifespan,
    concurrency=1,  # MediaPipe peak ~350MB on 2GB droplet (same as ARQ max_jobs=1)
)


def _adapt_ctx(context: WorkerContext) -> dict[str, Any]:
    """Convert the streaq `WorkerContext` to the ARQ-style `ctx: dict` that
    existing task bodies in analysis_worker.py / consent_cascade.py /
    paper_ingestion.py / cleanup.py / keepalive.py still expect.

    Keeping this adapter means we do NOT touch the task bodies in this
    migration — smaller diff, lower regression risk.
    """
    return {
        "redis": context.redis,
        "paper_storage": context.paper_storage,
        "db_session_maker": context.db_session_maker,
    }


@worker.task(timeout=300)
async def process_analysis(
    analysis_id: UUID,
    context: WorkerContext = WorkerDepends(),
) -> None:
    """Main analysis pipeline entry point. See analysis_worker.py for body."""
    from app.workers.analysis_worker import process_analysis as _run

    await _run(_adapt_ctx(context), analysis_id)


@worker.task(timeout=120)
async def cascade_consent_withdrawal(
    user_id: str,
    context: WorkerContext = WorkerDepends(),
) -> dict[str, int]:
    """Consent withdrawal cascade (FR-BRAIN-16). See consent_cascade.py."""
    from app.workers.consent_cascade import (
        cascade_consent_withdrawal as _cascade,
    )

    return await _cascade(_adapt_ctx(context), user_id)


@worker.task(timeout=60)
async def ingest_paper(
    paper_id: str,
    context: WorkerContext = WorkerDepends(),
) -> dict[str, Any]:
    """Expert PDF ingestion stub (ADR-EXPERT-01). See paper_ingestion.py."""
    from app.workers.paper_ingestion import ingest_paper as _ingest

    return await _ingest(_adapt_ctx(context), paper_id)


@worker.cron("0 3 * * *")  # 03:00 UTC nightly
async def cleanup_expired_artifacts_cron(
    context: WorkerContext = WorkerDepends(),
) -> int:
    """Nightly artifact cleanup. See cleanup.py."""
    from app.workers.cleanup import cleanup_expired_artifacts as _cleanup

    return await _cleanup(_adapt_ctx(context))


@worker.cron("0 2 * * *")  # 02:00 UTC nightly (ADR-P2-001)
async def ping_qdrant_health_cron(
    context: WorkerContext = WorkerDepends(),
) -> None:
    """Qdrant keepalive. See keepalive.py."""
    from app.workers.keepalive import ping_qdrant_health as _ping

    await _ping(_adapt_ctx(context))
