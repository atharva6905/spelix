"""Tests for the research papers seed corpus data (P2-007).

Validates the seed papers meet FR-RAGK-02 and FR-RAGK-03 requirements:
- At least 10 papers per exercise (squat, bench, deadlift)
- All papers have valid quality tiers and metadata
- Quality tier distribution includes multiple levels
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR.parent))

from app.utils.doi import DoiValidationError, normalize_doi  # noqa: E402
from scripts.seed_research_papers import (  # noqa: E402
    _INSERT_SQL,
    SEED_PAPERS,
    SeedPaper,
    build_rag_document_row,
    validate_seed_dois,
)

VALID_QUALITY_TIERS = {
    "L1_systematic_review",
    "L2_rct",
    "L3_observational",
    "L4_guideline",
}
VALID_DOCUMENT_TYPES = {
    "research_paper",
    "textbook",
    "clinical_guideline",
    "expert_annotation",
    "other",
}
VALID_EXERCISES = {"squat", "bench", "deadlift"}


class TestSeedPapersRequirements:
    """FR-RAGK-02: ≥10 papers per exercise."""

    def _count_by_exercise(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in SEED_PAPERS:
            for tag in p.exercise_tags:
                counts[tag] = counts.get(tag, 0) + 1
        return counts

    def test_total_at_least_30(self) -> None:
        assert len(SEED_PAPERS) >= 30

    @pytest.mark.parametrize("exercise", ["squat", "bench", "deadlift"])
    def test_at_least_10_per_exercise(self, exercise: str) -> None:
        counts = self._count_by_exercise()
        assert counts.get(exercise, 0) >= 10, f"{exercise}: only {counts.get(exercise, 0)} papers"

    def test_all_exercise_tags_valid(self) -> None:
        for i, p in enumerate(SEED_PAPERS):
            for tag in p.exercise_tags:
                assert tag in VALID_EXERCISES, f"Paper {i}: invalid exercise tag '{tag}'"

    def test_all_quality_tiers_valid(self) -> None:
        for i, p in enumerate(SEED_PAPERS):
            assert p.quality_tier in VALID_QUALITY_TIERS, f"Paper {i}: invalid tier '{p.quality_tier}'"

    def test_all_document_types_valid(self) -> None:
        for i, p in enumerate(SEED_PAPERS):
            assert p.document_type in VALID_DOCUMENT_TYPES, f"Paper {i}: invalid type '{p.document_type}'"

    def test_all_papers_have_title(self) -> None:
        for i, p in enumerate(SEED_PAPERS):
            assert len(p.title) >= 10, f"Paper {i}: title too short"

    def test_all_papers_have_authors(self) -> None:
        for i, p in enumerate(SEED_PAPERS):
            assert len(p.authors) >= 1, f"Paper {i}: no authors"

    def test_all_papers_have_year(self) -> None:
        for i, p in enumerate(SEED_PAPERS):
            assert p.year is not None and 1980 <= p.year <= 2026, f"Paper {i}: invalid year {p.year}"

    def test_all_papers_have_substantial_text(self) -> None:
        for i, p in enumerate(SEED_PAPERS):
            assert len(p.text) >= 200, f"Paper {i}: text too short ({len(p.text)} chars)"

    def test_quality_tier_diversity(self) -> None:
        """Ensure we have papers from at least 3 quality tier levels."""
        tiers = {p.quality_tier for p in SEED_PAPERS}
        assert len(tiers) >= 3, f"Only {len(tiers)} quality tiers represented: {tiers}"

    def test_no_injury_risk_language(self) -> None:
        """Spelix language rule."""
        for i, p in enumerate(SEED_PAPERS):
            lower = p.text.lower()
            assert "injury risk" not in lower, f"Paper {i}: forbidden 'injury risk'"
            assert "injury prevention" not in lower, f"Paper {i}: forbidden 'injury prevention'"


def _make_paper(doi: str | None) -> SeedPaper:
    return SeedPaper(
        title="Test paper title long enough",
        authors=["Author A"],
        year=2020,
        doi=doi,
        quality_tier="L2_rct",
        exercise_tags=["squat"],
        document_type="research_paper",
        text="x" * 250,
    )


class TestSeedDoiColumn:
    """Issue #230 / FR-RAGK-05: seed rows must populate the doi column."""

    def test_insert_sql_includes_doi_column(self) -> None:
        assert " doi," in _INSERT_SQL
        assert ":doi" in _INSERT_SQL

    def test_row_includes_normalized_doi(self) -> None:
        paper = _make_paper("https://doi.org/10.1519/JSC.0b013e3182a1fbd2")
        from datetime import datetime, timezone

        row = build_rag_document_row(paper, str(__import__("uuid").uuid4()), datetime.now(timezone.utc))
        assert row["doi"] == "10.1519/jsc.0b013e3182a1fbd2"

    def test_row_doi_null_when_paper_has_no_doi(self) -> None:
        paper = _make_paper(None)
        from datetime import datetime, timezone

        row = build_rag_document_row(paper, str(__import__("uuid").uuid4()), datetime.now(timezone.utc))
        assert row["doi"] is None

    def test_validate_seed_dois_raises_on_malformed_with_entry_name(self) -> None:
        bad = _make_paper("not-a-doi")
        with pytest.raises(DoiValidationError, match="Test paper title"):
            validate_seed_dois([bad])

    def test_validate_seed_dois_allows_none_doi(self) -> None:
        validate_seed_dois([_make_paper(None)])

    def test_all_hardcoded_seed_dois_normalize(self) -> None:
        validate_seed_dois(SEED_PAPERS)
        for p in SEED_PAPERS:
            if p.doi is not None:
                assert normalize_doi(p.doi)
