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
  - Cron wrappers: `cleanup_expired_artifacts_cron`, `ping_qdrant_health_cron`,
    `cleanup_orphan_papers_cron`.

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
from dataclasses import dataclass
from typing import Any, AsyncIterator
from uuid import UUID

import redis.asyncio as aioredis
from streaq import Worker, WorkerDepends

logger = logging.getLogger(__name__)

_HEARTBEAT_KEY = "spelix:worker:heartbeat"
_HEARTBEAT_TTL = 90  # seconds
_HEARTBEAT_INTERVAL = 30  # seconds

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

# When the FastAPI web process enters `async with worker:` to enable
# enqueueing, streaq still runs this lifespan. The heartbeat must NOT
# duplicate from both processes — an always-fresh heartbeat from the web
# process would mask a dead worker container. Set SPELIX_WEB_PROCESS=1 on
# the web container only; the worker container leaves it unset.
_IS_WEB_PROCESS = os.environ.get("SPELIX_WEB_PROCESS") == "1"


@dataclass
class WorkerContext:
    """Deps injected into every task via `WorkerDepends()`.

    `redis` is the live async redis client created in `lifespan()` — task
    bodies read it via the adapter for mid-pipeline heartbeat writes.
    `paper_storage` and `db_session_maker` are wired in `lifespan()` for
    the worker process; None on the web process (enqueue-only).
    """

    redis: Any
    paper_storage: Any = None
    db_session_maker: Any = None


async def _heartbeat_loop(redis: Any) -> None:
    """Write `spelix:worker:heartbeat` with 90s TTL every 30s (NFR-OPER-02)."""
    while True:
        try:
            await redis.set(_HEARTBEAT_KEY, "alive", ex=_HEARTBEAT_TTL)
        except Exception:
            logger.warning("Failed to write worker heartbeat")
        await asyncio.sleep(_HEARTBEAT_INTERVAL)


async def _build_supabase_client() -> Any | None:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        logger.warning("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set — paper_storage inert")
        return None
    from supabase import acreate_client  # type: ignore[import]

    return await acreate_client(supabase_url, supabase_key)


@asynccontextmanager
async def lifespan() -> AsyncIterator[WorkerContext]:
    """Startup/teardown: open redis, launch heartbeat loop (worker process
    only), expose deps.

    streaq 6.4.0 expects a zero-arg async context manager that yields the
    deps dataclass. The Worker uses the yielded value as the injection
    target for every parameter defaulting to `WorkerDepends()`.

    When the FastAPI web process enters `async with worker:` to enable
    enqueue-side functionality, this lifespan ALSO runs there. The web
    process must NOT start a competing heartbeat — a worker-dead but
    web-alive scenario would otherwise show a fresh heartbeat and mask the
    failure. Gated by the `SPELIX_WEB_PROCESS` env var (set on the web
    container only).
    """
    redis_client = aioredis.from_url(_REDIS_URL, decode_responses=False)
    heartbeat: asyncio.Task | None = None

    paper_storage = None
    db_session_maker = None
    if not _IS_WEB_PROCESS:
        heartbeat = asyncio.create_task(_heartbeat_loop(redis_client))
        logger.info("streaq worker started — heartbeat loop active")

        from app.db import async_session
        from app.services.paper_storage import PaperStorageService

        db_session_maker = async_session
        supabase_client = await _build_supabase_client()
        if supabase_client is not None:
            paper_storage = PaperStorageService(client=supabase_client)
    else:
        logger.info("streaq worker context entered on web process — heartbeat suppressed")

    ctx = WorkerContext(
        redis=redis_client,
        paper_storage=paper_storage,
        db_session_maker=db_session_maker,
    )
    try:
        yield ctx
    finally:
        if heartbeat is not None:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass
        await redis_client.aclose()
        logger.info("streaq worker shutdown — context closed")


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


# timeout=1800 restored 2026-04-24 after deadlift fixture E2E on prod (analysis
# 435065d5-e6f1, 26.2 s @60fps, 1547 frames, streaq task e6d23bc3) hit the 900 s
# ceiling during post-gate LLM coaching + CoVe verification and got killed —
# `task process_analysis … timed out` in worker logs at exactly 900 s. The ADR-060
# telemetry budget accounted for pose+barbell+annotation (670 s on a 22.8 s clip)
# but NOT the CoVe iteration cost on longer coaching outputs — each rep adds
# claim-extraction + verification LLM calls, and 26 s videos produce more reps +
# more claims than the 22.8 s reference. Raising the ceiling back to the ADR-058
# safety net (1800 s) is the conservative fix; splitting scoring and coaching into
# separate streaq tasks is the architecturally correct long-term move (tracked
# post-beta). Other tasks stay at 300 s — sub-second in the common case.
@worker.task(timeout=1800)
async def process_analysis(
    analysis_id: UUID,
    context: WorkerContext = WorkerDepends(),
) -> None:
    """Main analysis pipeline entry point. See analysis_worker.py for body."""
    # Lazy-imported to avoid api.v1 → worker → api.v1 cycle.
    from app.workers.analysis_worker import process_analysis as _run

    await _run(_adapt_ctx(context), analysis_id)


# D-035 Priority 3: diagnostic harness to triangulate bench-vs-prod gap.
# timeout=900 covers two extract_landmarks passes on a 22.8s 1080p@59fps
# clip at observed prod speed. Results land in the worker log under the
# D035_DIAG prefix for easy `docker logs | grep` retrieval.
@worker.task(timeout=900)
async def pose_extraction_diagnostic(
    video_path: str,
    context: WorkerContext = WorkerDepends(),
) -> dict[str, dict[str, float]]:
    """Run pose extraction in executor + inline variants; log timings."""
    # Lazy-imported to match other task wrappers and avoid cycles.
    from app.services.d035_diagnostic import _run_pose_extraction_diagnostic

    logger.info("D035_DIAG_START video_path=%s", video_path)
    result = await _run_pose_extraction_diagnostic(video_path)
    logger.info(
        "D035_DIAG_RESULT video_path=%s executor=%s inline=%s",
        video_path,
        result["executor"],
        result["inline"],
    )
    return result


@worker.task(timeout=300)
async def cascade_consent_withdrawal(
    user_id: str,
    context: WorkerContext = WorkerDepends(),
) -> dict[str, int]:
    """Consent withdrawal cascade (FR-BRAIN-16). See consent_cascade.py."""
    # Lazy-imported to avoid api.v1 → worker → api.v1 cycle.
    from app.workers.consent_cascade import (
        cascade_consent_withdrawal as _cascade,
    )

    return await _cascade(_adapt_ctx(context), user_id)


@worker.task(timeout=300)
async def ingest_paper(
    paper_id: str,
    context: WorkerContext = WorkerDepends(),
) -> dict[str, Any]:
    """Expert PDF ingestion stub (ADR-EXPERT-01). See paper_ingestion.py."""
    # Lazy-imported to avoid api.v1 → worker → api.v1 cycle.
    from app.workers.paper_ingestion import ingest_paper as _ingest

    return await _ingest(_adapt_ctx(context), paper_id)


@worker.task(timeout=300)
async def distill_analysis(
    analysis_id: UUID,
    context: WorkerContext = WorkerDepends(),
) -> dict[str, Any]:
    """Phase 3 Batch 2 distillation pipeline (FR-BRAIN-06). See distillation_worker.py."""
    # Lazy-imported to avoid api.v1 → worker → api.v1 cycle.
    from app.workers.deps import build_distillation_ctx
    from app.workers.distillation_worker import distill_analysis_body as _distill

    ctx = _adapt_ctx(context)
    extra = await build_distillation_ctx()
    ctx.update(extra)
    return await _distill(ctx, analysis_id)


@worker.cron("0 3 * * *")  # 03:00 UTC nightly
async def cleanup_expired_artifacts_cron(
    context: WorkerContext = WorkerDepends(),
) -> int:
    """Nightly artifact cleanup. See cleanup.py."""
    # Lazy-imported to avoid api.v1 → worker → api.v1 cycle.
    from app.workers.cleanup import cleanup_expired_artifacts as _cleanup

    return await _cleanup(_adapt_ctx(context))


@worker.cron("0 2 * * *")  # 02:00 UTC nightly (ADR-P2-001)
async def ping_qdrant_health_cron(
    context: WorkerContext = WorkerDepends(),
) -> None:
    """Qdrant keepalive. See keepalive.py."""
    # Lazy-imported to avoid api.v1 → worker → api.v1 cycle.
    from app.workers.keepalive import ping_qdrant_health as _ping

    await _ping(_adapt_ctx(context))


@worker.cron("0 4 * * *")  # 04:00 UTC nightly (D-030)
async def cleanup_orphan_papers_cron(
    context: WorkerContext = WorkerDepends(),
) -> int:
    """Nightly orphan rag_documents cleanup. See cleanup_orphan_papers.py."""
    from app.workers.cleanup_orphan_papers import cleanup_orphan_papers as _cleanup

    return await _cleanup(_adapt_ctx(context))
