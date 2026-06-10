#!/usr/bin/env node
// Smoke tests for .claude/hooks/*.js — pipes fixture stdin JSON, asserts exit codes.
// Run: node .claude/hooks/smoke-test.mjs   (exit 0 = all pass, 1 = failures)
// Worktree-mode cases run hooks from an ephemeral linked worktree to prove side
// effects (handoff writes) anchor to the MAIN checkout and gates skip correctly.
import { execSync, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = process.cwd();
const HOOKS = path.join(ROOT, '.claude', 'hooks');
const PID = process.pid;
const WT = path.join(ROOT, '.claude', 'worktrees', `smoke-${PID}`);
const BRANCH = `smoke/hooks-${PID}`;
const FIX = path.join(os.tmpdir(), `spelix-hook-fix-${PID}`);
const ROOT_HANDOFF = path.join(ROOT, '.claude', 'handoff.md');

// Fixtures: ephemeral linked worktree with a dirty .py + temp dir for the
// CLAUDE_PROJECT_DIR fallback path. Snapshot ROOT handoff.md for restore.
execSync(`git worktree add "${WT}" -b ${BRANCH} HEAD`, { cwd: ROOT, stdio: 'pipe', encoding: 'utf8' });
writeFileSync(path.join(WT, 'backend', '_smoke_dirty.py'), 'x = 1\n');
mkdirSync(path.join(FIX, '.claude'), { recursive: true });
const HANDOFF_SNAPSHOT = existsSync(ROOT_HANDOFF) ? readFileSync(ROOT_HANDOFF, 'utf8') : null;

function handoffAnchoredToRoot() {
  const before = HANDOFF_SNAPSHOT === null ? 0 : HANDOFF_SNAPSHOT.length;
  const after = existsSync(ROOT_HANDOFF) ? readFileSync(ROOT_HANDOFF, 'utf8').length : 0;
  if (after <= before) throw new Error('ROOT .claude/handoff.md did not grow');
  if (existsSync(path.join(WT, '.claude', 'handoff.md'))) throw new Error('worktree .claude/handoff.md was created');
}
function handoffInFixture() {
  if (!existsSync(path.join(FIX, '.claude', 'handoff.md'))) throw new Error('CLAUDE_PROJECT_DIR fallback did not write <FIX>/.claude/handoff.md');
}

const CASES = [
  // [script, stdinJSON, expectedExit, mustMatchStream, regex, opts]
  // opts: { cwd, env, noSmoke, timeoutMs, after }
  ['safety-blocklist.js', { tool_input: { command: 'rm -rf /' } }, 2, 'stderr', /BLOCKED/],
  ['safety-blocklist.js', { tool_input: { command: 'git push origin main' } }, 2, 'stderr', /BLOCKED/],
  ['safety-blocklist.js', { tool_input: { command: 'ls -la' } }, 0, null, null],
  ['safety-blocklist.js', 'not-json-at-all', 0, null, null], // malformed input must not block
  ['safety-caution.js', { tool_input: { command: 'git reset HEAD~1' } }, 0, 'stderr', /CAUTION/],
  ['safety-caution.js', { tool_input: { command: 'echo hi' } }, 0, null, null],
  ['secret-scan.js', { tool_input: { command: 'echo hi' } }, 0, null, null],
  ['worktree-freshness.js', { tool_input: { command: 'echo hi' } }, 0, null, null],
  ['graphify-hint.js', { tool_input: { command: 'echo hi' } }, 0, null, null],
  ['post-edit-lint.js', { tool_input: { file_path: 'README.md' } }, 0, null, null],
  ['session-start.js', {}, 0, 'stdout', /hookSpecificOutput/],
  ['session-end.js', {}, 0, null, null],
  ['pre-compact.js', {}, 0, null, null],
  ['stop-gate.js', {}, 0, null, null],
  // Worktree-mode: stop-gate must skip entirely in a linked worktree (no .venv there —
  // without the skip, the dirty .py makes it attempt `uv run ruff`, slow/fail).
  ['stop-gate.js', {}, 0, null, null, { cwd: WT, noSmoke: true, timeoutMs: 20000 }],
  // Worktree-mode: pre-compact must append to the MAIN checkout's handoff.md.
  ['pre-compact.js', {}, 0, null, null, { cwd: WT, noSmoke: true, after: handoffAnchoredToRoot }],
  // Non-repo cwd: resolveRoot falls back to CLAUDE_PROJECT_DIR.
  ['pre-compact.js', {}, 0, null, null, { cwd: os.tmpdir(), noSmoke: true, env: { CLAUDE_PROJECT_DIR: FIX }, after: handoffInFixture }],
];

let failures = 0;
try {
  for (const [script, input, wantExit, stream, re, opts = {}] of CASES) {
    const scriptPath = path.join(HOOKS, script);
    const tag = opts.cwd ? ' [worktree-mode]' : '';
    if (!existsSync(scriptPath)) { console.error(`FAIL ${script}${tag}: file missing`); failures++; continue; }
    const stdin = typeof input === 'string' ? input : JSON.stringify(input);
    const env = { ...process.env, HOOK_SMOKE: '1', ...(opts.env || {}) };
    if (opts.noSmoke) delete env.HOOK_SMOKE; // scripts with side effects (handoff writes, slow checks) short-circuit on HOOK_SMOKE
    const r = spawnSync('node', [scriptPath], {
      input: stdin, encoding: 'utf8', timeout: opts.timeoutMs ?? 180000,
      cwd: opts.cwd ?? ROOT, env,
    });
    const exit = r.status ?? -1;
    if (exit !== wantExit) { console.error(`FAIL ${script}${tag} [${stdin.slice(0, 40)}]: exit ${exit}, want ${wantExit}`); failures++; continue; }
    if (re && !re.test(r[stream] || '')) { console.error(`FAIL ${script}${tag}: ${stream} did not match ${re}`); failures++; continue; }
    if (opts.after) {
      try { opts.after(); }
      catch (e) { console.error(`FAIL ${script}${tag}: ${e.message}`); failures++; continue; }
    }
    console.log(`PASS ${script}${tag} [${stdin.slice(0, 40)}]`);
  }
} finally {
  try { if (HANDOFF_SNAPSHOT !== null) writeFileSync(ROOT_HANDOFF, HANDOFF_SNAPSHOT); } catch (e) { /* best-effort */ }
  try { rmSync(FIX, { recursive: true, force: true }); } catch (e) { /* best-effort */ }
  try { execSync(`git worktree remove --force "${WT}"`, { cwd: ROOT, stdio: 'pipe' }); } catch (e) { console.error(`cleanup: worktree remove failed (${e.message.split('\n')[0]})`); }
  try { execSync(`git branch -D ${BRANCH}`, { cwd: ROOT, stdio: 'pipe' }); } catch (e) { console.error(`cleanup: branch delete failed (${e.message.split('\n')[0]})`); }
}
console.log(failures ? `\n${failures} failure(s)` : '\nAll smoke tests passed');
process.exit(failures ? 1 : 0);
