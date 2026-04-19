"""extract_insights — Haiku-extractive distillation node.

Reads a completed CoachingOutput and emits falsifiable, reusable
coaching candidates tagged with exercise, phase, entry_type, and
trigger_tags. Never raises — any LLM failure returns an empty list.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from app.constants import HAIKU_MODEL as _HAIKU_MODEL
from app.distillation.state import CandidateInsight, DistillationState
from app.schemas.coaching import CoachingOutput

logger = logging.getLogger(__name__)

_MAX_TOKENS = 1024


class ExtractedInsights(BaseModel):
    """instructor response model for the extraction call."""

    candidates: list[CandidateInsight]


def _build_extraction_prompt(coaching_output: CoachingOutput, exercise_type: str) -> str:
    lines: list[str] = [
        "You are a coaching insight extractor. From the coaching feedback "
        "below, extract atomic reusable coaching insights suitable for a "
        "knowledge base.",
        "",
        f"Exercise: {exercise_type}",
        "",
        "Rules:",
        "- Only include insights you could verify against biomechanics "
        "literature. Skip subjective observations.",
        "- Each insight must be 5-25 words and phrase-complete.",
        "- Prefer verbatim or near-verbatim coaching language from the "
        "feedback — do NOT invent new cues.",
        "- Tag each insight with: exercise (squat|bench|deadlift), phase "
        "(setup|descent|bottom|ascent|lockout|general|null), entry_type "
        "(cue|correction|principle|drill|compensation), trigger_tags (e.g. knee_cave, "
        "forward_lean).",
        "- When the insight describes a multi-step causal chain where one weakness "
        "drives a secondary error (e.g. 'knee valgus compensates for weak hip "
        "abduction'), tag entry_type=\"compensation\". Biomechanics reviewers "
        "will gate these separately (FR-ADMN-12).",
        "- If there is nothing worth distilling, return an empty list.",
        "",
        f"Coaching summary: {coaching_output.summary}",
        "",
        "Issues identified:",
    ]
    for issue in coaching_output.issues:
        lines.append(
            f"- Rep {issue.rep_number} ({issue.joint}, {issue.severity}): "
            f"{issue.description}"
        )
    lines.append("")
    lines.append("Correction plan:")
    for cue in coaching_output.correction_plan:
        lines.append(f"- {cue}")
    if coaching_output.recommended_cues:
        lines.append("")
        lines.append("Recommended cues:")
        for cue in coaching_output.recommended_cues:
            lines.append(f"- {cue}")
    return "\n".join(lines)


async def extract_insights(
    state: DistillationState,
    *,
    anthropic_client: Any,
    instructor_client: Any,
) -> dict[str, Any]:
    """Extract candidate insights from the coaching output.

    Returns a partial state dict — LangGraph merges it into the running
    state. On any LLM failure we log and return an empty candidate list
    so the downstream graph short-circuits cleanly.
    """
    try:
        extracted: ExtractedInsights = await instructor_client.chat.completions.create(
            model=_HAIKU_MODEL,
            max_tokens=_MAX_TOKENS,
            response_model=ExtractedInsights,
            messages=[
                {
                    "role": "user",
                    "content": _build_extraction_prompt(
                        state["coaching_output"], state["exercise_type"]
                    ),
                }
            ],
        )
        return {"candidates": list(extracted.candidates)}
    except Exception as exc:  # noqa: BLE001 — must never raise
        logger.warning(
            "extract_insights failed (%s: %s) — returning empty candidate list",
            type(exc).__name__,
            exc,
        )
        return {"candidates": []}
