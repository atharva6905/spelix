"""FastAPI dependencies for Supabase JWT authentication.

Provides:
    get_current_user  — validates a Supabase-issued JWT and returns CurrentUser.
    get_admin_user    — guards endpoints to admin-role users only.

Requirements: FR-AUTH-02, FR-AUTH-08, NFR-SECU-05
"""

import os
import uuid
from typing import TypedDict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_JWT_ALGORITHM = "HS256"
_JWT_AUDIENCE = "authenticated"

_http_bearer = HTTPBearer()


def _get_jwt_secret() -> str:
    """Return the Supabase JWT secret from the environment.

    Raises RuntimeError immediately at startup if the env var is absent,
    keeping the fail-fast contract (NFR-SECU-05).  The secret is never
    logged or included in any exception message or HTTP response body.
    """
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "SUPABASE_JWT_SECRET environment variable is not set. "
            "This is required for JWT validation."
        )
    return secret


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
    secret = _get_jwt_secret()

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_JWT_ALGORITHM],
            audience=_JWT_AUDIENCE,
        )
    except ExpiredSignatureError:
        raise invalid_credentials_exc
    except JWTError:
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
