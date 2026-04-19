"""Tests for CoachBrainEntry Pydantic schemas.

TDD gate for P2-023 (FR-BRAIN-01).

Covers:
- CoachBrainEntry validates with all fields present
- Status literal validation: only seed/active/deprecated accepted
- CoachBrainEntryCreate defaults (id/timestamps absent, confirmation_count=0)
- CoachBrainEntryUpdate allows all fields optional
- CoachBrainPayload has required Qdrant payload fields
- Round-trip serialisation for all three models
- exercise CHECK constraint values (squat/bench/deadlift only)
- phase CHECK constraint values (setup/descent/bottom/ascent/lockout/general)
- entry_type CHECK constraint values (cue/correction/principle/drill)
- source_analysis_ids is list[UUID]
- trigger_tags is list[str] matching ARRAY(Text) in migration 004
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_entry_dict() -> dict:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": uuid.uuid4(),
        "content": "Brace your core before initiating the descent.",
        "exercise": "squat",
        "phase": "setup",
        "entry_type": "cue",
        "status": "seed",
        "confirmation_count": 0,
        "source_analysis_ids": [],
        "trigger_tags": [],
        "confidence_score": None,
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }


# ---------------------------------------------------------------------------
# CoachBrainEntry
# ---------------------------------------------------------------------------


class TestCoachBrainEntry:
    def test_round_trip_serialisation(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        data = _make_valid_entry_dict()
        entry = CoachBrainEntry(**data)
        dumped = entry.model_dump()
        assert dumped["content"] == data["content"]
        assert dumped["exercise"] == "squat"
        assert dumped["status"] == "seed"

    def test_all_status_values_accepted(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        for status in ("seed", "active", "deprecated"):
            data = {**_make_valid_entry_dict(), "status": status}
            entry = CoachBrainEntry(**data)
            assert entry.status == status

    def test_invalid_status_rejected(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        with pytest.raises(ValidationError):
            CoachBrainEntry(**{**_make_valid_entry_dict(), "status": "pending"})

    def test_invalid_status_approved_rejected(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        with pytest.raises(ValidationError):
            CoachBrainEntry(**{**_make_valid_entry_dict(), "status": "approved"})

    def test_invalid_status_rejected_literal_rejected(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        with pytest.raises(ValidationError):
            CoachBrainEntry(**{**_make_valid_entry_dict(), "status": "rejected"})

    def test_all_exercise_values_accepted(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        for ex in ("squat", "bench", "deadlift"):
            data = {**_make_valid_entry_dict(), "exercise": ex}
            entry = CoachBrainEntry(**data)
            assert entry.exercise == ex

    def test_invalid_exercise_rejected(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        with pytest.raises(ValidationError):
            CoachBrainEntry(**{**_make_valid_entry_dict(), "exercise": "pullup"})

    def test_all_phase_values_accepted(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        for phase in ("setup", "descent", "bottom", "ascent", "lockout", "general"):
            data = {**_make_valid_entry_dict(), "phase": phase}
            entry = CoachBrainEntry(**data)
            assert entry.phase == phase

    def test_invalid_phase_rejected(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        with pytest.raises(ValidationError):
            CoachBrainEntry(**{**_make_valid_entry_dict(), "phase": "warmup"})

    def test_all_entry_type_values_accepted(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        for et in ("cue", "correction", "principle", "drill"):
            data = {**_make_valid_entry_dict(), "entry_type": et}
            entry = CoachBrainEntry(**data)
            assert entry.entry_type == et

    def test_invalid_entry_type_rejected(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        # "pattern" and "insight" are NOT valid per migration 004
        with pytest.raises(ValidationError):
            CoachBrainEntry(**{**_make_valid_entry_dict(), "entry_type": "pattern"})

    def test_invalid_entry_type_insight_rejected(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        with pytest.raises(ValidationError):
            CoachBrainEntry(**{**_make_valid_entry_dict(), "entry_type": "insight"})

    def test_source_analysis_ids_is_list_of_uuids(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        ids = [uuid.uuid4(), uuid.uuid4()]
        data = {**_make_valid_entry_dict(), "source_analysis_ids": ids}
        entry = CoachBrainEntry(**data)
        assert len(entry.source_analysis_ids) == 2
        assert all(isinstance(i, uuid.UUID) for i in entry.source_analysis_ids)

    def test_trigger_tags_is_list_of_str(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        data = {**_make_valid_entry_dict(), "trigger_tags": ["knee_cave", "forward_lean"]}
        entry = CoachBrainEntry(**data)
        assert entry.trigger_tags == ["knee_cave", "forward_lean"]

    def test_confidence_score_can_be_none(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        data = {**_make_valid_entry_dict(), "confidence_score": None}
        entry = CoachBrainEntry(**data)
        assert entry.confidence_score is None

    def test_confidence_score_accepts_float(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        data = {**_make_valid_entry_dict(), "confidence_score": 0.875}
        entry = CoachBrainEntry(**data)
        assert entry.confidence_score == pytest.approx(0.875)

    def test_metadata_defaults_to_empty_dict(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        data = {**_make_valid_entry_dict(), "metadata": {}}
        entry = CoachBrainEntry(**data)
        assert entry.metadata == {}

    def test_id_is_uuid(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        entry = CoachBrainEntry(**_make_valid_entry_dict())
        assert isinstance(entry.id, uuid.UUID)

    def test_timestamps_are_datetime(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntry

        entry = CoachBrainEntry(**_make_valid_entry_dict())
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.updated_at, datetime)


# ---------------------------------------------------------------------------
# CoachBrainEntryCreate
# ---------------------------------------------------------------------------


class TestCoachBrainEntryCreate:
    def _valid_create_dict(self) -> dict:
        return {
            "content": "Drive your knees out over your toes.",
            "exercise": "squat",
            "phase": "descent",
            "entry_type": "cue",
        }

    def test_minimal_create_succeeds(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryCreate

        create = CoachBrainEntryCreate(**self._valid_create_dict())
        assert create.content == "Drive your knees out over your toes."

    def test_status_defaults_to_seed(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryCreate

        create = CoachBrainEntryCreate(**self._valid_create_dict())
        assert create.status == "seed"

    def test_confirmation_count_defaults_to_zero(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryCreate

        create = CoachBrainEntryCreate(**self._valid_create_dict())
        assert create.confirmation_count == 0

    def test_source_analysis_ids_defaults_to_empty(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryCreate

        create = CoachBrainEntryCreate(**self._valid_create_dict())
        assert create.source_analysis_ids == []

    def test_trigger_tags_defaults_to_empty(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryCreate

        create = CoachBrainEntryCreate(**self._valid_create_dict())
        assert create.trigger_tags == []

    def test_no_id_field(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryCreate

        create = CoachBrainEntryCreate(**self._valid_create_dict())
        assert not hasattr(create, "id") or not hasattr(CoachBrainEntryCreate.model_fields, "id")
        # id must not be a required field on Create
        dumped = create.model_dump()
        assert "id" not in dumped

    def test_no_created_at_field(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryCreate

        create = CoachBrainEntryCreate(**self._valid_create_dict())
        dumped = create.model_dump()
        assert "created_at" not in dumped

    def test_optional_phase_none(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryCreate

        data = {**self._valid_create_dict(), "phase": None}
        create = CoachBrainEntryCreate(**data)
        assert create.phase is None

    def test_all_entry_types_accepted(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryCreate

        for et in ("cue", "correction", "principle", "drill"):
            create = CoachBrainEntryCreate(**{**self._valid_create_dict(), "entry_type": et})
            assert create.entry_type == et

    def test_round_trip_serialisation(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryCreate

        create = CoachBrainEntryCreate(**self._valid_create_dict())
        dumped = create.model_dump()
        assert dumped["exercise"] == "squat"
        assert dumped["status"] == "seed"
        assert dumped["confirmation_count"] == 0


# ---------------------------------------------------------------------------
# CoachBrainEntryUpdate
# ---------------------------------------------------------------------------


class TestCoachBrainEntryUpdate:
    def test_empty_update_is_valid(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryUpdate

        update = CoachBrainEntryUpdate()
        dumped = update.model_dump(exclude_none=True)
        assert dumped == {}

    def test_partial_update_status_only(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryUpdate

        update = CoachBrainEntryUpdate(status="active")
        assert update.status == "active"

    def test_partial_update_content_only(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryUpdate

        update = CoachBrainEntryUpdate(content="Updated cue text.")
        assert update.content == "Updated cue text."

    def test_invalid_status_rejected_in_update(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryUpdate

        with pytest.raises(ValidationError):
            CoachBrainEntryUpdate(status="pending")

    def test_partial_update_confirmation_count(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryUpdate

        update = CoachBrainEntryUpdate(confirmation_count=5)
        assert update.confirmation_count == 5

    def test_partial_update_trigger_tags(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryUpdate

        update = CoachBrainEntryUpdate(trigger_tags=["hip_drop"])
        assert update.trigger_tags == ["hip_drop"]

    def test_all_fields_optional(self) -> None:
        from app.schemas.coach_brain import CoachBrainEntryUpdate

        # Supplying all update fields at once
        update = CoachBrainEntryUpdate(
            content="New cue.",
            exercise="deadlift",
            phase="lockout",
            entry_type="correction",
            status="active",
            confirmation_count=3,
            source_analysis_ids=[uuid.uuid4()],
            trigger_tags=["hip_drop"],
            confidence_score=0.9,
            metadata={"note": "reviewed"},
        )
        dumped = update.model_dump(exclude_none=True)
        assert dumped["exercise"] == "deadlift"
        assert dumped["status"] == "active"


# ---------------------------------------------------------------------------
# CoachBrainPayload
# ---------------------------------------------------------------------------


class TestCoachBrainPayload:
    def _valid_payload_dict(self) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "content": "Keep chest up throughout the squat.",
            "exercise": "squat",
            "phase": "descent",
            "entry_type": "cue",
            "status": "seed",
            "confirmation_count": 0,
            "trigger_tags": [],
        }

    def test_round_trip_serialisation(self) -> None:
        from app.schemas.coach_brain import CoachBrainPayload

        data = self._valid_payload_dict()
        payload = CoachBrainPayload(**data)
        dumped = payload.model_dump()
        assert dumped["content"] == data["content"]
        assert dumped["exercise"] == "squat"
        assert dumped["status"] == "seed"

    def test_id_is_string(self) -> None:
        """Qdrant payload stores id as string (UUID str), not UUID object."""
        from app.schemas.coach_brain import CoachBrainPayload

        payload = CoachBrainPayload(**self._valid_payload_dict())
        assert isinstance(payload.id, str)

    def test_required_qdrant_payload_fields_present(self) -> None:
        from app.schemas.coach_brain import CoachBrainPayload

        payload = CoachBrainPayload(**self._valid_payload_dict())
        dumped = payload.model_dump()
        # These are the fields Qdrant payload indexes are built on (qdrant.py)
        required = {"id", "content", "exercise", "status", "confirmation_count", "trigger_tags"}
        assert required.issubset(set(dumped.keys()))

    def test_invalid_status_rejected(self) -> None:
        from app.schemas.coach_brain import CoachBrainPayload

        data = {**self._valid_payload_dict(), "status": "approved"}
        with pytest.raises(ValidationError):
            CoachBrainPayload(**data)

    def test_invalid_exercise_rejected(self) -> None:
        from app.schemas.coach_brain import CoachBrainPayload

        data = {**self._valid_payload_dict(), "exercise": "overhead_press"}
        with pytest.raises(ValidationError):
            CoachBrainPayload(**data)

    def test_optional_phase_none(self) -> None:
        from app.schemas.coach_brain import CoachBrainPayload

        data = {**self._valid_payload_dict(), "phase": None}
        payload = CoachBrainPayload(**data)
        assert payload.phase is None

    def test_trigger_tags_is_list(self) -> None:
        from app.schemas.coach_brain import CoachBrainPayload

        data = {**self._valid_payload_dict(), "trigger_tags": ["knee_cave"]}
        payload = CoachBrainPayload(**data)
        assert payload.trigger_tags == ["knee_cave"]


# ---------------------------------------------------------------------------
# D-038: EntryTypeLiteral widening — compensation
# ---------------------------------------------------------------------------


def test_coach_brain_entry_create_accepts_compensation() -> None:
    from app.schemas.coach_brain import CoachBrainEntryCreate

    entry = CoachBrainEntryCreate(
        content="Quad-dominant ascent compensates for posterior-chain weakness",
        exercise="squat",
        phase="ascent",
        entry_type="compensation",
    )
    assert entry.entry_type == "compensation"


def test_coach_brain_candidate_create_accepts_compensation() -> None:
    from app.schemas.coach_brain_candidate import CoachBrainCandidateCreate

    candidate = CoachBrainCandidateCreate(
        exercise="squat",
        phase="descent",
        entry_type="compensation",
        content="Knee valgus compensates for weak hip abduction",
        source_analysis_ids=[uuid.uuid4()],
        lifecycle_decision="ADD",
    )
    assert candidate.entry_type == "compensation"
