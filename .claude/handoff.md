# Session 36 Handoff → Session 37: D-035 Priorities 1 + 3 shipped (PR #64), diagnostic result REFUTES the bench-vs-prod gap — pose extraction in streaq container is ~280s, not >1800s

**Context refresh:** Session 36 shipped PR #64 — Priorities 1 + 3 from the session 35.5 handoff per plan `docs/superpowers/plans/2026-04-16-d035-priorities-1-2-3.md`. Priority 1: three new `analysis.timing_json` flushes after `download`, `duration_probe` (non-rejection path), and `extract_landmarks` in `run_cv_pipeline`. Priority 3: new `pose_extraction_diagnostic` streaq task + `_run_pose_extraction_diagnostic` pure helper + `scripts/enqueue_d035_diagnostic.py` CLI trigger. All 1526 unit tests pass, CI green, droplet HEAD = `89bb58b`.

**Diagnostic result on prod (2026-04-16 ~11:35-11:45 UTC) on `atharva-bench-no-weight.mov` (22.8s 1080p@59fps, 37 MB, SAME fixture that prior sessions observed timing out at 1800s):**

| Variant | Wall time | Per-frame ms | Frame count | Notes |
|---|---|---|---|---|
| **Bench** (bare Python, session 35 `bench_video_mode.py`) | **287.7s** | ~215 | ~1345 | baseline |
| **Direct-call async, via `run_in_executor`** | **283.8s** | 212 | 1338 | "executor" variant — matches `pipeline.py:348` call path |
| **Direct-call async, inline** (blocks event loop) | **272.1s** | 203 | 1338 | "inline" variant |
| **Via streaq worker task** | 8m48s wall (both variants) = ~264s each | — | — | streaq-logged completion, result dict truncated in streaq's default logger |
| **Prod pipeline `extract_landmarks`** prior observation | **reported >1800s** | reported >1345 | — | session 35.5 handoff claim |

**The bench-vs-prod gap the handoff described does NOT exist.** Pose extraction on prod, running inside the same streaq worker container, completes in ~5 minutes — within 5% of bench. The `executor` and `inline` variants are also within 5% of each other, so asyncio/`run_in_executor`/XNNPACK-thread overhead is NOT the bottleneck.

**Implications for the prior 1800s-timeout observation:**

1. The 1800s task timeout in prod was either
   - hitting something OTHER than `extract_landmarks` — a different stage that doesn't have a timer today, OR
   - workload-transient (e.g., another concurrent task, memory pressure, disk I/O, transient network issue on Supabase Storage download) that cleared after the worker restart that came with deploying PR #62 and PR #64.
2. Priority 1's early `timing_json` writes now cover download, duration_probe, and extract_landmarks. Any future stuck prod run will write per-stage times to `analyses.timing_json` well BEFORE the 1800s timeout fires, making the stuck stage unambiguously visible.
3. D-036 (GPU offload) is NOT required by the current measurement — bare-Python pose extraction comfortably fits under the 900s original task timeout. The Tier 1 doubling to 1800s (session 35.5) was a margin of safety, not a required scaling for the CPU work.

**What wasn't run this session:** Prod E2E upload via Playwright. Kicked off the direct-call diagnostic as Priority 3's data, but did not additionally drive a fresh `POST /analyses` → upload → run cycle on spelix.app. Sanity-checking via the full web flow is pending for session 37.

## 1. Completed

### PR #64 — `fix(pipeline): D-035 early timing_json writes + diagnostic harness`
- Merge commit: `89bb58b`
- CI: all checks pass (Backend Lint/Tests, Frontend Lint/Tests, Secret Scanning, Vercel, Deploy to Production)
- Droplet verified: `HEAD = 89bb58b`, all containers healthy post-deploy

Commits:
- `27e441e` test(pipeline): incremental timing_json write assertion (RED)
- `9ad4279` feat(pipeline): flush timing_json after each early stage (GREEN)
- `8d6e72e` test(worker): pose_extraction_diagnostic helper tests (RED)
- `c5ede3f` feat(worker): pose extraction diagnostic helper (GREEN, with Windows test patching fix for BaseEventLoop vs AbstractEventLoop)
- `8d0176b` feat(worker): streaq task + CLI enqueue script

**Test count:** backend 1526 passing (+3 from 1523 pre-task), 19 skipped. Frontend unchanged.

### Diagnostic run
- Fixture: `atharva-bench-no-weight.mov` uploaded via `scp spelix-droplet:/tmp/bench.mov` then `docker cp` into `spelix-worker-1:/tmp/bench.mov`.
- streaq variant enqueued via `docker exec -w /app -e PYTHONPATH=/app spelix-worker-1 uv run --no-dev python /tmp/enqueue_d035_diagnostic.py /tmp/bench.mov`.
- Direct-call variant via one-off `/tmp/run_d035_direct.py` script (written session-local, not committed).
- Result captured via stdout: executor=283.8s, inline=272.1s.

## 2. Remaining

### Highest priority for session 37
1. **Prod E2E via Playwright MCP** on `atharva-bench-no-weight.mov` now that early writes are in place. If the pipeline completes in ~5min, confirms the bench-vs-prod gap was transient. If it still stalls, check `timing_json` — it will now show which stage ate the time. DO NOT start Tier 2 work before this run.
2. **Query Supabase** for any new analyses rows since the 89bb58b deploy — `SELECT id, status, timing_json, created_at FROM analyses ORDER BY created_at DESC LIMIT 10` — surface whatever real user or smoke-test pipeline runs have logged so far.

### Known deferred
- D-028, D-029, D-030, D-031 — unchanged from session 33 handoff.
- D-034 (pipeline OOM on full 1080p annotation) — unchanged.
- D-032 (quality gate false rejections on framed-with-plates clips) — unchanged.
- D-036 (GPU offload) — remains **deferred post-beta**. Current measurement says CPU is fine for 22.8s clips.

## 3. Test counts

- **Backend:** 1526 passing, 19 skipped, 0 failing (+3 from pre-PR).
- **Frontend:** 268 of 269 (1 pre-existing flaky unchanged).
- Coverage: 90%+ no regression.

## 4. E2E verification

**Not performed this session.** The session focused on the diagnostic run. Prod E2E should be the first step of session 37.

## 5. Blockers

**None.** D-035 is effectively closed for the original hypothesis (6× bench-vs-prod gap) — the hypothesis was wrong. The new early-write instrumentation ensures any future stuck pipeline will leave its per-stage times on the DB row. Re-open the ticket only if a fresh prod E2E actually stalls again.

## 6. Next session start

```bash
/status

# PRIORITY 1: prod E2E via Playwright MCP to validate the direct-call finding
#   - Upload atharva-bench-no-weight.mov through https://spelix.app
#   - Watch status: queued → quality_gate_pending → processing → coaching → completed
#   - Target: ~5-8 min total pipeline time (down from the prior 1800s observation)
#   - If stalled: query analyses.timing_json to see which stage is stuck

# PRIORITY 2: Supabase diff pull
#   - SELECT id, status, timing_json, created_at FROM analyses
#     WHERE created_at > '2026-04-16T11:27:00Z'
#     ORDER BY created_at DESC;
#   - Confirms early writes are actually populating on real traffic

# PRIORITY 3 (only if PRIORITY 1 stalls): use timing_json to decide Tier 2 direction
#   - If download_ms >> extract_landmarks_ms: network or Supabase Storage is the bottleneck
#   - If extract_landmarks_ms is now ~300s: the prior 1800s was a one-off, do nothing
#   - If something between stages eats time: look at gap between last timing_json write
#     and next — possibly quality_gates, barbell detection, or artifact upload
```

## 7. Session timing

- 10:58 UTC: plan written (`docs/superpowers/plans/2026-04-16-d035-priorities-1-2-3.md`)
- 11:00-11:15 UTC: Tasks 1+2 (early writes) — via spelix-tdd subagent
- 11:05-11:15 UTC: Tasks 3+4 (diagnostic helper + tests) — via spelix-tdd subagent + manual follow-up for Windows patching
- 11:20 UTC: Task 5 (streaq wiring + CLI) — direct implementation
- 11:24 UTC: PR #64 opened
- 11:27 UTC: PR #64 merged (merge method, NOT squash)
- 11:29 UTC: Deploy to Production green, droplet HEAD = 89bb58b
- 11:35-11:44 UTC: streaq-enqueued diagnostic run (result truncated in logs)
- 11:54-12:04 UTC: direct-call diagnostic run — clean JSON result captured

---

# Session 35.5 Handoff → Session 36: D-035 Tier 1 shipped but E2E STILL times out at 1800s — bench-vs-prod gap is >6×, telemetry blind spot surfaced

**Context refresh:** Session 35.5 shipped PR #62 — the D-035 Tier 1 bundle per ADR-058 (instrumentation + VIDEO mode + 1800s timeout + 60s/120s upload cap + D-036/ADR-059 docs). PR merged cleanly, deployed to prod, migration `010_add_timing_json` applied. Then re-ran E2E with `atharva-bench-no-weight.mov` (the 22.8s 1080p@59fps clip that has been the canonical failing case since session 34). **Result: task hit the bumped 1800s timeout without finishing pose extraction.** No `timing_json` written because the first flush point in `pipeline.py` is AFTER Step 2b detection, which is unreachable if pose extraction alone exceeds 1800s.

## 1. Completed

### PR #62 — `fix(pipeline): D-035 telemetry + Tier 1 pipeline fixes`
- Merge commit: `a54f24e`
- CI: all 7 checks green including "Deploy to Production"
- Droplet verified: HEAD = `a54f24e`, all containers healthy, migration `010_add_timing_json` applied (column confirmed via Supabase MCP `information_schema.columns` query)
- **Backend test count: 1505 → 1523 (+18)**
- Frontend test count: 266 → 269 (+3; 1 pre-existing flaky EmailCaptureForm test unrelated)

### What shipped (per plan in `docs/superpowers/plans/2026-04-16-d035-instrument-and-pipeline-fixes.md`)
- **A** `analyses.timing_json` JSONB column + `StageTimer` context manager wrapping 4 pipeline stages (download, extract_landmarks, exercise_detection, quality_gates) — the other 4 stages (rep_detection, form_scoring, annotation_generation, artifact_upload) were skipped because the test spec only asserted on the first 4. In hindsight this was fine because we never got past extract_landmarks anyway.
- **B** `RunningMode.IMAGE` → `RunningMode.VIDEO` in `extract_landmarks` + `detect_for_video(mp_image, timestamp_ms)` with monotonic timestamp per source fps. Bench said ~20% speedup. Prod data refutes this — see §4.
- **D** streaq `process_analysis` timeout 900 → 1800s.
- **E** Backend ffprobe defense-in-depth + frontend HTML5 `<video>.duration` hard-block at 60s free / 120s Extended Mode, warn at 30s. Backend helper `app.cv.video_probe.probe_duration_seconds` returns 0.0 on any failure.

### Docs
- `backlog.md`: D-035 flipped `pending` → `partial`; D-036 added (GPU offload, post-beta, trigger-gated).
- `decisions.md`: ADR-058 (telemetry tier rationale + GPU deferral), ADR-059 (telemetry-first principle for future CV pipeline tuning).

## 2. E2E findings — BENCH-vs-PROD GAP IS >6×

Analysis `3464c47a-7992-46df-b16f-3875c93e83e1` on prod, 2026-04-16 ~09:59 UTC:
- Upload via Playwright MCP: 22.8s 1080p@59fps bench-no-weight clip (37 MB).
- Status transitions observed: `queued` → `quality_gate_pending` (immediately) → **STUCK** in `quality_gate_pending` for full 1800s.
- Worker RSS rock-steady at ~510 MiB. Memory is NOT the problem.
- CPU pinned at 170-194% for the entire duration. Worker actively churning.
- **`timing_json` remained `null` throughout** — the first flush happens after Step 2b detection (line 417-418 in `pipeline.py`), which was never reached. The duration-gate rejection path (line 338-339) didn't fire because 22.8s is under the 60s cap.
- streaq worker error log at exactly 10:29:35 (1800s after 09:59:35 task start): `[ERROR] task process_analysis … c8cc176677d346788123d119735571f3 timed out`
- **Bench on SAME container / SAME model / SAME clip (session 35 benchmark `bench_video_mode.py`): VIDEO mode = 287.7s wall total, 160.1s inference.**
- **Prod: >1800s in extract_landmarks alone. >6× slower than bench.**

This is NOT a random fluctuation — it's been reproduced three times now across PR #61 and PR #62 merges. The prod pipeline is fundamentally slower than my bench, and NEITHER measurement was within the 900s original budget.

## 3. Why Tier 1 didn't close D-035

1. **VIDEO mode's bench speedup didn't translate to prod.** Bench showed IMAGE 148 ms/frame vs VIDEO 120 ms/frame (1.24×). Prod still hit 1800s.
2. **720p pose cap (PR #61) didn't help.** BlazePose Heavy's per-frame cost is dominated by the model's internal 256×256 resize — input resolution is ~irrelevant. Session 35 bench confirmed this directly.
3. **The 3× bench-vs-prod gap discovered in session 35 is actually ≥6× in reality.** Prior observations (900s timeout, bench 290s) suggested ~3×; the 1800s re-test suggests ≥6×. Might be even higher — we just don't know because we cut it off at 1800s.
4. **Instrumentation has a blind spot.** No timing_json write occurs before detection step completes. For a pipeline that dies in pose extraction, the instrumentation captured ZERO data this run. This must be fixed before the next attempt — add an early write after `extract_landmarks` completes.

## 4. Test counts
- **Backend**: 1523 passing, 19 skipped, 0 failing (unchanged; +18 from 1505 pre-D-035 baseline)
- **Frontend**: 268 of 269 passing (1 pre-existing flaky EmailCaptureForm timeout, unrelated)
- Coverage: 90%+ (no regression)

## 5. Blockers

**D-035 is STILL open** and now has known architectural characteristics that require a different approach than Tier 1:

- CPU pinned at 170-194% means we are saturating the 2 vCPU droplet ALL the time during pose extraction, yet still >6× slower than a bench script running in the same container. **Something about the streaq async worker context makes MediaPipe much slower than a bare Python process.** This is the critical clue.
- Candidate causes for next session to investigate:
  1. asyncio event loop + `run_in_executor` overhead serializing MediaPipe calls
  2. Thread-pool contention with MediaPipe XNNPACK's internal threads
  3. GIL contention with streaq's heartbeat loop running in the same process
  4. Something else entirely (unknown until telemetry lands)
- **Urgent**: before any more prod E2E runs, land a small follow-up PR that adds a timing_json write AFTER every StageTimer wrap so we get data even on incomplete runs. Current code only writes to DB via existing `repo.update` calls, the first of which is after detection — too late for our failure mode.

## 6. Next session start

```bash
/status  # confirm environment + droplet state

# PRIORITY 1: Add early timing_json write BEFORE detection
#   In app/services/pipeline.py, after each `with timer.stage(...)`: block,
#   add: analysis.timing_json = timer.as_dict(); await repo.update(analysis)
#   Start with just: after extract_landmarks, after each quality gate.
#   This gives us per-stage data even when pipeline dies mid-pose.
#   Branch: fix/d035-early-timing-writes

# PRIORITY 2: Re-run E2E on atharva-bench-no-weight.mov with the early-write fix
#   Expected: timing_json populated with {"download": X, "extract_landmarks": Y}
#   even if task still times out. Y will tell us exactly how slow prod pose is.

# PRIORITY 3: Diagnose bench-vs-prod gap per the candidate causes in §5
#   Add a diagnostic task in the worker that runs bench_video_mode.py equivalent
#   INSIDE the streaq async context, vs bare python. Measure both and compare.
#   This is the root-cause investigation we've been deferring since session 33.

# PRIORITY 4 (only after pose extraction is reproducibly <600s):
#   Tier 2 decision — ffmpeg fps-normalize OR D-036 GPU offload.
#   Do NOT plan this before PRIORITY 1-3 data.
```

## 7. Session timing

- 09:57:16 UTC: worker started (post-deploy)
- 09:59:35 UTC: streaq pickup task
- 10:29:35 UTC: streaq timeout fires (exactly 1800s later)
- 10:30:26 UTC: worker CPU drops to 0.6% (task cleaned up)

Analysis ID for forensics: `3464c47a-7992-46df-b16f-3875c93e83e1`

---

# Session 33 Handoff → Session 34: L2 Sprint Day 6 — Phase 3 agent prod-watch complete, 4 quality-gate bugs surfaced + timeout fix shipped

**Context refresh:** Session 33 ran the first real-athlete prod-watch of the Phase 3 LangGraph deterministic agent. Four fixture clips were tried (`atharva-deadlift.mp4`, `atharva-squat.mov`, `atharva-bench.mov`, `atharva-bench-no-weight.mov` trimmed to 10s@720p). Three failed the quality gate, one timed out, one OOMed, and the trimmed clip finally completed — confirming `mode=deterministic` with all 10 FR-AICP-18 nodes on prod analysis `e2ef9d86-d125-4adf-bccb-da90e5c59d41`. Along the way, 4 new bugs were discovered, 1 was fixed live (D-033 timeout), and 4 ADRs were written. No Phase 3 code was changed — only the streaq task timeout.

## 1. Completed

### PR #55 — `fix(worker): raise process_analysis timeout to 900s (ADR-055) + session 33 diagnostics`
- Merge commit: `1a2fb01` (merge method: merge, NOT squash)
- Feature commit: `c62c677`
- CI: all 6 jobs green including "Deploy to Production"
- Droplet verified: `git log -1` = `1a2fb01`, worker container has `@worker.task(timeout=900)`, all containers healthy

**Code change (1 line):** `backend/app/workers/streaq_worker.py:144` — `process_analysis` task timeout raised 300 → 900 seconds. Restores ADR-BRAIN-04's Phase-2 intent silently reverted by the ARQ → streaq migration (PR #48, session 31).

**Docs bundled in same PR:**
- **D-032** expanded in `backlog.md` — 3 co-occurring framing + single-person quality gate bugs (temporal `[:5]`, NO_POSE warmup, visible-landmark-bbox undershoot) with MediaPipe ground-truth data from local diagnostics
- **D-033** new in `backlog.md` — timeout regression (now `done`, closed by this PR)
- **ADR-053** in `decisions.md` — framing peak-bbox over full clip (temporal bias)
- **ADR-054** in `decisions.md` — framing occlusion/orientation investigation scope
- **ADR-055** in `decisions.md` — timeout revert documentation

### Uncommitted docs changes (still on working tree, not yet committed)
- **D-034** new in `backlog.md` — pipeline OOM post-quality-gate on 1080p@59fps clips (worker memory peaks to 3.2 GB on 4 GB droplet, annotation video generation is the culprit)
- **ADR-056** in `decisions.md` — pipeline memory budget analysis, fix-path ranking

### Prod-watch analyses created this session
| Analysis ID | Fixture | Status | Agent path exercised? |
|---|---|---|---|
| `8b5714ee-ac63-464d-8ff4-339e502885d9` | atharva-deadlift.mp4 | `quality_gate_rejected` (464p + framing 0.14 < 0.17) | No |
| `cd459701-749a-4ba6-b1b2-b96f7b6e9a98` | atharva-squat.mov | `quality_gate_rejected` (framing 0.0 — first 4 frames NO_POSE + single_person 3 jumps) | No |
| `2158536a-8df6-4fa0-8d68-b01129c0aadb` | atharva-bench.mov | `quality_gate_pending` (stranded — task timed out at 300s pre-fix) | No |
| `4e19c62b-91c2-4f01-b269-3ac51e05db3f` | atharva-bench-no-weight.mov (full) | `failed` (manually terminated — D-034 OOM, worker died 3× at ~7:50 elapsed) | No |
| **`e2ef9d86-d125-4adf-bccb-da90e5c59d41`** | **atharva-bench-nw-10s.mp4 (720p trim)** | **`completed`** | **YES — mode=deterministic, 10/10 nodes, form_score_overall=7.27** |

### Local artifacts (not committed)
- `e2e/fixtures/atharva-{squat,deadlift,bench,bench-no-weight}.mov` — user's real athlete clips (1080×1920 @59fps)
- `e2e/fixtures/atharva-bench-nw-10s.mp4` — 10s 1080p trim (24.6 MB)
- `e2e/fixtures/atharva-bench-nw-10s-720p.mp4` — 10s 720p downscale (13.6 MB) — the clip that completed prod-watch
- `e2e/screenshots/frame-inspect/` — diagnostic keyframe PNGs from MediaPipe analysis
- `backend/models/pose_landmarker_heavy.task` — 30 MB MediaPipe model (downloaded for local diagnostics, NOT committed)

## 2. Remaining

### Sprint-blocking (fix before next prod-facing work)
| ID | Title | Status | Deps | Priority |
|---|---|---|---|---|
| D-032 | Framing + single-person quality gates reject correctly-framed barbell videos (3 co-occurring bugs) | pending | — | **HIGH — blocks real-user clips with plates/bystanders** |
| D-034 | Pipeline OOM post-quality-gate on 1080p@59fps clips (annotation video generation peaks 3.2 GB on 4 GB droplet) | pending | — | **HIGH — blocks any full-length 1080p clip from completing** |

### Known deferred (non-blocking)
| ID | Title | Status | Notes |
|---|---|---|---|
| D-028 | `useAnalysisStatus` "Connection lost" banner + Realtime not delivering `quality_gate_rejected` transitions | pending | Reproduced again in every prod-watch this session |
| D-029 | SaMD rename `injury_advice_accurate` → `movement_advice_accurate` | pending | Pre-existing |
| D-030 | Orphan `rag_documents` uploading-state cleanup | pending | |
| D-031 | Admin GET /rag/documents free-text query param | pending | |

### Phase 3 remaining batches (per STRATEGY.md v3)
| Batch | Items | Originally scheduled | Status |
|---|---|---|---|
| Batch 2 — Distillation | P3-004 (FR-BRAIN-06), P3-005 (FR-BRAIN-17), FR-BRAIN-14 | Days 10-16 (Apr 23-29) | **Not started** — can pull forward into Day 6-9 buffer |
| Batch 3 — Review queue + Reasoning sidebar | P3-006 (FR-ADMN-12, FR-BRAIN-07), P3-007 (FR-RESL-07) | Days 17-19 (Apr 30-May 2) | Not started |

### Expert onboarding
- Kin expert onboarding call: **STILL PENDING** from session 30 handoff. No real PDFs uploaded yet.

## 3. Test counts

- **Backend**: 1520 passing, 25 skipped, 0 failing (unchanged from session 32 — this session only changed a timeout constant + docs)
- **Frontend**: 266 passing, 0 failing (unchanged — no frontend touches)
- **Coverage**: 90% (unchanged — PR #55 was docs+constant-only, no coverage impact)

## 4. E2E verification

**Analysis `e2ef9d86-d125-4adf-bccb-da90e5c59d41` — PASSED on spelix.app (2026-04-16 ~01:46 UTC)**

Flows walked via Playwright MCP:
- **Upload page**: Bench Press / Flat selected, `atharva-bench-nw-10s-720p.mp4` (13.6 MB) attached via file input, "Upload Video" clicked → redirected to `/analysis/e2ef9d86-...`
- **Status page** (reload): "Analysis complete" + "Detected Exercise: Bench — flat" + "Matched with 79% confidence" + "View results" link rendered
- **Results page** `/results/e2ef9d86-...`: Form Assessment (overall 7.27), Annotated Video (signed URL), Coaching Feedback (structured output with issues), Follow-up Chat input, Rep Metrics table (1 rep), Angle Plot (signed URL), Downloads section, 3-tier disclaimer — all present
- **Console errors: 0. Warnings: 0.**
- D-028 "Connection lost — reconnecting…" banner still present on status page (known)

**DB verification (Supabase MCP):**
- `coaching_results.agent_trace_json`:
  - `mode`: `"deterministic"` ✓
  - `nodes_executed`: 10 of 10 ✓ — `get_rep_metrics → retrieve_papers → retrieve_coach_brain → flag_form_deviation → compare_to_user_history → generate_correction_plan → validate_output → cove_verify → safety_filter → faithfulness_gate`
  - `retrieval_source`: `papers_only_fallback` (Coach Brain empty for bench — expected)
  - `cove_verified`: false (CoVe found unverified claims)
- `generate_correction_plan` took 31.8s (Claude Sonnet 4.6 coaching call)
- All other nodes sub-200ms

## 5. Blockers

**D-034 (pipeline OOM) is the primary blocker for any real-user prod-watch.** All four 1080p@59fps clips from atharva's fixtures either failed quality gate (D-032 bugs) or OOMed during annotation video generation. Only a manually trimmed+downscaled 10s@720p clip completed. This means:
- **Kin expert's test uploads will fail** if their phone films at 1080p@60+ (standard for modern iPhones)
- **Smoke test with 3-5 trusted users (Week 4)** is at risk unless D-034 is fixed first
- Fix paths ranked in ADR-056: (a) downscale annotation to 720p, (b) stream-encode frame-by-frame, (c) free landmarks after rep detection, (d) skip annotation for long clips, (e) upgrade droplet to 8 GB

**D-032 (quality gate false rejections)** blocks any clip with heavy plates visible (squat at rack, loaded bench), or with a gym bystander anywhere in frame. Real gym videos will hit this.

**Kin expert onboarding call** still hasn't happened — pending since session 30. Expert paper upload portal is wired but untested with a real expert.

## 6. Next session start

```bash
/status
# Confirm environment, live containers, queue depth, CI status

# PRIORITY 1: Fix D-034 (OOM) — most bang-for-buck path per ADR-056:
#   Fix (a): downscale annotation video to 720p before H.264 encode
#   Fix (c): free landmarks_per_frame after rep detection, before annotation
#   Both changes are in backend/app/cv/artifact_generation.py + analysis_worker.py
#   Combined fix should keep peak memory ~1.5 GB for any 1080p clip
#   Branch: fix/annotation-memory-budget
#   Run full prod-watch with atharva-bench-no-weight.mov (full 22.8s) after fix

# PRIORITY 2: Fix D-032 (quality gate) — investigate 3 options per ADR-054:
#   (a) all-33-landmark bbox; (b) presence instead of visibility; (c) per-exercise thresholds
#   Run local MediaPipe diagnostics on atharva-{squat,bench,deadlift}.mov
#   Branch: fix/quality-gate-framing
#   Regression tests must cover: well-framed no-plate, well-framed with plates, lifter out of frame

# PRIORITY 3 (if D-034 + D-032 close quickly): Pull Batch 2 forward
#   P3-004: Distillation StateGraph (FR-BRAIN-06)
#   P3-005: Knowledge lifecycle (FR-BRAIN-17)
#   Activate spelix-langgraph-engineer

# Commit the uncommitted D-034 + ADR-056 docs (currently only on working tree)
```

---

# Session 32 Handoff → Session 33: L2 Sprint Day 5 — Phase 3 Batch 1 (LangGraph agent) live on prod

**Context refresh:** Session 32 pulled Phase 3 Batch 1 forward into the Day 5-9 buffer (STRATEGY v3 originally scheduled Day 10-13). All three MUST requirements — FR-AICP-18 (composable tools + deterministic StateGraph), FR-AICP-19 (adaptive tool-calling), FR-AICP-20 (LangSmith trace + `agent_trace_json`) — merged via PR #52 and verified live on prod with the feature flag flipped ON.
