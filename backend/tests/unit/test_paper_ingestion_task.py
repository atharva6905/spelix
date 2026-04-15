"""Tests for the ingest_paper ARQ task stub (ADR-EXPERT-01, FR-EXPV-02).

Stub scope: confirms the task downloads head bytes via the injected
PaperStorageService and emits the docling_pending log. Full Docling
parsing arrives with P2-005.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.workers.paper_ingestion import ingest_paper


@pytest.mark.asyncio
async def test_ingest_paper_downloads_and_logs_pending(caplog):
    paper_id = str(uuid4())
    storage = AsyncMock()
    storage.download_head_bytes = AsyncMock(return_value=b"%PDF-1.4")

    ctx: dict = {
        "paper_storage": storage,
        "storage_path_override": f"papers/{paper_id}/test.pdf",
    }

    with caplog.at_level(logging.INFO):
        result = await ingest_paper(ctx, paper_id)

    assert result == {"paper_id": paper_id, "status": "docling_pending"}
    storage.download_head_bytes.assert_awaited_once_with(
        f"papers/{paper_id}/test.pdf", n=8
    )
    assert any("docling_pending" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_ingest_paper_not_found_when_row_missing(caplog):
    """If the DB lookup returns None and no override is set, return status=not_found."""
    paper_id = str(uuid4())
    # No storage_path_override, no db_session_maker — forces the None path.
    ctx: dict = {"paper_storage": AsyncMock()}

    with caplog.at_level(logging.WARNING):
        result = await ingest_paper(ctx, paper_id)

    assert result == {"paper_id": paper_id, "status": "not_found"}
    assert any("not_found" in rec.message for rec in caplog.records)


def test_ingest_paper_registered_in_streaq_worker():
    """Confirm the task is in the streaq worker's dispatch registry.

    Presence in worker.registry is the property the old WorkerSettings.functions
    check was really about — it means the worker process can actually invoke this
    task, not just that the wrapper object exists.
    """
    from app.workers.streaq_worker import ingest_paper, worker

    assert "ingest_paper" in worker.registry
    assert worker.registry["ingest_paper"] is ingest_paper
