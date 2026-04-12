"""SafetyFilter — safety language post-filter (P2-018).

Requirements: FR-AICP-14

Post-generation enforcement: replaces prohibited phrases ("injury risk",
"injury prevention") and injects medical screening disclaimer when
health-screening keywords are detected. Never raises.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.schemas.coaching import CoachingOutput

logger = logging.getLogger(__name__)

# Prohibited phrases and their approved replacements (case-insensitive matching)
_PROHIBITED_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"injury\s+risk", re.IGNORECASE), "movement quality concern"),
    (re.compile(r"injury\s+prevention", re.IGNORECASE), "movement quality improvement"),
]

MEDICAL_SCREENING_KEYWORDS: frozenset[str] = frozenset(
    {
        "preparticipation",
        "health screening",
        "medical clearance",
        "physician clearance",
        "cardiac screening",
        "par-q",
    }
)

SAFETY_SCREENING_DISCLAIMER = (
    "If you have any pre-existing health conditions or have not recently "
    "completed a health screening, consult a qualified health professional "
    "before undertaking this training programme."
)


@dataclass
class SafetyFilterResult:
    """Result of the safety language post-filter."""

    output: CoachingOutput
    injected_disclaimer: bool = False
    phrases_replaced: int = 0


def _replace_prohibited(text: str) -> tuple[str, int]:
    """Replace prohibited phrases in text, return (cleaned, count)."""
    count = 0
    for pattern, replacement in _PROHIBITED_REPLACEMENTS:
        text, n = pattern.subn(replacement, text)
        count += n
    return text, count


class SafetyFilter:
    """Post-generation safety enforcement for coaching output."""

    @staticmethod
    def apply(output: CoachingOutput) -> SafetyFilterResult:
        try:
            return SafetyFilter._apply_impl(output)
        except Exception:
            logger.warning(
                "SafetyFilter: unexpected error — returning input unchanged",
                exc_info=True,
            )
            return SafetyFilterResult(output=output)

    @staticmethod
    def _apply_impl(output: CoachingOutput) -> SafetyFilterResult:
        total_replaced = 0
        updates: dict = {}

        # Replace prohibited phrases in summary
        cleaned, n = _replace_prohibited(output.summary)
        if n:
            updates["summary"] = cleaned
            total_replaced += n

        # Replace in strengths
        new_strengths = []
        strengths_changed = False
        for s in output.strengths:
            cleaned, n = _replace_prohibited(s)
            new_strengths.append(cleaned)
            if n:
                strengths_changed = True
                total_replaced += n
        if strengths_changed:
            updates["strengths"] = new_strengths

        # Replace in issues
        new_issues = []
        issues_changed = False
        for issue in output.issues:
            cleaned, n = _replace_prohibited(issue.description)
            if n:
                new_issues.append(issue.model_copy(update={"description": cleaned}))
                issues_changed = True
                total_replaced += n
            else:
                new_issues.append(issue)
        if issues_changed:
            updates["issues"] = new_issues

        # Replace in correction_plan
        new_plan = []
        plan_changed = False
        for item in output.correction_plan:
            cleaned, n = _replace_prohibited(item)
            new_plan.append(cleaned)
            if n:
                plan_changed = True
                total_replaced += n
        if plan_changed:
            updates["correction_plan"] = new_plan

        # Replace in recommended_cues
        new_cues = []
        cues_changed = False
        for cue in output.recommended_cues:
            cleaned, n = _replace_prohibited(cue)
            new_cues.append(cleaned)
            if n:
                cues_changed = True
                total_replaced += n
        if cues_changed:
            updates["recommended_cues"] = new_cues

        # Replace in safety_warnings (but also check for medical keywords)
        new_warnings = []
        warnings_changed = False
        for w in output.safety_warnings:
            cleaned, n = _replace_prohibited(w)
            new_warnings.append(cleaned)
            if n:
                warnings_changed = True
                total_replaced += n
        if warnings_changed:
            updates["safety_warnings"] = new_warnings

        # Medical screening keyword detection in safety_warnings
        injected_disclaimer = False
        warnings_to_check = updates.get("safety_warnings", list(output.safety_warnings))
        all_warnings_text = " ".join(warnings_to_check).lower()

        if any(kw in all_warnings_text for kw in MEDICAL_SCREENING_KEYWORDS):
            if SAFETY_SCREENING_DISCLAIMER not in warnings_to_check:
                warnings_to_check = list(warnings_to_check) + [SAFETY_SCREENING_DISCLAIMER]
                updates["safety_warnings"] = warnings_to_check
                injected_disclaimer = True

        # Build result
        if updates:
            result_output = output.model_copy(update=updates)
        else:
            result_output = output

        return SafetyFilterResult(
            output=result_output,
            injected_disclaimer=injected_disclaimer,
            phrases_replaced=total_replaced,
        )
