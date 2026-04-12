"""Chat API — follow-up Q&A on completed analyses (FR-RESL-09, FR-AICP-17).

Routes:
    GET  /analyses/{analysis_id}/chat  → ChatHistoryResponse
    POST /analyses/{analysis_id}/chat  → ChatMessageResponse (201)
"""

from __future__ import annotations

import logging
import os
import uuid

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db import get_db
from app.rate_limit import limiter
from app.repositories.analysis import AnalysisRepository
from app.repositories.chat_message import ChatMessageRepository
from app.schemas.chat import ChatHistoryResponse, ChatMessageRequest, ChatMessageResponse
from app.services.chat import ChatService

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazily constructed Anthropic client (shared across requests)
_anthropic_client: anthropic.AsyncAnthropic | None = None


def _get_anthropic_client() -> anthropic.AsyncAnthropic | None:
    global _anthropic_client
    if _anthropic_client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            _anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
    return _anthropic_client


async def _get_chat_service(
    db: AsyncSession = Depends(get_db),
) -> ChatService:
    return ChatService(
        chat_repo=ChatMessageRepository(db),
        analysis_repo=AnalysisRepository(db),
        anthropic_client=_get_anthropic_client(),
    )


@router.get(
    "/{analysis_id}/chat",
    response_model=ChatHistoryResponse,
)
async def get_chat_history(
    analysis_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(_get_chat_service),
):
    """Retrieve chat history for an analysis."""
    try:
        messages = await service.get_history(analysis_id, user["id"])
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owner")

    return ChatHistoryResponse(
        messages=[ChatMessageResponse.model_validate(m) for m in messages]
    )


@router.post(
    "/{analysis_id}/chat",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/day")
async def send_chat_message(
    request: Request,
    response: Response,
    analysis_id: uuid.UUID,
    body: ChatMessageRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(_get_chat_service),
):
    """Send a follow-up chat message and receive an assistant response."""
    try:
        assistant_msg = await service.send_message(analysis_id, user["id"], body.content)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owner")
    except RuntimeError as e:
        logger.error("ChatService error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service unavailable",
        )

    return ChatMessageResponse.model_validate(assistant_msg)
