# Cross-Session Claim Protocol (ship-loop / groom)

Constants live in `.claude/lib/claims.constants.mjs` — never hardcode them elsewhere.

- **Ownership**: GitHub label `claim:<sid>` on the issue (the glanceable board).
- **Liveness**: `.claude/.claims.json` (local, gitignored) — `{ issue: { sid, ts, worktree } }`,
  refreshed each loop cycle. A claim is *live* iff the label exists AND `ts` is < 30 min old.
- **Atomicity**: a local lock dir `.claude/.claim.lock` (atomic `mkdir`) serializes the
  check-and-claim. Force-broken if older than 60 s. **Single-machine only** — running a
  session on another machine breaks the lock + heartbeat.
- **Eligibility (auto-claim)**: open ∧ has a tier label (`T0..T3` or `tier/T*`) ∧ no live
  `claim:*` ∧ none of `needs-human, needs-design, parked, blocked, wontfix, duplicate`.
- **Order**: tier asc → size asc → issue# asc.
- **Release outcomes**: `merged`/`skipped` drop the claim; `blocked` → `blocked` label;
  `needs-human` → `needs-human` label. Heartbeat entry cleared in all cases.

CLI (all output JSON): `node .claude/lib/claims.mjs <claim|release|heartbeat|reclaim-stale|gc-labels|board|ready> [--sid X --issue N --outcome O]`.
groom NEVER claims; it only runs `board`, `reclaim-stale`, `gc-labels`.
