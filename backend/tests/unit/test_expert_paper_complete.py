from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.expert import router as expert_router


TEST_EXPERT_ID = uuid4()


def _make_uploading_doc(doc_id: UUID, storage_path: str):
    from datetime import datetime, timezone
    from app.models.rag_document import RagDocument
    d = RagDocument(
        id=doc_id,
        title="t",
        document_type="research_paper",
        exercise_tags=[],
        authors=[],
        review_status="uploading",
        storage_path=storage_path,
        extra_metadata={},
        ingested_at=datetime.now(timezone.utc),
    )
    return d


@pytest.fixture()
def expert_app():
    from app.api.deps import get_expert_reviewer_user
    from app.db import get_db

    app = FastAPI()
    app.include_router(expert_router, prefix="/api/v1/expert")

    async def _mock_expert():
        return {"id": TEST_EXPERT_ID, "email": "x@s.app", "role": "expert_reviewer"}

    mock_db = AsyncMock()

    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_expert_reviewer_user] = _mock_expert
    app.dependency_overrides[get_db] = _mock_db
    return app, mock_db


@pytest.fixture()
def client(expert_app):
    app, _ = expert_app
    return TestClient(app, raise_server_exceptions=False)


class TestCompletePaperUpload:
    @patch("app.api.v1.expert.get_arq_pool")
    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_happy_path_flips_to_pending_and_enqueues(
        self, MockRepo, MockStorage, mock_svc, MockPool, client
    ):
        doc_id = uuid4()
        path = f"papers/{doc_id}/paper.pdf"
        uploading = _make_uploading_doc(doc_id, path)
        pending = _make_uploading_doc(doc_id, path)
        pending.review_status = "pending"

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=uploading)
        repo_instance.update_review_status = AsyncMock(return_value=pending)

        storage_instance = MockStorage.return_value
        storage_instance.download_head_bytes = AsyncMock(return_value=b"%PDF-1.4")

        mock_svc.return_value = MagicMock()

        pool = AsyncMock()
        pool.enqueue_job = AsyncMock()
        MockPool.return_value = pool

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["review_status"] == "pending"
        assert body["storage_path"] == path
        pool.enqueue_job.assert_awaited_once_with("ingest_paper", str(doc_id))
        repo_instance.update_review_status.assert_awaited_once()
        storage_instance.download_head_bytes.assert_awaited_once_with(path, n=8)

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_missing_magic_bytes_rejects_and_cleans_up(
        self, MockRepo, MockStorage, mock_svc, client
    ):
        doc_id = uuid4()
        path = f"papers/{doc_id}/paper.pdf"
        uploading = _make_uploading_doc(doc_id, path)

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=uploading)
        repo_instance.delete = AsyncMock()

        storage_instance = MockStorage.return_value
        storage_instance.download_head_bytes = AsyncMock(return_value=b"<html>xx")
        storage_instance.delete_object = AsyncMock()

        mock_svc.return_value = MagicMock()

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "INVALID_PDF"
        storage_instance.delete_object.assert_awaited_once_with(path)
        repo_instance.delete.assert_awaited_once_with(doc_id)

    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_rejects_if_not_in_uploading_state(self, MockRepo, client):
        doc_id = uuid4()
        pending = _make_uploading_doc(doc_id, f"papers/{doc_id}/p.pdf")
        pending.review_status = "pending"

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=pending)

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 409

    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_404_for_missing_doc(self, MockRepo, client):
        doc_id = uuid4()
        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=None)

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")
        assert resp.status_code == 404

    @patch("app.api.v1.expert.get_arq_pool")
    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_returns_503_when_arq_pool_is_none_and_does_not_flip_status(
        self, MockRepo, MockStorage, mock_svc, MockPool, client
    ):
        """Security review C-1: if get_arq_pool() returns None (REDIS_URL
        missing or pool creation failed), the DB row must NOT be flipped
        to 'pending'; otherwise we'd have a silent orphan with no
        ingestion job enqueued."""
        doc_id = uuid4()
        path = f"papers/{doc_id}/paper.pdf"
        uploading = _make_uploading_doc(doc_id, path)

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=uploading)
        repo_instance.update_review_status = AsyncMock()

        storage_instance = MockStorage.return_value
        storage_instance.download_head_bytes = AsyncMock(return_value=b"%PDF-1.4")

        mock_svc.return_value = MagicMock()
        MockPool.return_value = None  # missing REDIS_URL path

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 503
        assert resp.json()["detail"]["error"]["code"] == "QUEUE_UNAVAILABLE"
        repo_instance.update_review_status.assert_not_awaited()
