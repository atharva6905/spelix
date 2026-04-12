"""Unit tests for chat API endpoints (P2-022).

TDD gate:
- POST /analyses/{id}/chat with valid body -> 201 with assistant message
- POST /analyses/{id}/chat on non-existent analysis -> 404
- POST /analyses/{id}/chat on wrong user -> 403
- POST /analyses/{id}/chat with empty content -> 422
- POST /analyses/{id}/chat with content > 4000 chars -> 422
- GET /analyses/{id}/chat -> 200 with message list
- GET /analyses/{id}/chat on non-existent analysis -> 404
- Assistant response never contains "injury risk" (SafetyFilter applied)

Requirements: FR-RESL-09, FR-AICP-17
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.chat import _get_chat_service, router

TEST_USER_ID = uuid.uuid4()
TEST_EMAIL = "athlete@example.com"


def _make_mock_chat_message(
    analysis_id: uuid.UUID,
    role: str = "assistant",
    content: str = "Focus on pushing your knees out during the ascent.",
) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.analysis_id = analysis_id
    obj.role = role
    obj.content = content
    obj.created_at = datetime.now(timezone.utc)
    return obj


def _build_app(mock_service=None) -> FastAPI:
    """Build a FastAPI app with auth + optional service override."""
    from limits.storage import MemoryStorage

    from app.rate_limit import limiter

    app = FastAPI()
    mem = MemoryStorage()
    limiter._storage = mem
    limiter._limiter.storage = mem
    app.state.limiter = limiter
    app.include_router(router, prefix="/api/v1/analyses")

    # Auth override
    app.dependency_overrides[get_current_user] = lambda: {
        "id": TEST_USER_ID,
        "email": TEST_EMAIL,
    }

    if mock_service is not None:
        app.dependency_overrides[_get_chat_service] = lambda: mock_service

    return app


class TestSendChatMessage:
    def test_post_chat_returns_201_with_assistant_message(self):
        analysis_id = uuid.uuid4()
        mock_service = AsyncMock()
        mock_msg = _make_mock_chat_message(analysis_id, role="assistant")
        mock_service.send_message.return_value = mock_msg

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(
            f"/api/v1/analyses/{analysis_id}/chat",
            json={"content": "Why did my knees cave?"},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["role"] == "assistant"
        assert body["content"] == mock_msg.content
        assert "id" in body
        assert "created_at" in body

    def test_post_chat_returns_404_when_analysis_not_found(self):
        analysis_id = uuid.uuid4()
        mock_service = AsyncMock()
        mock_service.send_message.side_effect = LookupError("not found")

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(
            f"/api/v1/analyses/{analysis_id}/chat",
            json={"content": "hello"},
        )

        assert resp.status_code == 404

    def test_post_chat_returns_403_when_not_owner(self):
        analysis_id = uuid.uuid4()
        mock_service = AsyncMock()
        mock_service.send_message.side_effect = PermissionError("not owner")

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(
            f"/api/v1/analyses/{analysis_id}/chat",
            json={"content": "hello"},
        )

        assert resp.status_code == 403

    def test_post_chat_returns_422_with_empty_content(self):
        mock_service = AsyncMock()
        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(
            f"/api/v1/analyses/{uuid.uuid4()}/chat",
            json={"content": ""},
        )

        assert resp.status_code == 422

    def test_post_chat_returns_422_with_content_over_4000_chars(self):
        mock_service = AsyncMock()
        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(
            f"/api/v1/analyses/{uuid.uuid4()}/chat",
            json={"content": "x" * 4001},
        )

        assert resp.status_code == 422

    def test_post_chat_returns_503_when_anthropic_unavailable(self):
        analysis_id = uuid.uuid4()
        mock_service = AsyncMock()
        mock_service.send_message.side_effect = RuntimeError("no client")

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.post(
            f"/api/v1/analyses/{analysis_id}/chat",
            json={"content": "hello"},
        )

        assert resp.status_code == 503


class TestGetChatHistory:
    def test_get_history_returns_200_with_messages(self):
        analysis_id = uuid.uuid4()
        mock_service = AsyncMock()
        msgs = [
            _make_mock_chat_message(analysis_id, role="user", content="Why the cave?"),
            _make_mock_chat_message(analysis_id, role="assistant", content="Weak glutes."),
        ]
        mock_service.get_history.return_value = msgs

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{analysis_id}/chat")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["messages"]) == 2
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][1]["role"] == "assistant"

    def test_get_history_returns_404_when_analysis_not_found(self):
        mock_service = AsyncMock()
        mock_service.get_history.side_effect = LookupError("not found")

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{uuid.uuid4()}/chat")

        assert resp.status_code == 404

    def test_get_history_returns_403_when_not_owner(self):
        mock_service = AsyncMock()
        mock_service.get_history.side_effect = PermissionError("not owner")

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{uuid.uuid4()}/chat")

        assert resp.status_code == 403

    def test_get_history_empty_when_no_messages(self):
        mock_service = AsyncMock()
        mock_service.get_history.return_value = []

        client = TestClient(_build_app(mock_service), raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analyses/{uuid.uuid4()}/chat")

        assert resp.status_code == 200
        assert resp.json()["messages"] == []


class TestSafetyFilterApplyText:
    """Test that SafetyFilter.apply_text works on plain strings."""

    def test_replaces_injury_risk(self):
        from app.services.safety_filter import SafetyFilter

        result = SafetyFilter.apply_text("This reduces injury risk significantly.")
        assert "injury risk" not in result
        assert "movement quality concern" in result

    def test_replaces_injury_prevention(self):
        from app.services.safety_filter import SafetyFilter

        result = SafetyFilter.apply_text("Good for injury prevention.")
        assert "injury prevention" not in result
        assert "movement quality improvement" in result

    def test_returns_clean_text_unchanged(self):
        from app.services.safety_filter import SafetyFilter

        text = "Focus on pushing knees out during the ascent."
        assert SafetyFilter.apply_text(text) == text
