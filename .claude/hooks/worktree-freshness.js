#!/usr/bin/env node
// PreToolUse(Bash). Warns when 'git worktree add' is not branching from latest origin/main.
// FIX 2026-06-06: previous version read $CC_TOOL_INPUT which does not exist — hooks get stdin JSON.
const { execSync } = require('node:child_process');
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => {
  try {
    const j = JSON.parse(d);
    const c = j.tool_input?.command || '';
    if (c.includes('git worktree add')) {
      try {
        execSync('git fetch origin main', { stdio: 'pipe', timeout: 20000 });
        execSync('git merge-base --is-ancestor origin/main HEAD', { stdio: 'pipe', timeout: 10000 });
      } catch (e) {
        process.stderr.write('\n\u{26A0}\u{FE0F}  WARNING: not branching from latest origin/main\n');
      }
    }
  } catch (e) { /* ignore */ }
  process.exit(0);
});
