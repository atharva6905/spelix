"""One-shot: sanitize two bench seed entries on prod whose `content` field
contains prohibited SaMD language ("rotator cuff impingement risk", "risking
sternum or rib injury"). Surfaced when ADR-BRAIN-08 made seed entries
retrievable; the two strings would have reached the LLM prompt verbatim.

Updates BOTH the Postgres `coach_brain_entries.content` field AND the Qdrant
`coach_brain` collection payload's `content` field for matching points.
Idempotent — re-running against already-clean content is a no-op (the source
substring will not be found).

Run (from inside the prod backend container):
    docker exec spelix-backend-1 /app/.venv/bin/python \\
        /app/backend/scripts/oneoff/sanitize_seed_samd_content.py

Returns exit 0 on success OR when no matching rows exist. Nonzero on any
unexpected error. Safe to rerun.

NOTE: This script does NOT re-embed the Qdrant vectors. The embedding still
encodes the original text — so if a user query semantically matches the OLD
wording, this entry may still surface, but the returned content field will
carry the sanitized wording. This is an intentional tradeoff (avoids Cohere
re-embed cost for two entries); a future cleanup pass can re-embed if needed.
"""

import asyncio
import os
import sys

from qdrant_client import AsyncQdrantClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# The two bench seed entries that contain SaMD-violating language and their
# sanitized replacements. Matched by content prefix (stable enough to be
# idempotent without row-id knowledge, because these exact bench seeds are
# the only entries that share these prefixes).
_REPLACEMENTS = [
    (
        "Excessive elbow flare (elbows at 90° from torso) places the shoulder "
        "in a vulnerable position and increases rotator cuff impingement risk. "
        "Optimal elbow angle is 45–75° from the torso depending on grip width. "
        "Cue 'tuck your elbows' and 'bend the bar' to engage the lats and "
        "protect the shoulder joint.",
        "Excessive elbow flare (elbows at 90° from torso) places the shoulder "
        "in a mechanically disadvantaged position and reduces force transfer "
        "through the kinetic chain. Optimal elbow angle is 45–75° from the "
        "torso depending on grip width. Cue 'tuck your elbows' and 'bend the "
        "bar' to engage the lats and maintain shoulder stability.",
    ),
    (
        "Bouncing the bar off the chest uses elastic rebound to move the weight "
        "through the sticking point, masking weakness and risking sternum or rib "
        "injury. A controlled touch (bar contacts chest with zero downward "
        "velocity) followed by a deliberate press develops true strength through "
        "the bottom range. Pause reps at 1–2 seconds build this control.",
        "Bouncing the bar off the chest uses elastic rebound to move the weight "
        "through the sticking point, masking real strength deficits and reducing "
        "control at the touch point. A controlled touch (bar contacts chest with "
        "zero downward velocity) followed by a deliberate press develops true "
        "strength through the bottom range. Pause reps at 1–2 seconds build this "
        "control.",
    ),
]


async def _update_postgres(sessionmaker_: async_sessionmaker) -> list[str]:
    """Update `coach_brain_entries.content` for matching rows. Returns updated row IDs."""
    updated_ids: list[str] = []
    async with sessionmaker_() as session:
        for old, new in _REPLACEMENTS:
            result = await session.execute(
                text(
                    "UPDATE coach_brain_entries SET content = :new "
                    "WHERE content = :old RETURNING id"
                ),
                {"old": old, "new": new},
            )
            for row in result.fetchall():
                updated_ids.append(str(row[0]))
        await session.commit()
    return updated_ids


async def _update_qdrant(qdrant: AsyncQdrantClient, row_ids: list[str]) -> None:
    """Update `content` payload field for the matching Qdrant points."""
    for row_id, (_, new) in zip(row_ids, _REPLACEMENTS, strict=False):
        await qdrant.set_payload(
            collection_name="coach_brain",
            payload={"content": new},
            points=[row_id],
        )


async def main() -> int:
    db_url = os.environ["DATABASE_URL"].replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )
    qdrant_url = os.environ["QDRANT_URL"]
    qdrant_api_key = os.environ["QDRANT_API_KEY"]

    engine = create_async_engine(db_url, connect_args={"statement_cache_size": 0})
    sessionmaker_ = async_sessionmaker(engine, expire_on_commit=False)
    qdrant = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    try:
        updated_ids = await _update_postgres(sessionmaker_)
        print(f"postgres: updated {len(updated_ids)} coach_brain_entries row(s): {updated_ids}")

        if updated_ids:
            await _update_qdrant(qdrant, updated_ids)
            print(f"qdrant: patched payload.content on {len(updated_ids)} point(s)")
        else:
            print("qdrant: no rows to patch (content already sanitized or absent)")

        return 0
    except Exception as exc:
        print(f"FAIL: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        await qdrant.close()
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
