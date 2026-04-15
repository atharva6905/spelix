# Session 28 Handoff → Session 29: Droplet OOM permanently fixed, Phase 2 fully stable for L2 beta

## 1. Completed

### Session 28 PR merged
| PR | Commit | Title | Notes |
|----|--------|-------|-------|
| #41 | `3fb1269` merged as `181c754` | `docs: ADR-048 droplet sized to s-2vcpu-4gb for L2 beta, close D-026` | Docs-only — infrastructure change already live |

### Session 27 PRs merged (earlier in conversation, captured for continuity)
| PR | Commit | Title |
|----|--------|-------|
| #37 | `b86d07e` | `fix(pdf): add reports/templates bind mount to Docker compose (D-022)` |
| #38 | `2fbec9f` | `fix(pdf): resolve template path via CWD fallback for Docker (D-022)` |
| #39 | `6fde5e1` + `b7b6b1f` | `fix(rag,db): idempotent Qdrant indexes + enable Realtime on analyses (migration 007)` |
| #40 | `a586a58` | `docs(decisions,backlog,handoff): session 27 — Phase 2 gate, PDF/Qdrant/Realtime fixes` |

### Infrastructure operations applied directly to production (non-code)
| Op | When | Evidence |
|----|------|----------|
| Snapshot `spelix-pre-resize-session27` | DO action `3139971337` completed `2026-04-15T01:08:37Z` | Rollback insurance; delete after 7 days of stable runtime |
| Droplet resize `s-1vcpu-2gb` → `s-2vcpu-4gb` | DO action `3139981555` completed `2026-04-15T01:16:43Z` | +$12/mo ($24/mo total). Disk expanded 50GB → 77GB. |
| Datadog agent purged | root SSH `2026-04-15T01:20Z` | `apt-get remove --purge datadog-agent datadog-installer datadog-signing-keys` — 0 processes remaining, 181 MB RAM freed |
| Qdrant `coach_brain` payload indexes re-verified | inline Python on worker container | `exercise` + `status` both present on all 24 seed points |

### Backlog items closed/updated this session
- **D-022** (PDF template in Docker) — closed earlier via #37+#38
- **D-026** (Droplet OOM during concurrent analyses) — **closed**; see ADR-048 and infra ops above
- **D-028** (Cosmetic "Connection lost" banner after terminal-state unsubscribe) — **opened** (new)

### ADRs written this session
- **ADR-048**: Droplet Sizing for L2 Private Beta — Basic 2 vCPU / 4 GB

## 2. Remaining

Backlog items still `pending` after this session (`backlog.md` at repo root is authoritative):

| ID | Title | Size | Deps status |
|----|-------|------|-------------|
| **D-027** | Apply migration `007_enable_realtime_analyses` via `alembic upgrade head` — prod state already matches (applied via Supabase SQL console) but alembic_version table still at 006 | S | No deps — runnable now |
| **D-028** | Cosmetic: `useAnalysisStatus` shows "Connection lost — reconnecting…" after intentional unsubscribe on terminal state | S | No deps — UI-only fix in `frontend/src/hooks/useAnalysisStatus.ts` |
| **D-017** | Replace AI-synthesized paper text in `papers_rag` with real full-text PDFs via Docling ingestion | L | Depends on `P2-007` (✅ done). Quality improvement for RAG evals. |
| **D-004..D-010** | Session 13 tech debt (doubled `videos/` storage prefix, test fixture quality, tests-mock-everything anti-pattern doc, CI factory-coverage, etc.) | S/M | No deps — opportunistic cleanup |
| **P3-001..P3-007** | Phase 3 LangGraph agent orchestration (8 Must FRs) | M–XL | **Deferred until post-Saturniq (mid-August 2026)** per STRATEGY.md |

## 3. Test counts

- **Backend**: 1443 tests collected, all passing (last full run on `main@66a81a7` via CI — see PR #39 "Backend Tests: success")
- **Frontend**: 225 tests, all passing (local run after Datadog removal, 2026-04-15 ~21:35 UTC)
- **Coverage**: Last recorded **91%** at Phase 1 gate; not re-measured this session (docs + infra only — no code delta)
- **Known failures**: None

## 4. E2E verification

**Analysis `41a88ec8-7dbf-4909-8ca6-9951fd48cfbd` — PASSED against spelix.app (2026-04-15 01:22–01:26 UTC)**

Affected flows walked:
- Upload page: Squat / High Bar selection, file picker, test-squat.mp4 (8.1 MB) ✅
- TUS upload to Supabase Storage ✅
- **Realtime status page live-updated** from "Preparing to analyse…" → "Analysis complete" (no poll fallback) ✅
- Detection result shown: "Squat — high bar — Confirmed by vision analysis" (GPT-4o fallback) ✅
- Results page: 2 reps, 4-dimension scores (Overall 6.7, Movement Quality 5.0, Technique 10.0, Path & Balance 3.6, Control 10.0) ✅
- Coaching: summary, 3 strengths, 4 issues, 5 corrections, 5 cues, 4 citations, degraded-mode disclaimer ✅
- Annotated video (signed URL, H.264) + angle plot (signed URL) ✅
- CSV download + **PDF Report download** (D-022 end-to-end confirmed) ✅
- Three-tier disclaimer present ✅
- **Console errors: 0. Console warnings: 0.** No failed network requests observed.

Droplet-health evidence captured during + after analysis:
- Memory PSI `full` = 0.00 across all windows (was elevated before resize)
- CPU PSI `full` = 0.00 across all windows
- Swap used during full analysis: 524 KB (was 400+ MB before)
- SSH fully responsive throughout (was timing out at banner exchange before)
- Analysis wall-clock: ~150s (was 200s+ on single-vCPU droplet) — MediaPipe now uses both cores (111.87% CPU observed)

Residual observations (logged as backlog items, not blockers):
- **D-028**: "Connection lost — reconnecting…" banner flashes briefly on the status page AFTER the terminal UPDATE arrives — cosmetic only, results render correctly.
- **Retrieval `Retrieval failed — coaching without contexts (degraded mode)` message in worker logs**: occurred during this analysis but pipeline fell through to ungrounded coaching gracefully (FR-AICP-15 fallback working). Qdrant `exercise` + `status` indexes verified present on `coach_brain` — root cause of this particular retrieval failure not yet re-investigated.

## 5. Blockers

**None blocking Phase 2 stability or L2 beta launch.**

Open items worth flagging for next session:
1. **D-027** (alembic head sync) — trivial but housekeeping; run once in next session so `alembic upgrade head` no-ops cleanly instead of noticing migration 007 on disk doesn't match DB state
2. **"Retrieval failed" in degraded mode** — worth a 15-min investigation next session; indexes are correct, so the failure may be Cohere rate limit, network transient, or a separate bug. Non-blocking because fallback path works.
3. **Snapshot `spelix-pre-resize-session27`** — deletable after 7 days of stable runtime (~$0.60/mo while retained)

## 6. Next session start

```bash
/status
# Apply the one-off SQL already in prod to alembic's tracking table:
ssh spelix-droplet "cd /home/deploy/spelix && docker compose exec backend uv run alembic upgrade head"
# Expected: "Running upgrade 006_admin_expert_reviews -> 007_enable_realtime_analyses" or
# no-op if alembic_version was already bumped. Either way closes D-027.

# Then investigate residual "Retrieval failed" in degraded mode (non-blocking):
#   ssh spelix-droplet "docker logs spelix-worker-1 2>&1 | grep -B5 'Retrieval failed' | tail -30"

# Priority ordering for L2 beta polish (May 9 freeze):
#   1. D-027 — apply migration 007 (5 min)
#   2. Investigate Retrieval failed root cause (15-30 min)
#   3. D-028 — cosmetic Realtime banner fix (15 min, only if time)
#   4. D-017 — real paper PDFs via Docling (L — consider whether worth before freeze)
```
