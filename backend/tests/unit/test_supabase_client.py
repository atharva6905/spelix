"""Unit tests for app.services.supabase_client — branch coverage uplift."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_service_role_client_returns_cached_client():
    """Returns the cached client on second call without calling acreate_client again."""
    import app.services.supabase_client as module

    # Reset singleton so the test starts fresh
    module._service_role_client = None

    mock_client = AsyncMock()

    with patch.dict(
        os.environ,
        {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "svc-key"},
    ), patch("supabase.acreate_client", return_value=mock_client) as mock_create:
        first = await module.get_service_role_client()
        second = await module.get_service_role_client()

    # Should have called acreate_client exactly once
    mock_create.assert_awaited_once()
    assert first is mock_client
    assert second is mock_client

    # Reset for other tests
    module._service_role_client = None


@pytest.mark.asyncio
async def test_get_service_role_client_creates_new_when_none():
    """When _service_role_client is None, creates a new client."""
    import app.services.supabase_client as module

    module._service_role_client = None
    mock_client = AsyncMock()

    with patch.dict(
        os.environ,
        {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "svc-key"},
    ), patch("supabase.acreate_client", return_value=mock_client):
        result = await module.get_service_role_client()

    assert result is mock_client

    # Reset
    module._service_role_client = None
