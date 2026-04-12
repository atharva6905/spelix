"""Tests for Phase 2 shared RAG Pydantic schemas.

TDD gate for P2-002 (FR-AICP-09).

Covers:
- Round-trip serialisation for ChunkPayload, RetrievedContext,
  RetrievalResult, CitationBlock
- Invalid quality_tier values are rejected
- Invalid retrieval_source values are rejected
- Optional fields accept None
- Authors list must be a list, not a bare string
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# ChunkPayload
# ---------------------------------------------------------------------------


class TestChunkPayload:
    def _valid_payload(self) -> dict:
        return {
            "id": "a" * 64,  # sha256 hex
            "text": "The squat is a compound movement...",
            "paper_id": "paper-001",
            "chunk_index": 0,
            "section": "methods",
            "token_count": 256,
            "quality_tier": "L1_systematic_review",
            "title": "Effects of squat depth on muscle activation",
            "authors": ["Smith J", "Jones A"],
            "year": 2021,
            "doi": "10.1234/example",
        }

    def test_round_trip_serialisation(self) -> None:
        from app.schemas.rag import ChunkPayload

        data = self._valid_payload()
        chunk = ChunkPayload(**data)
        dumped = chunk.model_dump()
        assert dumped["id"] == data["id"]
        assert dumped["token_count"] == 256
        assert dumped["quality_tier"] == "L1_systematic_review"

    def test_all_quality_tier_values_accepted(self) -> None:
        from app.schemas.rag import ChunkPayload

        for tier in (
            "L1_systematic_review",
            "L2_rct",
            "L3_observational",
            "L4_guideline",
        ):
            data = {**self._valid_payload(), "quality_tier": tier}
            chunk = ChunkPayload(**data)
            assert chunk.quality_tier == tier

    def test_invalid_quality_tier_rejected(self) -> None:
        from app.schemas.rag import ChunkPayload

        data = {**self._valid_payload(), "quality_tier": "L5_blog_post"}
        with pytest.raises(ValidationError):
            ChunkPayload(**data)

    def test_section_can_be_none(self) -> None:
        from app.schemas.rag import ChunkPayload

        data = {**self._valid_payload(), "section": None}
        chunk = ChunkPayload(**data)
        assert chunk.section is None

    def test_year_can_be_none(self) -> None:
        from app.schemas.rag import ChunkPayload

        data = {**self._valid_payload(), "year": None}
        chunk = ChunkPayload(**data)
        assert chunk.year is None

    def test_doi_can_be_none(self) -> None:
        from app.schemas.rag import ChunkPayload

        data = {**self._valid_payload(), "doi": None}
        chunk = ChunkPayload(**data)
        assert chunk.doi is None

    def test_authors_must_be_list(self) -> None:
        from app.schemas.rag import ChunkPayload

        data = {**self._valid_payload(), "authors": "Smith J"}
        with pytest.raises(ValidationError):
            ChunkPayload(**data)

    def test_empty_authors_list_accepted(self) -> None:
        from app.schemas.rag import ChunkPayload

        data = {**self._valid_payload(), "authors": []}
        chunk = ChunkPayload(**data)
        assert chunk.authors == []


# ---------------------------------------------------------------------------
# RetrievedContext
# ---------------------------------------------------------------------------


def _make_chunk() -> dict:
    return {
        "id": "b" * 64,
        "text": "Hip hinge mechanics...",
        "paper_id": "paper-002",
        "chunk_index": 1,
        "section": "results",
        "token_count": 128,
        "quality_tier": "L2_rct",
        "title": "Hip hinge study",
        "authors": ["Brown K"],
        "year": 2019,
        "doi": None,
    }


class TestRetrievedContext:
    def test_round_trip_serialisation(self) -> None:
        from app.schemas.rag import ChunkPayload, RetrievedContext

        ctx = RetrievedContext(
            chunk=ChunkPayload(**_make_chunk()),
            score=0.923,
            collection="papers_rag",
        )
        dumped = ctx.model_dump()
        assert dumped["score"] == pytest.approx(0.923)
        assert dumped["collection"] == "papers_rag"

    def test_collection_coach_brain_accepted(self) -> None:
        from app.schemas.rag import ChunkPayload, RetrievedContext

        ctx = RetrievedContext(
            chunk=ChunkPayload(**_make_chunk()),
            score=0.7,
            collection="coach_brain",
        )
        assert ctx.collection == "coach_brain"

    def test_invalid_collection_rejected(self) -> None:
        from app.schemas.rag import ChunkPayload, RetrievedContext

        with pytest.raises(ValidationError):
            RetrievedContext(
                chunk=ChunkPayload(**_make_chunk()),
                score=0.5,
                collection="unknown_store",
            )


# ---------------------------------------------------------------------------
# RetrievalResult
# ---------------------------------------------------------------------------


def _make_retrieved_context() -> object:
    from app.schemas.rag import ChunkPayload, RetrievedContext

    return RetrievedContext(
        chunk=ChunkPayload(**_make_chunk()),
        score=0.8,
        collection="papers_rag",
    )


class TestRetrievalResult:
    def test_round_trip_serialisation(self) -> None:
        from app.schemas.rag import RetrievalResult

        ctx = _make_retrieved_context()
        result = RetrievalResult(
            primary=[ctx],
            supplementary=[],
            retrieval_source="coach_brain_primary",
        )
        dumped = result.model_dump()
        assert len(dumped["primary"]) == 1
        assert dumped["supplementary"] == []
        assert dumped["retrieval_source"] == "coach_brain_primary"

    def test_all_retrieval_source_values_accepted(self) -> None:
        from app.schemas.rag import RetrievalResult

        for src in (
            "coach_brain_primary",
            "hybrid_brain_supplementary",
            "papers_only_fallback",
        ):
            r = RetrievalResult(primary=[], supplementary=[], retrieval_source=src)
            assert r.retrieval_source == src

    def test_invalid_retrieval_source_rejected(self) -> None:
        from app.schemas.rag import RetrievalResult

        with pytest.raises(ValidationError):
            RetrievalResult(
                primary=[],
                supplementary=[],
                retrieval_source="made_up_source",
            )

    def test_empty_lists_are_valid(self) -> None:
        from app.schemas.rag import RetrievalResult

        r = RetrievalResult(
            primary=[],
            supplementary=[],
            retrieval_source="papers_only_fallback",
        )
        assert r.primary == []
        assert r.supplementary == []


# ---------------------------------------------------------------------------
# CitationBlock
# ---------------------------------------------------------------------------


class TestCitationBlock:
    def _valid_citation(self) -> dict:
        return {
            "index": 1,
            "title": "Squat depth and activation",
            "authors": ["Smith J", "Jones A"],
            "year": 2022,
            "doi": "10.1234/citation",
            "chunk_text_excerpt": "At 90° knee flexion, VL activation peaked...",
        }

    def test_round_trip_serialisation(self) -> None:
        from app.schemas.rag import CitationBlock

        data = self._valid_citation()
        citation = CitationBlock(**data)
        dumped = citation.model_dump()
        assert dumped["index"] == 1
        assert dumped["doi"] == "10.1234/citation"
        assert len(dumped["chunk_text_excerpt"]) > 0

    def test_year_can_be_none(self) -> None:
        from app.schemas.rag import CitationBlock

        data = {**self._valid_citation(), "year": None}
        citation = CitationBlock(**data)
        assert citation.year is None

    def test_doi_can_be_none(self) -> None:
        from app.schemas.rag import CitationBlock

        data = {**self._valid_citation(), "doi": None}
        citation = CitationBlock(**data)
        assert citation.doi is None

    def test_authors_must_be_list(self) -> None:
        from app.schemas.rag import CitationBlock

        data = {**self._valid_citation(), "authors": "Smith J"}
        with pytest.raises(ValidationError):
            CitationBlock(**data)

    def test_index_is_positive_integer(self) -> None:
        from app.schemas.rag import CitationBlock

        citation = CitationBlock(**self._valid_citation())
        assert isinstance(citation.index, int)
        assert citation.index >= 1
