#!/usr/bin/env node
// PreToolUse(Bash). Blocks git commit/push when staged+unstaged diff contains secrets. Exit 2 = block.
const { execSync } = require('node:child_process');
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => {
  try {
    const j = JSON.parse(d);
    const c = j.tool_input?.command || '';
    if (!/git (commit|push)/.test(c)) process.exit(0);
    const diff =
      execSync('git diff --cached', { encoding: 'utf8', timeout: 15000 }) +
      execSync('git diff', { encoding: 'utf8', timeout: 15000 });
    // Only scan ADDED lines to avoid blocking on removals of old strings.
    const added = diff.split('\n').filter((l) => l.startsWith('+') && !l.startsWith('+++')).join('\n');
    if (/(sk-|password|secret|supabase_service_role|anthropic_api_key)/i.test(added)) {
      process.stderr.write('\n\u{1F6AB} BLOCKED: secrets detected in staged changes\n');
      process.exit(2);
    }
  } catch (e) { /* git unavailable etc: allow */ }
  process.exit(0);
});
