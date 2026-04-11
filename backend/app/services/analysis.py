"""Analysis service — business logic for creating and starting analyses.

Two primary operations:
    create_analysis — validates request, creates DB row (status=queued),
                      generates a Supabase Storage signed upload URL.
    start_analysis  — validates ownership and status, enqueues the ARQ
                      worker job, transitions status to quality_gate_pending.

Requirements: FR-UPLD-07, FR-UPLD-16, FR-UPLD-17
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.models.analysis import Analysis
from app.models.base import gen_uuid
from app.repositories.analysis import AnalysisRepository
from app.services.status import InvalidTransition, transition
from app.services.storage import StorageService, get_storage_path

# ---------------------------------------------------------------------------
# Allowed exercise / variant combinations
# ---------------------------------------------------------------------------

_VALID_VARIANTS: dict[str, frozenset[str]] = {
    "squat": frozenset({"high_bar", "low_bar"}),
    "bench": frozenset({"flat", "incline", "decline"}),
    "deadlift": frozenset({"conventional", "sumo", "romanian"}),
}

MAX_FILE_SIZE_BYTES = 52_428_800  # 50 MB


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CreateAnalysisResult:
    analysis: Analysis
    upload_url: str
    expires_at: datetime


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AnalysisService:
    """Business logic for analysis creation and start.

    Parameters
    ----------
    repo:
        An ``AnalysisRepository`` instance (injected by FastAPI DI).
    storage:
        A ``StorageService`` instance (injected by FastAPI DI).
    arq_pool:
        An ARQ Redis pool used for enqueueing jobs.  May be ``None`` in
        contexts where ``start_analysis`` is not called (e.g. unit tests
        that only test ``create_analysis``).
    """

    def __init__(
        self,
        repo: AnalysisRepository,
        storage: StorageService,
        arq_pool: Any | None = None,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._arq_pool = arq_pool

    async def create_analysis(
        self,
        user_id: UUID,
        exercise_type: str,
        exercise_variant: str,
        filename: str,
        file_size_bytes: int,
    ) -> CreateAnalysisResult:
        """Create a new analysis record and return a signed upload URL.

        Validates:
        - exercise_type must be squat | bench | deadlift (400)
        - exercise_variant must match the exercise_type (400)
        - file_size_bytes must be > 0 (400)
        - file_size_bytes must be <= 50 MB (413)

        Creates the DB row with status="queued" via the transition guard,
        stores video_path = videos/{analysis_id}/{filename}.

        Returns a ``CreateAnalysisResult`` with the created analysis ORM
        object, a signed TUS upload URL, and its expiry timestamp.
        """
        # --- Validate file size ---
        if file_size_bytes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_FILE_SIZE",
                        "message": "file_size_bytes must be greater than 0.",
                        "detail": None,
                    }
                },
            )

        if file_size_bytes > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail={
                    "error": {
                        "code": "FILE_TOO_LARGE",
                        "message": "File exceeds the 50 MB limit.",
                        "detail": {"max_bytes": MAX_FILE_SIZE_BYTES},
                    }
                },
            )

        # --- Validate exercise type ---
        if exercise_type not in _VALID_VARIANTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_EXERCISE",
                        "message": (
                            f"Invalid exercise_type '{exercise_type}'. "
                            f"Must be one of: {sorted(_VALID_VARIANTS.keys())}."
                        ),
                        "detail": None,
                    }
                },
            )

        # --- Validate variant for exercise ---
        valid_variants = _VALID_VARIANTS[exercise_type]
        if exercise_variant not in valid_variants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_EXERCISE_VARIANT",
                        "message": (
                            f"Invalid exercise_variant '{exercise_variant}' for "
                            f"exercise_type '{exercise_type}'. "
                            f"Must be one of: {sorted(valid_variants)}."
                        ),
                        "detail": None,
                    }
                },
            )

        # --- Use transition guard to validate None → queued ---
        initial_status = transition(None, "queued")

        # --- Build the ORM object ---
        # IMPORTANT: pre-generate the UUID at construction time, NOT via the
        # ``default=gen_uuid`` model default. SQLAlchemy ``default=`` runs at
        # INSERT/flush time, NOT at object construction — so if we relied on
        # the model default, ``analysis.id`` would still be ``None`` here and
        # ``get_storage_path(analysis.id, filename)`` would format the literal
        # string "None" into the path. The DB row would store
        # ``"videos/None/<filename>"`` while the signed upload URL we hand
        # back to the browser would use the post-flush real UUID, leaving
        # the worker's later download attempt 404'ing on a path that doesn't
        # exist. Regression test:
        # ``test_analysis_service.py::TestCreateAnalysis::test_video_path_contains_real_uuid_not_string_none``.
        analysis = Analysis(
            id=gen_uuid(),
            user_id=user_id,
            status=initial_status,
            exercise_type=exercise_type,
            exercise_variant=exercise_variant,
        )

        analysis.video_path = get_storage_path(analysis.id, filename)

        # --- Persist ---
        analysis = await self._repo.create(analysis)

        # --- Generate signed upload URL ---
        signed = await self._storage.generate_signed_upload_url(
            analysis_id=analysis.id,
            filename=filename,
        )

        return CreateAnalysisResult(
            analysis=analysis,
            upload_url=signed["url"],
            expires_at=signed["expires_at"],
        )

    async def start_analysis(
        self,
        analysis_id: UUID,
        user_id: UUID,
    ) -> Analysis:
        """Enqueue an ARQ worker job and transition the analysis to quality_gate_pending.

        Validates:
        - analysis exists (404)
        - analysis is owned by user_id (403)
        - analysis is in status="queued" (409)

        On success, enqueues ``process_analysis`` ARQ job and transitions
        status to ``quality_gate_pending``.

        Returns the updated Analysis ORM object.
        """
        analysis = await self._repo.get_by_id(analysis_id)

        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ANALYSIS_NOT_FOUND",
                        "message": "Analysis not found.",
                        "detail": None,
                    }
                },
            )

        if analysis.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not own this analysis.",
                        "detail": None,
                    }
                },
            )

        # Validate the transition — only "queued" → "quality_gate_pending" is valid
        try:
            transition(analysis.status, "quality_gate_pending", analysis.retry_count)
        except InvalidTransition:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": (
                            f"Analysis cannot be started from status '{analysis.status}'. "
                            "Only queued analyses can be started."
                        ),
                        "detail": {"current_status": analysis.status},
                    }
                },
            )

        # Enqueue ARQ job before DB transition (idempotent on worker side)
        if self._arq_pool is not None:
            await self._arq_pool.enqueue_job(
                "process_analysis", analysis_id=analysis_id
            )

        # Transition status in DB
        updated = await self._repo.update_status(analysis_id, "quality_gate_pending")
        return updated

    # ---------------------------------------------------------------------------
    # CRUD methods (B-027, B-028, B-029)
    # ---------------------------------------------------------------------------

    async def get_analysis_status(
        self,
        analysis_id: UUID,
        user_id: UUID,
    ) -> Analysis:
        """Return the analysis for status polling (B-027, FR-RESL-13).

        Validates ownership and raises 404/403 as appropriate.
        """
        analysis = await self._repo.get_by_id(analysis_id)

        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ANALYSIS_NOT_FOUND",
                        "message": "Analysis not found.",
                        "detail": None,
                    }
                },
            )

        if analysis.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not own this analysis.",
                        "detail": None,
                    }
                },
            )

        return analysis

    async def get_analysis_detail(
        self,
        analysis_id: UUID,
        user_id: UUID,
    ) -> Analysis:
        """Return full analysis detail with eagerly loaded relationships (B-029).

        Validates ownership and raises 404/403 as appropriate.
        """
        analysis = await self._repo.get_by_id_with_relations(analysis_id)

        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ANALYSIS_NOT_FOUND",
                        "message": "Analysis not found.",
                        "detail": None,
                    }
                },
            )

        if analysis.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not own this analysis.",
                        "detail": None,
                    }
                },
            )

        return analysis

    async def list_analyses(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Analysis]:
        """Return analyses for a user in reverse chronological order (B-029, FR-HIST-01)."""
        return await self._repo.get_by_user(user_id, limit=limit, offset=offset)

    async def delete_analysis(
        self,
        analysis_id: UUID,
        user_id: UUID,
    ) -> None:
        """Delete an analysis and all its Storage artifacts (B-028, FR-UPLD-10-11).

        Validates ownership and raises 404/403 as appropriate.
        Deletes non-null artifact paths from Storage before removing the DB row.
        """
        analysis = await self._repo.get_by_id(analysis_id)

        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ANALYSIS_NOT_FOUND",
                        "message": "Analysis not found.",
                        "detail": None,
                    }
                },
            )

        if analysis.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not own this analysis.",
                        "detail": None,
                    }
                },
            )

        # Delete Storage artifacts for each non-null path
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
                    # Log but don't block deletion — storage may already be gone
                    pass

        await self._repo.delete(analysis_id)

    async def update_analysis(
        self,
        analysis_id: UUID,
        user_id: UUID,
        tags: list[str] | None = None,
    ) -> Analysis:
        """Update mutable fields on an analysis (B-028, FR-UPLD-10).

        Currently supports updating tags only.
        Validates ownership and raises 404/403 as appropriate.
        """
        analysis = await self._repo.get_by_id(analysis_id)

        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ANALYSIS_NOT_FOUND",
                        "message": "Analysis not found.",
                        "detail": None,
                    }
                },
            )

        if analysis.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not own this analysis.",
                        "detail": None,
                    }
                },
            )

        if tags is not None:
            analysis.tags = tags

        return await self._repo.update(analysis)
