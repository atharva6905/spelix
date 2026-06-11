---
name: feedback_decisions_crosslink
description: decisions.md cross-link rule — superseded ADRs MUST have a back-reference added; "cross-link both ways" is enforced
metadata:
  type: feedback
---

When an ADR supersedes an existing ADR (per git-github.md: "cross-link both ways"), the OLD ADR body MUST receive a non-substantive forward note ("Superseded in part by ADR-X...") even though decisions.md is nominally append-only. The append-only rule carves out supersession cross-links explicitly.

**Why:** git-github.md §File ownership says "if a decision is reversed, write a new ADR that supersedes the old one by ID and cross-link both ways." Append-only applies to "substance" — adding a one-line supersession note is not a substance edit.

**How to apply:** Any time a new ADR's Consequences says "supersedes [ADR-X]", verify that ADR-X's body was also edited to reference the new ADR. Flag CRITICAL if missing.
