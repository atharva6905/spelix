# spelix-governance-reviewer — memory

(Persisted by the main agent on 2026-06-10 — the reviewer ran read-only and asked for these to be recorded.)

## T0 gate precedents
- **PR #240 (2026-06-10) → PASS.** `.claude/skills/**/SKILL.md` diffs classify as T0 (`.claude/**` category, outside all exclusions).
- Documenting harness tool usage (ExitWorktree / worktree lifecycle) in a skill is procedure docs, not a governance-semantics change — stays T0 as long as tier definitions, self-merge conditions, and reviewer-isolation language are untouched.

## Traps
- "Deploy to Production = skipping" on a PR is expected and correct for a `.claude`-docs-only diff; it satisfies "CI green where applicable" — do not FAIL on it.
- Exact T0 disqualifier list to check file-by-file: `settings.json`, `settings.local.json`, `hooks/**`, `rules/governance.md`, `.mcp.json`, CI deploy steps, any T2 path (models/schemas/alembic/auth/user-facing strings/SRS.md).

## PR #250 (2026-06-10) → PASS — Skill-tool grant precedent
- `.claude/agents/*.md` diffs are T0 (`.claude/**`, outside exclusions). This diff granted the `Skill` tool to three IMPLEMENTER agents (tdd, cv, ai) + added a "nested sub-skill" TDD protocol pointing at `superpowers:test-driven-development`.
- Ruling: granting `Skill` to an *implementer* agent is NOT a gate-bypass. Implementers produce PRs; the merge gate is held by the main agent + this reviewer. `Skill` grants no merge/approval ability and does not touch governance.md tier semantics or self-merge conditions. Stays T0.
- The prose *strengthened* TDD discipline ("Spelix overrides take precedence", FR-ID/backlog gate runs BEFORE the skill, stop-after-3 preserved) — no weakening of any review gate.

## Tool-grant trap (added 2026-06-10)
- An added `tools:` entry (e.g. `Skill`) in an agent `.md` frontmatter is NOT a guardrail-file edit. Agent `.md` files are not in the governance.md meta-safety list (only settings.json / hooks/** / governance.md are). Distinguish "agent gains a capability" from "guardrail file modified": former is in-scope T0; latter is instant T0 FAIL.
- Decisive question for any tool grant: does the new tool create a self-merge / self-approval path? If the agent is an implementer (not the merge gate), the answer is no → stays T0.

## PR #252 (2026-06-10) → PASS — bugfix skill sub-skill rebuild (issue #247)
- Single file `.claude/skills/bugfix/SKILL.md`. T0 (`.claude/**`, outside all exclusions; no T2 paths, no guardrail files).
- Rewrote the bugfix loop to REQUIRE `superpowers:systematic-debugging` (4 binding phases) + `superpowers:test-driven-development` for the fix phase. Same pattern as #250: Spelix overrides take precedence over skill defaults; stop-after-3 backstop preserved (now "Phase 4.5 stop" → emit /implement Step 4 blocker report, "do not try harder").
- Net effect STRENGTHENS discipline (no "just try this", mandatory failing-test-first). No governance-semantics change, no self-merge/approval path created, no SaMD/user-facing strings. Kept test_pose_extraction.py Windows-crash exclusion ("CI is the gate") — consistent with env memory, not a gate weakening.
- Precedent: a skill markdown that ADDS a required `superpowers:` sub-skill and tightens the loop is in-scope T0, same as #250's tool-grant ruling.

## PR #253 (2026-06-10) → PASS — discipline-nesting in /implement + /ship-loop (issue #248)
- Two files: `.claude/skills/implement/SKILL.md` (+15), `.claude/skills/ship-loop/SKILL.md` (+3). T0 (`.claude/**`, both outside exclusions; no T2 paths, no guardrail files, no SaMD/user-facing strings, no secrets). 18 insertions, additive only.
- Nested-sub-skill grants added to existing loops: `superpowers:writing-skills` (gate harness meta-work on .claude/skills|agents), `superpowers:receiving-code-review` (fix-loop: verify findings vs code; refute-with-evidence routes BACK to reviewer — reviewer re-verdict still decides), `superpowers:verification-before-completion` (Step 5 report + ship-loop CI/deploy claims).
- KEY RULING on the fix-loop edit: "findings are claims not orders" does NOT weaken the gate because reviewer authority is explicitly preserved ("the reviewer's re-verdict decides") — implementer cannot unilaterally dismiss a finding. Refute-with-evidence is a round-trip, not a bypass. Watch for the inverse: any future edit that lets the implementer self-dismiss findings WITHOUT reviewer re-verdict would WEAKEN the gate → escalate/FAIL.
- ship-loop CI-claims tightening ("CI green" only after reading check conclusions; "deployed" only after droplet SHA/health output) reinforces self-merge condition #1 + the #211 deploy-CI-false-negative trap. Strengthens, never relaxes.
- Net: every insertion adds a verification obligation; merge gate (main agent + this reviewer), tier semantics, reviewer-isolation, and self-merge conditions all untouched. Same precedent family as #250/#252.

## PR #255 (2026-06-10) → PASS — ship-loop step-8 agent-memory preservation
- Single file `.claude/skills/ship-loop/SKILL.md` (+8, 0 deletions). T0 (`.claude/**`, outside all exclusions; no T2 paths, no guardrail file, no SaMD/user-facing strings, no secrets). Additive only.
- New block is the FIRST sub-bullet of step 8 Cleanup: preserve `.claude/agent-memory/**` BEFORE any ExitWorktree. Root cause it codifies: reviewer/implementer agents inherit the SESSION cwd, so their agent-memory writes land in the TASK WORKTREE; worktree removal would destroy them. Procedure: copy modified/untracked memory files from worktree to same path in main checkout, revert worktree copies (`git checkout -- .claude/agent-memory/` + delete untracked), commit main copies as `docs: <agent> memory from <PR> gate`.
- KEY RULING (the dispatch's flagged concern): does this relax discard_changes / reconcile? NO. The pre-existing rules survive VERBATIM and unchanged — "never pass discard_changes blind", "STOP and reconcile" (Merged branch), "sole sanctioned use of discard_changes" (Closed/abandoned branch). New block runs strictly BEFORE ExitWorktree and only ADDS a preservation obligation. Its targeted revert is scoped to `.claude/agent-memory/` so it does not touch/collide with the unmerged-task-changes reconcile guard.
- Mechanism note: this is the exact process that stamps "Persisted by the main agent" notes atop reviewer MEMORY.md files. Follow-on main-checkout memory commits are themselves T0 docs/`.claude/**` — consistent, no governance issue.
- Same precedent family as #240/#250/#252/#253: additive ship-loop/skill prose that TIGHTENS the loop (here: prevents silent loss of reviewer memory) stays in-scope T0.

## PR for issue #216 (2026-06-12) → PASS — first `tests/**` T0 precedent (FR-BRAIN-16 consent cascade)
- Single NEW file `backend/tests/integration/test_coach_brain_consent_cascade.py` (+391, 0 deletions). T0 via the "test-only additions under `tests/**`" category — distinct from all prior `.claude/**` precedents.
- KEY RULING #1 (the dispatch's flagged trap): a TEST that exercises COACHING-domain repo code is NOT a "coaching prompt change" (T3). T3 "coaching prompt changes" = edits to the LLM coaching prompt text/config. No prompt text, no `config/` thresholds, no LLM instruction in the diff — only DB row-selection assertions. Does not escalate. Watch the inverse: a diff editing the actual coaching prompt/config IS T3 regardless of how small.
- KEY RULING #2: the test does runtime INSERT/UPDATE/DELETE + rollback against existing tables. That is test DATA manipulation, NOT a migration (T3) — no alembic file, no schema DDL in the diff. Does not escalate.
- IMPORTING `app.models.*` / `app.repositories.*` does NOT pull in a T2 path. T2 triggers fire on EDITING files under models/schemas/alembic, not on a test importing them. Confirmed file-by-file: only the test file is in the diff.
- SaMD scan clean: only test-internal strings (`source_consent_withdrawn`, `squat`, `descent`, `cue`, UUID-tagged content). No "injury"/"safety score", and none user-facing anyway.
- General `tests/**` rule learned: test files are T0 even when they exercise auth/coaching/migration-adjacent production code, PROVIDED the diff contains ONLY files under `tests/**` and no production/guardrail/schema file. The DOMAIN the test covers does not tier the diff — the PATHS in the diff do.
