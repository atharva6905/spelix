"""Restamp retry task — reconciles papers_rag Qdrant payload to the DB.

Enqueued by PATCH /expert/papers/{id}/metadata when the inline best-effort
restamp fails (Qdrant unavailable, or set_payload raised). The task re-reads
``rag_documents.sex_applicability`` (the current source of truth) and stamps
it onto the paper's existing papers_rag points via set_payload — no re-embed.

Re-reading from the DB rather than trusting a passed-in payload makes the task
idempotent AND convergent under concurrent edits: it always stamps the latest
value. If the paper row is gone, it no-ops cleanly. Qdrant unavailability
RAISES so streaq's native retry/backoff kicks in (issue #258, FR-RAGK-05 ext.,
FR-AICP-12 ext.).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.repositories.rag_document import RagDocumentRepository
from app.services.qdrant import get_qdrant_client, paper_points_filter

logger = logging.getLogger(__name__)


async def restamp_paper_payload(ctx: dict[str, Any], paper_id: str) -> dict[str, Any]:
    """Re-stamp sex_applicability onto a paper's papers_rag points.

    Worker context must carry:
      ctx["db_session_maker"] — SQLAlchemy async_session factory
    """
    doc_id = UUID(paper_id)
    session_maker = ctx["db_session_maker"]

    async with session_maker() as session:
        repo = RagDocumentRepository(session)
        doc = await repo.get_by_id(doc_id)

    if doc is None:
        logger.warning("restamp.paper.not_found", extra={"paper_id": paper_id})
        return {"paper_id": paper_id, "status": "not_found"}

    sex_applicability = doc.sex_applicability

    qdrant = await get_qdrant_client()
    if qdrant is None:
        # Raise so streaq retries with backoff — a silent return would leave
        # the Qdrant payload (the retrieval hard-filter target) stale forever.
        raise RuntimeError(
            f"Qdrant unavailable — cannot restamp papers_rag for {paper_id}"
        )

    await qdrant.set_payload(
        "papers_rag",
        {"sex_applicability": sex_applicability},
        paper_points_filter(paper_id),
    )

    logger.info(
        "restamp.paper.done",
        extra={"paper_id": paper_id, "sex_applicability": sex_applicability},
    )
    return {"paper_id": paper_id, "status": "restamped"}
