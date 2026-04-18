"""D-045 diagnostic: measure rerank scores along the live agent retrieval path.

Goal
----
Determine which factor is keeping ``retrieval_source='papers_only_fallback'``
on prod even after M-04 re-embedded all 24 seeds with the FR-BRAIN-03
contextualized prefix.

The script mirrors the EXACT path used by ``app/agents/tools.py::retrieve_coach_brain``
(active on prod since ``SPELIX_PHASE3_AGENT_ENABLED=1`` was set in session 32):

    embed query (SEARCH_QUERY) → hybrid_search coach_brain (rerank=True)
    → top_brain_score = max(ctx.score for ctx in contexts)

Per-exercise we test four query variants:

  Q1  agent_current   — what live prod sends today:
                          "{exercise} {variant} coaching cue correction"
  Q2  vocab_rich      — query enriched with kinesiology terms drawn from the
                        seed trigger_tags (tests hypothesis (b) — does giving
                        the reranker overlapping vocabulary lift the score?)
  Q3  rep_context     — query with rep-metric-style language a real coaching
                        prompt would generate (tests whether richer real-world
                        queries clear the threshold)
  Q4  seed_self_query — embed a known seed's content as the query (ceiling:
                        bounds the maximum possible rerank score for the
                        seed corpus)

Output
------
Per exercise, a 4-row table with: query label, top-3 reranked docs (id +
score + content snippet), retrieval_source classification, plus a final
verdict per query about whether the score crossed the FR-BRAIN-05
thresholds (0.65 hybrid, 0.82 primary).

Run
---
Local (with .env at repo root):
    uv run python backend/scripts/oneoff/diagnose_coach_brain_retrieval.py

Prod (per session 46 docker workflow):
    docker exec -u root spelix-backend-1 mkdir -p /app/scripts/oneoff
    docker cp backend/scripts/oneoff/diagnose_coach_brain_retrieval.py \\
        spelix-backend-1:/app/scripts/oneoff/diagnose_coach_brain_retrieval.py
    docker exec spelix-backend-1 python \\
        /app/scripts/oneoff/diagnose_coach_brain_retrieval.py

Read-only — no DB writes, no Qdrant writes. Safe to rerun.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

_BACKEND_DIR = Path(__file__).parent.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

_BACKEND_ENV = _BACKEND_DIR / ".env"
_ROOT_ENV = _BACKEND_DIR.parent / ".env"
_ENV_PATH = _BACKEND_ENV if _BACKEND_ENV.exists() else _ROOT_ENV

if _ENV_PATH.exists():
    from dotenv import load_dotenv  # type: ignore[import-untyped]

    load_dotenv(_ENV_PATH)
    print(f"[diag] Loaded env from {_ENV_PATH}")


# FR-BRAIN-05 thresholds, mirrored from
# app/services/dual_collection.py + app/agents/tools.py.
_PRIMARY_THRESHOLD: float = 0.82
_HYBRID_FLOOR_THRESHOLD: float = 0.65


@dataclass(frozen=True)
class QueryProbe:
    label: str
    query: str
    note: str


def _classify(top_score: float) -> str:
    if top_score >= _PRIMARY_THRESHOLD:
        return "coach_brain_primary"
    if top_score >= _HYBRID_FLOOR_THRESHOLD:
        return "hybrid_brain_supplementary"
    return "papers_only_fallback"


def _build_probes(
    exercise: str,
    variant: str,
    seed_excerpt: str,
) -> list[QueryProbe]:
    """Construct the four query probes for one exercise.

    Vocab-rich and rep-context queries are hand-tuned per exercise from the
    seed trigger_tags + Phase 1 RepMetrics field names, so they read like
    plausible upgrades the agent could be made to emit.
    """
    if exercise == "bench":
        vocab_rich = (
            "bench press eccentric tempo control elbow flare "
            "scapular retraction lat engagement bar path j curve"
        )
        rep_context = (
            "bench press elbow angle at bottom 78 degrees descent phase "
            "rapid eccentric uneven lockout tempo correction cue"
        )
    elif exercise == "squat":
        vocab_rich = (
            "squat depth lumbar flexion butt wink knee valgus "
            "ankle dorsiflexion bar position torso lean lockout"
        )
        rep_context = (
            "squat depth angle 95 degrees torso lean 35 degrees descent "
            "knee cave hip mobility cue correction"
        )
    elif exercise == "deadlift":
        vocab_rich = (
            "deadlift hip hinge lumbar flexion bar path stripper pull "
            "lockout glute extension lat engagement RDL"
        )
        rep_context = (
            "deadlift hip angle at bottom 105 degrees ascent phase hips "
            "shooting up before shoulders quad weakness cue correction"
        )
    else:
        raise ValueError(f"unknown exercise: {exercise!r}")

    return [
        QueryProbe(
            label="Q1 agent_current",
            query=f"{exercise} {variant} coaching cue correction",
            note="what live prod sends today (tools.py::retrieve_coach_brain)",
        ),
        QueryProbe(
            label="Q2 vocab_rich",
            query=vocab_rich,
            note="enriched with seed trigger_tags vocabulary",
        ),
        QueryProbe(
            label="Q3 rep_context",
            query=rep_context,
            note="includes rep-metric language plausible from agent context",
        ),
        QueryProbe(
            label="Q4 seed_self_query",
            query=seed_excerpt,
            note="ceiling — uses real seed content as query",
        ),
    ]


async def _run_probe_for_collection(
    retrieval_svc,
    probe: QueryProbe,
    exercise: str,
) -> list:
    """Mirror tools.py::retrieve_coach_brain — hybrid_search with rerank=True."""
    from qdrant_client import models as qdrant_models

    status_filter = qdrant_models.FieldCondition(
        key="status",
        match=qdrant_models.MatchAny(any=["active", "seed"]),
    )
    contexts = await retrieval_svc.hybrid_search(
        probe.query,
        collection="coach_brain",
        top_k=10,
        rerank_top_n=5,
        exercise_filter=exercise,
        additional_filters=[status_filter],
        rerank=True,
    )
    return contexts


def _format_row(label: str, top_score: float, classification: str) -> str:
    cross_hybrid = "y" if top_score >= _HYBRID_FLOOR_THRESHOLD else "n"
    cross_primary = "y" if top_score >= _PRIMARY_THRESHOLD else "n"
    return (
        f"  {label:<22} top={top_score:.4f}  "
        f">=0.65? {cross_hybrid}  >=0.82? {cross_primary}  "
        f"-> {classification}"
    )


async def main() -> int:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from app.models.coach_brain_entry import CoachBrainEntry as CoachBrainEntryModel
    from app.services.cohere_client import get_cohere_client
    from app.services.qdrant import get_qdrant_client
    from app.services.retrieval import RetrievalService
    from app.services.sparse_retrieval import SparseRetrievalService

    raw_url = os.environ["DATABASE_URL"]
    db_url = (
        raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if raw_url.startswith("postgresql://")
        else raw_url
    )
    engine = create_async_engine(
        db_url, echo=False, connect_args={"statement_cache_size": 0}
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    qdrant = await get_qdrant_client()
    if qdrant is None:
        print(
            "[diag] ERROR: Qdrant client unavailable — check QDRANT_URL/QDRANT_API_KEY",
            file=sys.stderr,
        )
        return 1

    try:
        cohere = get_cohere_client()
    except RuntimeError as exc:
        print(
            f"[diag] ERROR: Cohere client unavailable — {type(exc).__name__}",
            file=sys.stderr,
        )
        return 1

    sparse_svc = SparseRetrievalService(qdrant_client=qdrant)
    retrieval_svc = RetrievalService(
        cohere_client=cohere,
        qdrant_client=qdrant,
        sparse_service=sparse_svc,
    )

    # ------------------------------------------------------------------
    # Pick one representative seed per exercise as the Q4 ceiling probe.
    # ------------------------------------------------------------------
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(CoachBrainEntryModel)
                .where(CoachBrainEntryModel.status == "seed")
                .order_by(CoachBrainEntryModel.created_at)
            )
        ).scalars().all()

    print(f"[diag] Loaded {len(rows)} seed rows from coach_brain_entries")
    if not rows:
        print(
            "[diag] ERROR: no seeds in DB — re-run scripts/seed_coach_brain.py first",
            file=sys.stderr,
        )
        await engine.dispose()
        return 1

    by_exercise: dict[str, list] = {}
    for r in rows:
        by_exercise.setdefault(r.exercise, []).append(r)

    exercises = [
        ("bench", "flat"),
        ("squat", "high_bar"),
        ("deadlift", "conventional"),
    ]

    print()
    print("=" * 78)
    print("D-045 diagnostic — coach_brain rerank scores by query construction")
    print("=" * 78)
    print(
        "Path: hybrid_search(coach_brain, rerank=True) — mirrors agent's "
        "retrieve_coach_brain"
    )
    print(f"Thresholds: {_HYBRID_FLOOR_THRESHOLD} hybrid_floor, {_PRIMARY_THRESHOLD} primary")
    print()

    try:
        for exercise, variant in exercises:
            seeds = by_exercise.get(exercise) or []
            if not seeds:
                print(f"[diag] no seeds for exercise={exercise!r} — skip")
                continue

            seed_excerpt = (
                seeds[0].content[:280]
                if seeds[0].content
                else f"{exercise} coaching cue"
            )
            probes = _build_probes(exercise, variant, seed_excerpt)

            print(f"--- exercise={exercise} variant={variant} (seed corpus={len(seeds)}) ---")

            for probe in probes:
                try:
                    contexts = await _run_probe_for_collection(
                        retrieval_svc, probe, exercise
                    )
                except Exception as exc:  # noqa: BLE001
                    print(
                        f"  {probe.label:<22} ERROR: {type(exc).__name__}",
                        file=sys.stderr,
                    )
                    continue

                top_score = max((ctx.score for ctx in contexts), default=0.0)
                classification = _classify(top_score)
                print(_format_row(probe.label, top_score, classification))
                print(f"    query: {probe.query!r}")
                print(f"    note:  {probe.note}")
                for i, ctx in enumerate(contexts[:3], 1):
                    snippet = (ctx.chunk.text or "")[:90].replace("\n", " ")
                    print(
                        f"    #{i} score={ctx.score:.4f} id={ctx.chunk.id[:8]}.. "
                        f"text={snippet!r}"
                    )
                print()

            print()

        # ----------------------------------------------------------------
        # Summary verdict
        # ----------------------------------------------------------------
        print("=" * 78)
        print("Verdict guide:")
        print(
            "  - If Q1 < 0.65 AND Q2/Q3 cross 0.65: query construction is the "
            "root cause"
        )
        print(
            "  - If Q1/Q2/Q3 < 0.65 AND Q4 also low: seed content insufficient "
            "(need richer corpus or richer FR-BRAIN-03 template)"
        )
        print(
            "  - If Q4 high but Q2/Q3 still low: prefix is creating a "
            "vocabulary mismatch with natural-language queries"
        )
        print("=" * 78)
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
