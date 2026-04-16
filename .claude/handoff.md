# Session 38 Handoff → Session 39: D-035 ROOT CAUSE FOUND — `track_barbell_from_video` takes 24.4 min on 1345 frames @ 1080p, next session diagnoses WHY and brainstorms permanent fix

**Context refresh:** Session 38 completed the D-035 telemetry instrumentation arc that sessions 35.5–37 started. Three PRs merged today (PR #68, #69 on top of session 37's #66 and #67). The final E2E run on `atharva-bench-no-weight.mov` (analysis `fc318bc3-3cf9-4f0e-85ee-0f5d61cb77b1`) produced the first-ever complete per-stage timing breakdown from a prod pipeline. **The 24-minute gap is `track_barbell_from_video`** — the streaming pixel-based barbell tracker that reads every frame from disk for color-based centroid detection.

**Full timing breakdown (prod, 22.8s 1080p@59fps bench-no-weight clip):**

| Stage | Duration | % of total | Notes |
|---|---|---|---|
| download | 2.1s | 0.1% | Supabase Storage → /tmp |
| duration_probe | 0.12s | <0.01% | ffprobe |
| extract_landmarks | 286.4s (4.8 min) | 16.3% | MediaPipe BlazePose Heavy, matches bench |
| exercise_detection | 4.4ms | <0.01% | Heuristic only (high conf, no GPT-4o) |
| quality_gates | 0.14s | <0.01% | |
| angle_timeseries | 24ms | <0.01% | |
| rep_detection | 1.3ms | <0.01% | |
| metric_extraction | 0.4ms | <0.01% | |
| confidence_scoring | 0.008ms | <0.01% | |
| keyframe_extraction | 0.3ms | <0.01% | |
| **barbell_tracking** | **1,465,647ms (24.4 min)** | **83.4%** | **THE BOTTLENECK** |
| form_scoring | 0.1ms | <0.01% | |
| generate_annotated_video | pending | — | Pipeline still running at handoff time |
| generate_angle_plot | pending | — | |
| upload_artifacts | pending | — | |

**Key insight: `track_barbell_from_video` is 83% of pipeline wall time.** Everything else COMBINED (including pose extraction) is <5 min. The pipeline would complete under 600s if barbell tracking were instant — comfortably within the 900s original task timeout, let alone the 1800s safety net.

**Additional findings this session:**
1. **Row-lock contention bug (PR #69).** The main pipeline session's `repo.update(analysis)` flush takes a Postgres row lock held until end-of-pipeline commit. Under PgBouncer transaction mode, any fresh-session UPDATE to the same row blocks on that lock, eventually hitting Supabase's `statement_timeout`. Fix: `await repo.db.commit()` after each `repo.update(analysis)`, releasing the lock between stages. Side benefit: frontend status polling now sees intermediate state (`processing`, `coaching`) instead of `quality_gate_pending` for 25 minutes.
2. **Session 37's "24-min gap" was NOT lock contention.** That was the actual `barbell_tracking` cost — the lock contention was an artifact introduced by PR #68's fresh-session writes, then fixed by PR #69's mid-pipeline commits. The telemetry was the tool; the barbell tracker is the bug.

## 1. Completed

| Task | Commit / PR | Description |
|---|---|---|
| S38 Task 1 | `e55ccea` (PR #68, merge `df52631`) | Test: full-stage telemetry assertion (RED) |
| S38 Task 2 | `e55ccea` (PR #68, merge `df52631`) | Wrap every post-extract stage in `timer.stage()` + `_persist_timing_telemetry` |
| S38 Task 3 (partial) | `74db2e5` + `55b009e` (PR #69, merge `0fdcc97`) | Fix row-lock contention via `repo.db.commit()` after each `repo.update` |
| S38 Task 3 E2E | analysis `fc318bc3` | Prod E2E produced complete per-stage timing for first time |

PRs merged this session:
- **PR #68** (`df52631`) — `feat(pipeline): D-035 instrument every stage after extract_landmarks`
- **PR #69** (`0fdcc97`) — `fix(pipeline): D-035 release row lock mid-pipeline via repo.db.commit()`

Earlier this session (before the plan pivot):
- **PR #67** (`5097257`) — `docs(handoff): session 37 findings`

## 2. Remaining

| ID | Title | Status | Deps | Priority |
|---|---|---|---|---|
| D-035 | Pipeline timeout on 1080p@59fps clips | **root-caused** | — | **CRITICAL — barbell_tracking is 24.4 min** |
| D-032 | Framing + single-person quality gates reject correctly-framed barbell videos | pending | — | HIGH |
| D-034 | Pipeline OOM post-quality-gate on 1080p@59fps clips | pending | — | HIGH (may be moot if barbell fix drops peak memory) |
| D-028 | `useAnalysisStatus` "Connection lost" banner | pending | — | medium |
| D-029 | SaMD rename `injury_advice_accurate` → `movement_advice_accurate` | pending | — | low |
| D-030 | Orphan `rag_documents` uploading-state cleanup | pending | — | low |
| D-031 | Admin GET /rag/documents free-text query param | pending | — | low |
| D-036 | GPU offload (deferred post-beta) | pending | D-035 close | low |

## 3. Test counts

- **Backend:** 1528 passing, 19 skipped, 0 failing (PR #68 added 1 test)
- **Frontend:** 268 of 269 passing (1 pre-existing flaky EmailCaptureForm timeout, unrelated)
- Coverage: 90%+ (no regression)

## 4. E2E verification

**Analysis `fc318bc3-3cf9-4f0e-85ee-0f5d61cb77b1` — IN PROGRESS at handoff time (status: `processing`, age: 31.7 min)**

Pipeline reached `form_scoring` (completed 0.1ms) meaning all stages through barbell_tracking are done. `generate_annotated_video`, `generate_angle_plot`, and `upload_artifacts` are still running. The task already exceeded the 1800s streaq timeout by ~100s but survived because `repo.db.commit()` (PR #69) keeps the connection alive.

Earlier E2E attempts this session:
- `7dd59618` — failed with `QueryCanceledError: statement timeout` (lock contention, pre-PR-#69)
- `fe64d814` (from session 37 continued) — timed out at 1800s, timing_json had 3 stages (pre-PR-#68)

Playwright MCP flows walked: upload page → file select → exercise select → upload → redirect to `/analysis/{id}` → status page poll. Console errors: 0. Network 4xx/5xx: not checked (pipeline didn't complete).

## 5. Blockers

**D-035 is root-caused but NOT fixed.** The `track_barbell_from_video` function in `backend/app/cv/barbell_detection.py` takes 24.4 min on a 22.8s 1080p@59fps clip (1345 frames). This blocks every real-user 1080p upload from completing.

**Next session must NOT jump to a quick fix without understanding WHY.** The streaming barbell tracker was specifically designed (session 33, D-034/ADR-056) to avoid memory peaks by reading one frame at a time from disk. It should process 1345 frames in seconds, not minutes. Possible causes to investigate:
- OpenCV `VideoCapture.read()` decoding 1080p H.264 at ~1s/frame instead of ~10ms/frame (codec issue? keyframe distance? container format?)
- Color-space conversion + contour detection at 1080p is O(2M pixels) per frame — possibly ~100ms/frame × 1345 = 134s, not 1465s
- The function may be re-opening the video file or re-seeking per frame (quadratic behavior)
- XNNPACK thread pool from MediaPipe may be contending with OpenCV's internal threading

## 6. Next session start

```bash
/status

# PRIORITY 1: Diagnose WHY track_barbell_from_video is 24.4 min
#   Read backend/app/cv/barbell_detection.py::track_barbell_from_video end-to-end.
#   Look for:
#     - Is it reading sequentially or seeking? (sequential should be fast)
#     - Is there a per-frame OpenCV operation that's O(n^2) on pixel count?
#     - Is it re-opening cv2.VideoCapture per frame? (quadratic decode)
#     - How many frames is it actually processing? (confirm 1345, not more)
#     - Is there accidental frame duplication or retry logic?
#
#   Run a BENCHMARK inside the worker container:
#     docker exec spelix-worker uv run --no-dev python -c "
#       import time, cv2
#       cap = cv2.VideoCapture('/tmp/bench.mov')
#       count = 0
#       start = time.perf_counter()
#       while True:
#           ret, frame = cap.read()
#           if not ret: break
#           count += 1
#       elapsed = time.perf_counter() - start
#       print(f'{count} frames in {elapsed:.1f}s = {elapsed/count*1000:.1f}ms/frame')
#       cap.release()
#     "
#   This isolates "is OpenCV frame read slow?" from "is barbell detection slow?"

# PRIORITY 2: Brainstorm permanent fix WITHOUT compromising bar path quality
#   Options to evaluate:
#     a. Downscale to 480p before tracking (fewer pixels per frame)
#     b. Sample every Nth frame instead of every frame (temporal downsampling)
#     c. Use landmark-based bar path always (skip pixel tracking entirely)
#     d. Run pixel tracking on a subset of frames around detected reps only
#     e. Offload to a background task (don't block pipeline completion)
#     f. Pre-process: ffmpeg downscale → track → scale coordinates back
#   Each option has quality implications for bar path accuracy — evaluate
#   against the Nuckols bar-over-midfoot anchor before choosing.

# PRIORITY 3: Implement the chosen fix, TDD, deploy, E2E verify
#   Expected: pipeline completes in <600s (pose 286s + everything else <300s)
#   If barbell tracking fix brings total under 600s, lower task timeout
#   back from 1800s to 900s and close D-035.

# DO NOT start Priority 3 before Priority 1+2 are complete.
# Upload bench.mov to worker container first:
#   scp e2e/fixtures/atharva-bench-no-weight.mov spelix-droplet:/tmp/bench.mov
#   ssh spelix-droplet "docker cp /tmp/bench.mov spelix-worker-1:/tmp/bench.mov"
```

## 7. Session timing

- 16:30 UTC: PR #68 opened (full-stage telemetry)
- 16:33 UTC: PR #68 merged
- 16:36 UTC: first E2E attempt (analysis `7dd59618`) — failed with lock contention error
- 16:45 UTC: root cause identified (row lock from repo.update blocking fresh-session writes)
- 16:51 UTC: PR #69 opened (repo.db.commit lock fix)
- 17:00 UTC: PR #69 merged + deployed
- 17:03 UTC: final E2E (analysis `fc318bc3`) — timing_json populated with all stages
- 17:13 UTC: first 10 stages visible — all fast (<0.2s each except extract_landmarks)
- 17:18 UTC: barbell_tracking still running at 10+ min
- 17:35 UTC: **barbell_tracking = 1,465,647ms (24.4 min)** — root cause confirmed
- 17:38 UTC: handoff written

Analysis IDs for forensics:
- `7dd59618-2857-4db8-9453-5ceb30f779e3` — lock contention error (pre-PR-69)
- `fc318bc3-3cf9-4f0e-85ee-0f5d61cb77b1` — first complete per-stage timing (THE run)

---

# Session 37 Handoff → Session 38: D-035 culprit narrowed — pose extraction is ~5min (NOT the bottleneck), real bug is in a stage AFTER extract_landmarks (exercise_detection / quality_gates / artifact_generation)

**Context refresh:** Session 37 tried to validate session 36's "bench-vs-prod gap was a workload-transient" hypothesis by running a prod E2E. **The gap reproduces 100%.** First attempt (analysis `31d06d13-8aa7-46f7-98d0-7b64e292651b`) showed `quality_gate_pending` stuck for the full 1800s, `timing_json` still NULL — because session 36's Priority 1 writes went through the main pipeline session, which `analysis_worker.py:1030` rolls back on timeout, wiping every pending write. Root-cause-of-root-cause: telemetry invisible whenever the pipeline actually needs telemetry.

**Fix shipped (PR #66, merge commit `a1a092e`):** new `_persist_timing_telemetry(analysis_id, timing_dict)` helper in `app.services.pipeline` opens a fresh `async_session()`, UPDATEs `analyses.timing_json`, commits immediately. The three early-stage writes (after download, duration_probe, extract_landmarks) now go through this helper — survive rollback. Later 6 writes kept on main-session flow (they're paired with other state changes that commit together).

**Second prod E2E run (analysis `fe64d814-6fe0-4feb-832b-3629f06c9be0`, 2026-04-16 18:03:00 UTC on `atharva-bench-no-weight.mov`):** this time `timing_json` populated in real time. Full result at 1800s task timeout:

```json
{
  "download":          2866.99,    // 2.87 s  - negligible
  "duration_probe":    149.85,     // 0.15 s  - negligible
  "extract_landmarks": 306940.24   // 306.94 s - 5.12 min, within 8% of 287.7s bench baseline
}
```

**Pose extraction is NOT the bottleneck.** It finished at 18:08:26, and the pipeline then spent **24.85 minutes (1800s - 307s = 1493s)** in a stage BETWEEN extract_landmarks and the timeout, with CPU pinned at ~172-192% the entire time. No Python progress log lines visible during that 25-minute gap (worker's log-level filter suppresses INFO from `app.services.pipeline`).

The stages that MUST live in that 25-min black box, in order:
1. `exercise_detection` — heuristic (~100 ms, pure math) + optional GPT-4o fallback (3 vision calls, each ~1-2 min if OpenAI is slow — network-bound, shouldn't pin CPU)
2. `quality_gates` — pure landmark math, fast
3. `compute_angle_timeseries`, `detect_reps`, `extract_rep_metrics`, `compute_session_confidence`, `track_barbell_from_video`, `compute_bar_path_from_landmarks`, `extract_keyframes` — all sub-second each
4. Form scoring (`ScoreComponent` subclasses) — pure math, sub-second
5. **`generate_annotated_video`** — H.264 encoding of 1345 frames @ 1080p with skeleton overlay. Known CPU-heavy per D-034 (the OOM case). Plausible 10-15 minutes on 2-vCPU droplet.
6. `upload_artifact` — network
7. `session.commit()` at line 1020 — never reached

**Prime suspect: `generate_annotated_video`.** It explains both the 24-min wall time AND the CPU pinning. The pipeline likely reached annotation and got stuck encoding frames.

**Additional finding: streaq error handling is broken on timeout.** When streaq cancels a coroutine mid-blocking-call (MediaPipe/OpenCV/H.264 native code), the Python `except` handler in `analysis_worker.py:1025-1057` never runs. Both prod E2E attempts this session ended with `error_message=NULL`, `status='quality_gate_pending'`, `detection_result=NULL`, `quality_gate_result=NULL`. Only the fresh-session `timing_json` writes survived, because they committed before the cancellation.

## 1. Completed

### PR #66 — `fix(pipeline): D-035 telemetry writes survive main-session rollback`
- Merge commit: `a1a092e`
- CI: all 7 checks green including "Deploy to Production"
- Droplet verified: HEAD = `a1a092e`, worker restarted, all containers healthy post-deploy

Commits:
- `4405fd8` fix(pipeline): `_persist_timing_telemetry` helper + 3 call sites + autouse test fixture

**Test count:** backend 1527 passing (+1 from 1526), 19 skipped. No regression.

### Plan for session 37: `docs/superpowers/plans/2026-04-16-session-37-d035-validation-and-triage.md`
- Task 1 (pre-flight) — done
- Task 2 (prod E2E) — done (ran TWICE, both timed out; second one produced the breakthrough `timing_json` data)
- Task 3 (Supabase query) — done (data inline in context refresh)
- Task 4 (worker log walk) — done (logs unhelpful — Python INFO filtered)
- Task 5 (decision) — Branch B (pivot to Tier 2 investigation of the post-extract gap)
- Task 6 (rollback fix, added mid-session when the bug was discovered) — done

## 2. Remaining — highest priority for session 38

1. **Extend `_persist_timing_telemetry` to cover every stage after `extract_landmarks`.** Same fresh-session pattern. Add calls after: `exercise_detection`, `quality_gates`, `compute_angle_timeseries`, `detect_reps`, `extract_rep_metrics`, `compute_session_confidence`, `track_barbell_from_video`, `compute_bar_path_from_landmarks`, `extract_keyframes`, form scoring, `generate_annotated_video`, `generate_angle_plot`, `upload_artifact`. Each stage gets its own named timer block.
2. **Re-run E2E.** Expected outcome: timing_json reveals the one stage eating 24 minutes. Hypothesis: `generate_annotated_video`.
3. **Only then decide the fix.** Don't plan the fix before the data lands.

### Known deferred (unchanged)
- D-028, D-029, D-030, D-031
- D-032 (quality gate false rejections)
- D-034 (pipeline OOM on 1080p annotation — may be the SAME root cause as D-035 once we confirm)
- D-036 (GPU offload) — remains deferred post-beta

## 3. Test counts

- **Backend:** 1527 passing, 19 skipped, 0 failing (+1 from session 36 end).
- **Frontend:** unchanged (1 pre-existing flaky).
- Coverage: 90%+ no regression.

## 4. E2E verification

Two runs this session, both timed out at 1800s:
- `31d06d13-8aa7-46f7-98d0-7b64e292651b` (pre-PR #66) — `timing_json=NULL` (rollback bug)
- `fe64d814-6fe0-4feb-832b-3629f06c9be0` (post-PR #66) — `timing_json` populated with first 3 stages (see above)

## 5. Blockers

**D-035 root cause is still open** — we now know pose extraction is fine, the culprit is a later stage. The 25-minute gap is unambiguous but the specific stage is not. Session 38 priority 1 closes that.

**Streaq error-handling on timeout is broken** (secondary finding). When streaq kills the coroutine mid-native-call, Python's except never runs and the analysis row stays in `quality_gate_pending` with NULL fields. Frontend shows "Preparing to analyse…" forever. This affects UX but is downstream of the real bug. Address after D-035 closes.

## 6. Next session start

```bash
/status

# PRIORITY 1: Extend _persist_timing_telemetry to every stage after extract_landmarks
#   Same fresh-session pattern from PR #66. Add a timer.stage("<name>") block around
#   each CV call in pipeline.py that doesn't already have one, then call the helper
#   immediately after the block closes.
#   Stages to instrument (in order):
#     exercise_detection, quality_gates, compute_angle_timeseries, detect_reps,
#     extract_rep_metrics, compute_session_confidence, track_barbell_from_video,
#     compute_bar_path_from_landmarks, extract_keyframes,
#     form_scoring, generate_annotated_video, generate_angle_plot, upload_artifact
#   Branch: fix/d035-full-stage-telemetry
#   TDD gate: add one unit test that patches _persist_timing_telemetry and asserts
#   it's called with a key set containing ALL expected stage names by the end of
#   the pipeline (happy path).

# PRIORITY 2: Re-run E2E on atharva-bench-no-weight.mov
#   Expected: timing_json fully populated at task timeout, one stage eating ~24 min.
#   Hypothesis: generate_annotated_video.

# PRIORITY 3: Based on the winning stage — decide the fix
#   - If generate_annotated_video: resize to 720p before encode (per D-034 ADR-056 plan a),
#     or skip annotation for clips >20s, or defer annotation to a separate streaq task
#     with its own timeout and non-blocking status update.
#   - If exercise_detection GPT-4o fallback loop: lower retry count, add a hard
#     wall-clock timeout on classify_exercise, or accept low-confidence heuristic
#     result without fallback when clip is short.
#   - If something unexpected: diagnose then fix.

# SECONDARY: streaq timeout -> row never updated. Fix in analysis_worker.py error
#   handler OR add a fresh-session "status=failed + error_message" write inside
#   _persist_timing_telemetry whenever called (so at least partial state lands).
#   NOT blocking — the telemetry approach gives us visibility without it.
```

## 7. Session timing

- 13:02 UTC: session 37 plan written (`docs/superpowers/plans/2026-04-16-session-37-d035-validation-and-triage.md`)
- 13:15-13:26 UTC: first E2E (analysis `31d06d13`) — timed out at 14:46, `timing_json=NULL`
- 13:28 UTC: root cause identified (rollback wipes telemetry), fix branched
- 13:51 UTC: PR #66 opened (fix/d035-telemetry-survives-rollback)
- 13:59 UTC: PR #66 merged
- 14:02 UTC: second E2E (analysis `fe64d814`) — timed out at 14:33, timing_json HAD DATA for the first time
- 14:37 UTC: session 37 findings compiled

---

# Session 33 Handoff → Session 34: L2 Sprint Day 6 — Phase 3 agent prod-watch complete, 4 quality-gate bugs surfaced + timeout fix shipped
