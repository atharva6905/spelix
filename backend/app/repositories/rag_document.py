"""Repository for rag_documents table operations.

FR-RAGK-08: list with filters for admin corpus view.
FR-RAGK-09: delete + update review status.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag_document import RagDocument

# Re-export timezone so the import isn't flagged as unused when
# update_review_status is the only consumer (security review H-3).
_UTC = timezone.utc


class RagDocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_all(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        review_status: str | None = None,
        exercise_tag: str | None = None,
        quality_tier: str | None = None,
        exclude_uploading: bool = False,
    ) -> list[RagDocument]:
        stmt = select(RagDocument).order_by(RagDocument.created_at.desc())
        if review_status is not None:
            stmt = stmt.where(RagDocument.review_status == review_status)
        elif exclude_uploading:
            stmt = stmt.where(RagDocument.review_status != "uploading")
        if exercise_tag is not None:
            stmt = stmt.where(RagDocument.exercise_tags.contains([exercise_tag]))
        if quality_tier is not None:
            stmt = stmt.where(RagDocument.quality_tier == quality_tier)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        review_status: str | None = None,
    ) -> int:
        stmt = select(func.count(RagDocument.id))
        if review_status is not None:
            stmt = stmt.where(RagDocument.review_status == review_status)
        result = await self._db.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, doc_id: uuid.UUID) -> RagDocument | None:
        result = await self._db.execute(
            select(RagDocument).where(RagDocument.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, doc_id: uuid.UUID) -> bool:
        result = await self._db.execute(
            delete(RagDocument).where(RagDocument.id == doc_id)
        )
        return result.rowcount > 0  # type: ignore[union-attr]

    async def update_review_status(
        self,
        doc_id: uuid.UUID,
        *,
        review_status: str,
        reviewer_id: uuid.UUID | None = None,
    ) -> RagDocument | None:
        """Update review_status; set reviewer_id + reviewed_at only when a
        reviewer actually acted (review decisions). System-initiated
        transitions (e.g. uploading→pending on upload completion per
        ADR-EXPERT-01) pass reviewer_id=None and leave those columns null.
        """
        result = await self._db.execute(
            select(RagDocument).where(RagDocument.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            return None
        doc.review_status = review_status
        if reviewer_id is not None:
            doc.reviewer_id = reviewer_id
            doc.reviewed_at = datetime.now(_UTC)
        await self._db.flush()
        await self._db.refresh(doc)
        return doc

    async def get_live_by_doi(self, doi: str) -> RagDocument | None:
        """First live row holding this (normalized) DOI.

        Live = any review_status except 'reviewed_rejected' (re-upload after
        rejection is allowed) and 'uploading' (orphaned attempts must not lock
        a DOI). Mirrors the uq_rag_documents_doi_live partial index predicate.
        """
        stmt = (
            select(RagDocument)
            .where(
                RagDocument.doi == doi,
                RagDocument.review_status.notin_(("reviewed_rejected", "uploading")),
            )
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_sex_applicability(
        self, doc_id: uuid.UUID, *, sex_applicability: str
    ) -> RagDocument | None:
        """Update sex_applicability post-upload (FR-RAGK-05 ext., issue #223).

        Returns the refreshed row, or None when the document does not exist.
        Qdrant payload restamping is the caller's responsibility.
        """
        result = await self._db.execute(
            select(RagDocument).where(RagDocument.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            return None
        doc.sex_applicability = sex_applicability
        await self._db.flush()
        await self._db.refresh(doc)
        return doc

    async def update_chunk_count(
        self, doc_id: uuid.UUID, *, chunk_count: int
    ) -> None:
        result = await self._db.execute(
            select(RagDocument).where(RagDocument.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if doc is not None:
            doc.chunk_count = chunk_count
            await self._db.flush()

    async def create(self, doc: RagDocument) -> RagDocument:
        self._db.add(doc)
        await self._db.flush()
        await self._db.refresh(doc)
        return doc
