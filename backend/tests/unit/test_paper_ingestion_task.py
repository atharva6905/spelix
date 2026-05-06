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


@pytest.mark.asyncio
async def test_ingest_paper_uses_db_session_maker_to_lookup_storage_path():
    """When db_session_maker is set (no override), the task looks up storage_path via DB."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    paper_id = str(uuid4())
    mock_doc = MagicMock()
    mock_doc.storage_path = f"papers/{paper_id}/doc.pdf"

    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_doc)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory = MagicMock(return_value=mock_session)

    mock_storage = AsyncMock()
    mock_storage.download_head_bytes = AsyncMock(return_value=b"%PDF")

    ctx = {
        "paper_storage": mock_storage,
        "db_session_maker": mock_session_factory,
    }

    with patch("app.repositories.rag_document.RagDocumentRepository", return_value=mock_repo):
        with patch(
            "app.workers.paper_ingestion._lookup_storage_path",
            AsyncMock(return_value=f"papers/{paper_id}/doc.pdf"),
        ):
            result = await ingest_paper(ctx, paper_id)

    assert result["status"] == "docling_pending"


@pytest.mark.asyncio
async def test_ingest_paper_returns_not_found_when_db_returns_none():
    """When _lookup_storage_path returns None (doc doesn't exist), returns not_found."""
    from unittest.mock import AsyncMock, patch
    from uuid import uuid4

    paper_id = str(uuid4())

    ctx = {
        "paper_storage": AsyncMock(),
    }

    with patch(
        "app.workers.paper_ingestion._lookup_storage_path",
        AsyncMock(return_value=None),
    ):
        result = await ingest_paper(ctx, paper_id)

    assert result["status"] == "not_found"


@pytest.mark.asyncio
async def test_lookup_storage_path_via_db_session_maker():
    """_lookup_storage_path uses db_session_maker when no override is set."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    from app.workers.paper_ingestion import _lookup_storage_path

    paper_id = uuid4()
    mock_doc = MagicMock()
    mock_doc.storage_path = f"papers/{paper_id}/doc.pdf"

    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_doc)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory = MagicMock(return_value=mock_session)

    ctx = {"db_session_maker": mock_session_factory}

    # RagDocumentRepository is imported inline inside _lookup_storage_path,
    # so patch at the source module that provides it.
    with patch(
        "app.repositories.rag_document.RagDocumentRepository",
        new=MagicMock(return_value=mock_repo),
    ):
        result = await _lookup_storage_path(ctx, paper_id)

    assert result == f"papers/{paper_id}/doc.pdf"


@pytest.mark.asyncio
async def test_lookup_storage_path_returns_none_when_doc_not_in_db():
    """_lookup_storage_path returns None when repo.get_by_id returns None."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    from app.workers.paper_ingestion import _lookup_storage_path

    paper_id = uuid4()
    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory = MagicMock(return_value=mock_session)

    ctx = {"db_session_maker": mock_session_factory}

    # Use builtins import patching for the deferred import
    import builtins

    real_import = builtins.__import__

    def _mock_import(name, *args, **kwargs):
        mod = real_import(name, *args, **kwargs)
        if name == "app.repositories.rag_document":
            mock_module = MagicMock()
            mock_module.RagDocumentRepository = lambda db: mock_repo
            return mock_module
        return mod

    with patch("builtins.__import__", side_effect=_mock_import):
        result = await _lookup_storage_path(ctx, paper_id)

    assert result is None
