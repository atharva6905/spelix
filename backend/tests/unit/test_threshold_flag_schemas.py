from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.threshold_flag import (
    ThresholdFlagCreate,
    ThresholdFlagResolveAction,
    ThresholdRow,
)


def test_threshold_row_requires_value_and_unit():
    row = ThresholdRow(
        section="squat",
        key="knee_valgus_caution_deg",
        value=5.0,
        unit="degrees",
        provenance_citation="Myer et al. 2010",
        last_modified_by="expert_reviewer",
    )
    assert row.section == "squat"
    assert row.value == 5.0


def test_flag_create_rejects_short_rationale():
    with pytest.raises(ValidationError):
        ThresholdFlagCreate(
            section="squat",
            key="knee_valgus_caution_deg",
            proposed_value=8.0,
            proposed_citation="Krosshaug 2016",
            rationale="too short",
        )


def test_flag_create_rejects_short_citation():
    with pytest.raises(ValidationError):
        ThresholdFlagCreate(
            section="squat",
            key="knee_valgus_caution_deg",
            proposed_value=8.0,
            proposed_citation="2016",
            rationale="An adequate-length rationale explaining the issue.",
        )


def test_flag_create_accepts_minimum_valid_payload():
    payload = ThresholdFlagCreate(
        section="bench",
        key="grip_width_biacromial_ratio_max",
        proposed_value=1.7,
        proposed_citation="Smith 2024 — wider grip safe",
        rationale="Recent evidence supports looser biacromial ratio limits.",
    )
    assert payload.proposed_value == 1.7


def test_flag_create_rejects_unknown_section():
    with pytest.raises(ValidationError):
        ThresholdFlagCreate(
            section="shoulder_press",
            key="elbow_flare_caution_deg",
            proposed_value=40.0,
            proposed_citation="Smith 2024",
            rationale="An adequate-length rationale explaining the issue.",
        )


def test_resolve_action_requires_valid_status():
    with pytest.raises(ValidationError):
        ThresholdFlagResolveAction(status="pending", resolution_note=None)

    action = ThresholdFlagResolveAction(
        status="resolved", resolution_note="Shipped in PR #999."
    )
    assert action.status == "resolved"
