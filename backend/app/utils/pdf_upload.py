"""Filename sanitisation and size constants for expert PDF upload (ADR-EXPERT-01)."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

MAX_PDF_BYTES: int = 50 * 1024 * 1024
PDF_MAGIC_BYTES: bytes = b"%PDF-"
_MAX_FILENAME_CHARS: int = 255
_ALLOWED_CHAR_RE = re.compile(r"[^A-Za-z0-9._-]")
_WHITESPACE_RE = re.compile(r"\s+")


class FilenameValidationError(ValueError):
    """Raised when a proposed PDF filename cannot be sanitised to a safe value."""


def sanitize_pdf_filename(raw: str) -> str:
    """Return a safe filename for Supabase Storage; raise on rejection.

    Rules:
    - Must end in `.pdf` (case-insensitive; output lowercases the extension).
    - Whitespace runs collapse to `_`.
    - Any character outside `[A-Za-z0-9._-]` is stripped.
    - Path separators and `..` segments are rejected.
    - Max 255 chars including extension.
    - Stem must be non-empty after sanitisation.
    """
    if not raw or not raw.strip():
        raise FilenameValidationError("filename is empty")

    if "/" in raw or "\\" in raw:
        raise FilenameValidationError("filename contains path separators")

    # Reject null bytes and other control characters before path parsing —
    # POSIX filesystems silently truncate at \x00 which would bypass the
    # extension check downstream (security review H-2).
    if any(ord(c) < 32 for c in raw):
        raise FilenameValidationError("filename contains control characters")

    name = PurePosixPath(raw).name
    if name in ("", ".", ".."):
        raise FilenameValidationError("filename resolves to a directory reference")

    lower = name.lower()
    if not lower.endswith(".pdf"):
        raise FilenameValidationError("filename must end in .pdf")

    stem = name[: -len(".pdf")]
    stem = _WHITESPACE_RE.sub("_", stem)
    stem = _ALLOWED_CHAR_RE.sub("", stem)

    if not stem:
        raise FilenameValidationError("filename stem is empty after sanitisation")

    safe = f"{stem}.pdf"
    if len(safe) > _MAX_FILENAME_CHARS:
        overflow = len(safe) - _MAX_FILENAME_CHARS
        truncated_stem = stem[:-overflow]
        # Edge case: if the stem is shorter than the overflow, truncation
        # would leave us with just ".pdf" (security review H-1). Reject
        # rather than silently produce a degenerate filename.
        if not truncated_stem:
            raise FilenameValidationError("filename too long to truncate safely")
        safe = f"{truncated_stem}.pdf"

    return safe
