"""Unit tests for the beta-request endpoint (mocked service layer)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.beta import _get_service, router as beta_router
from app.services.beta_request import BetaRequestConflictError


def _make_row(email: str = "new@example.com"):
    return SimpleNamespace(
        id=uuid4(),
        email=email,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )


def _make_app(service_mock: AsyncMock) -> FastAPI:
    from limits.storage import MemoryStorage

    from app.rate_limit import limiter

    app = FastAPI()
    # Use in-memory storage to avoid Redis dependency in unit tests
    mem = MemoryStorage()
    limiter._storage = mem
    limiter._limiter.storage = mem
    app.state.limiter = limiter
    app.include_router(beta_router, prefix="/api/v1/beta")
    app.dependency_overrides[_get_service] = lambda: service_mock
    return app


@pytest.mark.asyncio
async def test_valid_submission_returns_201() -> None:
    service = AsyncMock()
    service.submit.return_value = _make_row(email="newuser@example.com")
    app = _make_app(service)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/v1/beta/requests",
            json={
                "email": "NewUser@Example.com",
                "source": "hero",
                "consented_to_beta_terms": True,
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "newuser@example.com"
    assert body["status"] == "pending"
    assert "id" in body
    service.submit.assert_awaited_once()
    call = service.submit.await_args
    assert call.args[0].email == "newuser@example.com"


@pytest.mark.asyncio
async def test_invalid_email_returns_422() -> None:
    service = AsyncMock()
    app = _make_app(service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/beta/requests", json={
            "email": "not-an-email", "source": "hero", "consented_to_beta_terms": True,
        })
    assert resp.status_code == 422
    service.submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_consent_false_returns_422() -> None:
    service = AsyncMock()
    app = _make_app(service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/beta/requests", json={
            "email": "a@b.com", "source": "hero", "consented_to_beta_terms": False,
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_email_returns_409() -> None:
    service = AsyncMock()
    service.submit.side_effect = BetaRequestConflictError("dup")
    app = _make_app(service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/beta/requests", json={
            "email": "dup@example.com", "source": "final_cta", "consented_to_beta_terms": True,
        })
    assert resp.status_code == 409
    assert "beta_request_duplicate" in resp.text


@pytest.mark.asyncio
async def test_invalid_source_returns_422() -> None:
    service = AsyncMock()
    app = _make_app(service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/beta/requests", json={
            "email": "a@b.com", "source": "facebook_ad", "consented_to_beta_terms": True,
        })
    assert resp.status_code == 422
