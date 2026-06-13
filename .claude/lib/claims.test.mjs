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
