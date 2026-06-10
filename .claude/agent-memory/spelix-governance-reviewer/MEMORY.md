# spelix-governance-reviewer — memory

(Persisted by the main agent on 2026-06-10 — the reviewer ran read-only and asked for these to be recorded.)

## T0 gate precedents
- **PR #240 (2026-06-10) → PASS.** `.claude/skills/**/SKILL.md` diffs classify as T0 (`.claude/**` category, outside all exclusions).
- Documenting harness tool usage (ExitWorktree / worktree lifecycle) in a skill is procedure docs, not a governance-semantics change — stays T0 as long as tier definitions, self-merge conditions, and reviewer-isolation language are untouched.

## Traps
- "Deploy to Production = skipping" on a PR is expected and correct for a `.claude`-docs-only diff; it satisfies "CI green where applicable" — do not FAIL on it.
- Exact T0 disqualifier list to check file-by-file: `settings.json`, `settings.local.json`, `hooks/**`, `rules/governance.md`, `.mcp.json`, CI deploy steps, any T2 path (models/schemas/alembic/auth/user-facing strings/SRS.md).
