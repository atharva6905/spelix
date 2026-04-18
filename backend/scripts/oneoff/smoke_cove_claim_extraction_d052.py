"""D-052 smoke: exercise the tightened _build_claim_extraction_prompt
against real Haiku 4.5 with adversarial inputs that previously triggered
inversion and extrapolation hallucinations on prod analysis ``c46023c9``.

Usage (from repo root):

    ANTHROPIC_API_KEY=sk-ant-... uv run --project backend python \\
        backend/scripts/oneoff/smoke_cove_claim_extraction_d052.py

Qualitative gate (operator judgment, two axes):
  (A) NO claim inverts the fast-descent issue's direction. If the
      coaching says fast/rushed descent is the problem, extracted claims
      must reference fast/rushed — NOT slow.
  (B) NO claim extrapolates the bare optimal-range issue into a
      minimum, maximum, or alternative reference range. If the coaching
      says '45–75° is optimal' without a minimum, extracted claims must
      cite 45–75° — NOT 'minimum 60°' or '60–100° reference range'.

NOT run in CI — one-shot operator tool. Calls the real Anthropic API.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Make the backend package importable when run from repo root.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))

import anthropic  # noqa: E402
import instructor  # noqa: E402

from app.schemas.coaching import CoachingOutput, Issue  # noqa: E402
from app.services.cove import (  # noqa: E402
    HAIKU_MODEL,
    ClaimList,
    _build_claim_extraction_prompt,
)

# ---------------------------------------------------------------------------
# Adversarial CoachingOutput modeled on session 49 analysis c46023c9
# hallucination triggers. Two issues are included that previously caused
# inversion and extrapolation failures in iter 1 / iter 2 of that run.
# ---------------------------------------------------------------------------

_MANDATORY_DISCLAIMER = (
    "This feedback is for educational purposes only and is not a substitute "
    "for in-person coaching or medical advice."
)


def _build_adversarial_output() -> CoachingOutput:
    """Coaching shape designed to tempt inversion + extrapolation."""
    return CoachingOutput(
        summary=(
            "Your bench press shows controlled setup but the descent tempo "
            "is inconsistent and the elbow angle at the bottom is on the "
            "shallow end of the optimal range."
        ),
        strengths=[
            "Consistent eccentric tempo within each rep.",
            "Stable shoulder retraction throughout.",
        ],
        issues=[
            # Inversion trigger: coaching explicitly criticises a FAST
            # descent. Pre-D-052, extractor has been observed to
            # paraphrase this as 'slow descent is bad'.
            Issue(
                rep_number=1,
                joint="Tempo",
                description=(
                    "A rushed, fast eccentric descent reduces time under "
                    "tension and makes it harder to hit a consistent touch "
                    "point on the chest. Your descent phase on reps 1 and "
                    "2 was noticeably faster than reps 3 and 4."
                ),
                severity="Medium",
            ),
            # Extrapolation trigger: coaching cites the optimal 45–75°
            # range but NEVER states a minimum, maximum, or alternative
            # reference range. Pre-D-052, extractor has invented
            # 'minimum 60°' and '60–100° reference range'.
            Issue(
                rep_number=1,
                joint="Left elbow",
                description=(
                    "Optimal elbow angle at the bottom of the bench press "
                    "is 45\u201375\u00b0 from the torso. Your elbow reached 48\u00b0 "
                    "on rep 1, inside the optimal range but near the lower "
                    "bound."
                ),
                severity="Low",
            ),
        ],
        correction_plan=[
            (
                "Control the eccentric descent to approximately 2 seconds "
                "per rep rather than rushing the bar down."
            ),
            "Maintain elbow angle within the 45\u201375\u00b0 optimal range.",
        ],
        recommended_cues=[
            "Two-count descent.",
            "Elbows 45\u201375\u00b0 from torso.",
        ],
        disclaimer=_MANDATORY_DISCLAIMER,
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )


async def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    output = _build_adversarial_output()
    prompt = _build_claim_extraction_prompt(output)

    print("=" * 72)
    print("D-052 smoke: claim extraction against live Haiku 4.5 (adversarial)")
    print("=" * 72)
    print()
    print("Prompt head (first 400 chars):")
    print(prompt[:400])
    print("...")
    print()

    client = instructor.from_anthropic(anthropic.AsyncAnthropic())
    result: ClaimList = await client.chat.completions.create(
        model=HAIKU_MODEL,
        max_tokens=1024,
        response_model=ClaimList,
        messages=[{"role": "user", "content": prompt}],
    )

    print(f"Extracted {len(result.claims)} claim(s):")
    print()
    for i, claim in enumerate(result.claims, 1):
        print(f"  {i}. {claim}")
    print()
    print("Gate A — inversion-guard:")
    print("  - Does ANY claim say 'slow descent' / 'slow eccentric is bad'?")
    print("  - If yes \u2192 FAIL. Coaching said fast/rushed; no claim may invert.")
    print()
    print("Gate B — extrapolation-guard:")
    print("  - Does ANY claim say 'minimum', 'maximum', or a range other")
    print("    than 45\u201375\u00b0 for the elbow angle?")
    print("  - If yes \u2192 FAIL. Coaching cited only 45\u201375\u00b0 as optimal.")
    print()
    print("Expected post-D-052 shape (examples):")
    print("  'A rushed or fast eccentric descent reduces time under tension")
    print("   in the bench press.'")
    print("  'Optimal elbow angle at the bottom of the bench press is")
    print("   45\u201375\u00b0 from the torso.'")
    print()
    print("Anti-pattern (pre-D-052 on c46023c9): 'slow eccentric is harder",)
    print("to control', 'minimum elbow angle is 60\u00b0'.")


if __name__ == "__main__":
    asyncio.run(main())
