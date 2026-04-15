"""008_beta_requests

Create `beta_requests` table for the landing-page email capture queue.

Provenance: STRATEGY.md v3 (2026-04-14) §Day 1-2 "Landing V1 live on prod"
and `landing-page-plan.md` §7 Email Capture Flow. Not tied to a numbered
SRS FR — this is a growth/ops surface (private-beta queue), not a product
feature. The API layer and admin approval UI land in the Track A feature
PR that follows this migration.

Schema:
- UUID PK, TEXT email (normalised lowercase+trim by API before insert),
  source VARCHAR(30) CHECK, BOOLEAN consent (must be TRUE),
  VARCHAR(30) status CHECK ('pending'|'approved'|'rejected'),
  approval + invite audit columns.
- UNIQUE index on email (re-submits return 409 at the API layer).
- (status, created_at DESC) index for the admin review queue.
- Partial index on invite_token WHERE invite_token IS NOT NULL to
  support fast token lookup on /signup?invite=TOKEN.

RLS model:
- Anonymous `anon` role: INSERT only, and only rows with `status = 'pending'`
  and every admin-only column NULL/default. Cannot read the queue.
- Authenticated users: no access at all. Regular signed-in users should
  not be able to read pending beta invites.
- Service role: bypasses RLS via Supabase default — admin endpoints talk
  through the service-role client per existing convention (see migration
  002 docstring). No explicit service-role policy needed.

No DDL FK to `auth.users` on `approved_by` per the project-wide hard
rule (root CLAUDE.md): keep as bare UUID, enforce via the admin-only
API surface.

Prod application: manual via `docker cp backend/alembic* →
spelix-backend-1` then `docker exec -u root -w /app spelix-backend-1
.venv/bin/alembic upgrade head`, same procedure used for 007 on
2026-04-14 (see handoff §housekeeping). The CI Deploy pipeline does
not copy alembic into the image.

Revision ID: 008_beta_requests
Revises: 007_enable_realtime_analyses
Create Date: 2026-04-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "008_beta_requests"
down_revision: Union[str, Sequence[str], None] = "007_enable_realtime_analyses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "beta_requests",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "source",
            sa.String(30),
            nullable=False,
            comment="hero | final_cta | reddit | dm | other",
        ),
        sa.Column("consented_to_beta_terms", sa.Boolean(), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="pending",
            comment="pending | approved | rejected",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        # approved_by is the admin user UUID — intentionally NOT a FK to
        # auth.users (root CLAUDE.md: "No DDL FK to auth.users").
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("invite_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invite_token", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "source IN ('hero','final_cta','reddit','dm','other')",
            name="ck_beta_requests_source",
        ),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected')",
            name="ck_beta_requests_status",
        ),
        sa.CheckConstraint(
            "consented_to_beta_terms = TRUE",
            name="ck_beta_requests_consent_required",
        ),
    )

    # Unique on email so a given address only enters the queue once —
    # API layer returns 409 on conflict rather than creating duplicates.
    op.create_index(
        "uq_beta_requests_email",
        "beta_requests",
        ["email"],
        unique=True,
    )

    # Admin review queue query pattern: WHERE status = ? ORDER BY created_at DESC.
    op.create_index(
        "ix_beta_requests_status_created_at",
        "beta_requests",
        ["status", sa.text("created_at DESC")],
    )

    # Partial index on invite_token for /signup?invite=TOKEN lookup.
    op.create_index(
        "ix_beta_requests_invite_token",
        "beta_requests",
        ["invite_token"],
        unique=True,
        postgresql_where=sa.text("invite_token IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # RLS — anon INSERT only; authenticated users and anon SELECT blocked.
    # Service role bypasses RLS by default (Supabase convention).
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE beta_requests ENABLE ROW LEVEL SECURITY")

    # Anonymous clients can INSERT, but CANNOT pre-set admin-only columns.
    # The WITH CHECK clause enforces that anon submissions land in the
    # 'pending' state with no approval / invite metadata.
    op.execute(
        """
        CREATE POLICY beta_requests_anon_insert
            ON beta_requests
            FOR INSERT
            TO anon
            WITH CHECK (
                status = 'pending'
                AND approved_at IS NULL
                AND approved_by IS NULL
                AND invite_sent_at IS NULL
                AND invite_token IS NULL
                AND consented_to_beta_terms = TRUE
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS beta_requests_anon_insert ON beta_requests")
    op.execute("ALTER TABLE beta_requests DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_beta_requests_invite_token", table_name="beta_requests")
    op.drop_index("ix_beta_requests_status_created_at", table_name="beta_requests")
    op.drop_index("uq_beta_requests_email", table_name="beta_requests")

    op.drop_table("beta_requests")
