"""Unit tests for Supabase JWT auth dependency (B-005).

Tests cover:
- Valid JWT decodes correctly and returns CurrentUser
- Expired JWT raises 401
- Malformed JWT raises 401
- Missing Authorization header raises 401 (via HTTPBearer)
- Admin check passes for admin role
- Admin check raises 403 for non-admin role
- Default role is "user" when user_metadata.role is missing
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

# Test secret — never expose in production
TEST_SECRET = "test-supabase-jwt-secret-for-unit-tests-only"
TEST_USER_ID = str(uuid.uuid4())
TEST_EMAIL = "test@example.com"
ALGORITHM = "HS256"
AUDIENCE = "authenticated"


def make_jwt(
    user_id: str = TEST_USER_ID,
    email: str = TEST_EMAIL,
    role: str | None = "user",
    expired: bool = False,
    audience: str = AUDIENCE,
) -> str:
    """Generate a test JWT signed with TEST_SECRET."""
    now = datetime.now(timezone.utc)
    exp = now - timedelta(minutes=5) if expired else now + timedelta(hours=1)
    payload: dict = {
        "sub": user_id,
        "email": email,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if role is not None:
        payload["user_metadata"] = {"role": role}
    return jwt.encode(payload, TEST_SECRET, algorithm=ALGORITHM)


@pytest.fixture(autouse=True)
def set_jwt_secret(monkeypatch):
    """Inject test JWT secret into environment for all tests in this module."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_SECRET)


# ---------------------------------------------------------------------------
# Import under test — done inside each test so SUPABASE_JWT_SECRET is already
# set by the autouse fixture when the module is first imported.
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    def test_valid_jwt_returns_current_user(self, set_jwt_secret):
        """Valid JWT decodes correctly and returns a CurrentUser dict."""
        from app.api.deps import get_current_user

        token = make_jwt(role="user")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = asyncio.run(get_current_user(creds))

        assert str(result["id"]) == TEST_USER_ID
        assert result["email"] == TEST_EMAIL
        assert result["role"] == "user"

    def test_expired_jwt_raises_401(self, set_jwt_secret):
        """Expired JWT raises HTTP 401."""
        from app.api.deps import get_current_user

        token = make_jwt(expired=True)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    def test_malformed_jwt_raises_401(self, set_jwt_secret):
        """Malformed JWT string raises HTTP 401."""
        from app.api.deps import get_current_user

        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="this.is.not.a.valid.jwt"
        )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    def test_wrong_secret_raises_401(self, set_jwt_secret):
        """JWT signed with a different secret raises HTTP 401."""
        from app.api.deps import get_current_user

        token = jwt.encode(
            {
                "sub": TEST_USER_ID,
                "email": TEST_EMAIL,
                "aud": AUDIENCE,
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            },
            "wrong-secret",
            algorithm=ALGORITHM,
        )
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401

    def test_default_role_is_user_when_user_metadata_missing(self, set_jwt_secret):
        """When user_metadata.role is absent, role defaults to 'user'."""
        from app.api.deps import get_current_user

        # role=None causes make_jwt to omit user_metadata entirely
        token = make_jwt(role=None)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = asyncio.run(get_current_user(creds))

        assert result["role"] == "user"

    def test_admin_role_preserved(self, set_jwt_secret):
        """JWT with user_metadata.role='admin' returns role='admin'."""
        from app.api.deps import get_current_user

        token = make_jwt(role="admin")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = asyncio.run(get_current_user(creds))

        assert result["role"] == "admin"


class TestGetAdminUser:
    """Tests for get_admin_user dependency."""

    def test_admin_role_passes(self):
        """Admin user dict passes through unchanged."""
        from app.api.deps import get_admin_user

        user = {"id": uuid.UUID(TEST_USER_ID), "email": TEST_EMAIL, "role": "admin"}
        result = get_admin_user(user)
        assert result == user

    def test_non_admin_raises_403(self):
        """Non-admin role raises HTTP 403 with FORBIDDEN code."""
        from app.api.deps import get_admin_user

        user = {"id": uuid.UUID(TEST_USER_ID), "email": TEST_EMAIL, "role": "user"}

        with pytest.raises(HTTPException) as exc_info:
            get_admin_user(user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"]["code"] == "FORBIDDEN"

    def test_missing_role_raises_403(self):
        """User without any role field raises HTTP 403."""
        from app.api.deps import get_admin_user

        user = {"id": uuid.UUID(TEST_USER_ID), "email": TEST_EMAIL, "role": "viewer"}

        with pytest.raises(HTTPException) as exc_info:
            get_admin_user(user)

        assert exc_info.value.status_code == 403
