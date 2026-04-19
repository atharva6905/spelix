"""Module-level constants that do NOT vary per environment.

Runtime-configurable values live in ``app.config``; anything that changes
with env (model key, endpoint URL, feature flag) belongs there. Anything
here is a code-level identifier that changes only when the code changes.

D-046 (session 52 follow-up from spelix-auditor M-03 on PR #85) hoisted
HAIKU_MODEL here after it had been duplicated across three call sites
(``app.distillation.cove_brain``, ``app.distillation.extract``,
``app.services.cove``).
"""

from __future__ import annotations

HAIKU_MODEL = "claude-haiku-4-5-20251001"
"""Anthropic Haiku 4.5 snapshot ID used by CoVe (coaching + distillation)
and extractive distillation. Centralised per D-046 / ADR-DISTILL-03."""
