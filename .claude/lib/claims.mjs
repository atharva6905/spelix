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

function lockAgeMs() { try { return Date.now() - statSync(C.lockDir()).mtimeMs; } catch { return Infinity; } }

export async function withLock(fn) {
  const start = Date.now();
  for (;;) {
    try {
      mkdirSync(C.lockDir());
      writeFileSync(`${C.lockDir()}/owner`, `${process.pid} ${new Date().toISOString()}`);
      break;
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
      if (lockAgeMs() >= C.LOCK_STALE_MS) { try { rmSync(C.lockDir(), { recursive: true, force: true }); } catch { /* race */ } continue; }
      if (Date.now() - start > C.LOCK_STALE_MS * 2) throw new Error('claims: lock acquisition timed out');
      await sleep(150);
    }
  }
  try { return await fn(); }
  finally { try { rmSync(C.lockDir(), { recursive: true, force: true }); } catch { /* already gone */ } }
}

export function readState() { try { return JSON.parse(readFileSync(C.stateFile(), 'utf8')); } catch { return {}; } }
export function writeState(s) { writeFileSync(C.stateFile(), JSON.stringify(s, null, 2)); }
export function isFresh(ts) { return !!ts && (Date.now() - Date.parse(ts) < C.HEARTBEAT_STALE_MS); }

export function tierRank(names) {
  let best = null;
  for (const n of names) if (n in C.TIER_RANK) best = best === null ? C.TIER_RANK[n] : Math.min(best, C.TIER_RANK[n]);
  return best;
}
export function sizeRank(names) { for (const n of names) if (n in C.SIZE_RANK) return C.SIZE_RANK[n]; return 99; }
export function claimOwner(names) {
  const l = names.find((n) => n.startsWith(C.CLAIM_LABEL_PREFIX));
  return l ? l.slice(C.CLAIM_LABEL_PREFIX.length) : null;
}
export async function readyQueue() {
  const issues = await listOpenIssues();
  const eligible = issues.filter((i) => {
    const names = i.labels.map((l) => l.name);
    if (tierRank(names) === null) return false;
    if (names.some((n) => C.EXCLUDE_LABELS.includes(n))) return false;
    return true;
  });
  eligible.sort((a, b) => {
    const an = a.labels.map((l) => l.name), bn = b.labels.map((l) => l.name);
    return (tierRank(an) - tierRank(bn)) || (sizeRank(an) - sizeRank(bn)) || (a.number - b.number);
  });
  return eligible;
}

function isLiveClaim(issueNum, ownerSid, state) {
  const e = state[issueNum];
  return !!(e && e.sid === ownerSid && isFresh(e.ts));
}

export async function claim({ sid }) {
  const chosen = await withLock(async () => {
    const state = readState();
    for (const c of await readyQueue()) {
      const names = await issueLabelNames(c.number);
      const owner = claimOwner(names);
      if (owner) {
        if (isLiveClaim(c.number, owner, state)) continue;
        await removeLabel(c.number, C.CLAIM_LABEL_PREFIX + owner);
        delete state[c.number];
      }
      const myLabel = C.CLAIM_LABEL_PREFIX + sid;
      await ensureLabel(myLabel);
      await addLabel(c.number, myLabel);
      state[c.number] = { sid, ts: new Date().toISOString(), worktree: process.env.CLAIMS_WORKTREE || null };
      writeState(state);
      return { number: c.number, title: c.title, sid };
    }
    return null;
  });
  if (chosen) { try { await comment(chosen.number, `${C.MARKER_SENTINEL} ${sid} @ ${new Date().toISOString()}`); } catch { /* best effort */ } }
  return chosen;
}
