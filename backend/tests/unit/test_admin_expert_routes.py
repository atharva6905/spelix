"""Unit tests for Phase 2 admin and expert reviewer API endpoints.

Tests cover:
- Admin RAG corpus management (P2-035, FR-ADMN-06, FR-RAGK-08/09)
- Admin expert reviewer queue (P2-036, FR-ADMN-07)
- Admin Coach Brain management (P2-037, FR-ADMN-10)
- Expert reviewer auth guard (P2-038, FR-EXPV-01)
- Expert review queue (P2-039, FR-EXPV-02)
- Expert analysis detail anonymization (P2-040, FR-EXPV-03)
- Expert annotation submission (P2-041, FR-EXPV-04)
- Expert paper upload (P2-042, FR-EXPV-05)
- Expert paper review (P2-043, FR-EXPV-06)
- Golden dataset labeling (P2-044, FR-EXPV-07)
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.admin import router as admin_router
from app.api.v1.expert import router as expert_router
from app.schemas.expert_review import ExpertAnalysisDetail, ExpertQueueItem

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

TEST_ADMIN_ID = uuid.uuid4()
TEST_EXPERT_ID = uuid.uuid4()
TEST_USER_ID = uuid.uuid4()
TEST_ANALYSIS_ID = uuid.uuid4()
TEST_DOC_ID = uuid.uuid4()
TEST_ENTRY_ID = uuid.uuid4()

NOW = datetime.now(timezone.utc)


def _make_rag_document(**kwargs):
    from app.models.rag_document import RagDocument

    doc = RagDocument(
        title=kwargs.get("title", "Test Paper"),
        source_url=kwargs.get("source_url", "https://example.com/paper.pdf"),
        document_type=kwargs.get("document_type", "research_paper"),
        exercise_tags=kwargs.get("exercise_tags", ["squat"]),
        chunk_count=kwargs.get("chunk_count", 3),
        ingested_at=kwargs.get("ingested_at", NOW),
        authors=kwargs.get("authors", ["Smith J", "Jones A"]),
        year=kwargs.get("year", 2023),
        doi=kwargs.get("doi", "10.1234/test"),
        study_design=kwargs.get("study_design", "rct"),
        population=kwargs.get("population", "trained adults"),
        measurement_method=kwargs.get("measurement_method", "3D motion capture"),
        quality_tier=kwargs.get("quality_tier", "L2_rct"),
        quality_score=kwargs.get("quality_score", Decimal("0.750")),
        review_status=kwargs.get("review_status", "pending"),
        reviewer_id=kwargs.get("reviewer_id", None),
        reviewed_at=kwargs.get("reviewed_at", None),
        storage_path=kwargs.get("storage_path", None),
    )
    doc.__dict__.update({
        "id": kwargs.get("id", TEST_DOC_ID),
        "extra_metadata": kwargs.get("extra_metadata", {}),
        "created_at": kwargs.get("created_at", NOW),
        "updated_at": kwargs.get("updated_at", NOW),
    })
    return doc


def _make_coach_brain_entry(**kwargs):
    from app.models.coach_brain_entry import CoachBrainEntry

    entry = CoachBrainEntry(
        exercise=kwargs.get("exercise", "squat"),
        phase=kwargs.get("phase", "descent"),
        entry_type=kwargs.get("entry_type", "cue"),
        content=kwargs.get("content", "Drive knees out over toes"),
        trigger_tags=kwargs.get("trigger_tags", ["knee_cave"]),
        confirmation_count=kwargs.get("confirmation_count", 1),
        status=kwargs.get("status", "seed"),
        source_analysis_ids=kwargs.get("source_analysis_ids", []),
        confidence_score=kwargs.get("confidence_score", Decimal("0.850")),
    )
    entry.__dict__.update({
        "id": kwargs.get("id", TEST_ENTRY_ID),
        "extra_metadata": kwargs.get("extra_metadata", {}),
        "created_at": kwargs.get("created_at", NOW),
        "updated_at": kwargs.get("updated_at", NOW),
    })
    return entry


def _make_analysis(**kwargs):
    from app.models.analysis import Analysis

    a = Analysis(
        user_id=kwargs.get("user_id", TEST_USER_ID),
        exercise_type=kwargs.get("exercise_type", "squat"),
        exercise_variant=kwargs.get("exercise_variant", "high_bar"),
        status=kwargs.get("status", "completed"),
    )
    a.__dict__.update({
        "id": kwargs.get("id", TEST_ANALYSIS_ID),
        "confidence_score": kwargs.get("confidence_score", 0.80),
        "flagged_for_review": kwargs.get("flagged_for_review", False),
        "is_golden_dataset": kwargs.get("is_golden_dataset", False),
        "created_at": kwargs.get("created_at", NOW),
        "updated_at": kwargs.get("updated_at", NOW),
        "error_message": None,
        "retry_count": 0,
        "video_path": None,
        "annotated_video_path": None,
        "plot_path": None,
        "pdf_path": None,
        "summary_json": kwargs.get("summary_json", {"total_reps": 3}),
        "quality_gate_result": kwargs.get("quality_gate_result", {"passed": True}),
        "tags": None,
        "threshold_version": None,
        "weight_kg": None,
        "form_score_safety": kwargs.get("form_score_safety", 7.5),
        "form_score_technique": kwargs.get("form_score_technique", 8.0),
        "form_score_path_balance": kwargs.get("form_score_path_balance", 7.0),
        "form_score_control": kwargs.get("form_score_control", 6.5),
        "form_score_overall": kwargs.get("form_score_overall", 7.3),
        "retrieval_context": None,
        "eval_scores": None,
        "detection_result": None,
    })
    return a


def _make_expert_review(**kwargs):
    from app.models.analysis_expert_review import AnalysisExpertReview

    r = AnalysisExpertReview(
        analysis_id=kwargs.get("analysis_id", TEST_ANALYSIS_ID),
        annotator_id=kwargs.get("annotator_id", TEST_EXPERT_ID),
        issues_identified=kwargs.get("issues_identified", {"knee_cave": "moderate"}),
        coaching_quality_score=kwargs.get("coaching_quality_score", Decimal("7.5")),
        movement_advice_accurate=kwargs.get("movement_advice_accurate", True),
        engagement_advice_accurate=kwargs.get("engagement_advice_accurate", True),
        suggested_corrections=kwargs.get("suggested_corrections", "Add knee tracking cue"),
        cited_sources=kwargs.get("cited_sources", [{"title": "Squat Biomechanics", "doi": "10.1234/squat"}]),
        is_golden_label=kwargs.get("is_golden_label", False),
    )
    r.__dict__.update({
        "id": kwargs.get("id", uuid.uuid4()),
        "created_at": kwargs.get("created_at", NOW),
        "updated_at": kwargs.get("updated_at", NOW),
    })
    return r


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def admin_app():
    from app.api.deps import get_admin_user, get_redis
    from app.db import get_db

    app = FastAPI()
    app.include_router(admin_router, prefix="/api/v1/admin")

    async def _mock_admin():
        return {"id": TEST_ADMIN_ID, "email": "admin@spelix.app", "role": "admin"}

    mock_db = AsyncMock()

    async def _mock_db():
        yield mock_db

    async def _mock_redis():
        yield AsyncMock()

    app.dependency_overrides[get_admin_user] = _mock_admin
    app.dependency_overrides[get_db] = _mock_db
    app.dependency_overrides[get_redis] = _mock_redis
    return app, mock_db


@pytest.fixture()
def admin_client(admin_app):
    app, _ = admin_app
    return TestClient(app, raise_server_exceptions=False)


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
def expert_client(expert_app):
    app, _ = expert_app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def non_expert_app():
    """App with regular user auth — should get 403 on expert routes."""
    from app.api.deps import get_current_user
    from app.db import get_db

    app = FastAPI()
    app.include_router(expert_router, prefix="/api/v1/expert")

    async def _mock_user():
        return {"id": TEST_USER_ID, "email": "user@spelix.app", "role": "user"}

    app.dependency_overrides[get_current_user] = _mock_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Expert Reviewer Auth Guard (P2-038, FR-EXPV-01)
# ---------------------------------------------------------------------------


class TestExpertAuthGuard:
    def test_regular_user_gets_403_on_queue(self, non_expert_app):
        resp = non_expert_app.get("/api/v1/expert/queue")
        assert resp.status_code == 403

    def test_regular_user_gets_403_on_analysis_detail(self, non_expert_app):
        resp = non_expert_app.get(f"/api/v1/expert/analyses/{TEST_ANALYSIS_ID}")
        assert resp.status_code == 403

    def test_regular_user_gets_403_on_annotation(self, non_expert_app):
        resp = non_expert_app.post(
            f"/api/v1/expert/analyses/{TEST_ANALYSIS_ID}/annotations",
            json={"issues_identified": {}, "coaching_quality_score": 5.0},
        )
        assert resp.status_code == 403

    def test_regular_user_gets_403_on_paper_upload(self, non_expert_app):
        resp = non_expert_app.post(
            "/api/v1/expert/papers",
            json={"title": "Test"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin RAG Corpus (P2-035, FR-ADMN-06)
# ---------------------------------------------------------------------------


class TestAdminRagCorpus:
    @patch("app.api.v1.admin.RagDocumentRepository")
    def test_list_rag_documents(self, MockRepo, admin_client):
        doc = _make_rag_document()
        instance = MockRepo.return_value
        instance.list_all = AsyncMock(return_value=[doc])

        resp = admin_client.get("/api/v1/admin/rag/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Paper"
        assert data[0]["review_status"] == "pending"

    @patch("app.api.v1.admin.RagDocumentRepository")
    def test_list_rag_documents_with_filters(self, MockRepo, admin_client):
        doc = _make_rag_document(review_status="reviewed_approved")
        instance = MockRepo.return_value
        instance.list_all = AsyncMock(return_value=[doc])

        resp = admin_client.get(
            "/api/v1/admin/rag/documents",
            params={"review_status": "reviewed_approved", "exercise_tag": "squat"},
        )
        assert resp.status_code == 200

    @patch("app.api.v1.admin.RagDocumentRepository")
    def test_delete_rag_document_success(self, MockRepo, admin_client):
        doc = _make_rag_document()
        instance = MockRepo.return_value
        instance.get_by_id = AsyncMock(return_value=doc)
        instance.delete = AsyncMock(return_value=True)

        resp = admin_client.delete(f"/api/v1/admin/rag/documents/{TEST_DOC_ID}")
        assert resp.status_code == 204

    @patch("app.api.v1.admin.RagDocumentRepository")
    def test_delete_rag_document_not_found(self, MockRepo, admin_client):
        instance = MockRepo.return_value
        instance.get_by_id = AsyncMock(return_value=None)

        resp = admin_client.delete(f"/api/v1/admin/rag/documents/{uuid.uuid4()}")
        assert resp.status_code == 404

    @patch("app.api.v1.admin.RagDocumentRepository")
    def test_re_embed_approved_doc(self, MockRepo, admin_client):
        doc = _make_rag_document(review_status="reviewed_approved")
        instance = MockRepo.return_value
        instance.get_by_id = AsyncMock(return_value=doc)

        resp = admin_client.post(f"/api/v1/admin/rag/documents/{TEST_DOC_ID}/re-embed")
        assert resp.status_code == 200
        assert "Re-embed queued" in resp.json()["message"]

    @patch("app.api.v1.admin.RagDocumentRepository")
    def test_re_embed_pending_doc_rejected(self, MockRepo, admin_client):
        doc = _make_rag_document(review_status="pending")
        instance = MockRepo.return_value
        instance.get_by_id = AsyncMock(return_value=doc)

        resp = admin_client.post(f"/api/v1/admin/rag/documents/{TEST_DOC_ID}/re-embed")
        assert resp.status_code == 400

    @patch("app.api.v1.admin.RagDocumentRepository")
    def test_list_rag_documents_invalid_review_status_422(self, MockRepo, admin_client):
        instance = MockRepo.return_value
        instance.list_all = AsyncMock(return_value=[])

        resp = admin_client.get(
            "/api/v1/admin/rag/documents",
            params={"review_status": "bogus_value"},
        )
        assert resp.status_code == 422

    @patch("app.api.v1.admin.RagDocumentRepository")
    def test_list_rag_documents_excludes_uploading_by_default(
        self, MockRepo, admin_client
    ):
        instance = MockRepo.return_value
        instance.list_all = AsyncMock(return_value=[])

        admin_client.get("/api/v1/admin/rag/documents")

        instance.list_all.assert_called_once()
        call_kwargs = instance.list_all.call_args.kwargs
        assert call_kwargs.get("exclude_uploading") is True


# ---------------------------------------------------------------------------
# Admin Expert Queue (P2-036, FR-ADMN-07)
# ---------------------------------------------------------------------------


class TestAdminExpertQueue:
    @patch("app.api.v1.admin.AnalysisExpertReviewRepository")
    @patch("app.api.v1.admin.AdminService")
    def test_list_expert_queue(self, MockService, MockReviewRepo, admin_client):
        analysis = _make_analysis(flagged_for_review=True)
        service_instance = MockService.return_value
        service_instance.list_flagged_analyses = AsyncMock(return_value=[analysis])

        review_instance = MockReviewRepo.return_value
        review_instance.count_by_analysis = AsyncMock(return_value=2)
        review_instance.latest_annotation_at = AsyncMock(return_value=NOW)

        resp = admin_client.get("/api/v1/admin/expert-queue")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["annotation_count"] == 2
        assert data[0]["flagged_for_review"] is True

    @patch("app.api.v1.admin.AdminService")
    def test_expert_queue_stats(self, MockService, admin_client):
        service_instance = MockService.return_value
        service_instance.get_expert_queue_stats = AsyncMock(
            return_value={"total_flagged": 5, "total_annotated": 3, "golden_dataset_count": 1}
        )

        resp = admin_client.get("/api/v1/admin/expert-queue/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_flagged"] == 5
        assert data["golden_dataset_count"] == 1


# ---------------------------------------------------------------------------
# Admin Coach Brain (P2-037, FR-ADMN-10)
# ---------------------------------------------------------------------------


class TestAdminCoachBrain:
    @patch("app.api.v1.admin.CoachBrainRepository")
    def test_list_coach_brain(self, MockRepo, admin_client):
        entry = _make_coach_brain_entry()
        instance = MockRepo.return_value
        instance.list_all = AsyncMock(return_value=[entry])

        resp = admin_client.get("/api/v1/admin/coach-brain")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["content"] == "Drive knees out over toes"

    @patch("app.api.v1.admin.CoachBrainRepository")
    def test_list_coach_brain_with_filters(self, MockRepo, admin_client):
        entry = _make_coach_brain_entry()
        instance = MockRepo.return_value
        instance.list_all = AsyncMock(return_value=[entry])

        resp = admin_client.get(
            "/api/v1/admin/coach-brain",
            params={"exercise": "squat", "status": "seed"},
        )
        assert resp.status_code == 200

    @patch("app.api.v1.admin.CoachBrainRepository")
    def test_create_coach_brain_entry(self, MockRepo, admin_client):
        entry = _make_coach_brain_entry()
        instance = MockRepo.return_value
        instance.create = AsyncMock(return_value=entry)

        resp = admin_client.post(
            "/api/v1/admin/coach-brain",
            json={
                "content": "Drive knees out over toes",
                "exercise": "squat",
                "phase": "descent",
                "entry_type": "cue",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["exercise"] == "squat"

    @patch("app.api.v1.admin.CoachBrainRepository")
    def test_update_coach_brain_entry(self, MockRepo, admin_client):
        entry = _make_coach_brain_entry()
        instance = MockRepo.return_value
        instance.get_by_id = AsyncMock(return_value=entry)
        instance.update = AsyncMock(return_value=entry)

        resp = admin_client.patch(
            f"/api/v1/admin/coach-brain/{TEST_ENTRY_ID}",
            json={"status": "active"},
        )
        assert resp.status_code == 200

    @patch("app.api.v1.admin.CoachBrainRepository")
    def test_update_coach_brain_not_found(self, MockRepo, admin_client):
        instance = MockRepo.return_value
        instance.get_by_id = AsyncMock(return_value=None)

        resp = admin_client.patch(
            f"/api/v1/admin/coach-brain/{uuid.uuid4()}",
            json={"status": "active"},
        )
        assert resp.status_code == 404

    @patch("app.api.v1.admin.CoachBrainRepository")
    def test_delete_coach_brain_entry(self, MockRepo, admin_client):
        entry = _make_coach_brain_entry()
        instance = MockRepo.return_value
        instance.get_by_id = AsyncMock(return_value=entry)
        instance.delete_by_id = AsyncMock(return_value=True)

        resp = admin_client.delete(f"/api/v1/admin/coach-brain/{TEST_ENTRY_ID}")
        assert resp.status_code == 204

    @patch("app.api.v1.admin.CoachBrainRepository")
    def test_delete_coach_brain_not_found(self, MockRepo, admin_client):
        instance = MockRepo.return_value
        instance.get_by_id = AsyncMock(return_value=None)

        resp = admin_client.delete(f"/api/v1/admin/coach-brain/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Expert Review Queue (P2-039, FR-EXPV-02)
# ---------------------------------------------------------------------------


class TestExpertQueue:
    @patch("app.api.v1.expert.ExpertService")
    def test_get_queue_returns_items(self, MockService, expert_client):
        item = ExpertQueueItem(
            analysis_id=TEST_ANALYSIS_ID,
            exercise_type="squat",
            exercise_variant="high_bar",
            confidence_score=0.80,
            form_score_overall=7.3,
            flagged_for_review=True,
            created_at=NOW,
            annotation_count=0,
        )
        instance = MockService.return_value
        instance.get_review_queue = AsyncMock(return_value=[item])

        resp = expert_client.get("/api/v1/expert/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["exercise_type"] == "squat"

    @patch("app.api.v1.expert.ExpertService")
    def test_get_queue_with_type_filter(self, MockService, expert_client):
        instance = MockService.return_value
        instance.get_review_queue = AsyncMock(return_value=[])

        resp = expert_client.get("/api/v1/expert/queue", params={"queue_type": "flagged"})
        assert resp.status_code == 200

    def test_get_queue_invalid_type_rejected(self, expert_client):
        resp = expert_client.get("/api/v1/expert/queue", params={"queue_type": "invalid"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Expert Analysis Detail (P2-040, FR-EXPV-03)
# ---------------------------------------------------------------------------


class TestExpertAnalysisDetail:
    @patch("app.api.v1.expert.ExpertService")
    def test_detail_is_anonymized(self, MockService, expert_client):
        """FR-EXPV-03: user_id must NOT appear in the response."""
        detail = ExpertAnalysisDetail(
            id=TEST_ANALYSIS_ID,
            exercise_type="squat",
            exercise_variant="high_bar",
            confidence_score=0.80,
            form_score_safety=7.5,
            form_score_technique=8.0,
            form_score_path_balance=7.0,
            form_score_control=6.5,
            form_score_overall=7.3,
            summary_json={"total_reps": 3},
            quality_gate_result={"passed": True},
            coaching_result=None,
            rep_metrics=[],
            retrieval_context=None,
            eval_scores=None,
            flagged_for_review=False,
            is_golden_dataset=False,
            created_at=NOW,
        )
        instance = MockService.return_value
        instance.get_analysis_detail = AsyncMock(return_value=detail)

        resp = expert_client.get(f"/api/v1/expert/analyses/{TEST_ANALYSIS_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" not in data
        assert data["exercise_type"] == "squat"
        assert data["form_score_safety"] == 7.5

    @patch("app.api.v1.expert.ExpertService")
    def test_detail_not_found(self, MockService, expert_client):
        instance = MockService.return_value
        instance.get_analysis_detail = AsyncMock(return_value=None)

        resp = expert_client.get(f"/api/v1/expert/analyses/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Expert Annotation (P2-041, FR-EXPV-04)
# ---------------------------------------------------------------------------


class TestExpertAnnotation:
    @patch("app.api.v1.expert.ExpertService")
    def test_submit_annotation(self, MockService, expert_client):
        review = _make_expert_review()
        instance = MockService.return_value
        instance.submit_annotation = AsyncMock(return_value=review)

        resp = expert_client.post(
            f"/api/v1/expert/analyses/{TEST_ANALYSIS_ID}/annotations",
            json={
                "issues_identified": {"knee_cave": "moderate"},
                "coaching_quality_score": 7.5,
                "movement_advice_accurate": True,
                "engagement_advice_accurate": True,
                "suggested_corrections": "Add knee tracking cue",
                "cited_sources": [{"title": "Squat Biomechanics"}],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["coaching_quality_score"] == 7.5

    @patch("app.api.v1.expert.ExpertService")
    def test_submit_annotation_score_out_of_range(self, MockService, expert_client):
        resp = expert_client.post(
            f"/api/v1/expert/analyses/{TEST_ANALYSIS_ID}/annotations",
            json={"coaching_quality_score": 11.0},
        )
        assert resp.status_code == 422

    @patch("app.api.v1.expert.AnalysisExpertReviewRepository")
    def test_list_annotations(self, MockRepo, expert_client):
        review = _make_expert_review()
        instance = MockRepo.return_value
        instance.list_by_analysis = AsyncMock(return_value=[review])

        resp = expert_client.get(f"/api/v1/expert/analyses/{TEST_ANALYSIS_ID}/annotations")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1


def test_annotation_create_uses_movement_advice_field():
    """D-029: field must be movement_advice_accurate, not injury_advice_accurate."""
    from app.schemas.expert_review import AnnotationCreate

    schema = AnnotationCreate(movement_advice_accurate=True)
    assert schema.movement_advice_accurate is True
    assert not hasattr(schema, "injury_advice_accurate")


# ---------------------------------------------------------------------------
# Expert Paper Upload (P2-042, FR-EXPV-05, FR-EXPV-02 + ADR-EXPERT-01)
# The legacy metadata-only test was replaced when POST /expert/papers became
# a two-phase signed-URL flow. The 3-phase flow is covered end-to-end by
# tests/unit/test_expert_paper_upload.py (phase 1) and
# tests/unit/test_expert_paper_complete.py (phase 3).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Expert Paper Review (P2-043, FR-EXPV-06)
# ---------------------------------------------------------------------------


class TestExpertPaperReview:
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_approve_paper(self, MockRepo, expert_client):
        doc = _make_rag_document(review_status="reviewed_approved", reviewer_id=TEST_EXPERT_ID, reviewed_at=NOW)
        instance = MockRepo.return_value
        instance.update_review_status = AsyncMock(return_value=doc)

        resp = expert_client.patch(
            f"/api/v1/expert/papers/{TEST_DOC_ID}/review",
            json={"decision": "reviewed_approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["review_status"] == "reviewed_approved"

    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_reject_paper(self, MockRepo, expert_client):
        doc = _make_rag_document(review_status="reviewed_rejected", reviewer_id=TEST_EXPERT_ID, reviewed_at=NOW)
        instance = MockRepo.return_value
        instance.update_review_status = AsyncMock(return_value=doc)

        resp = expert_client.patch(
            f"/api/v1/expert/papers/{TEST_DOC_ID}/review",
            json={"decision": "reviewed_rejected", "review_notes": "Poor methodology"},
        )
        assert resp.status_code == 200

    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_review_not_found(self, MockRepo, expert_client):
        instance = MockRepo.return_value
        instance.update_review_status = AsyncMock(return_value=None)

        resp = expert_client.patch(
            f"/api/v1/expert/papers/{uuid.uuid4()}/review",
            json={"decision": "reviewed_approved"},
        )
        assert resp.status_code == 404

    def test_invalid_decision_rejected(self, expert_client):
        resp = expert_client.patch(
            f"/api/v1/expert/papers/{TEST_DOC_ID}/review",
            json={"decision": "invalid_status"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Golden Dataset Labeling (P2-044, FR-EXPV-07)
# ---------------------------------------------------------------------------


class TestGoldenDataset:
    @patch("app.api.v1.expert.ExpertService")
    def test_label_golden(self, MockService, expert_client):
        instance = MockService.return_value
        instance.set_golden_label = AsyncMock(
            return_value={"id": str(TEST_ANALYSIS_ID), "is_golden_dataset": True}
        )

        resp = expert_client.patch(
            f"/api/v1/expert/analyses/{TEST_ANALYSIS_ID}/golden",
            json={"is_golden_dataset": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_golden_dataset"] is True

    @patch("app.api.v1.expert.ExpertService")
    def test_label_golden_not_found(self, MockService, expert_client):
        instance = MockService.return_value
        instance.set_golden_label = AsyncMock(return_value={})

        resp = expert_client.patch(
            f"/api/v1/expert/analyses/{uuid.uuid4()}/golden",
            json={"is_golden_dataset": True},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Expert Reviewer Role Dep Unit Tests
# ---------------------------------------------------------------------------


class TestExpertReviewerDep:
    def test_admin_can_access_expert_portal(self):
        """ADR-041: admins can also access expert portal."""
        from app.api.deps import get_expert_reviewer_user

        user = {"id": TEST_ADMIN_ID, "email": "admin@spelix.app", "role": "admin"}
        result = get_expert_reviewer_user(user)
        assert result["role"] == "admin"

    def test_expert_reviewer_can_access(self):
        from app.api.deps import get_expert_reviewer_user

        user = {"id": TEST_EXPERT_ID, "email": "expert@spelix.app", "role": "expert_reviewer"}
        result = get_expert_reviewer_user(user)
        assert result["role"] == "expert_reviewer"

    def test_regular_user_rejected(self):
        from fastapi import HTTPException
        from app.api.deps import get_expert_reviewer_user

        user = {"id": TEST_USER_ID, "email": "user@spelix.app", "role": "user"}
        with pytest.raises(HTTPException) as exc_info:
            get_expert_reviewer_user(user)
        assert exc_info.value.status_code == 403
