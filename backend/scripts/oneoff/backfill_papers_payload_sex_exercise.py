"""One-shot: backfill `exercise` + `sex_applicability` payload keys onto
existing prod `papers_rag` Qdrant points. Idempotent — re-running is a no-op
(set_payload overwrites with the same values).

Fixes the live bug (issue #222): prod papers_rag points carry NO `exercise`
key, so the papers-side exercise_filter (a MatchValue on a missing key) matches
zero points → research papers are silently never retrieved into coaching. For
each rag_documents row we set_payload(exercise=row.exercise_tags,
sex_applicability=row.sex_applicability) on all points whose paper_id matches
that row's id. Also (re)creates the sex_applicability keyword index.

Run (from inside the prod backend container):
    docker exec spelix-backend-1 /app/.venv/bin/python \\
        /app/backend/scripts/oneoff/backfill_papers_payload_sex_exercise.py

Exit code 0 on success/no-op. Nonzero on any unexpected error. Safe to rerun.

Environment: DATABASE_URL, QDRANT_URL, QDRANT_API_KEY
"""

import asyncio
import os
import sys

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

_COLLECTION = "papers_rag"


async def _ensure_sex_index(client: AsyncQdrantClient) -> None:
    """Create the sex_applicability keyword index; swallow already-exists."""
    try:
        await client.create_payload_index(
            collection_name=_COLLECTION,
            field_name="sex_applicability",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        print("OK: created papers_rag.sex_applicability keyword payload index")
    except Exception as exc:
        msg = str(exc).lower()
        if "already" in msg or "exists" in msg or "duplicate" in msg:
            print(
                "OK: papers_rag.sex_applicability index already present "
                f"({exc.__class__.__name__})"
            )
        else:
            raise


async def main() -> int:
    raw_url = os.environ["DATABASE_URL"]
    db_url = (
        raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if raw_url.startswith("postgresql://")
        else raw_url
    )
    engine = create_async_engine(
        db_url, echo=False, connect_args={"statement_cache_size": 0}
    )

    qdrant_url = os.environ["QDRANT_URL"]
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")
    client = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    try:
        await _ensure_sex_index(client)

        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT id, exercise_tags, sex_applicability "
                        "FROM rag_documents"
                    )
                )
            ).all()

        print(f"[backfill] {len(rows)} rag_documents rows to backfill")

        updated = 0
        for row in rows:
            paper_id = str(row.id)
            exercise_tags = list(row.exercise_tags) if row.exercise_tags else []
            sex_applicability = row.sex_applicability or "both"

            points_filter = Filter(
                must=[
                    FieldCondition(
                        key="paper_id", match=MatchValue(value=paper_id)
                    )
                ]
            )

            await client.set_payload(
                collection_name=_COLLECTION,
                payload={
                    "exercise": exercise_tags,
                    "sex_applicability": sex_applicability,
                },
                points=points_filter,
            )
            updated += 1
            print(
                f"  {paper_id}: exercise={exercise_tags} "
                f"sex_applicability={sex_applicability}"
            )

        print(f"[backfill] Done. Updated payload on {updated} papers.")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.close()
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
