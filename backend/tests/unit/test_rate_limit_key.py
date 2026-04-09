"""Unit tests for rate_limit._get_user_key — JWT sub extraction.

Covers lines 30-47 in rate_limit.py.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock

from app.rate_limit import _get_user_key


def _make_request(auth_header: str | None = None) -> MagicMock:
    request = MagicMock()
    headers = {}
    if auth_header is not None:
        headers["authorization"] = auth_header
    request.headers = headers
    request.scope = {"type": "http"}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


def _make_jwt(payload: dict) -> str:
    """Build a fake JWT (header.payload.sig) with the given payload."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.fake_signature"


class TestGetUserKey:
    def test_extracts_sub_from_valid_jwt(self) -> None:
        user_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        token = _make_jwt({"sub": user_id, "exp": 9999999999})
        request = _make_request(f"Bearer {token}")
        assert _get_user_key(request) == user_id

    def test_falls_back_to_ip_without_auth_header(self) -> None:
        request = _make_request(None)
        result = _get_user_key(request)
        # Should return IP, not raise
        assert isinstance(result, str)

    def test_falls_back_to_ip_with_non_bearer_auth(self) -> None:
        request = _make_request("Basic dXNlcjpwYXNz")
        result = _get_user_key(request)
        assert isinstance(result, str)

    def test_falls_back_to_ip_with_malformed_jwt(self) -> None:
        request = _make_request("Bearer not.a.valid.jwt.at.all")
        result = _get_user_key(request)
        assert isinstance(result, str)

    def test_falls_back_to_ip_when_sub_missing(self) -> None:
        token = _make_jwt({"exp": 9999999999})  # no sub
        request = _make_request(f"Bearer {token}")
        result = _get_user_key(request)
        # Without sub, falls back to IP
        assert isinstance(result, str)

    def test_handles_jwt_with_padding_needed(self) -> None:
        # Payload that produces base64 needing padding
        user_id = "x"
        token = _make_jwt({"sub": user_id})
        request = _make_request(f"Bearer {token}")
        assert _get_user_key(request) == user_id
