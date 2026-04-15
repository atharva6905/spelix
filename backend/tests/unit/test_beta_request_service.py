"""Unit tests for BetaRequestService (pure — mocks the repository)."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.schemas.beta_request import BetaRequestCreate
from app.services.beta_request import (
    BetaRequestConflictError,
    BetaRequestService,
)


def _make_row(email: str = "a@b.com", source: str = "hero"):
    from types import SimpleNamespace

    return SimpleNamespace(
        id=uuid4(),
        email=email,
        source=source,
        status="pending",
        created_at="2026-04-15T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_submit_calls_repo_create_and_returns_row() -> None:
    repo = AsyncMock()
    repo.create.return_value = _make_row()
    service = BetaRequestService(repo=repo)

    payload = BetaRequestCreate(
        email="user@example.com",
        source="hero",
        consented_to_beta_terms=True,
    )
    row = await service.submit(payload)

    repo.create.assert_awaited_once_with(
        email="user@example.com", source="hero", consented=True
    )
    assert row.email == "a@b.com"


@pytest.mark.asyncio
async def test_submit_translates_integrity_error_to_conflict() -> None:
    repo = AsyncMock()
    repo.create.side_effect = IntegrityError("stmt", {}, Exception("dup"))
    service = BetaRequestService(repo=repo)

    payload = BetaRequestCreate(
        email="dup@example.com",
        source="hero",
        consented_to_beta_terms=True,
    )
    with pytest.raises(BetaRequestConflictError):
        await service.submit(payload)
