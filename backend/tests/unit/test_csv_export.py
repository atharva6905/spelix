"""Unit tests for CSV export endpoint (B-036).

Tests cover:
- GET /api/v1/analyses/{id}/export/csv returns 200 with text/csv content type
- CSV has correct headers
- CSV has correct data rows from rep_metrics
- metrics_json fields are flattened into columns
- 404 for non-existent analysis
- 403 for analysis not owned by user
- Empty rep_metrics → CSV with headers only

Requirements: FR-XPRT-04, NFR-SECU-07 (GDPR Article 20)
"""

import csv
import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.exports import router
from app.models.analysis import Analysis
from app.models.rep_metric import RepMetric


TEST_USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
TEST_ANALYSIS_ID = uuid.uuid4()
TEST_EMAIL = "test@example.com"
NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_analysis(user_id=None, **kwargs) -> Analysis:
    a = Analysis(
        user_id=user_id or TEST_USER_ID,
        exercise_type=kwargs.get("exercise_type", "squat"),
        exercise_variant=kwargs.get("exercise_variant", "low_bar"),
        status="completed",
    )
    a.__dict__.update(
        {
            "id": kwargs.get("id", TEST_ANALYSIS_ID),
            "created_at": kwargs.get("created_at", NOW),
            "updated_at": kwargs.get("updated_at", NOW),
            "confidence_score": kwargs.get("confidence_score", 0.92),
        }
    )
    return a


def _make_rep_metric(analysis_id=None, rep_index=1, metrics_json=None, **kwargs) -> RepMetric:
    rm = RepMetric(
        analysis_id=analysis_id or TEST_ANALYSIS_ID,
        rep_index=rep_index,
        start_frame=kwargs.get("start_frame", 0),
        end_frame=kwargs.get("end_frame", 60),
        confidence_score=kwargs.get("confidence_score", 0.90),
    )
    rm.__dict__.update(
        {
            "id": uuid.uuid4(),
            "metrics_json": metrics_json or {"hip_angle_min": 80.5, "knee_angle_min": 85.2},
        }
    )
    return rm


@pytest.fixture()
def app_client():
    """Return a TestClient with auth dependency overridden."""
    from app.api.deps import get_current_user

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/analyses")

    async def _mock_user():
        return {"id": TEST_USER_ID, "email": TEST_EMAIL, "role": "user"}

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /api/v1/analyses/{id}/export/csv — success cases
# ---------------------------------------------------------------------------


class TestExportCsvSuccess:
    def test_returns_200_with_csv_content_type(self, app_client: TestClient):
        analysis = _make_analysis()
        rep = _make_rep_metric()
        analysis.rep_metrics = [rep]

        with patch("app.api.v1.exports.ExportService") as MockService:
            instance = AsyncMock()
            instance.generate_csv.return_value = (
                "exercise_type,exercise_variant,created_at,confidence_score,"
                "rep_index,start_frame,end_frame,rep_confidence_score,hip_angle_min,knee_angle_min\r\n"
                "squat,low_bar,2024-01-15T12:00:00+00:00,0.92,"
                "1,0,60,0.9,80.5,85.2\r\n"
            )
            MockService.return_value = instance

            resp = app_client.get(f"/api/v1/analyses/{TEST_ANALYSIS_ID}/export/csv")

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_content_disposition_filename(self, app_client: TestClient):
        with patch("app.api.v1.exports.ExportService") as MockService:
            instance = AsyncMock()
            instance.generate_csv.return_value = "exercise_type\r\nsquat\r\n"
            MockService.return_value = instance

            resp = app_client.get(f"/api/v1/analyses/{TEST_ANALYSIS_ID}/export/csv")

        assert resp.status_code == 200
        content_disposition = resp.headers.get("content-disposition", "")
        assert f"analysis_{TEST_ANALYSIS_ID}.csv" in content_disposition
        assert "attachment" in content_disposition

    def test_csv_has_correct_headers(self, app_client: TestClient):
        with patch("app.api.v1.exports.ExportService") as MockService:
            instance = AsyncMock()
            # Generate a real CSV with expected headers
            buf = io.StringIO()
            writer = csv.DictWriter(
                buf,
                fieldnames=[
                    "exercise_type", "exercise_variant", "created_at", "confidence_score",
                    "rep_index", "start_frame", "end_frame", "rep_confidence_score",
                    "hip_angle_min", "knee_angle_min",
                ],
            )
            writer.writeheader()
            instance.generate_csv.return_value = buf.getvalue()
            MockService.return_value = instance

            resp = app_client.get(f"/api/v1/analyses/{TEST_ANALYSIS_ID}/export/csv")

        assert resp.status_code == 200
        reader = csv.DictReader(io.StringIO(resp.text))
        headers = reader.fieldnames or []
        assert "exercise_type" in headers
        assert "exercise_variant" in headers
        assert "created_at" in headers
        assert "confidence_score" in headers
        assert "rep_index" in headers
        assert "start_frame" in headers
        assert "end_frame" in headers
        assert "rep_confidence_score" in headers

    def test_csv_data_rows_from_rep_metrics(self, app_client: TestClient):
        with patch("app.api.v1.exports.ExportService") as MockService:
            instance = AsyncMock()
            buf = io.StringIO()
            writer = csv.DictWriter(
                buf,
                fieldnames=[
                    "exercise_type", "exercise_variant", "created_at", "confidence_score",
                    "rep_index", "start_frame", "end_frame", "rep_confidence_score",
                    "hip_angle_min",
                ],
            )
            writer.writeheader()
            writer.writerow({
                "exercise_type": "squat",
                "exercise_variant": "low_bar",
                "created_at": NOW.isoformat(),
                "confidence_score": 0.92,
                "rep_index": 1,
                "start_frame": 0,
                "end_frame": 60,
                "rep_confidence_score": 0.90,
                "hip_angle_min": 80.5,
            })
            writer.writerow({
                "exercise_type": "squat",
                "exercise_variant": "low_bar",
                "created_at": NOW.isoformat(),
                "confidence_score": 0.92,
                "rep_index": 2,
                "start_frame": 70,
                "end_frame": 130,
                "rep_confidence_score": 0.88,
                "hip_angle_min": 82.1,
            })
            instance.generate_csv.return_value = buf.getvalue()
            MockService.return_value = instance

            resp = app_client.get(f"/api/v1/analyses/{TEST_ANALYSIS_ID}/export/csv")

        assert resp.status_code == 200
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["rep_index"] == "1"
        assert rows[0]["start_frame"] == "0"
        assert rows[0]["end_frame"] == "60"
        assert rows[1]["rep_index"] == "2"

    def test_metrics_json_fields_flattened_into_columns(self, app_client: TestClient):
        with patch("app.api.v1.exports.ExportService") as MockService:
            instance = AsyncMock()
            buf = io.StringIO()
            writer = csv.DictWriter(
                buf,
                fieldnames=[
                    "exercise_type", "exercise_variant", "created_at", "confidence_score",
                    "rep_index", "start_frame", "end_frame", "rep_confidence_score",
                    "hip_angle_min", "knee_angle_min", "ankle_angle_min",
                ],
            )
            writer.writeheader()
            writer.writerow({
                "exercise_type": "squat",
                "exercise_variant": "low_bar",
                "created_at": NOW.isoformat(),
                "confidence_score": 0.92,
                "rep_index": 1,
                "start_frame": 0,
                "end_frame": 60,
                "rep_confidence_score": 0.90,
                "hip_angle_min": 80.5,
                "knee_angle_min": 85.2,
                "ankle_angle_min": 70.1,
            })
            instance.generate_csv.return_value = buf.getvalue()
            MockService.return_value = instance

            resp = app_client.get(f"/api/v1/analyses/{TEST_ANALYSIS_ID}/export/csv")

        assert resp.status_code == 200
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 1
        # All three metrics_json fields are flattened as columns
        assert "hip_angle_min" in reader.fieldnames
        assert "knee_angle_min" in reader.fieldnames
        assert "ankle_angle_min" in reader.fieldnames
        assert rows[0]["hip_angle_min"] == "80.5"
        assert rows[0]["knee_angle_min"] == "85.2"

    def test_empty_rep_metrics_returns_headers_only(self, app_client: TestClient):
        with patch("app.api.v1.exports.ExportService") as MockService:
            instance = AsyncMock()
            # Headers only — no data rows
            instance.generate_csv.return_value = (
                "exercise_type,exercise_variant,created_at,confidence_score,"
                "rep_index,start_frame,end_frame,rep_confidence_score\r\n"
            )
            MockService.return_value = instance

            resp = app_client.get(f"/api/v1/analyses/{TEST_ANALYSIS_ID}/export/csv")

        assert resp.status_code == 200
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert rows == []
        # Headers must still be present
        assert reader.fieldnames is not None
        assert len(reader.fieldnames) > 0


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestExportCsvErrors:
    def test_404_for_nonexistent_analysis(self, app_client: TestClient):
        nonexistent_id = uuid.uuid4()

        with patch("app.api.v1.exports.ExportService") as MockService:
            from fastapi import HTTPException

            instance = AsyncMock()
            instance.generate_csv.side_effect = HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "ANALYSIS_NOT_FOUND",
                        "message": "Analysis not found.",
                        "detail": None,
                    }
                },
            )
            MockService.return_value = instance

            resp = app_client.get(f"/api/v1/analyses/{nonexistent_id}/export/csv")

        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "ANALYSIS_NOT_FOUND"

    def test_403_for_analysis_not_owned_by_user(self, app_client: TestClient):
        with patch("app.api.v1.exports.ExportService") as MockService:
            from fastapi import HTTPException

            instance = AsyncMock()
            instance.generate_csv.side_effect = HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not have access to this analysis.",
                        "detail": None,
                    }
                },
            )
            MockService.return_value = instance

            resp = app_client.get(f"/api/v1/analyses/{TEST_ANALYSIS_ID}/export/csv")

        assert resp.status_code == 403
        assert resp.json()["detail"]["error"]["code"] == "FORBIDDEN"

    def test_unauthenticated_returns_401(self):
        """Without the auth override the bearer scheme returns 403 (no token)."""

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/analyses")
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(f"/api/v1/analyses/{TEST_ANALYSIS_ID}/export/csv")
        # FastAPI HTTPBearer returns 403 when Authorization header is absent
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# ExportService unit tests (pure logic — no HTTP layer)
# ---------------------------------------------------------------------------


class TestExportServiceGenerateCsv:
    """Test ExportService.generate_csv directly with mocked repository."""

    @pytest.mark.asyncio
    async def test_generate_csv_returns_string(self):
        from app.services.export import ExportService

        analysis = _make_analysis()
        rep1 = _make_rep_metric(rep_index=1, metrics_json={"hip_angle_min": 80.5})
        analysis.rep_metrics = [rep1]

        repo = AsyncMock()
        repo.get_by_id.return_value = analysis

        service = ExportService(repo)
        result = await service.generate_csv(TEST_ANALYSIS_ID, TEST_USER_ID)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_csv_raises_404_for_missing_analysis(self):
        from fastapi import HTTPException

        from app.services.export import ExportService

        repo = AsyncMock()
        repo.get_by_id.return_value = None

        service = ExportService(repo)
        with pytest.raises(HTTPException) as exc_info:
            await service.generate_csv(uuid.uuid4(), TEST_USER_ID)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"]["code"] == "ANALYSIS_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_generate_csv_raises_403_for_wrong_owner(self):
        from fastapi import HTTPException

        from app.services.export import ExportService

        analysis = _make_analysis(user_id=OTHER_USER_ID)
        analysis.rep_metrics = []

        repo = AsyncMock()
        repo.get_by_id.return_value = analysis

        service = ExportService(repo)
        with pytest.raises(HTTPException) as exc_info:
            await service.generate_csv(TEST_ANALYSIS_ID, TEST_USER_ID)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"]["code"] == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_generate_csv_correct_metadata_columns(self):
        from app.services.export import ExportService

        analysis = _make_analysis()
        analysis.rep_metrics = []

        repo = AsyncMock()
        repo.get_by_id.return_value = analysis

        service = ExportService(repo)
        csv_content = await service.generate_csv(TEST_ANALYSIS_ID, TEST_USER_ID)

        reader = csv.DictReader(io.StringIO(csv_content))
        headers = reader.fieldnames or []
        assert "exercise_type" in headers
        assert "exercise_variant" in headers
        assert "created_at" in headers
        assert "confidence_score" in headers

    @pytest.mark.asyncio
    async def test_generate_csv_correct_rep_columns(self):
        from app.services.export import ExportService

        analysis = _make_analysis()
        rep = _make_rep_metric(rep_index=1, metrics_json={"hip_angle_min": 80.5, "knee_angle_min": 85.2})
        analysis.rep_metrics = [rep]

        repo = AsyncMock()
        repo.get_by_id.return_value = analysis

        service = ExportService(repo)
        csv_content = await service.generate_csv(TEST_ANALYSIS_ID, TEST_USER_ID)

        reader = csv.DictReader(io.StringIO(csv_content))
        headers = reader.fieldnames or []
        assert "rep_index" in headers
        assert "start_frame" in headers
        assert "end_frame" in headers
        assert "rep_confidence_score" in headers
        assert "hip_angle_min" in headers
        assert "knee_angle_min" in headers

    @pytest.mark.asyncio
    async def test_generate_csv_flattens_metrics_json(self):
        from app.services.export import ExportService

        analysis = _make_analysis()
        rep = _make_rep_metric(
            rep_index=1,
            metrics_json={"hip_angle_min": 80.5, "knee_angle_min": 85.2, "ankle_dorsiflexion": 22.0},
        )
        analysis.rep_metrics = [rep]

        repo = AsyncMock()
        repo.get_by_id.return_value = analysis

        service = ExportService(repo)
        csv_content = await service.generate_csv(TEST_ANALYSIS_ID, TEST_USER_ID)

        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["hip_angle_min"] == "80.5"
        assert rows[0]["knee_angle_min"] == "85.2"
        assert rows[0]["ankle_dorsiflexion"] == "22.0"

    @pytest.mark.asyncio
    async def test_generate_csv_empty_reps_headers_only(self):
        from app.services.export import ExportService

        analysis = _make_analysis()
        analysis.rep_metrics = []

        repo = AsyncMock()
        repo.get_by_id.return_value = analysis

        service = ExportService(repo)
        csv_content = await service.generate_csv(TEST_ANALYSIS_ID, TEST_USER_ID)

        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        assert rows == []
        assert reader.fieldnames is not None

    @pytest.mark.asyncio
    async def test_generate_csv_multiple_reps_with_different_metrics(self):
        """All metrics_json keys across all reps become columns; missing values are empty."""
        from app.services.export import ExportService

        analysis = _make_analysis()
        rep1 = _make_rep_metric(rep_index=1, metrics_json={"hip_angle_min": 80.5, "knee_angle_min": 85.2})
        rep2 = _make_rep_metric(
            rep_index=2,
            start_frame=70,
            end_frame=130,
            confidence_score=0.88,
            metrics_json={"hip_angle_min": 82.0, "extra_metric": 5.0},
        )
        analysis.rep_metrics = [rep1, rep2]

        repo = AsyncMock()
        repo.get_by_id.return_value = analysis

        service = ExportService(repo)
        csv_content = await service.generate_csv(TEST_ANALYSIS_ID, TEST_USER_ID)

        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        assert len(rows) == 2
        # All metrics keys from all reps should be present as columns
        assert "hip_angle_min" in reader.fieldnames
        assert "knee_angle_min" in reader.fieldnames
        assert "extra_metric" in reader.fieldnames
        # rep2 doesn't have knee_angle_min — should be empty string
        assert rows[1]["knee_angle_min"] == ""
        # rep1 doesn't have extra_metric — should be empty string
        assert rows[0]["extra_metric"] == ""

    @pytest.mark.asyncio
    async def test_generate_csv_analysis_metadata_on_every_row(self):
        """Each rep row repeats the analysis-level metadata columns."""
        from app.services.export import ExportService

        analysis = _make_analysis()
        rep1 = _make_rep_metric(rep_index=1)
        rep2 = _make_rep_metric(rep_index=2, start_frame=70, end_frame=130, confidence_score=0.88)
        analysis.rep_metrics = [rep1, rep2]

        repo = AsyncMock()
        repo.get_by_id.return_value = analysis

        service = ExportService(repo)
        csv_content = await service.generate_csv(TEST_ANALYSIS_ID, TEST_USER_ID)

        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        assert len(rows) == 2
        for row in rows:
            assert row["exercise_type"] == "squat"
            assert row["exercise_variant"] == "low_bar"
            assert row["confidence_score"] == "0.92"
