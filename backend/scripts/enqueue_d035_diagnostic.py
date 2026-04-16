"""Enqueue a D-035 pose-extraction diagnostic run.

Usage (run inside the worker container):

    docker exec spelix-worker /app/.venv/bin/python \\
        /app/scripts/enqueue_d035_diagnostic.py /tmp/bench.mov

Then tail the worker log for the result:

    docker logs spelix-worker --tail 500 | grep D035_DIAG

The enqueue side requires `async with worker:` per streaq 6.4.0 — entering
the context manager is what spins up the Redis publisher that `.enqueue()`
writes to.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


async def main(video_path: str) -> None:
    from app.workers.streaq_worker import pose_extraction_diagnostic, worker

    async with worker:
        await pose_extraction_diagnostic.enqueue(video_path)
    print(f"[D035_DIAG] enqueued diagnostic for {video_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: enqueue_d035_diagnostic.py <video_path>", file=sys.stderr)
        sys.exit(2)
    p = sys.argv[1]
    if not Path(p).exists():
        print(f"error: {p} does not exist on this container", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(p))
