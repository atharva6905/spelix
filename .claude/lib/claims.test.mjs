import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as C from './claims.constants.mjs';

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
