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
    depth = next(r for r in squat_rows if r.key == "depth_parallel_hip_angle_deg")

    assert depth.unit == "degrees"
    assert "Schoenfeld" in depth.provenance_citation


async def test_create_flag_snapshots_current_value_and_citation():
    repo = AsyncMock()
    repo.create.side_effect = lambda flag: flag  # echo the persisted flag
    svc = _make_service(repo=repo)

    reviewer_id = uuid4()
    result = await svc.create_flag(
        reviewer_id=reviewer_id,
        section="squat",
        key="torso_lean_caution_deg",
        proposed_value=50.0,
        proposed_citation="Fry 2003 — revisit caution threshold",
        rationale="An adequate-length rationale revisiting the torso-lean caution threshold for squats.",
    )

    assert result.current_value == 45.0
    assert result.current_citation == "Fry et al. 2003"
    assert result.proposed_value == 50.0
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


async def test_get_listing_skips_underscore_keys() -> None:
    """Keys starting with _ (comment/metadata) are skipped in the listing."""
    from unittest.mock import MagicMock

    mock_config = MagicMock()
    mock_config.version = "v1"
    # Return a section with one underscore key (should be skipped) and one valid key
    mock_config.get_section.return_value = {
        "_comment": "This is a comment",
        "some_threshold": {"value": 5.0, "unit": "degrees"},
        "_metadata": {"author": "test"},
    }

    svc = ThresholdFlagService(repo=AsyncMock(), config=mock_config)
    listing = svc.get_listing()

    for rows in listing.sections.values():
        for row in rows:
            assert not row.key.startswith("_")


async def test_get_listing_skips_non_dict_entries() -> None:
    """Entries that are not dicts or lack 'value' key are skipped."""
    from unittest.mock import MagicMock

    mock_config = MagicMock()
    mock_config.version = "v1"
    mock_config.get_section.return_value = {
        "valid_key": {"value": 5.0, "unit": "degrees"},
        "bad_string_entry": "not a dict",
        "bad_list_entry": [1, 2, 3],
        "missing_value_dict": {"unit": "degrees"},  # no 'value' key
    }

    svc = ThresholdFlagService(repo=AsyncMock(), config=mock_config)
    listing = svc.get_listing()

    for rows in listing.sections.values():
        assert all(row.key == "valid_key" for row in rows)


async def test_create_flag_with_unvalidated_metrics_section_bypasses_config_lookup():
    """Session 3 (ADR-SAGITTAL-METRICS-REGISTRY): the 'unvalidated_metrics'
    section names sagittal metrics that have NO entry in thresholds_v1.json,
    so the service must NOT raise InvalidThresholdKey. current_value defaults
    to 0.0 and current_citation to None for these proposals."""
    repo = AsyncMock()
    repo.create.side_effect = lambda flag: flag  # echo the persisted flag
    svc = _make_service(repo=repo)

    reviewer_id = uuid4()
    result = await svc.create_flag(
        reviewer_id=reviewer_id,
        section="unvalidated_metrics",
        key="ankle_dorsiflexion_deg",
        proposed_value=15.0,
        proposed_citation="Smith 2023 -- ankle dorsiflexion ROM norms",
        rationale=(
            "Current threshold absent; literature suggests 15 deg minimum "
            "for full squat depth without heel rise."
        ),
    )

    assert result.section == "unvalidated_metrics"
    assert result.key == "ankle_dorsiflexion_deg"
    assert result.current_value == 0.0
    assert result.current_citation is None
    assert result.proposed_value == 15.0
    assert result.reviewer_id == reviewer_id
    assert result.status == "open"
    repo.create.assert_awaited_once()


async def test_create_flag_unvalidated_metrics_does_not_raise_on_missing_v1_key():
    """The bypass must hold for ANY key under unvalidated_metrics --
    Sessions 4-7 will write new keys to JSONB before threshold values exist."""
    repo = AsyncMock()
    repo.create.side_effect = lambda flag: flag
    svc = _make_service(repo=repo)

    # A key that absolutely does not exist in thresholds_v1.json.
    result = await svc.create_flag(
        reviewer_id=uuid4(),
        section="unvalidated_metrics",
        key="lumbar_flexion_proxy_delta_deg",
        proposed_value=20.0,
        proposed_citation="McGill 2014 -- spine flexion thresholds",
        rationale=(
            "Sagittal lumbar proxy uncomputed today; propose 20 deg as the "
            "upper bound based on cadaver flexion-tolerance studies."
        ),
    )
    assert result.current_value == 0.0


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
