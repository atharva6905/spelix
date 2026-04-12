"""Tests for get_langfuse_client factory singleton.

TDD gate for P2-034 (FR-BRAIN-13).

Covers:
- Factory returns a Langfuse instance when keys are set
- Factory returns None gracefully when keys are missing
- Factory caches the result (second call returns same object)
- Factory caches None result (no retry when keys absent)
- CoachingService accepts langfuse_client parameter
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: reset module-level factory cache between tests
# ---------------------------------------------------------------------------


def _reset_factory() -> None:
    from app.services import langfuse_client as lf_mod

    lf_mod._langfuse_client_cache = None
    lf_mod._langfuse_client_cache_initialized = False


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestGetLangfuseClientFactory:
    """Two-flag singleton factory — None result is cached (missing keys in dev/test)."""

    @pytest.mark.asyncio
    async def test_returns_client_when_keys_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Factory must return a Langfuse instance when env vars are present."""
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-abc")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-xyz")
        monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        _reset_factory()

        fake_langfuse = MagicMock(name="Langfuse_instance")

        with patch("langfuse.Langfuse", return_value=fake_langfuse):
            from app.services.langfuse_client import get_langfuse_client

            client = await get_langfuse_client()

        assert client is fake_langfuse

    @pytest.mark.asyncio
    async def test_returns_none_when_keys_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Factory must return None gracefully when env vars are absent."""
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
        _reset_factory()

        from app.services.langfuse_client import get_langfuse_client

        client = await get_langfuse_client()
        assert client is None

    @pytest.mark.asyncio
    async def test_client_cached_after_first_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Factory must return the same instance on repeated calls (no reconnect)."""
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-abc")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-xyz")
        _reset_factory()

        fake_langfuse = MagicMock(name="Langfuse_instance")

        with patch("langfuse.Langfuse", return_value=fake_langfuse) as mock_cls:
            from app.services.langfuse_client import get_langfuse_client

            first = await get_langfuse_client()
            second = await get_langfuse_client()

        # Constructor called exactly once — second call hits cache
        mock_cls.assert_called_once()
        assert first is second

    @pytest.mark.asyncio
    async def test_none_result_cached_no_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """None result (missing keys) must be cached — no repeated constructor attempts."""
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
        _reset_factory()

        with patch("langfuse.Langfuse") as mock_cls:
            from app.services.langfuse_client import get_langfuse_client

            first = await get_langfuse_client()
            second = await get_langfuse_client()

        mock_cls.assert_not_called()
        assert first is None
        assert second is None

    @pytest.mark.asyncio
    async def test_returns_none_on_constructor_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If Langfuse() raises (e.g. bad host), factory must return None, not raise."""
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
        _reset_factory()

        with patch("langfuse.Langfuse", side_effect=Exception("connection refused")):
            from app.services.langfuse_client import get_langfuse_client

            client = await get_langfuse_client()

        assert client is None


# ---------------------------------------------------------------------------
# CoachingService integration
# ---------------------------------------------------------------------------


class TestCoachingServiceAcceptsLangfuse:
    """CoachingService must store a langfuse_client param without breaking."""

    def test_coaching_service_accepts_langfuse_param(self) -> None:
        """Construct CoachingService with langfuse_client=MagicMock, assert stored."""
        from app.services.coaching import CoachingService

        mock_lf = MagicMock(name="langfuse_client")
        svc = CoachingService(anthropic_client=None, langfuse_client=mock_lf)
        assert svc._langfuse_client is mock_lf

    def test_coaching_service_defaults_langfuse_to_none(self) -> None:
        """Default construction must leave _langfuse_client as None."""
        from app.services.coaching import CoachingService

        svc = CoachingService(anthropic_client=None)
        assert svc._langfuse_client is None
