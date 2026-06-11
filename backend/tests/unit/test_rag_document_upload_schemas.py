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

    def test_rejects_missing_doi_for_research_paper(self):
        """DOI is the unique business key for research papers
        (FR-EXPV-02, issues #218/#234). document_type defaults to
        research_paper, so an omitted DOI must fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            RagDocumentUploadRequest(
                title="Test",
                filename="paper.pdf",
                file_size_bytes=100,
            )
        assert "DOI is required for research papers" in str(exc_info.value)

    def test_rejects_null_doi_for_explicit_research_paper(self):
        with pytest.raises(ValidationError):
            RagDocumentUploadRequest(
                title="Test",
                document_type="research_paper",
                doi=None,
                filename="paper.pdf",
                file_size_bytes=100,
            )

    @pytest.mark.parametrize(
        "doc_type", ["textbook", "clinical_guideline", "expert_annotation", "other"]
    )
    def test_doi_optional_for_non_research_paper_types(self, doc_type):
        """DOI-less document types are part of the contract (issue #234):
        the dedup index tolerates NULL and the corpus already has a
        DOI-less guideline row."""
        req = RagDocumentUploadRequest(
            title="Test",
            document_type=doc_type,
            filename="paper.pdf",
            file_size_bytes=100,
        )
        assert req.doi is None

    def test_doi_accepted_when_provided_for_non_research_paper_type(self):
        """An optional DOI supplied for e.g. a textbook is still kept (and
        normalized/dedup'd downstream)."""
        req = RagDocumentUploadRequest(
            title="Test",
            document_type="textbook",
            doi=VALID_DOI,
            filename="paper.pdf",
            file_size_bytes=100,
        )
        assert req.doi == VALID_DOI

    def test_rejects_empty_string_doi(self):
        """min_length=1 still applies to non-null values for every type."""
        with pytest.raises(ValidationError):
            RagDocumentUploadRequest(
                title="Test",
                document_type="textbook",
                doi="",
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
