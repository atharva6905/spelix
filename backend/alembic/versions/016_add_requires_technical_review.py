"""add requires_technical_review to coach_brain_candidates

Revision ID: 016_add_requires_technical_review
Revises: 015_rls_admin_tables
Create Date: 2026-04-20

FR-ADMN-12: compensation entries must be flagged for biomechanics-qualified
reviewer routing. The requires_technical_review boolean defaults false and is
set true by the distillation store when entry_type='compensation'.
"""

from alembic import op
import sqlalchemy as sa

revision = "016_add_req_tech_review"
down_revision = "015_rls_admin_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "coach_brain_candidates",
        sa.Column(
            "requires_technical_review",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("coach_brain_candidates", "requires_technical_review")
