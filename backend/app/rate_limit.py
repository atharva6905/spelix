"""Rate limiting configuration using slowapi + Redis.

NFR-SECU-10: POST /api/v1/analyses limited to 10/user/day.

Uses Redis as storage backend in production; falls back to memory in tests.
The key function extracts the user ID from the Supabase JWT to rate limit
per authenticated user, not per IP.
"""

from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_user_key(request: Request) -> str:
    """Extract user ID from the resolved auth dependency for rate limiting.

    Falls back to remote address if user is not yet resolved (e.g. auth failed
    before rate limit check).
    """
    # After get_current_user runs, the user dict is available via dependency
    # injection — but slowapi key functions run before dependencies resolve.
    # We parse the JWT sub claim directly from the Authorization header.
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            import json
            import base64

            # Decode JWT payload (second segment) — no verification needed
            # here since get_current_user validates the full token.
            payload_b64 = token.split(".")[1]
            # Add padding
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            sub = payload.get("sub")
            if sub:
                return str(sub)
        except Exception:
            pass

    return get_remote_address(request)


_redis_url = os.environ.get("REDIS_URL", "memory://")

limiter = Limiter(
    key_func=_get_user_key,
    storage_uri=_redis_url,
    headers_enabled=True,
)
