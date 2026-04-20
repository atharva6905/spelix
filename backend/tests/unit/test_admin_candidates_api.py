"""Unit tests for /api/v1/admin/coach-brain/candidates endpoints.

P3-006: FR-ADMN-12 (admin review queue), FR-BRAIN-07 (promote / reject / edit).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.admin import router
from app.schemas.candidate_review import ApproveResponse, RejectResponse, SimilarEntry
from app.schemas.coach_brain_candidate import CoachBrainCandidate
from app.services.candidate_review import (
    CandidateAlreadyReviewed,
    CandidateNotFound,
    PromptInjectionDetected,
    QdrantUpsertFailed,
)

_ = PromptInjectionDetected  # keep import alive through formatter strip

TEST_ADMIN_ID = uuid.uuid4()


def _candidate_schema(**overrides) -> CoachBrainCandidate:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(),
        exercise="bench",
        phase="descent",
        entry_type="cue",
        content="Tuck elbows.",
        trigger_tags=["bench"],
        source_analysis_ids=[uuid.uuid4()],
        confidence_score=None,
        eval_scores={"faithfulness": 0.82},
        cove_verified=False,
        cove_explanation="evaluation_failed",
        cove_trace=None,
        lifecycle_decision="ADD",
        nearest_entry_id=None,
        nearest_cosine_sim=None,
        contradiction_flag=False,
        requires_technical_review=False,
        review_status="pending",
        rejected_reason=None,
        promoted_entry_id=None,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return CoachBrainCandidate(**defaults)


@pytest.fixture()
def mock_service():
    """Shared mock CandidateReviewService — injected via FastAPI dep override."""
    from unittest.mock import MagicMock

    return MagicMock()


@pytest.fixture()
def admin_client(mock_service):
    from app.api.deps import get_admin_user
    from app.api.v1.admin import _get_review_service

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin")

    async def _mock_admin():
        return {"id": TEST_ADMIN_ID, "email": "admin@spelix.app", "role": "admin"}

    async def _mock_review_service():
        return mock_service

    app.dependency_overrides[get_admin_user] = _mock_admin
    app.dependency_overrides[_get_review_service] = _mock_review_service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def non_admin_client():
    from app.api.deps import get_current_user

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin")

    async def _mock_user():
        return {"id": uuid.uuid4(), "email": "u@spelix.app", "role": "user"}

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


class TestListPendingCandidates:
    def test_non_admin_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/coach-brain/candidates")
        assert resp.status_code == 403

    def test_lists_pending_default_limit(self, admin_client):
        rows = [_candidate_schema(), _candidate_schema()]
        with patch("app.api.v1.admin.CoachBrainCandidateRepository") as RepoCls:
            repo = RepoCls.return_value
            repo.list_pending_ordered = AsyncMock(return_value=rows)
            repo.count_pending = AsyncMock(return_value=2)

            resp = admin_client.get("/api/v1/admin/coach-brain/candidates")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["exercise"] == "bench"
        assert "created_at" in body[0]

    def test_honours_limit_and_offset(self, admin_client):
        with patch("app.api.v1.admin.CoachBrainCandidateRepository") as RepoCls:
            repo = RepoCls.return_value
            repo.list_pending_ordered = AsyncMock(return_value=[])
            repo.count_pending = AsyncMock(return_value=0)

            resp = admin_client.get(
                "/api/v1/admin/coach-brain/candidates?limit=10&offset=5"
            )

        assert resp.status_code == 200
        repo.list_pending_ordered.assert_awaited_once_with(limit=10, offset=5)

    def test_stats_endpoint_returns_pending_count(self, admin_client):
        with patch("app.api.v1.admin.CoachBrainCandidateRepository") as RepoCls:
            repo = RepoCls.return_value
            repo.count_pending = AsyncMock(return_value=11)

            resp = admin_client.get("/api/v1/admin/coach-brain/candidates/stats")

        assert resp.status_code == 200
        assert resp.json() == {"total_pending": 11}


class TestApproveCandidate:
    def test_non_admin_forbidden(self, non_admin_client):
        cid = uuid.uuid4()
        resp = non_admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/approve",
            json={},
        )
        assert resp.status_code == 403

    def test_approve_returns_entry_id_and_qdrant_point(self, admin_client, mock_service):
        cid = uuid.uuid4()
        eid = uuid.uuid4()
        mock_service.approve = AsyncMock(
            return_value=ApproveResponse(
                candidate_id=cid, entry_id=eid, qdrant_point_id=str(eid)
            )
        )
        resp = admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/approve",
            json={},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["candidate_id"] == str(cid)
        assert body["entry_id"] == str(eid)
        mock_service.approve.assert_awaited_once()
        assert mock_service.approve.await_args.kwargs["content_override"] is None

    def test_approve_passes_content_override(self, admin_client, mock_service):
        cid = uuid.uuid4()
        eid = uuid.uuid4()
        mock_service.approve = AsyncMock(
            return_value=ApproveResponse(
                candidate_id=cid, entry_id=eid, qdrant_point_id=str(eid)
            )
        )
        resp = admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/approve",
            json={"content_override": "edited cue"},
        )
        assert resp.status_code == 200
        assert mock_service.approve.await_args.kwargs["content_override"] == "edited cue"

    def test_approve_404_when_not_found(self, admin_client, mock_service):
        cid = uuid.uuid4()
        mock_service.approve = AsyncMock(side_effect=CandidateNotFound(str(cid)))
        resp = admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/approve",
            json={},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"

    def test_approve_409_when_already_reviewed(self, admin_client, mock_service):
        cid = uuid.uuid4()
        mock_service.approve = AsyncMock(
            side_effect=CandidateAlreadyReviewed("approved")
        )
        resp = admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/approve",
            json={},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "ALREADY_REVIEWED"

    def test_approve_502_when_qdrant_fails(self, admin_client, mock_service):
        cid = uuid.uuid4()
        mock_service.approve = AsyncMock(side_effect=QdrantUpsertFailed("qdrant down"))
        resp = admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/approve",
            json={},
        )
        assert resp.status_code == 502
        assert resp.json()["detail"]["error"]["code"] == "QDRANT_UPSERT_FAILED"
        # Ensure vendor exception string is not leaked in response body
        assert resp.json()["detail"]["error"]["detail"] is None

    def test_approve_422_on_prompt_injection(self, admin_client, mock_service):
        cid = uuid.uuid4()
        mock_service.approve = AsyncMock(
            side_effect=PromptInjectionDetected("content_override matches denylist")
        )
        resp = admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/approve",
            json={"content_override": "ok tuck elbows now"},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "PROMPT_INJECTION_DETECTED"


class TestRejectCandidate:
    def test_non_admin_forbidden(self, non_admin_client):
        cid = uuid.uuid4()
        resp = non_admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/reject",
            json={"reason": "off-topic"},
        )
        assert resp.status_code == 403

    def test_reject_happy_path(self, admin_client, mock_service):
        cid = uuid.uuid4()
        mock_service.reject = AsyncMock(
            return_value=RejectResponse(candidate_id=cid, rejected_reason="off-topic")
        )
        resp = admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/reject",
            json={"reason": "off-topic"},
        )
        assert resp.status_code == 200
        assert resp.json()["rejected_reason"] == "off-topic"

    def test_reject_422_when_reason_missing(self, admin_client):
        cid = uuid.uuid4()
        resp = admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/reject",
            json={},
        )
        assert resp.status_code == 422

    def test_reject_422_when_reason_blank(self, admin_client):
        cid = uuid.uuid4()
        resp = admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/reject",
            json={"reason": "   "},
        )
        assert resp.status_code == 422

    def test_reject_404_when_not_found(self, admin_client, mock_service):
        cid = uuid.uuid4()
        mock_service.reject = AsyncMock(side_effect=CandidateNotFound(str(cid)))
        resp = admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/reject",
            json={"reason": "off-topic"},
        )
        assert resp.status_code == 404

    def test_reject_409_when_already_reviewed(self, admin_client, mock_service):
        cid = uuid.uuid4()
        mock_service.reject = AsyncMock(side_effect=CandidateAlreadyReviewed("rejected"))
        resp = admin_client.post(
            f"/api/v1/admin/coach-brain/candidates/{cid}/reject",
            json={"reason": "irrelevant"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "ALREADY_REVIEWED"


class TestListSimilarEntries:
    def test_returns_top_2(self, admin_client, mock_service):

        e1_id, e2_id = uuid.uuid4(), uuid.uuid4()
        cand_id = uuid.uuid4()

        mock_service.get_similar_entries = AsyncMock(
            return_value=[
                SimilarEntry(
                    id=e1_id,
                    content="knees out",
                    exercise="squat",
                    phase="descent",
                    entry_type="cue",
                    cosine_sim=0.88,
                ),
                SimilarEntry(
                    id=e2_id,
                    content="push the floor apart",
                    exercise="squat",
                    phase="ascent",
                    entry_type="cue",
                    cosine_sim=0.81,
                ),
            ]
        )

        resp = admin_client.get(
            f"/api/v1/admin/coach-brain/candidates/{cand_id}/similar",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["items"][0]["cosine_sim"] == 0.88
        assert body["items"][1]["id"] == str(e2_id)
        mock_service.get_similar_entries.assert_awaited_once_with(
            candidate_id=cand_id, limit=2
        )

    def test_404_on_missing_candidate(self, admin_client, mock_service):
        mock_service.get_similar_entries = AsyncMock(
            side_effect=CandidateNotFound(str(uuid.uuid4()))
        )
        resp = admin_client.get(
            f"/api/v1/admin/coach-brain/candidates/{uuid.uuid4()}/similar",
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"

    def test_requires_admin(self, non_admin_client):
        resp = non_admin_client.get(
            f"/api/v1/admin/coach-brain/candidates/{uuid.uuid4()}/similar",
        )
        assert resp.status_code == 403

    def test_limit_zero_rejected(self, admin_client):
        """FastAPI validates `limit >= 1` before the handler runs → 422."""
        resp = admin_client.get(
            f"/api/v1/admin/coach-brain/candidates/{uuid.uuid4()}/similar?limit=0",
        )
        assert resp.status_code == 422

    def test_limit_above_max_rejected(self, admin_client):
        """FastAPI validates `limit <= 5` before the handler runs → 422."""
        resp = admin_client.get(
            f"/api/v1/admin/coach-brain/candidates/{uuid.uuid4()}/similar?limit=6",
        )
        assert resp.status_code == 422
