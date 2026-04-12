"""RetrievalGuard — minimum retrieval quality gate before coaching generation.

Implements FR-AICP-09 (P2-012): if fewer than 3 documents are retrieved,
emit a coaching_unavailable sentinel rather than generating low-quality output.

Design notes:
- Pure static method, no async, no I/O — safe to call inline in any context.
- The sentinel string is a module-level constant so callers can import and
  compare without magic strings.
- RetrievalGuardResult is a dataclass (not Pydantic) — it never crosses an
  API boundary; keeping it lightweight avoids validation overhead.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.rag import RetrievedContext

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

MIN_DOCS_FOR_GENERATION: int = 3
_COACHING_UNAVAILABLE_SENTINEL: str = "coaching_unavailable"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class RetrievalGuardResult:
    """Outcome of a RetrievalGuard.check() call.

    Attributes
    ----------
    passed:
        True when the retrieval set meets the minimum threshold.
    reason:
        Human-readable explanation populated only when passed=False.
    sentinel:
        ``"coaching_unavailable"`` when passed=False, None otherwise.
        Callers should check this value to decide whether to suppress
        coaching generation.
    """

    passed: bool
    reason: str | None = field(default=None)
    sentinel: str | None = field(default=None)


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------


class RetrievalGuard:
    """Ensures minimum retrieval quality before coaching generation (FR-AICP-09).

    If fewer than 3 documents are retrieved, emits a coaching_unavailable
    sentinel rather than generating low-quality output.
    """

    @staticmethod
    def check(results: list[RetrievedContext]) -> RetrievalGuardResult:
        """Check whether retrieval results meet the minimum threshold.

        Parameters
        ----------
        results:
            The list of retrieved contexts returned by hybrid_search or
            dense_search.

        Returns
        -------
        RetrievalGuardResult
            ``passed=True`` when ``len(results) >= MIN_DOCS_FOR_GENERATION``.
            ``passed=False`` with ``sentinel="coaching_unavailable"`` otherwise.
        """
        count = len(results)
        if count >= MIN_DOCS_FOR_GENERATION:
            return RetrievalGuardResult(passed=True)

        return RetrievalGuardResult(
            passed=False,
            reason=(
                f"Retrieval returned {count} document(s); "
                f"minimum {MIN_DOCS_FOR_GENERATION} required for coaching generation."
            ),
            sentinel=_COACHING_UNAVAILABLE_SENTINEL,
        )
