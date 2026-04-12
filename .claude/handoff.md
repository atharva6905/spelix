# Session 21 Handoff → Session 22: P2-026 dual-collection orchestrator, backlog reconciliation, droplet OOM persists

## Completed

| Task | PR | Squash SHA | Description |
|------|----|------------|-------------|
| P2-026 | #27 | `18c56cf` | **DualCollectionOrchestrator** — queries both `papers_rag` and `coach_brain` concurrently via `asyncio.gather`, merges results with single cross-collection Cohere Rerank 4.0, classifies `retrieval_source` per FR-BRAIN-05 thresholds (≥0.82 brain_primary, 0.65–0.82 hybrid, <0.65 papers_fallback). Worker wired to use orchestrator. Coaching prompt tags evidence with `[RESEARCH]`/`[COACHING]` labels per FR-BRAIN-04. RetrievalService extended with `additional_filters` and `rerank=False` params. |
| P2-027 | #27 | `18c56cf` | **Cold-start fallback** — empty `coach_brain` → top_score=0.0 → `papers_only_fallback` routing. No `[COACHING]` labels in prompt. Handled automatically by P2-026 threshold logic. |
| BACKLOG-FIX | #27 | `18c56cf` | **Backlog reconciliation** — 7 tasks were already implemented in PRs #17-#19 but never marked done: P2-008 (dense retrieval), P2-009 (BM25 sparse), P2-010 (RRF+Rerank), P2-011 (exercise filter), P2-012 (min docs guard), P2-024 (contextual embedding), P2-028 (privacy triggers). All marked done with SHAs. |

### Files created
- `backend/app/services/dual_collection.py` — `DualCollectionOrchestrator` class
- `backend/tests/unit/test_dual_collection.py` — 8 TDD gate tests

### Files modified
- `backend/app/services/retrieval.py` — `additional_filters` + `rerank=False` params
- `backend/app/services/coaching.py` — `retrieval_source` param + `[RESEARCH]`/`[COACHING]` labels
- `backend/app/workers/analysis_worker.py` — orchestrator wiring + `retrieval_source` forwarding
- `backend/tests/unit/test_retrieval.py` — 2 new tests
- `backend/tests/unit/test_coaching.py` — 2 new tests + `collection` param on helper
- `backend/tests/unit/test_coaching_worker.py` — `DualCollectionOrchestrator` mock pattern
- `backend/tests/unit/test_qdrant_fallback.py` — `DualCollectionOrchestrator` mock pattern
- `backlog.md` — 9 tasks marked done (P2-008..012, P2-024, P2-026..028)

## Remaining

### Phase 2 Batch 7 — Coach Brain Foundation
| ID | Status | Deps met? | Notes |
|----|--------|-----------|-------|
| P2-025 | open | ✅ (P2-023 + P2-024 done) | Seed corpus ingestion (≥20 entries). Data task, not code. |
| P2-029 | open | ✅ (P2-001 done) | Three-tier consent UI (frontend) |
| P2-030 | open | blocked on P2-029 | Consent withdrawal cascade (ARQ job) |
| P2-031 | open | no deps | DPIA document — hard privacy gate |

### Phase 2 Batch 8 — Eval Logging
| ID | Status | Deps met? | Notes |
|----|--------|-----------|-------|
| P2-032 | open | needs P2-034 | Retrieval metrics logging to Langfuse |
| P2-033 | open | ✅ | Per-analysis RAGAS/HHEM eval scores |
| P2-034 | open | no deps | Langfuse Cloud integration |

### Other
| ID | Status | Notes |
|----|--------|-------|
| P2-007 | open | Corpus curation — seed research papers (≥10 per exercise from PubMed/OpenAlex) |
| D-004..D-010 | open | Session 13 tech debt items |

## Test counts

- **Backend**: 1257 passed / 19 skipped / 0 failures (+15 from session 20's 1242)
- **Frontend**: 213 passed / 0 failures (unchanged)
- **Coverage**: ~91% backend (CI enforces ≥90%)
- **CI**: All 6 checks green on PR #27 (backend lint+tests, frontend lint+tests, secret scan, Vercel preview)
- **Known local-only failures**: 2 DB-dependent integration tests (`test_models.py::test_cascade_delete_rep_metrics`, `test_repositories.py::test_delete_removes_row`) — CI passes.
- **Alembic head**: `005_add_chat_messages` (applied on droplet)

## E2E verification

### PR #27 — Dual-collection orchestrator ⏳ PENDING
- Code merged to main (`18c56cf`) but **NOT deployed to droplet** — containers run old code from pre-reboot build
- Droplet needs `cd /home/deploy/spelix && git pull && docker compose -f docker-compose.prod.yml build backend worker && docker compose -f docker-compose.prod.yml up -d backend worker` to deploy PR #27
- Cannot verify dual-collection routing until deployed

### PR #26 — Portrait framing fix ⏳ PENDING (carried from session 20)
- Code deployed on droplet (pre-reboot build includes PR #26)
- Test upload of deadlift video submitted (analysis ID: `a411eddf-95a4-4c23-9478-70500db36850`)
- **Droplet went OOM during MediaPipe processing** — SSH, API, and web all became unresponsive
- This is the **3rd consecutive OOM** (sessions 20, 21, 22) triggered by MediaPipe Heavy on the 2GB droplet

### Upload flow verified ✅
- Upload page loads correctly, exercise type/variant selection works
- File selection + upload progress bar + redirect to status page all functional
- Status page shows initial state immediately (PR #24 fix confirmed working)
- Exercise-specific filming guidance renders per variant

### Droplet OOM pattern (CRITICAL)
- **Root cause**: MediaPipe BlazePose Heavy peaks at ~350MB RAM. Combined with backend (~200MB), Redis (~50MB), and Caddy (~30MB), total exceeds 2GB during processing
- **Trigger**: any video upload that passes quality gates and reaches MediaPipe processing
- **Impact**: SSH, API, and web all become unresponsive. Requires hard reboot from DO dashboard
- **Mitigation options**: (a) upgrade to 4GB droplet ($24/mo → $48/mo), (b) reduce `model_complexity` to 1 (lighter model, lower accuracy), (c) add swap space, (d) process videos on a separate worker machine
- Three sessions in a row have been blocked by this. It's the single biggest production blocker.

## Blockers

1. **Droplet OOM (3rd time)** — 2GB droplet cannot run MediaPipe Heavy + backend simultaneously. Needs hard reboot from DO dashboard, then decide on mitigation (upgrade RAM or add swap). Until resolved, no video can complete processing on prod.
2. **PR #27 not deployed to droplet** — merged to GitHub main but droplet containers run old code. After reboot, run: `cd /home/deploy/spelix && git pull && docker compose -f docker-compose.prod.yml build backend worker && docker compose -f docker-compose.prod.yml up -d backend worker`
3. **Future deploys**: use `docker compose build` (WITH cache), never `--no-cache`, on the 2GB droplet. Better: add swap first (`fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab`).

## Next session start

```bash
# 1. Hard reboot droplet from DO dashboard (if still unresponsive)
# 2. After reboot, deploy PR #27 and add swap:
ssh spelix-droplet "fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab"
ssh spelix-droplet "cd /home/deploy/spelix && git pull && docker compose -f docker-compose.prod.yml build backend worker && docker compose -f docker-compose.prod.yml up -d backend worker"
# 3. Then:
/status
# 4. Upload test video → verify full pipeline with dual-collection orchestrator
# 5. Continue with P2-031 (DPIA) or P2-034 (Langfuse)
```
