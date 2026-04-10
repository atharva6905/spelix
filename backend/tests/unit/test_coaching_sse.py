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
        mock_coaching_repo.get_by_analysis_id = AsyncMock(
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
        mock_coaching_repo.get_by_analysis_id = AsyncMock(
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
        """Streaming coaching should publish chunks to Redis pub/sub."""
        from app.config import ThresholdConfig
        from app.services.coaching import CoachingService

        mock_anthropic = MagicMock()
        mock_pubsub_redis = AsyncMock()
        mock_pubsub_redis.publish = AsyncMock()

        analysis_id = uuid4()

        # Mock the streaming context manager
        mock_text_stream = AsyncMock()

        async def text_iter():
            for chunk in ["Hello ", "world ", "coaching"]:
                yield chunk

        mock_text_stream.text_stream = text_iter()

        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_text_stream)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_anthropic.messages = MagicMock()
        mock_anthropic.messages.stream = MagicMock(return_value=mock_stream_cm)

        # Mock the instructor validation call
        from app.schemas.coaching import CoachingOutput

        mock_validated = CoachingOutput(
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

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(return_value=mock_validated)

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

        # Verify Redis publish was called for each chunk + done sentinel
        channel = f"coaching:{analysis_id}"
        publish_calls = mock_pubsub_redis.publish.call_args_list

        # 3 chunks + 1 done = 4 publish calls
        assert len(publish_calls) == 4

        # Check chunk messages
        for i, chunk_text in enumerate(["Hello ", "world ", "coaching"]):
            call_channel, call_data = publish_calls[i].args
            assert call_channel == channel
            parsed = json.loads(call_data)
            assert parsed["type"] == "chunk"
            assert parsed["text"] == chunk_text

        # Check done sentinel
        done_channel, done_data = publish_calls[3].args
        assert done_channel == channel
        assert json.loads(done_data)["type"] == "done"

    @pytest.mark.asyncio
    async def test_works_without_redis(self) -> None:
        """When pubsub_redis is None, should still work (skip publishing)."""
        from app.config import ThresholdConfig
        from app.services.coaching import CoachingService

        mock_anthropic = MagicMock()

        # Mock streaming
        mock_text_stream = AsyncMock()

        async def text_iter():
            yield "coaching output"

        mock_text_stream.text_stream = text_iter()

        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_text_stream)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_anthropic.messages = MagicMock()
        mock_anthropic.messages.stream = MagicMock(return_value=mock_stream_cm)

        from app.schemas.coaching import CoachingOutput

        mock_validated = CoachingOutput(
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

        mock_instructor = AsyncMock()
        mock_instructor.chat.completions.create = AsyncMock(return_value=mock_validated)

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
