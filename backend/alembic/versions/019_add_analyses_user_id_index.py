"""add standalone index on analyses.user_id

Revision ID: 019_add_analyses_user_id_index
Revises: f2c0572a0bde
Create Date: 2026-04-20

NFR-PERF-01 (M-13): RLS policies and admin user-lookup queries that filter on
analyses.user_id alone cannot use the existing composite index
(user_id, created_at DESC) efficiently. A standalone index on user_id closes
this gap for equality-only predicates.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "019_add_analyses_user_id_index"
down_revision = "f2c0572a0bde"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_analyses_user_id", "analyses", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_analyses_user_id", table_name="analyses")
