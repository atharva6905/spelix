// Cross-session issue-claim protocol. The ONLY code that touches the lock/labels/heartbeat.
// CLI: node .claude/lib/claims.mjs <claim|release|heartbeat|reclaim-stale|gc-labels|board|ready> [--k v ...]
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import * as C from './claims.constants.mjs';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function gh(args) {
  const mod = process.env.CLAIMS_GH_MODULE;
  if (mod) { const { default: handler } = await import(mod); return handler(args); }
  return execFileSync(C.ghBin(), args, { encoding: 'utf8' });
}
export async function listOpenIssues() {
  const out = await gh(['issue', 'list', '--state', 'open', '--json', 'number,title,labels', '--limit', '200']);
  return JSON.parse(out || '[]');
}
async function issueLabelNames(n) {
  const out = await gh(['issue', 'view', String(n), '--json', 'labels']);
  return (JSON.parse(out).labels || []).map((l) => l.name);
}
async function ensureLabel(name) {
  try { await gh(['label', 'create', name, '--color', C.LABEL_COLOR, '--description', 'ship-loop session claim', '--force']); } catch { /* exists */ }
}
async function addLabel(n, name) { await gh(['issue', 'edit', String(n), '--add-label', name]); }
async function removeLabel(n, name) { await gh(['issue', 'edit', String(n), '--remove-label', name]); }
async function comment(n, body) { await gh(['issue', 'comment', String(n), '--body', body]); }
