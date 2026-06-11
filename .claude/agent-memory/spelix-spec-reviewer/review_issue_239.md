---
name: review_issue_239
description: Spec review of issue #239 — in-session approval gate (ship-loop/governance/ADR); PASS after fix iteration 1, 2026-06-10
metadata:
  type: project
---

## Reviewed: issue #239 (approval gate, 2026-06-10) → PASS (after 1 fix iteration)

Branch: docs/issue-239-approval-gate. Commits: 4065693, f02b932, 0582288, 112f58d. Tier T2.

**Files touched:** .claude/skills/ship-loop/SKILL.md, .claude/rules/governance.md, decisions.md

**Initial FAIL findings (both fixed in commit 112f58d):**
1. CRITICAL: ADR-HARNESS-01 body missing forward reference to ADR-HARNESS-02. Fixed by appending "Superseded in part by ADR-HARNESS-02 (T1/T2 merge terminal behavior, 2026-06-10)." to Consequences.
2. MEDIUM: `**Status**: Accepted 2026-06-10.` line in ADR-HARNESS-02 body — format mismatch with existing ADRs (status belongs only in the index table). Fixed by removing the line.

**Pattern confirmed:** "cross-link both ways" in git-github.md is a hard requirement. When a new ADR's Consequences says "supersedes [ADR-X]", ADR-X's body must also be edited with a forward reference. See [[feedback_decisions_crosslink]].

**All Task 7/8/9 requirements verified IMPLEMENTED:**
- SKILL.md step 7 T1+ approval gate (6-sub-step block, all options, headless fallback)
- governance.md T1 paragraph: recorded approval, no-response/headless/defer → needs-human+STOP
- governance.md T2 new paragraph: per-file diff + verbatim security verdict conditions
- T0/T3/Meta-safety sections semantically unchanged
- ADR-HARNESS-02: Decision Index row + body (Context/Decision/Consequences)
- Bidirectional cross-link ADR-HARNESS-01 ↔ ADR-HARNESS-02 (after fix)
- No Status field in ADR body (after fix)
- No files touched outside the three specified
