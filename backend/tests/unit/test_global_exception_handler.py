"""Tests for the global Exception handler in app.main.

Regression coverage for the production outage where an unhandled
``RuntimeError`` from ``StorageService`` escaped FastAPI's exception
middleware AND ``CORSMiddleware``, causing uvicorn to emit a plain-text
``Internal Server Error`` (21 bytes, no JSON envelope, no
``Access-Control-Allow-Origin`` header). Browsers then reported the
failure as a misleading "CORS policy" error, hiding the real bug for
the entire existence of Phase 0 + Phase 1.

The fix: a global ``@app.exception_handler(Exception)`` that wraps any
non-``HTTPException`` raised by a route into a JSON envelope with the
correct CORS headers attached, so future crashes show the real error
instead of a CORS red herring.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


# Register a route that intentionally raises a non-HTTPException so the
# global handler is exercised. Adding this once at module-import time is
# safe because no other test hits this path. The path is namespaced under
# ``/__test__`` to make accidental discovery impossible.
@app.get("/__test__/boom")
async def _boom_for_global_handler_test() -> dict[str, str]:
    raise RuntimeError("synthetic crash for global handler test")


class TestGlobalExceptionHandler:
    def test_unhandled_exception_returns_500_json_envelope(self) -> None:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/__test__/boom",
            headers={"Origin": "https://www.spelix.app"},
        )

        assert response.status_code == 500
        body = response.json()
        # Match Spelix error envelope shape from backend/CLAUDE.md.
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_unhandled_exception_response_carries_cors_header(self) -> None:
        """The crucial assertion — without this, browsers see a CORS error
        instead of the real 500 and the bug stays invisible."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/__test__/boom",
            headers={"Origin": "https://www.spelix.app"},
        )

        assert response.status_code == 500
        # CORS middleware would normally attach this header on success
        # responses, but unhandled exceptions used to bypass it. The new
        # global handler must put it back.
        assert (
            response.headers.get("access-control-allow-origin")
            == "https://www.spelix.app"
        )

    def test_unhandled_exception_does_not_leak_internal_message(self) -> None:
        """The synthetic message must not appear in the response body —
        we don't want to leak Python tracebacks or internal state to clients.
        """
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/__test__/boom",
            headers={"Origin": "https://www.spelix.app"},
        )

        body_text = response.text
        assert "synthetic crash" not in body_text
        assert "Traceback" not in body_text
