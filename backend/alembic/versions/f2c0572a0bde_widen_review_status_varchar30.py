"""widen coach_brain_candidates.review_status to VARCHAR(30)

Revision ID: f2c0572a0bde
Revises: 017_add_missing_indexes
Create Date: 2026-04-20

NFR-MAIN-02 (M-12): project-wide rule that all status columns use VARCHAR(30).
The review_status column on coach_brain_candidates was VARCHAR(20), which
violates the consistent schema pattern enforced across other tables
(e.g. rag_documents.review_status is VARCHAR(30)).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f2c0572a0bde'
down_revision: Union[str, Sequence[str], None] = '017_add_missing_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen review_status from VARCHAR(20) to VARCHAR(30)."""
    op.alter_column(
        'coach_brain_candidates',
        'review_status',
        existing_type=sa.String(length=20),
        type_=sa.String(length=30),
        existing_nullable=False,
        existing_server_default=sa.text("'pending'::character varying"),
    )


def downgrade() -> None:
    """Narrow review_status back to VARCHAR(20)."""
    op.alter_column(
        'coach_brain_candidates',
        'review_status',
        existing_type=sa.String(length=30),
        type_=sa.String(length=20),
        existing_nullable=False,
        existing_server_default=sa.text("'pending'::character varying"),
    )
