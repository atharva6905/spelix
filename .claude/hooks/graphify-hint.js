#!/usr/bin/env node
// PreToolUse(Bash). When a raw search command runs and a knowledge graph exists,
// injects additionalContext pointing at graphify-out/GRAPH_REPORT.md.
const { existsSync } = require('node:fs');
const path = require('node:path');
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => {
  try {
    const j = JSON.parse(d);
    const c = j.tool_input?.command || '';
    if (/\b(grep|rg|ripgrep|find|fd|ack|ag)\b/.test(c) && existsSync(path.join(require('./_lib.js').resolveRoot(), 'graphify-out', 'graph.json'))) {
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          additionalContext: 'graphify: Knowledge graph exists. Read graphify-out/GRAPH_REPORT.md for god nodes and community structure before searching raw files.',
        },
      }));
    }
  } catch (e) { /* ignore */ }
  process.exit(0);
});
