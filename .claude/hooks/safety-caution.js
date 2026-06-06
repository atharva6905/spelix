#!/usr/bin/env node
// PreToolUse(Bash). Warn-only on risky commands. ALWAYS exits 0.
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => {
  try {
    const j = JSON.parse(d);
    const c = j.tool_input?.command || '';
    const cl = c.toLowerCase();
    const WARN = [
      ['rm -r', 'recursive delete'], ['rm -f', 'force delete'], ['rmdir', 'remove directory'],
      ['git reset', 'git reset'], ['git checkout -- .', 'discard all changes'],
      ['git stash drop', 'drop stash'], ['alembic downgrade', 'downgrade migration'],
      ['delete from', 'SQL delete rows'], ['printenv', 'print all env vars'],
    ];
    for (const [p, r] of WARN) {
      if (cl.includes(p)) {
        process.stderr.write(`\n\u{26A0}\u{FE0F}  CAUTION: ${r} — ${c}\n`);
        break;
      }
    }
  } catch (e) { /* ignore */ }
  process.exit(0);
});
