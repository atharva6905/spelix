// Single source of truth for the claim protocol. claims.md documents these for humans.
export const CLAIM_LABEL_PREFIX = 'claim:';
export const HEARTBEAT_STALE_MS = 30 * 60 * 1000;
export const LOCK_STALE_MS = 60 * 1000;
export const WATCH_POLL_SECONDS = 1200;
export const MARKER_SENTINEL = '🔒 claimed by';
export const LABEL_COLOR = '5319e7';
export const EXCLUDE_LABELS = ['needs-human', 'needs-design', 'parked', 'blocked', 'wontfix', 'duplicate'];
export const TIER_RANK = {
  'T0': 0, 'tier/T0': 0, 'T1': 1, 'tier/T1': 1, 'T2': 2, 'tier/T2': 2, 'T3': 3, 'tier/T3': 3,
};
export const SIZE_RANK = { 'size/XS': 0, 'size/S': 1, 'size/M': 2, 'size/L': 3, 'size/XL': 4 };
export const stateDir = () => process.env.CLAIMS_STATE_DIR || '.claude';
export const stateFile = () => `${stateDir()}/.claims.json`;
export const lockDir = () => `${stateDir()}/.claim.lock`;
export const ghBin = () => process.env.CLAIMS_GH_BIN || 'gh';
