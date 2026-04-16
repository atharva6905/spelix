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
