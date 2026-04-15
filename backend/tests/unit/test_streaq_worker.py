"""Unit tests for backend/app/workers/streaq_worker.py.

Covers the module's shape — the Worker instance exists, the WorkerContext
dataclass is importable, and all 5 job types are registered (3 tasks + 2
cron jobs). Does NOT exercise Redis — that's integration-test territory
(Task 5 adds a single roundtrip test).
"""

from __future__ import annotations

import pytest


def test_streaq_worker_module_importable() -> None:
    """The module must import without touching Redis."""
    from app.workers import streaq_worker  # noqa: F401


def test_worker_instance_exists() -> None:
    """Module must expose a `worker` attr of type streaq.Worker."""
    from streaq import Worker

    from app.workers.streaq_worker import worker

    assert isinstance(worker, Worker)


def test_worker_context_dataclass_has_correct_fields() -> None:
    """WorkerContext must be a dataclass carrying the 3 drop-in fields.

    `redis` is required so tasks can do mid-pipeline heartbeat writes
    (existing analysis_worker.py pattern). `paper_storage` and
    `db_session_maker` default to None and stay None in this drop-in
    migration — P2-005 will wire real values.
    """
    from dataclasses import fields

    from app.workers.streaq_worker import WorkerContext

    field_names = {f.name for f in fields(WorkerContext)}
    assert field_names == {
        "redis",
        "paper_storage",
        "db_session_maker",
    }


def test_all_three_enqueued_tasks_are_registered() -> None:
    """The 3 enqueued tasks must exist as module attrs callable via .enqueue."""
    from app.workers.streaq_worker import (
        cascade_consent_withdrawal,
        ingest_paper,
        process_analysis,
    )

    for task in (process_analysis, cascade_consent_withdrawal, ingest_paper):
        assert hasattr(task, "enqueue"), f"{task} is not a streaq task"


def test_both_cron_jobs_are_registered() -> None:
    """The 2 cron jobs must exist as module attrs."""
    from app.workers.streaq_worker import (
        cleanup_expired_artifacts_cron,
        ping_qdrant_health_cron,
    )

    # Cron jobs are registered differently in streaq — they may not have
    # .enqueue; we just assert they exist as callables (streaq registers
    # them with the worker via decorator side-effect).
    assert callable(cleanup_expired_artifacts_cron)
    assert callable(ping_qdrant_health_cron)


@pytest.mark.integration
async def test_streaq_worker_opens_redis_connection_cleanly() -> None:
    """End-to-end: streaq Worker can open its redis connection, roundtrip a
    PING, and close cleanly against a live local Redis.

    Does NOT invoke any task or cron — those are exercised at higher levels
    (unit tests in Tasks 3+4 verified module shape; Task 12 verifies real
    prod flow via Playwright MCP).

    Requires Redis running on localhost:6379 (docker-compose.dev.yml).
    """
    from app.workers.streaq_worker import worker

    async with worker:
        pong = await worker.redis.ping()
        # coredis returns the string "PONG", not a bool
        assert pong in (True, b"PONG", "PONG")


@pytest.mark.integration
async def test_task_enqueue_requires_worker_context() -> None:
    """Regression: calling `task.enqueue(...)` outside `async with worker:`
    raises StreaqError. This is the contract the FastAPI web process MUST
    satisfy — it must enter the worker context on startup for enqueue to
    function. The fastapi_lifespan in main.py does exactly that.

    Missing this context was the root cause of the PR #48 prod 500s: the
    web process imported `process_analysis` from streaq_worker and called
    `.enqueue(...)`, but streaq's `worker.lib` was unset because the
    context was never entered, so every POST /analyses/{id}/start returned
    500 with `StreaqError: Worker not initialized`. Unit tests didn't
    catch it because they mock the enqueue call entirely.

    We construct a fresh Worker instance for the regression so module-
    singleton state doesn't leak between tests. Asserting only the
    outside-context failure mode documents the contract; the inside-
    context behavior is exercised by the real worker process on prod.
    """
    import uuid

    from streaq import Worker
    from streaq.types import StreaqError

    from app.workers.streaq_worker import lifespan

    fresh_worker = Worker(
        redis_url="redis://localhost:6379",
        queue_name="spelix-test-regression",
        lifespan=lifespan,
        concurrency=1,
    )

    @fresh_worker.task(timeout=10)
    async def _noop(x: int) -> int:
        return x

    with pytest.raises(StreaqError, match="Worker not initialized"):
        await _noop.enqueue(uuid.uuid4().int % 100)


@pytest.mark.integration
async def test_web_process_flag_suppresses_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `SPELIX_WEB_PROCESS=1`, the lifespan must NOT start the
    heartbeat loop — otherwise the web process masks a dead worker
    container by keeping `spelix:worker:heartbeat` fresh. The worker
    container leaves this unset so it IS the one writing heartbeats.

    Asserts the heartbeat key is NOT set by the lifespan alone when the
    flag is active. (The worker process side is covered implicitly — if
    the flag is False/unset, the existing 20s heartbeat cadence test would
    already fail.)
    """
    import asyncio

    import redis.asyncio as aioredis

    monkeypatch.setenv("SPELIX_WEB_PROCESS", "1")
    # Re-import so the module re-evaluates the _IS_WEB_PROCESS constant.
    import importlib

    from app.workers import streaq_worker as sw

    importlib.reload(sw)

    # Clear any stale heartbeat left by other tests.
    probe = aioredis.from_url(sw._REDIS_URL, decode_responses=False)
    try:
        await probe.delete(sw._HEARTBEAT_KEY)

        async with sw.lifespan() as ctx:
            assert ctx.redis is not None
            # Give the loop a tick in case a heartbeat was erroneously scheduled.
            await asyncio.sleep(0.1)
            # Key must remain absent.
            assert await probe.get(sw._HEARTBEAT_KEY) is None

    finally:
        await probe.aclose()
        # Restore default process-role for subsequent tests.
        monkeypatch.delenv("SPELIX_WEB_PROCESS", raising=False)
        importlib.reload(sw)
