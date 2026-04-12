"""Tests for BrainEmbeddingService (P2-024, FR-BRAIN-03).

TDD gate — these tests are written before the implementation.

Covers:
1. build_contextual_text: exercise/phase/type prefix format
2. build_contextual_text: None phase → uses "general"
3. embed_and_upsert: calls Cohere with SEARCH_DOCUMENT input type
4. embed_and_upsert: constructs CoachBrainPayload correctly (raw content stored)
5. embed_and_upsert: upserts to "coach_brain" collection
6. embed_and_upsert_batch: embeds all entries in one batch call
7. embed_and_upsert: point ID is str(entry.id)

All Cohere and Qdrant calls are mocked — no real API calls in unit tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock


from app.schemas.coach_brain import CoachBrainEntry, CoachBrainEntryCreate
from app.services.brain_embedding import BrainEmbeddingService
from app.services.cohere_client import EmbedInputType
from app.services.qdrant import COLLECTION_COACH_BRAIN


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_entry(
    *,
    exercise: str = "squat",
    phase: str = "descent",
    entry_type: str = "cue",
    content: str = "Keep your chest up through the descent.",
    status: str = "active",
    confirmation_count: int = 3,
    trigger_tags: list[str] | None = None,
    entry_id: uuid.UUID | None = None,
) -> CoachBrainEntry:
    return CoachBrainEntry(
        id=entry_id or uuid.uuid4(),
        content=content,
        exercise=exercise,  # type: ignore[arg-type]
        phase=phase,  # type: ignore[arg-type]
        entry_type=entry_type,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        confirmation_count=confirmation_count,
        source_analysis_ids=[],
        trigger_tags=trigger_tags or ["forward_lean"],
        confidence_score=0.85,
        metadata={},
        created_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
    )


def _make_service(
    *,
    vectors: list[list[float]] | None = None,
) -> tuple[BrainEmbeddingService, MagicMock, MagicMock]:
    """Return (service, mock_cohere_client, mock_qdrant_client)."""
    mock_cohere = MagicMock()
    # Default: return a single 1024-dim vector
    default_vectors = vectors or [[0.1] * 1024]
    mock_cohere.embed_batch = AsyncMock(return_value=default_vectors)

    mock_qdrant = MagicMock()
    mock_qdrant.upsert_points = AsyncMock(return_value=None)

    service = BrainEmbeddingService(
        cohere_client=mock_cohere,
        qdrant_client=mock_qdrant,
    )
    return service, mock_cohere, mock_qdrant


# ---------------------------------------------------------------------------
# Test 1 — build_contextual_text: correct format with exercise/phase/type
# ---------------------------------------------------------------------------


def test_build_contextual_text_format() -> None:
    """Contextual text must follow 'exercise:X phase:Y type:Z\ncontent' format."""
    service, _, _ = _make_service()
    entry = _make_entry(exercise="squat", phase="descent", entry_type="cue",
                        content="Keep your chest up.")

    result = service.build_contextual_text(entry)

    assert result == "exercise:squat phase:descent type:cue\nKeep your chest up."


# ---------------------------------------------------------------------------
# Test 2 — build_contextual_text: None phase uses "general"
# ---------------------------------------------------------------------------


def test_build_contextual_text_none_phase_uses_general() -> None:
    """When phase is None (CoachBrainEntryCreate), prefix uses 'general'."""
    service, _, _ = _make_service()
    create_entry = CoachBrainEntryCreate(
        content="Brace your core before initiating the pull.",
        exercise="deadlift",
        phase=None,
        entry_type="principle",
    )

    result = service.build_contextual_text(create_entry)

    assert result == "exercise:deadlift phase:general type:principle\nBrace your core before initiating the pull."


# ---------------------------------------------------------------------------
# Test 3 — embed_and_upsert: calls Cohere with SEARCH_DOCUMENT input type
# ---------------------------------------------------------------------------


async def test_embed_and_upsert_calls_cohere_search_document() -> None:
    """embed_and_upsert must call embed_batch with input_type=SEARCH_DOCUMENT."""
    service, mock_cohere, _ = _make_service()
    entry = _make_entry()

    await service.embed_and_upsert(entry)

    mock_cohere.embed_batch.assert_called_once()
    call_kwargs = mock_cohere.embed_batch.call_args
    # Positional: texts list; keyword: input_type
    assert call_kwargs.kwargs["input_type"] == EmbedInputType.SEARCH_DOCUMENT


# ---------------------------------------------------------------------------
# Test 4 — embed_and_upsert: CoachBrainPayload stores RAW content (not contextual)
# ---------------------------------------------------------------------------


async def test_embed_and_upsert_payload_stores_raw_content() -> None:
    """CoachBrainPayload.content must be the RAW entry content, not the contextual text.

    The contextual text (with exercise/phase/type prefix) is used ONLY for
    embedding. The payload in Qdrant stores the original content for display.
    """
    raw_content = "Keep your chest up through the descent."
    service, _, mock_qdrant = _make_service()
    entry = _make_entry(content=raw_content, exercise="squat", phase="descent",
                        entry_type="cue")

    await service.embed_and_upsert(entry)

    mock_qdrant.upsert_points.assert_called_once()
    call_args = mock_qdrant.upsert_points.call_args
    points = call_args.kwargs.get("points") or call_args.args[1]
    assert len(points) == 1
    payload = points[0].payload
    # Raw content, not "exercise:squat phase:descent type:cue\nKeep your..."
    assert payload["content"] == raw_content
    assert "exercise:squat" not in payload["content"]


# ---------------------------------------------------------------------------
# Test 5 — embed_and_upsert: upserts to COLLECTION_COACH_BRAIN
# ---------------------------------------------------------------------------


async def test_embed_and_upsert_targets_coach_brain_collection() -> None:
    """Upsert must go to the 'coach_brain' collection constant."""
    service, _, mock_qdrant = _make_service()
    entry = _make_entry()

    await service.embed_and_upsert(entry)

    mock_qdrant.upsert_points.assert_called_once()
    call_args = mock_qdrant.upsert_points.call_args
    collection_arg = call_args.kwargs.get("collection") or call_args.args[0]
    assert collection_arg == COLLECTION_COACH_BRAIN


# ---------------------------------------------------------------------------
# Test 6 — embed_and_upsert_batch: all entries embedded in one batch call
# ---------------------------------------------------------------------------


async def test_embed_and_upsert_batch_single_embed_call() -> None:
    """embed_and_upsert_batch must call embed_batch ONCE for all entries."""
    n = 3
    vectors = [[float(i)] * 1024 for i in range(n)]
    service, mock_cohere, mock_qdrant = _make_service(vectors=vectors)
    entries = [
        _make_entry(exercise="squat", content=f"Cue {i}") for i in range(n)
    ]

    ids = await service.embed_and_upsert_batch(entries)

    # Single embed_batch call with all contextual texts
    mock_cohere.embed_batch.assert_called_once()
    texts_arg = mock_cohere.embed_batch.call_args.args[0]
    assert len(texts_arg) == n

    # Single upsert call with all points
    mock_qdrant.upsert_points.assert_called_once()
    points_arg = (
        mock_qdrant.upsert_points.call_args.kwargs.get("points")
        or mock_qdrant.upsert_points.call_args.args[1]
    )
    assert len(points_arg) == n

    # Returns one ID per entry
    assert len(ids) == n


# ---------------------------------------------------------------------------
# Test 7 — embed_and_upsert: point ID is str(entry.id)
# ---------------------------------------------------------------------------


async def test_embed_and_upsert_point_id_is_string_of_uuid() -> None:
    """Qdrant PointStruct ID must be str(entry.id) — UUID as a string."""
    entry_id = uuid.uuid4()
    service, _, mock_qdrant = _make_service()
    entry = _make_entry(entry_id=entry_id)

    returned_id = await service.embed_and_upsert(entry)

    mock_qdrant.upsert_points.assert_called_once()
    call_args = mock_qdrant.upsert_points.call_args
    points = call_args.kwargs.get("points") or call_args.args[1]
    assert points[0].id == str(entry_id)
    # Return value also matches
    assert returned_id == str(entry_id)


# ---------------------------------------------------------------------------
# Test 8 — embed_and_upsert: contextual text (not raw content) is embedded
# ---------------------------------------------------------------------------


async def test_embed_and_upsert_embeds_contextual_text_not_raw() -> None:
    """The text passed to embed_batch must include the exercise/phase/type prefix."""
    service, mock_cohere, _ = _make_service()
    entry = _make_entry(
        exercise="bench",
        phase="bottom",
        entry_type="correction",
        content="Touch the bar to your sternum.",
    )

    await service.embed_and_upsert(entry)

    texts = mock_cohere.embed_batch.call_args.args[0]
    assert len(texts) == 1
    assert texts[0] == "exercise:bench phase:bottom type:correction\nTouch the bar to your sternum."


# ---------------------------------------------------------------------------
# Test 9 — embed_and_upsert: CoachBrainPayload fields match entry fields
# ---------------------------------------------------------------------------


async def test_embed_and_upsert_payload_fields_match_entry() -> None:
    """All CoachBrainPayload fields must come from the source entry."""
    entry_id = uuid.uuid4()
    service, _, mock_qdrant = _make_service()
    entry = _make_entry(
        entry_id=entry_id,
        exercise="deadlift",
        phase="ascent",
        entry_type="drill",
        content="Drive the floor away with your legs.",
        status="active",
        confirmation_count=7,
        trigger_tags=["slow_ascent"],
    )

    await service.embed_and_upsert(entry)

    call_args = mock_qdrant.upsert_points.call_args
    points = call_args.kwargs.get("points") or call_args.args[1]
    payload = points[0].payload

    assert payload["id"] == str(entry_id)
    assert payload["exercise"] == "deadlift"
    assert payload["phase"] == "ascent"
    assert payload["entry_type"] == "drill"
    assert payload["status"] == "active"
    assert payload["confirmation_count"] == 7
    assert payload["trigger_tags"] == ["slow_ascent"]
