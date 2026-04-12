"""Repository for the chat_messages table — SQLAlchemy 2.0 async style."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage


class ChatMessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, message: ChatMessage) -> ChatMessage:
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def get_by_analysis(self, analysis_id: UUID) -> list[ChatMessage]:
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.analysis_id == analysis_id)
            .order_by(ChatMessage.created_at.asc())
        )
        return list(result.scalars().all())
