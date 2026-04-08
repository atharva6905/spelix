"""Export service — CSV generation for analysis data.

Requirements: FR-XPRT-04, NFR-SECU-07 (GDPR Article 20)
"""

import csv
import io
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.repositories.analysis import AnalysisRepository


# Ordered base columns that always appear in the CSV output
_ANALYSIS_COLUMNS = [
    "exercise_type",
    "exercise_variant",
    "created_at",
    "confidence_score",
]

_REP_COLUMNS = [
    "rep_index",
    "start_frame",
    "end_frame",
    "rep_confidence_score",
]


class ExportService:
    def __init__(self, repo: AnalysisRepository) -> None:
        self._repo = repo

    async def generate_csv(self, analysis_id: UUID, user_id: UUID) -> str:
        """Generate CSV content for an analysis.

        Validates that the analysis exists and belongs to *user_id*.  Returns
        a CSV string with one header row and one data row per rep.  If there
        are no reps the CSV contains only the header row.

        All keys found in any rep's ``metrics_json`` are unioned into the
        column set and appended after the fixed rep columns.  Rows that are
        missing a given metric key receive an empty string for that column.

        Raises:
            HTTPException 404 — analysis does not exist.
            HTTPException 403 — analysis exists but belongs to a different user.
        """
        analysis = await self._repo.get_by_id(analysis_id)
        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ANALYSIS_NOT_FOUND",
                        "message": "Analysis not found.",
                        "detail": None,
                    }
                },
            )

        if analysis.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not have access to this analysis.",
                        "detail": None,
                    }
                },
            )

        # Collect all metrics_json keys across every rep to build a stable
        # column order.  Insertion order is preserved (Python 3.7+ dict).
        metric_keys: list[str] = _collect_metric_keys(analysis.rep_metrics)

        fieldnames = _ANALYSIS_COLUMNS + _REP_COLUMNS + metric_keys

        # Analysis-level values repeated on every row
        analysis_values: dict[str, Any] = {
            "exercise_type": analysis.exercise_type,
            "exercise_variant": analysis.exercise_variant,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else "",
            "confidence_score": analysis.confidence_score if analysis.confidence_score is not None else "",
        }

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for rep in analysis.rep_metrics:
            metrics: dict[str, Any] = rep.metrics_json or {}
            row: dict[str, Any] = {
                **analysis_values,
                "rep_index": rep.rep_index,
                "start_frame": rep.start_frame,
                "end_frame": rep.end_frame,
                "rep_confidence_score": rep.confidence_score if rep.confidence_score is not None else "",
            }
            # Flatten metrics_json — missing keys become empty string via DictWriter restval
            for key in metric_keys:
                row[key] = metrics.get(key, "")

            writer.writerow(row)

        return buf.getvalue()


def _collect_metric_keys(rep_metrics) -> list[str]:
    """Return an ordered, deduplicated list of all keys found in metrics_json
    across all reps.  The order is determined by first-seen insertion order."""
    seen: dict[str, None] = {}
    for rep in rep_metrics:
        if rep.metrics_json:
            for key in rep.metrics_json:
                seen[key] = None
    return list(seen.keys())
