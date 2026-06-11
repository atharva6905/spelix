#!/usr/bin/env node
// Smoke tests for .claude/hooks/*.js — pipes fixture stdin JSON, asserts exit codes.
// Run: node .claude/hooks/smoke-test.mjs   (exit 0 = all pass, 1 = failures)
// Worktree-mode cases run hooks from an ephemeral linked worktree to prove side
// effects (handoff writes) anchor to the MAIN checkout and gates skip correctly.
// Correct from any cwd: handoff snapshot/assert/restore anchor to resolveRoot().
import { execSync, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';

const ROOT = process.cwd();
const HOOKS = path.join(ROOT, '.claude', 'hooks');
const require = createRequire(import.meta.url);
const { resolveRoot, inLinkedWorktree } = require(path.join(HOOKS, '_lib.js'));
const MAIN = resolveRoot();
const MAIN_HANDOFF = path.join(MAIN, '.claude', 'handoff.md');
const PID = process.pid;
const WT = path.join(ROOT, '.claude', 'worktrees', `smoke-${PID}`);
const BRANCH = `smoke/hooks-${PID}`;
const FIX = path.join(os.tmpdir(), `spelix-hook-fix-${PID}`);

if (inLinkedWorktree()) console.log(`note: running from a linked worktree (${ROOT}); handoff assertions anchor to main checkout ${MAIN}`);

let HANDOFF_SNAPSHOT = null; // content of MAIN handoff.md at setup, null = absent
let SNAPSHOTTED = false;

function handoffAnchoredToMain() {
  const before = HANDOFF_SNAPSHOT === null ? 0 : HANDOFF_SNAPSHOT.length;
  const after = existsSync(MAIN_HANDOFF) ? readFileSync(MAIN_HANDOFF, 'utf8').length : 0;
  if (after <= before) throw new Error('main checkout .claude/handoff.md did not grow');
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
  // Worktree-mode: stop-gate must skip entirely in a linked worktree.
  ['stop-gate.js', {}, 0, null, null, { cwd: WT, noSmoke: true, timeoutMs: 20000 }],
  // Worktree-mode: pre-compact must append to the MAIN checkout's handoff.md.
  ['pre-compact.js', {}, 0, null, null, { cwd: WT, noSmoke: true, after: handoffAnchoredToMain }],
  // Non-repo cwd: resolveRoot falls back to CLAUDE_PROJECT_DIR.
  ['pre-compact.js', {}, 0, null, null, { cwd: os.tmpdir(), noSmoke: true, env: { CLAUDE_PROJECT_DIR: FIX }, after: handoffInFixture }],
];

let failures = 0;
try {
  // Fixtures: ephemeral linked worktree + temp dir for the CLAUDE_PROJECT_DIR
  // fallback path. Inside the try so the finally-cleanup runs even on setup throw.
  execSync(`git worktree add "${WT}" -b ${BRANCH} HEAD`, { cwd: ROOT, stdio: 'pipe', encoding: 'utf8' });
  // Dirty .py would send stop-gate down the slow uv path if the worktree skip
  // regressed; the 20s timeout is the tripwire.
  writeFileSync(path.join(WT, 'backend', '_smoke_dirty.py'), 'x = 1\n');
  mkdirSync(path.join(FIX, '.claude'), { recursive: true });
  HANDOFF_SNAPSHOT = existsSync(MAIN_HANDOFF) ? readFileSync(MAIN_HANDOFF, 'utf8') : null;
  SNAPSHOTTED = true;

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
  try {
    if (SNAPSHOTTED) {
      if (HANDOFF_SNAPSHOT !== null) writeFileSync(MAIN_HANDOFF, HANDOFF_SNAPSHOT);
      else rmSync(MAIN_HANDOFF, { force: true }); // was absent: remove what case (b) created
    }
  } catch (e) { console.error(`cleanup: handoff restore failed (${e.message.split('\n')[0]})`); }
  try { rmSync(FIX, { recursive: true, force: true }); } catch (e) { /* best-effort */ }
  try { execSync(`git worktree remove --force "${WT}"`, { cwd: ROOT, stdio: 'pipe' }); } catch (e) { console.error(`cleanup: worktree remove failed (${e.message.split('\n')[0]})`); }
  try { execSync(`git branch -D ${BRANCH}`, { cwd: ROOT, stdio: 'pipe' }); } catch (e) { console.error(`cleanup: branch delete failed (${e.message.split('\n')[0]})`); }
}
console.log(failures ? `\n${failures} failure(s)` : '\nAll smoke tests passed');
process.exit(failures ? 1 : 0);
