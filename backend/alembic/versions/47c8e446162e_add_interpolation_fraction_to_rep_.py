"""add interpolation_fraction to rep_metrics

Revision ID: 47c8e446162e
Revises: 7c4af3e51f08
Create Date: 2026-05-24 17:21:14.925784

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '47c8e446162e'
down_revision: Union[str, Sequence[str], None] = '7c4af3e51f08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "rep_metrics",
        sa.Column("interpolation_fraction", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rep_metrics", "interpolation_fraction")
