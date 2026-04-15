"""ARQ task fired after an expert PDF upload completes (ADR-EXPERT-01).

Enqueued by POST /api/v1/expert/papers/{id}/complete once the uploaded
object passes the magic-byte check.

Scope: stub that downloads the head bytes of the stored PDF via the
service-role Supabase client (to prove the read path works under the
papers-bucket RLS policy) and logs `docling_pending`. P2-005 will
replace the body with actual Docling parsing + IngestionService call.
Until then, rag_documents rows for expert-uploaded papers stay at
chunk_count=0 and ingested_at=<upload time>.

FR-EXPV-02 (Should — Docling ingestion, deferred to P2-005).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


async def ingest_paper(ctx: dict[str, Any], paper_id: str) -> dict[str, Any]:
    """Download the uploaded PDF head bytes and log `docling_pending`.

    Worker context must carry:
      ctx["paper_storage"]    — app.services.paper_storage.PaperStorageService
      ctx["db_session_maker"] — SQLAlchemy async_session factory (for lookup)

    In unit tests both are supplied directly in the ctx fixture, bypassing
    the real on_startup wiring.
    """
    storage_path = await _lookup_storage_path(ctx, UUID(paper_id))
    if storage_path is None:
        logger.warning("paper.ingest.not_found", extra={"paper_id": paper_id})
        return {"paper_id": paper_id, "status": "not_found"}

    storage = ctx["paper_storage"]
    head = await storage.download_head_bytes(storage_path, n=8)
    logger.info(
        "paper.ingest.docling_pending",
        extra={
            "paper_id": paper_id,
            "storage_path": storage_path,
            "head_len": len(head),
        },
    )
    return {"paper_id": paper_id, "status": "docling_pending"}


async def _lookup_storage_path(ctx: dict[str, Any], paper_id: UUID) -> str | None:
    """Resolve the storage_path for a paper via the DB.

    Tests may bypass by setting ctx['storage_path_override'].
    """
    override = ctx.get("storage_path_override")
    if override is not None:
        return override

    maker = ctx.get("db_session_maker")
    if maker is None:
        return None

    from app.repositories.rag_document import RagDocumentRepository

    async with maker() as session:
        repo = RagDocumentRepository(session)
        doc = await repo.get_by_id(paper_id)
        return doc.storage_path if doc is not None else None
