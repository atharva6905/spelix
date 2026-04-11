"""
Analysis status transition guard (SRS Section 5.2a).

Enforces the valid state machine for analysis records. All transitions must
pass through `transition()` — invalid transitions are defects per CLAUDE.md.

Valid statuses: queued, quality_gate_pending, quality_gate_rejected,
                processing, coaching, completed, failed
"""

from __future__ import annotations

# All 7 recognised status values (VARCHAR(30) CHECK constraint in migration 001)
VALID_STATUSES: frozenset[str] = frozenset(
    {
        "queued",
        "quality_gate_pending",
        "quality_gate_rejected",
        "processing",
        "coaching",
        "completed",
        "failed",
    }
)

# Transition table per SRS Section 5.2a.
# Key: current status (None = new row / no prior status).
# Value: set of valid target statuses (empty = terminal state).
#
# Note on "→ failed" edges: operational failures (missing config, OOM,
# ARQ crash, Anthropic 401, MediaPipe model download failure) can fire
# at ANY phase of the worker pipeline, including BEFORE the worker has
# transitioned the row out of ``queued`` or ``quality_gate_pending``.
# The error handler in ``analysis_worker.process_analysis`` MUST be able
# to mark the row as ``failed`` regardless of where in the pipeline the
# crash happened — otherwise an early-pipeline crash leaves the row
# orphaned at its starting status forever (regression: thresholds_v1.json
# missing in container caused exactly this in Phase 1 prod). The
# distinction with ``quality_gate_rejected`` is preserved: that state is
# reserved for analyses where the actual quality-gate predicate refused
# the user's video content, NOT for infrastructure failures.
_TRANSITIONS: dict[str | None, frozenset[str]] = {
    None: frozenset({"queued"}),
    "queued": frozenset({"quality_gate_pending", "failed"}),
    "quality_gate_pending": frozenset({"quality_gate_rejected", "processing", "failed"}),
    "processing": frozenset({"coaching", "failed"}),
    "coaching": frozenset({"completed", "failed"}),
    # failed → queued allowed only when retry_count < 3 (checked at runtime)
    "failed": frozenset({"queued"}),
    # Terminal states: no valid outgoing edges
    "quality_gate_rejected": frozenset(),
    "completed": frozenset(),
}


class InvalidTransition(Exception):
    """Raised when an analysis status transition is not permitted."""


def transition(current: str | None, target: str, retry_count: int = 0) -> str:
    """Validate and return ``target`` if the transition is legal.

    Args:
        current: The current status of the analysis, or ``None`` for a new row.
        target: The desired next status.
        retry_count: Number of times this analysis has been retried (default 0).
                     Only relevant for ``failed → queued`` to enforce the
                     maximum retry limit of 3.

    Returns:
        ``target`` unchanged — callers can use the return value directly when
        updating the row, e.g. ``analysis.status = transition(analysis.status, "queued")``.

    Raises:
        InvalidTransition: If the transition is not permitted by SRS Section 5.2a,
                           including terminal-state attempts and exhausted retries.
    """
    # Validate target is a known status value
    if target not in VALID_STATUSES:
        raise InvalidTransition(
            f"Unknown target status '{target}': must be one of {sorted(VALID_STATUSES)}"
        )

    # Validate current is None or a known status value
    if current is not None and current not in VALID_STATUSES:
        raise InvalidTransition(
            f"Unknown current status '{current}': must be None or one of {sorted(VALID_STATUSES)}"
        )

    allowed = _TRANSITIONS.get(current)

    # current not in table at all (shouldn't happen after validation above, but be safe)
    if allowed is None:
        raise InvalidTransition(
            f"No transition table entry for current status '{current}' → '{target}'"
        )

    # Terminal state check (empty allowed set)
    if not allowed:
        raise InvalidTransition(
            f"Status '{current}' is terminal — transition to '{target}' is not permitted"
        )

    if target not in allowed:
        raise InvalidTransition(
            f"Transition from '{current}' to '{target}' is not permitted "
            f"(allowed targets: {sorted(allowed)})"
        )

    # Special case: failed → queued is only valid when retry_count < 3
    if current == "failed" and target == "queued" and retry_count >= 3:
        raise InvalidTransition(
            f"Transition from 'failed' to 'queued' is not permitted: "
            f"retry_count={retry_count} has reached the maximum of 3"
        )

    return target
