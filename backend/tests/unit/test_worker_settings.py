"""Unit tests for worker settings — heartbeat loop, on_startup, on_shutdown.

Covers settings.py lines 30-55.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.workers.settings import (
    WorkerSettings,
    _heartbeat_loop,
    on_shutdown,
    on_startup,
)


class TestHeartbeatLoop:
    @pytest.mark.asyncio
    async def test_writes_heartbeat_key(self) -> None:
        """Heartbeat loop writes 'alive' with 90s TTL."""
        redis = AsyncMock()
        call_count = 0

        async def counting_set(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError

        redis.set = AsyncMock(side_effect=counting_set)

        with pytest.raises(asyncio.CancelledError):
            await _heartbeat_loop(redis)

        # First call should have been made
        first_call = redis.set.call_args_list[0]
        assert first_call.args[0] == "spelix:worker:heartbeat"
        assert first_call.args[1] == "alive"
        assert first_call.kwargs["ex"] == 90

    @pytest.mark.asyncio
    async def test_heartbeat_loop_survives_redis_error(self) -> None:
        """If redis.set raises, the loop continues."""
        redis = AsyncMock()
        call_count = 0

        async def failing_then_cancel(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Redis down")
            raise asyncio.CancelledError

        redis.set = AsyncMock(side_effect=failing_then_cancel)

        with pytest.raises(asyncio.CancelledError):
            await _heartbeat_loop(redis)

        assert call_count == 2  # survived first error, tried again


class TestOnStartup:
    @pytest.mark.asyncio
    async def test_creates_heartbeat_task(self) -> None:
        redis = AsyncMock()
        ctx: dict = {"redis": redis}

        await on_startup(ctx)

        assert "_heartbeat_task" in ctx
        task = ctx["_heartbeat_task"]
        assert isinstance(task, asyncio.Task)

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestOnShutdown:
    @pytest.mark.asyncio
    async def test_cancels_heartbeat_task(self) -> None:
        redis = AsyncMock()
        ctx: dict = {"redis": redis}

        await on_startup(ctx)
        task = ctx["_heartbeat_task"]
        assert not task.cancelled()

        await on_shutdown(ctx)
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_handles_missing_task(self) -> None:
        """on_shutdown is safe when called without on_startup."""
        ctx: dict = {}
        await on_shutdown(ctx)  # Should not raise


class TestWorkerSettingsConfig:
    def test_queue_name(self) -> None:
        assert WorkerSettings.queue_name == "arq:queue"

    def test_max_jobs(self) -> None:
        assert WorkerSettings.max_jobs == 1

    def test_job_timeout(self) -> None:
        assert WorkerSettings.job_timeout == 300

    def test_keep_result(self) -> None:
        assert WorkerSettings.keep_result == 0

    def test_has_cron_jobs(self) -> None:
        assert len(WorkerSettings.cron_jobs) >= 1

    def test_functions_include_process_analysis(self) -> None:
        from app.workers.analysis_worker import process_analysis
        assert process_analysis in WorkerSettings.functions
