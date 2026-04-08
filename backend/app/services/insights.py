"""Insights service — exercise-specific and global analytics (B-031).

Requirements: FR-HIST-02, FR-HIST-03

Computes:
- Per-exercise: 7-session rolling avg confidence, rep count trend,
  most common QG warning, personal best confidence
- Global: most common warning (30 days), highest rep count variance exercise
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis


class InsightsService:
    """Compute history insights from completed analyses."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def exercise_insights(
        self,
        user_id: UUID,
        exercise_type: str,
        exercise_variant: str,
    ) -> dict[str, Any]:
        """Compute per-exercise insights for a user.

        Returns
        -------
        dict with keys:
            rolling_avg_confidence: list[float]  — last 7 sessions
            rep_count_trend: list[int]            — last 7 sessions
            most_common_warning: str | None
            personal_best_confidence: float
        """
        stmt = (
            select(Analysis)
            .where(
                and_(
                    Analysis.user_id == user_id,
                    Analysis.exercise_type == exercise_type,
                    Analysis.exercise_variant == exercise_variant,
                    Analysis.status == "completed",
                )
            )
            .order_by(desc(Analysis.created_at))
            .limit(7)
        )
        result = await self._db.execute(stmt)
        analyses = list(result.scalars().all())

        # Reverse to chronological order for trend display
        analyses.reverse()

        # Rolling avg confidence (last 7 sessions)
        confidences = [
            a.confidence_score for a in analyses if a.confidence_score is not None
        ]
        rolling_avg = _rolling_average(confidences, window=7)

        # Rep count trend from summary_json
        rep_counts = []
        for a in analyses:
            if a.summary_json and "rep_count" in a.summary_json:
                rep_counts.append(a.summary_json["rep_count"])
            else:
                rep_counts.append(0)

        # Most common QG warning
        warnings: list[str] = []
        for a in analyses:
            if a.quality_gate_result and "checks" in a.quality_gate_result:
                for check in a.quality_gate_result["checks"]:
                    if not check.get("passed", True) and check.get("user_message"):
                        warnings.append(check["user_message"])

        warning_counter = Counter(warnings)
        most_common = warning_counter.most_common(1)
        most_common_warning = most_common[0][0] if most_common else None

        # Personal best confidence (all time for this exercise)
        best_stmt = (
            select(func.max(Analysis.confidence_score))
            .where(
                and_(
                    Analysis.user_id == user_id,
                    Analysis.exercise_type == exercise_type,
                    Analysis.exercise_variant == exercise_variant,
                    Analysis.status == "completed",
                    Analysis.confidence_score.isnot(None),
                )
            )
        )
        best_result = await self._db.execute(best_stmt)
        personal_best = best_result.scalar() or 0.0

        return {
            "rolling_avg_confidence": rolling_avg,
            "rep_count_trend": rep_counts,
            "most_common_warning": most_common_warning,
            "personal_best_confidence": float(personal_best),
        }

    async def global_insights(self, user_id: UUID) -> dict[str, Any]:
        """Compute global insights across all exercises for a user.

        Returns
        -------
        dict with keys:
            most_common_warning: str | None     — last 30 days
            highest_variance_exercise: str | None
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        stmt = (
            select(Analysis)
            .where(
                and_(
                    Analysis.user_id == user_id,
                    Analysis.status == "completed",
                    Analysis.created_at >= cutoff,
                )
            )
            .order_by(desc(Analysis.created_at))
        )
        result = await self._db.execute(stmt)
        analyses = list(result.scalars().all())

        # Most common warning (30 days)
        warnings: list[str] = []
        for a in analyses:
            if a.quality_gate_result and "checks" in a.quality_gate_result:
                for check in a.quality_gate_result["checks"]:
                    if not check.get("passed", True) and check.get("user_message"):
                        warnings.append(check["user_message"])

        warning_counter = Counter(warnings)
        most_common = warning_counter.most_common(1)
        most_common_warning = most_common[0][0] if most_common else None

        # Highest rep count variance exercise
        exercise_reps: dict[str, list[int]] = {}
        for a in analyses:
            rep_count = 0
            if a.summary_json and "rep_count" in a.summary_json:
                rep_count = a.summary_json["rep_count"]
            exercise_reps.setdefault(a.exercise_type, []).append(rep_count)

        highest_variance_exercise = None
        max_variance = 0.0
        for ex, counts in exercise_reps.items():
            if len(counts) >= 2:
                import numpy as np

                var = float(np.var(counts))
                if var > max_variance:
                    max_variance = var
                    highest_variance_exercise = ex

        return {
            "most_common_warning": most_common_warning,
            "highest_variance_exercise": highest_variance_exercise,
        }


def _rolling_average(values: list[float], window: int = 7) -> list[float]:
    """Compute a simple rolling average over the last *window* values."""
    if not values:
        return []
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        segment = values[start : i + 1]
        result.append(round(sum(segment) / len(segment), 4))
    return result
