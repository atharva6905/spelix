"""Add 'compensation' to entry_type CHECK constraints on coach_brain_* tables.

Revision ID: 012_compensation_entry_type
Revises: 011_coach_brain_candidates
Create Date: 2026-04-19

D-038 / FR-ADMN-12: the review-card UI already renders a "biomechanics
reviewer required" banner forward-compatibly when entry_type == 'compensation'
(AdminCoachBrainCandidatesPage.tsx:190). This migration widens the DB
CHECK constraints on both the candidates table (migration 011) and the
entries table (migration 004) so the distillation pipeline can actually
produce compensation-typed rows.

No backfill — the constraint is a pure widening; existing rows all match
the original four values.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012_compensation_entry_type"
down_revision: str | None = "011_coach_brain_candidates"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


_NEW_VALUES = "('cue','correction','principle','drill','compensation')"
_OLD_VALUES = "('cue','correction','principle','drill')"


def upgrade() -> None:
    # coach_brain_candidates
    op.drop_constraint(
        "ck_coach_brain_candidates_entry_type",
        "coach_brain_candidates",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coach_brain_candidates_entry_type",
        "coach_brain_candidates",
        f"entry_type IN {_NEW_VALUES}",
    )

    # coach_brain_entries
    op.drop_constraint(
        "ck_coach_brain_entries_entry_type",
        "coach_brain_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coach_brain_entries_entry_type",
        "coach_brain_entries",
        f"entry_type IN {_NEW_VALUES}",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_coach_brain_candidates_entry_type",
        "coach_brain_candidates",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coach_brain_candidates_entry_type",
        "coach_brain_candidates",
        f"entry_type IN {_OLD_VALUES}",
    )

    op.drop_constraint(
        "ck_coach_brain_entries_entry_type",
        "coach_brain_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coach_brain_entries_entry_type",
        "coach_brain_entries",
        f"entry_type IN {_OLD_VALUES}",
    )
