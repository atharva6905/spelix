"""Repository for rag_documents table operations.

FR-RAGK-08: list with filters for admin corpus view.
FR-RAGK-09: delete + update review status.
"""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag_document import RagDocument


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
    ) -> list[RagDocument]:
        stmt = select(RagDocument).order_by(RagDocument.created_at.desc())
        if review_status is not None:
            stmt = stmt.where(RagDocument.review_status == review_status)
        if exercise_tag is not None:
            stmt = stmt.where(RagDocument.exercise_tags.any(exercise_tag))
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
        reviewer_id: uuid.UUID,
    ) -> RagDocument | None:
        result = await self._db.execute(
            select(RagDocument).where(RagDocument.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            return None
        doc.review_status = review_status
        doc.reviewer_id = reviewer_id
        doc.reviewed_at = datetime.now().astimezone()
        await self._db.flush()
        await self._db.refresh(doc)
        return doc

    async def create(self, doc: RagDocument) -> RagDocument:
        self._db.add(doc)
        await self._db.flush()
        await self._db.refresh(doc)
        return doc
