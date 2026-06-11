"""Tests for IngestionService — document ingestion pipeline.

TDD gate for P2-004 (FR-AICP-09, FR-RAGK-01).

Covers:
1. Chunking: 500-token chunks with 50-token overlap, section-aware
2. Point ID determinism: same (paper_id, chunk_index) → same UUID
3. Idempotency: re-ingest produces same point IDs
4. Status guard: reject documents that are not reviewed_approved
5. ChunkPayload construction with all metadata fields
6. End-to-end ingest with mocked Cohere + Qdrant
7. Batch embed called with input_type=SEARCH_DOCUMENT
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ingestion import (
    DocumentMetadata,
    IngestionResult,
    IngestionService,
    _chunk_text,
    _make_point_id,
    _section_chunks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_METADATA = DocumentMetadata(
    title="Effects of squat depth on knee torque",
    authors=["Smith J", "Lee K"],
    year=2022,
    doi="10.1234/test.doi",
    quality_tier="L1_systematic_review",
    review_status="reviewed_approved",
)

SHORT_TEXT = "The quick brown fox jumped over the lazy dog. " * 5  # ~50 tokens

# 600 words → roughly 600 tokens → should produce 2 chunks with 500/50 settings
LONG_TEXT = " ".join(["word"] * 600)


# ---------------------------------------------------------------------------
# Unit: _make_point_id
# ---------------------------------------------------------------------------


class TestMakePointId:
    def test_deterministic_same_inputs(self) -> None:
        uid1 = _make_point_id("paper-abc", 0)
        uid2 = _make_point_id("paper-abc", 0)
        assert uid1 == uid2

    def test_different_chunk_index_gives_different_id(self) -> None:
        uid0 = _make_point_id("paper-abc", 0)
        uid1 = _make_point_id("paper-abc", 1)
        assert uid0 != uid1

    def test_different_paper_id_gives_different_id(self) -> None:
        uid_a = _make_point_id("paper-abc", 0)
        uid_b = _make_point_id("paper-xyz", 0)
        assert uid_a != uid_b

    def test_returns_uuid_string(self) -> None:
        uid = _make_point_id("paper-abc", 3)
        # Must be a valid UUID string
        parsed = uuid.UUID(uid)
        assert str(parsed) == uid

    def test_derives_from_sha256(self) -> None:
        raw = hashlib.sha256(b"paper-abc:2").hexdigest()
        expected = str(uuid.UUID(raw[:32]))
        assert _make_point_id("paper-abc", 2) == expected


# ---------------------------------------------------------------------------
# Unit: _chunk_text
# ---------------------------------------------------------------------------


class TestChunkText:
    def test_short_text_is_single_chunk(self) -> None:
        chunks = _chunk_text(SHORT_TEXT, max_tokens=500, overlap_tokens=50)
        assert len(chunks) == 1
        assert chunks[0] == SHORT_TEXT.strip()

    def test_long_text_produces_multiple_chunks(self) -> None:
        chunks = _chunk_text(LONG_TEXT, max_tokens=500, overlap_tokens=50)
        assert len(chunks) >= 2

    def test_each_chunk_within_token_limit(self) -> None:
        chunks = _chunk_text(LONG_TEXT, max_tokens=500, overlap_tokens=50)
        for chunk in chunks:
            # Whitespace-split approximation
            token_count = len(chunk.split())
            assert token_count <= 500

    def test_overlap_tokens_present_between_adjacent_chunks(self) -> None:
        # Use a text long enough for 3+ chunks
        very_long = " ".join([f"word{i}" for i in range(1200)])
        chunks = _chunk_text(very_long, max_tokens=500, overlap_tokens=50)
        assert len(chunks) >= 3
        # Last 50 tokens of chunk N should appear at the start of chunk N+1
        for i in range(len(chunks) - 1):
            tail_tokens = chunks[i].split()[-50:]
            head_tokens = chunks[i + 1].split()[:50]
            # At least some overlap tokens should match
            assert tail_tokens == head_tokens

    def test_empty_text_returns_empty_list(self) -> None:
        chunks = _chunk_text("", max_tokens=500, overlap_tokens=50)
        assert chunks == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        chunks = _chunk_text("   \n\t  ", max_tokens=500, overlap_tokens=50)
        assert chunks == []


# ---------------------------------------------------------------------------
# Unit: _section_chunks
# ---------------------------------------------------------------------------


class TestSectionChunks:
    def test_no_sections_falls_back_to_full_text(self) -> None:
        results = _section_chunks(SHORT_TEXT, sections=None, max_tokens=500, overlap_tokens=50)
        assert len(results) >= 1
        # Each result is (section_name, chunk_text)
        section, chunk = results[0]
        assert section is None

    def test_sections_labelled_correctly(self) -> None:
        sections = {
            "abstract": "Abstract text about squat depth.",
            "methods": "Methods used participants n=20.",
        }
        results = _section_chunks("full text fallback", sections=sections, max_tokens=500, overlap_tokens=50)
        section_names = {s for s, _ in results}
        assert "abstract" in section_names
        assert "methods" in section_names

    def test_section_not_split_if_under_limit(self) -> None:
        sections = {"abstract": SHORT_TEXT}
        results = _section_chunks("ignored", sections=sections, max_tokens=500, overlap_tokens=50)
        abstract_chunks = [(s, c) for s, c in results if s == "abstract"]
        assert len(abstract_chunks) == 1

    def test_large_section_is_chunked(self) -> None:
        sections = {"methods": LONG_TEXT}
        results = _section_chunks("ignored", sections=sections, max_tokens=500, overlap_tokens=50)
        methods_chunks = [(s, c) for s, c in results if s == "methods"]
        assert len(methods_chunks) >= 2


# ---------------------------------------------------------------------------
# Unit: ChunkPayload construction (via IngestionService._build_payloads)
# ---------------------------------------------------------------------------


class TestChunkPayloadConstruction:
    def test_payload_has_all_required_fields(self) -> None:
        mock_cohere = MagicMock()
        mock_qdrant = MagicMock()
        svc = IngestionService(cohere_client=mock_cohere, qdrant_client=mock_qdrant)

        section_text_pairs = [(None, "Chunk text content")]
        payloads = svc._build_payloads(
            paper_id="paper-001",
            section_text_pairs=section_text_pairs,
            metadata=SAMPLE_METADATA,
        )

        assert len(payloads) == 1
        p = payloads[0]
        assert p.paper_id == "paper-001"
        assert p.chunk_index == 0
        assert p.text == "Chunk text content"
        assert p.title == SAMPLE_METADATA.title
        assert p.authors == SAMPLE_METADATA.authors
        assert p.year == SAMPLE_METADATA.year
        assert p.doi == SAMPLE_METADATA.doi
        assert p.quality_tier == SAMPLE_METADATA.quality_tier
        assert p.section is None
        assert p.token_count == len("Chunk text content".split())

    def test_payload_id_is_deterministic_point_id(self) -> None:
        mock_cohere = MagicMock()
        mock_qdrant = MagicMock()
        svc = IngestionService(cohere_client=mock_cohere, qdrant_client=mock_qdrant)

        pairs = [(None, "chunk A"), ("methods", "chunk B")]
        payloads = svc._build_payloads("paper-002", pairs, SAMPLE_METADATA)

        assert payloads[0].id == _make_point_id("paper-002", 0)
        assert payloads[1].id == _make_point_id("paper-002", 1)

    def test_section_label_preserved_in_payload(self) -> None:
        mock_cohere = MagicMock()
        mock_qdrant = MagicMock()
        svc = IngestionService(cohere_client=mock_cohere, qdrant_client=mock_qdrant)

        pairs = [("results", "Result text here")]
        payloads = svc._build_payloads("paper-003", pairs, SAMPLE_METADATA)
        assert payloads[0].section == "results"

    def test_exercise_and_sex_applicability_stamped_on_payloads(self) -> None:
        """Issue #222 (FR-RAGK-02 ext., FR-AICP-12): every ChunkPayload carries the
        exercise list and sex_applicability from DocumentMetadata, and both keys
        survive model_dump() (the dict actually upserted to Qdrant)."""
        mock_cohere = MagicMock()
        mock_qdrant = MagicMock()
        svc = IngestionService(cohere_client=mock_cohere, qdrant_client=mock_qdrant)

        metadata = DocumentMetadata(
            title="Female-specific squat mechanics",
            authors=["Doe J"],
            year=2023,
            doi=None,
            quality_tier="L2_rct",
            review_status="reviewed_approved",
            exercise_tags=["squat"],
            sex_applicability="female",
        )

        pairs = [(None, "chunk A"), ("methods", "chunk B")]
        payloads = svc._build_payloads("paper-sex", pairs, metadata)

        for p in payloads:
            assert p.exercise == ["squat"]
            assert p.sex_applicability == "female"
            dumped = p.model_dump()
            assert dumped["exercise"] == ["squat"]
            assert dumped["sex_applicability"] == "female"

    def test_exercise_and_sex_applicability_default_when_unset(self) -> None:
        """DocumentMetadata defaults: exercise_tags=[] and sex_applicability='both'."""
        mock_cohere = MagicMock()
        mock_qdrant = MagicMock()
        svc = IngestionService(cohere_client=mock_cohere, qdrant_client=mock_qdrant)

        pairs = [(None, "chunk")]
        payloads = svc._build_payloads("paper-default", pairs, SAMPLE_METADATA)
        assert payloads[0].exercise == []
        assert payloads[0].sex_applicability == "both"


# ---------------------------------------------------------------------------
# Integration: IngestionService.ingest_document — status guard
# ---------------------------------------------------------------------------


class TestStatusGuard:
    @pytest.mark.asyncio
    async def test_rejects_pending_review_document(self) -> None:
        mock_cohere = AsyncMock()
        mock_qdrant = AsyncMock()
        svc = IngestionService(cohere_client=mock_cohere, qdrant_client=mock_qdrant)

        bad_metadata = DocumentMetadata(
            title="Pending doc",
            authors=["Author A"],
            year=2021,
            doi=None,
            quality_tier="L2_rct",
            review_status="pending_review",
        )

        with pytest.raises(ValueError, match="reviewed_approved"):
            await svc.ingest_document(
                paper_id="paper-bad",
                text=SHORT_TEXT,
                metadata=bad_metadata,
            )

    @pytest.mark.asyncio
    async def test_rejects_reviewed_rejected_document(self) -> None:
        mock_cohere = AsyncMock()
        mock_qdrant = AsyncMock()
        svc = IngestionService(cohere_client=mock_cohere, qdrant_client=mock_qdrant)

        bad_metadata = DocumentMetadata(
            title="Rejected doc",
            authors=["Author B"],
            year=2020,
            doi=None,
            quality_tier="L3_observational",
            review_status="reviewed_rejected",
        )

        with pytest.raises(ValueError, match="reviewed_approved"):
            await svc.ingest_document(
                paper_id="paper-rejected",
                text=SHORT_TEXT,
                metadata=bad_metadata,
            )

    @pytest.mark.asyncio
    async def test_rejects_needs_revision_document(self) -> None:
        mock_cohere = AsyncMock()
        mock_qdrant = AsyncMock()
        svc = IngestionService(cohere_client=mock_cohere, qdrant_client=mock_qdrant)

        bad_metadata = DocumentMetadata(
            title="Needs revision doc",
            authors=["Author C"],
            year=2019,
            doi=None,
            quality_tier="L4_guideline",
            review_status="needs_revision",
        )

        with pytest.raises(ValueError, match="reviewed_approved"):
            await svc.ingest_document(
                paper_id="paper-needs-rev",
                text=SHORT_TEXT,
                metadata=bad_metadata,
            )

    @pytest.mark.asyncio
    async def test_cohere_not_called_when_guard_rejects(self) -> None:
        mock_cohere = AsyncMock()
        mock_qdrant = AsyncMock()
        svc = IngestionService(cohere_client=mock_cohere, qdrant_client=mock_qdrant)

        bad_metadata = DocumentMetadata(
            title="Pending doc",
            authors=[],
            year=None,
            doi=None,
            quality_tier="L2_rct",
            review_status="pending_review",
        )

        with pytest.raises(ValueError):
            await svc.ingest_document("paper-x", SHORT_TEXT, bad_metadata)

        mock_cohere.embed_batch.assert_not_called()
        mock_qdrant.upsert_points.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: IngestionService.ingest_document — happy path
# ---------------------------------------------------------------------------


class TestIngestDocumentHappyPath:
    def _make_service(
        self, embed_return: list[list[float]] | None = None
    ) -> tuple[IngestionService, MagicMock, MagicMock]:
        mock_cohere = AsyncMock()
        mock_qdrant = AsyncMock()

        # Default: return 1024-dim zero vectors
        if embed_return is None:
            embed_return = [[0.0] * 1024]
        mock_cohere.embed_batch = AsyncMock(return_value=embed_return)
        mock_qdrant.upsert_points = AsyncMock(return_value=None)

        svc = IngestionService(cohere_client=mock_cohere, qdrant_client=mock_qdrant)
        return svc, mock_cohere, mock_qdrant

    @pytest.mark.asyncio
    async def test_returns_ingestion_result(self) -> None:
        svc, _, _ = self._make_service([[0.0] * 1024])
        result = await svc.ingest_document(
            paper_id="paper-001",
            text=SHORT_TEXT,
            metadata=SAMPLE_METADATA,
        )
        assert isinstance(result, IngestionResult)

    @pytest.mark.asyncio
    async def test_result_contains_chunk_count(self) -> None:
        svc, _, _ = self._make_service([[0.0] * 1024])
        result = await svc.ingest_document(
            paper_id="paper-001",
            text=SHORT_TEXT,
            metadata=SAMPLE_METADATA,
        )
        assert result.chunk_count >= 1

    @pytest.mark.asyncio
    async def test_embed_called_with_search_document_input_type(self) -> None:
        svc, mock_cohere, _ = self._make_service([[0.0] * 1024])
        await svc.ingest_document(
            paper_id="paper-001",
            text=SHORT_TEXT,
            metadata=SAMPLE_METADATA,
        )
        # embed_batch must have been called
        mock_cohere.embed_batch.assert_called_once()
        call_kwargs = mock_cohere.embed_batch.call_args

        from app.services.cohere_client import EmbedInputType

        # input_type must be SEARCH_DOCUMENT
        assert call_kwargs.kwargs.get("input_type") == EmbedInputType.SEARCH_DOCUMENT

    @pytest.mark.asyncio
    async def test_qdrant_upsert_called_with_papers_rag_collection(self) -> None:
        svc, _, mock_qdrant = self._make_service([[0.0] * 1024])
        await svc.ingest_document(
            paper_id="paper-001",
            text=SHORT_TEXT,
            metadata=SAMPLE_METADATA,
        )
        mock_qdrant.upsert_points.assert_called_once()
        upsert_args = mock_qdrant.upsert_points.call_args
        assert upsert_args.kwargs.get("collection") == "papers_rag" or upsert_args.args[0] == "papers_rag"

    @pytest.mark.asyncio
    async def test_point_ids_are_deterministic(self) -> None:
        """Same paper_id + text must produce same Qdrant point IDs on re-ingest."""
        svc, _, mock_qdrant = self._make_service([[0.0] * 1024])

        # First ingest
        await svc.ingest_document("paper-idem", SHORT_TEXT, SAMPLE_METADATA)
        first_call_points = mock_qdrant.upsert_points.call_args

        # Reset mock and re-ingest
        mock_qdrant.upsert_points.reset_mock()
        await svc.ingest_document("paper-idem", SHORT_TEXT, SAMPLE_METADATA)
        second_call_points = mock_qdrant.upsert_points.call_args

        # Extract the points list from both calls
        first_points = first_call_points.kwargs.get("points") or first_call_points.args[1]
        second_points = second_call_points.kwargs.get("points") or second_call_points.args[1]

        first_ids = {p.id for p in first_points}
        second_ids = {p.id for p in second_points}
        assert first_ids == second_ids

    @pytest.mark.asyncio
    async def test_with_sections_metadata_is_attached(self) -> None:
        svc, _, mock_qdrant = self._make_service([[0.0] * 1024, [0.0] * 1024])
        sections = {
            "abstract": "Brief abstract about study.",
            "methods": "Participants were n=30.",
        }
        result = await svc.ingest_document(
            paper_id="paper-sec",
            text="fallback full text",
            metadata=SAMPLE_METADATA,
            sections=sections,
        )
        assert result.chunk_count == 2

        upsert_args = mock_qdrant.upsert_points.call_args
        points = upsert_args.kwargs.get("points") or upsert_args.args[1]
        section_names = {p.payload["section"] for p in points if p.payload.get("section")}
        assert section_names == {"abstract", "methods"}

    @pytest.mark.asyncio
    async def test_long_text_produces_multiple_chunks_and_vectors(self) -> None:
        # Use side_effect to return exactly as many vectors as texts requested
        def _embed_side_effect(texts: list[str], *, input_type: Any) -> list[list[float]]:
            return [[0.0] * 1024 for _ in texts]

        mock_cohere = AsyncMock()
        mock_qdrant = AsyncMock()
        mock_cohere.embed_batch = AsyncMock(side_effect=_embed_side_effect)
        mock_qdrant.upsert_points = AsyncMock(return_value=None)
        svc = IngestionService(cohere_client=mock_cohere, qdrant_client=mock_qdrant)

        result = await svc.ingest_document(
            paper_id="paper-long",
            text=LONG_TEXT,
            metadata=SAMPLE_METADATA,
        )
        assert result.chunk_count >= 2

        upsert_args = mock_qdrant.upsert_points.call_args
        points = upsert_args.kwargs.get("points") or upsert_args.args[1]
        assert len(points) >= 2

    @pytest.mark.asyncio
    async def test_result_paper_id_matches_input(self) -> None:
        svc, _, _ = self._make_service([[0.0] * 1024])
        result = await svc.ingest_document("paper-xyz", SHORT_TEXT, SAMPLE_METADATA)
        assert result.paper_id == "paper-xyz"

    @pytest.mark.asyncio
    async def test_result_point_ids_are_valid_uuids(self) -> None:
        svc, _, _ = self._make_service([[0.0] * 1024])
        result = await svc.ingest_document("paper-001", SHORT_TEXT, SAMPLE_METADATA)
        for pid in result.point_ids:
            # Must not raise
            uuid.UUID(pid)
