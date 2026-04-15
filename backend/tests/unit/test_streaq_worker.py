"""Unit tests for backend/app/workers/streaq_worker.py.

Covers the module's shape — the Worker instance exists, the WorkerContext
dataclass is importable, and all 5 job types are registered (3 tasks + 2
cron jobs). Does NOT exercise Redis — that's integration-test territory
(Task 5 adds a single roundtrip test).
"""

from __future__ import annotations


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
