# Issue #239 — in-session APPROVAL GATE for T1/T2 merges (reviewed 2026-06-10) → PASS

Type: project.

**What changed (markdown-only):** governance.md T1 paragraph rewritten + T2 paragraph appended; ship-loop SKILL.md step 7 T1+ terminal "label needs-human" replaced with an APPROVAL GATE, step 8 made per-outcome cleanup; decisions.md ADR-HARNESS-02 + index row + bidirectional cross-link to ADR-HARNESS-01.

**Why:** old terminal `needs-human` added a detour without rigor when the human was already in-session (#227/#228/#233 were inline-authorized) and left worktrees parked. Deliberate ADR-backed loosening of T1 "Never merge," not an accident.

**Control-integrity invariants to re-check on any future governance/ship-loop edit:**
- Merge precondition = "explicit in-session human approval, recorded as a PR comment BEFORE merging" — stated in BOTH governance.md (T1) AND the skill (step 7.3). Dropping it from either file = CRITICAL.
- Every non-approve branch is fail-safe (no merge): no-response/headless/autonomous//groom → needs-human+STOP; defer → needs-human; skip → leave PR open; close → close without merge.
- Override "Merge anyway" is a HUMAN AskUserQuestion choice, never agent-initiated; on selection the agent must comment "(override: …what was overridden)" before merge.
- T2 gate satisfied ONLY WITH per-file diff summary + verbatim spelix-security-reviewer verdict (governance.md: "Absent that, T2 stays needs-human"). Making the verbatim verdict optional in either file weakens T2 → escalate.
- Audit timing "comment BEFORE merge" agrees in both files; no documented merge-before-comment window.

**Byte-unchanged (verified at #239):** T0 4-item self-merge conditions (incl. reviewer-isolation clause), T2 path list (settings.json, hooks/**, governance.md, .mcp.json, CI deploy, docs/SRS.md), T3 requirements, Meta-safety — all intact outside the specified T1/T2 edits. governance.md remains self-T2 by Meta-safety.

**Standing note (NOT a finding):** governance.md is a documentary control, not a programmatic gate; "recorded before merge" is post-hoc auditable but not tool-enforced. Pre-exists #239. (Reviewer-environment note: agent worktrees are branch snapshots — memory files committed to main after the worktree's base commit are invisible there; check the MAIN checkout's agent-memory before declaring a memory file missing.)

**SaMD:** none — internal process docs only.
