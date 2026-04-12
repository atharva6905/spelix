"""One-shot Qdrant Cloud provisioning script.

Reads QDRANT_URL and QDRANT_API_KEY from backend/.env (or environment),
instantiates QdrantClientWrapper, and calls ensure_collections().

This is a manual provisioning tool — run once against the live cluster after
the first deploy.  It is idempotent: safe to re-run if a collection already
exists.

Usage (from backend/ directory):
    uv run python scripts/provision_qdrant.py

Environment:
    QDRANT_URL      — e.g. https://<cluster-id>.eu-central.aws.cloud.qdrant.io:6333
    QDRANT_API_KEY  — Qdrant Cloud API key (in backend/.env)

DO NOT add to tests — tests always mock the Qdrant client (ADR-032).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env from backend/ directory so this script works from the scripts/
# subdirectory without setting env vars manually.
# ---------------------------------------------------------------------------

_ENV_PATH = Path(__file__).parent.parent / ".env"
if _ENV_PATH.exists():
    from dotenv import load_dotenv  # type: ignore[import-untyped]

    load_dotenv(_ENV_PATH)
    print(f"[provision] Loaded env from {_ENV_PATH}")
else:
    print(f"[provision] No .env found at {_ENV_PATH} — using process environment")


async def main() -> None:
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")

    if not qdrant_url:
        print("[provision] ERROR: QDRANT_URL is not set. Cannot provision.", file=sys.stderr)
        sys.exit(1)
    if not qdrant_api_key:
        print("[provision] ERROR: QDRANT_API_KEY is not set. Cannot provision.", file=sys.stderr)
        sys.exit(1)

    print(f"[provision] Connecting to Qdrant at {qdrant_url}")

    # Import here so the script fails fast on missing qdrant-client.
    from app.services.qdrant import get_qdrant_client

    # Reset the module-level cache so we always get a fresh client here.
    import app.services.qdrant as qdrant_mod

    qdrant_mod._qdrant_client_cache = None
    qdrant_mod._qdrant_client_cache_initialized = False

    wrapper = await get_qdrant_client()
    if wrapper is None:
        print("[provision] ERROR: get_qdrant_client() returned None — check QDRANT_URL", file=sys.stderr)
        sys.exit(1)

    # Ping first to confirm connectivity.
    print("[provision] Pinging cluster…")
    ok = await wrapper.ping()
    if not ok:
        print("[provision] ERROR: ping failed — cluster unreachable or API key invalid", file=sys.stderr)
        sys.exit(1)
    print("[provision] Ping OK")

    # Provision both collections.
    print("[provision] Ensuring collections…")
    await wrapper.ensure_collections()

    # Report final state.
    from qdrant_client import AsyncQdrantClient

    inner: AsyncQdrantClient = wrapper._client
    collections = await inner.get_collections()
    existing = {c.name for c in collections.collections}

    print()
    print("[provision] Collections now in cluster:")
    for name in sorted(existing):
        info = await inner.get_collection(name)
        vec_cfg = info.config.params.vectors
        sparse_cfg = info.config.params.sparse_vectors
        size = vec_cfg.size if hasattr(vec_cfg, "size") else "?"
        print(f"  {name}:")
        print(f"    dense:  size={size}, distance={vec_cfg.distance if hasattr(vec_cfg, 'distance') else '?'}")
        print(f"    sparse: {list(sparse_cfg.keys()) if sparse_cfg else 'none'}")

    print()
    print("[provision] Done.")


if __name__ == "__main__":
    asyncio.run(main())
