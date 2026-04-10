"""003_add_detection_result

Add detection_result JSONB column to analyses table for FR-XDET-07
(exercise auto-detection confidence display on upload confirmation).

Revision ID: 003_add_detection_result
Revises: 002_rls_policies
Create Date: 2026-04-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "003_add_detection_result"
down_revision: Union[str, Sequence[str], None] = "002_rls_policies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("detection_result", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "detection_result")
