"""One-shot: re-embed the 24 seed Coach Brain entries with FR-BRAIN-03
contextualized prefix via BrainEmbeddingService.build_contextual_text.

Idempotent — Qdrant upsert_points with matching UUIDs replaces existing
points. No Postgres rows are touched. Safe to rerun.

Implements M-04 (backlog). Addresses session-44 observation that
retrieval_source='papers_only_fallback' on prod despite seeds being
eligible per FR-BRAIN-05 + ADR-BRAIN-08.

Run (from inside the prod backend container):
    docker exec spelix-backend /app/.venv/bin/python \\
        /app/backend/scripts/oneoff/reembed_coach_brain_seeds.py

Run locally against prod (from backend/ with .env loaded):
    uv run python scripts/oneoff/reembed_coach_brain_seeds.py

Exit code 0 on success. Nonzero on any unexpected error.

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
from pathlib import Path


# Ensure backend/ is on sys.path for app.* imports when run outside container.
_BACKEND_DIR = Path(__file__).parent.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

_BACKEND_ENV = _BACKEND_DIR / ".env"
_ROOT_ENV = _BACKEND_DIR.parent / ".env"
_ENV_PATH = _BACKEND_ENV if _BACKEND_ENV.exists() else _ROOT_ENV

if _ENV_PATH.exists():
    from dotenv import load_dotenv  # type: ignore[import-untyped]

    load_dotenv(_ENV_PATH)
    print(f"[reembed] Loaded env from {_ENV_PATH}")


async def main() -> int:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from app.models.coach_brain_entry import CoachBrainEntry as CoachBrainEntryModel
    from app.schemas.coach_brain import CoachBrainEntry as CoachBrainEntrySchema
    from app.services.brain_embedding import BrainEmbeddingService
    from app.services.cohere_client import get_cohere_client
    from app.services.qdrant import get_qdrant_client

    # ------------------------------------------------------------------
    # DB setup
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Qdrant + Cohere setup
    # ------------------------------------------------------------------
    qdrant = await get_qdrant_client()
    if qdrant is None:
        print(
            "[reembed] ERROR: Qdrant client unavailable — check QDRANT_URL/QDRANT_API_KEY",
            file=sys.stderr,
        )
        return 1

    try:
        cohere = get_cohere_client()
    except RuntimeError as exc:
        print(f"[reembed] ERROR: Cohere client unavailable — {exc}", file=sys.stderr)
        return 1

    embedding_svc = BrainEmbeddingService(
        cohere_client=cohere, qdrant_client=qdrant
    )

    # ------------------------------------------------------------------
    # Load seeds from Postgres
    # ------------------------------------------------------------------
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(CoachBrainEntryModel).where(
                    CoachBrainEntryModel.status == "seed"
                )
            )
        ).scalars().all()

        print(f"[reembed] Loaded {len(rows)} seed rows from coach_brain_entries")

        if not rows:
            print(
                "[reembed] ERROR: no seed rows found. "
                "Run `scripts/seed_coach_brain.py` first if this is a fresh env.",
                file=sys.stderr,
            )
            await engine.dispose()
            return 1

        schema_entries: list[CoachBrainEntrySchema] = []
        for r in rows:
            schema_entries.append(
                CoachBrainEntrySchema(
                    id=r.id,
                    content=r.content,
                    exercise=r.exercise,  # type: ignore[arg-type]
                    phase=r.phase,  # type: ignore[arg-type]
                    entry_type=r.entry_type,  # type: ignore[arg-type]
                    status=r.status,  # type: ignore[arg-type]
                    confirmation_count=r.confirmation_count,
                    source_analysis_ids=r.source_analysis_ids,
                    trigger_tags=r.trigger_tags,
                    confidence_score=(
                        float(r.confidence_score)
                        if r.confidence_score is not None
                        else None
                    ),
                    metadata=r.extra_metadata,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
            )

    # ------------------------------------------------------------------
    # Re-embed + upsert
    # ------------------------------------------------------------------
    print(
        f"[reembed] Re-embedding {len(schema_entries)} entries via "
        "Cohere embed-v4.0 (SEARCH_DOCUMENT) with FR-BRAIN-03 prefix..."
    )
    point_ids = await embedding_svc.embed_and_upsert_batch(schema_entries)

    print(f"[reembed] Upserted {len(point_ids)} points to coach_brain collection")

    # Report per-exercise breakdown.
    from collections import Counter

    by_ex: Counter[str] = Counter(e.exercise for e in schema_entries)
    for ex, n in sorted(by_ex.items()):
        print(f"  {ex}: {n} entries")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
