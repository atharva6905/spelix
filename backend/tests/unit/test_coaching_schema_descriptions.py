"""Ensure CoachingOutput / Issue field descriptions instruct Claude to embed
[N] citation markers inline. instructor passes these descriptions to Claude
via the JSON Schema. Tasks 2+3 together provide two enforcement points for
the same requirement — system prompt level AND schema level."""

from app.schemas.coaching import CoachingOutput, Issue


def test_schema_field_descriptions_mention_citation_markers():
    fields_to_check = {
        "CoachingOutput.summary": CoachingOutput.model_fields["summary"].description or "",
        "CoachingOutput.strengths": CoachingOutput.model_fields["strengths"].description or "",
        "CoachingOutput.correction_plan": CoachingOutput.model_fields["correction_plan"].description or "",
        "Issue.description": Issue.model_fields["description"].description or "",
    }
    missing = [name for name, desc in fields_to_check.items() if "[N]" not in desc and "[1]" not in desc]
    assert not missing, (
        f"These field descriptions must mention [N] or [1] marker syntax, but don't: {missing}"
    )
