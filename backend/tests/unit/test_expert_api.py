"""Tests for expert API sex-applicability surfaces (issue #223).

FR-EXPV-05 (ext.): experts set "Applicable population" (male/female/both)
at paper upload time.
FR-RAGK-05/08 (ext.): post-upload metadata edit restamps the paper's existing
papers_rag Qdrant points via set_payload (no re-embed).
"""

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


def _wire_repo(MockRepo):
    repo_instance = MockRepo.return_value
    repo_instance.get_live_by_doi = AsyncMock(return_value=None)

    async def fake_create(doc):
        return doc

    repo_instance.create = AsyncMock(side_effect=fake_create)
    return repo_instance


# ---------------------------------------------------------------------------
# Task C1 — POST /papers accepts sex_applicability (FR-EXPV-05 ext.)
# ---------------------------------------------------------------------------


class TestUploadSexApplicability:
    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_upload_with_sex_applicability_female_stamps_row(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        _wire_storage(MockStorage, mock_service_role_client)
        repo_instance = _wire_repo(MockRepo)

        body = {**VALID_BODY, "sex_applicability": "female"}
        resp = client.post("/api/v1/expert/papers", json=body)

        assert resp.status_code == 201, resp.text
        doc_arg = repo_instance.create.await_args[0][0]
        assert doc_arg.sex_applicability == "female"

    @patch("app.api.v1.expert.get_service_role_client")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_upload_omitted_sex_applicability_defaults_to_both(
        self, MockRepo, MockStorage, mock_service_role_client, client
    ):
        _wire_storage(MockStorage, mock_service_role_client)
        repo_instance = _wire_repo(MockRepo)

        assert "sex_applicability" not in VALID_BODY
        resp = client.post("/api/v1/expert/papers", json=VALID_BODY)

        assert resp.status_code == 201, resp.text
        doc_arg = repo_instance.create.await_args[0][0]
        assert doc_arg.sex_applicability == "both"

    def test_upload_invalid_sex_applicability_returns_422(self, client):
        body = {**VALID_BODY, "sex_applicability": "all"}
        resp = client.post("/api/v1/expert/papers", json=body)
        assert resp.status_code == 422
