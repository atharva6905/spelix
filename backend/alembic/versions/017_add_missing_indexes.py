"""add missing indexes on analyses.status and consent_records.consent_type

Revision ID: 017_add_missing_indexes
Revises: 016_add_req_tech_review
Create Date: 2026-04-20

NFR-PERF-01 (H-14, H-15): worker queue polling on analyses.status and
consent lookups by type were doing full table scans. Add btree indexes to
keep those queries O(log n).
"""

from alembic import op

revision = "017_add_missing_indexes"
down_revision = "016_add_req_tech_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_analyses_status",
        "analyses",
        ["status"],
        postgresql_using="btree",
    )
    op.create_index(
        "ix_consent_records_consent_type",
        "consent_records",
        ["consent_type"],
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("ix_consent_records_consent_type", table_name="consent_records")
    op.drop_index("ix_analyses_status", table_name="analyses")
