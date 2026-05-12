"""Paper ingestion task — Docling PDF extraction + IngestionService.

Enqueued when an admin approves a paper via PATCH /expert/papers/{id}/review
with decision="reviewed_approved". Also enqueued by POST /expert/papers/{id}/complete
as a no-op pre-check (returns pending_review since the paper is not yet approved).

Pipeline: download PDF → Docling text extraction → IngestionService
(chunk + Cohere embed + Qdrant upsert) → update chunk_count in DB.

FR-EXPV-02, ADR-EXPERT-01.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


async def ingest_paper(ctx: dict[str, Any], paper_id: str) -> dict[str, Any]:
    """Full paper ingestion pipeline.

    Worker context must carry:
      ctx["paper_storage"]    — PaperStorageService
      ctx["db_session_maker"] — SQLAlchemy async_session factory
    """
    doc = await _lookup_document(ctx, UUID(paper_id))
    if doc is None:
        logger.warning("paper.ingest.not_found", extra={"paper_id": paper_id})
        return {"paper_id": paper_id, "status": "not_found"}

    if doc.review_status != "reviewed_approved":
        logger.info(
            "paper.ingest.pending_review",
            extra={"paper_id": paper_id, "review_status": doc.review_status},
        )
        return {"paper_id": paper_id, "status": "pending_review"}

    storage = ctx["paper_storage"]
    pdf_bytes = await storage.download_bytes(doc.storage_path)

    from app.services.pdf_extraction import extract_text_from_pdf

    full_text, sections = await extract_text_from_pdf(pdf_bytes)
    if not full_text.strip():
        logger.warning("paper.ingest.extraction_failed", extra={"paper_id": paper_id})
        return {"paper_id": paper_id, "status": "extraction_failed"}

    from app.services.cohere_client import get_cohere_client
    from app.services.ingestion import DocumentMetadata, IngestionService
    from app.services.qdrant import get_qdrant_client

    metadata = DocumentMetadata(
        title=doc.title,
        authors=list(doc.authors) if doc.authors else [],
        year=doc.year,
        doi=doc.doi,
        quality_tier=doc.quality_tier,
        review_status=doc.review_status,
    )

    cohere_client = get_cohere_client()
    qdrant_client = await get_qdrant_client()
    if qdrant_client is None:
        logger.error("paper.ingest.qdrant_unavailable", extra={"paper_id": paper_id})
        return {"paper_id": paper_id, "status": "qdrant_unavailable"}
    svc = IngestionService(cohere_client=cohere_client, qdrant_client=qdrant_client)

    result = await svc.ingest_document(
        paper_id=paper_id,
        text=full_text,
        metadata=metadata,
        sections=sections,
    )

    from app.repositories.rag_document import RagDocumentRepository

    async with ctx["db_session_maker"]() as session:
        repo = RagDocumentRepository(session)
        await repo.update_chunk_count(UUID(paper_id), chunk_count=result.chunk_count)
        await session.commit()

    logger.info(
        "paper.ingest.complete",
        extra={"paper_id": paper_id, "chunk_count": result.chunk_count},
    )
    return {
        "paper_id": paper_id,
        "status": "ingested",
        "chunk_count": result.chunk_count,
    }


async def _lookup_document(ctx: dict[str, Any], paper_id: UUID) -> Any | None:
    """Resolve the full RagDocument row from the DB.

    Tests may bypass by setting ctx['doc_override'].
    """
    override = ctx.get("doc_override")
    if override is not None:
        return override

    maker = ctx.get("db_session_maker")
    if maker is None:
        return None

    from app.repositories.rag_document import RagDocumentRepository

    async with maker() as session:
        repo = RagDocumentRepository(session)
        return await repo.get_by_id(paper_id)
