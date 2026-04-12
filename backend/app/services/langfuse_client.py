"""langfuse_client.py — Langfuse observability singleton factory.

Implements P2-034 (FR-BRAIN-13).

Architecture:
- Two-flag singleton pattern (ADR-032): ``_langfuse_client_cache_initialized``
  + ``_langfuse_client_cache`` so that a None result (missing env vars in
  dev/test/CI) is cached and never retried.
- ``langfuse.Langfuse`` is imported *inside* ``get_langfuse_client`` so that
  ``patch("langfuse.Langfuse")`` intercepts the constructor at call time
  (same ADR-032 source-patch pattern used by qdrant.py).
- All callers must guard on ``None`` — Langfuse is an optional observability
  layer and must never fail the pipeline.

Usage::

    from app.services.langfuse_client import get_langfuse_client

    lf = await get_langfuse_client()
    if lf is not None:
        try:
            lf.trace(name="analysis", ...)
        except Exception:
            pass  # always best-effort
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level two-flag cache (ADR-032)
# ---------------------------------------------------------------------------

_langfuse_client_cache: Any | None = None
_langfuse_client_cache_initialized: bool = False


async def get_langfuse_client() -> Any | None:
    """Build and cache a ``langfuse.Langfuse`` client.

    Reads ``LANGFUSE_PUBLIC_KEY``, ``LANGFUSE_SECRET_KEY``, and optionally
    ``LANGFUSE_HOST`` from environment variables.  Returns ``None`` when
    either key is absent — callers must guard on None.

    The constructed client is cached at module level.  None is also cached
    (two-flag pattern) so missing-key dev environments don't retry on every
    call.

    ``langfuse.Langfuse`` is imported inside this function body so that tests
    can patch it via ``patch("langfuse.Langfuse")`` and intercept the
    constructor call at runtime (ADR-032 source-patch pattern).
    """
    global _langfuse_client_cache, _langfuse_client_cache_initialized

    if _langfuse_client_cache_initialized:
        return _langfuse_client_cache

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        logger.debug(
            "get_langfuse_client: LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY not set "
            "— Langfuse observability disabled"
        )
        _langfuse_client_cache = None
        _langfuse_client_cache_initialized = True
        return None

    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

    try:
        # Deferred import so patch("langfuse.Langfuse") intercepts the
        # constructor call at test time (ADR-032).
        import langfuse as _langfuse_mod

        _langfuse_client_cache = _langfuse_mod.Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        logger.info("get_langfuse_client: Langfuse client initialised (host=%s)", host)
    except Exception as exc:
        logger.warning(
            "get_langfuse_client: failed to construct Langfuse client: %s — "
            "observability disabled",
            exc,
        )
        _langfuse_client_cache = None

    _langfuse_client_cache_initialized = True
    return _langfuse_client_cache
