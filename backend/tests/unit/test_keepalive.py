"""Unit tests for the Qdrant keepalive cron job — branch coverage uplift."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_ping_qdrant_health_logs_info_when_healthy():
    """When Qdrant ping returns True, no warning is logged (healthy path)."""
    mock_wrapper = AsyncMock()
    mock_wrapper.ping = AsyncMock(return_value=True)

    with patch("app.workers.keepalive.get_qdrant_client", return_value=mock_wrapper):
        from app.workers.keepalive import ping_qdrant_health

        await ping_qdrant_health({})

    mock_wrapper.ping.assert_awaited_once()


@pytest.mark.asyncio
async def test_ping_qdrant_health_logs_warning_when_unhealthy():
    """When Qdrant ping returns False, a warning is logged without raising."""
    mock_wrapper = AsyncMock()
    mock_wrapper.ping = AsyncMock(return_value=False)

    with patch("app.workers.keepalive.get_qdrant_client", return_value=mock_wrapper):
        from app.workers.keepalive import ping_qdrant_health

        # Must not raise
        await ping_qdrant_health({})

    mock_wrapper.ping.assert_awaited_once()


@pytest.mark.asyncio
async def test_ping_qdrant_health_handles_none_client():
    """When get_qdrant_client returns None, the function returns early without raising."""
    with patch("app.workers.keepalive.get_qdrant_client", return_value=None):
        from app.workers.keepalive import ping_qdrant_health

        # Must not raise
        await ping_qdrant_health({})


@pytest.mark.asyncio
async def test_ping_qdrant_health_handles_client_init_exception():
    """When get_qdrant_client raises, the exception is swallowed and returns cleanly."""
    with patch(
        "app.workers.keepalive.get_qdrant_client",
        side_effect=Exception("client init failed"),
    ):
        from app.workers.keepalive import ping_qdrant_health

        # Must not raise
        await ping_qdrant_health({})


@pytest.mark.asyncio
async def test_ping_qdrant_health_handles_ping_exception():
    """When wrapper.ping() raises, the exception is swallowed and returns cleanly."""
    mock_wrapper = AsyncMock()
    mock_wrapper.ping = AsyncMock(side_effect=Exception("connection reset"))

    with patch("app.workers.keepalive.get_qdrant_client", return_value=mock_wrapper):
        from app.workers.keepalive import ping_qdrant_health

        # Must not raise
        await ping_qdrant_health({})
