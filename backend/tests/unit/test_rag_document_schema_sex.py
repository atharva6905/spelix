"""Sex applicability on RagDocument + UserProfile.sex (FR-RAGK-05, FR-PROF-03)."""
import pytest
from pydantic import ValidationError

from app.models.rag_document import RagDocument
from app.models.user_profile import UserProfile
from app.schemas.rag_document import RagDocumentUploadRequest


def test_rag_document_has_sex_applicability_column():
    col = RagDocument.__table__.columns["sex_applicability"]
    assert col.nullable is False
    assert col.server_default.arg == "both"


def test_user_profile_has_nullable_sex_column():
    col = UserProfile.__table__.columns["sex"]
    assert col.nullable is True


def _req(**kw):
    # doi is required since #218 (PR #227) — omit it and validation fails for the wrong reason
    base = dict(title="T", doi="10.1234/test", filename="a.pdf", file_size_bytes=100)
    base.update(kw)
    return RagDocumentUploadRequest(**base)


def test_upload_request_sex_applicability_defaults_to_both():
    assert _req().sex_applicability == "both"


def test_upload_request_rejects_invalid_sex_applicability():
    with pytest.raises(ValidationError):
        _req(sex_applicability="all")
