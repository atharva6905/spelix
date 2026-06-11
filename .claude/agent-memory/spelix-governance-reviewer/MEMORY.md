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
