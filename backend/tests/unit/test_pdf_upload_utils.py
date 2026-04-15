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


class TestConstants:
    def test_max_pdf_bytes_is_50mib(self):
        assert MAX_PDF_BYTES == 52_428_800

    def test_pdf_magic_bytes(self):
        assert PDF_MAGIC_BYTES == b"%PDF-"
