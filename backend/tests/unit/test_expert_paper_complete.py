from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.expert import router as expert_router


TEST_EXPERT_ID = uuid4()
OTHER_EXPERT_ID = uuid4()
TEST_ADMIN_ID = uuid4()

_SENTINEL = object()


def _make_uploading_doc(doc_id: UUID, storage_path: str, uploaded_by: object = _SENTINEL):
    from datetime import datetime, timezone
    from app.models.rag_document import RagDocument

    if uploaded_by is _SENTINEL:
        extra_metadata: dict | None = {"uploaded_by": str(TEST_EXPERT_ID)}
    elif uploaded_by is None:
        extra_metadata = None
    else:
        extra_metadata = {"uploaded_by": str(uploaded_by)}
    d = RagDocument(
        id=doc_id,
        title="t",
        document_type="research_paper",
        exercise_tags=[],
        authors=[],
        review_status="uploading",
        storage_path=storage_path,
        extra_metadata=extra_metadata,
        ingested_at=datetime.now(timezone.utc),
    )
    return d


def _build_app(user_id: UUID, role: str):
    from app.api.deps import get_expert_reviewer_user
    from app.db import get_db

    app = FastAPI()
    app.include_router(expert_router, prefix="/api/v1/expert")

    async def _mock_user():
        return {"id": user_id, "email": "x@s.app", "role": role}

    mock_db = AsyncMock()

    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_expert_reviewer_user] = _mock_user
    app.dependency_overrides[get_db] = _mock_db
    return app, mock_db


@pytest.fixture()
def expert_app():
    return _build_app(TEST_EXPERT_ID, "expert_reviewer")


@pytest.fixture()
def client(expert_app):
    app, _ = expert_app
    return TestClient(app, raise_server_exceptions=False)


class TestCompletePaperUpload:
    @patch("app.api.v1.expert.get_streaq_worker")
    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_happy_path_flips_to_pending_and_enqueues(
        self, MockRepo, MockStorage, mock_svc, MockWorker, client
    ):
        from app.workers.streaq_worker import ingest_paper as _ingest_task

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
        MockWorker.return_value = MagicMock()

        with patch.object(_ingest_task, "enqueue", new_callable=AsyncMock) as mock_enqueue:
            resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["review_status"] == "pending"
            assert body["storage_path"] == path
            mock_enqueue.assert_awaited_once_with(str(doc_id))
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

    @patch("app.api.v1.expert.get_streaq_worker")
    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_returns_503_when_streaq_worker_is_none_and_does_not_flip_status(
        self, MockRepo, MockStorage, mock_svc, MockWorker, client
    ):
        """Security review C-1: if get_streaq_worker() returns None (REDIS_URL
        missing or import failed), the DB row must NOT be flipped
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
        MockWorker.return_value = None  # missing REDIS_URL / import-failure path

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 503
        assert resp.json()["detail"]["error"]["code"] == "QUEUE_UNAVAILABLE"
        repo_instance.update_review_status.assert_not_awaited()


class TestCompletePaperUploadOwnership:
    """FR-EXPV-02 / issue #231: uploaded_by ownership guard on complete.

    Policy: caller must match extra_metadata.uploaded_by unless admin.
    Missing/None uploaded_by (legacy/corrupt rows) is FAIL-CLOSED for
    non-admins — uploading rows are transient orphans, admins can clean up.
    """

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_non_owner_expert_gets_403_and_no_destructive_action(
        self, MockRepo, MockStorage, mock_svc, client
    ):
        """A different expert must get 403 BEFORE any storage/DB cleanup —
        even when the stored bytes are not a PDF (the destructive path)."""
        doc_id = uuid4()
        path = f"papers/{doc_id}/paper.pdf"
        doc = _make_uploading_doc(doc_id, path, uploaded_by=OTHER_EXPERT_ID)

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=doc)
        repo_instance.delete = AsyncMock()

        storage_instance = MockStorage.return_value
        storage_instance.download_head_bytes = AsyncMock(return_value=b"<html>xx")
        storage_instance.delete_object = AsyncMock()

        mock_svc.return_value = MagicMock()

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 403
        assert resp.json()["detail"]["error"]["code"] == "NOT_PAPER_OWNER"
        storage_instance.delete_object.assert_not_awaited()
        repo_instance.delete.assert_not_awaited()
        storage_instance.download_head_bytes.assert_not_awaited()

    @patch("app.api.v1.expert.get_streaq_worker")
    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_owner_expert_completes_successfully(
        self, MockRepo, MockStorage, mock_svc, MockWorker, client
    ):
        from app.workers.streaq_worker import ingest_paper as _ingest_task

        doc_id = uuid4()
        path = f"papers/{doc_id}/paper.pdf"
        uploading = _make_uploading_doc(doc_id, path, uploaded_by=TEST_EXPERT_ID)
        pending = _make_uploading_doc(doc_id, path, uploaded_by=TEST_EXPERT_ID)
        pending.review_status = "pending"

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=uploading)
        repo_instance.update_review_status = AsyncMock(return_value=pending)

        storage_instance = MockStorage.return_value
        storage_instance.download_head_bytes = AsyncMock(return_value=b"%PDF-1.4")

        mock_svc.return_value = MagicMock()
        MockWorker.return_value = MagicMock()

        with patch.object(_ingest_task, "enqueue", new_callable=AsyncMock):
            resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 200, resp.text
        assert resp.json()["review_status"] == "pending"

    @patch("app.api.v1.expert.get_streaq_worker")
    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_admin_can_complete_another_experts_paper(
        self, MockRepo, MockStorage, mock_svc, MockWorker
    ):
        from app.workers.streaq_worker import ingest_paper as _ingest_task

        app, _ = _build_app(TEST_ADMIN_ID, "admin")
        admin_client = TestClient(app, raise_server_exceptions=False)

        doc_id = uuid4()
        path = f"papers/{doc_id}/paper.pdf"
        uploading = _make_uploading_doc(doc_id, path, uploaded_by=OTHER_EXPERT_ID)
        pending = _make_uploading_doc(doc_id, path, uploaded_by=OTHER_EXPERT_ID)
        pending.review_status = "pending"

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=uploading)
        repo_instance.update_review_status = AsyncMock(return_value=pending)

        storage_instance = MockStorage.return_value
        storage_instance.download_head_bytes = AsyncMock(return_value=b"%PDF-1.4")

        mock_svc.return_value = MagicMock()
        MockWorker.return_value = MagicMock()

        with patch.object(_ingest_task, "enqueue", new_callable=AsyncMock):
            resp = admin_client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 200, resp.text
        assert resp.json()["review_status"] == "pending"

    @pytest.mark.parametrize("uploaded_by", [None, "missing-key"])
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_legacy_row_without_uploaded_by_is_fail_closed_for_experts(
        self, MockRepo, client, uploaded_by
    ):
        doc_id = uuid4()
        path = f"papers/{doc_id}/paper.pdf"
        doc = _make_uploading_doc(doc_id, path, uploaded_by=None)
        if uploaded_by == "missing-key":
            doc.extra_metadata = {}

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=doc)

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 403
        assert resp.json()["detail"]["error"]["code"] == "NOT_PAPER_OWNER"
