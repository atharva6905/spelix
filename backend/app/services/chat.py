"""ChatService — follow-up Q&A on completed analyses (FR-RESL-09, FR-AICP-17).

Non-streaming POST for Phase 2 MVP. Loads coaching context + conversation
history, calls Claude Sonnet, applies safety filter, stores both messages.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import TYPE_CHECKING

import anthropic

from app.config_constants import LLM_MAX_TOKENS_CHAT as CHAT_MAX_TOKENS
from app.models.chat_message import ChatMessage
from app.repositories.chat_message import ChatMessageRepository
from app.services.safety_filter import SafetyFilter

if TYPE_CHECKING:
    from app.repositories.analysis import AnalysisRepository

logger = logging.getLogger(__name__)

_MAX_MESSAGE_LENGTH = 2000
_XML_TAG_PATTERN = re.compile(
    r"</?(?:system|human|assistant|tool_use|tool_result|function_call|function_result)[^>]*>",
    re.IGNORECASE,
)


def _sanitize_user_message(content: str) -> str:
    """Sanitize user chat message before LLM context injection.

    Truncates to 2000 chars and strips XML-like tags that could
    confuse Claude's prompt structure.
    """
    content = content[:_MAX_MESSAGE_LENGTH]
    content = _XML_TAG_PATTERN.sub("", content)
    return content.strip()


CHAT_MODEL = "claude-sonnet-4-6"
CHAT_TEMPERATURE = 0.3

SYSTEM_PROMPT = (
    "You are a knowledgeable barbell coaching assistant. The user has just received "
    "an automated form analysis and coaching feedback (provided below as context). "
    "Answer their follow-up questions about the analysis, technique cues, or training. "
    "Be concise and specific. Never use the phrases 'injury risk' or 'injury prevention' — "
    "use 'movement quality concern' or 'movement quality improvement' instead. "
    "Always remind users that this is not medical advice if they ask about pain or health conditions."
)


class ChatService:
    def __init__(
        self,
        chat_repo: ChatMessageRepository,
        analysis_repo: "AnalysisRepository",
        anthropic_client: anthropic.AsyncAnthropic | None,
    ) -> None:
        self._chat_repo = chat_repo
        self._analysis_repo = analysis_repo
        self._anthropic_client = anthropic_client

    async def send_message(
        self,
        analysis_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
    ) -> ChatMessage:
        """Process a user chat message and return the assistant response."""
        # Load analysis + verify ownership
        analysis = await self._analysis_repo.get_by_id(analysis_id)
        if analysis is None:
            raise LookupError(f"Analysis {analysis_id} not found")
        if analysis.user_id != user_id:
            raise PermissionError("Not the owner of this analysis")

        if self._anthropic_client is None:
            raise RuntimeError(
                "ChatService was constructed with anthropic_client=None. "
                "Cannot generate chat response."
            )

        # Build context from coaching result
        context_parts: list[str] = []
        if analysis.coaching_result and analysis.coaching_result.structured_output_json:
            context_parts.append(
                "## Coaching Result\n"
                + json.dumps(analysis.coaching_result.structured_output_json, indent=2)
            )
        if analysis.coaching_result and analysis.coaching_result.retrieved_sources_json:
            context_parts.append(
                "## Retrieved Sources\n"
                + json.dumps(analysis.coaching_result.retrieved_sources_json, indent=2)
            )

        system_text = SYSTEM_PROMPT
        if context_parts:
            system_text += "\n\n---\n\n" + "\n\n".join(context_parts)

        # Load conversation history
        history = await self._chat_repo.get_by_analysis(analysis_id)
        messages: list[anthropic.types.MessageParam] = []
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})  # type: ignore[arg-type]
        messages.append({"role": "user", "content": _sanitize_user_message(content)})

        # Call Claude
        response = await self._anthropic_client.messages.create(
            model=CHAT_MODEL,
            max_tokens=CHAT_MAX_TOKENS,
            temperature=CHAT_TEMPERATURE,
            system=system_text,
            messages=messages,
        )

        first_block = response.content[0]
        assistant_text: str = first_block.text  # type: ignore[union-attr]

        # Apply safety filter
        assistant_text = SafetyFilter.apply_text(assistant_text)

        # Store both messages
        user_msg = ChatMessage(
            analysis_id=analysis_id,
            role="user",
            content=content,
        )
        await self._chat_repo.create(user_msg)

        assistant_msg = ChatMessage(
            analysis_id=analysis_id,
            role="assistant",
            content=assistant_text,
        )
        await self._chat_repo.create(assistant_msg)

        return assistant_msg

    async def get_history(
        self,
        analysis_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[ChatMessage]:
        """Return all chat messages for an analysis, ordered by created_at."""
        analysis = await self._analysis_repo.get_by_id(analysis_id)
        if analysis is None:
            raise LookupError(f"Analysis {analysis_id} not found")
        if analysis.user_id != user_id:
            raise PermissionError("Not the owner of this analysis")

        return await self._chat_repo.get_by_analysis(analysis_id)
