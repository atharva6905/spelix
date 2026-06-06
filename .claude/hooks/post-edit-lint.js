#!/usr/bin/env node
// PostToolUse(Write|Edit). ruff --fix + pyright on edited .py files only.
// tsc deliberately NOT run here (whole-frontend check is slow) — see stop-gate.js.
const { execSync } = require('node:child_process');
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => {
  try {
    const j = JSON.parse(d);
    const f = j.tool_input?.file_path || j.tool_input?.path || '';
    if (f.endsWith('.py')) {
      try { execSync(`ruff check --fix ${JSON.stringify(f)}`, { stdio: 'pipe', timeout: 30000 }); }
      catch (e) { process.stdout.write(e.stdout?.toString() || ''); }
      try { execSync(`pyright ${JSON.stringify(f)}`, { stdio: 'pipe', timeout: 60000 }); }
      catch (e) { process.stdout.write(e.stdout?.toString() || ''); }
    }
  } catch (e) { /* ignore */ }
  process.exit(0);
});
