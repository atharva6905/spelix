"""Tests for the restamp_paper_payload retry task (issue #258).

FR-RAGK-05 (ext.), FR-AICP-12 (ext.): when the expert-portal metadata PATCH
fails to restamp the paper's papers_rag Qdrant points, a streaq task retries
the idempotent set_payload. The task re-reads sex_applicability from the DB
(current source of truth) so it stays convergent under concurrent edits.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.workers.restamp_paper import restamp_paper_payload


def _make_ctx(session_maker):
    return {"db_session_maker": session_maker}


def _session_maker_for(session):
    """Build a db_session_maker() that yields `session` as an async context mgr."""

    def maker():
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    return maker


def _doc(doc_id, sex_applicability):
    doc = MagicMock()
    doc.id = doc_id
    doc.sex_applicability = sex_applicability
    return doc


@pytest.mark.asyncio
async def test_restamp_rereads_db_and_calls_set_payload(monkeypatch):
    doc_id = uuid4()
    session = AsyncMock()

    # Repo returns the current DB value (NOT a stale passed-in payload).
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_doc(doc_id, "female"))
    monkeypatch.setattr(
        "app.workers.restamp_paper.RagDocumentRepository",
        MagicMock(return_value=repo),
    )

    qdrant = MagicMock()
    qdrant.set_payload = AsyncMock()
    monkeypatch.setattr(
        "app.workers.restamp_paper.get_qdrant_client",
        AsyncMock(return_value=qdrant),
    )

    await restamp_paper_payload(_make_ctx(_session_maker_for(session)), str(doc_id))

    repo.get_by_id.assert_awaited_once_with(doc_id)
    qdrant.set_payload.assert_awaited_once()
    args = qdrant.set_payload.await_args[0]
    assert args[0] == "papers_rag"
    assert args[1] == {"sex_applicability": "female"}
    points_filter = args[2]
    assert points_filter.must[0].key == "paper_id"
    assert points_filter.must[0].match.value == str(doc_id)


@pytest.mark.asyncio
async def test_restamp_noops_when_paper_row_missing(monkeypatch):
    doc_id = uuid4()
    session = AsyncMock()

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.workers.restamp_paper.RagDocumentRepository",
        MagicMock(return_value=repo),
    )

    qdrant = MagicMock()
    qdrant.set_payload = AsyncMock()
    get_client = AsyncMock(return_value=qdrant)
    monkeypatch.setattr(
        "app.workers.restamp_paper.get_qdrant_client", get_client
    )

    result = await restamp_paper_payload(
        _make_ctx(_session_maker_for(session)), str(doc_id)
    )

    qdrant.set_payload.assert_not_awaited()
    assert result["status"] == "not_found"


@pytest.mark.asyncio
async def test_restamp_raises_when_qdrant_unavailable(monkeypatch):
    """get_qdrant_client() None must raise so streaq retries with backoff."""
    doc_id = uuid4()
    session = AsyncMock()

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_doc(doc_id, "male"))
    monkeypatch.setattr(
        "app.workers.restamp_paper.RagDocumentRepository",
        MagicMock(return_value=repo),
    )
    monkeypatch.setattr(
        "app.workers.restamp_paper.get_qdrant_client",
        AsyncMock(return_value=None),
    )

    with pytest.raises(RuntimeError):
        await restamp_paper_payload(
            _make_ctx(_session_maker_for(session)), str(doc_id)
        )
