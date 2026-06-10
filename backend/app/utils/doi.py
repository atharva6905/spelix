"""DOI normalization for the rag_documents dedup key (FR-EXPV-02).

DOIs are case-insensitive per the DOI Handbook; the canonical stored form is
lowercase, prefix-stripped, whitespace-trimmed. The partial unique index
uq_rag_documents_doi_live assumes values are already normalized at write time.
"""

from __future__ import annotations

import re

_DOI_PREFIX_RE = re.compile(r"^(https?://(dx\.)?doi\.org/|doi:)", re.IGNORECASE)
# Registrant prefix "10." + 4-9 digits + "/" + non-whitespace suffix.
_DOI_SHAPE_RE = re.compile(r"^10\.\d{4,9}/\S+$")


class DoiValidationError(ValueError):
    """Raised when a DOI cannot be normalized to the canonical 10.xxxx/suffix form."""


def normalize_doi(raw: str) -> str:
    value = _DOI_PREFIX_RE.sub("", raw.strip()).strip().lower()
    if not _DOI_SHAPE_RE.match(value):
        raise DoiValidationError(
            "DOI must be of the form 10.<registrant>/<suffix>, e.g. 10.1519/jsc.0b013e31818546bb"
        )
    return value
