"""LangSmith tracing helpers (FR-AICP-20).

The LangGraph compiled graph automatically emits traces to LangSmith
when ``LANGCHAIN_TRACING_V2=true`` and ``LANGCHAIN_API_KEY`` are set in
env — no per-call wiring is needed. This module adds:

- ``langsmith_enabled()``: cheap env probe.
- ``run_config_for_analysis()``: builds ``config`` dict for
  ``graph.ainvoke(state, config=...)`` with ``run_name``, ``tags``, and
  ``metadata`` so runs are discoverable in the LangSmith UI.
- ``serialize_trace_for_storage()``: truncates overly-large trace
  payloads before writing to ``coaching_results.agent_trace_json`` so
  Postgres JSONB queries stay performant. Target: ≤4 KB per entry.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def langsmith_enabled() -> bool:
    """Return True iff LangSmith tracing is both flagged on and keyed."""
    if os.environ.get("LANGCHAIN_TRACING_V2", "").lower() not in ("1", "true", "yes"):
        return False
    if not os.environ.get("LANGCHAIN_API_KEY"):
        return False
    return True


def run_config_for_analysis(
    *,
    analysis_id: str,
    user_id: str,
    mode: str,
) -> dict[str, Any]:
    """Build the ``config`` dict passed to ``graph.ainvoke``.

    Populates ``run_name`` (shown in the LangSmith run list), ``tags``
    (filterable chips), and ``metadata`` (structured fields). When
    LangSmith is not enabled, the dict is still valid as LangGraph
    runtime config — the tracing fields are simply ignored.
    """
    return {
        "run_name": f"coaching_analysis_{analysis_id}",
        "tags": [
            f"analysis_id:{analysis_id}",
            f"user_id:{user_id}",
            f"mode:{mode}",
            "phase:3",
            "task:coaching",
        ],
        "metadata": {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "mode": mode,
        },
    }


def serialize_trace_for_storage(
    trace: list[dict[str, Any]],
    *,
    max_bytes: int = 8192,
) -> list[dict[str, Any]]:
    """Return a JSONB-safe trace list capped at ``max_bytes`` total.

    When the trace would exceed ``max_bytes``, event fields larger than
    1 KB are progressively truncated (longest-first) until the payload
    fits. Essential fields (``node``, ``duration_ms``, ``error``,
    ``started_at``) are preserved verbatim.
    """

    def _size(obj: Any) -> int:
        return len(json.dumps(obj).encode("utf-8"))

    result = [dict(ev) for ev in trace]
    if _size(result) <= max_bytes:
        return result

    # Truncate long string fields until it fits.
    ESSENTIAL = {"node", "duration_ms", "error", "started_at", "output_keys"}
    for ev in result:
        for key in list(ev.keys()):
            if key in ESSENTIAL:
                continue
            val = ev[key]
            if isinstance(val, str) and len(val) > 1024:
                ev[key] = val[:1024] + "…[truncated]"
            elif isinstance(val, (list, dict)):
                serialized = json.dumps(val)
                if len(serialized) > 1024:
                    ev[key] = serialized[:1024] + "…[truncated]"
        if _size(result) <= max_bytes:
            return result

    # Hard cap: drop non-essential fields entirely.
    for ev in result:
        for key in list(ev.keys()):
            if key not in ESSENTIAL:
                del ev[key]
    return result
