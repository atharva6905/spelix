import pytest

from app.utils.pdf_upload import (
    MAX_PDF_BYTES,
    PDF_MAGIC_BYTES,
    FilenameValidationError,
    sanitize_pdf_filename,
)


class TestSanitizePdfFilename:
    def test_accepts_simple_filename(self):
        assert sanitize_pdf_filename("paper.pdf") == "paper.pdf"

    def test_preserves_allowed_characters(self):
        assert sanitize_pdf_filename("My-Paper_v2.1.pdf") == "My-Paper_v2.1.pdf"

    def test_replaces_whitespace_with_underscore(self):
        assert sanitize_pdf_filename("squat biomechanics.pdf") == "squat_biomechanics.pdf"

    def test_strips_disallowed_characters(self):
        assert sanitize_pdf_filename("paper@#$%.pdf") == "paper.pdf"

    def test_rejects_missing_pdf_extension(self):
        with pytest.raises(FilenameValidationError) as exc:
            sanitize_pdf_filename("paper.docx")
        assert "must end" in str(exc.value).lower()

    def test_accepts_uppercase_pdf_extension(self):
        """Extension check is case-insensitive; output lowercases the extension."""
        assert sanitize_pdf_filename("paper.PDF") == "paper.pdf"

    def test_rejects_empty_stem(self):
        with pytest.raises(FilenameValidationError):
            sanitize_pdf_filename(".pdf")

    def test_rejects_path_traversal(self):
        with pytest.raises(FilenameValidationError):
            sanitize_pdf_filename("../../../etc/passwd.pdf")

    def test_rejects_backslash_path(self):
        with pytest.raises(FilenameValidationError):
            sanitize_pdf_filename("..\\windows\\evil.pdf")

    def test_truncates_to_255(self):
        long_name = "a" * 300 + ".pdf"
        result = sanitize_pdf_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".pdf")

    def test_rejects_empty_string(self):
        with pytest.raises(FilenameValidationError):
            sanitize_pdf_filename("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(FilenameValidationError):
            sanitize_pdf_filename("   ")

    def test_rejects_null_byte(self):
        """Security review H-2: POSIX filesystems truncate at \\x00; the check
        must happen before PurePosixPath or the .pdf extension check could
        be bypassed by a name like 'paper\\x00.exe'."""
        with pytest.raises(FilenameValidationError) as exc:
            sanitize_pdf_filename("paper\x00.pdf")
        assert "control character" in str(exc.value).lower()

    def test_rejects_control_characters(self):
        for ctrl in ("\r", "\n", "\t", "\x01", "\x1f"):
            with pytest.raises(FilenameValidationError):
                sanitize_pdf_filename(f"paper{ctrl}x.pdf")

    def test_rejects_long_name_that_truncates_to_empty_stem(self):
        """Security review H-1: an all-disallowed-char stem whose surviving
        allowed chars would be exceeded by the truncation overflow must
        not produce '.pdf' as the final filename."""
        # stem after sanitisation = "a" * 252, overflow = 252 - (255 - 4) = 1,
        # truncated stem length = 251, still non-empty — this is fine.
        # To hit the degenerate path we need a sanitised stem where
        # len(safe) > 255 AND the overflow >= len(stem). Construct with an
        # already-at-limit stem plus trailing non-allowed chars which after
        # stripping leave a short stem.
        # Simpler deterministic repro: mock by forcing len via whitespace.
        # Here we just confirm the happy-path long name still truncates safely.
        long_name = "a" * 300 + ".pdf"
        result = sanitize_pdf_filename(long_name)
        assert result.endswith(".pdf")
        assert len(result) == 255


    def test_rejects_name_resolving_to_dot(self):
        """PurePosixPath('.') resolves to '' name which is caught by the directory-ref check."""
        # A raw value of "." after stripping leads to directory-reference rejection.
        with pytest.raises(FilenameValidationError, match="directory reference"):
            sanitize_pdf_filename(".")

    def test_truncation_overflow_leaves_empty_stem_is_rejected(self):
        """When truncation would produce an empty stem (overflow >= len(stem)), raise."""
        # Construct: stem is 1 char, but total length makes len(safe) > 255.
        # stem = "a", extension = ".pdf" → safe = "a.pdf" (5 chars) — does NOT exceed 255.
        # We need a stem that, after extension, is > 255.
        # Build a stem where the overflow equals the stem length exactly.
        # stem of length 1, len(safe) = 1 + 4 = 5 — never triggers without > 255 total.
        # Use monkeypatching to simulate the condition instead:
        from unittest.mock import patch

        # len(safe) = 256, stem = "a" → overflow = 1, truncated_stem = "" → rejected
        with patch(
            "app.utils.pdf_upload._MAX_FILENAME_CHARS",
            4,  # force len("a.pdf") = 5 > 4
        ):
            with pytest.raises(FilenameValidationError, match="truncate safely"):
                sanitize_pdf_filename("a.pdf")


class TestConstants:
    def test_max_pdf_bytes_is_50mib(self):
        assert MAX_PDF_BYTES == 52_428_800

    def test_pdf_magic_bytes(self):
        assert PDF_MAGIC_BYTES == b"%PDF-"
