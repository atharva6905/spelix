"""Server-side Supabase clients (service-role only — never exposed to browser).

Cached as a module-level singleton created lazily on first access. The
`acreate_client` factory in supabase-py>=2.x returns a coroutine that must
be awaited before any `.storage.from_(...)` calls; this module awaits it
once and stashes the resolved client, so callers get a ready-to-use client
from a single `await get_service_role_client()` call.
"""

from __future__ import annotations

import os
from typing import Any

_service_role_client: Any | None = None


async def get_service_role_client() -> Any:
    """Return a cached Supabase async client authenticated with the service-role key.

    Lazy singleton. Tests patch this symbol via `@patch` which substitutes an
    AsyncMock (Python 3.12 auto-detects the async signature), so the test
    call sites already await correctly without any test-side changes.
    """
    global _service_role_client
    if _service_role_client is not None:
        return _service_role_client

    from supabase import acreate_client  # type: ignore[import]

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    _service_role_client = await acreate_client(url, key)
    return _service_role_client
