"""007_enable_realtime_analyses

Enable Supabase Realtime on the analyses table.

Context: FR-RESL-13 requires the frontend to receive live status updates
via Supabase Realtime. For this to work:
1. The analyses table must be part of the supabase_realtime publication so
   Postgres WAL events are replicated to the Realtime service.
2. REPLICA IDENTITY FULL ensures UPDATE events carry the full row payload
   (default identity only sends PK + modified columns, which breaks the
   frontend hook's ``payload.new`` expectation).

Without these, the hook subscribes successfully but never receives UPDATEs,
so the status page stays on "Preparing to analyse…" forever and only the
10-second polling fallback brings it up to date. Session 27 observed this
on prod and fixed it manually via the SQL console; this migration makes the
config reproducible against any fresh Supabase project.

Idempotent: re-runnable — ADD TABLE on a table already in the publication
is a no-op and ALTER TABLE ... REPLICA IDENTITY FULL on a table already set
to FULL is also a no-op.

Not reversible in a meaningful way — downgrade removes the table from the
publication and resets REPLICA IDENTITY to DEFAULT, which is what fresh
Supabase projects start with, but doing this in prod would silently break
the live status page again.
"""
from __future__ import annotations

from alembic import op

# revision identifiers
revision = "007_enable_realtime_analyses"
down_revision = "006_admin_expert_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add analyses to the supabase_realtime publication.
    #    Wrapped in DO block to make this idempotent — ADD TABLE raises if the
    #    table is already a member of the publication.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_publication_tables
                WHERE pubname = 'supabase_realtime'
                  AND schemaname = 'public'
                  AND tablename = 'analyses'
            ) THEN
                ALTER PUBLICATION supabase_realtime ADD TABLE public.analyses;
            END IF;
        END $$;
        """
    )

    # 2. REPLICA IDENTITY FULL so UPDATE events carry the full row payload.
    #    ALTER ... REPLICA IDENTITY is idempotent at the DDL level.
    op.execute("ALTER TABLE public.analyses REPLICA IDENTITY FULL;")


def downgrade() -> None:
    # Drop the table from the publication if it's a member.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_publication_tables
                WHERE pubname = 'supabase_realtime'
                  AND schemaname = 'public'
                  AND tablename = 'analyses'
            ) THEN
                ALTER PUBLICATION supabase_realtime DROP TABLE public.analyses;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE public.analyses REPLICA IDENTITY DEFAULT;")
