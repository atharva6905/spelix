#!/usr/bin/env node
// Smoke tests for .claude/hooks/*.js — pipes fixture stdin JSON, asserts exit codes.
// Run: node .claude/hooks/smoke-test.mjs   (exit 0 = all pass, 1 = failures)
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';

const CASES = [
  // [script, stdinJSON, expectedExit, mustMatchStream, regex]
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
];

let failures = 0;
for (const [script, input, wantExit, stream, re] of CASES) {
  const path = `.claude/hooks/${script}`;
  if (!existsSync(path)) { console.error(`FAIL ${script}: file missing`); failures++; continue; }
  const stdin = typeof input === 'string' ? input : JSON.stringify(input);
  const r = spawnSync('node', [path], {
    input: stdin, encoding: 'utf8', timeout: 180000,
    env: { ...process.env, HOOK_SMOKE: '1' }, // scripts with side effects (handoff writes, slow checks) short-circuit
  });
  const exit = r.status ?? -1;
  if (exit !== wantExit) { console.error(`FAIL ${script} [${stdin.slice(0, 40)}]: exit ${exit}, want ${wantExit}`); failures++; continue; }
  if (re && !re.test(r[stream] || '')) { console.error(`FAIL ${script}: ${stream} did not match ${re}`); failures++; continue; }
  console.log(`PASS ${script} [${stdin.slice(0, 40)}]`);
}
console.log(failures ? `\n${failures} failure(s)` : '\nAll smoke tests passed');
process.exit(failures ? 1 : 0);
