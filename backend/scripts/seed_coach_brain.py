"""Seed the Coach Brain with ≥20 expert coaching entries (P2-025).

Inserts entries into the coach_brain_entries DB table and embeds them into
the Qdrant coach_brain collection via BrainEmbeddingService.

Requirements:
- FR-BRAIN-09: seed corpus covering squat/bench/deadlift common issues
- FR-BRAIN-18: confirmation_count=1 for seed entries
- status=seed, source=seed_manual_validated in metadata

Usage (from backend/ directory):
    uv run python scripts/seed_coach_brain.py

    Dry-run (print entries, no DB/Qdrant writes):
    uv run python scripts/seed_coach_brain.py --dry-run

Environment:
    DATABASE_URL    — Supabase PgBouncer connection string
    QDRANT_URL      — Qdrant Cloud endpoint
    QDRANT_API_KEY  — Qdrant Cloud API key
    COHERE_API_KEY  — Cohere API key (for embed-v4.0)
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------

# Ensure backend/ is on sys.path for app.* imports
_BACKEND_DIR = Path(__file__).parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

_BACKEND_ENV = _BACKEND_DIR / ".env"
_ROOT_ENV = _BACKEND_DIR.parent / ".env"
_ENV_PATH = _BACKEND_ENV if _BACKEND_ENV.exists() else _ROOT_ENV

if _ENV_PATH.exists():
    from dotenv import load_dotenv  # type: ignore[import-untyped]

    load_dotenv(_ENV_PATH)
    print(f"[seed] Loaded env from {_ENV_PATH}")

# ---------------------------------------------------------------------------
# Seed data — 24 entries (8 per exercise)
# ---------------------------------------------------------------------------

# Each tuple: (exercise, phase, entry_type, content, trigger_tags)
SEED_ENTRIES: list[tuple[str, str, str, str, list[str]]] = [
    # -----------------------------------------------------------------------
    # SQUAT (8 entries)
    # -----------------------------------------------------------------------
    (
        "squat",
        "descent",
        "correction",
        "Excessive forward knee travel past toes with heel rise indicates ankle "
        "dorsiflexion limitation. Cue 'push knees out and sit back' while ensuring "
        "heels remain planted. If persistent, elevate heels with 1.25kg plates or "
        "squat shoes to compensate for limited ankle mobility.",
        ["knee_cave", "ankle_mobility", "heel_rise"],
    ),
    (
        "squat",
        "bottom",
        "correction",
        "Lumbar flexion at depth ('butt wink') increases shear forces on the "
        "lumbar spine. Primary causes: insufficient hip flexion ROM or attempting "
        "depth beyond current mobility. Reduce depth to the point where neutral "
        "spine is maintained, and progressively work hip mobility drills (90/90 "
        "stretch, pigeon pose) to safely increase range over time.",
        ["lumbar_flexion", "butt_wink", "depth"],
    ),
    (
        "squat",
        "descent",
        "correction",
        "Knee valgus (inward knee collapse) during the descent places excessive "
        "stress on the MCL and ACL. Common causes include weak hip external "
        "rotators and poor motor control. Cue 'spread the floor with your feet' "
        "and 'push knees over pinky toes'. Strengthen with banded squats and "
        "single-leg glute bridges.",
        ["knee_cave", "valgus", "hip_weakness"],
    ),
    (
        "squat",
        "ascent",
        "cue",
        "Drive up by pushing your back into the bar and leading with the chest. "
        "Think 'chest up, hips forward' — this prevents the good-morning squat "
        "pattern where hips rise faster than shoulders, shifting load to the lower "
        "back. Maintain a consistent torso angle throughout the ascent.",
        ["good_morning_squat", "torso_lean", "chest_up"],
    ),
    (
        "squat",
        "setup",
        "principle",
        "Bar position determines torso angle requirements. High bar (on traps) "
        "allows a more upright torso and requires greater ankle dorsiflexion. "
        "Low bar (on rear delts) demands more hip hinge and forward lean but "
        "reduces ankle demands. Neither is inherently superior — match bar "
        "position to individual anthropometry and mobility.",
        ["bar_position", "high_bar", "low_bar", "anthropometry"],
    ),
    (
        "squat",
        "descent",
        "cue",
        "Initiate the squat by simultaneously breaking at the hips and knees. "
        "A pure hip-hinge start shifts load posterior and increases forward lean; "
        "a pure knee-break start shifts load anterior onto the quads and patellar "
        "tendon. The coordinated break distributes load evenly across the kinetic "
        "chain.",
        ["initiation", "hip_break", "knee_break"],
    ),
    (
        "squat",
        "bottom",
        "principle",
        "Adequate squat depth is defined as the hip crease descending below the "
        "top of the knee (for powerlifting) or thighs parallel to the floor (for "
        "general training). Depth is limited by ankle dorsiflexion, hip flexion "
        "ROM, and femur-to-torso length ratio. Depth should never be pursued at "
        "the cost of lumbar neutral position.",
        ["depth", "parallel", "hip_crease"],
    ),
    (
        "squat",
        "lockout",
        "cue",
        "At lockout, fully extend hips and knees while maintaining neutral spine. "
        "Avoid hyperextending the lumbar spine by 'squeezing glutes at the top' "
        "rather than leaning back. The bar should be directly over midfoot at "
        "lockout for maximal stability.",
        ["lockout", "hyperextension", "glute_squeeze"],
    ),
    # -----------------------------------------------------------------------
    # BENCH (8 entries)
    # -----------------------------------------------------------------------
    (
        "bench",
        "descent",
        "correction",
        "Excessive elbow flare (elbows at 90° from torso) places the shoulder "
        "in a mechanically disadvantaged position and reduces force transfer "
        "through the kinetic chain. Optimal elbow angle is 45–75° from the "
        "torso depending on grip width. Cue 'tuck your elbows' and 'bend the "
        "bar' to engage the lats and maintain shoulder stability.",
        ["elbow_flare", "shoulder_impingement", "lat_engagement"],
    ),
    (
        "bench",
        "descent",
        "principle",
        "The bar path in a bench press should follow a slight diagonal arc — "
        "lowering to the lower sternum/nipple line and pressing back toward the "
        "face to lockout over the shoulder joint. A straight vertical path either "
        "hits too high on the chest (shoulder strain) or locks out too far forward "
        "(inefficient lever arm). The Nuckols J-curve is the reference pattern.",
        ["bar_path", "j_curve", "touch_point"],
    ),
    (
        "bench",
        "setup",
        "cue",
        "Retract and depress the scapulae before unracking. Think 'put your "
        "shoulder blades in your back pockets'. This creates a stable shelf, "
        "shortens the range of motion, and protects the shoulders. If scapular "
        "position is lost during the set, re-rack and reset — pressing with "
        "protracted scapulae loads the anterior shoulder capsule.",
        ["scapular_retraction", "shoulder_stability", "setup"],
    ),
    (
        "bench",
        "bottom",
        "correction",
        "Bouncing the bar off the chest uses elastic rebound to move the weight "
        "through the sticking point, masking real strength deficits and reducing "
        "control at the touch point. A controlled touch (bar contacts chest with "
        "zero downward velocity) followed by a deliberate press develops true "
        "strength through the bottom range. Pause reps at 1–2 seconds build this "
        "control.",
        ["bounce", "chest_touch", "pause_bench", "control"],
    ),
    (
        "bench",
        "ascent",
        "correction",
        "Uneven press where one arm locks out before the other indicates a "
        "strength imbalance between left and right pecs/triceps. Address with "
        "unilateral dumbbell pressing (3 sets of 8–12 per side) and conscious "
        "effort to initiate the press symmetrically. If the bar tilts "
        "consistently to one side, the weaker side should start the concentric "
        "push.",
        ["asymmetry", "uneven_lockout", "strength_imbalance"],
    ),
    (
        "bench",
        "setup",
        "principle",
        "Leg drive transfers force from the floor through the posterior chain "
        "into the bench, creating a stable base and assisting the press. Feet "
        "should be flat on the floor (or on toes for those with shorter legs) "
        "with knees at roughly 90° and pushed outward. Drive the feet into the "
        "floor as if leg pressing the bench away — this maintains the arch and "
        "scapular position throughout the lift.",
        ["leg_drive", "foot_position", "arch", "stability"],
    ),
    (
        "bench",
        "descent",
        "cue",
        "Control the eccentric at a consistent tempo — aim for a 2-second "
        "descent. A rushed descent reduces time under tension and makes it harder "
        "to hit the correct touch point. Think 'pull the bar to your chest' using "
        "the lats, as if performing a barbell row in reverse. This maintains "
        "tightness and bar path control.",
        ["eccentric_control", "tempo", "lat_pull"],
    ),
    (
        "bench",
        "lockout",
        "cue",
        "At lockout, the bar should be directly over the shoulder joint with "
        "elbows fully extended. Avoid excessive forward drift past the shoulders "
        "which creates an unstable position. Cue 'press to the ceiling' and "
        "'lock your elbows'. Maintain scapular retraction — do not let the "
        "shoulders roll forward at the top.",
        ["lockout", "elbow_extension", "shoulder_position"],
    ),
    # -----------------------------------------------------------------------
    # DEADLIFT (8 entries)
    # -----------------------------------------------------------------------
    (
        "deadlift",
        "ascent",
        "correction",
        "Lumbar flexion (rounding of the lower back) during the pull dramatically "
        "increases shear forces on the lumbar discs. Primary causes: starting "
        "with hips too high, weak erectors, or attempting loads beyond current "
        "capacity. Cue 'big chest, push the floor away' and ensure the initial "
        "pull is leg-driven with the back angle fixed until the bar passes the "
        "knees.",
        ["lumbar_flexion", "back_rounding", "disc_injury"],
    ),
    (
        "deadlift",
        "setup",
        "principle",
        "The hip hinge is the fundamental movement pattern of the deadlift. "
        "Hips load posteriorly while the spine maintains neutral. The torso angle "
        "is determined by limb proportions — longer femurs relative to torso "
        "require more forward lean. Do not force an upright torso if anthropometry "
        "demands otherwise; instead ensure the lumbar spine stays neutral "
        "regardless of torso angle.",
        ["hip_hinge", "anthropometry", "neutral_spine", "torso_angle"],
    ),
    (
        "deadlift",
        "setup",
        "cue",
        "Set up with the bar over midfoot (approximately 1 inch from the shins). "
        "Grip the bar, then bring the shins to the bar — not the bar to the "
        "shins. This ensures optimal leverage. Shoulders should be directly over "
        "or slightly in front of the bar. The arms hang straight down like "
        "cables — never pull with bent elbows.",
        ["setup", "bar_position", "midfoot", "shoulder_position"],
    ),
    (
        "deadlift",
        "ascent",
        "correction",
        "Hips shooting up before the shoulders ('stripper pull') converts the "
        "deadlift into a stiff-leg pull and overloads the lower back. This "
        "indicates either weak quads or a setup where hips start too low. Cue "
        "'push the floor away with your legs' and 'chest and hips rise together'. "
        "Film from the side to verify the back angle stays constant until the bar "
        "passes the knees.",
        ["hips_shooting", "stripper_pull", "quad_weakness"],
    ),
    (
        "deadlift",
        "lockout",
        "correction",
        "Incomplete lockout — failing to fully extend the hips at the top — "
        "leaves the load on the posterior chain and constitutes a failed lift in "
        "competition. Common cause is weak glutes or fear of hyperextension. "
        "Cue 'squeeze your glutes and stand tall' — the lockout should feel like "
        "a standing plank, not a lean-back. Hip thrusts and block pulls above the "
        "knee build lockout strength.",
        ["lockout", "hip_extension", "glute_weakness"],
    ),
    (
        "deadlift",
        "ascent",
        "cue",
        "Keep the bar in contact with the legs throughout the pull. Any forward "
        "drift of the barbell increases the moment arm on the lumbar spine "
        "exponentially. Think 'drag the bar up your shins and thighs'. Wearing "
        "long socks or knee sleeves protects the shins. If the bar drifts forward "
        "off the floor, the lats are not engaged — cue 'protect your armpits' "
        "or 'bend the bar around your legs'.",
        ["bar_path", "lat_engagement", "bar_drift"],
    ),
    (
        "deadlift",
        "descent",
        "principle",
        "The eccentric (lowering) phase of the deadlift should mirror the "
        "concentric in reverse: hinge at the hips first, then bend the knees once "
        "the bar passes them. A controlled descent builds positional awareness and "
        "trains the same muscles eccentrically. Dropping the bar from lockout "
        "(where allowed) eliminates half the training stimulus and provides no "
        "feedback on form breakdown.",
        ["eccentric", "lowering", "hip_hinge", "control"],
    ),
    (
        "deadlift",
        "general",
        "drill",
        "Romanian deadlifts (RDLs) with submaximal load are the primary accessory "
        "for deadlift hip hinge patterning. Keep knees slightly bent and fixed, "
        "hinge until hamstring stretch limits further descent (typically mid-shin "
        "to just below the knee). Maintain a neutral spine throughout. 3 sets of "
        "8–10 at 50–60% of deadlift 1RM, twice per week. This builds posterior "
        "chain strength and reinforces the hip-dominant movement pattern.",
        ["rdl", "accessory", "hip_hinge", "hamstring"],
    ),
]


async def main(dry_run: bool = False) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.models.coach_brain_entry import CoachBrainEntry as CoachBrainEntryModel
    from app.schemas.coach_brain import CoachBrainEntry as CoachBrainEntrySchema

    print(f"[seed] {len(SEED_ENTRIES)} entries to seed")

    if dry_run:
        for i, (ex, ph, et, content, tags) in enumerate(SEED_ENTRIES, 1):
            print(f"\n--- Entry {i}: {ex}/{ph}/{et} ---")
            print(f"  Tags: {tags}")
            print(f"  Content: {content[:100]}...")
        print(f"\n[seed] Dry run — {len(SEED_ENTRIES)} entries would be created.")
        return

    # -----------------------------------------------------------------------
    # DB setup
    # -----------------------------------------------------------------------
    raw_url = os.environ["DATABASE_URL"]
    db_url = (
        raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if raw_url.startswith("postgresql://")
        else raw_url
    )
    engine = create_async_engine(
        db_url, echo=False, connect_args={"statement_cache_size": 0}
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # -----------------------------------------------------------------------
    # Qdrant + Cohere setup
    # -----------------------------------------------------------------------
    from app.services.cohere_client import get_cohere_client
    from app.services.qdrant import get_qdrant_client

    import app.services.qdrant as qdrant_mod

    qdrant_mod._qdrant_client_cache = None
    qdrant_mod._qdrant_client_cache_initialized = False

    qdrant = await get_qdrant_client()
    if qdrant is None:
        print("[seed] ERROR: Qdrant client unavailable — check QDRANT_URL/QDRANT_API_KEY", file=sys.stderr)
        sys.exit(1)

    try:
        cohere = get_cohere_client()
    except RuntimeError as exc:
        print(f"[seed] ERROR: Cohere client unavailable — {exc}", file=sys.stderr)
        sys.exit(1)

    from app.services.brain_embedding import BrainEmbeddingService

    embedding_svc = BrainEmbeddingService(cohere_client=cohere, qdrant_client=qdrant)

    # -----------------------------------------------------------------------
    # Insert into DB + embed into Qdrant
    # -----------------------------------------------------------------------
    schema_entries: list[CoachBrainEntrySchema] = []

    async with session_factory() as session:
        for ex, ph, et, content, tags in SEED_ENTRIES:
            entry_id = uuid.uuid4()
            model = CoachBrainEntryModel(
                id=entry_id,
                exercise=ex,
                phase=ph,
                entry_type=et,
                content=content,
                trigger_tags=tags,
                status="seed",
                confirmation_count=1,
                source_analysis_ids=[],
                extra_metadata={"source": "seed_manual_validated"},
            )
            session.add(model)

            # Build schema entry for embedding (needs the UUID)
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            schema_entries.append(
                CoachBrainEntrySchema(
                    id=entry_id,
                    content=content,
                    exercise=ex,
                    phase=ph,
                    entry_type=et,
                    status="seed",
                    confirmation_count=1,
                    source_analysis_ids=[],
                    trigger_tags=tags,
                    confidence_score=None,
                    metadata={"source": "seed_manual_validated"},
                    created_at=now,
                    updated_at=now,
                )
            )

        await session.commit()
        print(f"[seed] Inserted {len(SEED_ENTRIES)} entries into coach_brain_entries table")

    # Embed and upsert to Qdrant
    print("[seed] Embedding entries via Cohere embed-v4.0 and upserting to Qdrant...")
    point_ids = await embedding_svc.embed_and_upsert_batch(schema_entries)
    print(f"[seed] Upserted {len(point_ids)} points to coach_brain collection")

    # Report
    print("\n[seed] Summary:")
    exercises = {}
    for ex, ph, et, _, _ in SEED_ENTRIES:
        exercises.setdefault(ex, []).append(f"{ph}/{et}")
    for ex, items in sorted(exercises.items()):
        print(f"  {ex}: {len(items)} entries")

    print(f"\n[seed] Done. Total: {len(SEED_ENTRIES)} entries seeded.")

    await engine.dispose()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=dry_run))
