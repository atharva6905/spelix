#!/usr/bin/env node
// SessionEnd. Appends a one-line close stamp to .claude/handoff.md.
const { execSync } = require('node:child_process');
const { appendFileSync } = require('node:fs');
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => {
  if (process.env.HOOK_SMOKE) process.exit(0); // smoke test: skip side effects
  try {
    const branch = execSync('git branch --show-current', { encoding: 'utf8', timeout: 8000 }).trim();
    const dirty = execSync('git status --porcelain', { encoding: 'utf8', timeout: 8000 }).trim().split('\n').filter(Boolean).length;
    appendFileSync('.claude/handoff.md', `\n<!-- session-end ${new Date().toISOString()} branch=${branch} dirty=${dirty} -->\n`);
  } catch (e) { /* ignore */ }
  process.exit(0);
});
