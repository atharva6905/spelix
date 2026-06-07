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
  Postgres JSONB queries stay performant. Target: ≤8 KB per payload
  (the ``max_bytes=8192`` default).
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# Compiled once at module load — used by sanitize_error_message.
# Unix absolute paths: leading / followed by at least two path segments
# (word-chars, dots, hyphens), e.g. /tmp/spelix/abc.mp4  /app/foo/bar.py
# The negative lookbehind keeps URL path components intact — a leading /
# preceded by a word char, ':' or another '/' (e.g. the /v1/messages in
# https://api.anthropic.com/v1/messages) is part of a URL, not an fs path.
_UNIX_PATH_RE = re.compile(r"(?<![\w:/])/(?:[\w.\-]+/)+[\w.\-]*")
# Windows absolute paths: drive letter + colon + backslash or forward-slash.
# The lookbehind stops URL schemes from matching as drive letters — the
# trailing "s" of "https://..." would otherwise match [A-Za-z]:[/].
_WIN_PATH_RE = re.compile(r"(?<!\w)[A-Za-z]:[/\\][^\s'\"]+")
# Windows UNC paths: \\server\share\...
_UNC_PATH_RE = re.compile(r"\\\\[\w.\-]+\\[^\s'\"]+")


def sanitize_error_message(message: str) -> str:
    """Replace filesystem paths in *message* with the literal ``<path>``.

    Applied to every ``NodeEvent.error`` value before the trace is
    persisted to ``coaching_results.agent_trace_json`` (ADR-DISTILL-05,
    issue #188).  Non-path text — plain English errors, URLs, bare domain
    names, arithmetic fractions like ``1/2`` — passes through unchanged
    because the Unix pattern requires a leading ``/`` **plus** at least
    two ``word/dot/hyphen`` segments, not preceded by a word char/``:``/``/``.

    Known limitation: path segments containing spaces are only sanitized up
    to the first space (prod stores artifacts at ``/tmp/spelix/{uuid}.mp4``
    — no spaces — so this cannot leak on the droplet).
    """
    message = _UNIX_PATH_RE.sub("<path>", message)
    message = _WIN_PATH_RE.sub("<path>", message)
    message = _UNC_PATH_RE.sub("<path>", message)
    return message


def sanitize_trace_errors(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy of *events* with any string ``error`` values sanitized.

    Shared by both ``agent_trace_json`` write paths: the LangGraph path
    (via ``serialize_trace_for_storage``) and the imperative Phase 2 path
    (``cove_iterations`` in the worker). Input dicts are not mutated.
    """
    cleaned: list[dict[str, Any]] = []
    for ev in events:
        if isinstance(ev, dict) and isinstance(ev.get("error"), str):
            ev = {**ev, "error": sanitize_error_message(ev["error"])}
        cleaned.append(ev)
    return cleaned


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
    (filterable chips), ``metadata`` (structured fields), and ``run_id``
    (a fresh UUID4 used as the LangSmith root-run id). When LangSmith is
    not enabled, the dict is still valid as LangGraph runtime config —
    the tracing fields are simply ignored.
    """
    run_id = uuid.uuid4()
    return {
        "run_id": run_id,
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

    # Sanitize error strings before any size logic — choke point for the
    # graph path's agent_trace_json JSONB write (issue #188, ADR-DISTILL-05:
    # never persist raw str(exc) to admin-visible columns).
    result = sanitize_trace_errors([dict(ev) for ev in trace])
    if _size(result) <= max_bytes:
        return result

    # Truncate long string fields until it fits.
    # tool_calls_invoked is an optional list of internal tool-name strings —
    # no PII, no paths. Listed as essential so adaptive-mode reasoner data
    # survives the hard-cap path (FR-AICP-19 / FR-RESL-07).
    ESSENTIAL = {"node", "duration_ms", "error", "started_at", "output_keys", "tool_calls_invoked"}
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
