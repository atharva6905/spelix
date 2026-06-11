"""sex applicability + profile sex

Revision ID: 9fffb59ba45f
Revises: cf685bd7e8f8
Create Date: 2026-06-10 00:37:30.290772

Sex-aware coaching contract (issue #221, FR-RAGK-05 ext., FR-PROF-03 ext.).

- rag_documents.sex_applicability: which lifter sex a paper's findings apply
  to. NOT NULL DEFAULT 'both'; the server_default backfills every existing
  rag_documents row, so no separate data migration is needed. CHECK restricts
  to ('male','female','both').
- user_profiles.sex: optional self-reported lifter sex, used to match coaching
  evidence. Nullable (lifters may decline). CHECK restricts to
  ('male','female','prefer_not_to_say').

Autogenerate ran against a drifted local DB and emitted unrelated diffs
(DateTime type churn, dropped indexes/tables, comment-only changes). Those were
discarded; this migration carries only the two intended columns + their CHECK
constraints (which autogenerate does not emit for table-level constraints).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9fffb59ba45f'
down_revision: Union[str, Sequence[str], None] = 'cf685bd7e8f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # rag_documents.sex_applicability — NOT NULL DEFAULT 'both' (backfills existing rows)
    op.add_column(
        'rag_documents',
        sa.Column(
            'sex_applicability',
            sa.String(length=30),
            server_default='both',
            nullable=False,
        ),
    )
    op.create_check_constraint(
        'ck_rag_documents_sex_applicability',
        'rag_documents',
        "sex_applicability IN ('male','female','both')",
    )

    # user_profiles.sex — optional lifter sex
    op.add_column(
        'user_profiles',
        sa.Column('sex', sa.String(length=30), nullable=True),
    )
    op.create_check_constraint(
        'ck_user_profiles_sex',
        'user_profiles',
        "sex IN ('male','female','prefer_not_to_say')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_user_profiles_sex', 'user_profiles', type_='check')
    op.drop_column('user_profiles', 'sex')
    op.drop_constraint(
        'ck_rag_documents_sex_applicability', 'rag_documents', type_='check'
    )
    op.drop_column('rag_documents', 'sex_applicability')
