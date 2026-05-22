"""threshold_flags section check

Revision ID: 7c4af3e51f08
Revises: 616609f042ed
Create Date: 2026-05-22 16:00:00.000000

Adds a CHECK constraint on ``threshold_flags.section`` enumerating the five
allowed values: ``'squat'``, ``'bench'``, ``'deadlift'``, ``'control'``, and
``'unvalidated_metrics'`` (new in Session 3, ADR-SAGITTAL-METRICS-REGISTRY).

The column previously had no DB-level CHECK -- the Pydantic Literal on
``ThresholdFlagCreate.section`` was the only validator. This migration
hardens the data layer so that bypassing FastAPI (e.g. via direct SQL or
a future internal tool) cannot insert invalid section values.

Reversible: ``downgrade()`` drops the constraint.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7c4af3e51f08"
down_revision: Union[str, Sequence[str], None] = "616609f042ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CHECK constraint enumerating the five allowed sections."""
    op.create_check_constraint(
        "ck_threshold_flags_section",
        "threshold_flags",
        "section IN ("
        "'squat', 'bench', 'deadlift', 'control', 'unvalidated_metrics'"
        ")",
    )


def downgrade() -> None:
    """Drop the section CHECK constraint."""
    op.drop_constraint(
        "ck_threshold_flags_section", "threshold_flags", type_="check"
    )
