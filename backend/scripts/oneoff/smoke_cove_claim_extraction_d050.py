"""D-050 smoke: exercise the refined _build_claim_extraction_prompt
against real Haiku 4.5 and print the extracted claims.

Usage (from repo root):

    ANTHROPIC_API_KEY=sk-ant-... uv run python \\
        backend/scripts/oneoff/smoke_cove_claim_extraction_d050.py

Qualitative gate: at least 60% of the extracted claims should read as
principle-level statements (about what is biomechanically optimal for
a lift in general), NOT lifter-specific measurements ("your eccentric
was 5.16s", "elbow angle reached 38°"). Compare the printed claims to
the ADR-COVE-02 worked examples.

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
# Synthetic CoachingOutput modeled on session 48 prod analysis bfbed270
# (bench fixture, atharva-bench-nw-10s-720p.mp4). Mix of principle-level
# statements and measurement-based observations.
# ---------------------------------------------------------------------------

_MANDATORY_DISCLAIMER = (
    "This feedback is for educational purposes only and is not a substitute "
    "for in-person coaching or medical advice."
)


def _build_synthetic_output() -> CoachingOutput:
    """Coaching shape matching session 48 bench ``bfbed270``."""
    return CoachingOutput(
        summary=(
            "Your bench press shows controlled descent but limited depth at "
            "the bottom. Elbow flare is within acceptable range but bar path "
            "drifted forward at lockout."
        ),
        strengths=[
            "Consistent eccentric tempo across all reps.",
            "Stable setup position with shoulder blades retracted.",
        ],
        issues=[
            Issue(
                rep_number=1,
                joint="Left elbow",
                description=(
                    "Elbow angle reached 38° at the bottom, below the "
                    "optimal 45–75° range from torso for bench press."
                ),
                severity="Medium",
            ),
            Issue(
                rep_number=1,
                joint="Bar path",
                description=(
                    "Bar path drifted forward at lockout instead of following "
                    "the slight diagonal J-curve that optimizes lever arm."
                ),
                severity="Low",
            ),
            Issue(
                rep_number=1,
                joint="Tempo",
                description=(
                    "Your eccentric phase measured 5.16 seconds, above the "
                    "approximately 2-second target for hypertrophy training."
                ),
                severity="Low",
            ),
        ],
        correction_plan=[
            "Tuck your elbows to 45–75° from the torso during descent.",
            (
                "Follow a slight diagonal J-curve: lower to the lower "
                "sternum, press back toward lockout over the shoulders."
            ),
            "Target approximately 2 seconds of eccentric descent per rep.",
        ],
        recommended_cues=[
            "Elbows 45–75° on the way down.",
            "J-curve bar path, not straight up.",
        ],
        disclaimer=_MANDATORY_DISCLAIMER,
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )


async def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    output = _build_synthetic_output()
    prompt = _build_claim_extraction_prompt(output)

    print("=" * 72)
    print("D-050 smoke: claim extraction against live Haiku 4.5")
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
    print("Qualitative gate (operator judgment):")
    print("  - Do these read as PRINCIPLES (general optimal ranges / targets)?")
    print("  - Or do they mention THIS lifter's measurements (38°, 5.16s)?")
    print()
    print("Expected post-D-050 shape: 'Optimal elbow angle is 45–75°...',")
    print("'Recommended eccentric is ~2s for hypertrophy...',")
    print("'J-curve bar path optimizes lever arm...'")
    print()
    print("Anti-pattern (pre-D-050): 'Elbow angle was 38°',")
    print("'Eccentric measured 5.16s', 'Bar path drifted forward'.")


if __name__ == "__main__":
    asyncio.run(main())
