import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.candidate_review import (
    ApproveRequest,
    ApproveResponse,
    CandidateListItem,
    RejectRequest,
    RejectResponse,
)


def test_approve_request_allows_empty_body():
    req = ApproveRequest()
    assert req.content_override is None


def test_approve_request_strips_empty_string_to_none():
    req = ApproveRequest(content_override="")
    assert req.content_override is None


def test_approve_request_keeps_non_empty_string():
    req = ApproveRequest(content_override="  tuck elbows at 45  ")
    assert req.content_override == "tuck elbows at 45"


def test_approve_request_rejects_too_short():
    with pytest.raises(ValidationError):
        ApproveRequest(content_override="abc")


def test_approve_request_rejects_too_long():
    with pytest.raises(ValidationError):
        ApproveRequest(content_override="x" * 501)


def test_reject_request_requires_reason_min_length():
    with pytest.raises(ValidationError):
        RejectRequest(reason="")
    with pytest.raises(ValidationError):
        RejectRequest(reason="   ")
    req = RejectRequest(reason="off-topic")
    assert req.reason == "off-topic"


def _make_list_item(**overrides) -> CandidateListItem:
    cid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=cid,
        exercise="bench",
        phase="descent",
        entry_type="cue",
        content="Tuck elbows at 45.",
        trigger_tags=["bench", "elbow"],
        source_analysis_ids=[uuid.uuid4()],
        confidence_score=0.7,
        eval_scores={"faithfulness": 0.82},
        cove_verified=False,
        cove_explanation="evaluation_failed",
        lifecycle_decision="ADD",
        nearest_entry_id=None,
        nearest_cosine_sim=None,
        contradiction_flag=False,
        requires_technical_review=False,
        review_status="pending",
        created_at=now,
    )
    defaults.update(overrides)
    return CandidateListItem(**defaults)


def test_candidate_list_item_roundtrip_from_schema():
    item = _make_list_item()
    dumped = item.model_dump()
    assert dumped["eval_scores"]["faithfulness"] == 0.82


def test_candidate_list_item_requires_technical_review_false_for_cue():
    item = _make_list_item(entry_type="cue", requires_technical_review=False)
    assert item.requires_technical_review is False


def test_candidate_list_item_requires_technical_review_true_for_compensation():
    item = _make_list_item(entry_type="compensation", requires_technical_review=True)
    assert item.requires_technical_review is True
    dumped = item.model_dump()
    assert dumped["requires_technical_review"] is True


def test_candidate_list_item_defaults_requires_technical_review_false():
    """Field has a default of False — omitting it in construction should not error."""
    cid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    # Build without requires_technical_review — should default to False
    item = CandidateListItem(
        id=cid,
        exercise="bench",
        phase=None,
        entry_type="cue",
        content="Drive heels down.",
        trigger_tags=[],
        source_analysis_ids=[uuid.uuid4()],
        confidence_score=None,
        eval_scores={},
        cove_verified=None,
        cove_explanation=None,
        lifecycle_decision="ADD",
        nearest_entry_id=None,
        nearest_cosine_sim=None,
        contradiction_flag=False,
        review_status="pending",
        created_at=now,
    )
    assert item.requires_technical_review is False


def test_approve_response_carries_both_ids():
    c = uuid.uuid4()
    e = uuid.uuid4()
    resp = ApproveResponse(candidate_id=c, entry_id=e, qdrant_point_id=str(e))
    assert resp.candidate_id == c
    assert resp.entry_id == e
    assert resp.qdrant_point_id == str(e)


def test_reject_response_echoes_reason():
    c = uuid.uuid4()
    resp = RejectResponse(candidate_id=c, rejected_reason="off-topic")
    assert resp.rejected_reason == "off-topic"
