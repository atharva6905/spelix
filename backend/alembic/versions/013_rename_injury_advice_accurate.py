"""Rename injury_advice_accurate to movement_advice_accurate.

SaMD/FTC compliance (D-029): the wire name 'injury_advice_accurate'
leaks prohibited terminology. User-facing label is already correct.

Revision ID: 013_rename_movement_advice
Revises: 012_compensation_entry_type
Create Date: 2026-04-19
"""

from alembic import op

revision = "013_rename_movement_advice"
down_revision = "012_compensation_entry_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE analysis_expert_reviews "
        "RENAME COLUMN injury_advice_accurate TO movement_advice_accurate"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE analysis_expert_reviews "
        "RENAME COLUMN movement_advice_accurate TO injury_advice_accurate"
    )
