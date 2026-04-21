"""add composite index on consent_records(user_id, consent_type)

Revision ID: 020_consent_records_comp_idx
Revises: 019_add_analyses_user_id_index
Create Date: 2026-04-20

NFR-PERF-01 (L-10): Consent lookup queries filter on both user_id and
consent_type simultaneously (WHERE user_id = $1 AND consent_type = $2).
Standalone indexes on each column exist but force a bitmap-AND operation.
A composite index on (user_id, consent_type) satisfies the conjunction
in a single index scan.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "020_consent_records_comp_idx"
down_revision = "019_add_analyses_user_id_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_consent_records_user_id_consent_type",
        "consent_records",
        ["user_id", "consent_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_consent_records_user_id_consent_type",
        table_name="consent_records",
    )
