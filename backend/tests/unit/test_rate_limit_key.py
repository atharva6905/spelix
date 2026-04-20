"""Unit tests for rate_limit._get_user_key — IP-based rate limit key.

M-02 fix: JWT sub extraction was removed because unverified token payloads
are spoofable. _get_user_key now always returns the client IP address.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock

from app.rate_limit import _get_user_key


def _make_request(auth_header: str | None = None, client_ip: str = "127.0.0.1") -> MagicMock:
    request = MagicMock()
    headers = {}
    if auth_header is not None:
        headers["authorization"] = auth_header
    request.headers = headers
    request.scope = {"type": "http"}
    request.client = MagicMock()
    request.client.host = client_ip
    return request


def _make_jwt(payload: dict) -> str:
    """Build a fake JWT (header.payload.sig) with the given payload."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.fake_signature"


class TestGetUserKey:
    def test_returns_ip_without_auth_header(self) -> None:
        """No auth header — must return client IP."""
        request = _make_request(None)
        result = _get_user_key(request)
        assert result == "127.0.0.1"

    def test_returns_ip_with_bearer_jwt(self) -> None:
        """Even a well-formed JWT — must return client IP, never the sub."""
        user_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        token = _make_jwt({"sub": user_id, "exp": 9999999999})
        request = _make_request(f"Bearer {token}")
        result = _get_user_key(request)
        assert result == "127.0.0.1"
        assert result != user_id

    def test_returns_ip_with_non_bearer_auth(self) -> None:
        request = _make_request("Basic dXNlcjpwYXNz")
        result = _get_user_key(request)
        assert result == "127.0.0.1"

    def test_returns_ip_with_malformed_jwt(self) -> None:
        request = _make_request("Bearer not.a.valid.jwt.at.all")
        result = _get_user_key(request)
        assert result == "127.0.0.1"

    def test_returns_ip_when_sub_missing_from_jwt(self) -> None:
        token = _make_jwt({"exp": 9999999999})  # no sub
        request = _make_request(f"Bearer {token}")
        result = _get_user_key(request)
        assert result == "127.0.0.1"

    def test_returns_correct_ip_for_different_clients(self) -> None:
        """Different client IPs produce different rate-limit keys."""
        request_a = _make_request(client_ip="10.0.0.1")
        request_b = _make_request(client_ip="10.0.0.2")
        assert _get_user_key(request_a) == "10.0.0.1"
        assert _get_user_key(request_b) == "10.0.0.2"

    def test_forged_jwt_with_different_sub_uses_ip_not_sub(self) -> None:
        """M-02: A forged JWT with a victim's sub must NOT be used as the rate-limit key.

        An attacker can craft a JWT with an arbitrary sub claim (invalid
        signature). The old code decoded without verification and returned
        the victim's sub, allowing quota exhaustion against any user.
        After the fix, _get_user_key must return the client IP, never the
        forged sub.
        """
        victim_sub = "victim-user-id-12345"
        # Forge a JWT with the victim's sub but an invalid signature
        forged_token = _make_jwt({"sub": victim_sub, "exp": 9999999999})
        request = _make_request(f"Bearer {forged_token}")
        result = _get_user_key(request)
        # Must NOT return the victim's sub — must use IP instead
        assert result != victim_sub, (
            "M-02: _get_user_key returned the forged JWT sub — unverified JWT "
            "payloads must never be trusted for rate limiting."
        )
        # Result must be the IP address
        assert result == "127.0.0.1"
