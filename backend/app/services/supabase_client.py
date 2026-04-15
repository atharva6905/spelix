"""Server-side Supabase clients (service-role only — never exposed to browser).

Cached as module-level singletons created lazily on first access.
Uses acreate_client (async variant) consistent with the rest of the backend
(analyses.py, analysis_worker.py, cleanup.py).
"""

from __future__ import annotations

import os
from typing import Any

_service_role_client: Any | None = None


def get_service_role_client() -> Any:
    """Return a cached Supabase async client authenticated with the service-role key.

    Lazy singleton so tests can monkeypatch the module-level cache or patch
    this function directly via unittest.mock.patch.
    """
    global _service_role_client
    if _service_role_client is not None:
        return _service_role_client

    from supabase import acreate_client  # type: ignore[import]

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    # acreate_client is a coroutine in supabase>=2.x — callers that actually
    # need the live client must await the result.  In tests this function is
    # monkeypatched so the coroutine is never awaited.
    _service_role_client = acreate_client(url, key)
    return _service_role_client
