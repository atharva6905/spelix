"""add timing_json JSONB column to analyses

Revision ID: 010_add_timing_json
Revises: 009_papers_bucket_rls
Create Date: 2026-04-16

D-035 instrumentation column. Stores per-stage wall durations recorded by
``app.services.timing.StageTimer`` from inside the pipeline. JSONB shape:
``{"stage_name": elapsed_ms_float, ...}``. Nullable so pre-existing analyses
unaffected; written incrementally during pipeline run so partial completions
still leave useful data for triage.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "010_add_timing_json"
down_revision: str | None = "009_papers_bucket_rls"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column(
            "timing_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("analyses", "timing_json")
