"""add eval_scores_json to coaching_results

Revision ID: 0906139da711
Revises: 022_threshold_flags
Create Date: 2026-05-04 12:10:26.909746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0906139da711'
down_revision: Union[str, Sequence[str], None] = '022_threshold_flags'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add eval_scores_json JSONB column to coaching_results (SRS 7.2 C-002)."""
    op.add_column(
        'coaching_results',
        sa.Column('eval_scores_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Remove eval_scores_json column from coaching_results."""
    op.drop_column('coaching_results', 'eval_scores_json')
