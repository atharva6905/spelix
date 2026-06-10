"""doi unique live index

Revision ID: cf685bd7e8f8
Revises: 47c8e446162e
Create Date: 2026-06-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'cf685bd7e8f8'
down_revision: Union[str, Sequence[str], None] = '47c8e446162e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill-normalize existing DOIs: trim, strip doi.org/doi: prefixes, lowercase.
    # Prod state verified 2026-06-09: 12 rows, no duplicates after normalization,
    # so the unique index below cannot fail on existing data.
    op.execute(
        r"""
        UPDATE rag_documents
        SET doi = lower(regexp_replace(btrim(doi), '^(https?://(dx\.)?doi\.org/|doi:)', '', 'i'))
        WHERE doi IS NOT NULL AND btrim(doi) <> ''
        """
    )
    op.execute(
        "UPDATE rag_documents SET doi = NULL WHERE doi IS NOT NULL AND btrim(doi) = ''"
    )
    # Partial unique index: DOI is the business key for LIVE rows only.
    # 'reviewed_rejected' (re-upload allowed) and 'uploading' (orphans must not
    # lock a DOI; uniqueness enforced at the uploading->pending flip) excluded.
    op.create_index(
        "uq_rag_documents_doi_live",
        "rag_documents",
        ["doi"],
        unique=True,
        postgresql_where=sa.text(
            "doi IS NOT NULL AND review_status NOT IN ('reviewed_rejected', 'uploading')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_rag_documents_doi_live", table_name="rag_documents")
    # Backfill normalization is not reversed (lossy, cosmetic).
