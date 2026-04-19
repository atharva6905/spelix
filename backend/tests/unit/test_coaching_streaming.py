"""Unit tests for CoachingService streaming path (D-049)."""

from __future__ import annotations

import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import ThresholdConfig
from app.schemas.coaching import CoachingOutput
from app.services.coaching import CoachingService


def _make_partial_output_with_dict_citations() -> CoachingOutput:
    """Build a CoachingOutput whose citations is a list[dict] masquerading as list[Citation].

    Mirrors instructor.create_partial's intermediate shape: the outer
    model has validated, but nested list items are still raw dicts
    carrying the right keys. Pydantic v2 emits
    PydanticSerializationUnexpectedValueWarning when such an object is
    serialized via model_dump_json under strict type expectations.
    """
    return CoachingOutput.model_construct(
        summary="partial summary",
        strengths=["tempo"],
        issues=[],
        correction_plan=[],
        recommended_cues=[],
        citations=[  # type: ignore[arg-type]
            {"title": "S2010", "authors": ["Schoenfeld"], "year": 2010}
        ],
        safety_warnings=[],
        confidence_level="High",
        dimension_addressed="Movement Quality",
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )


@pytest.mark.asyncio
async def test_generate_coaching_streaming_emits_no_pydantic_serializer_warnings() -> None:
    """D-049: SSE publish path must suppress the per-chunk
    PydanticSerializationUnexpectedValueWarning that fires when instructor's
    create_partial yields dict-shaped nested items (citations) against a
    schema declaring list[Citation].

    The warning is benign (the final snapshot is fully validated) but
    spams worker logs. Fix is model_dump_json(warnings=False) on partial
    snapshots only — the final validated CoachingOutput is returned
    unchanged.
    """

    async def _fake_create_partial(**kwargs):  # type: ignore[no-untyped-def]
        yield _make_partial_output_with_dict_citations()
        yield _make_partial_output_with_dict_citations()

    mock_instructor_client = MagicMock()
    mock_instructor_client.chat.completions.create_partial = _fake_create_partial

    pubsub_redis = MagicMock()
    pubsub_redis.publish = AsyncMock()

    mock_anthropic = MagicMock()

    with patch("app.services.coaching.instructor") as mock_instructor_module:
        mock_instructor_module.from_anthropic.return_value = mock_instructor_client

        svc = CoachingService(anthropic_client=mock_anthropic)

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            await svc.generate_coaching_streaming(
                exercise_type="squat",
                exercise_variant="high_bar",
                rep_metrics=[],
                confidence_score=0.9,
                thresholds=ThresholdConfig(),
                analysis_id="fake-uuid",
                pubsub_redis=pubsub_redis,
            )

    # Pydantic v2 emits a UserWarning whose message contains
    # "PydanticSerializationUnexpectedValue" when model_dump_json is called on
    # a model_construct'd object that has dict-shaped nested items in a
    # list[SomeModel] field.  There is no named class for this in pydantic.warnings
    # on the installed version, so we match on the message string.
    serializer_warnings = [
        w for w in captured
        if issubclass(w.category, UserWarning)
        and "PydanticSerializationUnexpectedValue" in str(w.message)
    ]
    assert serializer_warnings == [], (
        f"expected zero PydanticSerializationUnexpectedValue UserWarning from the "
        f"SSE publish path (D-049); got {len(serializer_warnings)}:\n"
        + "\n".join(f"  - {w.message}" for w in serializer_warnings)
    )
