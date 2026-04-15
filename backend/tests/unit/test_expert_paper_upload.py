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
