# Session 28 Handoff → Session 29: Phase 2 stable; entering 19-day L2 sprint to 2026-05-03

**Context refresh:** STRATEGY.md was rewritten as v3 on 2026-04-14 (same day as this handoff). Phase 3 is **no longer deferred** — it is pulled forward into a compressed 19-day sprint with a hard gate on **2026-05-03** (not May 9). Previous handoff framing around a May 9 freeze and post-Saturniq Phase 3 is obsolete. Read `STRATEGY.md` before acting on anything in §2 or §6 below.

## 1. Completed

### Session 28 PR merged
| PR | Commit | Title | Notes |
|----|--------|-------|-------|
| #41 | `3fb1269` merged as `181c754` | `docs: ADR-048 droplet sized to s-2vcpu-4gb for L2 beta, close D-026` | Docs-only — infrastructure change already live |
| #42 | `4ad7c8f` merged as `3f48923` | `docs(handoff): session 28 → session 29 — droplet resized, Phase 2 stable` | Stale against STRATEGY.md v3 — superseded by this document |

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

## 2. Remaining — L2 Sprint Scope (Apr 14 → May 3, 19 days)

Source of truth for this section is `STRATEGY.md` v3 (2026-04-14). Backlog items `backlog.md` is authoritative for IDs. Where sprint work lacks backlog IDs, create them at session start via `/backlog`.

### Day 1-2 (Apr 14-15) — Hard gates

| Item | Track | Size | Notes |
|------|-------|------|-------|
| **Landing V1 live on prod** per `landing-page-plan.md` (Hero + Problem + How It Works + Three Differentiators + Privacy + CTA + email capture → manual approval) | Track A, solo lead or `spelix-tdd` | L | Replaces current `HomePage.tsx`. Includes `/beta-terms` rendering `public/beta-terms.md`. PostHog events `landing_view`, `landing_email_submit_*`. |
| **Alembic migration 008** — `beta_requests` table, RLS, anonymous INSERT | `spelix-migration` | S | Blocker for landing email capture. |
| **Expert PDF upload wired end-to-end** — currently metadata-only. Backend: signed-URL endpoint (preferred, matches TUS pattern) OR `multipart/form-data` on `/api/v1/expert/papers`. Frontend: file input + progress UI on `ExpertPaperUploadPage.tsx`. | Track B team, `spelix-tdd` + `spelix-security-reviewer` | L | Hardening: magic-byte PDF check, 50 MB limit, filename sanitisation, Supabase Storage bucket RLS (expert_reviewer + admin write, service-role read), Docling ingestion trigger on upload. Security review mandatory before merge. |
| **Kin expert onboarding call** (60 min) — walk portal end-to-end, agree paper priority list, agree cadence, write `docs/expert-cadence.md` | Track C, solo lead | S | Today Apr 14. Unblocks first 5 seed papers by end of Day 2. |

### Day 3-9 (Apr 16-22) — ARQ → streaq migration

Reverses ADR-BRAIN-04's "defer to Phase 3" decision. Scoped as **drop-in replacement only**, no adoption of streaq task graphs / middleware in this window.

| Item | Notes |
|------|-------|
| Migrate `run_analysis`, coaching stream worker, `ping_qdrant_health` cron, Docling ingestion job | 4 job types total |
| Update `docker-compose.yml`, Dockerfile env, droplet deploy scripts | |
| New ADR documenting reversal + compressed 7-day scope | `ADR-BRAIN-04-reversal` per STRATEGY.md §ADR Updates |
| Kin expert Phase B steady throughput (parallel) | Target 5-10 papers reviewed by Day 9 |

### Day 10-16 (Apr 23-29) — Phase 3 Batches 1 + 2

**Activate `spelix-langgraph-engineer`** at start of Day 10.

| FR | Task | Size |
|----|------|------|
| FR-AICP-18 (P3-001) | `StateGraph` + typed `AgentState` Blackboard + composable tools: `get_rep_metrics`, `retrieve_papers`, `retrieve_coach_brain`, `flag_form_deviation`, `compare_to_user_history`, `generate_correction_plan`. Conditional edges, deterministic flow first. | XL |
| FR-AICP-19 (P3-002) | Adaptive reasoning — docstring-driven tool selection. | L |
| FR-AICP-20 (P3-003) | LangSmith tracing integration. | M |
| FR-BRAIN-06 (P3-004) | Standalone distillation `StateGraph` per ADR-BRAIN-07 — `extract_insights → validate_quality → format_entry → store_entry`. Eval gate `overall ≥ 0.85 AND correctness ≥ 0.8`. Runs async, never blocks coaching. | XL |
| FR-BRAIN-17 (P3-005) | Knowledge lifecycle ADD/UPDATE/NOOP with cosine thresholds (>0.92 NOOP, 0.75–0.92 UPDATE, <0.75 ADD) + contradiction flagging. | L |
| FR-BRAIN-14 (Should) | CoVe verification against `papers_rag` before every promotion. | M |

### Day 17-19 (Apr 30 - May 2) — Phase 3 Batch 3 + Smoke Test

| FR | Task | Size |
|----|------|------|
| FR-ADMN-12, FR-BRAIN-07 (P3-006) | Coach Brain expert review queue — single-screen cards, eval scorecard + CoVe result + approve/reject/edit, <30 sec/entry target. | L |
| FR-RESL-07 (P3-007) | "How AI Reasoned" sidebar on `ResultsPage` — `@xyflow/react` graph rendered from LangSmith trace, plain English per NFR-USAB-05. | M |
| Smoke test (Day 19 evening) | 3-5 trusted test users (McMaster barbell club + kin expert's network) through full upload → stream → results flow. Log to `docs/user-sessions/smoke-{date}-{initials}.md`. | — |

### Day 20 (May 3) — L2 Gate Audit

All gates below required; any miss triages before mid-May application batch.
- [ ] Landing page V1 live on prod, email capture functional, migration 008 applied
- [ ] Expert paper upload live on prod; kin expert has uploaded ≥5 papers end-to-end
- [ ] ARQ → streaq migration complete; all 4 job types running on streaq
- [ ] Phase 3 agent on prod, LangSmith traces visible
- [ ] Distillation `StateGraph` operational (idle pending user data is OK)
- [ ] Coach Brain review queue accessible from admin panel
- [ ] Reasoning sidebar renders on `ResultsPage` for at least one real test-user analysis
- [ ] 3-5 trusted test users through end-to-end flow
- [ ] No CRITICAL production bugs open

### Required ADRs (write inline with the first PR that reflects each)

Per STRATEGY.md §Required ADR Updates:
- **ADR-BRAIN-04 reversal** — streaq migration now, not deferred; compressed 7-day drop-in scope
- **ADR-EXPERT-01 (new)** — Expert paper upload security model (signed URL, magic-byte, 50 MB, RLS, Docling trigger)
- **ADR-TIMELINE-01 (new)** — Phase 3 pulled forward to 19-day sprint ending 2026-05-03, driven by mid-May applications + July interviews

### Parked / opportunistic (NOT in sprint scope)

| ID | Title | Size | Reason parked |
|----|-------|------|---------------|
| **D-027** | Apply migration `007_enable_realtime_analyses` via `alembic upgrade head` — prod state matches but `alembic_version` table still at 006 | S | Housekeeping; run once at convenience in next session start so future `alembic upgrade head` no-ops cleanly. |
| **D-028** | Cosmetic: `useAnalysisStatus` shows "Connection lost — reconnecting…" after intentional unsubscribe on terminal state | S | UI-only fix in `frontend/src/hooks/useAnalysisStatus.ts`. Fit in between sprint tasks if time. |
| **D-017** | Replace AI-synthesized paper text in `papers_rag` with real full-text PDFs via Docling ingestion | L | Obsolete once expert PDF upload lands Day 1-2 — real PDFs will arrive via the portal. Close D-017 once first expert paper is ingested. |
| **D-004..D-010** | Session 13 tech debt (doubled `videos/` storage prefix, fixture quality, tests-mock-everything doc, factory coverage) | S/M | Defer to post-L2. |
| **"Retrieval failed" in degraded mode** | 15-min root-cause probe on Cohere rate limit vs network transient | S | Fallback path works (FR-AICP-15). Investigate when a real sprint task is blocked, otherwise leave. |

## 3. Test counts

- **Backend**: 1443 tests collected, all passing (last full run on `main@66a81a7` via CI — PR #39 "Backend Tests: success")
- **Frontend**: 225 tests, all passing (local run after Datadog removal, 2026-04-15 ~21:35 UTC)
- **Coverage**: Last recorded **91%** at Phase 1 gate; not re-measured this session (docs + infra only)
- **Known failures**: None

## 4. E2E verification

**Analysis `41a88ec8-7dbf-4909-8ca6-9951fd48cfbd` — PASSED against spelix.app (2026-04-15 01:22–01:26 UTC)**

Affected flows walked:
- Upload page: Squat / High Bar selection, file picker, test-squat.mp4 (8.1 MB) ✅
- TUS upload to Supabase Storage ✅
- **Realtime status page live-updated** from "Preparing to analyse…" → "Analysis complete" (no poll fallback) ✅
- Detection result: "Squat — high bar — Confirmed by vision analysis" (GPT-4o fallback) ✅
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
- SSH fully responsive throughout
- Analysis wall-clock: ~150s (was 200s+ on single-vCPU) — MediaPipe uses both cores (111.87% CPU observed)

Residual observations (parked, see §2):
- **D-028**: "Connection lost — reconnecting…" banner flashes briefly AFTER the terminal UPDATE arrives — cosmetic only.
- **"Retrieval failed"** in worker logs during this analysis; fallback to ungrounded coaching worked. Qdrant indexes verified present.

## 5. Blockers

**None blocking Phase 2 stability. Sprint-critical risks (per STRATEGY.md stop-loss triggers):**

1. **Phase 3 slips past May 3 by >3 days** → re-scope Batch 2 (distillation) optional or defer Batch 3 (review queue + sidebar) to post-L2. Agent core (Batch 1) is non-negotiable.
2. **streaq migration blocks Phase 3 start by >5 days** → fall back to ARQ with `max_jobs=1`, `job_timeout=900` per ADR-BRAIN-04's Phase-2 config. Migrate post-interviews.
3. **Expert portal security review surfaces a critical vuln unfixable Day 1-2** → delay kin expert onboarding, ship portal with role-check only (no uploads) until fixed.

**Sub-blockers to track:**
- Snapshot `spelix-pre-resize-session27` deletable after 7 days of stable runtime (~$0.60/mo while retained)
- `docs/expert-cadence.md` doesn't exist yet — write after onboarding call

## 6. Next session start

**Day 1 of the 19-day L2 sprint.** Priority ordering below matches STRATEGY.md §Day 1-2.

```bash
/status
# Confirm environment, live containers, queue depth, CI status

# Track A — Landing V1 + migration 008 (solo lead or spelix-tdd)
#   Read: landing-page-plan.md, public/beta-terms.md (to be created)
#   Create branch: feat/landing-v1
#   Migration: use spelix-migration to scaffold 008_beta_requests
#   Instrumentation: PostHog landing_view, landing_email_submit_*

# Track B — Expert PDF upload wiring (parallel team)
#   Team via /team — backend (signed-URL + magic-byte + RLS + Docling trigger)
#   + frontend (file input + progress UI on ExpertPaperUploadPage.tsx)
#   + spelix-security-reviewer pre-merge
#   Write ADR-EXPERT-01 alongside first PR

# Track C — Kin expert onboarding call (today, 60 min)
#   Walk the portal end-to-end once Track B is even partially live
#   Agree paper priority list + cadence
#   Log to docs/expert-cadence.md

# Housekeeping (<5 min, do at session open):
ssh spelix-droplet "cd /home/deploy/spelix && docker compose exec backend uv run alembic upgrade head"
# Closes D-027. Expected: no-op or "006 → 007" bump.
```

**Do NOT start with D-027 / D-028 / D-017 / retrieval-failed probe as top priority** — those are parked per §2. Landing + expert upload + onboarding call are the actual Day 1-2 hard gates.
