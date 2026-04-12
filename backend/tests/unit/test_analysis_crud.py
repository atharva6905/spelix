"""Unit tests for analysis CRUD, list, and status poll endpoints (B-027/028/029).

TDD gate:
- GET /api/v1/analyses/{id}/status returns current status + updated_at
- GET /api/v1/analyses/{id}/status 404 on missing analysis
- GET /api/v1/analyses/{id}/status 403 on wrong user
- DELETE /api/v1/analyses/{id} cascades (mocked Storage delete)
- DELETE /api/v1/analyses/{id} 404 on missing
- DELETE /api/v1/analyses/{id} 403 on wrong user
- PATCH /api/v1/analyses/{id} updates tags
- PATCH /api/v1/analyses/{id} 404/403
- GET /api/v1/analyses/{id} returns nested coaching + rep_metrics
- GET /api/v1/analyses/{id} 404/403
- GET /api/v1/analyses returns reverse-chron list, user-filtered
- GET /api/v1/analyses respects limit/offset

Requirements: FR-RESL-13, FR-UPLD-10, FR-UPLD-11, FR-HIST-01
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.analyses import _get_service, router

TEST_USER_ID = uuid.uuid4()
TEST_EMAIL = "athlete@example.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_analysis(
    user_id=None,
    status="completed",
    exercise_type="squat",
    exercise_variant="high_bar",
    tags=None,
    coaching_result=None,
    rep_metrics=None,
):
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.user_id = user_id or TEST_USER_ID
    obj.status = status
    obj.exercise_type = exercise_type
    obj.exercise_variant = exercise_variant
    obj.confidence_score = 0.85
    obj.video_path = f"videos/{obj.id}/squat.mp4"
    obj.annotated_video_path = f"artifacts/{obj.id}/annotated.mp4"
    obj.plot_path = f"artifacts/{obj.id}/plot.png"
    obj.pdf_path = f"artifacts/{obj.id}/report.pdf"
    obj.tags = tags or []
    obj.quality_gate_result = {"passed": True}
    obj.summary_json = {"reps": 5}
    obj.detection_result = None
    obj.form_score_safety = None
    obj.form_score_technique = None
    obj.form_score_path_balance = None
    obj.form_score_control = None
    obj.form_score_overall = None
    obj.created_at = datetime.now(timezone.utc)
    obj.updated_at = datetime.now(timezone.utc)
    obj.retry_count = 0

    # Relationships
    obj.coaching_result = coaching_result
    obj.rep_metrics = rep_metrics or []
    obj.chat_messages = []
    return obj


def _make_mock_coaching_result():
    cr = MagicMock()
    cr.structured_output_json = {"summary": "Good form", "strengths": [], "issues": []}
    cr.created_at = datetime.now(timezone.utc)
    return cr


def _make_mock_rep_metric(rep_index=0):
    rm = MagicMock()
    rm.rep_index = rep_index
    rm.start_frame = rep_index * 30
    rm.end_frame = rep_index * 30 + 25
    rm.confidence_score = 0.9
    rm.metrics_json = {"hip_angle_min": 85.0}
    return rm


def _build_app(mock_service=None) -> FastAPI:
    """Build a FastAPI app with auth and optionally service overrides."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/analyses")

    async def _mock_user():
        return {"id": TEST_USER_ID, "email": TEST_EMAIL, "role": "user"}

    app.dependency_overrides[get_current_user] = _mock_user

    if mock_service is not None:

        async def _mock_service():
            return mock_service

        app.dependency_overrides[_get_service] = _mock_service

    return app


# ---------------------------------------------------------------------------
# GET /api/v1/analyses/{id}/status
# ---------------------------------------------------------------------------


class TestGetAnalysisStatus:
    def test_returns_status_and_updated_at(self):
        analysis = _make_mock_analysis(status="processing")
        mock_service = AsyncMock()
        mock_service.get_analysis_status.return_value = analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis.id}/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(analysis.id)
        assert body["status"] == "processing"
        assert "updated_at" in body

    def test_not_found_returns_404(self):
        mock_service = AsyncMock()
        mock_service.get_analysis_status.side_effect = HTTPException(
            status_code=404,
            detail={"error": {"code": "ANALYSIS_NOT_FOUND", "message": "Not found.", "detail": None}},
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{uuid.uuid4()}/status")

        assert resp.status_code == 404

    def test_wrong_user_returns_403(self):
        mock_service = AsyncMock()
        mock_service.get_analysis_status.side_effect = HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "Not your analysis.", "detail": None}},
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{uuid.uuid4()}/status")

        assert resp.status_code == 403

    def test_invalid_uuid_returns_422(self):
        mock_service = AsyncMock()
        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get("/api/v1/analyses/not-a-uuid/status")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/v1/analyses/{id}
# ---------------------------------------------------------------------------


class TestDeleteAnalysis:
    def test_delete_owned_analysis_returns_204(self):
        mock_service = AsyncMock()
        mock_service.delete_analysis.return_value = None

        analysis_id = uuid.uuid4()
        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.delete(f"/api/v1/analyses/{analysis_id}")

        assert resp.status_code == 204
        mock_service.delete_analysis.assert_called_once_with(
            analysis_id=analysis_id,
            user_id=TEST_USER_ID,
        )

    def test_delete_not_found_returns_404(self):
        mock_service = AsyncMock()
        mock_service.delete_analysis.side_effect = HTTPException(
            status_code=404,
            detail={"error": {"code": "ANALYSIS_NOT_FOUND", "message": "Not found.", "detail": None}},
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.delete(f"/api/v1/analyses/{uuid.uuid4()}")

        assert resp.status_code == 404

    def test_delete_wrong_user_returns_403(self):
        mock_service = AsyncMock()
        mock_service.delete_analysis.side_effect = HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "Not your analysis.", "detail": None}},
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.delete(f"/api/v1/analyses/{uuid.uuid4()}")

        assert resp.status_code == 403

    def test_delete_invalid_uuid_returns_422(self):
        mock_service = AsyncMock()
        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.delete("/api/v1/analyses/not-a-uuid")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/v1/analyses/{id}
# ---------------------------------------------------------------------------


class TestPatchAnalysis:
    def test_update_tags_returns_updated_analysis(self):
        updated = _make_mock_analysis(tags=["competition", "pr"])
        mock_service = AsyncMock()
        mock_service.update_analysis.return_value = updated

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.patch(
            f"/api/v1/analyses/{updated.id}",
            json={"tags": ["competition", "pr"]},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["tags"] == ["competition", "pr"]
        mock_service.update_analysis.assert_called_once_with(
            analysis_id=updated.id,
            user_id=TEST_USER_ID,
            tags=["competition", "pr"],
        )

    def test_patch_not_found_returns_404(self):
        mock_service = AsyncMock()
        mock_service.update_analysis.side_effect = HTTPException(
            status_code=404,
            detail={"error": {"code": "ANALYSIS_NOT_FOUND", "message": "Not found.", "detail": None}},
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.patch(f"/api/v1/analyses/{uuid.uuid4()}", json={"tags": []})

        assert resp.status_code == 404

    def test_patch_wrong_user_returns_403(self):
        mock_service = AsyncMock()
        mock_service.update_analysis.side_effect = HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "Not your analysis.", "detail": None}},
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.patch(f"/api/v1/analyses/{uuid.uuid4()}", json={"tags": []})

        assert resp.status_code == 403

    def test_patch_null_tags_leaves_tags_unchanged(self):
        """PATCH with tags=null should pass None → service (no-op update)."""
        existing = _make_mock_analysis(tags=["existing"])
        mock_service = AsyncMock()
        mock_service.update_analysis.return_value = existing

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.patch(f"/api/v1/analyses/{existing.id}", json={})

        assert resp.status_code == 200
        # tags not in payload means None is passed
        call_kwargs = mock_service.update_analysis.call_args[1]
        assert call_kwargs["tags"] is None


# ---------------------------------------------------------------------------
# GET /api/v1/analyses/{id}
# ---------------------------------------------------------------------------


class TestGetAnalysisDetail:
    def test_returns_detail_with_nested_coaching_and_reps(self):
        coaching = _make_mock_coaching_result()
        reps = [_make_mock_rep_metric(0), _make_mock_rep_metric(1)]
        analysis = _make_mock_analysis(coaching_result=coaching, rep_metrics=reps)

        mock_service = AsyncMock()
        mock_service.get_analysis_detail.return_value = analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis.id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(analysis.id)
        assert body["status"] == analysis.status
        assert body["coaching_result"] is not None
        assert "structured_output_json" in body["coaching_result"]
        assert len(body["rep_metrics"]) == 2
        assert body["rep_metrics"][0]["rep_index"] == 0
        assert body["rep_metrics"][1]["rep_index"] == 1

    def test_returns_detail_without_coaching_or_reps(self):
        analysis = _make_mock_analysis(coaching_result=None, rep_metrics=[])

        mock_service = AsyncMock()
        mock_service.get_analysis_detail.return_value = analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis.id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["coaching_result"] is None
        assert body["rep_metrics"] == []

    def test_not_found_returns_404(self):
        mock_service = AsyncMock()
        mock_service.get_analysis_detail.side_effect = HTTPException(
            status_code=404,
            detail={"error": {"code": "ANALYSIS_NOT_FOUND", "message": "Not found.", "detail": None}},
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{uuid.uuid4()}")

        assert resp.status_code == 404

    def test_wrong_user_returns_403(self):
        mock_service = AsyncMock()
        mock_service.get_analysis_detail.side_effect = HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "Not your analysis.", "detail": None}},
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{uuid.uuid4()}")

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/v1/analyses
# ---------------------------------------------------------------------------


class TestListAnalyses:
    def test_returns_list_of_summaries(self):
        analyses = [_make_mock_analysis(), _make_mock_analysis()]
        mock_service = AsyncMock()
        mock_service.list_analyses.return_value = analyses

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get("/api/v1/analyses")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 2
        # Summaries should NOT contain coaching_result or rep_metrics
        assert "coaching_result" not in body[0]
        assert "rep_metrics" not in body[0]

    def test_list_passes_default_limit_and_offset(self):
        mock_service = AsyncMock()
        mock_service.list_analyses.return_value = []

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get("/api/v1/analyses")

        assert resp.status_code == 200
        mock_service.list_analyses.assert_called_once_with(
            user_id=TEST_USER_ID,
            limit=50,
            offset=0,
        )

    def test_list_respects_limit_and_offset_params(self):
        mock_service = AsyncMock()
        mock_service.list_analyses.return_value = []

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get("/api/v1/analyses?limit=10&offset=20")

        assert resp.status_code == 200
        mock_service.list_analyses.assert_called_once_with(
            user_id=TEST_USER_ID,
            limit=10,
            offset=20,
        )

    def test_list_empty_returns_empty_array(self):
        mock_service = AsyncMock()
        mock_service.list_analyses.return_value = []

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get("/api/v1/analyses")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_unauthenticated_returns_401(self):
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/analyses")
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/analyses")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Service unit tests: get_analysis_status
# ---------------------------------------------------------------------------


class TestGetAnalysisStatusService:
    @pytest.mark.asyncio
    async def test_returns_analysis_when_owned(self):
        from app.services.analysis import AnalysisService

        user_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=user_id, status="processing")
        repo = AsyncMock()
        repo.get_by_id.return_value = analysis
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        result = await service.get_analysis_status(analysis.id, user_id)
        assert result.status == "processing"

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self):
        from app.services.analysis import AnalysisService

        repo = AsyncMock()
        repo.get_by_id.return_value = None
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_analysis_status(uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_403_when_wrong_user(self):
        from app.services.analysis import AnalysisService

        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=owner_id)
        repo = AsyncMock()
        repo.get_by_id.return_value = analysis
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_analysis_status(analysis.id, other_id)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Service unit tests: delete_analysis
# ---------------------------------------------------------------------------


class TestDeleteAnalysisService:
    @pytest.mark.asyncio
    async def test_deletes_analysis_and_calls_storage_for_each_artifact(self):
        from app.services.analysis import AnalysisService

        user_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=user_id)
        repo = AsyncMock()
        repo.get_by_id.return_value = analysis
        storage = AsyncMock()
        storage.delete_file.return_value = None
        service = AnalysisService(repo=repo, storage=storage)

        await service.delete_analysis(analysis.id, user_id)

        repo.delete.assert_called_once_with(analysis.id)
        # Should delete all 4 non-null artifact paths
        assert storage.delete_file.call_count == 4

    @pytest.mark.asyncio
    async def test_delete_skips_null_artifact_paths(self):
        from app.services.analysis import AnalysisService

        user_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=user_id)
        # Set some paths to None
        analysis.annotated_video_path = None
        analysis.plot_path = None
        repo = AsyncMock()
        repo.get_by_id.return_value = analysis
        storage = AsyncMock()
        storage.delete_file.return_value = None
        service = AnalysisService(repo=repo, storage=storage)

        await service.delete_analysis(analysis.id, user_id)

        # Only video_path and pdf_path are non-null
        assert storage.delete_file.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_raises_404_when_not_found(self):
        from app.services.analysis import AnalysisService

        repo = AsyncMock()
        repo.get_by_id.return_value = None
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_analysis(uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_raises_403_when_wrong_user(self):
        from app.services.analysis import AnalysisService

        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=owner_id)
        repo = AsyncMock()
        repo.get_by_id.return_value = analysis
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_analysis(analysis.id, other_id)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Service unit tests: update_analysis
# ---------------------------------------------------------------------------


class TestUpdateAnalysisService:
    @pytest.mark.asyncio
    async def test_update_tags(self):
        from app.services.analysis import AnalysisService

        user_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=user_id, tags=[])
        repo = AsyncMock()
        repo.get_by_id.return_value = analysis
        repo.update.return_value = analysis
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        await service.update_analysis(analysis.id, user_id, tags=["pr"])
        # Tags should have been set on the model
        assert analysis.tags == ["pr"]
        repo.update.assert_called_once_with(analysis)

    @pytest.mark.asyncio
    async def test_update_raises_404_when_not_found(self):
        from app.services.analysis import AnalysisService

        repo = AsyncMock()
        repo.get_by_id.return_value = None
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.update_analysis(uuid.uuid4(), uuid.uuid4(), tags=["x"])
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_raises_403_when_wrong_user(self):
        from app.services.analysis import AnalysisService

        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=owner_id)
        repo = AsyncMock()
        repo.get_by_id.return_value = analysis
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.update_analysis(analysis.id, other_id, tags=["x"])
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Service unit tests: list_analyses
# ---------------------------------------------------------------------------


class TestListAnalysesService:
    @pytest.mark.asyncio
    async def test_list_returns_repo_results(self):
        from app.services.analysis import AnalysisService

        user_id = uuid.uuid4()
        analyses = [_make_mock_analysis(user_id=user_id) for _ in range(3)]
        repo = AsyncMock()
        repo.get_by_user.return_value = analyses
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        result = await service.list_analyses(user_id, limit=50, offset=0)
        assert len(result) == 3
        repo.get_by_user.assert_called_once_with(user_id, limit=50, offset=0)


# ---------------------------------------------------------------------------
# Service unit tests: get_analysis_detail
# ---------------------------------------------------------------------------


class TestGetAnalysisDetailService:
    @pytest.mark.asyncio
    async def test_returns_analysis_with_relations(self):
        from app.services.analysis import AnalysisService

        user_id = uuid.uuid4()
        coaching = _make_mock_coaching_result()
        reps = [_make_mock_rep_metric(0)]
        analysis = _make_mock_analysis(user_id=user_id, coaching_result=coaching, rep_metrics=reps)

        repo = AsyncMock()
        repo.get_by_id_with_relations.return_value = analysis
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        result = await service.get_analysis_detail(analysis.id, user_id)
        assert result.coaching_result is not None
        assert len(result.rep_metrics) == 1
        repo.get_by_id_with_relations.assert_called_once_with(analysis.id)

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self):
        from app.services.analysis import AnalysisService

        repo = AsyncMock()
        repo.get_by_id_with_relations.return_value = None
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_analysis_detail(uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_403_when_wrong_user(self):
        from app.services.analysis import AnalysisService

        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=owner_id)
        repo = AsyncMock()
        repo.get_by_id_with_relations.return_value = analysis
        storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_analysis_detail(analysis.id, other_id)
        assert exc_info.value.status_code == 403
