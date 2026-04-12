"""005_add_chat_messages

Chat messages table for follow-up Q&A on completed analyses.

SRS requirements:
- FR-RESL-09  — Follow-up chat panel below coaching feedback
- FR-AICP-17  — Follow-up chat with session data + knowledge base context

Revision ID: 005_add_chat_messages
Revises: 004_phase2_rag_coach_brain
Create Date: 2026-04-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "005_add_chat_messages"
down_revision: Union[str, Sequence[str], None] = "004_phase2_rag_coach_brain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("analysis_id", UUID(as_uuid=True), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_messages_role"),
    )
    op.create_index(
        "ix_chat_messages_analysis_created",
        "chat_messages",
        ["analysis_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_analysis_created", table_name="chat_messages")
    op.drop_table("chat_messages")
