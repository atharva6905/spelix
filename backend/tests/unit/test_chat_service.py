"""Unit tests for ChatService (M-08).

Tests the main paths in app.services.chat.ChatService:
- send_message happy path
- send_message error cases (not found, wrong user, no client)
- get_history happy path
- get_history wrong user
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.chat import ChatService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis(user_id: uuid.UUID, *, has_coaching_result: bool = True) -> MagicMock:
    """Build a minimal mock Analysis object."""
    analysis = MagicMock()
    analysis.user_id = user_id
    if has_coaching_result:
        coaching_result = MagicMock()
        coaching_result.structured_output_json = {"summary": "Good form overall."}
        coaching_result.retrieved_sources_json = None
        analysis.coaching_result = coaching_result
    else:
        analysis.coaching_result = None
    return analysis


def _make_chat_message(
    analysis_id: uuid.UUID,
    role: str = "assistant",
    content: str = "Keep your chest up during the descent.",
) -> MagicMock:
    msg = MagicMock()
    msg.id = uuid.uuid4()
    msg.analysis_id = analysis_id
    msg.role = role
    msg.content = content
    msg.created_at = datetime.now(timezone.utc)
    return msg


def _make_anthropic_response(text: str = "Try keeping your knees tracking over toes.") -> MagicMock:
    response = MagicMock()
    block = MagicMock()
    block.text = text
    response.content = [block]
    return response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def analysis_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def chat_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_analysis = AsyncMock(return_value=[])
    repo.create = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def analysis_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def anthropic_client() -> AsyncMock:
    client = AsyncMock()
    client.messages = AsyncMock()
    return client


@pytest.fixture
def chat_service(chat_repo, analysis_repo, anthropic_client) -> ChatService:
    return ChatService(
        chat_repo=chat_repo,
        analysis_repo=analysis_repo,
        anthropic_client=anthropic_client,
    )


# ---------------------------------------------------------------------------
# send_message tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_happy_path(
    chat_service: ChatService,
    chat_repo: AsyncMock,
    analysis_repo: AsyncMock,
    anthropic_client: AsyncMock,
    user_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    """Happy path: returns assistant ChatMessage and persists both messages."""
    mock_analysis = _make_analysis(user_id)
    analysis_repo.get_by_id_with_relations = AsyncMock(return_value=mock_analysis)

    assistant_text = "Focus on hip hinge pattern before adding weight."
    anthropic_client.messages.create = AsyncMock(
        return_value=_make_anthropic_response(assistant_text)
    )

    result = await chat_service.send_message(
        analysis_id=analysis_id,
        user_id=user_id,
        content="How can I improve my deadlift?",
    )

    # Assistant message is returned
    assert result is not None

    # Both user and assistant messages were stored
    assert chat_repo.create.call_count == 2
    created_msgs = [call.args[0] for call in chat_repo.create.call_args_list]
    roles = [msg.role for msg in created_msgs]
    assert "user" in roles
    assert "assistant" in roles

    # The assistant message content goes through SafetyFilter — just verify it's a non-empty string
    assistant_created = next(m for m in created_msgs if m.role == "assistant")
    assert isinstance(assistant_created.content, str)
    assert len(assistant_created.content) > 0


@pytest.mark.asyncio
async def test_send_message_returns_assistant_chat_message(
    chat_service: ChatService,
    analysis_repo: AsyncMock,
    anthropic_client: AsyncMock,
    user_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    """Return value is the assistant ChatMessage (role='assistant')."""
    mock_analysis = _make_analysis(user_id)
    analysis_repo.get_by_id_with_relations = AsyncMock(return_value=mock_analysis)
    anthropic_client.messages.create = AsyncMock(
        return_value=_make_anthropic_response("Tuck your elbows slightly.")
    )

    result = await chat_service.send_message(
        analysis_id=analysis_id,
        user_id=user_id,
        content="Any bench press tips?",
    )

    assert result.role == "assistant"


@pytest.mark.asyncio
async def test_send_message_analysis_not_found_raises_lookup_error(
    chat_service: ChatService,
    analysis_repo: AsyncMock,
    user_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    """LookupError when analysis does not exist."""
    analysis_repo.get_by_id_with_relations = AsyncMock(return_value=None)

    with pytest.raises(LookupError, match=str(analysis_id)):
        await chat_service.send_message(
            analysis_id=analysis_id,
            user_id=user_id,
            content="Tell me about my form.",
        )


@pytest.mark.asyncio
async def test_send_message_wrong_user_raises_permission_error(
    chat_service: ChatService,
    analysis_repo: AsyncMock,
    user_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    """PermissionError when analysis belongs to a different user."""
    other_user_id = uuid.uuid4()
    mock_analysis = _make_analysis(other_user_id)
    analysis_repo.get_by_id_with_relations = AsyncMock(return_value=mock_analysis)

    with pytest.raises(PermissionError):
        await chat_service.send_message(
            analysis_id=analysis_id,
            user_id=user_id,
            content="How was my squat?",
        )


@pytest.mark.asyncio
async def test_send_message_no_anthropic_client_raises_runtime_error(
    chat_repo: AsyncMock,
    analysis_repo: AsyncMock,
    user_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    """RuntimeError when ChatService is constructed without an Anthropic client."""
    service = ChatService(
        chat_repo=chat_repo,
        analysis_repo=analysis_repo,
        anthropic_client=None,
    )
    mock_analysis = _make_analysis(user_id)
    analysis_repo.get_by_id_with_relations = AsyncMock(return_value=mock_analysis)

    with pytest.raises(RuntimeError):
        await service.send_message(
            analysis_id=analysis_id,
            user_id=user_id,
            content="What should I work on?",
        )


@pytest.mark.asyncio
async def test_send_message_includes_history_in_llm_call(
    chat_service: ChatService,
    chat_repo: AsyncMock,
    analysis_repo: AsyncMock,
    anthropic_client: AsyncMock,
    user_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    """Existing conversation history is forwarded to the Anthropic API call."""
    mock_analysis = _make_analysis(user_id)
    analysis_repo.get_by_id_with_relations = AsyncMock(return_value=mock_analysis)

    prev_user = _make_chat_message(analysis_id, role="user", content="First question.")
    prev_asst = _make_chat_message(analysis_id, role="assistant", content="First answer.")
    chat_repo.get_by_analysis = AsyncMock(return_value=[prev_user, prev_asst])

    anthropic_client.messages.create = AsyncMock(
        return_value=_make_anthropic_response("Follow-up answer.")
    )

    await chat_service.send_message(
        analysis_id=analysis_id,
        user_id=user_id,
        content="Follow-up question.",
    )

    call_kwargs = anthropic_client.messages.create.call_args.kwargs
    messages_sent = call_kwargs["messages"]
    # 2 history messages + 1 new user message = 3 total
    assert len(messages_sent) == 3
    assert messages_sent[0]["role"] == "user"
    assert messages_sent[1]["role"] == "assistant"
    assert messages_sent[2]["role"] == "user"


@pytest.mark.asyncio
async def test_send_message_no_coaching_result_still_works(
    chat_service: ChatService,
    analysis_repo: AsyncMock,
    anthropic_client: AsyncMock,
    user_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    """send_message succeeds even when coaching_result is None."""
    mock_analysis = _make_analysis(user_id, has_coaching_result=False)
    analysis_repo.get_by_id_with_relations = AsyncMock(return_value=mock_analysis)
    anthropic_client.messages.create = AsyncMock(
        return_value=_make_anthropic_response("General tip here.")
    )

    result = await chat_service.send_message(
        analysis_id=analysis_id,
        user_id=user_id,
        content="Any general advice?",
    )
    assert result is not None


# ---------------------------------------------------------------------------
# get_history tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_history_happy_path(
    chat_service: ChatService,
    chat_repo: AsyncMock,
    analysis_repo: AsyncMock,
    user_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    """Returns the ordered list of ChatMessages from the repo."""
    mock_analysis = _make_analysis(user_id)
    analysis_repo.get_by_id = AsyncMock(return_value=mock_analysis)

    messages = [
        _make_chat_message(analysis_id, role="user", content="Q1"),
        _make_chat_message(analysis_id, role="assistant", content="A1"),
        _make_chat_message(analysis_id, role="user", content="Q2"),
    ]
    chat_repo.get_by_analysis = AsyncMock(return_value=messages)

    result = await chat_service.get_history(analysis_id=analysis_id, user_id=user_id)

    assert result == messages
    chat_repo.get_by_analysis.assert_called_once_with(analysis_id)


@pytest.mark.asyncio
async def test_get_history_empty_returns_empty_list(
    chat_service: ChatService,
    chat_repo: AsyncMock,
    analysis_repo: AsyncMock,
    user_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    """get_history returns an empty list when no messages exist."""
    mock_analysis = _make_analysis(user_id)
    analysis_repo.get_by_id = AsyncMock(return_value=mock_analysis)
    chat_repo.get_by_analysis = AsyncMock(return_value=[])

    result = await chat_service.get_history(analysis_id=analysis_id, user_id=user_id)

    assert result == []


@pytest.mark.asyncio
async def test_get_history_analysis_not_found_raises_lookup_error(
    chat_service: ChatService,
    analysis_repo: AsyncMock,
    user_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    """LookupError when analysis does not exist."""
    analysis_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(LookupError, match=str(analysis_id)):
        await chat_service.get_history(analysis_id=analysis_id, user_id=user_id)


@pytest.mark.asyncio
async def test_get_history_wrong_user_raises_permission_error(
    chat_service: ChatService,
    analysis_repo: AsyncMock,
    user_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> None:
    """PermissionError when analysis belongs to a different user."""
    other_user_id = uuid.uuid4()
    mock_analysis = _make_analysis(other_user_id)
    analysis_repo.get_by_id = AsyncMock(return_value=mock_analysis)

    with pytest.raises(PermissionError):
        await chat_service.get_history(analysis_id=analysis_id, user_id=user_id)
