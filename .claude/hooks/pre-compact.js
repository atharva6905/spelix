#!/usr/bin/env node
// PreCompact. Appends a mini-handoff snapshot to .claude/handoff.md before compaction.
const { execSync } = require('node:child_process');
const { appendFileSync } = require('node:fs');
function safe(cmd) { try { return execSync(cmd, { encoding: 'utf8', timeout: 8000 }).trim(); } catch (e) { return '(unavailable)'; } }
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => {
  if (process.env.HOOK_SMOKE) process.exit(0); // smoke test: skip side effects
  try {
    const { resolveRoot, inLinkedWorktree } = require('./_lib.js');
    const path = require('node:path');
    const stamp = new Date().toISOString();
    const lines = [``, `## Auto mini-handoff (pre-compact) — ${stamp}`];
    if (inLinkedWorktree()) lines.push(`worktree: ${process.cwd()}`);
    lines.push(
      `branch: ${safe('git branch --show-current')}`,
      `dirty files:`, safe('git status --porcelain').split('\n').slice(0, 30).join('\n') || '(clean)',
      `recent commits:`, safe('git log --oneline -5'), ``,
    );
    appendFileSync(path.join(resolveRoot(), '.claude', 'handoff.md'), lines.join('\n'));
  } catch (e) { /* never block compaction */ }
  process.exit(0);
});
