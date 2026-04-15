"""Integration test: full expert PDF upload flow phase 1 -> phase 3.

Walks POST /expert/papers (signed URL) -> (simulated PUT) ->
POST /expert/papers/{id}/complete through a FastAPI TestClient with an
in-memory RagDocumentRepository override. Storage + ARQ pool are mocked
but the route handlers run against a real ASGI dispatcher.

Reference: ADR-EXPERT-01, FR-EXPV-02.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient


VALID_METADATA = {
    "title": "Integration test paper",
    "document_type": "research_paper",
    "exercise_tags": ["squat"],
    "authors": ["Doe J"],
    "filename": "int_test.pdf",
    "file_size_bytes": 1000,
}


class _InMemoryRagRepo:
    """Dict-backed RagDocumentRepository stand-in for the end-to-end walk."""

    def __init__(self) -> None:
        self._rows: dict[UUID, object] = {}

    async def create(self, doc):
        self._rows[doc.id] = doc
        return doc

    async def get_by_id(self, doc_id):
        return self._rows.get(doc_id)

    async def update_review_status(self, doc_id, *, review_status, reviewer_id=None):
        self._rows[doc_id].review_status = review_status
        if reviewer_id is not None:
            self._rows[doc_id].reviewer_id = reviewer_id
        return self._rows[doc_id]

    async def delete(self, doc_id):
        self._rows.pop(doc_id, None)
        return True


@patch("app.api.v1.expert.get_arq_pool")
@patch("app.api.v1.expert.get_service_role_client")
@patch("app.api.v1.expert.PaperStorageService")
def test_full_upload_flow_phase1_through_phase3(MockStorage, mock_svc, MockPool):
    from app.api.deps import get_expert_reviewer_user
    from app.api.v1.expert import _get_rag_repo, router
    from app.services.paper_storage import SignedPaperUpload

    repo = _InMemoryRagRepo()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/expert")
    app.dependency_overrides[get_expert_reviewer_user] = lambda: {
        "id": uuid4(),
        "email": "e@s.app",
        "role": "expert_reviewer",
    }
    app.dependency_overrides[_get_rag_repo] = lambda: repo

    storage = MockStorage.return_value
    storage.generate_signed_upload_url = AsyncMock(
        return_value=SignedPaperUpload(
            url="https://s/upload-tok",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    storage.download_head_bytes = AsyncMock(return_value=b"%PDF-1.7")
    mock_svc.return_value = MagicMock()

    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    MockPool.return_value = pool  # patched fn is awaited by handler; AsyncMock matches

    client = TestClient(app)

    r1 = client.post("/api/v1/expert/papers", json=VALID_METADATA)
    assert r1.status_code == 201, r1.text
    body1 = r1.json()
    paper_id = body1["id"]
    storage_path = body1["storage_path"]
    assert storage_path.startswith(f"papers/{paper_id}/")
    assert storage_path.endswith("int_test.pdf")
    assert body1["upload_url"] == "https://s/upload-tok"

    stored = repo._rows[UUID(paper_id)]
    assert stored.review_status == "uploading"
    assert stored.storage_path == storage_path

    r3 = client.post(f"/api/v1/expert/papers/{paper_id}/complete")
    assert r3.status_code == 200, r3.text
    body3 = r3.json()
    assert body3["review_status"] == "pending"
    assert body3["storage_path"] == storage_path

    pool.enqueue_job.assert_awaited_once_with("ingest_paper", paper_id)
    assert repo._rows[UUID(paper_id)].review_status == "pending"


@patch("app.api.v1.expert.get_service_role_client")
@patch("app.api.v1.expert.PaperStorageService")
def test_invalid_pdf_bytes_rejected_and_row_deleted(MockStorage, mock_svc):
    from app.api.deps import get_expert_reviewer_user
    from app.api.v1.expert import _get_rag_repo, router
    from app.services.paper_storage import SignedPaperUpload

    repo = _InMemoryRagRepo()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/expert")
    app.dependency_overrides[get_expert_reviewer_user] = lambda: {
        "id": uuid4(),
        "email": "e@s.app",
        "role": "expert_reviewer",
    }
    app.dependency_overrides[_get_rag_repo] = lambda: repo

    storage = MockStorage.return_value
    storage.generate_signed_upload_url = AsyncMock(
        return_value=SignedPaperUpload(
            url="https://s/upload-tok",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    storage.download_head_bytes = AsyncMock(return_value=b"<html>not")
    storage.delete_object = AsyncMock()
    mock_svc.return_value = MagicMock()

    client = TestClient(app)

    r1 = client.post("/api/v1/expert/papers", json=VALID_METADATA)
    assert r1.status_code == 201
    paper_id = r1.json()["id"]
    storage_path = r1.json()["storage_path"]

    r3 = client.post(f"/api/v1/expert/papers/{paper_id}/complete")
    assert r3.status_code == 422
    assert r3.json()["detail"]["error"]["code"] == "INVALID_PDF"

    storage.delete_object.assert_awaited_once_with(storage_path)
    assert UUID(paper_id) not in repo._rows
