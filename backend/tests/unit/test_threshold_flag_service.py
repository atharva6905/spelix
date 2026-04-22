from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.config import ThresholdConfig
from app.models.threshold_flag import ThresholdFlag
from app.services.threshold_flag import (
    InvalidThresholdKey,
    ThresholdFlagService,
)


pytestmark = pytest.mark.asyncio


def _make_service(repo: AsyncMock, cfg: ThresholdConfig | None = None) -> ThresholdFlagService:
    return ThresholdFlagService(repo=repo, config=cfg or ThresholdConfig())


async def test_get_listing_excludes_non_angle_sections():
    svc = _make_service(repo=AsyncMock())

    listing = svc.get_listing()

    assert listing.version == "v1"
    assert set(listing.sections.keys()) == {"squat", "bench", "deadlift", "control"}
    for rows in listing.sections.values():
        for row in rows:
            assert row.value is not None


async def test_get_listing_populates_provenance():
    svc = _make_service(repo=AsyncMock())

    listing = svc.get_listing()
    squat_rows = listing.sections["squat"]
    valgus = next(r for r in squat_rows if r.key == "knee_valgus_caution_deg")

    assert valgus.unit == "degrees"
    assert valgus.provenance_citation == "Myer et al. 2010"


async def test_create_flag_snapshots_current_value_and_citation():
    repo = AsyncMock()
    repo.create.side_effect = lambda flag: flag  # echo the persisted flag
    svc = _make_service(repo=repo)

    reviewer_id = uuid4()
    result = await svc.create_flag(
        reviewer_id=reviewer_id,
        section="squat",
        key="knee_valgus_caution_deg",
        proposed_value=8.0,
        proposed_citation="Krosshaug 2016 — 8° not replicated",
        rationale="Original Myer finding did not replicate in larger cohorts.",
    )

    assert result.current_value == 5.0
    assert result.current_citation == "Myer et al. 2010"
    assert result.proposed_value == 8.0
    assert result.reviewer_id == reviewer_id
    assert result.status == "open"
    repo.create.assert_awaited_once()


async def test_create_flag_rejects_unknown_key():
    repo = AsyncMock()
    svc = _make_service(repo=repo)

    with pytest.raises(InvalidThresholdKey):
        await svc.create_flag(
            reviewer_id=uuid4(),
            section="squat",
            key="not_a_real_threshold",
            proposed_value=1.0,
            proposed_citation="fake 2024",
            rationale="An adequate-length rationale explaining the issue.",
        )
    repo.create.assert_not_awaited()


async def test_resolve_flag_updates_status_and_resolver():
    repo = AsyncMock()
    flag_id = uuid4()
    admin_id = uuid4()
    resolved_flag = ThresholdFlag(
        id=flag_id,
        reviewer_id=uuid4(),
        section="squat",
        key="knee_valgus_caution_deg",
        current_value=5.0,
        current_citation="Myer et al. 2010",
        proposed_value=8.0,
        proposed_citation="Krosshaug 2016",
        rationale="An adequate-length rationale explaining the issue.",
        status="resolved",
    )
    repo.update_status.return_value = resolved_flag
    svc = _make_service(repo=repo)

    out = await svc.resolve_flag(
        flag_id=flag_id,
        status="resolved",
        resolution_note="Merged PR #999",
        resolver_id=admin_id,
    )

    assert out is resolved_flag
    repo.update_status.assert_awaited_once_with(
        flag_id,
        status="resolved",
        resolution_note="Merged PR #999",
        resolved_by=admin_id,
    )
