"""add standalone index on coach_brain_entries.status

Revision ID: 021_coach_brain_status_idx
Revises: 020_consent_records_comp_idx
Create Date: 2026-04-20

NFR-PERF-01 (L-11): retrieve_coach_brain filters by
status IN ('active', 'seed'). The existing composite index
ix_coach_brain_entries_exercise_phase_status cannot serve this predicate
efficiently without also binding exercise and phase. A standalone index
on status enables an index scan for any status-only or status-leading
query, including the retrieval filter and the distillation gate check.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "021_coach_brain_status_idx"
down_revision = "020_consent_records_comp_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_coach_brain_entries_status",
        "coach_brain_entries",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_coach_brain_entries_status",
        table_name="coach_brain_entries",
    )
