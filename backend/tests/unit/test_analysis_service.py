"""Unit tests for AnalysisService (B-009).

TDD gate:
- create_analysis with valid exercise/variant → Analysis ORM object, status=queued
- create_analysis with invalid exercise type → ValueError
- create_analysis with invalid variant for exercise → ValueError
- create_analysis with file_size_bytes > 50MB → ValueError
- create_analysis with file_size_bytes <= 0 → ValueError
- start_analysis on owned queued analysis → transitions status to quality_gate_pending
- start_analysis on non-existent analysis → raises 404 HTTPException
- start_analysis on wrong user → raises 403 HTTPException
- start_analysis on non-queued status → raises 409 HTTPException

Requirements: FR-UPLD-07, FR-UPLD-16, FR-UPLD-17
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.analysis import AnalysisService


MAX_FILE_SIZE = 52_428_800  # 50 MB


def _make_mock_repo(analysis=None):
    """Return a mock AnalysisRepository."""
    repo = AsyncMock()
    if analysis is not None:
        repo.get_by_id.return_value = analysis
        repo.update_status.return_value = analysis
    else:
        repo.get_by_id.return_value = None
        repo.update_status.return_value = None
    repo.create.side_effect = lambda a: a
    return repo


def _make_mock_analysis(
    user_id=None,
    status="queued",
    exercise_type="squat",
    exercise_variant="high_bar",
):
    """Return a mock Analysis ORM object."""
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.user_id = user_id or uuid.uuid4()
    obj.status = status
    obj.exercise_type = exercise_type
    obj.exercise_variant = exercise_variant
    obj.retry_count = 0
    obj.video_path = None
    obj.created_at = datetime.now(timezone.utc)
    obj.updated_at = datetime.now(timezone.utc)
    return obj


# ---------------------------------------------------------------------------
# create_analysis
# ---------------------------------------------------------------------------


class TestCreateAnalysis:
    @pytest.mark.asyncio
    async def test_valid_squat_high_bar(self):
        user_id = uuid.uuid4()
        repo = _make_mock_repo()

        analysis_obj = _make_mock_analysis(user_id=user_id)
        repo.create.return_value = analysis_obj

        mock_storage = AsyncMock()
        mock_storage.generate_signed_upload_url.return_value = {
            "url": "https://storage.example.com/upload/signed?token=abc",
            "expires_at": datetime.now(timezone.utc),
        }

        service = AnalysisService(repo=repo, storage=mock_storage)
        result = await service.create_analysis(
            user_id=user_id,
            exercise_type="squat",
            exercise_variant="high_bar",
            filename="squat.mp4",
            file_size_bytes=10_000_000,
        )

        assert result.analysis is not None
        assert result.upload_url.startswith("https://")
        repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_video_path_contains_real_uuid_not_string_none(self):
        """Regression: AnalysisService.create_analysis must populate
        video_path with the actual analysis UUID, not the literal string
        ``"None"``.

        Production bug: SQLAlchemy ``default=gen_uuid`` runs at INSERT
        time (flush), not at object construction. The original code did
        ``analysis.video_path = get_storage_path(analysis.id, filename)``
        BEFORE the flush, when ``analysis.id`` was still None — so the
        f-string formatted ``f"videos/{None}/{filename}"`` and stored
        ``"videos/None/squat-high-bar.mp4"``. The signed upload URL
        handed back to the browser used the post-flush UUID (correct),
        but the database row stored the literal "None" path. Worker
        download then 404'd because the actual file in Storage is at
        ``videos/<real-uuid>/...``, not ``videos/None/...``.
        """
        from uuid import UUID

        # Capture whatever Analysis instance the repo.create call receives,
        # so we can inspect its video_path attribute AFTER the service
        # has built it. We use side_effect to capture + return.
        captured: dict = {}

        async def fake_create(analysis):
            captured["analysis"] = analysis
            return analysis

        user_id = uuid.uuid4()
        repo = _make_mock_repo()
        repo.create.side_effect = fake_create

        mock_storage = AsyncMock()
        mock_storage.generate_signed_upload_url.return_value = {
            "url": "https://storage.example.com/upload/signed?token=abc",
            "expires_at": datetime.now(timezone.utc),
        }

        service = AnalysisService(repo=repo, storage=mock_storage)
        await service.create_analysis(
            user_id=user_id,
            exercise_type="squat",
            exercise_variant="high_bar",
            filename="squat-high-bar.mp4",
            file_size_bytes=10_000_000,
        )

        a = captured["analysis"]
        # The crucial assertion — video_path MUST contain a parseable
        # UUID where the analysis ID belongs, NOT the literal "None".
        assert a.video_path is not None
        assert "None" not in a.video_path, (
            f"video_path contains literal 'None' (Bug C): {a.video_path!r}"
        )
        # The path should be of the form "videos/{uuid}/{filename}".
        # Parse the UUID component and verify it's a real UUID.
        parts = a.video_path.split("/")
        assert len(parts) == 3, f"unexpected video_path shape: {a.video_path!r}"
        assert parts[0] == "videos"
        assert parts[2] == "squat-high-bar.mp4"
        # This must NOT raise — the middle component must be a valid UUID
        UUID(parts[1])
        assert UUID(parts[1]) == a.id

    @pytest.mark.asyncio
    async def test_valid_bench_flat(self):
        user_id = uuid.uuid4()
        repo = _make_mock_repo()
        analysis_obj = _make_mock_analysis(
            user_id=user_id, exercise_type="bench", exercise_variant="flat"
        )
        repo.create.return_value = analysis_obj

        mock_storage = AsyncMock()
        mock_storage.generate_signed_upload_url.return_value = {
            "url": "https://storage.example.com/upload/signed?token=xyz",
            "expires_at": datetime.now(timezone.utc),
        }

        service = AnalysisService(repo=repo, storage=mock_storage)
        result = await service.create_analysis(
            user_id=user_id,
            exercise_type="bench",
            exercise_variant="flat",
            filename="bench.mp4",
            file_size_bytes=5_000_000,
        )

        assert result.analysis is not None

    @pytest.mark.asyncio
    async def test_valid_deadlift_conventional(self):
        user_id = uuid.uuid4()
        repo = _make_mock_repo()
        analysis_obj = _make_mock_analysis(
            user_id=user_id, exercise_type="deadlift", exercise_variant="conventional"
        )
        repo.create.return_value = analysis_obj

        mock_storage = AsyncMock()
        mock_storage.generate_signed_upload_url.return_value = {
            "url": "https://storage.example.com/upload",
            "expires_at": datetime.now(timezone.utc),
        }

        service = AnalysisService(repo=repo, storage=mock_storage)
        result = await service.create_analysis(
            user_id=user_id,
            exercise_type="deadlift",
            exercise_variant="conventional",
            filename="dl.mp4",
            file_size_bytes=20_000_000,
        )

        assert result.analysis is not None

    @pytest.mark.asyncio
    async def test_invalid_exercise_type_raises_400(self):
        user_id = uuid.uuid4()
        repo = _make_mock_repo()
        mock_storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=mock_storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_analysis(
                user_id=user_id,
                exercise_type="lunges",
                exercise_variant="high_bar",
                filename="lunges.mp4",
                file_size_bytes=1_000_000,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_variant_for_exercise_raises_400(self):
        user_id = uuid.uuid4()
        repo = _make_mock_repo()
        mock_storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=mock_storage)

        # "high_bar" is squat, not bench
        with pytest.raises(HTTPException) as exc_info:
            await service.create_analysis(
                user_id=user_id,
                exercise_type="bench",
                exercise_variant="high_bar",
                filename="bench.mp4",
                file_size_bytes=1_000_000,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_file_too_large_raises_413(self):
        user_id = uuid.uuid4()
        repo = _make_mock_repo()
        mock_storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=mock_storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_analysis(
                user_id=user_id,
                exercise_type="squat",
                exercise_variant="high_bar",
                filename="huge.mp4",
                file_size_bytes=MAX_FILE_SIZE + 1,
            )
        assert exc_info.value.status_code == 413  # noqa: PLR2004

    @pytest.mark.asyncio
    async def test_file_size_at_limit_accepted(self):
        user_id = uuid.uuid4()
        repo = _make_mock_repo()
        analysis_obj = _make_mock_analysis(user_id=user_id)
        repo.create.return_value = analysis_obj

        mock_storage = AsyncMock()
        mock_storage.generate_signed_upload_url.return_value = {
            "url": "https://storage.example.com/upload",
            "expires_at": datetime.now(timezone.utc),
        }

        service = AnalysisService(repo=repo, storage=mock_storage)
        result = await service.create_analysis(
            user_id=user_id,
            exercise_type="squat",
            exercise_variant="high_bar",
            filename="ok.mp4",
            file_size_bytes=MAX_FILE_SIZE,
        )
        assert result.analysis is not None

    @pytest.mark.asyncio
    async def test_file_size_zero_raises_400(self):
        user_id = uuid.uuid4()
        repo = _make_mock_repo()
        mock_storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=mock_storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_analysis(
                user_id=user_id,
                exercise_type="squat",
                exercise_variant="high_bar",
                filename="empty.mp4",
                file_size_bytes=0,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_file_size_negative_raises_400(self):
        user_id = uuid.uuid4()
        repo = _make_mock_repo()
        mock_storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=mock_storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_analysis(
                user_id=user_id,
                exercise_type="squat",
                exercise_variant="high_bar",
                filename="negative.mp4",
                file_size_bytes=-100,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_creates_analysis_with_queued_status(self):
        """Analysis is created with status=queued via the transition guard."""
        user_id = uuid.uuid4()
        repo = _make_mock_repo()

        created_analysis = None

        async def capture_create(analysis):
            nonlocal created_analysis
            created_analysis = analysis
            return analysis

        repo.create.side_effect = capture_create

        mock_storage = AsyncMock()
        mock_storage.generate_signed_upload_url.return_value = {
            "url": "https://storage.example.com/upload",
            "expires_at": datetime.now(timezone.utc),
        }

        service = AnalysisService(repo=repo, storage=mock_storage)
        await service.create_analysis(
            user_id=user_id,
            exercise_type="squat",
            exercise_variant="low_bar",
            filename="test.mp4",
            file_size_bytes=5_000_000,
        )

        assert created_analysis is not None
        assert created_analysis.status == "queued"
        assert created_analysis.user_id == user_id

    @pytest.mark.asyncio
    async def test_video_path_stored_on_analysis(self):
        """video_path is set to videos/{analysis_id}/{filename}."""
        user_id = uuid.uuid4()
        repo = _make_mock_repo()

        created_analysis = None

        async def capture_create(analysis):
            nonlocal created_analysis
            created_analysis = analysis
            return analysis

        repo.create.side_effect = capture_create

        mock_storage = AsyncMock()
        mock_storage.generate_signed_upload_url.return_value = {
            "url": "https://storage.example.com/upload",
            "expires_at": datetime.now(timezone.utc),
        }

        service = AnalysisService(repo=repo, storage=mock_storage)
        await service.create_analysis(
            user_id=user_id,
            exercise_type="deadlift",
            exercise_variant="sumo",
            filename="sumo.mp4",
            file_size_bytes=8_000_000,
        )

        analysis_id = created_analysis.id
        expected_path = f"videos/{analysis_id}/sumo.mp4"
        assert created_analysis.video_path == expected_path


# ---------------------------------------------------------------------------
# start_analysis
# ---------------------------------------------------------------------------


class TestStartAnalysis:
    @pytest.mark.asyncio
    async def test_start_valid_owned_queued_analysis(self):
        user_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=user_id, status="queued")
        repo = _make_mock_repo(analysis=analysis)

        updated_analysis = _make_mock_analysis(
            user_id=user_id, status="quality_gate_pending"
        )
        updated_analysis.id = analysis.id
        repo.update_status.return_value = updated_analysis

        mock_arq = AsyncMock()
        mock_storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=mock_storage, arq_pool=mock_arq)

        result = await service.start_analysis(
            analysis_id=analysis.id, user_id=user_id
        )

        assert result.status == "quality_gate_pending"
        mock_arq.enqueue_job.assert_called_once_with(
            "process_analysis", analysis_id=analysis.id
        )

    @pytest.mark.asyncio
    async def test_start_nonexistent_raises_404(self):
        user_id = uuid.uuid4()
        repo = _make_mock_repo(analysis=None)
        mock_storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=mock_storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.start_analysis(
                analysis_id=uuid.uuid4(), user_id=user_id
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_start_wrong_user_raises_403(self):
        owner_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=owner_id, status="queued")
        repo = _make_mock_repo(analysis=analysis)
        mock_storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=mock_storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.start_analysis(
                analysis_id=analysis.id, user_id=other_user_id
            )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_start_non_queued_status_raises_409(self):
        user_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=user_id, status="processing")
        repo = _make_mock_repo(analysis=analysis)
        mock_storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=mock_storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.start_analysis(
                analysis_id=analysis.id, user_id=user_id
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_start_already_started_quality_gate_pending_raises_409(self):
        user_id = uuid.uuid4()
        analysis = _make_mock_analysis(
            user_id=user_id, status="quality_gate_pending"
        )
        repo = _make_mock_repo(analysis=analysis)
        mock_storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=mock_storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.start_analysis(
                analysis_id=analysis.id, user_id=user_id
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_start_completed_analysis_raises_409(self):
        user_id = uuid.uuid4()
        analysis = _make_mock_analysis(user_id=user_id, status="completed")
        repo = _make_mock_repo(analysis=analysis)
        mock_storage = AsyncMock()
        service = AnalysisService(repo=repo, storage=mock_storage)

        with pytest.raises(HTTPException) as exc_info:
            await service.start_analysis(
                analysis_id=analysis.id, user_id=user_id
            )
        assert exc_info.value.status_code == 409
