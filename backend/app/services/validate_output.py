"""ValidateOutputTool — citation cross-reference validation (P2-017).

Requirements: FR-AICP-10

Scans CoachingOutput for [N] citation markers, cross-references against
available CitationBlocks, populates Issue.citation_indices, and flags
invalid references. Never raises.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.schemas.coaching import CoachingOutput, Issue
from app.schemas.rag import CitationBlock

logger = logging.getLogger(__name__)

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def extract_citation_indices(text: str) -> list[int]:
    """Return sorted unique 1-based citation indices found in text."""
    return sorted(set(int(m) for m in _CITATION_PATTERN.findall(text)))


@dataclass
class ValidationResult:
    """Result of citation cross-reference validation."""

    output: CoachingOutput
    has_invalid_citations: bool = False
    invalid_indices: list[int] = field(default_factory=list)
    uncited_issues: list[int] = field(default_factory=list)


class ValidateOutputTool:
    """Validates that coaching output citations reference real citation blocks."""

    @staticmethod
    def validate(
        output: CoachingOutput,
        citation_blocks: list[CitationBlock],
    ) -> ValidationResult:
        try:
            return ValidateOutputTool._validate_impl(output, citation_blocks)
        except Exception:
            logger.warning(
                "ValidateOutputTool: unexpected error — returning input unchanged",
                exc_info=True,
            )
            return ValidationResult(output=output)

    @staticmethod
    def _validate_impl(
        output: CoachingOutput,
        citation_blocks: list[CitationBlock],
    ) -> ValidationResult:
        valid_indices = set(range(1, len(citation_blocks) + 1))
        all_found: set[int] = set()

        # Scan summary
        all_found.update(extract_citation_indices(output.summary))

        # Scan strengths items
        for item in output.strengths:
            all_found.update(extract_citation_indices(item))

        # Scan correction_plan items
        for item in output.correction_plan:
            all_found.update(extract_citation_indices(item))

        # Scan recommended_cues items
        for cue in output.recommended_cues:
            all_found.update(extract_citation_indices(cue))

        # Scan issues and populate citation_indices per issue
        annotated_issues: list[Issue] = []
        uncited_issues: list[int] = []

        for issue in output.issues:
            indices = extract_citation_indices(issue.description)
            all_found.update(indices)
            annotated_issue = issue.model_copy(update={"citation_indices": indices})
            annotated_issues.append(annotated_issue)

            # Track uncited issues (only when citation blocks exist)
            if citation_blocks and not indices:
                uncited_issues.append(issue.rep_number)

        # Build annotated output copy
        annotated_output = output.model_copy(update={"issues": annotated_issues})

        # Check for invalid indices
        invalid = sorted(all_found - valid_indices)
        # Index 0 is always invalid (1-based system)
        if 0 in all_found:
            invalid = sorted(set(invalid) | {0})

        return ValidationResult(
            output=annotated_output,
            has_invalid_citations=len(invalid) > 0,
            invalid_indices=invalid,
            uncited_issues=uncited_issues,
        )
