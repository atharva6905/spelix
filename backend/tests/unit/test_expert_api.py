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


# ---------------------------------------------------------------------------
# Task C2 — PATCH /papers/{doc_id}/metadata (FR-RAGK-05/08 ext.)
# ---------------------------------------------------------------------------


def _make_doc(doc_id, sex_applicability="both"):
    from app.models.rag_document import RagDocument

    return RagDocument(
        id=doc_id,
        title="Squat biomechanics",
        document_type="research_paper",
        exercise_tags=["squat"],
        authors=[],
        doi="10.1234/meta",
        review_status="reviewed_approved",
        sex_applicability=sex_applicability,
        extra_metadata={},
        ingested_at=datetime.now(timezone.utc),
    )


class TestPatchPaperMetadata:
    @patch("app.api.v1.expert.get_qdrant_client", new_callable=AsyncMock)
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_patch_updates_row_and_restamps_qdrant(
        self, MockRepo, mock_get_qdrant, client
    ):
        doc_id = uuid4()
        repo_instance = MockRepo.return_value
        repo_instance.update_sex_applicability = AsyncMock(
            return_value=_make_doc(doc_id, sex_applicability="female")
        )

        qdrant = MagicMock()
        qdrant.set_payload = AsyncMock()
        mock_get_qdrant.return_value = qdrant

        resp = client.patch(
            f"/api/v1/expert/papers/{doc_id}/metadata",
            json={"sex_applicability": "female"},
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["sex_applicability"] == "female"
        repo_instance.update_sex_applicability.assert_awaited_once_with(
            doc_id, sex_applicability="female"
        )

        qdrant.set_payload.assert_awaited_once()
        call_args = qdrant.set_payload.await_args[0]
        assert call_args[0] == "papers_rag"
        assert call_args[1] == {"sex_applicability": "female"}
        points_filter = call_args[2]
        assert points_filter.must[0].key == "paper_id"
        assert points_filter.must[0].match.value == str(doc_id)

    @patch("app.api.v1.expert.get_qdrant_client", new_callable=AsyncMock)
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_patch_commits_row_before_restamp(
        self, MockRepo, mock_get_qdrant, expert_app, client
    ):
        _, mock_db = expert_app
        doc_id = uuid4()
        repo_instance = MockRepo.return_value
        repo_instance.update_sex_applicability = AsyncMock(
            return_value=_make_doc(doc_id, sex_applicability="male")
        )
        mock_get_qdrant.return_value = None

        resp = client.patch(
            f"/api/v1/expert/papers/{doc_id}/metadata",
            json={"sex_applicability": "male"},
        )

        assert resp.status_code == 200, resp.text
        mock_db.commit.assert_awaited()

    @patch("app.api.v1.expert.get_qdrant_client", new_callable=AsyncMock)
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_patch_qdrant_failure_does_not_fail_request(
        self, MockRepo, mock_get_qdrant, client
    ):
        """Restamp is best-effort: ingestion re-stamps on next re-embed."""
        doc_id = uuid4()
        repo_instance = MockRepo.return_value
        repo_instance.update_sex_applicability = AsyncMock(
            return_value=_make_doc(doc_id, sex_applicability="female")
        )

        qdrant = MagicMock()
        qdrant.set_payload = AsyncMock(side_effect=RuntimeError("qdrant down"))
        mock_get_qdrant.return_value = qdrant

        resp = client.patch(
            f"/api/v1/expert/papers/{doc_id}/metadata",
            json={"sex_applicability": "female"},
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["sex_applicability"] == "female"

    @patch("app.api.v1.expert.get_qdrant_client", new_callable=AsyncMock)
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_patch_unknown_doc_returns_404(self, MockRepo, mock_get_qdrant, client):
        repo_instance = MockRepo.return_value
        repo_instance.update_sex_applicability = AsyncMock(return_value=None)
        mock_get_qdrant.return_value = None

        resp = client.patch(
            f"/api/v1/expert/papers/{uuid4()}/metadata",
            json={"sex_applicability": "female"},
        )

        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"

    def test_patch_invalid_value_returns_422(self, client):
        resp = client.patch(
            f"/api/v1/expert/papers/{uuid4()}/metadata",
            json={"sex_applicability": "all"},
        )
        assert resp.status_code == 422

    def test_patch_non_expert_returns_403(self):
        """Real get_expert_reviewer_user role gate — no expert override."""
        from app.api.deps import get_current_user
        from app.db import get_db

        app = FastAPI()
        app.include_router(expert_router, prefix="/api/v1/expert")

        async def _mock_regular_user():
            return {"id": uuid4(), "email": "user@spelix.app", "role": "user"}

        mock_db = AsyncMock()

        async def _mock_db():
            yield mock_db

        app.dependency_overrides[get_current_user] = _mock_regular_user
        app.dependency_overrides[get_db] = _mock_db
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.patch(
            f"/api/v1/expert/papers/{uuid4()}/metadata",
            json={"sex_applicability": "female"},
        )
        assert resp.status_code == 403
