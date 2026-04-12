"""
Unit tests for coaching SSE endpoint (FR-AICP-07).

Tests the SSE streaming endpoint and Redis pub/sub integration.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.v1.coaching_sse import _stream_from_pubsub, _stream_stored_output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coaching_result(*, stream_complete: bool = True) -> MagicMock:
    result = MagicMock()
    result.stream_complete = stream_complete
    result.structured_output_json = {
        "summary": "Good session.",
        "strengths": ["Solid depth"],
        "issues": [],
        "correction_plan": ["Keep knees tracking."],
        "disclaimer": "This feedback is for educational purposes only.",
        "raw_prompt_tokens": 300,
        "raw_completion_tokens": 180,
    }
    return result


# ---------------------------------------------------------------------------
# _stream_stored_output tests
# ---------------------------------------------------------------------------


class TestStreamStoredOutput:
    @pytest.mark.asyncio
    async def test_yields_complete_event(self) -> None:
        """Stored output should yield a single 'complete' SSE event."""
        coaching = _make_coaching_result()
        events: list[str] = []
        async for event in _stream_stored_output(coaching):
            events.append(event)

        assert len(events) == 1
        assert events[0].startswith("event: complete\n")
        # Parse the data portion
        data_line = events[0].split("data: ", 1)[1].strip()
        parsed = json.loads(data_line)
        assert parsed["summary"] == "Good session."


# ---------------------------------------------------------------------------
# _stream_from_pubsub tests
# ---------------------------------------------------------------------------


class TestStreamFromPubsub:
    @pytest.mark.asyncio
    async def test_streams_chunks_then_done(self) -> None:
        """Pub/sub chunks forwarded as SSE data events, done triggers complete."""
        analysis_id = uuid4()
        channel = f"coaching:{analysis_id}"

        # Mock Redis pubsub
        mock_pubsub = AsyncMock()

        async def mock_listen():
            messages = [
                {"type": "subscribe", "data": 1},
                {"type": "message", "data": json.dumps({"type": "chunk", "text": "Hello "})},
                {"type": "message", "data": json.dumps({"type": "chunk", "text": "world"})},
                {"type": "message", "data": json.dumps({"type": "done"})},
            ]
            for msg in messages:
                yield msg

        mock_pubsub.listen = mock_listen
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Mock coaching repo — no existing result on first check, then has result on done
        mock_coaching_repo = AsyncMock()
        mock_coaching_repo.get_by_analysis = AsyncMock(
            side_effect=[None, _make_coaching_result()]
        )

        events: list[str] = []
        async for event in _stream_from_pubsub(
            channel, mock_redis, mock_coaching_repo, analysis_id
        ):
            events.append(event)

        # Should have 2 chunk events + 1 complete event
        assert len(events) == 3
        assert '"text": "Hello "' in events[0]
        assert '"text": "world"' in events[1]
        assert "event: complete" in events[2]

    @pytest.mark.asyncio
    async def test_returns_stored_if_complete_during_subscribe(self) -> None:
        """If coaching completes between subscribe and check, return stored output."""
        analysis_id = uuid4()
        channel = f"coaching:{analysis_id}"

        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Coaching already complete when we check
        mock_coaching_repo = AsyncMock()
        mock_coaching_repo.get_by_analysis = AsyncMock(
            return_value=_make_coaching_result(stream_complete=True)
        )

        events: list[str] = []
        async for event in _stream_from_pubsub(
            channel, mock_redis, mock_coaching_repo, analysis_id
        ):
            events.append(event)

        assert len(events) == 1
        assert "event: complete" in events[0]


# ---------------------------------------------------------------------------
# Streaming coaching method tests
# ---------------------------------------------------------------------------


class TestGenerateCoachingStreaming:
    @pytest.mark.asyncio
    async def test_publishes_chunks_to_redis(self) -> None:
        """Streaming coaching should publish chunks to Redis pub/sub.

        D-001 refactored streaming to use instructor.create_partial which yields
        progressively-complete partial CoachingOutput snapshots.  The mock must
        return an async iterable of partial models.
        """
        from app.config import ThresholdConfig
        from app.services.coaching import CoachingService

        mock_anthropic = MagicMock()
        mock_pubsub_redis = AsyncMock()
        mock_pubsub_redis.publish = AsyncMock()

        analysis_id = uuid4()

        from app.schemas.coaching import CoachingOutput

        # Build progressively-complete partial snapshots that instructor
        # create_partial would yield.  Each snapshot adds more fields.
        partial_1 = CoachingOutput(
            summary="Good",
            strengths=["Depth"],
            issues=[],
            correction_plan=["Cue"],
            disclaimer="d",
            raw_prompt_tokens=0,
            raw_completion_tokens=0,
        )
        partial_2 = CoachingOutput(
            summary="Good session.",
            strengths=["Solid depth"],
            issues=[],
            correction_plan=["Keep tracking"],
            disclaimer="d",
            raw_prompt_tokens=0,
            raw_completion_tokens=0,
        )
        final = CoachingOutput(
            summary="Good session.",
            strengths=["Solid depth"],
            issues=[],
            correction_plan=["Keep knees tracking."],
            disclaimer=(
                "This feedback is for educational purposes only and is not a "
                "substitute for in-person coaching or medical advice."
            ),
            raw_prompt_tokens=400,
            raw_completion_tokens=200,
        )

        async def partial_iter():
            for snapshot in [partial_1, partial_2, final]:
                yield snapshot

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create_partial = MagicMock(
            return_value=partial_iter()
        )

        with patch("app.services.coaching.instructor") as mock_mod:
            mock_mod.from_anthropic.return_value = mock_instructor

            svc = CoachingService(anthropic_client=mock_anthropic)
            result = await svc.generate_coaching_streaming(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=[{"rep_number": 1}],
                confidence_score=0.85,
                thresholds=ThresholdConfig(),
                analysis_id=analysis_id,
                pubsub_redis=mock_pubsub_redis,
            )

        assert isinstance(result, CoachingOutput)
        assert result.summary == "Good session."

        # Verify Redis publish was called for chunk deltas + done sentinel
        channel = f"coaching:{analysis_id}"
        publish_calls = mock_pubsub_redis.publish.call_args_list

        # Each partial snapshot that produces a JSON delta → chunk publish,
        # plus 1 done sentinel at the end.
        assert len(publish_calls) >= 2  # at least 1 chunk + 1 done

        # Last publish must be the done sentinel
        last_channel, last_data = publish_calls[-1].args
        assert last_channel == channel
        parsed_last = json.loads(last_data)
        assert parsed_last["type"] == "done"

        # All non-done publishes must be chunk type
        for call in publish_calls[:-1]:
            call_channel, call_data = call.args
            assert call_channel == channel
            parsed = json.loads(call_data)
            assert parsed["type"] == "chunk"

    @pytest.mark.asyncio
    async def test_works_without_redis(self) -> None:
        """When pubsub_redis is None, should still work (skip publishing)."""
        from app.config import ThresholdConfig
        from app.services.coaching import CoachingService

        mock_anthropic = MagicMock()

        from app.schemas.coaching import CoachingOutput

        final = CoachingOutput(
            summary="Good session.",
            strengths=["Solid depth"],
            issues=[],
            correction_plan=["Keep knees tracking."],
            disclaimer=(
                "This feedback is for educational purposes only and is not a "
                "substitute for in-person coaching or medical advice."
            ),
            raw_prompt_tokens=400,
            raw_completion_tokens=200,
        )

        async def partial_iter():
            yield final

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create_partial = MagicMock(
            return_value=partial_iter()
        )

        with patch("app.services.coaching.instructor") as mock_mod:
            mock_mod.from_anthropic.return_value = mock_instructor

            svc = CoachingService(anthropic_client=mock_anthropic)
            result = await svc.generate_coaching_streaming(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=[],
                confidence_score=0.85,
                thresholds=ThresholdConfig(),
                pubsub_redis=None,
            )

        assert isinstance(result, CoachingOutput)
