"""Streaq-level E2E: process_analysis tail enqueues distill_analysis."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_enqueue_skipped_when_flag_off(monkeypatch) -> None:
    monkeypatch.delenv("SPELIX_DISTILLATION_ENABLED", raising=False)
    from app.workers.analysis_worker import _maybe_enqueue_distillation

    enqueue = AsyncMock()
    with patch(
        "app.workers.streaq_worker.distill_analysis.enqueue", enqueue
    ):
        await _maybe_enqueue_distillation(
            analysis_id=uuid.uuid4(),
            eval_scores={"overall": 0.9},
        )
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_skipped_when_eval_below_floor(monkeypatch) -> None:
    monkeypatch.setenv("SPELIX_DISTILLATION_ENABLED", "1")
    from app.workers.analysis_worker import _maybe_enqueue_distillation

    enqueue = AsyncMock()
    with patch(
        "app.workers.streaq_worker.distill_analysis.enqueue", enqueue
    ):
        await _maybe_enqueue_distillation(
            analysis_id=uuid.uuid4(),
            eval_scores={"overall": 0.4},
        )
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_called_when_flag_on_and_eval_above_floor(monkeypatch) -> None:
    monkeypatch.setenv("SPELIX_DISTILLATION_ENABLED", "1")
    from app.workers.analysis_worker import _maybe_enqueue_distillation

    enqueue = AsyncMock()
    with patch(
        "app.workers.streaq_worker.distill_analysis.enqueue", enqueue
    ):
        aid = uuid.uuid4()
        await _maybe_enqueue_distillation(
            analysis_id=aid,
            eval_scores={"overall": 0.7},
        )
    enqueue.assert_awaited_once_with(aid)


@pytest.mark.asyncio
async def test_enqueue_errors_are_swallowed(monkeypatch, caplog) -> None:
    monkeypatch.setenv("SPELIX_DISTILLATION_ENABLED", "1")
    from app.workers.analysis_worker import _maybe_enqueue_distillation

    enqueue = AsyncMock(side_effect=RuntimeError("redis down"))
    with patch(
        "app.workers.streaq_worker.distill_analysis.enqueue", enqueue
    ):
        await _maybe_enqueue_distillation(
            analysis_id=uuid.uuid4(),
            eval_scores={"overall": 0.9},
        )
    assert "redis down" in caplog.text or "distillation enqueue failed" in caplog.text
