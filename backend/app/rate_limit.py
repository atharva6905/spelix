"""Rate limiting configuration using slowapi + Redis.

NFR-SECU-10: POST /api/v1/analyses limited to 10/user/day.

Uses Redis as storage backend in production; falls back to memory in tests.
The key function uses the client IP address. Keying by JWT sub was removed
because unverified tokens are spoofable (M-02 audit finding).
"""

from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_user_key(request: Request) -> str:
    """Extract rate-limit key from request.

    Uses client IP address. Previously extracted JWT sub without
    verification (M-02 audit finding) — removed because unverified
    tokens are spoofable.
    """
    return get_remote_address(request)


_redis_url = os.environ.get("REDIS_URL", "memory://")

limiter = Limiter(
    key_func=_get_user_key,
    storage_uri=_redis_url,
    headers_enabled=True,
)
