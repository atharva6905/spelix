"""FastAPI dependencies for Supabase JWT authentication.

Provides:
    get_current_user  — validates a Supabase-issued JWT and returns CurrentUser.
    get_admin_user    — guards endpoints to admin-role users only.

Requirements: FR-AUTH-02, FR-AUTH-08, NFR-SECU-05
"""

import os
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any, TypedDict

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_JWT_AUDIENCE = "authenticated"

_http_bearer = HTTPBearer()


def _get_expected_issuer() -> str:
    """Return the expected JWT issuer.

    Checks SUPABASE_JWT_ISSUER first; falls back to deriving from SUPABASE_URL
    as ``{SUPABASE_URL}/auth/v1``.
    """
    explicit = os.environ.get("SUPABASE_JWT_ISSUER")
    if explicit:
        return explicit
    return f"{_get_supabase_url()}/auth/v1"

# JWKS cache: fetched from Supabase and refreshed every 60 minutes
_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0
_JWKS_TTL_SECONDS = 3600


def _get_supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL environment variable is not set.")
    return url.rstrip("/")


async def _get_jwks() -> dict:
    """Fetch and cache the Supabase JWKS (public keys for JWT verification)."""
    global _jwks_cache, _jwks_fetched_at

    now = time.monotonic()
    if _jwks_cache is not None and (now - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
        return _jwks_cache

    jwks_url = f"{_get_supabase_url()}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url, timeout=10)
    resp.raise_for_status()
    data: dict = resp.json()
    _jwks_cache = data
    _jwks_fetched_at = now
    return data


def _get_jwt_secret() -> str | None:
    """Return the legacy HS256 JWT secret if set, or None."""
    return os.environ.get("SUPABASE_JWT_SECRET")


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


class CurrentUser(TypedDict):
    """Decoded and validated Supabase JWT claims."""

    id: uuid.UUID
    email: str
    role: str


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
) -> CurrentUser:
    """Validate a Supabase Bearer JWT and return the authenticated user.

    Raises:
        HTTPException 401 — token is missing, malformed, expired, or has an
                            invalid signature / audience.
    """
    invalid_credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": {
                "code": "INVALID_TOKEN",
                "message": "Could not validate credentials.",
                "detail": None,
            }
        },
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    # Try JWKS-based verification first (ES256), fall back to legacy HS256
    payload = None
    try:
        jwks_data = await _get_jwks()
        payload = jwt.decode(
            token,
            jwks_data,
            algorithms=["ES256", "RS256"],
            audience=_JWT_AUDIENCE,
        )
    except (httpx.HTTPError, JWTError, ExpiredSignatureError, KeyError, ValueError):
        # Fall back to legacy HS256 for expected JWKS/JWT errors only.
        # KeyError/ValueError cover malformed JWKS response parsing.
        secret = _get_jwt_secret()
        if secret:
            try:
                payload = jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    audience=_JWT_AUDIENCE,
                )
            except (ExpiredSignatureError, JWTError):
                raise invalid_credentials_exc
        else:
            raise invalid_credentials_exc

    if payload is None:
        raise invalid_credentials_exc

    # Validate issuer claim (B-075)
    try:
        expected_issuer = _get_expected_issuer()
        token_issuer: str | None = payload.get("iss")
        if token_issuer != expected_issuer:
            raise invalid_credentials_exc
    except HTTPException:
        raise
    except Exception:
        raise invalid_credentials_exc

    # Extract standard Supabase claims
    sub: str | None = payload.get("sub")
    email: str | None = payload.get("email")

    if not sub or not email:
        raise invalid_credentials_exc

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise invalid_credentials_exc

    # user_metadata.role is optional — default to "user"
    user_metadata: dict = payload.get("user_metadata") or {}
    role: str = user_metadata.get("role") or "user"

    return CurrentUser(id=user_id, email=email, role=role)


async def get_redis() -> AsyncGenerator[Any, None]:
    """Yield an async Redis client for dependency injection.

    Uses redis.asyncio backed by the REDIS_URL environment variable.
    The caller receives the client directly (not a generator) when used
    with FastAPI's Depends().
    """
    import redis.asyncio as aioredis

    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    client = aioredis.from_url(url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


def get_admin_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Guard dependency that passes only if the authenticated user is an admin.

    Raises:
        HTTPException 403 — user is authenticated but does not have the
                            "admin" role.
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Admin access required.",
                    "detail": None,
                }
            },
        )
    return user


def get_expert_reviewer_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Guard dependency that passes if the user is an expert reviewer or admin.

    Admins can also access the expert portal (ADR-041).

    Raises:
        HTTPException 403 — user does not have expert_reviewer or admin role.
    """
    if user.get("role") not in ("expert_reviewer", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Expert reviewer access required.",
                    "detail": None,
                }
            },
        )
    return user
