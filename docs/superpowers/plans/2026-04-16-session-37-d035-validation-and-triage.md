# Session 37: D-035 Prod Validation + Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate that the post-89bb58b prod pipeline actually completes on `atharva-bench-no-weight.mov` (refuting the prior 1800s observation via E2E evidence, not just bench), then either close D-035 cleanly or pivot to fixing the true stuck stage using the new `timing_json` telemetry.

**Architecture:** Evidence-first. Three linear phases — (A) prod E2E via Playwright MCP + DB inspection, (B) conditional branch based on what the E2E shows, (C) backlog/ADR hygiene. Phase A is pure measurement — no code. Phase B branches: if the clip completes under 10 minutes, we write the closeout ADR; if it stalls, we use `timing_json` to scope a Tier 2 sub-plan (not implemented here — this plan just identifies the next one). Phase C is docs-only.

**Tech Stack:** Playwright MCP (browser automation against spelix.app), Supabase MCP (`execute_sql`, `list_tables`), SSH to `spelix-droplet` (`docker logs`, `docker exec`), `mcp__github__*` (PR creation for any backlog/ADR updates). No backend code is modified unless Phase B's investigation says so — this plan stops before that.

**File Structure:**
- Modify: `.claude/handoff.md` — append E2E findings + close-out or pivot call.
- Modify: `backlog.md` — flip D-035 row based on outcome.
- Modify: `decisions.md` — append ADR-060 (D-035 closeout: why the prior gap observation didn't reproduce) if outcome is closure.
- Create (conditional, Phase B only): `docs/superpowers/plans/2026-04-17-<tier-2-direction>.md` — next plan if we find a real bottleneck.

---

## Task 1: Pre-flight — confirm droplet state + empty streaq queue

**Files:** none (read-only checks).

Why: session 36 left `/tmp/bench.mov` on the droplet and a diagnostic Python process running in `spelix-worker-1`. We need to make sure nothing is stuck before kicking a real E2E — a fresh test needs a clean queue.

- [ ] **Step 1: Check droplet HEAD matches main's current tip**

Run:
```bash
git fetch origin main
LOCAL_MAIN=$(git rev-parse origin/main)
DROPLET_HEAD=$(ssh spelix-droplet "git -C /home/deploy/spelix rev-parse HEAD")
echo "local main: $LOCAL_MAIN"
echo "droplet HEAD: $DROPLET_HEAD"
[ "$LOCAL_MAIN" = "$DROPLET_HEAD" ] && echo "match" || echo "MISMATCH — redeploy needed"
```

Expected: droplet HEAD == origin/main (`233b430` or later if the handoff PR #65 merge has been followed by other commits).

- [ ] **Step 2: Confirm all containers healthy and no task in the queue**

Run:
```bash
ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"
ssh spelix-droplet "docker exec spelix-redis-1 redis-cli XLEN streaq:spelix:queues:normal"
ssh spelix-droplet "docker exec spelix-redis-1 redis-cli --scan --pattern 'streaq:spelix:task:data:*' | head -5"
```

Expected: all containers `(healthy)` or `Up`; `XLEN` returns `0` (queue empty); no `task:data:*` keys lingering (no stuck in-flight tasks). If any task data keys exist, `docker exec spelix-redis-1 redis-cli DEL <key>` them — they're leftovers from session 36's diagnostic run.

- [ ] **Step 3: Confirm diagnostic fixture is NOT still on the worker**

Run:
```bash
ssh spelix-droplet "docker exec spelix-worker-1 ls -la /tmp/bench.mov 2>/dev/null && echo 'FOUND' || echo 'absent'"
```

If `FOUND`, remove — a stale fixture is harmless but signals the worker wasn't restarted since session 36, which matters for `Step 4`:

```bash
ssh spelix-droplet "docker exec spelix-worker-1 rm -f /tmp/bench.mov"
```

- [ ] **Step 4: Decide on worker restart**

If the worker has been up since session 36 (prior to the `89bb58b` deploy), restart it so it picks up the merged code. Check `docker ps` uptime column from Step 2 — if the worker has been up > ~5 hours, force restart:

```bash
ssh spelix-droplet "docker restart spelix-worker-1 && sleep 3 && docker ps --format '{{.Names}} {{.Status}}'"
```

Expected: `spelix-worker-1` shows `Up <seconds>` after restart.

---

## Task 2: Prod E2E via Playwright MCP — the 22.8s fixture

**Files:** none (Playwright actions + screenshots land in `.playwright-mcp/` which is gitignored).

Why: session 36 measured pose extraction at ~284s via a direct-call script. Prior sessions claimed the full prod pipeline timed out at 1800s on the same clip. The only way to resolve the contradiction is to drive a real upload through https://spelix.app and watch.

- [ ] **Step 1: Open the site and sign in**

Via Playwright MCP:
```
mcp__playwright__browser_navigate({url: "https://spelix.app"})
mcp__playwright__browser_snapshot()
```

If the snapshot shows a login form (not a logged-in home page), the browse daemon cookies have expired. Run `/setup-browser-cookies` first. Do NOT paste credentials into Playwright.

- [ ] **Step 2: Start an upload for the fixture**

Navigate to the new-analysis page, fill the form, select the fixture file via absolute path:
```
mcp__playwright__browser_navigate({url: "https://spelix.app/upload"})   # actual route may be /analyze or /new — read the snapshot
mcp__playwright__browser_snapshot()
# click "Bench Press" / "Flat", then the file input
mcp__playwright__browser_file_upload({
  paths: ["C:/Users/athar/projects/spelix/e2e/fixtures/atharva-bench-no-weight.mov"]
})
mcp__playwright__browser_click({
  element: "Upload Video button",
  ref: "<ref from snapshot>"
})
```

Expected: redirect to `/analysis/<id>`. **Record the analysis ID from the URL** — you'll query it in Task 3.

- [ ] **Step 3: Watch status transitions for up to 15 minutes**

The expected trajectory per backend/CLAUDE.md: `queued → quality_gate_pending → processing → coaching → completed`. Bench on this clip is ~5 min of pose extraction plus other stages = expect ~8-12 minutes total.

```
mcp__playwright__browser_navigate({url: "https://spelix.app/analysis/<id>"})
# Wait for content change. The status poll fallback refreshes every ~5s per the useAnalysisStatus hook.
mcp__playwright__browser_wait_for({time: 60})   # minute 1
mcp__playwright__browser_snapshot()
# ... repeat each 60 seconds ...
```

Record the status at each minute mark (a table in your notes — don't commit a timing log, just remember for Task 4).

**Stopping criteria:**
- **Success:** status reaches `completed` → move to Task 3 to verify `timing_json`, then Task 5 branch A.
- **Partial progress, still running at minute 15:** task has NOT hit the 1800s (30 min) timeout yet. Keep waiting — just less aggressively. Check every 3 minutes.
- **Task hits `failed` or `quality_gate_rejected`:** abnormal — investigate logs (`ssh spelix-droplet "docker logs --tail 200 spelix-worker-1"`) and fall through to Task 5 branch B with whatever `timing_json` is on the row.
- **Still stuck at minute 30:** timeout fired. Go to Task 3, then Task 5 branch B.

- [ ] **Step 4: Capture the end-state screenshot**

```
mcp__playwright__browser_take_screenshot({filename: "session-37-d035-e2e-end.png"})
```

Screenshot lands in `e2e/screenshots/` (or wherever `frontend/CLAUDE.md` says). Reference from handoff but don't commit it.

---

## Task 3: Pull the `timing_json` row from Supabase and read it

**Files:** none.

- [ ] **Step 1: Run the DB query for the specific analysis row**

Via Supabase MCP:
```
mcp__supabase__execute_sql({
  query: "SELECT id, status, timing_json, error_message, retry_count, created_at, updated_at FROM analyses WHERE id = '<analysis_id_from_task_2>'"
})
```

- [ ] **Step 2: Also pull the last 10 analysis rows for comparison**

```
mcp__supabase__execute_sql({
  query: "SELECT id, status, timing_json, created_at FROM analyses WHERE created_at > '2026-04-16T11:27:00Z' ORDER BY created_at DESC LIMIT 10"
})
```

- [ ] **Step 3: Interpret `timing_json`**

The JSONB shape is `{stage_name: ms_float}`. After PR #64 the order of insertion is: `download` → `duration_probe` → `extract_landmarks` → `exercise_detection` → `quality_gates` → (then later stages that don't have timers today).

Record each stage's ms. Compare `extract_landmarks` against the session 36 diagnostic number (283,789 ms for executor variant). If prod `extract_landmarks` >> diagnostic → the in-pipeline-async vs direct-call hypothesis matters; if prod ≈ diagnostic → pose extraction is fine and the time is being burned elsewhere.

---

## Task 4: Walk the worker log and confirm the stage ordering matches

**Files:** none.

Why: `timing_json` tells us how long each named stage took, but NOT what happened BETWEEN stages (e.g., exercise_detection finishes then quality_gates starts 60s later — that gap is invisible). Worker logs fill that in.

- [ ] **Step 1: Dump the last hour of worker logs filtered by task ID**

```bash
ssh spelix-droplet "docker logs --since 1h spelix-worker-1 2>&1 | grep -E '(<analysis_id>|D035_DIAG|stage|extract|quality_gate|exercise_detection|download)' | head -60"
```

Expected: a chronological sequence showing task pickup, stage entries/exits, and task completion or timeout.

- [ ] **Step 2: Note any unusually long gaps**

If two adjacent log lines are more than ~60s apart with no intermediate log, that gap is probably where the real bottleneck lives. Write the gap duration + the stages it spans into your notes for Task 5.

---

## Task 5: Decision branch — close D-035 (A) or scope Tier 2 (B)

**Files:**
- Modify: `.claude/handoff.md`
- Modify: `backlog.md`
- Modify: `decisions.md`
- (Branch B only) Create: `docs/superpowers/plans/2026-04-17-<direction>.md`

This task is the whole point of Phase A. Exactly one branch is taken.

### Branch A — pipeline completed successfully on the 22.8s fixture

Triggered when: Task 2 reached `completed` in under ~15 min AND `timing_json.extract_landmarks` is within 2× of the 283,789 ms diagnostic baseline.

- [ ] **A.1: Update `backlog.md` — flip D-035 row from `partial` to `done`**

Find the D-035 line in `backlog.md`. Change status to `done` and append the PR merge commit (`89bb58b`) plus session 37's validating analysis ID. Example row shape:
```
| D-035 | Pipeline telemetry + bench-vs-prod gap validation | done | 89bb58b, analysis <id> on 2026-04-16 |
```

- [ ] **A.2: Write ADR-060 to `decisions.md`**

Append a new ADR block at the bottom of `decisions.md` — matching the style of ADR-058 and ADR-059:

```markdown
## ADR-060 — D-035 closeout: bench-vs-prod gap did not reproduce (2026-04-16)

**Context:** Session 35.5 reported prod `extract_landmarks` taking >1800s on
`atharva-bench-no-weight.mov`, ≥6× the 287.7s bench baseline. D-035 was opened
to diagnose and close that gap.

**Data:** Session 36 (post-PR #64 deploy, droplet HEAD `89bb58b`) ran a
diagnostic helper inside `spelix-worker-1` that executed `extract_landmarks`
on the same clip under two variants: via `run_in_executor` (283.8s) and
inline in an async function (272.1s). Session 37 ran a full prod E2E on the
same clip — it completed end-to-end in ~<X> min, with
`timing_json.extract_landmarks = <Y>` ms. Both measurements fall within ~5%
of bench.

**Decision:** Close D-035. The original 1800s observation was either
workload-transient (concurrent task, transient disk/network issue on
Supabase Storage download) or misattributed to `extract_landmarks` when the
actual stuck stage was unnamed-and-untimed.

**Consequences:**
- D-036 (GPU offload) remains deferred post-beta. CPU pose extraction at
  ~284s for a 22.8s clip is comfortably under the 1800s task timeout.
- Priority 1's early `timing_json` writes (after download, duration_probe,
  extract_landmarks) remain in place as permanent instrumentation so any
  future stuck run has per-stage timings on the analysis row before the
  timeout fires.
- The streaq `pose_extraction_diagnostic` task + `scripts/enqueue_d035_diagnostic.py`
  CLI remain as diagnostic tooling — small surface area, useful if the
  question re-opens.

**Supersedes:** neither ADR-058 nor ADR-059. Those remain authoritative for
the telemetry tier and GPU deferral decisions they describe.
```

Replace `<X>` and `<Y>` with the actual measured values.

- [ ] **A.3: Append "Session 37 Findings" to `.claude/handoff.md`**

Add a new section at the top of the handoff file (above the existing "Session 36" section):

```markdown
# Session 37 Findings — D-035 CLOSED on prod E2E

**Result:** prod E2E on `atharva-bench-no-weight.mov` completed in <X> minutes.
`timing_json` populated as expected. ADR-060 written, backlog D-035 → done.

Analysis ID for reference: <analysis_id>.
Measured per-stage times (ms): <JSON from Task 3>.
```

- [ ] **A.4: Open a single PR bundling backlog.md + decisions.md + handoff.md**

Branch: `docs/session-37-d035-closeout`.

```bash
git checkout -b docs/session-37-d035-closeout
git add .claude/handoff.md backlog.md decisions.md
git commit -m "docs: close D-035 (session 37) — prod E2E validates bench-vs-prod gap does not reproduce"
git push -u origin docs/session-37-d035-closeout
```

Then open the PR via `mcp__github__create_pull_request` with base `main`, title `docs: close D-035 (session 37)`, and a body that lists the analysis ID + measured times.

Wait for CI green (2-3 min for docs PR). Merge with `merge_method: "merge"`.

### Branch B — pipeline stalled, or `timing_json` shows a real bottleneck

Triggered when: Task 2 did NOT reach `completed` within 30 min, OR `timing_json.extract_landmarks` is > 2× the diagnostic baseline, OR any other stage shows an obviously wrong duration (e.g., `quality_gates > 60_000` ms).

- [ ] **B.1: Identify the single dominant stage**

From Task 3's `timing_json` output, pick the stage with the largest `ms` value. Call it `<worst_stage>`. From Task 4's log-gap analysis, note if the real time is actually in an un-timed gap (e.g., between `extract_landmarks` finishing and `exercise_detection` starting). If the gap is bigger than any named stage, the next plan must ADD a timer for that gap, not optimize a named stage.

- [ ] **B.2: Write the Tier 2 scoping plan**

Create `docs/superpowers/plans/2026-04-17-<worst_stage>-optimization.md` with a single-phase plan:

1. Reproduce locally or on droplet (one task).
2. Add any missing timers if Task 4 revealed an un-timed gap (one task).
3. Instrument the specific call path with finer sub-timings (one task).
4. Fix the hot spot (tasks scoped to what the instrumentation reveals — do NOT predict here).

Stop writing the plan when Task 4 of the new plan is "measure again" — the actual fix tasks depend on sub-timings we don't have yet. Example filename: `docs/superpowers/plans/2026-04-17-quality-gate-stage-timing.md`.

- [ ] **B.3: Update `backlog.md` — keep D-035 open but narrow its scope**

Change the D-035 description from the generic "pipeline telemetry" to the specific finding, e.g., "`quality_gates` stage takes <Y> ms on 1080p@59fps clips — unacceptable". Do NOT flip to `done`.

- [ ] **B.4: Append "Session 37 Findings" to `.claude/handoff.md`**

```markdown
# Session 37 Findings — D-035 STILL OPEN, pivot to <worst_stage>

**Result:** prod E2E on `atharva-bench-no-weight.mov` <stalled at / completed in>
<X> minutes. `timing_json` reveals <worst_stage> = <Y> ms — well above
the <diagnostic or expected> baseline.

Next plan: `docs/superpowers/plans/2026-04-17-<worst_stage>-optimization.md`.

Analysis ID: <analysis_id>.
```

- [ ] **B.5: Open one PR bundling backlog.md + handoff.md + new plan file**

Branch: `docs/session-37-d035-pivot-<worst_stage>`. Same mechanics as branch A.4.

---

## Self-Review

**Spec coverage:**
- "Prod E2E via Playwright MCP to validate the direct-call finding" (handoff §6) → Task 2. ✓
- "Supabase diff pull — confirms early writes populate on real traffic" (handoff §6) → Task 3. ✓
- "Use timing_json to decide Tier 2 direction" (handoff §6) → Task 5 branch B. ✓
- "Sanity-checking via the full web flow is pending for session 37" (handoff §0) → Task 2. ✓
- "Query Supabase for any new analyses rows since the 89bb58b deploy" (handoff §2) → Task 3 Step 2. ✓

**Placeholder scan:**
- `<analysis_id_from_task_2>` — placeholder-looking but is a deliberate variable. Task 2 Step 2 tells you to record the ID and Task 3 Step 1 uses it. Acceptable.
- `<X>`, `<Y>`, `<worst_stage>` in Branch A/B — also deliberate. These are the measured outputs the writer substitutes in. Acceptable.
- No "TBD", "implement later", or "add appropriate X" text.

**Type consistency:**
- `timing_json` treated as `dict[str, float]` (ms floats) throughout — matches `backend/app/models/analysis.py:58-63` and `StageTimer.as_dict()` return type.
- Analysis ID referenced consistently as a UUID string.
- Branch names follow `docs/session-37-*` convention consistently.

**Scope check:** Phase B explicitly REFUSES to write the fix plan — it writes the *scoping* plan whose first task is "reproduce + instrument finer". This keeps the plan honest: we don't pretend to know which code to change before we have the data.

**Known risks:**
- Task 2 Playwright flow may hit an auth wall if cookies expired — explicit guidance in Step 1 to run `/setup-browser-cookies` first.
- Task 1 Step 4 conservative: restarts worker on > 5h uptime. Restart has some cost (drops any in-flight tasks), but at 16:30 UTC on a quiet day this is worth paying for a clean baseline.
- Task 5 branch A.2's ADR-060 text embeds `<X>` / `<Y>` — the writer must substitute actual numbers before committing. Rejected if they ship with literal `<X>`.

---

## Execution

Plan complete and saved to `docs/superpowers/plans/2026-04-16-session-37-d035-validation-and-triage.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
