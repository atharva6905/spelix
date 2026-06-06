#!/usr/bin/env node
// Stop. v1: informational final checks (ruff backend + tsc frontend). Always exits 0.
// v2 (governance batch) turns this into a blocking gate — see harness v2 plan Batch 2 Task 9.
const { execSync } = require('node:child_process');
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => {
  if (process.env.HOOK_SMOKE) process.exit(0); // smoke test: skip slow checks
  try {
    try { execSync('uv run ruff check . --quiet', { cwd: 'backend', stdio: 'pipe', timeout: 60000 }); }
    catch (e) { process.stdout.write('ruff (backend):\n' + (e.stdout?.toString() || '').slice(0, 2000)); }
    try { execSync('npx tsc --noEmit', { cwd: 'frontend', stdio: 'pipe', timeout: 90000 }); }
    catch (e) { process.stdout.write('tsc (frontend):\n' + (e.stdout?.toString() || '').slice(0, 2000)); }
  } catch (e) { /* ignore */ }
  process.exit(0);
});
