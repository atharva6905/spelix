"""
streaq periodic cleanup job — orphan rag_documents lifecycle enforcement.

Implements D-030: nightly hard-delete of `rag_documents` rows stuck in
`review_status='uploading'` for more than 2 hours.

An upload is considered orphaned when:
  - ``review_status == 'uploading'``
  - ``created_at < NOW() - 2 hours``

For each orphaned row:
  1. If ``storage_path`` is set, delete the object from the ``papers``
     bucket via ``PaperStorageService``.
  2. Hard-delete the row from ``rag_documents`` via ``DELETE WHERE id = …``.
  3. Commit per-row so a later failure cannot roll back an already-cleaned row.

Storage errors are caught and logged per-row; the job continues with
remaining rows so one failure cannot block the rest. On a Storage error the
DB row is NOT deleted (the transaction is rolled back) — a subsequent run
will retry it.

Architecture notes:
  - 2-hour window is intentionally tight: TUS direct-to-Supabase uploads
    complete in <90 s for the 50 MB cap enforced by the signed URL. Anything
    still 'uploading' after 2 hours is genuinely orphaned.
  - Registered as a streaq cron in ``streaq_worker.py`` at 04:00 UTC (D-030).
  - ``PaperStorageService`` is instantiated within the job — no DI since this
    is not a request context.
  - ``_build_supabase_client()`` mirrors the pattern in ``cleanup.py`` exactly.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, select

from app.db import async_session
from app.models.rag_document import RagDocument
from app.services.paper_storage import PaperStorageService

logger = logging.getLogger(__name__)

_ORPHAN_AGE_HOURS = 2


async def cleanup_orphan_papers(ctx: dict) -> int:  # noqa: ARG001
    """streaq periodic job: hard-delete orphaned 'uploading' rag_documents rows.

    Finds all ``rag_documents`` with ``review_status='uploading'`` whose
    ``created_at`` predates the 2-hour cutoff. For each such row:

    1. If ``storage_path`` is set, deletes the object from Supabase Storage.
    2. Hard-deletes the row from ``rag_documents``.
    3. Commits per-row.

    Storage errors for a single row are caught and logged; the job continues
    with the remaining rows. On failure the transaction is rolled back and the
    row is left for the next nightly run.

    Parameters
    ----------
    ctx:
        ARQ-style context dict (unused but required by the job signature).

    Returns
    -------
    int
        Number of rows successfully deleted.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=_ORPHAN_AGE_HOURS)).replace(
        tzinfo=None
    )

    paper_storage = PaperStorageService(
        client=await _build_supabase_client(),
        bucket="papers",
    )

    deleted_count = 0

    async with async_session() as session:
        stmt = select(RagDocument).where(
            and_(
                RagDocument.review_status == "uploading",
                RagDocument.created_at < cutoff,
            )
        )
        result = await session.execute(stmt)
        docs = result.scalars().all()

        logger.info(
            "cleanup_orphan_papers: found %d orphaned uploading rows (cutoff=%s)",
            len(docs),
            cutoff.isoformat(),
        )

        for doc in docs:
            try:
                if doc.storage_path is not None:
                    await paper_storage.delete_object(doc.storage_path)
                    logger.debug(
                        "cleanup_orphan_papers: deleted storage object %s for doc %s",
                        doc.storage_path,
                        doc.id,
                    )

                await session.execute(
                    delete(RagDocument).where(RagDocument.id == doc.id)
                )
                await session.commit()
                deleted_count += 1
                logger.info(
                    "cleanup_orphan_papers: hard-deleted orphan doc %s",
                    doc.id,
                )
            except Exception:
                await session.rollback()
                logger.exception(
                    "cleanup_orphan_papers: failed to delete doc %s — skipping",
                    doc.id,
                )

    logger.info(
        "cleanup_orphan_papers: completed — %d orphan rows deleted",
        deleted_count,
    )
    return deleted_count


async def _build_supabase_client() -> object | None:
    """Construct an *async* Supabase client from environment variables.

    Must use ``acreate_client`` (async) — ``PaperStorageService.delete_object``
    awaits ``self._client.storage.from_(...).remove(...)``, which only works
    on the async client.

    Returns None in test/local environments where env vars are not set;
    ``PaperStorageService`` will raise ``RuntimeError`` if actually called.
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_service_key:
        logger.warning(
            "cleanup_orphan_papers: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set — "
            "PaperStorageService will be inert (tests/local only)"
        )
        return None

    try:
        from supabase import acreate_client  # type: ignore[import]

        return await acreate_client(supabase_url, supabase_service_key)
    except ImportError:
        logger.warning("cleanup_orphan_papers: supabase package not installed")
        return None
    except Exception as e:
        logger.warning(
            "cleanup_orphan_papers: failed to create async Supabase client: %s", e
        )
        return None
