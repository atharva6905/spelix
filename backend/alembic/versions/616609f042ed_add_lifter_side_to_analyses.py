"""add lifter side to analyses

Revision ID: 616609f042ed
Revises: 2371965f8072
Create Date: 2026-05-22 14:52:49.075619

Adds a nullable ``lifter_side VARCHAR(10)`` column to ``analyses`` with a
CHECK constraint enforcing ``lifter_side IN ('left', 'right')``. Populated
by the CV pipeline at runtime (Session 2, ADR-LIFTER-SIDE-DETECTION) once
``detect_lifter_side()`` runs between quality gates and angle timeseries.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '616609f042ed'
down_revision: Union[str, Sequence[str], None] = '2371965f8072'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable lifter_side column + CHECK constraint."""
    op.add_column(
        "analyses",
        sa.Column("lifter_side", sa.String(length=10), nullable=True),
    )
    op.create_check_constraint(
        "ck_analyses_lifter_side",
        "analyses",
        "lifter_side IS NULL OR lifter_side IN ('left', 'right')",
    )


def downgrade() -> None:
    """Drop CHECK constraint and column."""
    op.drop_constraint("ck_analyses_lifter_side", "analyses", type_="check")
    op.drop_column("analyses", "lifter_side")
