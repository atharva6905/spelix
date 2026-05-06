"""Unit tests for lifecycle_decision — embed + Qdrant cosine routing."""

import logging
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.distillation.lifecycle import lifecycle_decision
from app.distillation.state import CandidateInsight, make_initial_distillation_state
from app.schemas.coaching import CoachingOutput


def _state_with_candidates(candidates: list[CandidateInsight]):
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.9, "correctness": 0.85},
    )
    state["candidates"] = candidates
    state["validation_decision"] = "pass"
    return state


def _stub_candidate():
    return CandidateInsight(
        content="Drive knees out as you descend.",
        exercise="squat",
        phase="descent",
        entry_type="cue",
        trigger_tags=["knee_cave"],
    )


def _mock_brain_embedding(vector):
    svc = MagicMock()
    svc.build_contextual_text = MagicMock(return_value="stub contextual text")
    return svc


def _mock_cohere(vector):
    c = MagicMock()
    c.embed_batch = AsyncMock(return_value=[vector])
    return c


def _mock_qdrant(nearest_id, score):
    """Mock the QdrantClientWrapper.query_points surface used by
    lifecycle_decision (D-053). The wrapper's query_points returns a
    QueryResponse envelope with a .points attribute; each point has
    .id, .score, .payload. Mocking .search would silently mask the
    pre-D-053 regression where lifecycle_decision called a method that
    no longer exists on AsyncQdrantClient in qdrant-client 1.x.
    """
    q = MagicMock()
    if nearest_id is None:
        response = MagicMock()
        response.points = []
    else:
        hit = MagicMock()
        hit.id = str(nearest_id)
        hit.score = score
        response = MagicMock()
        response.points = [hit]
    q.query_points = AsyncMock(return_value=response)
    return q


@pytest.mark.asyncio
async def test_lifecycle_noop_when_cosine_above_092() -> None:
    nearest = uuid.uuid4()
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(nearest, 0.95),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert len(update["decisions"]) == 1
    assert update["decisions"][0].decision == "NOOP"
    assert update["decisions"][0].nearest_entry_id == nearest


@pytest.mark.asyncio
async def test_lifecycle_update_when_cosine_in_075_092() -> None:
    nearest = uuid.uuid4()
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(nearest, 0.81),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert update["decisions"][0].decision == "UPDATE"


@pytest.mark.asyncio
async def test_lifecycle_update_at_noop_boundary_exact_092() -> None:
    """FR-BRAIN-17 boundary — SRS says `>0.92` NOOP (strict). At exactly
    0.92 the route must be UPDATE (increment confirmation_count), not
    NOOP. Regression test for auditor C-01."""
    nearest = uuid.uuid4()
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(nearest, 0.92),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert update["decisions"][0].decision == "UPDATE"


@pytest.mark.asyncio
async def test_lifecycle_add_when_cosine_below_075() -> None:
    nearest = uuid.uuid4()
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(nearest, 0.6),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert update["decisions"][0].decision == "ADD"


@pytest.mark.asyncio
async def test_lifecycle_add_when_empty_qdrant() -> None:
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(None, 0.0),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert update["decisions"][0].decision == "ADD"
    assert update["decisions"][0].nearest_entry_id is None


@pytest.mark.asyncio
async def test_lifecycle_decision_never_calls_legacy_search() -> None:
    """D-053: lifecycle_decision must NOT call the deprecated
    AsyncQdrantClient.search API. qdrant-client 1.x removed `.search`
    on AsyncQdrantClient; the prod warning 'AsyncQdrantClient object
    has no attribute search — treating as ADD' meant every candidate
    was silently routed to ADD, over-admitting duplicates to the review
    queue. Regression guard: use spec=QdrantClientWrapper so any attempt
    to access `.search` (not on the wrapper) raises AttributeError —
    stricter than __getattr__ override which MagicMock blocks.
    """
    from app.services.qdrant import QdrantClientWrapper

    nearest = uuid.uuid4()
    state = _state_with_candidates([_stub_candidate()])

    # spec=QdrantClientWrapper enforces the attribute boundary: any attribute
    # not on QdrantClientWrapper (including .search) raises AttributeError.
    # QdrantClientWrapper exposes .query_points but NOT .search, so the spec
    # is the exact boundary we want.
    q = MagicMock(spec=QdrantClientWrapper)
    response = MagicMock()
    hit = MagicMock()
    hit.id = str(nearest)
    hit.score = 0.95
    response.points = [hit]
    q.query_points = AsyncMock(return_value=response)

    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=q,
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )

    # If we got here, lifecycle_decision went through query_points, not search.
    assert len(update["decisions"]) == 1
    assert update["decisions"][0].decision == "NOOP"
    q.query_points.assert_awaited_once()


def _stub_coaching_output():
    return CoachingOutput(
        summary="s",
        strengths=["Consistent tempo"],
        issues=[],
        correction_plan=["Maintain neutral spine throughout the lift."],
        recommended_cues=[],
        citations=[],
        safety_warnings=[],
        confidence_level="High",
        dimension_addressed="Movement Quality",
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )


@pytest.mark.asyncio
async def test_lifecycle_decision_logs_qdrant_4xx_at_error_level(caplog) -> None:
    """D-054: Qdrant 401/403/404 must be logged at ERROR level (not WARNING).

    A sustained auth drift (revoked API key) would otherwise be
    operationally invisible at WARNING level. Ops dashboards that
    page on ERROR-and-above miss it. The broad fallback → ADD stays
    intact — distillation must not crash on transient errors —
    but 4xx gets promoted so it surfaces.
    """

    class _Fake4xx(Exception):
        """Duck-types the Qdrant UnexpectedResponse status_code attribute."""

        status_code = 401

    state = _state_with_candidates([_stub_candidate()])

    q = MagicMock()
    q.query_points = AsyncMock(side_effect=_Fake4xx("Unauthorized"))

    with caplog.at_level(logging.WARNING, logger="app.distillation.lifecycle"):
        update = await lifecycle_decision(
            state,
            cohere_client=_mock_cohere([0.0] * 1024),
            qdrant_client=q,
            brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
        )

    # Broad fallback is preserved — pipeline must not crash on auth errors.
    assert len(update["decisions"]) == 1
    assert update["decisions"][0].decision == "ADD"

    # 4xx must be logged at ERROR so ops dashboards surface auth drift.
    error_records = [
        r
        for r in caplog.records
        if r.levelno == logging.ERROR and "lifecycle_decision" in r.message
    ]
    assert error_records, (
        "Expected at least one ERROR log containing 'lifecycle_decision' "
        "for a Qdrant 4xx failure, but got none. "
        f"All captured records: {[(r.levelname, r.message) for r in caplog.records]}"
    )


@pytest.mark.asyncio
async def test_lifecycle_decision_logs_transient_error_at_warning_level(caplog) -> None:
    """D-054: non-4xx errors (ConnectionError, timeout, RuntimeError) stay at WARNING.

    Keeps noise down for transient network flakes that don't need paging.
    """
    state = _state_with_candidates([_stub_candidate()])

    q = MagicMock()
    q.query_points = AsyncMock(side_effect=ConnectionError("connection refused"))

    with caplog.at_level(logging.WARNING, logger="app.distillation.lifecycle"):
        update = await lifecycle_decision(
            state,
            cohere_client=_mock_cohere([0.0] * 1024),
            qdrant_client=q,
            brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
        )

    # Broad fallback is preserved.
    assert len(update["decisions"]) == 1
    assert update["decisions"][0].decision == "ADD"

    # Transient errors must log at WARNING, not ERROR.
    warning_records = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "lifecycle_decision" in r.message
    ]
    assert warning_records, (
        "Expected at least one WARNING log containing 'lifecycle_decision' "
        "for a transient error, but got none. "
        f"All captured records: {[(r.levelname, r.message) for r in caplog.records]}"
    )

    error_records = [
        r
        for r in caplog.records
        if r.levelno == logging.ERROR and "lifecycle_decision" in r.message
    ]
    assert not error_records, (
        "Transient ConnectionError must NOT be logged at ERROR level, "
        f"but found: {[(r.levelname, r.message) for r in error_records]}"
    )


@pytest.mark.asyncio
async def test_lifecycle_decision_empty_candidates_returns_empty_decisions() -> None:
    """When state has no candidates, lifecycle_decision returns empty decisions (line 86)."""
    state = _state_with_candidates([])

    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(None, 0.0),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )

    assert update == {"decisions": []}
