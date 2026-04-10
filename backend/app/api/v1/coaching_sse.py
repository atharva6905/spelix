"""SSE streaming endpoint for coaching output (FR-AICP-07).

GET /api/v1/analyses/{analysis_id}/coaching/stream

Streams coaching output to the client via Server-Sent Events.

Architecture:
    - Worker generates coaching via Claude streaming, publishes chunks
      to Redis pub/sub channel ``coaching:{analysis_id}``.
    - This endpoint subscribes to that channel and forwards chunks as SSE.
    - If coaching is already complete (stream_complete=True), sends the
      stored output as a single event and closes.
    - Race prevention: subscribe to Redis BEFORE checking stream_complete.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_redis
from app.db import get_db
from app.repositories.analysis import AnalysisRepository
from app.repositories.coaching_result import CoachingResultRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["coaching"])


async def _stream_stored_output(coaching_result: Any) -> AsyncGenerator[str, None]:
    """Yield stored coaching output as a single SSE event."""
    payload = json.dumps(coaching_result.structured_output_json)
    yield f"event: complete\ndata: {payload}\n\n"


async def _stream_from_pubsub(
    channel: str,
    redis: Any,
    coaching_repo: CoachingResultRepository,
    analysis_id: UUID,
) -> AsyncGenerator[str, None]:
    """Subscribe to Redis pub/sub and forward coaching chunks as SSE events.

    Race prevention: we subscribe BEFORE checking stream_complete. If coaching
    finished between subscribe and check, we catch it in the DB check and
    return stored output instead.
    """
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        # Check if coaching completed while we were subscribing
        existing = await coaching_repo.get_by_analysis_id(analysis_id)
        if existing and existing.stream_complete:
            payload = json.dumps(existing.structured_output_json)
            yield f"event: complete\ndata: {payload}\n\n"
            return

        # Stream from pub/sub
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            data = json.loads(message["data"])
            msg_type = data.get("type")

            if msg_type == "done":
                # Fetch final validated output from DB
                final = await coaching_repo.get_by_analysis_id(analysis_id)
                if final and final.structured_output_json:
                    payload = json.dumps(final.structured_output_json)
                    yield f"event: complete\ndata: {payload}\n\n"
                else:
                    yield "event: done\ndata: {}\n\n"
                break
            elif msg_type == "chunk":
                chunk_payload = json.dumps({"text": data["text"]})
                yield f"data: {chunk_payload}\n\n"
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


@router.get("/{analysis_id}/coaching/stream")
async def stream_coaching(
    analysis_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> StreamingResponse:
    """Stream coaching output for an analysis via SSE.

    - If coaching is already complete, sends stored output as single event.
    - Otherwise, subscribes to Redis pub/sub and forwards chunks.
    - Requires authentication and ownership of the analysis.
    """
    repo = AnalysisRepository(db)
    analysis = await repo.get_by_id(analysis_id)

    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Analysis not found"}},
        )

    # Ownership check
    if str(analysis.user_id) != user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Not your analysis"}},
        )

    coaching_repo = CoachingResultRepository(db)
    existing = await coaching_repo.get_by_analysis_id(analysis_id)

    # If coaching already complete, return stored output immediately
    if existing and existing.stream_complete:
        return StreamingResponse(
            _stream_stored_output(existing),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Otherwise, stream from Redis pub/sub
    channel = f"coaching:{analysis_id}"
    return StreamingResponse(
        _stream_from_pubsub(channel, redis, coaching_repo, analysis_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
