from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.expert import router as expert_router


TEST_EXPERT_ID = uuid4()
VALID_BODY = {
    "title": "Squat biomechanics",
    "document_type": "research_paper",
    "exercise_tags": ["squat"],
    "authors": ["Escamilla R"],
    "year": 2001,
    "doi": "10.1249/00005768-200101000-00020",
    "study_design": "observational",
    "population": "10 powerlifters",
    "measurement_method": "emg + force plate",
    "quality_tier": "L3_observational",
    "filename": "escamilla_2001.pdf",
    "file_size_bytes": 2_500_000,
}


@pytest.fixture()
def expert_app():
    from app.api.deps import get_expert_reviewer_user
    from app.db import get_db

    app = FastAPI()
    app.include_router(expert_router, prefix="/api/v1/expert")

    async def _mock_expert():
        return {"id": TEST_EXPERT_ID, "email": "expert@spelix.app", "role": "expert_reviewer"}

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


class TestRequestPaperUpload:
    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_returns_signed_url_and_creates_uploading_row(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        from app.services.paper_storage import SignedPaperUpload

        repo_instance = MockRepo.return_value

        # Return the doc unchanged — the handler pre-assigns id=paper_id so
        # storage_path and doc.id are always the same UUID.
        async def fake_create(doc):
            return doc

        repo_instance.create = AsyncMock(side_effect=fake_create)
        repo_instance.get_live_by_doi = AsyncMock(return_value=None)

        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        storage_instance = MockStorage.return_value
        storage_instance.generate_signed_upload_url = AsyncMock(
            return_value=SignedPaperUpload(url="https://x.supabase.co/upload/tok", expires_at=expires)
        )
        mock_service_role_client.return_value = MagicMock()

        resp = client.post("/api/v1/expert/papers", json=VALID_BODY)

        assert resp.status_code == 201, resp.text
        body = resp.json()
        doc_id = body["id"]
        assert body["upload_url"] == "https://x.supabase.co/upload/tok"
        # storage_path is built with the same UUID as the returned id
        assert body["storage_path"] == f"papers/{doc_id}/escamilla_2001.pdf"
        assert repo_instance.create.await_count == 1
        doc_arg = repo_instance.create.await_args[0][0]
        assert doc_arg.review_status == "uploading"
        storage_instance.generate_signed_upload_url.assert_awaited_once_with(body["storage_path"])

    def test_rejects_oversize(self, client):
        body = {**VALID_BODY, "file_size_bytes": 60_000_000}
        resp = client.post("/api/v1/expert/papers", json=body)
        assert resp.status_code == 422

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_rejects_non_pdf_extension(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        body = {**VALID_BODY, "filename": "paper.docx"}
        resp = client.post("/api/v1/expert/papers", json=body)
        assert resp.status_code == 422
        assert "pdf" in resp.text.lower()

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_rejects_path_traversal(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        body = {**VALID_BODY, "filename": "../../../etc/passwd.pdf"}
        resp = client.post("/api/v1/expert/papers", json=body)
        assert resp.status_code == 422

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_sanitizes_filename_in_storage_path(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        from app.services.paper_storage import SignedPaperUpload
        repo_instance = MockRepo.return_value
        async def fake_create(doc):
            doc.id = uuid4()
            return doc
        repo_instance.create = AsyncMock(side_effect=fake_create)
        repo_instance.get_live_by_doi = AsyncMock(return_value=None)
        storage_instance = MockStorage.return_value
        storage_instance.generate_signed_upload_url = AsyncMock(
            return_value=SignedPaperUpload(url="https://x/u", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        )
        mock_service_role_client.return_value = MagicMock()

        body = {**VALID_BODY, "filename": "Squat biomechanics study@#.pdf"}
        resp = client.post("/api/v1/expert/papers", json=body)
        assert resp.status_code == 201, resp.text
        storage_path = resp.json()["storage_path"]
        assert storage_path.endswith("Squat_biomechanics_study.pdf")


class TestUploadDoiEnforcement:
    """FR-EXPV-02 / FR-RAGK-05: DOI is the enforced unique business key."""

    @staticmethod
    def _wire_storage(MockStorage, mock_service_role_client):
        from app.services.paper_storage import SignedPaperUpload

        storage_instance = MockStorage.return_value
        storage_instance.generate_signed_upload_url = AsyncMock(
            return_value=SignedPaperUpload(
                url="https://x.supabase.co/upload/tok",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        mock_service_role_client.return_value = MagicMock()
        return storage_instance

    def test_upload_missing_doi_returns_422(self, client):
        body = {k: v for k, v in VALID_BODY.items() if k != "doi"}
        resp = client.post("/api/v1/expert/papers", json=body)
        assert resp.status_code == 422

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_upload_malformed_doi_returns_422_invalid_doi(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        self._wire_storage(MockStorage, mock_service_role_client)
        repo_instance = MockRepo.return_value
        repo_instance.get_live_by_doi = AsyncMock(return_value=None)
        repo_instance.create = AsyncMock()

        resp = client.post(
            "/api/v1/expert/papers", json={**VALID_BODY, "doi": "not-a-doi"}
        )

        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["error"]["code"] == "INVALID_DOI"
        repo_instance.create.assert_not_awaited()

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_upload_duplicate_doi_returns_409(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        from app.models.rag_document import RagDocument

        self._wire_storage(MockStorage, mock_service_role_client)
        existing = RagDocument(id=uuid4(), title="Existing Paper")
        repo_instance = MockRepo.return_value
        repo_instance.get_live_by_doi = AsyncMock(return_value=existing)
        repo_instance.create = AsyncMock()

        resp = client.post("/api/v1/expert/papers", json=VALID_BODY)

        assert resp.status_code == 409, resp.text
        err = resp.json()["detail"]["error"]
        assert err["code"] == "DUPLICATE_DOI"
        assert "Existing Paper" in err["message"]
        assert err["detail"]["existing_paper_id"] == str(existing.id)
        assert err["detail"]["existing_title"] == "Existing Paper"
        repo_instance.create.assert_not_awaited()

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_upload_doi_stored_normalized(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        self._wire_storage(MockStorage, mock_service_role_client)
        repo_instance = MockRepo.return_value
        repo_instance.get_live_by_doi = AsyncMock(return_value=None)

        async def fake_create(doc):
            return doc

        repo_instance.create = AsyncMock(side_effect=fake_create)

        body = {**VALID_BODY, "doi": "https://doi.org/10.1519/JSC.0B013E31818546BB"}
        resp = client.post("/api/v1/expert/papers", json=body)

        assert resp.status_code == 201, resp.text
        create_args = repo_instance.create.await_args
        assert create_args is not None
        doc_arg = create_args[0][0]
        assert doc_arg.doi == "10.1519/jsc.0b013e31818546bb"
        repo_instance.get_live_by_doi.assert_awaited_once_with(
            "10.1519/jsc.0b013e31818546bb"
        )

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_upload_rejected_doi_does_not_block(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        """A reviewed_rejected row is not 'live' — get_live_by_doi returns None
        and re-upload of the same DOI proceeds (FR-EXPV-02 re-upload path)."""
        self._wire_storage(MockStorage, mock_service_role_client)
        repo_instance = MockRepo.return_value
        repo_instance.get_live_by_doi = AsyncMock(return_value=None)

        async def fake_create(doc):
            return doc

        repo_instance.create = AsyncMock(side_effect=fake_create)

        resp = client.post("/api/v1/expert/papers", json=VALID_BODY)

        assert resp.status_code == 201, resp.text
        assert repo_instance.create.await_count == 1


class TestUploadDoiOptionalByDocumentType:
    """Issue #234 (FR-EXPV-02): DOI required iff document_type ==
    'research_paper'; optional (omit/null) for DOI-less types."""

    @staticmethod
    def _wire(MockRepo, MockStorage, mock_service_role_client):
        from app.services.paper_storage import SignedPaperUpload

        repo_instance = MockRepo.return_value
        repo_instance.get_live_by_doi = AsyncMock(return_value=None)

        async def fake_create(doc):
            return doc

        repo_instance.create = AsyncMock(side_effect=fake_create)
        storage_instance = MockStorage.return_value
        storage_instance.generate_signed_upload_url = AsyncMock(
            return_value=SignedPaperUpload(
                url="https://x.supabase.co/upload/tok",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        mock_service_role_client.return_value = MagicMock()
        return repo_instance

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_textbook_without_doi_returns_201_and_skips_dedup(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        repo_instance = self._wire(MockRepo, MockStorage, mock_service_role_client)

        body = {k: v for k, v in VALID_BODY.items() if k != "doi"}
        body["document_type"] = "textbook"
        resp = client.post("/api/v1/expert/papers", json=body)

        assert resp.status_code == 201, resp.text
        repo_instance.get_live_by_doi.assert_not_awaited()
        doc_arg = repo_instance.create.await_args[0][0]
        assert doc_arg.doi is None
        assert doc_arg.document_type == "textbook"

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_textbook_with_doi_still_normalized_and_deduped(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        """An optional DOI provided for a DOI-less type still goes through
        normalize_doi + the get_live_by_doi pre-check."""
        repo_instance = self._wire(MockRepo, MockStorage, mock_service_role_client)

        body = {
            **VALID_BODY,
            "document_type": "textbook",
            "doi": "https://doi.org/10.1519/JSC.0B013E31818546BB",
        }
        resp = client.post("/api/v1/expert/papers", json=body)

        assert resp.status_code == 201, resp.text
        repo_instance.get_live_by_doi.assert_awaited_once_with(
            "10.1519/jsc.0b013e31818546bb"
        )
        doc_arg = repo_instance.create.await_args[0][0]
        assert doc_arg.doi == "10.1519/jsc.0b013e31818546bb"

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_textbook_with_malformed_doi_still_422(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        repo_instance = self._wire(MockRepo, MockStorage, mock_service_role_client)

        body = {**VALID_BODY, "document_type": "textbook", "doi": "not-a-doi"}
        resp = client.post("/api/v1/expert/papers", json=body)

        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["error"]["code"] == "INVALID_DOI"
        repo_instance.create.assert_not_awaited()

    def test_research_paper_null_doi_returns_422_with_message(self, client):
        body = {**VALID_BODY, "doi": None}
        resp = client.post("/api/v1/expert/papers", json=body)

        assert resp.status_code == 422, resp.text
        assert "DOI is required for research papers" in resp.text


class TestCompletePaperUploadDoiRace:
    """Concurrent-race close-out (issue #218): the partial unique index
    uq_rag_documents_doi_live fires on the uploading->pending UPDATE."""

    @staticmethod
    def _make_uploading_doc(doc_id, storage_path):
        from app.models.rag_document import RagDocument

        return RagDocument(
            id=doc_id,
            title="t",
            document_type="research_paper",
            exercise_tags=[],
            authors=[],
            doi="10.1234/race",
            review_status="uploading",
            storage_path=storage_path,
            # FR-EXPV-02 / issue #231: caller must own the row to reach the
            # DOI-race close-out path at all.
            extra_metadata={"uploaded_by": str(TEST_EXPERT_ID)},
            ingested_at=datetime.now(timezone.utc),
        )

    @patch("app.api.v1.expert.get_streaq_worker")
    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_complete_integrity_error_returns_409_and_cleans_up(
        self, MockRepo, MockStorage, mock_svc, MockWorker, expert_app, client
    ):
        from sqlalchemy.exc import IntegrityError

        _, mock_db = expert_app
        doc_id = uuid4()
        path = f"papers/{doc_id}/paper.pdf"

        order: list[str] = []
        mock_db.rollback = AsyncMock(side_effect=lambda: order.append("rollback"))
        mock_db.commit = AsyncMock(side_effect=lambda: order.append("commit"))

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(
            return_value=self._make_uploading_doc(doc_id, path)
        )
        repo_instance.update_review_status = AsyncMock(
            side_effect=IntegrityError(
                "UPDATE rag_documents",
                {},
                Exception(
                    "duplicate key value violates unique constraint"
                    " uq_rag_documents_doi_live"
                ),
            )
        )
        repo_instance.delete = AsyncMock(
            side_effect=lambda _id: order.append("repo_delete")
        )

        storage_instance = MockStorage.return_value
        storage_instance.download_head_bytes = AsyncMock(return_value=b"%PDF-1.4")
        storage_instance.delete_object = AsyncMock(
            side_effect=lambda _p: order.append("storage_delete")
        )

        mock_svc.return_value = MagicMock()
        MockWorker.return_value = MagicMock()

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["error"]["code"] == "DUPLICATE_DOI"
        storage_instance.delete_object.assert_awaited_once_with(path)
        repo_instance.delete.assert_awaited_once_with(doc_id)
        # rollback discards the poisoned txn BEFORE cleanup; commit persists
        # the cleanup BEFORE raising (get_db rolls back on HTTPException).
        assert order == ["rollback", "storage_delete", "repo_delete", "commit"]

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_invalid_pdf_cleanup_commits_before_raise(
        self, MockRepo, MockStorage, mock_svc, expert_app, client
    ):
        """Regression (issue #218 drive-by): get_db ROLLS BACK on HTTPException,
        so the INVALID_PDF row cleanup must be explicitly committed or the
        orphan 'uploading' row survives."""
        _, mock_db = expert_app
        doc_id = uuid4()
        path = f"papers/{doc_id}/paper.pdf"

        order: list[str] = []
        mock_db.commit = AsyncMock(side_effect=lambda: order.append("commit"))

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(
            return_value=self._make_uploading_doc(doc_id, path)
        )
        repo_instance.delete = AsyncMock(
            side_effect=lambda _id: order.append("repo_delete")
        )

        storage_instance = MockStorage.return_value
        storage_instance.download_head_bytes = AsyncMock(return_value=b"<html>xx")
        storage_instance.delete_object = AsyncMock()

        mock_svc.return_value = MagicMock()

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["error"]["code"] == "INVALID_PDF"
        assert order == ["repo_delete", "commit"]
