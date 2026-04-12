"""Unit tests for analyses API endpoints (B-009).

TDD gate:
- POST /api/v1/analyses with valid body -> 201 with UUID + upload_url
- POST /api/v1/analyses with >50MB -> 413
- POST /api/v1/analyses with bad exercise -> 400
- POST /api/v1/analyses/{id}/start on owned queued analysis -> 202
- POST /api/v1/analyses/{id}/start on non-existent -> 404
- POST /api/v1/analyses/{id}/start on wrong user -> 403
- POST /api/v1/analyses/{id}/start on already-started -> 409

Requirements: FR-UPLD-07, FR-UPLD-16, FR-UPLD-17
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


def _make_mock_analysis(
    user_id=None,
    status="queued",
    exercise_type="squat",
    exercise_variant="high_bar",
):
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.user_id = user_id or TEST_USER_ID
    obj.status = status
    obj.exercise_type = exercise_type
    obj.exercise_variant = exercise_variant
    obj.retry_count = 0
    obj.video_path = f"videos/{obj.id}/squat.mp4"
    obj.created_at = datetime.now(timezone.utc)
    obj.updated_at = datetime.now(timezone.utc)
    return obj


class _CreateResult:
    def __init__(self, analysis, upload_url, expires_at):
        self.analysis = analysis
        self.upload_url = upload_url
        self.expires_at = expires_at


def _build_app(mock_service=None) -> FastAPI:
    """Build a FastAPI app with auth and optionally service overrides."""

    from limits.storage import MemoryStorage

    from app.rate_limit import limiter

    app = FastAPI()
    # Use in-memory storage to avoid Redis dependency in unit tests
    mem = MemoryStorage()
    limiter._storage = mem
    limiter._limiter.storage = mem
    app.state.limiter = limiter
    app.include_router(router, prefix="/api/v1/analyses")

    async def _mock_user():
        return {"id": TEST_USER_ID, "email": TEST_EMAIL, "role": "user"}

    app.dependency_overrides[get_current_user] = _mock_user

    if mock_service is not None:

        async def _mock_service():
            return mock_service

        app.dependency_overrides[_get_service] = _mock_service

    return app


@pytest.fixture()
def app_client():
    """Return a TestClient with auth dependency overridden (no service mock)."""
    return TestClient(_build_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /api/v1/analyses
# ---------------------------------------------------------------------------


class TestPostAnalyses:
    def test_valid_request_returns_201(self):
        analysis = _make_mock_analysis()
        expires_at = datetime.now(timezone.utc)
        upload_url = "https://storage.example.com/upload/signed?token=abc123"
        create_result = _CreateResult(analysis, upload_url, expires_at)

        mock_service = AsyncMock()
        mock_service.create_analysis.return_value = create_result

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/analyses",
            json={
                "exercise_type": "squat",
                "exercise_variant": "high_bar",
                "filename": "squat.mp4",
                "file_size_bytes": 10_000_000,
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert "upload_url" in body
        assert body["status"] == "queued"
        assert "expires_at" in body

    def test_invalid_exercise_type_returns_422(self):
        # Pydantic Literal enforcement rejects invalid types at schema
        # validation time (before the service is called), so FastAPI
        # returns 422 Unprocessable Entity rather than 400.
        mock_service = AsyncMock()

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/analyses",
            json={
                "exercise_type": "lunges",
                "exercise_variant": "high_bar",
                "filename": "lunges.mp4",
                "file_size_bytes": 1_000_000,
            },
        )

        assert resp.status_code == 422
        mock_service.create_analysis.assert_not_called()

    def test_file_over_50mb_returns_413(self):
        mock_service = AsyncMock()
        mock_service.create_analysis.side_effect = HTTPException(
            status_code=413,
            detail={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": "File exceeds the 50 MB limit.",
                    "detail": None,
                }
            },
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/analyses",
            json={
                "exercise_type": "squat",
                "exercise_variant": "high_bar",
                "filename": "huge.mp4",
                "file_size_bytes": 52_428_801,
            },
        )

        assert resp.status_code == 413

    def test_missing_required_field_returns_422(self, app_client: TestClient):
        resp = app_client.post(
            "/api/v1/analyses",
            json={
                "exercise_type": "squat",
                # missing exercise_variant, filename, file_size_bytes
            },
        )
        assert resp.status_code == 422

    def test_unauthenticated_returns_401(self):
        """Without auth override, missing token -> 401."""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/analyses")
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/api/v1/analyses",
            json={
                "exercise_type": "squat",
                "exercise_variant": "high_bar",
                "filename": "squat.mp4",
                "file_size_bytes": 1_000_000,
            },
        )
        assert resp.status_code == 401

    def test_response_contains_uuid(self):
        analysis = _make_mock_analysis()
        expires_at = datetime.now(timezone.utc)
        upload_url = "https://storage.example.com/upload/signed?token=test"
        create_result = _CreateResult(analysis, upload_url, expires_at)

        mock_service = AsyncMock()
        mock_service.create_analysis.return_value = create_result

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/analyses",
            json={
                "exercise_type": "bench",
                "exercise_variant": "incline",
                "filename": "bench.mp4",
                "file_size_bytes": 5_000_000,
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        parsed_id = uuid.UUID(body["id"])
        assert parsed_id == analysis.id


# ---------------------------------------------------------------------------
# POST /api/v1/analyses/{id}/start
# ---------------------------------------------------------------------------


class TestPostAnalysesStart:
    def test_start_owned_queued_analysis_returns_202(self):
        analysis_id = uuid.uuid4()
        started_analysis = _make_mock_analysis(status="quality_gate_pending")
        started_analysis.id = analysis_id

        mock_service = AsyncMock()
        mock_service.start_analysis.return_value = started_analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(f"/api/v1/analyses/{analysis_id}/start")

        assert resp.status_code == 202
        body = resp.json()
        assert body["id"] == str(analysis_id)
        assert body["status"] == "quality_gate_pending"

    def test_start_nonexistent_returns_404(self):
        analysis_id = uuid.uuid4()

        mock_service = AsyncMock()
        mock_service.start_analysis.side_effect = HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "ANALYSIS_NOT_FOUND",
                    "message": "Analysis not found.",
                    "detail": None,
                }
            },
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(f"/api/v1/analyses/{analysis_id}/start")

        assert resp.status_code == 404

    def test_start_wrong_user_returns_403(self):
        analysis_id = uuid.uuid4()

        mock_service = AsyncMock()
        mock_service.start_analysis.side_effect = HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You do not own this analysis.",
                    "detail": None,
                }
            },
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(f"/api/v1/analyses/{analysis_id}/start")

        assert resp.status_code == 403

    def test_start_wrong_status_returns_409(self):
        analysis_id = uuid.uuid4()

        mock_service = AsyncMock()
        mock_service.start_analysis.side_effect = HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "INVALID_STATUS_TRANSITION",
                    "message": "Analysis is not in queued state.",
                    "detail": None,
                }
            },
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(f"/api/v1/analyses/{analysis_id}/start")

        assert resp.status_code == 409

    def test_start_invalid_uuid_returns_422(self, app_client: TestClient):
        resp = app_client.post("/api/v1/analyses/not-a-uuid/start")
        assert resp.status_code == 422

    def test_start_unauthenticated_returns_401(self):
        """Without auth override, missing token -> 401."""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/analyses")
        client = TestClient(app, raise_server_exceptions=False)

        analysis_id = uuid.uuid4()
        resp = client.post(f"/api/v1/analyses/{analysis_id}/start")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/analyses/{id} — full detail (B-087)
# ---------------------------------------------------------------------------


class TestGetAnalysisDetail:
    """Tests for GET /api/v1/analyses/{id} full detail endpoint."""

    def _make_detail_analysis(self, user_id=None, status="completed"):
        """Build a mock analysis object that satisfies AnalysisDetail schema."""
        obj = _make_mock_analysis(user_id=user_id, status=status)
        obj.confidence_score = 0.85
        obj.annotated_video_path = f"artifacts/{obj.id}/annotated.mp4"
        obj.plot_path = f"artifacts/{obj.id}/plot.png"
        obj.pdf_path = f"artifacts/{obj.id}/report.pdf"
        obj.tags = ["competition", "pr"]
        obj.quality_gate_result = None
        obj.summary_json = None
        obj.detection_result = None
        obj.form_score_safety = None
        obj.form_score_technique = None
        obj.form_score_path_balance = None
        obj.form_score_control = None
        obj.form_score_overall = None
        # Nested relationships — empty for simplicity
        obj.coaching_result = None
        obj.rep_metrics = []
        obj.chat_messages = []
        return obj

    def test_get_detail_returns_200_with_correct_fields(self):
        """GET /analyses/{id} returns 200 and all expected fields for the owner."""
        analysis = self._make_detail_analysis()
        mock_service = AsyncMock()
        mock_service.get_analysis_detail.return_value = analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis.id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(analysis.id)
        assert body["status"] == "completed"
        assert body["exercise_type"] == "squat"
        assert body["exercise_variant"] == "high_bar"
        assert "confidence_score" in body
        assert "created_at" in body
        assert "updated_at" in body

    def test_get_detail_includes_tags(self):
        """GET /analyses/{id} response includes the tags list."""
        analysis = self._make_detail_analysis()
        analysis.tags = ["pr", "competition"]
        mock_service = AsyncMock()
        mock_service.get_analysis_detail.return_value = analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis.id}")

        assert resp.status_code == 200
        assert resp.json()["tags"] == ["pr", "competition"]

    def test_get_detail_wrong_user_returns_403(self):
        """GET /analyses/{id} for an analysis owned by another user returns 403."""
        analysis_id = uuid.uuid4()
        mock_service = AsyncMock()
        from fastapi import HTTPException as _HTTPException
        mock_service.get_analysis_detail.side_effect = _HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You do not own this analysis.",
                    "detail": None,
                }
            },
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis_id}")

        assert resp.status_code == 403

    def test_get_detail_not_found_returns_404(self):
        """GET /analyses/{id} for a non-existent ID returns 404."""
        analysis_id = uuid.uuid4()
        mock_service = AsyncMock()
        from fastapi import HTTPException as _HTTPException
        mock_service.get_analysis_detail.side_effect = _HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "ANALYSIS_NOT_FOUND",
                    "message": "Analysis not found.",
                    "detail": None,
                }
            },
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis_id}")

        assert resp.status_code == 404

    def test_get_detail_invalid_uuid_returns_422(self, app_client: TestClient):
        """GET /analyses/not-a-uuid returns 422 (FastAPI path validation)."""
        resp = app_client.get("/api/v1/analyses/not-a-uuid")
        assert resp.status_code == 422

    def test_get_detail_unauthenticated_returns_401(self):
        """GET /analyses/{id} without a JWT returns 401."""
        bare_app = FastAPI()
        bare_app.include_router(router, prefix="/api/v1/analyses")
        client = TestClient(bare_app, raise_server_exceptions=False)

        resp = client.get(f"/api/v1/analyses/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_get_detail_nested_coaching_result_present(self):
        """When a coaching result is attached, it appears in the response."""
        analysis = self._make_detail_analysis()
        coaching_mock = MagicMock()
        coaching_mock.structured_output_json = {"summary": "Good form overall."}
        coaching_mock.created_at = datetime.now(timezone.utc)
        analysis.coaching_result = coaching_mock

        mock_service = AsyncMock()
        mock_service.get_analysis_detail.return_value = analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis.id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["coaching_result"] is not None
        assert body["coaching_result"]["structured_output_json"]["summary"] == "Good form overall."

    def test_get_detail_rep_metrics_list(self):
        """Rep metrics nested list is serialised correctly (may be empty)."""
        analysis = self._make_detail_analysis()
        analysis.rep_metrics = []  # empty list is valid

        mock_service = AsyncMock()
        mock_service.get_analysis_detail.return_value = analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis.id}")

        assert resp.status_code == 200
        assert resp.json()["rep_metrics"] == []


# ---------------------------------------------------------------------------
# GET /api/v1/analyses/{id}/status — status poll (B-087)
# ---------------------------------------------------------------------------


class TestGetAnalysisStatus:
    """Tests for GET /api/v1/analyses/{id}/status endpoint."""

    def _make_status_analysis(self, status="processing"):
        obj = _make_mock_analysis(status=status)
        obj.detection_result = None
        return obj

    def test_get_status_returns_200_with_status_fields(self):
        """GET /analyses/{id}/status returns 200 with id, status, updated_at."""
        analysis = self._make_status_analysis(status="processing")
        mock_service = AsyncMock()
        mock_service.get_analysis_status.return_value = analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis.id}/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(analysis.id)
        assert body["status"] == "processing"
        assert "updated_at" in body

    def test_get_status_returns_all_valid_statuses(self):
        """Status endpoint can return any of the 7 valid status values."""
        valid_statuses = [
            "queued",
            "quality_gate_pending",
            "quality_gate_rejected",
            "processing",
            "coaching",
            "completed",
            "failed",
        ]
        for s in valid_statuses:
            analysis = self._make_status_analysis(status=s)
            mock_service = AsyncMock()
            mock_service.get_analysis_status.return_value = analysis

            client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
            resp = client.get(f"/api/v1/analyses/{analysis.id}/status")

            assert resp.status_code == 200, f"Expected 200 for status={s}"
            assert resp.json()["status"] == s

    def test_get_status_wrong_user_returns_403(self):
        """GET /analyses/{id}/status for another user's analysis returns 403."""
        analysis_id = uuid.uuid4()
        mock_service = AsyncMock()
        from fastapi import HTTPException as _HTTPException
        mock_service.get_analysis_status.side_effect = _HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You do not own this analysis.",
                    "detail": None,
                }
            },
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis_id}/status")

        assert resp.status_code == 403

    def test_get_status_not_found_returns_404(self):
        """GET /analyses/{id}/status for non-existent ID returns 404."""
        analysis_id = uuid.uuid4()
        mock_service = AsyncMock()
        from fastapi import HTTPException as _HTTPException
        mock_service.get_analysis_status.side_effect = _HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "ANALYSIS_NOT_FOUND",
                    "message": "Analysis not found.",
                    "detail": None,
                }
            },
        )

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis_id}/status")

        assert resp.status_code == 404

    def test_get_status_invalid_uuid_returns_422(self, app_client: TestClient):
        """GET /analyses/bad-id/status returns 422."""
        resp = app_client.get("/api/v1/analyses/not-a-uuid/status")
        assert resp.status_code == 422

    def test_get_status_unauthenticated_returns_401(self):
        """GET /analyses/{id}/status without token returns 401."""
        bare_app = FastAPI()
        bare_app.include_router(router, prefix="/api/v1/analyses")
        client = TestClient(bare_app, raise_server_exceptions=False)

        resp = client.get(f"/api/v1/analyses/{uuid.uuid4()}/status")
        assert resp.status_code == 401

    def test_get_status_response_has_no_extra_fields(self):
        """
        The status endpoint returns only id, status, updated_at — no video paths,
        no coaching results, no rep metrics. Verify the response is minimal.
        """
        analysis = self._make_status_analysis(status="completed")
        mock_service = AsyncMock()
        mock_service.get_analysis_status.return_value = analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis.id}/status")

        assert resp.status_code == 200
        body = resp.json()
        # Only the three AnalysisStatusResponse fields should be present
        assert set(body.keys()) == {"id", "status", "updated_at", "detection_result"}

    def test_get_status_includes_detection_result(self):
        """Status response exposes detection_result when set (FR-XDET-07)."""
        analysis = self._make_status_analysis(status="processing")
        analysis.detection_result = {
            "detected_type": "squat",
            "detected_variant": "high_bar",
            "confidence": 0.87,
            "method": "heuristic",
            "details": {"scores": {"squat": 0.87, "bench": 0.08, "deadlift": 0.05}},
        }
        mock_service = AsyncMock()
        mock_service.get_analysis_status.return_value = analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis.id}/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["detection_result"]["detected_type"] == "squat"
        assert body["detection_result"]["detected_variant"] == "high_bar"
        assert body["detection_result"]["confidence"] == 0.87
        assert body["detection_result"]["method"] == "heuristic"

    def test_get_status_detection_result_null_when_unset(self):
        """detection_result is null when not yet populated."""
        analysis = self._make_status_analysis(status="queued")
        # detection_result already None from factory
        mock_service = AsyncMock()
        mock_service.get_analysis_status.return_value = analysis

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis.id}/status")

        assert resp.status_code == 200
        assert resp.json()["detection_result"] is None
