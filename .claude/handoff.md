# Session 31 Handoff → Session 32: L2 Sprint Day 4 — ARQ → streaq migration live on prod

**Context refresh:** Session 31 shipped the ARQ → streaq drop-in migration on 2026-04-15 (Day 4 of the 19-day L2 sprint) per ADR-BRAIN-04-reversal. STRATEGY.md v3 Day 3-9 scope complete 5 days ahead of the Apr 22 target. Phase 3 LangGraph pull-forward (Day 10-16) is now unblocked. Production worker is running streaq 6.4.0 on queue `spelix` with heartbeat at `spelix:worker:heartbeat` TTL 61s observed post-hotfix-deploy.

## L2-STREAQ-MIGRATION shipped via PR #48 + hotfix PR #49 (2026-04-15)

**Main migration:** PR #48 merge commit `2870c6a`. 19 commits on `feat/streaq-migration`. Backend 1475 tests passing (net +8 new, -11 deleted), ruff + pyright clean, coverage preserved.

**Hotfix:** PR #49 merge commit `e35826b`. Single-line `docker-compose.prod.yml` fix — streaq 6.4.0 CLI uses `streaq run <worker_path>`, not bare `streaq <worker_path>` (CLI was restructured into `run`/`web` subcommands). Worker container went from `Restarting (2)` back to `Up` after the hotfix deploy.

Droplet state after hotfix (2026-04-15 ~12:28 UTC):
- `git log -1`: `e35826b Merge pull request #49 from atharva6905/fix/streaq-cli-run-subcommand`
- `docker ps`: `spelix-worker-1 Up About a minute`, `spelix-backend-1 Up (healthy)`, `spelix-redis-1 Up 11 hours (healthy)`
- Heartbeat: `alive`, TTL **61s** (NFR-OPER-02 confirmed)
- Worker logs: `[INFO] 2026-04-15 12:28:18: starting worker 886e2c68 for queue spelix`

E2E verify on `https://spelix.app` via Playwright MCP after hotfix: landing loaded clean, **0 console errors, 0 4xx/5xx network requests**.

## Commits on `main` from this session

**PR #48 (19 commits)** — `94126b6..67e1a51`, merged as `2870c6a`:
- `94126b6` implementation plan committed to branch
- `9145b6a`, `9f9caeb` ADR-BRAIN-04-reversal + URL for arq tracking issue
- `9fae77e` streaq dep added alongside arq
- `6c3dbe0` plan revised for actual streaq 6.4.0 API (`TaskContext` + `WorkerDepends`)
- `8b279e3`, `ccff88d` failing test + rename
- `71f082d`, `97d4c4a` streaq_worker.py skeleton + heartbeat/timeout fixup
- `9a6248d` Redis roundtrip integration test
- `125900a`, `d801591` analyses.py enqueue migration + import-failure coverage
- `1c85c21`, `5d60208` consent.py migration + import-failure regression test
- `5da091f` expert.py migration (includes test_expert_paper_complete.py sweep)
- `5118eb4`, `43c9176` worker-body test retarget + admin.py llen→xlen fix
- `4831528` docker-compose worker command swap
- `67e1a51` drop arq dep, delete settings.py, CLAUDE.md rewrite

**PR #49 (1 commit)** — merged as `e35826b`:
- `0e5e350` add streaq `run` subcommand to worker start command

## Key learnings from this session (write to memory / CLAUDE.md if useful)

1. **streaq 6.4.0 API ≠ Context7 docs.** Context7 showed `WrappedContext[C]` and `lifespan(worker)`; actual 6.4.0 exports `TaskContext` + `WorkerDepends()` + zero-arg `lifespan()`. Always verify library API against installed source when the plan depends on it.
2. **streaq 6.4.0 CLI uses subcommands.** `streaq run <path>` and `streaq web <path>`, not bare `streaq <path>`. Cost: 1 prod deploy cycle + hotfix PR. Documenting in `backend/CLAUDE.md` streaq Gotchas subsection so next time we see the error in logs we know to reach for `run`.
3. **streaq uses Redis streams, not lists.** Queue depth must be queried with `XLEN streaq:<queue_name>:queues:`, NOT `LLEN`. Bare `LLEN` on the queue name silently returns 0 (key is nonexistent) — this was a latent bug in `app/services/admin.py` left over from the ARQ era and caught during Task 9 code review.
4. **Subagent-driven development caught every real bug.** Over 13 tasks, code-quality reviewers found: 1 Critical (weak cache assertion → missed import-failure regression across 3 enqueue sites), 1 Critical (llen→xlen wrong key), plus Important issues on every task except the smallest. The review loop is expensive in tokens but catches things the implementer misses. Pattern worth keeping.

## Next session start (Session 32)

**Day 5 of L2 sprint (Apr 16).** STRATEGY.md v3 §Day 10-16 starts Apr 23 (Phase 3 Batch 1), so Days 5-9 (Apr 16-22) are a buffer window. Priority ordering:

1. **Kin expert onboarding call** — still pending from Session 30 handoff. Walk the portal end-to-end with real expert, upload first real PDF end-to-end. Log cadence + paper priority list to `docs/expert-cadence.md` (to be created).
2. **Decide the Day 5-9 buffer work** — options:
   - Pull Phase 3 Batch 1 forward (LangGraph StateGraph + composable tools). streaq done early leaves 5 days of bonus time before Batch 1's scheduled start.
   - Use the buffer for Sprint BETA prep (blog post drafting, application-materials work per STRATEGY §Sprint BETA).
   - Close the parked `/retrieval failed/` Cohere probe (session 28 §2 parked).
   - Ship one of the deferred V2 landing items if time.
3. **P2-005 still open** — `ingest_paper` is a stub downloading head bytes only. Real Docling parsing remains for Phase 2 backfill; kin expert's first uploaded PDF will exercise the stub path and surface any cleanup needed.

## Parked / opportunistic (unchanged from session 30, still deferred)

- **D-029** — Rename `injury_advice_accurate` → `movement_advice_accurate` (pre-existing SaMD violation; 6 files)
- **D-030** — Nightly cron to sweep abandoned `rag_documents.review_status='uploading'` rows older than 2 hours
- **D-031** — Admin `GET /rag/documents` query type-safety
- **D-028** — Cosmetic "Connection lost" banner in `useAnalysisStatus`
- **D-004..D-010** — Session 13 tech debt

## Test counts on `main` after hotfix

- **Backend**: 1475 passing (on `--ignore=tests/e2e` due to rate-limit noise from repeated local runs; CI runs full suite). 25 skipped, 0 failing.
- **Frontend**: 266 passing (unchanged — no frontend touches this session).
- **Coverage**: 91% preserved (not re-measured; CI coverage gate not failing).

## Test artifacts

- `docs/superpowers/plans/2026-04-15-arq-to-streaq-migration.md` — full task-by-task plan (13 tasks, 1281 lines on branch, merged via PR #48)
- `.playwright-mcp/page-2026-04-15T12-29-40-032Z.yml` — Playwright snapshot of post-hotfix landing page on prod

## Prior session continues below

---

# Session 30 Handoff → Session 31: L2 Sprint Day 3 — Expert PDF Upload live on prod

**Context refresh:** Session 30 shipped end-to-end expert PDF upload on 2026-04-15 (Day 3 of the 19-day L2 sprint). STRATEGY.md v3 Day 1-2 Track B hard gate now met — the kin expert onboarding can proceed with a working upload portal. Phase 3 LangGraph pull-forward is now unblocked for Day 10-16. The Day 3-9 ARQ→streaq migration is the next scheduled sprint item.

## L2-EXPERT-UPLOAD shipped via PR #47 (2026-04-15)

Merge commit: `864c3c9` (merge commit, not squash). Deploy workflow completed. Droplet on `864c3c9`, all containers healthy. Migration 009 applied to prod Supabase — bucket `papers` exists with 50 MB + `application/pdf` mime allow-list; three storage-objects RLS policies in place (`expert_papers_insert`, `expert_papers_service_delete`, `expert_papers_service_select`).

**14 commits**, `1b5fa79..83b5d08` (plus the merge):
- `1b5fa79` ADR-EXPERT-01 + expert PDF upload plan
- `732f157` migration 009 papers bucket RLS + review_status='uploading'
- `54c7ddd` PDF filename sanitiser + 50 MB + magic-byte constants (16 tests)
- `0e5ded1` PaperStorageService (5 tests)
- `973b180` RagDocumentUploadRequest/Response/CompleteResponse schemas (9 tests)
- `0d5e705` POST /expert/papers phase 1 signed URL (5 tests)
- `ae1a71b` POST /expert/papers/:id/complete phase 3 magic-byte + enqueue (5 tests)
- `6b2d514` ingest_paper ARQ task stub (3 tests)
- `0ae6a8c` e2e integration test phase 1→3 (2 tests)
- `af8bbee` frontend expert paper upload API client (5 vitest cases)
- `86a1670` ExpertPaperUploadPage file input + progress UI (5 vitest cases)
- `18acd67` security review fixes C-1, H-1..H-4
- `b8635fe` backlog L2-EXPERT-UPLOAD + close D-017
- `83b5d08` pyright fix: narrow Optional types in complete handler

## E2E Verification — Expert PDF Upload (2026-04-15 ~05:15 EDT)

**UI probe** via Playwright MCP against live `https://spelix.app/expert/papers/upload`:
- Route exists on prod (not a 404) — role guard redirects unauthenticated session to `/upload` (user's own video upload page), which is the expected defense-in-depth behavior.
- No console errors or network 5xx on redirect.

**API probes** via curl against `https://api.spelix.app/api/v1/expert/...`:
- `POST /expert/papers` unauthenticated → `401 Not authenticated` ✓
- `POST /expert/papers/:id/complete` unauthenticated → `401 Not authenticated` ✓
- JWT-gated paths confirmed live.

**Prod Supabase verification** via `docker exec` + `/app/.venv/bin/python` one-off query:
- `storage.buckets` row `('papers', 52428800)` present ✓
- `storage.objects` policies `['expert_papers_insert', 'expert_papers_service_delete', 'expert_papers_service_select']` all present ✓

**Full upload flow (metadata → PUT → complete) NOT yet exercised on prod** — requires an expert-reviewer JWT we don't have set up in a test fixture. The kin expert is the first real user and will exercise the flow during today's onboarding call. If anything breaks at that step, it's a fast fix (I've already verified backend + frontend wiring at unit + integration level).

## Next session start (Session 31)

**Day 4 of L2 sprint** — STRATEGY.md v3 Day 3-9 is the **ARQ → streaq migration** (drop-in replacement, 4 job types). See `STRATEGY.md §Day 3-9`.

Priority ordering:
1. **Kin expert onboarding call** (60 min) — walk the portal, upload first PDF end-to-end (the very first prod exercise of this feature). Agree paper priority list + cadence. Log to `docs/expert-cadence.md`.
2. **Begin ARQ → streaq migration** — migrate `run_analysis`, coaching stream, `ping_qdrant_health`, `ingest_paper`. Write ADR-BRAIN-04-reversal. Target: all 4 job types on streaq by Day 9 (Apr 22).
3. **Watch for expert-upload first-use feedback** — if any UX bug lands during the onboarding call, fix in a quick follow-up PR.

## Parked / opportunistic (deferred)

Backlog rows opened by security review + handoff:
- **D-029** — Rename `injury_advice_accurate` to `movement_advice_accurate` (pre-existing SaMD violation; 6 files across DB + schemas + UI; separate PR; size M)
- **D-030** — Nightly cron to sweep abandoned `rag_documents.review_status='uploading'` rows (+ their storage objects) older than 2 hours (size S)
- **D-031** — Admin `GET /rag/documents` free-text `review_status` query should be `Literal`-constrained or default-filter `uploading` rows (size S)
- **D-028** — useAnalysisStatus cosmetic "Connection lost" banner (size S, unchanged)
- **D-004..D-010** — Session 13 tech debt (defer to post-L2)

**Do NOT make D-029/D-030/D-031 top priority** — they're follow-ups from the security audit, not merge-blockers. The kin expert onboarding + streaq migration own the next 7 days.

## Test counts on `main` after merge

- **Backend**: 1479 passing, 25 skipped, 0 failing
- **Frontend**: 266 passing, 0 failing
- **Coverage**: 91% preserved (not re-measured this session; CI coverage job not failing)

## Test artifacts

- `docs/superpowers/plans/2026-04-15-expert-pdf-upload-wiring.md` — the implementation plan used to drive this session
- `.playwright-mcp/page-2026-04-15T09-15-07-923Z.yml` — Playwright snapshot of the expert upload route redirect (unauth'd)

## Prior session continues below

---

# Session 29 Handoff → Session 30: L2 Sprint Day 1-2 complete — Landing V1 live on prod

**Context refresh:** Session 29 shipped Landing V1 to prod on 2026-04-15 (end of Day 2 of the 19-day L2 sprint). STRATEGY.md v3 Day 1-2 hard gate met. Next up per STRATEGY v3 Day 3-5: Track A = expert PDF upload wiring; Track B starts the Phase 3 LangGraph pull-forward. `backlog.md` seeds the V2 polish items under the L2-LANDING-V2-* IDs (deferred to Sprint BETA, May 4-14).

## E2E Verification — Landing V1 (2026-04-15 02:51 EDT)

Merge commit: `ae3b4fb`. Deploy workflow run: `24440399064`, conclusion success. All 6 jobs green. Droplet on merge commit, containers healthy, health endpoint returns `{"status":"ok"}`.

Canary walk via browse skill against live `https://www.spelix.app/` as anonymous:
- **Title**: "Spelix — Barbell form coaching, grounded in research"
- **H1**: "Barbell form coaching where every piece of feedback cites its source." (Option A verbatim)
- **H2 count**: 5 (Problem, HowItWorks, Differentiators, Privacy, FinalCta)
- **Interactive inventory** (via `$B snapshot -i`): NavBar link-to-Spelix + 3 anchor links (#how-it-works, #why-spelix, #privacy) + "Request beta access" pill, Hero email input + Request private-beta-access button (disabled until consent), consent checkbox + beta-terms link, Read-beta-terms-→ link in disclaimer, DifferentiatorsSection accordion 3 items (first expanded), PrivacySection accordion 3 items (first expanded), FinalCTA email input + Join-the-private-beta button (disabled until consent) + consent checkbox, Footer Beta-terms link.
- **Perf**: TTFB 11ms, download 105ms, domParse 9ms.
- **Console errors**: none.
- **Form submission**: filled `qa-prod-landing-v1-1776235907@example.com`, checked consent, clicked submit. `POST https://api.spelix.app/api/v1/beta/requests` returned `201 Created` in 2295ms, body 107 bytes (no email echoed — C-1 security fix verified). Page transitioned to "Thanks — you're on the list. We'll email an invite within a few days." success state. Check Supabase SQL for the row: `SELECT email, source, status, created_at FROM beta_requests WHERE email LIKE 'qa-prod-%@example.com' ORDER BY created_at DESC LIMIT 1` (expect 1 row, status='pending').

Prod-verification artefacts persisted to `e2e/screenshots/landing-v1-prod/`:
- `hero-annotated.png` — full interactive snapshot with @ref labels (770 KB)
- `hero-after-thanks.png` — hero viewport showing Thanks success state (307 KB)
- `full-page.png` — full-page screenshot post-submission (734 KB)

Local-render validation artefacts (Vite dev server via browse skill) persisted to `landing-page/screenshots/built-v1/`:
- `00-full-page.png` + one viewport per section (01-hero through 07-footer) + `responsive-{mobile,tablet,desktop}.png`.

## L2-LANDING PRs merged this session

| PR | Title | Merge SHA | Notes |
|----|-------|-----------|-------|
| #45 | `feat(landing): private-beta landing page V1` | `ae3b4fb` | 23 commits. Backend beta-request endpoint + 8 landing sections + Tailwind 4 `@theme` brand tokens + PostHog cookieless + route swap. Security review C-1 resolved pre-merge. CI fix for `uq_beta_requests_email` model-side Index applied mid-flight. See ADR-049..ADR-052. |

## Known follow-ups (non-blocking)

- `frontend/src/api/__tests__/beta.test.ts` has a local-uncommitted cleanup (remove the mock's extra `email: "a@b.com"` field so the mock matches production) — stashed as `landing-v1 post-merge: beta.test.ts C-1 mock cleanup + local impl plan`. Harmless on remote (`JSON.stringify(any)` doesn't type-check extra fields), so low-priority to recover.
- `landing-page/implementation-plan.md` is local-only (also stashed). It's a by-product of this session's subagent-driven execution; not core docs — decide whether to commit as historical reference or discard.
- Node.js 20 deprecation warnings across all CI jobs ("The following actions target Node.js 20 but are being forced to run on Node.js 24") — unrelated tech debt, bump `actions/checkout@v4` etc. in a future CI maintenance PR.

---

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
