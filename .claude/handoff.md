# Session 13 Handoff → Session 14: Phase 2 Planning Kickoff

## Status

- **Phase 1 production-functional** as of 2026-04-11 after 14 PRs (#3–#14, plus 2 docs commits) cleared 12 layers of dormant Phase 0 bugs. The full upload → worker pipeline → quality gates path runs end-to-end on `spelix.app`. Verified live via direct droplet SSH with the orphan analysis row `214bf593-bd41-45a4-81a1-98064a1fd199` — pipeline ran 100.48s, transitioned `quality_gate_pending → processing → quality_gate_rejected` cleanly, produced structured per-check metrics from real MediaPipe pose extraction.
- **Backend**: 960 tests passing (was 895), 91% coverage. **Frontend**: 178 tests passing (was 177).
- **Main branch**: clean, all CI green, last commit `6188e33` (docs catch-up for decisions.md + backlog.md).
- **Outstanding**: one Phase 2 cleanup task (P2-027) blocking happy-path verification — need a real 720p+ side-view squat video fixture.

## Completed this session

| PR | Commit | Description |
|----|--------|-------------|
| #3 | `94dd0fa` | `_make_storage_service` returned `client=None` even with env vars set + initial global exception handler with CORS headers. |
| #4 | `754393c` | Sync `create_client` vs awaited storage methods → `acreate_client` + module-level cache + enriched exception envelope (`detail.type`/`detail.message`). |
| #5 | `02fcc88` | `/insights/global` + cleanup cron tz-aware datetime against naive `created_at` column → strip tzinfo. |
| (env) | (droplet) | `SUPABASE_SERVICE_ROLE_KEY` was a JWT from the wrong Supabase project — fixed via `.env.prod` + `--force-recreate`. |
| (dashboard) | (Supabase) | Created the missing `videos` storage bucket in the canonical project. |
| #6 | `12cd90b` | Frontend `tus-js-client` against REST signed upload URL — wrong protocol. Switched to XHR PUT, dropped pause/resume. 22 tests rewritten. |
| #7 | `4415ad0` | `get_db()` never committed — every DB write rolled back since Phase 0 B-005. SQLAlchemy `autocommit=False` strikes. |
| #8 | `eb1a8c9` | `_get_service` never wired the ARQ pool → `start_analysis` silently no-op'd the worker enqueue while flipping the row to `quality_gate_pending`. |
| #9 | `b427f17` | (a) `ThresholdConfig()` path resolution computed `/config/...` (filesystem root) inside Docker + Dockerfile didn't copy `config/` at all. (b) Status guard rejected `queued/quality_gate_pending → failed`. |
| #10 | `92ecc85` | `start_analysis` AND `pipeline.run_cv_pipeline` both did `→ quality_gate_pending` → self-transition wall. Removed duplicate. |
| #11 | `7076c4b` | `analysis.video_path` set to literal string `'None'` because `gen_uuid` runs at flush, not `__init__` + worker error handler `failed → failed` self-transition wall. |
| #12 | `fb1b12d` | `mediapipe.solutions` doesn't exist on Linux x86_64 wheels (verified across 0.10.9–0.10.33) → migrated `pose_extraction.py` to MediaPipe Tasks API. Bake `pose_landmarker_heavy.task` into Docker image at build via curl. |
| #13 | `491da90` | Tasks API `libmediapipe.so` needs `libGLESv2.so.2` + `libEGL.so.1` (verified via `ldd`). Added `libgles2` + `libegl1` to Dockerfile. |
| #14 | `7bf8361` | `quality_gates.video_file_check` shells out to `ffprobe`. Added `ffmpeg` to Dockerfile. |
| docs | `bd16861` | Session 13 handoff with full layer-by-layer breakdown. |
| docs | `6188e33` | `decisions.md` + `backlog.md` catch-up: 6 new ADRs (027–032), 15 new B-IDs (B-138–B-149c), 7 new Phase 2 cleanup tasks (P2-026–P2-032). |
| docs | (this commit) | `/adr` command path bug fix + new `/backlog` command + CLAUDE.md update protocol for decisions.md and backlog.md. |

## Test counts

- Backend: **960 passed**, 8 skipped, 0 failures, 91% coverage (was 895 at Phase 1 transition gate)
- Frontend: **178 passed**, 0 failures, tsc clean (was 177)
- CI: green on PRs #3 through #14 + the docs commits on `main`
- Production E2E: pipeline verified end-to-end via SSH on the droplet (see "End-to-end production verification" in commit `bd16861`)

## E2E verification

Direct SSH against `spelix-droplet`:

```
worker-1 | 12:18:27: 0.31s → 9d507b689ed5450987af1528ee925f34:process_analysis(...)
worker-1 | INFO: Created TensorFlow Lite XNNPACK delegate for CPU.
worker-1 | 12:20:08: 100.48s ← 9d507b689ed5450987af1528ee925f34:process_analysis ●
```

Final row state:

```json
{
  "status": "quality_gate_rejected",
  "retry_count": 0,
  "error_message": null,
  "quality_gate_result": {
    "passed": false,
    "checks": [
      {"name": "video_file_check", "passed": true,  "metric_value": 14.23, "threshold": 120},
      {"name": "resolution",       "passed": false, "metric_value": 360,   "threshold": 720},
      {"name": "body_visibility",  "passed": true,  "metric_value": 0.6946,"threshold": 0.3},
      {"name": "framing",          "passed": false, "metric_value": 0.0799,"threshold": 0.3},
      {"name": "single_person",    "passed": true,  "metric_value": 0,     "threshold": 2}
    ]
  }
}
```

The pipeline works end-to-end. The test fixture itself is what fails the gate (360p, body fills 8% of frame). Replace the fixture and the success path runs.

## Remaining

| ID | Title | Why it blocks Phase 2 | Owner |
|----|-------|-----------------------|-------|
| P2-027 | Replace `e2e/fixtures/squat-high-bar.mp4` with a real 720p+ side-view clip | Without this, the **success path** (`processing → coaching → completed → results page → PDF`) cannot be verified end-to-end. Pipeline rejects on `resolution` (360p < 720p) and `framing` (8% < 30%). | **You** — phone-record a 10–30s squat clip, drop in `e2e/fixtures/squat-high-bar.mp4`, commit. |
| P2-030 | Verify untested production subsystems via E2E once happy path lands | Anthropic coaching, OpenAI keyframe, WeasyPrint PDF, Realtime status, artifact upload — none have been exercised in production yet. The orphan row never reached them because the gate rejected first. | Next session — run after P2-027 lands. |

The other Phase 2 cleanup tasks (P2-026, P2-028, P2-029, P2-031, P2-032) are not blocking — they're polish.

## Blockers

- **None code-side.** Main is clean, CI green, all 12 production layers fixed.
- **One content-side**: P2-027. Recording a 10s squat clip at 720p is the only thing standing between us and full happy-path verification.

## Next session start

This session is ending. The next session should be a **Phase 2 planning kickoff**. Kick off with this exact sequence:

```bash
# 1. Sync main + verify clean state
git checkout main && git pull
git log --oneline -5  # last 5 should include 6188e33 docs catch-up
ssh spelix-droplet "cd /home/deploy/spelix && git log --oneline -1"
# Both should show the same commit if the deploy ran cleanly.

# 2. Re-read the SRS Phase 2 Must filter to generate the canonical task list
rg "\| \*\*Must\*\*.*\| 2 \s*\|" docs/SRS.md
# Paste output into backlog.md under "Phase 2 — Planning" — REPLACE the
# existing P2-001 through P2-022 IF they don't match the SRS exactly.
# CLAUDE.md general rule says: "Never schedule batches from session memory
# alone — Phase 1 missed FR-REPM-08/09 this way."

# 3. Activate Phase 2 specialist agents (per Agent Architecture in CLAUDE.md):
#    - spelix-rag-engineer (Qdrant, Cohere embed/rerank, hybrid retrieval, ingestion)
#    - spelix-corpus-curator (research document ingestion, metadata, citation provenance)
# Both agent definitions live in .claude/agents/ — verify they exist + are current.

# 4. Run /phase to execute the phase transition gate checklist:
#    - Verify Phase 1 is actually complete (all MUSTs implemented, tests green,
#      audit clean)
#    - Update CLAUDE.md to "Current phase: Phase 2"
#    - Update memory.md to phase=2 task=P2-001 status=ready

# 5. Ask the user (Atharva) for:
#    - Decision on Migration 004 schema (rag_documents + expert_annotations)
#    - Qdrant Cloud cluster — already provisioned, or create now?
#    - Cohere API key — already in .env.prod, or set up now?
#    - Initial corpus seed — which research papers to ingest first
#      (probably starting with the SRS-cited references for FR-AICP-09)

# 6. Use /plan for the first Phase 2 task (P2-001 — Migration 004), then dispatch
#    to spelix-migration. Do NOT skip /plan — Phase 1 missed FR-REPM-08/09 via
#    backlog drift; the structured Explore → Plan → Execute workflow exists to
#    prevent that.

# 7. Run /adr inline whenever you make any architectural choice during Phase 2
#    planning — Qdrant collection schema, chunking strategy, embedding model
#    pinning, RLS policies on rag_documents, etc. The CLAUDE.md "decisions.md
#    update protocol" section now makes this a hard rule. Don't batch.

# 8. Run /backlog inline whenever you complete or discover a task. Same rule.
```

## Session 14 expectations

- **Length**: planning-only session, no code shipping. Should finish in <3 hours.
- **Output**: a fully-seeded `backlog.md` Phase 2 section, ADR-033+ for any new architectural decisions, the first task (P2-001) planned via `/plan` and ready to execute in session 15.
- **Optional**: if the user records the test fixture during the session, run the happy-path E2E verification (P2-030) before starting Phase 2 planning. That way Phase 1 closure is fully observed before opening Phase 2.

## Key learnings carried forward from session 13

1. **Mocking entire third-party modules masks dormant bugs.** Every Spelix test that touched storage / mediapipe / repo layer mocked them entirely, so production code paths were untested. ADR-032 codifies the "exercise real factory with source-patched third-party" rule. Phase 2 RAG tests MUST follow this pattern — mock at `cohere.Client`, not at `EmbeddingService`.
2. **`SQLAlchemy default=` runs at flush, not construction.** Anyone reading `obj.id` before flush sees `None`. ADR-028. Pre-generate UUIDs explicitly.
3. **`AsyncSession` requires explicit commit.** ADR-027. Every dependency or worker session block needs commit-on-success / rollback-on-exception.
4. **State machine guards must allow operational `→ failed` transitions OR error handlers must guard against self-transitions.** ADR-031.
5. **Linux mediapipe wheels never had `solutions`.** Use the Tasks API. ADR-029.
6. **Docker `COPY` can't reach above the build context.** Bind-mounting via docker-compose is the cleanest fix. The same pattern will apply to Phase 2 RAG documents if they ever live outside `backend/`.
7. **Pre-launch debugging via direct SSH (`spelix-droplet` alias) is way faster than asking the user to paste commands.** CLAUDE.md "Droplet Debugging (SSH)" section codifies this.
8. **The enriched global exception handler (PR #4) was the single biggest force multiplier of the session.** Every subsequent layer was diagnosed in one browser fetch instead of requiring server-log access. Worth keeping permanently.
9. **`/adr` and `/backlog` must be invoked INLINE with code changes**, not batched at end-of-session. Session 13 lost track of half the decisions because of end-of-session batching. CLAUDE.md "decisions.md & backlog.md Update Protocol" section codifies this.
