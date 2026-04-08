"""Account service — destructive account deletion.

Cascade-deletes all user data and Storage artifacts, then removes the
user_profiles row. The Supabase auth.users row is NOT touched here —
that is handled by Supabase Auth separately (no DDL FK to auth.users).

Requirements: FR-AUTH-07, FR-XPRT-05, NFR-SECU-08
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.repositories.analysis import AnalysisRepository
from app.repositories.user_profile import UserProfileRepository
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

# Fetch all analyses in a single page; 1000 is a safe upper bound for a
# free-tier account (rate-limited to 10 uploads/day → years of data).
_MAX_ANALYSES = 1000


class AccountService:
    """Business logic for full account deletion.

    Parameters
    ----------
    repo:
        An ``AnalysisRepository`` instance (injected by FastAPI DI).
    profile_repo:
        A ``UserProfileRepository`` instance (injected by FastAPI DI).
    storage:
        A ``StorageService`` instance (injected by FastAPI DI).
    """

    def __init__(
        self,
        repo: AnalysisRepository,
        profile_repo: UserProfileRepository,
        storage: StorageService,
    ) -> None:
        self._repo = repo
        self._profile_repo = profile_repo
        self._storage = storage

    async def delete_account(self, user_id: UUID) -> None:
        """Delete all user data, Storage artifacts, and profile.

        Steps:
        1. Fetch all analyses for user (up to _MAX_ANALYSES).
        2. For each analysis, delete Storage artifacts (errors logged, not raised).
        3. Delete each analysis row (ORM cascade removes rep_metrics and
           coaching_results via SQLAlchemy relationship cascade).
        4. Delete user_profiles row if present.

        The auth.users row is intentionally NOT touched.
        """
        # --- 1. Fetch all analyses ---
        analyses = await self._repo.get_by_user(
            user_id, limit=_MAX_ANALYSES, offset=0
        )

        # --- 2 & 3. Delete artifacts then DB row for each analysis ---
        for analysis in analyses:
            artifact_paths = [
                analysis.video_path,
                analysis.annotated_video_path,
                analysis.plot_path,
                analysis.pdf_path,
            ]
            for path in artifact_paths:
                if path is not None:
                    try:
                        await self._storage.delete_file(path)
                    except Exception:
                        logger.warning(
                            "Failed to delete Storage artifact during account deletion "
                            "(user_id=%s, path=%s) — continuing.",
                            user_id,
                            path,
                        )

            await self._repo.delete(analysis.id)

        # --- 4. Delete user profile ---
        profile = await self._profile_repo.get_by_user_id(user_id)
        if profile is not None:
            await self._profile_repo.delete(profile.id)

        logger.info("Account deletion completed for user_id=%s", user_id)
