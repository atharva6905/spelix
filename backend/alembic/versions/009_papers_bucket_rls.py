"""009_papers_bucket_rls

Create `papers` Supabase Storage bucket, widen `rag_documents.review_status`
CHECK constraint to include the `'uploading'` transient state, and add
storage-layer RLS policies on `storage.objects` for the `papers` bucket.

Requirements implemented:
- FR-EXPV-02: Expert reviewer portal paper upload with metadata.
  The `papers` bucket is the storage layer that enables PDF uploads.
- FR-EXPV-01: Expert reviewer portal role gating.
  The RLS policies on storage.objects (INSERT restricted to
  expert_reviewer + admin JWT roles) enforce this at the storage layer.

Security model: ADR-EXPERT-01 (decisions.md:390, commit 1b5fa79).
Two-phase signed-URL upload — bucket RLS restricts INSERT to
expert_reviewer/admin JWT roles; SELECT/DELETE are service_role only.

All DDL is via op.execute because:
1. storage.buckets / storage.objects live in the `storage` schema,
   not in `public` — op.create_table cannot target other schemas.
2. The CHECK constraint edit is an ALTER TABLE op not covered by
   autogenerate for cross-session constraint name matching.

No DDL FK to auth.users anywhere in this migration.

Revision ID: 009_papers_bucket_rls
Revises: 008_beta_requests
Create Date: 2026-04-15
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_papers_bucket_rls"
down_revision: Union[str, Sequence[str], None] = "008_beta_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create the `papers` Supabase Storage bucket.
    #    file_size_limit: 52 428 800 bytes = 50 MiB (FR-EXPV-02).
    #    allowed_mime_types: application/pdf only — Supabase enforces
    #    this on the signed-URL PUT before the object is committed.
    #    ON CONFLICT (id) DO NOTHING makes the step idempotent so a
    #    re-run (e.g. after a failed partial migration) is safe.
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
        VALUES (
            'papers',
            'papers',
            false,
            52428800,
            ARRAY['application/pdf']::text[]
        )
        ON CONFLICT (id) DO NOTHING
        """
    )

    # ------------------------------------------------------------------
    # 2. Widen the review_status CHECK constraint on rag_documents to
    #    include 'uploading'.
    #
    #    The existing constraint name (from migration 006) is
    #    ck_rag_documents_review_status with values:
    #      'pending','needs_revision','reviewed_approved','reviewed_rejected'
    #
    #    We drop and recreate it to append 'uploading'.  DROP CONSTRAINT
    #    IF EXISTS is safe here — if it somehow doesn't exist (e.g. this
    #    migration is replayed against a blank schema) the ADD CONSTRAINT
    #    below will still create the correct final state.
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE rag_documents "
        "DROP CONSTRAINT IF EXISTS ck_rag_documents_review_status"
    )
    op.execute(
        "ALTER TABLE rag_documents ADD CONSTRAINT ck_rag_documents_review_status "
        "CHECK (review_status IN ("
        "'pending','needs_revision','reviewed_approved','reviewed_rejected','uploading'"
        "))"
    )

    # ------------------------------------------------------------------
    # 3. RLS policies on storage.objects for the `papers` bucket.
    #
    #    Drop any pre-existing expert_papers_* policies first so the
    #    migration is idempotent (safe to replay after partial failure).
    #
    #    Policy design (ADR-EXPERT-01):
    #    - expert_papers_insert: authenticated users whose JWT
    #      user_metadata.role is 'expert_reviewer' or 'admin' may INSERT.
    #      The JWT claim path auth.jwt()->'user_metadata'->>'role' is the
    #      Supabase-standard way to read a custom role from user_metadata.
    #    - expert_papers_service_select: service_role may SELECT (needed
    #      by the /complete endpoint's magic-byte check).
    #    - expert_papers_service_delete: service_role may DELETE (needed
    #      by the /complete endpoint's cleanup on invalid PDF).
    #
    #    No public READ policy — the bucket is private (public=false).
    # ------------------------------------------------------------------
    op.execute(
        "DROP POLICY IF EXISTS expert_papers_insert ON storage.objects"
    )
    op.execute(
        "DROP POLICY IF EXISTS expert_papers_service_select ON storage.objects"
    )
    op.execute(
        "DROP POLICY IF EXISTS expert_papers_service_delete ON storage.objects"
    )

    op.execute(
        """
        CREATE POLICY "expert_papers_insert" ON storage.objects
            FOR INSERT TO authenticated
            WITH CHECK (
                bucket_id = 'papers'
                AND (auth.jwt()->'user_metadata'->>'role') IN ('expert_reviewer', 'admin')
            )
        """
    )
    op.execute(
        """
        CREATE POLICY "expert_papers_service_select" ON storage.objects
            FOR SELECT TO service_role
            USING (bucket_id = 'papers')
        """
    )
    op.execute(
        """
        CREATE POLICY "expert_papers_service_delete" ON storage.objects
            FOR DELETE TO service_role
            USING (bucket_id = 'papers')
        """
    )


def downgrade() -> None:
    # Reverse in inverse order of upgrade.

    # ------------------------------------------------------------------
    # 3. Drop the three storage RLS policies.
    # ------------------------------------------------------------------
    op.execute(
        "DROP POLICY IF EXISTS expert_papers_insert ON storage.objects"
    )
    op.execute(
        "DROP POLICY IF EXISTS expert_papers_service_select ON storage.objects"
    )
    op.execute(
        "DROP POLICY IF EXISTS expert_papers_service_delete ON storage.objects"
    )

    # ------------------------------------------------------------------
    # 2. Restore the review_status CHECK constraint without 'uploading'.
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE rag_documents "
        "DROP CONSTRAINT IF EXISTS ck_rag_documents_review_status"
    )
    op.execute(
        "ALTER TABLE rag_documents ADD CONSTRAINT ck_rag_documents_review_status "
        "CHECK (review_status IN ("
        "'pending','needs_revision','reviewed_approved','reviewed_rejected'"
        "))"
    )

    # ------------------------------------------------------------------
    # 1. Remove the papers bucket row.
    #    Supabase does not CASCADE-delete storage.objects on bucket delete,
    #    so we only remove the bucket metadata row here. Any objects in the
    #    bucket must be cleaned up manually before downgrading in production.
    # ------------------------------------------------------------------
    op.execute("DELETE FROM storage.buckets WHERE id = 'papers'")
