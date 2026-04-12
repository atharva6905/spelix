"""Tests for SafetyFilter — safety language post-filter (P2-018).

Requirements: FR-AICP-14

TDD protocol: tests written before implementation.
"""

from __future__ import annotations

from app.schemas.coaching import CoachingOutput, Issue

MANDATORY_DISCLAIMER = (
    "This feedback is for educational purposes only and is not a "
    "substitute for in-person coaching or medical advice."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coaching_output(**overrides) -> CoachingOutput:
    data = {
        "summary": "Good squat session overall.",
        "strengths": ["Consistent tempo", "Good bracing"],
        "issues": [],
        "correction_plan": ["Drive knees out."],
        "disclaimer": MANDATORY_DISCLAIMER,
        "raw_prompt_tokens": 400,
        "raw_completion_tokens": 200,
    }
    data.update(overrides)
    return CoachingOutput(**data)


# ---------------------------------------------------------------------------
# Prohibited phrase replacement tests
# ---------------------------------------------------------------------------


def test_replace_injury_risk_in_summary() -> None:
    from app.services.safety_filter import SafetyFilter

    output = _make_coaching_output(summary="This presents an injury risk to the lifter.")
    result = SafetyFilter.apply(output)

    assert "injury risk" not in result.output.summary.lower()
    assert "movement quality concern" in result.output.summary.lower()
    assert result.phrases_replaced >= 1


def test_replace_injury_prevention_in_issue_description() -> None:
    from app.services.safety_filter import SafetyFilter

    output = _make_coaching_output(
        issues=[
            Issue(
                rep_number=1,
                joint="knee",
                description="For injury prevention, keep knees tracking.",
                severity="Medium",
            ),
        ],
    )
    result = SafetyFilter.apply(output)

    assert "injury prevention" not in result.output.issues[0].description.lower()
    assert "movement quality improvement" in result.output.issues[0].description.lower()


def test_replace_in_correction_plan_items() -> None:
    from app.services.safety_filter import SafetyFilter

    output = _make_coaching_output(
        correction_plan=["Address the injury risk by widening stance."],
    )
    result = SafetyFilter.apply(output)

    assert "injury risk" not in result.output.correction_plan[0].lower()


def test_replace_in_recommended_cues() -> None:
    from app.services.safety_filter import SafetyFilter

    output = _make_coaching_output(
        recommended_cues=["Focus on injury prevention during descent."],
    )
    result = SafetyFilter.apply(output)

    assert "injury prevention" not in result.output.recommended_cues[0].lower()


def test_replace_in_strengths() -> None:
    from app.services.safety_filter import SafetyFilter

    output = _make_coaching_output(
        strengths=["Good injury prevention technique."],
    )
    result = SafetyFilter.apply(output)

    assert "injury prevention" not in result.output.strengths[0].lower()


def test_disclaimer_not_scanned_for_prohibited_phrases() -> None:
    """The mandatory disclaimer field must never be modified."""
    from app.services.safety_filter import SafetyFilter

    output = _make_coaching_output()
    result = SafetyFilter.apply(output)

    assert result.output.disclaimer == MANDATORY_DISCLAIMER


def test_phrases_replaced_count_accurate() -> None:
    from app.services.safety_filter import SafetyFilter

    output = _make_coaching_output(
        summary="The injury risk is high. Watch for injury prevention.",
        correction_plan=["Reduce injury risk in setup."],
    )
    result = SafetyFilter.apply(output)

    assert result.phrases_replaced == 3


# ---------------------------------------------------------------------------
# Medical screening disclaimer injection tests
# ---------------------------------------------------------------------------


def test_medical_screening_keyword_injects_disclaimer() -> None:
    from app.services.safety_filter import SAFETY_SCREENING_DISCLAIMER, SafetyFilter

    output = _make_coaching_output(
        safety_warnings=["Recommend preparticipation health screening before heavy loading."],
    )
    result = SafetyFilter.apply(output)

    assert result.injected_disclaimer is True
    assert SAFETY_SCREENING_DISCLAIMER in result.output.safety_warnings


def test_no_medical_keyword_no_disclaimer_injection() -> None:
    from app.services.safety_filter import SafetyFilter

    output = _make_coaching_output(
        safety_warnings=["Watch knee tracking during descent."],
    )
    result = SafetyFilter.apply(output)

    assert result.injected_disclaimer is False


def test_disclaimer_not_duplicated_when_already_present() -> None:
    from app.services.safety_filter import SAFETY_SCREENING_DISCLAIMER, SafetyFilter

    output = _make_coaching_output(
        safety_warnings=[
            "Recommend medical clearance before heavy training.",
            SAFETY_SCREENING_DISCLAIMER,
        ],
    )
    result = SafetyFilter.apply(output)

    count = sum(1 for w in result.output.safety_warnings if w == SAFETY_SCREENING_DISCLAIMER)
    assert count == 1


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------


def test_returns_copy_not_mutation() -> None:
    from app.services.safety_filter import SafetyFilter

    output = _make_coaching_output(summary="Check injury risk carefully.")
    original_summary = output.summary
    result = SafetyFilter.apply(output)

    assert output.summary == original_summary  # original unchanged
    assert result.output.summary != original_summary  # result modified


def test_never_raises_on_malformed_input() -> None:
    """SafetyFilter.apply must never raise."""
    from app.services.safety_filter import SafetyFilter

    output = _make_coaching_output()
    # Shouldn't raise even with weird inputs
    result = SafetyFilter.apply(output)
    assert result.output is not None
