#!/usr/bin/env node
// Shared root/worktree resolution for hooks. Hooks may execute with cwd inside a
// linked worktree (.claude/worktrees/*) — side effects (handoff writes, graph
// lookups) must anchor to the MAIN checkout; git state probes stay cwd-relative.
const { execSync } = require('node:child_process');
const path = require('node:path');

function git(cmd) {
  return execSync(cmd, { encoding: 'utf8', stdio: 'pipe', timeout: 5000 }).trim();
}

// Main checkout root = parent of the COMMON git dir (works from any linked worktree).
// Fallbacks: CLAUDE_PROJECT_DIR (set by Claude Code), then cwd.
function resolveRoot() {
  try { return path.dirname(git('git rev-parse --path-format=absolute --git-common-dir')); }
  catch (e) { /* not a repo / git missing */ }
  if (process.env.CLAUDE_PROJECT_DIR) return process.env.CLAUDE_PROJECT_DIR;
  return process.cwd();
}

// True iff cwd is inside a LINKED worktree (git-dir differs from common git-dir).
function inLinkedWorktree() {
  try {
    return path.resolve(git('git rev-parse --absolute-git-dir')) !==
           path.resolve(git('git rev-parse --path-format=absolute --git-common-dir'));
  } catch (e) { return false; }
}

module.exports = { resolveRoot, inLinkedWorktree };
