"""015_rls_admin_tables

Enable Row Level Security on admin/system tables: rag_documents,
expert_annotations, and coach_brain_entries.

These tables were created in migration 004 without RLS. The correct policy
for admin-only tables is: enable RLS with no user-level policies. Supabase
service_role bypasses RLS by default, so only service_role can access.
Regular authenticated users are denied at the RLS layer — no CREATE POLICY
statements are needed.

Security audit finding H-03 (NFR-SECU-07 compliance).

Revision ID: 015_rls_admin_tables
Revises: 1862247fad86
Create Date: 2026-04-20
"""

from typing import Sequence, Union

from alembic import op


revision: str = "015_rls_admin_tables"
down_revision: Union[str, Sequence[str], None] = "1862247fad86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # rag_documents — admin/system table, service_role access only
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE rag_documents ENABLE ROW LEVEL SECURITY")

    # ------------------------------------------------------------------
    # expert_annotations — admin/system table, service_role access only
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE expert_annotations ENABLE ROW LEVEL SECURITY")

    # ------------------------------------------------------------------
    # coach_brain_entries — admin/system table, service_role access only
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE coach_brain_entries ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE coach_brain_entries DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE expert_annotations DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rag_documents DISABLE ROW LEVEL SECURITY")
