"""One-shot: create the missing `exercise` keyword payload index on
prod `papers_rag` Qdrant collection. Idempotent — re-running is a no-op.

Run (from inside the prod backend container):
    docker exec spelix-backend-1 /app/.venv/bin/python \\
        /app/backend/scripts/oneoff/create_papers_rag_exercise_index.py

Exit code 0 on success OR when the index already exists. Nonzero on any
unexpected error. Safe to rerun.
"""

import asyncio
import os
import sys

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import PayloadSchemaType


async def main() -> int:
    url = os.environ["QDRANT_URL"]
    api_key = os.environ["QDRANT_API_KEY"]
    client = AsyncQdrantClient(url=url, api_key=api_key)
    try:
        try:
            await client.create_payload_index(
                collection_name="papers_rag",
                field_name="exercise",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            print("OK: created papers_rag.exercise keyword payload index")
            return 0
        except Exception as exc:
            msg = str(exc).lower()
            if "already" in msg or "exists" in msg or "duplicate" in msg:
                print(
                    f"OK: papers_rag.exercise index already present ({exc.__class__.__name__})"
                )
                return 0
            print(f"FAIL: {exc.__class__.__name__}: {exc}", file=sys.stderr)
            return 1
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
