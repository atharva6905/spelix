#!/usr/bin/env node
// SessionStart. Injects live environment state as additionalContext + reloads skills.
// Every probe is timeout-guarded; failures degrade to a SKIPPED line, never an error.
const { execSync } = require('node:child_process');
const { readFileSync, existsSync } = require('node:fs');
const path = require('node:path');
const { resolveRoot, inLinkedWorktree } = require('./_lib.js');
function probe(label, fn) {
  try { return `${label}:\n${fn().toString().trim()}`; }
  catch (e) { return `${label}: SKIPPED (${e.message.split('\n')[0].slice(0, 80)})`; }
}
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => {
  const parts = [
    probe('git', () => execSync('git status -sb', { timeout: 8000 })),
    probe('last commits', () => execSync('git log --oneline -3', { timeout: 8000 })),
    probe('worktrees', () => execSync('git worktree list', { timeout: 8000 })),
    probe('streaq queue depth', () =>
      execSync('docker compose exec -T redis redis-cli llen streaq:queue', { timeout: 6000 })),
    probe('session cwd', () => inLinkedWorktree()
      ? `LINKED WORKTREE: ${process.cwd()} (main checkout: ${resolveRoot()})`
      : process.cwd()),
    probe('handoff (head)', () => {
      const handoff = path.join(resolveRoot(), '.claude', 'handoff.md');
      if (!existsSync(handoff)) return '(no handoff file)';
      return readFileSync(handoff, 'utf8').split('\n').slice(0, 20).join('\n');
    }),
  ];
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'SessionStart',
      additionalContext: `## Live environment (SessionStart hook)\n${parts.join('\n\n')}`,
    },
    reloadSkills: true,
  }));
  process.exit(0);
});
