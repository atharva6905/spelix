import pytest
from pydantic import ValidationError

from app.schemas.rag_document import (
    RagDocumentCompleteResponse,
    RagDocumentUploadRequest,
    RagDocumentUploadResponse,
)

# DOI became required in issue #218 (FR-EXPV-02 dedup key).
VALID_DOI = "10.1519/jsc.0b013e31818546bb"


class TestRagDocumentUploadRequest:
    def test_minimal_valid_body(self):
        req = RagDocumentUploadRequest(
            title="Test",
            doi=VALID_DOI,
            filename="paper.pdf",
            file_size_bytes=100,
        )
        assert req.title == "Test"
        assert req.document_type == "research_paper"
        assert req.exercise_tags == []
        assert req.authors == []

    def test_rejects_missing_doi(self):
        """DOI is the enforced unique business key (FR-EXPV-02, issue #218)."""
        with pytest.raises(ValidationError):
            RagDocumentUploadRequest(
                title="Test",
                filename="paper.pdf",
                file_size_bytes=100,
            )

    def test_rejects_size_over_50mib(self):
        with pytest.raises(ValidationError):
            RagDocumentUploadRequest(
                title="Test", doi=VALID_DOI,
                filename="p.pdf", file_size_bytes=52_428_801,
            )

    def test_rejects_size_zero(self):
        with pytest.raises(ValidationError):
            RagDocumentUploadRequest(
                title="Test", doi=VALID_DOI,
                filename="p.pdf", file_size_bytes=0,
            )

    def test_rejects_short_filename(self):
        """Filename must be at least 5 chars (x.pdf is the minimum)."""
        with pytest.raises(ValidationError):
            RagDocumentUploadRequest(
                title="Test", doi=VALID_DOI,
                filename="x.pd", file_size_bytes=100,
            )

    def test_accepts_all_study_designs(self):
        for design in ["rct", "observational", "systematic_review", "narrative_review"]:
            req = RagDocumentUploadRequest(
                title="t", doi=VALID_DOI,
                filename="p.pdf", file_size_bytes=100, study_design=design,
            )
            assert req.study_design == design

    def test_rejects_invalid_document_type(self):
        with pytest.raises(ValidationError):
            RagDocumentUploadRequest(
                title="t", document_type="invalid_kind", doi=VALID_DOI,
                filename="p.pdf", file_size_bytes=100,
            )


class TestRagDocumentUploadResponse:
    def test_fields(self):
        from datetime import datetime, timezone
        from uuid import uuid4
        r = RagDocumentUploadResponse(
            id=uuid4(), upload_url="https://x", storage_path="papers/x/y.pdf",
            expires_at=datetime.now(timezone.utc),
        )
        assert r.upload_url == "https://x"


class TestRagDocumentCompleteResponse:
    def test_review_status_must_be_pending(self):
        from uuid import uuid4
        r = RagDocumentCompleteResponse(id=uuid4(), review_status="pending", storage_path="p/x.pdf")
        assert r.review_status == "pending"

    def test_rejects_non_pending_status(self):
        from uuid import uuid4
        with pytest.raises(ValidationError):
            RagDocumentCompleteResponse(id=uuid4(), review_status="uploading", storage_path="p/x.pdf")
