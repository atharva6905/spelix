"""Tests for ValidateOutputTool — citation cross-reference validation (P2-017).

Requirements: FR-AICP-10

TDD protocol: tests written before implementation.
"""

from __future__ import annotations


from app.schemas.coaching import CoachingOutput, Issue
from app.schemas.rag import CitationBlock

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
        "issues": [
            Issue(
                rep_number=1,
                joint="Left knee",
                description="Slight valgus during descent [1].",
                severity="Medium",
            ),
        ],
        "correction_plan": ["Drive knees out [1]."],
        "disclaimer": MANDATORY_DISCLAIMER,
        "raw_prompt_tokens": 400,
        "raw_completion_tokens": 200,
    }
    data.update(overrides)
    return CoachingOutput(**data)


def _make_citation_blocks(n: int = 3) -> list[CitationBlock]:
    return [
        CitationBlock(
            index=i + 1,
            title=f"Paper {i + 1}",
            authors=[f"Author {i + 1}"],
            year=2022 + i,
            doi=f"10.1234/paper{i + 1}",
            chunk_text_excerpt=f"Excerpt from paper {i + 1}.",
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# extract_citation_indices tests
# ---------------------------------------------------------------------------


def test_extract_citation_indices_single_marker() -> None:
    from app.services.validate_output import extract_citation_indices

    assert extract_citation_indices("[1]") == [1]


def test_extract_citation_indices_multiple_unique() -> None:
    from app.services.validate_output import extract_citation_indices

    result = extract_citation_indices("[1] and [2] again [1]")
    assert result == [1, 2]


def test_extract_citation_indices_empty_string() -> None:
    from app.services.validate_output import extract_citation_indices

    assert extract_citation_indices("") == []


def test_extract_citation_indices_no_markers() -> None:
    from app.services.validate_output import extract_citation_indices

    assert extract_citation_indices("no citations here") == []


def test_extract_citation_indices_ignores_non_digit_brackets() -> None:
    """[High] severity labels must not be matched as citation indices."""
    from app.services.validate_output import extract_citation_indices

    assert extract_citation_indices("[High] severity issue") == []


# ---------------------------------------------------------------------------
# ValidateOutputTool.validate tests
# ---------------------------------------------------------------------------


def test_validate_populates_citation_indices_on_issues() -> None:
    from app.services.validate_output import ValidateOutputTool

    output = _make_coaching_output(
        issues=[
            Issue(
                rep_number=1,
                joint="Left knee",
                description="Slight valgus during descent [1] and [2].",
                severity="Medium",
            ),
        ],
    )
    blocks = _make_citation_blocks(3)
    result = ValidateOutputTool.validate(output, blocks)

    assert result.output.issues[0].citation_indices == [1, 2]


def test_validate_no_invalid_citations_when_all_valid() -> None:
    from app.services.validate_output import ValidateOutputTool

    output = _make_coaching_output(
        summary="Good form [1] with minor issues [2].",
        issues=[
            Issue(
                rep_number=1,
                joint="hip",
                description="Depth issue [1].",
                severity="Medium",
            ),
        ],
    )
    blocks = _make_citation_blocks(2)
    result = ValidateOutputTool.validate(output, blocks)

    assert result.has_invalid_citations is False
    assert result.invalid_indices == []


def test_validate_flags_invalid_when_index_too_high() -> None:
    from app.services.validate_output import ValidateOutputTool

    output = _make_coaching_output(
        summary="Good form [3] cited.",
    )
    blocks = _make_citation_blocks(2)  # only [1] and [2] valid
    result = ValidateOutputTool.validate(output, blocks)

    assert result.has_invalid_citations is True
    assert 3 in result.invalid_indices


def test_validate_flags_invalid_when_index_zero() -> None:
    from app.services.validate_output import ValidateOutputTool

    output = _make_coaching_output(
        summary="Cited [0] which is invalid.",
    )
    blocks = _make_citation_blocks(2)
    result = ValidateOutputTool.validate(output, blocks)

    assert result.has_invalid_citations is True
    assert 0 in result.invalid_indices


def test_validate_returns_copy_not_mutation() -> None:
    from app.services.validate_output import ValidateOutputTool

    output = _make_coaching_output()
    blocks = _make_citation_blocks(2)
    result = ValidateOutputTool.validate(output, blocks)

    # Original issues should have empty citation_indices
    assert output.issues[0].citation_indices == []
    # Result output should have populated citation_indices
    assert result.output.issues[0].citation_indices == [1]


def test_validate_empty_citation_blocks() -> None:
    from app.services.validate_output import ValidateOutputTool

    output = _make_coaching_output(
        summary="No RAG contexts available.",
        issues=[
            Issue(
                rep_number=1,
                joint="hip",
                description="No citations here.",
                severity="Low",
            ),
        ],
        correction_plan=["No citations."],
    )
    result = ValidateOutputTool.validate(output, [])

    assert result.has_invalid_citations is False
    assert result.output.issues[0].citation_indices == []


def test_validate_never_raises_on_malformed_output() -> None:
    """ValidateOutputTool must never raise — return input unchanged on error."""
    from app.services.validate_output import ValidateOutputTool

    output = _make_coaching_output()
    # Pass None as citation_blocks to trigger an error path
    result = ValidateOutputTool.validate(output, None)  # type: ignore[arg-type]

    assert result.output == output
    assert result.has_invalid_citations is False


def test_validate_tracks_uncited_issues() -> None:
    from app.services.validate_output import ValidateOutputTool

    output = _make_coaching_output(
        issues=[
            Issue(
                rep_number=1,
                joint="hip",
                description="No citation reference at all.",
                severity="High",
            ),
            Issue(
                rep_number=2,
                joint="knee",
                description="Has a reference [1].",
                severity="Medium",
            ),
        ],
    )
    blocks = _make_citation_blocks(2)
    result = ValidateOutputTool.validate(output, blocks)

    # Rep 1 has no citations, so it should be in uncited_issues
    assert 1 in result.uncited_issues
    assert 2 not in result.uncited_issues


def test_validator_scans_strengths_for_citation_markers() -> None:
    """strengths[] items with [N] markers must be scanned — not just summary / issues / correction_plan.

    The test puts an out-of-range [5] marker ONLY in strengths (all other fields
    are citation-free). With only 2 citation blocks, [5] is invalid. If the
    validator does NOT scan strengths it will silently miss the bad index and
    return has_invalid_citations=False — which would be the wrong (failing) answer.
    """
    from app.services.validate_output import ValidateOutputTool

    # Only strengths contains a [5] marker — all other text fields are citation-free.
    output = _make_coaching_output(
        summary="Good squat session overall.",
        strengths=["Consistent bracing throughout [5].", "Good bar path"],
        issues=[
            Issue(
                rep_number=1,
                joint="knee",
                description="No citation here.",
                severity="Low",
            ),
        ],
        correction_plan=["No citation here either."],
    )
    # Only 2 citation blocks — [5] is out of range.
    blocks = _make_citation_blocks(2)
    result = ValidateOutputTool.validate(output, blocks)

    # The [5] in strengths is invalid — the validator must catch it.
    assert result.has_invalid_citations is True
    assert 5 in result.invalid_indices


def test_validator_scans_recommended_cues_for_citation_markers() -> None:
    """recommended_cues[] items with [N] markers must be scanned.

    An out-of-range [9] marker ONLY in recommended_cues must be caught.
    """
    from app.services.validate_output import ValidateOutputTool

    output = _make_coaching_output(
        summary="Good squat session.",
        issues=[
            Issue(rep_number=1, joint="knee", description="No citation.", severity="Low"),
        ],
        correction_plan=["No citation here."],
        recommended_cues=["Focus on knee drive [9]."],
    )
    # Only 2 citation blocks — [9] is out of range.
    blocks = _make_citation_blocks(2)
    result = ValidateOutputTool.validate(output, blocks)

    assert result.has_invalid_citations is True
    assert 9 in result.invalid_indices
