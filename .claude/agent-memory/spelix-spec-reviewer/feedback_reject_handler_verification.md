---
name: feedback-reject-handler-verification
description: Implementer may claim no reject handler exists — always verify by grepping for all reviewPaper call sites before accepting the claim
metadata:
  type: feedback
---

When a task references both `handleApprovePaper` and `handleRejectPaper`, always grep the actual file for ALL `reviewPaper` call sites to verify the implementer's claim about which handlers exist.

**Why:** Issue #260 referenced `handleRejectPaper` in the task, but the implementer reported only `handleApprovePaper` existed. Grepping confirmed only one `reviewPaper` call site (`handleApprovePaper`, line 446) — the reject handler was never present in this code. Accepting this claim without verification would be a review gap.

**How to apply:** Before concluding "reject handler covered/not covered", always grep for `reviewPaper` calls in the target file, not just search for handler names.
