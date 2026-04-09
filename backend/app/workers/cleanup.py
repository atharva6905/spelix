"""
ARQ periodic cleanup job — artifact retention enforcement.

Implements FR-UPLD-15, FR-UPLD-19 (artifact lifecycle management).

A nightly cron job deletes Storage artifacts (annotated MP4, plot PNG, PDF)
for analyses older than 7 days, then NULLs the corresponding path columns.
The analyses row, rep_metrics, coaching_results, and summary_json are
preserved indefinitely — only artifact bytes are removed.

Architecture notes (CLAUDE.md):
- 7-day retention keeps active Storage at ~413 MB within Supabase free 1 GB tier
- Registered as an ARQ cron job in WorkerSettings (runs at 03:00 UTC daily)
- StorageService instantiated within the job — no DI since this is not a request
- Storage errors per analysis are caught and logged; remaining analyses continue
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select

from app.db import async_session
from app.models.analysis import Analysis
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

_RETENTION_DAYS = 7

# Artifact columns to clean — video_path is excluded (deleted by pipeline, not cleanup)
_ARTIFACT_ATTRS = ("annotated_video_path", "plot_path", "pdf_path")


async def cleanup_expired_artifacts(ctx: dict) -> int:  # noqa: ARG001
    """ARQ periodic job: delete artifacts older than 7 days from Storage.

    Finds all analyses with ``status='completed'`` whose ``created_at`` predates
    the 7-day retention window and that still have at least one non-NULL artifact
    path. For each such analysis:

    1. Deletes each non-NULL artifact from Supabase Storage.
    2. Sets the corresponding path columns to NULL in the database.
    3. Flushes the session so changes are persisted.

    Storage errors for a single analysis are caught and logged; the job
    continues with the remaining analyses so one failure cannot block the rest.

    Parameters
    ----------
    ctx:
        ARQ context dict (unused but required by the ARQ job signature).

    Returns
    -------
    int
        Number of analyses whose artifacts were fully cleaned up.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)

    storage = StorageService(
        supabase_client=_build_supabase_client(),
        bucket=os.environ.get("SUPABASE_STORAGE_BUCKET", "videos"),
    )

    cleaned_count = 0

    async with async_session() as session:
        # Fetch completed analyses older than the cutoff that still have at
        # least one non-NULL artifact path — avoids re-processing already-clean rows.
        stmt = select(Analysis).where(
            and_(
                Analysis.status == "completed",
                Analysis.created_at < cutoff,
                or_(
                    Analysis.annotated_video_path.is_not(None),
                    Analysis.plot_path.is_not(None),
                    Analysis.pdf_path.is_not(None),
                ),
            )
        )
        result = await session.execute(stmt)
        analyses = result.scalars().all()

        logger.info(
            "cleanup_expired_artifacts: found %d analyses to clean (cutoff=%s)",
            len(analyses),
            cutoff.isoformat(),
        )

        for analysis in analyses:
            try:
                cleaned = await _clean_analysis(analysis, storage)
                if cleaned:
                    await session.flush()
                    cleaned_count += 1
                    logger.info(
                        "cleanup_expired_artifacts: cleaned analysis %s",
                        analysis.id,
                    )
            except Exception:
                logger.exception(
                    "cleanup_expired_artifacts: failed to clean analysis %s — skipping",
                    analysis.id,
                )

    logger.info(
        "cleanup_expired_artifacts: completed — %d analyses cleaned",
        cleaned_count,
    )
    return cleaned_count


async def _clean_analysis(analysis: Analysis, storage: StorageService) -> bool:
    """Delete all non-NULL artifact paths from Storage and NULL them in the model.

    Parameters
    ----------
    analysis:
        The Analysis ORM instance to clean.
    storage:
        Initialised StorageService to use for deletion.

    Returns
    -------
    bool
        True if any artifact was deleted (model was modified), False otherwise.
    """
    modified = False

    for attr in _ARTIFACT_ATTRS:
        path: str | None = getattr(analysis, attr)
        if path is None:
            continue

        # Delete from Supabase Storage — propagate exceptions to the caller
        # so the per-analysis error handler can catch and log them.
        await storage.delete_file(path)
        setattr(analysis, attr, None)
        modified = True
        logger.debug(
            "cleanup_expired_artifacts: deleted %s for analysis %s",
            path,
            analysis.id,
        )

    return modified


def _build_supabase_client() -> object | None:
    """Construct a Supabase async client from environment variables.

    Returns None in test/local environments where env vars are not set,
    causing StorageService to raise RuntimeError if actually called.
    This matches the existing StorageService contract.
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_service_key:
        logger.warning(
            "cleanup_expired_artifacts: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set — "
            "StorageService will be inert (tests/local only)"
        )
        return None

    try:
        from supabase import create_client  # type: ignore[import]

        return create_client(supabase_url, supabase_service_key)
    except ImportError:
        logger.warning("cleanup_expired_artifacts: supabase package not installed")
        return None
