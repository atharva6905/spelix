"""Tests for SparseRetrievalService — BM25 sparse vector retrieval.

TDD gate for P2-009 (FR-AICP-09 — hybrid RAG pipeline, sparse leg).
Also covers exercise_filter parameter (P2-011, FR-AICP-12).

Covers:
1. sparse_search calls query_points with the correct collection name
2. sparse_search uses "bm25" as the `using` parameter (ADR-BRAIN-03)
3. Results are parsed into list[RetrievedContext] with correct collection field
4. Empty query returns empty list without calling query_points
5. Empty Qdrant response returns empty list
6. top_k is forwarded as `limit` to query_points
7. _build_sparse_vector produces correct TF-weighted indices and values
8. _build_sparse_vector returns None for blank text
9. Points with invalid payloads are skipped (defensive parsing)
10. sparse_search accepts "coach_brain" collection
11. exercise_filter passes query_filter to query_points (FR-AICP-12)
12. None exercise_filter omits query_filter
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.sparse_retrieval import (
    SparseRetrievalService,
    _build_sparse_vector,
    _parse_response,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> SparseRetrievalService:
    """Build a SparseRetrievalService with a mocked QdrantClientWrapper."""
    mock_qdrant = MagicMock()
    mock_qdrant.query_points = AsyncMock()
    return SparseRetrievalService(qdrant_client=mock_qdrant)


def _make_chunk_payload_dict(
    *,
    text: str = "Squat depth increases knee torque.",
    paper_id: str = "paper-001",
    chunk_index: int = 0,
    title: str = "Effects of squat depth",
    quality_tier: str = "L1_systematic_review",
) -> dict:
    """Return a valid ChunkPayload dict for use in mock point payloads."""
    return {
        "id": f"chunk-{chunk_index}",
        "text": text,
        "paper_id": paper_id,
        "chunk_index": chunk_index,
        "section": None,
        "token_count": len(text.split()),
        "quality_tier": quality_tier,
        "title": title,
        "authors": ["Smith J", "Lee K"],
        "year": 2022,
        "doi": "10.1234/test",
    }


def _make_scored_point(*, payload: dict, score: float = 0.75) -> MagicMock:
    """Return a mock ScoredPoint with the given payload and score."""
    point = MagicMock()
    point.payload = payload
    point.score = score
    point.id = payload.get("id", "unknown")
    return point


def _make_query_response(points: list) -> MagicMock:
    """Return a mock QueryResponse with .points attribute."""
    response = MagicMock()
    response.points = points
    return response


# ---------------------------------------------------------------------------
# _build_sparse_vector — unit tests (pure function)
# ---------------------------------------------------------------------------


class TestBuildSparseVector:
    def test_blank_string_returns_none(self) -> None:
        assert _build_sparse_vector("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert _build_sparse_vector("   ") is None

    def test_single_token_returns_one_entry(self) -> None:
        result = _build_sparse_vector("squat")
        assert result is not None
        assert len(result["indices"]) == 1
        assert len(result["values"]) == 1

    def test_tf_value_is_correct_for_uniform_distribution(self) -> None:
        # 4 tokens, each appearing once → TF = 0.25 each
        result = _build_sparse_vector("squat knee valgus depth")
        assert result is not None
        assert len(result["values"]) == 4
        for v in result["values"]:
            assert abs(v - 0.25) < 1e-9, f"Expected 0.25, got {v}"

    def test_repeated_token_has_higher_tf(self) -> None:
        # "squat squat knee" → squat TF = 2/3, knee TF = 1/3
        result = _build_sparse_vector("squat squat knee")
        assert result is not None
        # Both tokens present
        assert len(result["indices"]) == 2
        assert len(result["values"]) == 2
        # Sum of TF values = 1.0
        total = sum(result["values"])
        assert abs(total - 1.0) < 1e-9

    def test_indices_are_non_negative_integers(self) -> None:
        result = _build_sparse_vector("bench press elbow lockout")
        assert result is not None
        for idx in result["indices"]:
            assert isinstance(idx, int)
            assert idx >= 0

    def test_indices_within_vocab_size(self) -> None:
        from app.services.sparse_retrieval import _VOCAB_SIZE

        result = _build_sparse_vector("barbell hip deadlift sumo conventional")
        assert result is not None
        for idx in result["indices"]:
            assert idx < _VOCAB_SIZE

    def test_same_query_produces_same_indices(self) -> None:
        r1 = _build_sparse_vector("knee valgus squat")
        r2 = _build_sparse_vector("knee valgus squat")
        assert r1 == r2

    def test_lowercases_before_hashing(self) -> None:
        # "Squat" and "squat" should map to the same index
        r_lower = _build_sparse_vector("squat")
        r_upper = _build_sparse_vector("Squat")
        assert r_lower is not None
        assert r_upper is not None
        assert r_lower["indices"] == r_upper["indices"]
        assert r_lower["values"] == r_upper["values"]

    def test_indices_and_values_same_length(self) -> None:
        result = _build_sparse_vector("hip hinge posterior chain")
        assert result is not None
        assert len(result["indices"]) == len(result["values"])


# ---------------------------------------------------------------------------
# sparse_search — integration tests (mocked Qdrant)
# ---------------------------------------------------------------------------


class TestSparseSearch:
    @pytest.mark.asyncio
    async def test_calls_query_points_with_correct_collection(self) -> None:
        """sparse_search must forward the collection name to query_points."""
        service = _make_service()
        service._qdrant.query_points.return_value = _make_query_response([])

        await service.sparse_search("squat depth", collection="papers_rag")

        service._qdrant.query_points.assert_awaited_once()
        call_kwargs = service._qdrant.query_points.call_args
        assert call_kwargs.kwargs.get("collection") == "papers_rag" or (
            call_kwargs.args and call_kwargs.args[0] == "papers_rag"
        )

    @pytest.mark.asyncio
    async def test_uses_bm25_sparse_vector_name(self) -> None:
        """query_points must be called with using='bm25' (ADR-BRAIN-03)."""
        service = _make_service()
        service._qdrant.query_points.return_value = _make_query_response([])

        await service.sparse_search("deadlift hip hinge")

        call_kwargs = service._qdrant.query_points.call_args.kwargs
        assert call_kwargs.get("using") == "bm25"

    @pytest.mark.asyncio
    async def test_top_k_forwarded_as_limit(self) -> None:
        """top_k must be passed as the limit parameter to query_points."""
        service = _make_service()
        service._qdrant.query_points.return_value = _make_query_response([])

        await service.sparse_search("bench press", top_k=7)

        call_kwargs = service._qdrant.query_points.call_args.kwargs
        assert call_kwargs.get("limit") == 7

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_list(self) -> None:
        """Blank query must return [] without calling query_points."""
        service = _make_service()

        result = await service.sparse_search("")

        assert result == []
        service._qdrant.query_points.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_qdrant_response_returns_empty_list(self) -> None:
        """QueryResponse with no points must return empty list."""
        service = _make_service()
        service._qdrant.query_points.return_value = _make_query_response([])

        result = await service.sparse_search("squat")

        assert result == []

    @pytest.mark.asyncio
    async def test_results_parsed_into_retrieved_context(self) -> None:
        """Returned ScoredPoints must be parsed into list[RetrievedContext]."""
        from app.schemas.rag import RetrievedContext

        service = _make_service()
        payload = _make_chunk_payload_dict(text="Hip hinge mechanics in deadlift.")
        point = _make_scored_point(payload=payload, score=0.82)
        service._qdrant.query_points.return_value = _make_query_response([point])

        result = await service.sparse_search("deadlift hip")

        assert len(result) == 1
        assert isinstance(result[0], RetrievedContext)
        assert result[0].score == pytest.approx(0.82)
        assert result[0].chunk.text == "Hip hinge mechanics in deadlift."

    @pytest.mark.asyncio
    async def test_collection_field_set_on_retrieved_context(self) -> None:
        """RetrievedContext.collection must match the queried collection."""
        service = _make_service()
        payload = _make_chunk_payload_dict()
        point = _make_scored_point(payload=payload, score=0.5)
        service._qdrant.query_points.return_value = _make_query_response([point])

        result = await service.sparse_search("squat", collection="coach_brain")

        assert result[0].collection == "coach_brain"

    @pytest.mark.asyncio
    async def test_multiple_results_returned_in_order(self) -> None:
        """Multiple points must be returned in the order Qdrant provides them."""
        service = _make_service()
        points = [
            _make_scored_point(
                payload=_make_chunk_payload_dict(text="Result A", chunk_index=0),
                score=0.9,
            ),
            _make_scored_point(
                payload=_make_chunk_payload_dict(text="Result B", chunk_index=1),
                score=0.7,
            ),
        ]
        service._qdrant.query_points.return_value = _make_query_response(points)

        result = await service.sparse_search("squat", top_k=10)

        assert len(result) == 2
        assert result[0].chunk.text == "Result A"
        assert result[1].chunk.text == "Result B"

    @pytest.mark.asyncio
    async def test_accepts_coach_brain_collection(self) -> None:
        """sparse_search must work for coach_brain collection (not just papers_rag)."""
        service = _make_service()
        service._qdrant.query_points.return_value = _make_query_response([])

        result = await service.sparse_search("squat", collection="coach_brain")

        assert result == []
        call_kwargs = service._qdrant.query_points.call_args.kwargs
        assert call_kwargs.get("collection") == "coach_brain" or (
            service._qdrant.query_points.call_args.args
            and service._qdrant.query_points.call_args.args[0] == "coach_brain"
        )

    @pytest.mark.asyncio
    async def test_sparse_vector_passed_to_query_points(self) -> None:
        """query_points must receive a SparseVector (not a plain list)."""
        from qdrant_client import models as qdrant_models

        service = _make_service()
        service._qdrant.query_points.return_value = _make_query_response([])

        await service.sparse_search("knee flexion angle")

        call_kwargs = service._qdrant.query_points.call_args.kwargs
        query_arg = call_kwargs.get("query")
        assert isinstance(query_arg, qdrant_models.SparseVector), (
            f"Expected SparseVector, got {type(query_arg)}"
        )

    # -----------------------------------------------------------------------
    # P2-011 — exercise_filter tests (FR-AICP-12)
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_exercise_filter_passes_query_filter_to_query_points(self) -> None:
        """When exercise_filter is provided, query_points must receive a query_filter
        with a FieldCondition matching payload.exercise == exercise_filter value.
        """
        from qdrant_client import models as qdrant_models

        service = _make_service()
        service._qdrant.query_points.return_value = _make_query_response([])

        await service.sparse_search(
            "squat depth hip mobility",
            collection="coach_brain",
            exercise_filter="squat",
        )

        service._qdrant.query_points.assert_awaited_once()
        call_kwargs = service._qdrant.query_points.call_args.kwargs

        query_filter = call_kwargs.get("query_filter")
        assert query_filter is not None, (
            "query_filter must be passed to query_points when exercise_filter is set."
        )
        assert isinstance(query_filter, qdrant_models.Filter), (
            f"query_filter must be qdrant_client.models.Filter, got {type(query_filter)}"
        )
        must_conditions = query_filter.must
        assert must_conditions and len(must_conditions) == 1
        condition = must_conditions[0]
        assert isinstance(condition, qdrant_models.FieldCondition)
        assert condition.key == "exercise"
        assert isinstance(condition.match, qdrant_models.MatchValue)
        assert condition.match.value == "squat"

    @pytest.mark.asyncio
    async def test_no_exercise_filter_omits_query_filter(self) -> None:
        """When exercise_filter is None (default), query_filter must NOT be passed
        to query_points.
        """
        service = _make_service()
        service._qdrant.query_points.return_value = _make_query_response([])

        await service.sparse_search("deadlift hip hinge")

        call_kwargs = service._qdrant.query_points.call_args.kwargs
        assert "query_filter" not in call_kwargs, (
            "query_filter must not be present in query_points call when exercise_filter is None."
        )

    # -----------------------------------------------------------------------
    # #225 — additional_filters merged into Filter.must (sex-applicability leak fix)
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_additional_filters_merged_into_must(self) -> None:
        """additional_filters conditions are added to query_filter.must alongside
        the exercise condition (FR-AICP-12 ext.). Without this the BM25 leg would
        surface opposite-sex papers that the dense leg already filters out."""
        from qdrant_client import models as qdrant_models

        service = _make_service()
        service._qdrant.query_points.return_value = _make_query_response([])

        sex_cond = qdrant_models.FieldCondition(
            key="sex_applicability",
            match=qdrant_models.MatchAny(any=["female", "both"]),
        )

        await service.sparse_search(
            "squat depth",
            collection="papers_rag",
            exercise_filter="squat",
            additional_filters=[sex_cond],
        )

        call_kwargs = service._qdrant.query_points.call_args.kwargs
        query_filter = call_kwargs.get("query_filter")
        assert query_filter is not None
        keys = {c.key for c in query_filter.must}
        assert keys == {"exercise", "sex_applicability"}
        sex = next(c for c in query_filter.must if c.key == "sex_applicability")
        assert set(sex.match.any) == {"female", "both"}

    @pytest.mark.asyncio
    async def test_additional_filters_without_exercise_filter(self) -> None:
        """additional_filters alone (no exercise_filter) still builds a query_filter."""
        from qdrant_client import models as qdrant_models

        service = _make_service()
        service._qdrant.query_points.return_value = _make_query_response([])

        sex_cond = qdrant_models.FieldCondition(
            key="sex_applicability",
            match=qdrant_models.MatchAny(any=["male", "both"]),
        )

        await service.sparse_search(
            "bench press",
            collection="papers_rag",
            additional_filters=[sex_cond],
        )

        call_kwargs = service._qdrant.query_points.call_args.kwargs
        query_filter = call_kwargs.get("query_filter")
        assert query_filter is not None
        assert len(query_filter.must) == 1
        assert query_filter.must[0].key == "sex_applicability"

    @pytest.mark.asyncio
    async def test_no_additional_filters_omits_query_filter(self) -> None:
        """No exercise_filter and no additional_filters → no query_filter at all."""
        service = _make_service()
        service._qdrant.query_points.return_value = _make_query_response([])

        await service.sparse_search("deadlift", additional_filters=None)

        call_kwargs = service._qdrant.query_points.call_args.kwargs
        assert "query_filter" not in call_kwargs


# ---------------------------------------------------------------------------
# _parse_response — unit tests (pure function)
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_empty_points_list_returns_empty(self) -> None:
        response = _make_query_response([])
        result = _parse_response(response, "papers_rag")
        assert result == []

    def test_valid_point_parsed_correctly(self) -> None:
        from app.schemas.rag import RetrievedContext

        payload = _make_chunk_payload_dict(
            text="Eccentric control in the squat.", chunk_index=0
        )
        point = _make_scored_point(payload=payload, score=0.88)
        response = _make_query_response([point])

        result = _parse_response(response, "papers_rag")

        assert len(result) == 1
        ctx = result[0]
        assert isinstance(ctx, RetrievedContext)
        assert ctx.score == pytest.approx(0.88)
        assert ctx.collection == "papers_rag"
        assert ctx.chunk.text == "Eccentric control in the squat."

    def test_point_with_missing_payload_is_skipped(self) -> None:
        point = MagicMock()
        point.payload = None
        point.score = 0.5
        point.id = "bad-point"
        response = _make_query_response([point])

        result = _parse_response(response, "papers_rag")

        assert result == []

    def test_point_with_invalid_payload_is_skipped(self) -> None:
        """A payload missing required ChunkPayload fields must be skipped."""
        point = _make_scored_point(
            payload={"invalid": "data", "missing_required_fields": True},
            score=0.5,
        )
        response = _make_query_response([point])

        result = _parse_response(response, "papers_rag")

        assert result == []

    def test_mixed_valid_invalid_points(self) -> None:
        """Valid points are returned; invalid points are skipped."""
        valid_payload = _make_chunk_payload_dict(text="Valid chunk.", chunk_index=0)
        valid_point = _make_scored_point(payload=valid_payload, score=0.9)

        invalid_point = MagicMock()
        invalid_point.payload = {"broken": True}
        invalid_point.score = 0.8
        invalid_point.id = "bad"

        response = _make_query_response([valid_point, invalid_point])

        result = _parse_response(response, "papers_rag")

        assert len(result) == 1
        assert result[0].chunk.text == "Valid chunk."

    def test_response_without_points_attribute_returns_empty(self) -> None:
        """If the response has no .points, return empty list gracefully."""
        response = MagicMock(spec=[])  # no attributes
        result = _parse_response(response, "papers_rag")
        assert result == []
