"""Tests for the ingest_paper worker task (real pipeline).

Covers: not_found, pending_review guard, extraction_failed,
happy path (mocked Docling + IngestionService), and worker registration.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.workers.paper_ingestion import ingest_paper


def _make_doc(
    paper_id=None,
    review_status="reviewed_approved",
    storage_path=None,
    title="Test Paper",
    authors=None,
    year=2024,
    doi="10.1234/test",
    quality_tier="L2_rct",
    exercise_tags=None,
    sex_applicability="both",
):
    pid = paper_id or str(uuid4())
    return SimpleNamespace(
        id=pid,
        title=title,
        authors=authors or ["Smith J"],
        year=year,
        doi=doi,
        quality_tier=quality_tier,
        review_status=review_status,
        storage_path=storage_path or f"papers/{pid}/doc.pdf",
        chunk_count=0,
        exercise_tags=exercise_tags if exercise_tags is not None else ["squat"],
        sex_applicability=sex_applicability,
    )


@pytest.mark.asyncio
async def test_ingest_paper_not_found(caplog):
    paper_id = str(uuid4())
    ctx: dict = {"paper_storage": AsyncMock()}

    with caplog.at_level(logging.WARNING):
        result = await ingest_paper(ctx, paper_id)

    assert result == {"paper_id": paper_id, "status": "not_found"}


@pytest.mark.asyncio
async def test_ingest_paper_pending_review(caplog):
    paper_id = str(uuid4())
    doc = _make_doc(paper_id=paper_id, review_status="pending")

    ctx: dict = {"paper_storage": AsyncMock(), "doc_override": doc}

    with caplog.at_level(logging.INFO):
        result = await ingest_paper(ctx, paper_id)

    assert result == {"paper_id": paper_id, "status": "pending_review"}


@pytest.mark.asyncio
async def test_ingest_paper_extraction_failed():
    paper_id = str(uuid4())
    doc = _make_doc(paper_id=paper_id)

    storage = AsyncMock()
    storage.download_bytes = AsyncMock(return_value=b"%PDF-1.4 fake")

    ctx: dict = {"paper_storage": storage, "doc_override": doc}

    with patch(
        "app.services.pdf_extraction.extract_text_from_pdf",
        AsyncMock(return_value=("", None)),
    ):
        result = await ingest_paper(ctx, paper_id)

    assert result == {"paper_id": paper_id, "status": "extraction_failed"}


@pytest.mark.asyncio
async def test_ingest_paper_happy_path():
    paper_id = str(uuid4())
    doc = _make_doc(paper_id=paper_id, exercise_tags=["squat"], sex_applicability="both")

    storage = AsyncMock()
    storage.download_bytes = AsyncMock(return_value=b"%PDF-1.4 content")

    mock_ingestion_result = SimpleNamespace(
        paper_id=paper_id, chunk_count=7, point_ids=["a", "b"]
    )
    mock_svc = AsyncMock()
    mock_svc.ingest_document = AsyncMock(return_value=mock_ingestion_result)

    mock_repo = AsyncMock()
    mock_repo.update_chunk_count = AsyncMock()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.commit = AsyncMock()
    mock_session_factory = MagicMock(return_value=mock_session)

    ctx: dict = {
        "paper_storage": storage,
        "doc_override": doc,
        "db_session_maker": mock_session_factory,
    }

    with (
        patch(
            "app.services.pdf_extraction.extract_text_from_pdf",
            AsyncMock(return_value=("Full paper text here.", {"abstract": "Summary."})),
        ),
        patch("app.services.cohere_client.get_cohere_client", return_value=MagicMock()),
        patch(
            "app.services.qdrant.get_qdrant_client",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "app.services.ingestion.IngestionService",
            return_value=mock_svc,
        ),
        patch(
            "app.repositories.rag_document.RagDocumentRepository",
            return_value=mock_repo,
        ),
    ):
        result = await ingest_paper(ctx, paper_id)

    assert result["status"] == "ingested"
    assert result["chunk_count"] == 7
    storage.download_bytes.assert_awaited_once_with(doc.storage_path)
    mock_svc.ingest_document.assert_awaited_once()

    # Issue #222: exercise_tags + sex_applicability propagate from the doc row
    # into the DocumentMetadata the task builds.
    passed_metadata = mock_svc.ingest_document.await_args.kwargs["metadata"]
    assert passed_metadata.exercise_tags == ["squat"]
    assert passed_metadata.sex_applicability == "both"


def test_ingest_paper_registered_in_streaq_worker():
    from app.workers.streaq_worker import ingest_paper as task_fn
    from app.workers.streaq_worker import worker

    assert "ingest_paper" in worker.registry
    assert worker.registry["ingest_paper"] is task_fn
