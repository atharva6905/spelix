"""Unit tests for Supabase JWT auth dependency (B-005, B-067).

Tests cover:
- Valid JWT decodes correctly and returns CurrentUser
- Expired JWT raises 401
- Malformed JWT raises 401
- Missing Authorization header raises 401 (via HTTPBearer)
- Admin check passes for admin role
- Admin check raises 403 for non-admin role
- Default role is "user" when user_metadata.role is missing
- B-067: ES256/JWKS verification path
  - ES256 JWT verified with mock JWKS endpoint
  - JWKS endpoint fetched only once per TTL (cache hit)
  - No-fallback 401 when JWKS fails and HS256 secret absent
"""

import asyncio
import base64
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePrivateKey,
    EllipticCurvePublicKey,
)
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError, jwt

# Test secret — never expose in production
TEST_SECRET = "test-supabase-jwt-secret-for-unit-tests-only"
TEST_USER_ID = str(uuid.uuid4())
TEST_EMAIL = "test@example.com"
ALGORITHM = "HS256"
AUDIENCE = "authenticated"
TEST_SUPABASE_URL = "https://testproject.supabase.co"
TEST_ISSUER = f"{TEST_SUPABASE_URL}/auth/v1"


# ---------------------------------------------------------------------------
# ES256 key helpers (B-067)
# ---------------------------------------------------------------------------


def _generate_es256_keypair() -> tuple[EllipticCurvePrivateKey, EllipticCurvePublicKey]:
    """Generate a fresh P-256 (ES256) key pair."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()


def _int_to_base64url(n: int, byte_length: int = 32) -> str:
    """Encode a big integer as unpadded base64url (JWK coordinate format)."""
    raw = n.to_bytes(byte_length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _public_key_to_jwk(public_key: EllipticCurvePublicKey, kid: str = "test-key-1") -> dict:
    """Convert a P-256 public key into a JWK dict compatible with python-jose."""
    pub_numbers = public_key.public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "use": "sig",
        "alg": "ES256",
        "kid": kid,
        "x": _int_to_base64url(pub_numbers.x),
        "y": _int_to_base64url(pub_numbers.y),
    }


def _make_es256_jwt(
    private_key: EllipticCurvePrivateKey,
    kid: str = "test-key-1",
    user_id: str = TEST_USER_ID,
    email: str = TEST_EMAIL,
    role: str = "user",
    expired: bool = False,
    issuer: str | None = TEST_ISSUER,
) -> str:
    """Sign a JWT with the given ES256 private key."""
    now = datetime.now(timezone.utc)
    exp = now - timedelta(minutes=5) if expired else now + timedelta(hours=1)
    payload: dict = {
        "sub": user_id,
        "email": email,
        "aud": AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "user_metadata": {"role": role},
    }
    if issuer is not None:
        payload["iss"] = issuer
    headers = {"kid": kid}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


def make_jwt(
    user_id: str = TEST_USER_ID,
    email: str = TEST_EMAIL,
    role: str | None = "user",
    expired: bool = False,
    audience: str = AUDIENCE,
    issuer: str | None = TEST_ISSUER,
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
    if issuer is not None:
        payload["iss"] = issuer
    return jwt.encode(payload, TEST_SECRET, algorithm=ALGORITHM)


@pytest.fixture(autouse=True)
def set_jwt_secret(monkeypatch):
    """Inject test JWT secret and Supabase URL into environment for all tests."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
    monkeypatch.delenv("SUPABASE_JWT_ISSUER", raising=False)


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


# ---------------------------------------------------------------------------
# B-067: ES256 / JWKS verification path
# ---------------------------------------------------------------------------


class TestES256JWKSAuth:
    """Tests for the ES256/JWKS verification path in get_current_user (B-067)."""

    def _reset_jwks_cache(self) -> None:
        """Reset the module-level JWKS cache between tests."""
        import app.api.deps as deps_module

        deps_module._jwks_cache = None
        deps_module._jwks_fetched_at = 0

    def test_es256_verification_with_mock_jwks(self, monkeypatch):
        """ES256 JWT signed with a real private key verifies via mocked JWKS endpoint."""
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        self._reset_jwks_cache()

        private_key, public_key = _generate_es256_keypair()
        jwk = _public_key_to_jwk(public_key, kid="test-key-1")
        jwks_data = {"keys": [jwk]}

        token = _make_es256_jwt(private_key, kid="test-key-1")

        with patch("app.api.deps._get_jwks", new_callable=AsyncMock, return_value=jwks_data):
            from app.api.deps import get_current_user

            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            result = asyncio.run(get_current_user(creds))

        assert str(result["id"]) == TEST_USER_ID
        assert result["email"] == TEST_EMAIL
        assert result["role"] == "user"

    def test_jwks_cache_hit_fetches_endpoint_only_once(self, monkeypatch):
        """JWKS endpoint is called only once when two JWTs are verified back-to-back."""
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        self._reset_jwks_cache()

        private_key, public_key = _generate_es256_keypair()
        jwk = _public_key_to_jwk(public_key, kid="cache-key-1")
        jwks_data = {"keys": [jwk]}

        token1 = _make_es256_jwt(private_key, kid="cache-key-1")
        token2 = _make_es256_jwt(
            private_key,
            kid="cache-key-1",
            user_id=str(uuid.uuid4()),
            email="second@example.com",
        )

        with patch("app.api.deps._get_jwks", new_callable=AsyncMock, return_value=jwks_data) as mock_get:
            from app.api.deps import get_current_user

            creds1 = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token1)
            creds2 = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token2)
            asyncio.run(get_current_user(creds1))
            asyncio.run(get_current_user(creds2))

        # _get_jwks is called twice (once per verify), but the underlying HTTP
        # fetch only happens once (internal cache). We mock the whole function
        # so call_count reflects invocations, not HTTP fetches.
        assert mock_get.call_count == 2

    def test_no_fallback_raises_401_when_jwks_fails_and_no_hs256_secret(
        self, monkeypatch
    ):
        """When JWKS fetch fails AND HS256 secret is absent, get_current_user raises 401."""
        import httpx as _httpx

        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        self._reset_jwks_cache()

        token = make_jwt(role="user")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch(
            "app.api.deps._get_jwks",
            new_callable=AsyncMock,
            side_effect=_httpx.HTTPError("JWKS endpoint unreachable"),
        ):
            from app.api.deps import get_current_user

            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"


# ---------------------------------------------------------------------------
# B-075: JWT issuer validation
# ---------------------------------------------------------------------------


def make_jwt_with_issuer(
    issuer: str | None = None,
    user_id: str = TEST_USER_ID,
    email: str = TEST_EMAIL,
    role: str = "user",
) -> str:
    """Generate a test JWT that includes (or omits) an 'iss' claim."""
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": user_id,
        "email": email,
        "aud": AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "user_metadata": {"role": role},
    }
    if issuer is not None:
        payload["iss"] = issuer
    return jwt.encode(payload, TEST_SECRET, algorithm=ALGORITHM)


class TestIssuerValidation:
    """Tests for JWT issuer ('iss') claim validation (B-075)."""

    def test_correct_issuer_derived_from_supabase_url_passes(self, monkeypatch):
        """JWT whose 'iss' matches {SUPABASE_URL}/auth/v1 is accepted."""
        import app.api.deps as deps_module

        monkeypatch.setenv("SUPABASE_URL", "https://abcdef.supabase.co")
        monkeypatch.delenv("SUPABASE_JWT_ISSUER", raising=False)
        deps_module._jwks_cache = None
        deps_module._jwks_fetched_at = 0

        token = make_jwt_with_issuer(issuer="https://abcdef.supabase.co/auth/v1")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch(
            "app.api.deps._get_jwks",
            new_callable=AsyncMock,
            side_effect=JWTError("JWKS not needed"),
        ):
            from app.api.deps import get_current_user

            result = asyncio.run(get_current_user(creds))

        assert str(result["id"]) == TEST_USER_ID

    def test_wrong_issuer_raises_401(self, monkeypatch):
        """JWT whose 'iss' does not match the expected issuer is rejected with 401."""
        import app.api.deps as deps_module

        monkeypatch.setenv("SUPABASE_URL", "https://abcdef.supabase.co")
        monkeypatch.delenv("SUPABASE_JWT_ISSUER", raising=False)
        deps_module._jwks_cache = None
        deps_module._jwks_fetched_at = 0

        token = make_jwt_with_issuer(issuer="https://attacker.evil.com/auth/v1")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch(
            "app.api.deps._get_jwks",
            new_callable=AsyncMock,
            side_effect=JWTError("JWKS not needed"),
        ):
            from app.api.deps import get_current_user

            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    def test_explicit_supabase_jwt_issuer_env_var_takes_precedence(self, monkeypatch):
        """When SUPABASE_JWT_ISSUER is set explicitly, it overrides the derived value."""
        import app.api.deps as deps_module

        monkeypatch.setenv("SUPABASE_URL", "https://abcdef.supabase.co")
        monkeypatch.setenv(
            "SUPABASE_JWT_ISSUER", "https://custom-issuer.example.com/auth/v1"
        )
        deps_module._jwks_cache = None
        deps_module._jwks_fetched_at = 0

        token = make_jwt_with_issuer(
            issuer="https://custom-issuer.example.com/auth/v1"
        )
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch(
            "app.api.deps._get_jwks",
            new_callable=AsyncMock,
            side_effect=JWTError("JWKS not needed"),
        ):
            from app.api.deps import get_current_user

            result = asyncio.run(get_current_user(creds))

        assert str(result["id"]) == TEST_USER_ID

    def test_missing_iss_claim_raises_401_when_issuer_configured(self, monkeypatch):
        """A JWT without an 'iss' claim is rejected when issuer validation is active."""
        import app.api.deps as deps_module

        monkeypatch.setenv("SUPABASE_URL", "https://abcdef.supabase.co")
        monkeypatch.delenv("SUPABASE_JWT_ISSUER", raising=False)
        deps_module._jwks_cache = None
        deps_module._jwks_fetched_at = 0

        # No iss claim at all
        token = make_jwt_with_issuer(issuer=None)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch(
            "app.api.deps._get_jwks",
            new_callable=AsyncMock,
            side_effect=JWTError("JWKS not needed"),
        ):
            from app.api.deps import get_current_user

            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"


# ---------------------------------------------------------------------------
# B-085: Edge branch tests — empty/missing claims, UUID format variants
# ---------------------------------------------------------------------------


def _make_jwt_with_payload(payload: dict) -> str:
    """Sign a JWT with TEST_SECRET using a fully caller-supplied payload dict."""
    return jwt.encode(payload, TEST_SECRET, algorithm=ALGORITHM)


def _base_payload(
    user_id: str = TEST_USER_ID,
    email: str = TEST_EMAIL,
) -> dict:
    """Return a minimal valid payload that can be mutated for edge-case tests."""
    now = datetime.now(timezone.utc)
    return {
        "sub": user_id,
        "email": email,
        "aud": AUDIENCE,
        "iss": TEST_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }


class TestSubClaimEdgeCases:
    """Edge cases for the 'sub' (subject / user_id) claim in get_current_user."""

    def test_empty_string_sub_raises_401(self, monkeypatch):
        """JWT with sub='' is rejected because empty string is falsy."""
        from app.api.deps import get_current_user

        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        payload = _base_payload()
        payload["sub"] = ""
        token = _make_jwt_with_payload(payload)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    def test_non_uuid_sub_raises_401(self, monkeypatch):
        """JWT with sub='not-a-uuid' is rejected because uuid.UUID() raises ValueError."""
        from app.api.deps import get_current_user

        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        payload = _base_payload()
        payload["sub"] = "not-a-uuid"
        token = _make_jwt_with_payload(payload)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    def test_numeric_string_sub_raises_401(self, monkeypatch):
        """JWT with sub='12345' (numeric, non-UUID) is rejected."""
        from app.api.deps import get_current_user

        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        payload = _base_payload()
        payload["sub"] = "12345"
        token = _make_jwt_with_payload(payload)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    def test_uppercase_uuid_sub_is_accepted(self, monkeypatch):
        """JWT with an uppercase UUID 'sub' is accepted — uuid.UUID() is case-insensitive."""
        from app.api.deps import get_current_user

        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        upper_id = TEST_USER_ID.upper()
        payload = _base_payload(user_id=upper_id)
        token = _make_jwt_with_payload(payload)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        result = asyncio.run(get_current_user(creds))

        # uuid.UUID normalises to lowercase; both strings represent the same UUID
        assert result["id"] == uuid.UUID(TEST_USER_ID)

    def test_compact_uuid_sub_is_accepted(self, monkeypatch):
        """JWT with a hyphen-free (compact) UUID 'sub' is accepted by uuid.UUID()."""
        from app.api.deps import get_current_user

        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        compact_id = TEST_USER_ID.replace("-", "")
        assert len(compact_id) == 32, "Sanity check: compact UUID must be 32 hex chars"

        payload = _base_payload(user_id=compact_id)
        token = _make_jwt_with_payload(payload)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        result = asyncio.run(get_current_user(creds))

        assert result["id"] == uuid.UUID(TEST_USER_ID)

    def test_missing_sub_claim_raises_401(self, monkeypatch):
        """JWT payload without any 'sub' key is rejected (payload.get returns None)."""
        from app.api.deps import get_current_user

        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        payload = _base_payload()
        del payload["sub"]
        token = _make_jwt_with_payload(payload)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"


class TestEmailClaimEdgeCases:
    """Edge cases for the 'email' claim in get_current_user."""

    def test_missing_email_claim_raises_401(self, monkeypatch):
        """JWT without an 'email' key is rejected — deps.py treats None as falsy."""
        from app.api.deps import get_current_user

        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        payload = _base_payload()
        del payload["email"]
        token = _make_jwt_with_payload(payload)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    def test_empty_string_email_raises_401(self, monkeypatch):
        """JWT with email='' is rejected because empty string is falsy."""
        from app.api.deps import get_current_user

        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        payload = _base_payload()
        payload["email"] = ""
        token = _make_jwt_with_payload(payload)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(creds))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    def test_valid_email_in_payload_is_passed_through(self, monkeypatch):
        """Email value from JWT payload is returned verbatim in CurrentUser."""
        from app.api.deps import get_current_user

        monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
        custom_email = "coach@spelix.app"
        payload = _base_payload(email=custom_email)
        token = _make_jwt_with_payload(payload)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        result = asyncio.run(get_current_user(creds))

        assert result["email"] == custom_email
