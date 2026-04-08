"""Unit tests for AccountService — account deletion (B-037).

TDD Gate:
1. DELETE /api/v1/account returns 204
2. All analyses for the user are deleted
3. All Storage artifacts are cleaned up (mock storage calls verified)
4. User profile is deleted
5. Storage errors don't block deletion (graceful handling)
6. Auth required (401 without token)

Requirements: FR-AUTH-07, FR-XPRT-05, NFR-SECU-08
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.account import AccountService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_analysis(
    user_id: uuid.UUID,
    video_path: str | None = None,
    annotated_video_path: str | None = None,
    plot_path: str | None = None,
    pdf_path: str | None = None,
) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.user_id = user_id
    obj.video_path = video_path
    obj.annotated_video_path = annotated_video_path
    obj.plot_path = plot_path
    obj.pdf_path = pdf_path
    return obj


def _make_mock_profile(user_id: uuid.UUID) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.user_id = user_id
    return obj


def _make_mock_analysis_repo(analyses: list) -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_user.return_value = analyses
    repo.delete.return_value = None
    return repo


def _make_mock_profile_repo(profile=None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_user_id.return_value = profile
    repo.delete.return_value = None
    return repo


def _make_mock_storage() -> AsyncMock:
    storage = AsyncMock()
    storage.delete_file.return_value = None
    return storage


# ---------------------------------------------------------------------------
# AccountService unit tests
# ---------------------------------------------------------------------------


class TestAccountServiceDeleteAccount:
    @pytest.mark.asyncio
    async def test_deletes_all_analyses_for_user(self):
        """All analyses belonging to the user are deleted from DB."""
        user_id = uuid.uuid4()
        analysis1 = _make_mock_analysis(user_id)
        analysis2 = _make_mock_analysis(user_id)

        analysis_repo = _make_mock_analysis_repo([analysis1, analysis2])
        profile_repo = _make_mock_profile_repo()
        storage = _make_mock_storage()

        service = AccountService(
            repo=analysis_repo, profile_repo=profile_repo, storage=storage
        )
        await service.delete_account(user_id)

        analysis_repo.get_by_user.assert_called_once_with(user_id, limit=1000, offset=0)
        assert analysis_repo.delete.call_count == 2
        analysis_repo.delete.assert_any_call(analysis1.id)
        analysis_repo.delete.assert_any_call(analysis2.id)

    @pytest.mark.asyncio
    async def test_deletes_storage_artifacts_for_each_analysis(self):
        """All non-null artifact paths are deleted from Storage."""
        user_id = uuid.uuid4()
        analysis = _make_mock_analysis(
            user_id,
            video_path="videos/123/video.mp4",
            annotated_video_path="videos/123/annotated.mp4",
            plot_path="artifacts/123/plot.png",
            pdf_path="artifacts/123/report.pdf",
        )

        analysis_repo = _make_mock_analysis_repo([analysis])
        profile_repo = _make_mock_profile_repo()
        storage = _make_mock_storage()

        service = AccountService(
            repo=analysis_repo, profile_repo=profile_repo, storage=storage
        )
        await service.delete_account(user_id)

        assert storage.delete_file.call_count == 4
        storage.delete_file.assert_any_call("videos/123/video.mp4")
        storage.delete_file.assert_any_call("videos/123/annotated.mp4")
        storage.delete_file.assert_any_call("artifacts/123/plot.png")
        storage.delete_file.assert_any_call("artifacts/123/report.pdf")

    @pytest.mark.asyncio
    async def test_skips_null_artifact_paths(self):
        """Null artifact paths are silently skipped (not passed to storage)."""
        user_id = uuid.uuid4()
        analysis = _make_mock_analysis(
            user_id,
            video_path="videos/123/video.mp4",
            # all others None
        )

        analysis_repo = _make_mock_analysis_repo([analysis])
        profile_repo = _make_mock_profile_repo()
        storage = _make_mock_storage()

        service = AccountService(
            repo=analysis_repo, profile_repo=profile_repo, storage=storage
        )
        await service.delete_account(user_id)

        assert storage.delete_file.call_count == 1
        storage.delete_file.assert_called_once_with("videos/123/video.mp4")

    @pytest.mark.asyncio
    async def test_storage_errors_do_not_block_db_deletion(self):
        """Storage errors are swallowed — DB deletion still proceeds."""
        user_id = uuid.uuid4()
        analysis = _make_mock_analysis(
            user_id,
            video_path="videos/123/video.mp4",
            annotated_video_path="videos/123/annotated.mp4",
        )

        analysis_repo = _make_mock_analysis_repo([analysis])
        profile_repo = _make_mock_profile_repo()
        storage = _make_mock_storage()
        storage.delete_file.side_effect = Exception("Storage unavailable")

        service = AccountService(
            repo=analysis_repo, profile_repo=profile_repo, storage=storage
        )

        # Must not raise even though storage fails
        await service.delete_account(user_id)

        # DB delete was still called
        analysis_repo.delete.assert_called_once_with(analysis.id)

    @pytest.mark.asyncio
    async def test_deletes_user_profile(self):
        """User profile is deleted from DB after analyses are deleted."""
        user_id = uuid.uuid4()
        profile = _make_mock_profile(user_id)

        analysis_repo = _make_mock_analysis_repo([])
        profile_repo = _make_mock_profile_repo(profile=profile)
        storage = _make_mock_storage()

        service = AccountService(
            repo=analysis_repo, profile_repo=profile_repo, storage=storage
        )
        await service.delete_account(user_id)

        profile_repo.get_by_user_id.assert_called_once_with(user_id)
        profile_repo.delete.assert_called_once_with(profile.id)

    @pytest.mark.asyncio
    async def test_no_analyses_still_deletes_profile(self):
        """Works correctly when user has no analyses."""
        user_id = uuid.uuid4()
        profile = _make_mock_profile(user_id)

        analysis_repo = _make_mock_analysis_repo([])
        profile_repo = _make_mock_profile_repo(profile=profile)
        storage = _make_mock_storage()

        service = AccountService(
            repo=analysis_repo, profile_repo=profile_repo, storage=storage
        )
        await service.delete_account(user_id)

        analysis_repo.delete.assert_not_called()
        storage.delete_file.assert_not_called()
        profile_repo.delete.assert_called_once_with(profile.id)

    @pytest.mark.asyncio
    async def test_no_profile_does_not_raise(self):
        """Works correctly when user has no profile row (e.g. never completed setup)."""
        user_id = uuid.uuid4()

        analysis_repo = _make_mock_analysis_repo([])
        profile_repo = _make_mock_profile_repo(profile=None)
        storage = _make_mock_storage()

        service = AccountService(
            repo=analysis_repo, profile_repo=profile_repo, storage=storage
        )

        # Must not raise
        await service.delete_account(user_id)

        profile_repo.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_analyses_multiple_artifacts(self):
        """All artifacts across multiple analyses are cleaned up."""
        user_id = uuid.uuid4()
        analysis1 = _make_mock_analysis(
            user_id,
            video_path="videos/a1/v.mp4",
            plot_path="artifacts/a1/plot.png",
        )
        analysis2 = _make_mock_analysis(
            user_id,
            video_path="videos/a2/v.mp4",
            annotated_video_path="videos/a2/ann.mp4",
        )

        analysis_repo = _make_mock_analysis_repo([analysis1, analysis2])
        profile_repo = _make_mock_profile_repo()
        storage = _make_mock_storage()

        service = AccountService(
            repo=analysis_repo, profile_repo=profile_repo, storage=storage
        )
        await service.delete_account(user_id)

        # 2 artifacts for a1, 2 for a2 = 4 total
        assert storage.delete_file.call_count == 4
        assert analysis_repo.delete.call_count == 2


# ---------------------------------------------------------------------------
# API endpoint tests (using FastAPI TestClient with mocked service)
# ---------------------------------------------------------------------------


class TestDeleteAccountEndpoint:
    """Tests for DELETE /api/v1/account using FastAPI test client with mocked auth."""

    def _make_app_with_mock_service(self, service: AccountService):
        """Build a minimal FastAPI app with the account router and a mocked service."""

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.v1.account import router, _get_service

        test_app = FastAPI()
        test_app.include_router(router, prefix="/api/v1/account")
        test_app.dependency_overrides[_get_service] = lambda: service
        return TestClient(test_app)

    def _make_service_that_succeeds(self) -> AccountService:
        service = MagicMock(spec=AccountService)
        service.delete_account = AsyncMock(return_value=None)
        return service

    def test_returns_204_on_success(self):
        """DELETE /api/v1/account returns 204 No Content."""
        import os

        os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-for-unit-tests-only")

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.v1.account import router, _get_service
        from app.api.deps import get_current_user

        fake_user = {"id": uuid.uuid4(), "email": "test@example.com", "role": "user"}

        test_app = FastAPI()
        test_app.include_router(router, prefix="/api/v1/account")

        mock_service = self._make_service_that_succeeds()
        test_app.dependency_overrides[_get_service] = lambda: mock_service
        test_app.dependency_overrides[get_current_user] = lambda: fake_user

        client = TestClient(test_app)
        response = client.delete("/api/v1/account")

        assert response.status_code == 204

    def test_returns_401_without_auth_token(self):
        """DELETE /api/v1/account returns 401 when no auth token is provided."""
        import os

        os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-for-unit-tests-only")

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.v1.account import router, _get_service

        test_app = FastAPI()
        test_app.include_router(router, prefix="/api/v1/account")

        mock_service = self._make_service_that_succeeds()
        test_app.dependency_overrides[_get_service] = lambda: mock_service

        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.delete("/api/v1/account")

        assert response.status_code == 401
