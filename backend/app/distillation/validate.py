"""validate_quality — pure gate node.

Reads eval_scores from the triggering analysis and emits one of three
decisions:
- pass:   overall >= 0.85 AND correctness >= 0.8  (high-quality, route
          all candidates to lifecycle → CoVe → store as pending review)
- review: 0.6 <= overall < 0.85                   (still distill, but
          flag eval_tier=low for Batch 3 display priority)
- reject: overall < 0.6 or missing                (END; no candidates
          written — avoids polluting the review queue with noise)

FR-BRAIN-06 threshold definition.
"""

from __future__ import annotations

from typing import Any

from app.distillation.state import DistillationState

_OVERALL_PASS = 0.85
_CORRECTNESS_PASS = 0.80
_OVERALL_REVIEW_FLOOR = 0.60


async def validate_quality(state: DistillationState) -> dict[str, Any]:
    """Decide whether candidates proceed, proceed-for-review, or reject."""
    eval_scores = state.get("eval_scores") or {}
    overall = eval_scores.get("overall")
    correctness = eval_scores.get("correctness")

    if overall is None or overall < _OVERALL_REVIEW_FLOOR:
        return {"validation_decision": "reject"}

    if (
        overall >= _OVERALL_PASS
        and correctness is not None
        and correctness >= _CORRECTNESS_PASS
    ):
        return {"validation_decision": "pass"}

    return {"validation_decision": "review"}
