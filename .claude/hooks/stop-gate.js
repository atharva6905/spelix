#!/usr/bin/env node
// Stop. v2: BLOCKING quality gate (exit 2 prevents Claude stopping; CC caps at 8 consecutive blocks).
// Gate fires ONLY when code files are dirty — casual Q&A sessions are never blocked.
// Checks: ruff (backend, if .py dirty) + tsc (frontend, if .ts/.tsx dirty) + pytest on dirty test files.
const { execSync } = require('node:child_process');
function run(cmd, opts = {}) { return execSync(cmd, { encoding: 'utf8', stdio: 'pipe', timeout: 120000, ...opts }); }
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => {
  if (process.env.HOOK_SMOKE) process.exit(0); // smoke test: skip slow checks
  // Linked worktree: no .venv/node_modules here — checks would fail spuriously and
  // exit-2 would trap the session. Worktree code is gated by the /implement review
  // chain + local checks + CI instead. (Human decision 2026-06-10: skip entirely.)
  if (require('./_lib.js').inLinkedWorktree()) process.exit(0);
  let failures = [];
  try {
    const dirty = run('git status --porcelain').split('\n').filter(Boolean).map((l) => l.slice(3).trim());
    const pyDirty = dirty.filter((f) => f.endsWith('.py'));
    const tsDirty = dirty.filter((f) => f.endsWith('.ts') || f.endsWith('.tsx'));
    if (!pyDirty.length && !tsDirty.length) process.exit(0); // nothing code-dirty: never block

    if (pyDirty.length) {
      try { run('uv run ruff check . --quiet', { cwd: 'backend' }); }
      catch (e) { failures.push('ruff:\n' + (e.stdout || '').slice(0, 1500)); }
      // Scoped pytest: dirty test files only (never the whole 2301-test suite per stop).
      const testFiles = pyDirty
        .filter((f) => /backend[\\/]tests[\\/].*test_.*\.py$/.test(f) || /^tests[\\/].*test_.*\.py$/.test(f))
        .map((f) => f.replace(/^backend[\\/]/, '').replace(/\\/g, '/'))
        .filter((f) => !f.includes('test_pose_extraction')); // Windows hard-crash — CI is the gate
      if (testFiles.length) {
        try { run(`uv run pytest ${testFiles.map((f) => JSON.stringify(f)).join(' ')} -x -q`, { cwd: 'backend' }); }
        catch (e) { failures.push('pytest (changed tests):\n' + (e.stdout || '').slice(0, 2000)); }
      }
    }
    if (tsDirty.length) {
      try { run('npx tsc --noEmit', { cwd: 'frontend' }); }
      catch (e) { failures.push('tsc:\n' + (e.stdout || '').slice(0, 1500)); }
    }
  } catch (e) { process.exit(0); } // gate infrastructure failure must not trap the session
  if (failures.length) {
    process.stderr.write('\u{1F6A7} STOP GATE: fix before finishing —\n\n' + failures.join('\n\n'));
    process.exit(2);
  }
  process.exit(0);
});
