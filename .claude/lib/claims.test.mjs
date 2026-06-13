import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as C from './claims.constants.mjs';
import { mkdtempSync, writeFileSync as wf, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);

function harness(issues = {}, labels = []) {
  const dir = mkdtempSync(join(tmpdir(), 'claims-'));
  const db = join(dir, 'db.json');
  wf(db, JSON.stringify({ issues, labels, comments: [] }));
  process.env.CLAIMS_STATE_DIR = dir;
  process.env.CLAIMS_SHIM_DB = db;
  process.env.CLAIMS_GH_MODULE = pathToFileURL(join(process.cwd(), '.claude/lib/claims.ghshim.mjs')).href;
  return { dir, db, read: () => JSON.parse(readFileSync(db, 'utf8')) };
}

test('constants: tunables and predicates are well-formed', () => {
  assert.equal(C.CLAIM_LABEL_PREFIX, 'claim:');
  assert.equal(C.HEARTBEAT_STALE_MS, 30 * 60 * 1000);
  assert.equal(C.LOCK_STALE_MS, 60 * 1000);
  assert.equal(C.WATCH_POLL_SECONDS, 1200);
  assert.ok(C.EXCLUDE_LABELS.includes('needs-human'));
  assert.ok(C.EXCLUDE_LABELS.includes('blocked'));
  assert.equal(C.TIER_RANK['T0'], 0);
  assert.equal(C.TIER_RANK['tier/T1'], 1);
  assert.equal(C.SIZE_RANK['size/XS'], 0);
});

test('constants: path resolvers honor env overrides', () => {
  process.env.CLAIMS_STATE_DIR = '/tmp/x';
  assert.equal(C.stateFile(), '/tmp/x/.claims.json');
  assert.equal(C.lockDir(), '/tmp/x/.claim.lock');
  delete process.env.CLAIMS_STATE_DIR;
});

test('gh adapter: listOpenIssues parses the shim DB', async () => {
  harness({ '5': { number: 5, title: 'A', labels: ['T1', 'size/S'] } });
  const { listOpenIssues } = await import('./claims.mjs?adapter=1');
  const issues = await listOpenIssues();
  assert.equal(issues.length, 1);
  assert.equal(issues[0].number, 5);
  assert.deepEqual(issues[0].labels.map((l) => l.name), ['T1', 'size/S']);
});

test('lock: two processes incrementing under withLock never interleave', () => {
  const h = harness();
  const counter = join(h.dir, 'counter.txt');
  wf(counter, '0');
  const cpath = counter.replace(/\\/g, '/');
  const claimsUrl = pathToFileURL(join(process.cwd(), '.claude/lib/claims.mjs')).href;
  const worker = `
    import { withLock } from '${claimsUrl}';
    import { readFileSync, writeFileSync } from 'node:fs';
    await withLock(async () => {
      const v = Number(readFileSync('${cpath}', 'utf8'));
      await new Promise((r) => setTimeout(r, 200));
      writeFileSync('${cpath}', String(v + 1));
    });
  `;
  const { spawn } = require('node:child_process');
  const env = { ...process.env };
  const p1 = spawn(process.execPath, ['--input-type=module', '-e', worker], { env });
  const p2 = spawn(process.execPath, ['--input-type=module', '-e', worker], { env });
  return new Promise((resolve) => {
    let done = 0;
    const fin = () => { if (++done === 2) { assert.equal(readFileSync(counter, 'utf8'), '2'); resolve(); } };
    p1.on('exit', fin); p2.on('exit', fin);
  });
});

test('lock: a stale lock dir (older than LOCK_STALE_MS) is force-broken', async () => {
  const h = harness();
  const { withLock } = await import('./claims.mjs?lock=1');
  const { mkdirSync, utimesSync } = await import('node:fs');
  mkdirSync(`${h.dir}/.claim.lock`);
  const past = (Date.now() - 5 * 60 * 1000) / 1000;
  utimesSync(`${h.dir}/.claim.lock`, past, past);
  let ran = false;
  await withLock(async () => { ran = true; });
  assert.ok(ran);
});

test('state: read/write round-trips and isFresh respects the threshold', async () => {
  harness();
  const { readState, writeState, isFresh } = await import('./claims.mjs?state=1');
  assert.deepEqual(readState(), {});
  writeState({ 5: { sid: 'sl-a', ts: new Date().toISOString(), worktree: null } });
  assert.equal(readState()[5].sid, 'sl-a');
  assert.ok(isFresh(new Date().toISOString()));
  assert.equal(isFresh(new Date(Date.now() - 40 * 60 * 1000).toISOString()), false);
});

test('readyQueue: filters by tier, excludes exclusion labels, orders tier→size→number', async () => {
  harness({
    '10': { number: 10, title: 'no tier', labels: ['size/S'] },
    '11': { number: 11, title: 'excluded', labels: ['T0', 'needs-human'] },
    '12': { number: 12, title: 'T1 big', labels: ['T1', 'size/L'] },
    '13': { number: 13, title: 'T0 small', labels: ['T0', 'size/S'] },
    '14': { number: 14, title: 'T1 small', labels: ['tier/T1', 'size/S'] },
  });
  const { readyQueue } = await import('./claims.mjs?ready=1');
  const q = (await readyQueue()).map((i) => i.number);
  assert.deepEqual(q, [13, 14, 12]);
});

test('claim: takes the top eligible issue, labels it, records heartbeat', async () => {
  const h = harness({
    '13': { number: 13, title: 'T0 small', labels: ['T0', 'size/S'] },
    '12': { number: 12, title: 'T1 big', labels: ['T1', 'size/L'] },
  });
  const { claim } = await import('./claims.mjs?claim=1');
  const got = await claim({ sid: 'sl-a' });
  assert.equal(got.number, 13);
  assert.ok(h.read().issues['13'].labels.includes('claim:sl-a'));
  assert.ok(h.read().comments.some((c) => c.n === '13' && c.body.includes('claimed by sl-a')));
});

test('claim: skips an issue with a LIVE claim by another session', async () => {
  const h = harness({ '13': { number: 13, title: 'x', labels: ['T0', 'size/S', 'claim:sl-b'] } });
  wf(join(h.dir, '.claims.json'), JSON.stringify({ 13: { sid: 'sl-b', ts: new Date().toISOString() } }));
  const { claim } = await import('./claims.mjs?claim=2');
  const got = await claim({ sid: 'sl-a' });
  assert.equal(got, null);
});

test('claim: reclaims an issue whose claim heartbeat is STALE', async () => {
  const h = harness({ '13': { number: 13, title: 'x', labels: ['T0', 'size/S', 'claim:sl-b'] } });
  wf(join(h.dir, '.claims.json'), JSON.stringify({ 13: { sid: 'sl-b', ts: new Date(Date.now() - 45 * 60 * 1000).toISOString() } }));
  const { claim } = await import('./claims.mjs?claim=3');
  const got = await claim({ sid: 'sl-a' });
  assert.equal(got.number, 13);
  const labels = h.read().issues['13'].labels;
  assert.ok(labels.includes('claim:sl-a'));
  assert.ok(!labels.includes('claim:sl-b'));
});
