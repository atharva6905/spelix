"""SummaryService — compute and store summary_json for a completed analysis.

Requirements: FR-HIST-04 (B-030)

After coaching completes and the analysis reaches `completed` status, this
service computes summary_json and writes it to the analyses table.

summary_json fields:
    confidence_score        float    session confidence
    confidence_label        str      "High" / "Moderate" / "Low" / "Very Low"
    rep_count               int      total reps detected
    exercise_type           str
    exercise_variant        str
    quality_gate_warnings   list[str]  user_message from non-passing checks
    top_metric_keys         list[str]  union of all metrics_json keys across reps
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.cv.confidence import confidence_label
from app.repositories.analysis import AnalysisRepository
from app.repositories.rep_metric import RepMetricRepository

logger = logging.getLogger(__name__)


def _extract_quality_gate_warnings(quality_gate_result: dict[str, Any] | None) -> list[str]:
    """Return user_message from every check where passed=False.

    quality_gate_result JSONB structure (from the quality gate pipeline):
    {
        "passed": bool,
        "checks": [
            {"name": str, "passed": bool, "user_message": str, ...},
            ...
        ]
    }
    """
    if not quality_gate_result:
        return []

    checks = quality_gate_result.get("checks", [])
    warnings: list[str] = []
    for check in checks:
        if not check.get("passed", True):
            msg = check.get("user_message", "")
            if msg:
                warnings.append(msg)
    return warnings


def _collect_top_metric_keys(rep_metrics_json_list: list[dict[str, Any] | None]) -> list[str]:
    """Return sorted union of all keys found across all rep metrics_json dicts."""
    keys: set[str] = set()
    for metrics_json in rep_metrics_json_list:
        if metrics_json:
            keys.update(metrics_json.keys())
    return sorted(keys)


class SummaryService:
    """Compute and persist summary_json for a completed analysis.

    Parameters
    ----------
    repo:
        AnalysisRepository for fetching and updating the analysis row.
    rep_metric_repo:
        RepMetricRepository for fetching rep metrics.
    """

    def __init__(
        self,
        repo: AnalysisRepository,
        rep_metric_repo: RepMetricRepository,
    ) -> None:
        self._repo = repo
        self._rep_metric_repo = rep_metric_repo

    async def compute_and_store(self, analysis_id: UUID) -> dict[str, Any]:
        """Compute summary_json from analysis + rep_metrics and write to DB.

        Parameters
        ----------
        analysis_id:
            UUID of the analysis to summarise.

        Returns
        -------
        dict
            The computed summary_json dict (also stored on the analysis row).

        Raises
        ------
        ValueError
            If the analysis does not exist.
        """
        # 1. Fetch analysis by ID
        analysis = await self._repo.get_by_id(analysis_id)
        if analysis is None:
            raise ValueError(f"Analysis {analysis_id} not found")

        # 2. Fetch rep_metrics for analysis
        rep_metrics = await self._rep_metric_repo.get_by_analysis(analysis_id)

        # 3. Build summary dict
        confidence_score: float = analysis.confidence_score or 0.0
        label = confidence_label(confidence_score)

        warnings = _extract_quality_gate_warnings(analysis.quality_gate_result)

        metric_keys = _collect_top_metric_keys(
            [rm.metrics_json for rm in rep_metrics]
        )

        summary: dict[str, Any] = {
            "confidence_score": confidence_score,
            "confidence_label": label,
            "rep_count": len(rep_metrics),
            "exercise_type": analysis.exercise_type,
            "exercise_variant": analysis.exercise_variant,
            "quality_gate_warnings": warnings,
            "top_metric_keys": metric_keys,
        }

        # 4. Write to analysis.summary_json
        analysis.summary_json = summary
        await self._repo.update(analysis)

        logger.info(
            "summary_json computed for analysis %s: %d reps, confidence=%s (%s)",
            analysis_id,
            summary["rep_count"],
            round(confidence_score, 3),
            label,
        )

        # 5. Return the dict
        return summary
