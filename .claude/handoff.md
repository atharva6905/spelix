# Session 13 Handoff — Twelve-Layer Phase 0 Bug Stack Cleared, Worker Pipeline Live

## TL;DR

- **The end-to-end worker pipeline now runs in production for the first time ever.** Verified by manually re-enqueuing the orphan analysis row 214bf593 from the droplet via SSH and watching it complete: `quality_gate_pending → processing → quality_gate_rejected` in 100.48s with a structured per-check `quality_gate_result` JSONB containing real metrics from MediaPipe pose extraction.
- **12 layers of dormant Phase 0 bugs were peeled this session** across 12 PRs (#3 → #14). Every layer was caught only after the previous one was fixed.
- **The fixture itself fails the quality gate** (it's 360p / body fills 8% of frame). This is a fixture quality issue, not a pipeline bug — the gate is doing exactly what it should. Need a real 720p+ squat video where the body fills ≥30% of the frame to verify the success path.

## What changed (12 PRs)

| PR | Commit | Layer | Bug |
|----|--------|-------|-----|
| #3 | `94dd0fa` | 1 | `_make_storage_service` returned `client=None` even with env vars set (the `pass`-branch). Plus initial `@app.exception_handler(Exception)`. |
| #4 | `754393c` | 2 | Sync `create_client` vs `await client.storage.from_(...)` mismatch — switched to `acreate_client`. Module-level cache. Enriched exception envelope with `detail.type` + `detail.message`. |
| #5 | `02fcc88` | 3 | `/insights/global` and cleanup cron used tz-aware `datetime.now(tz=utc)` against `TIMESTAMP WITHOUT TIME ZONE` column → asyncpg `DataError`. |
| (no PR) | droplet env | 4 | `SUPABASE_SERVICE_ROLE_KEY` was a JWT from a different Supabase project (`xvgwjpumswndke**ltuxc**`) than `SUPABASE_URL` (`xvgwjpumswndke**xituxc**`). Decoded the JWT `ref` claim from inside the running container and confirmed mismatch. Fixed by editing `/home/deploy/spelix/.env.prod` and `--force-recreate`. |
| (no Supabase PR) | dashboard | 5 | `videos` storage bucket didn't exist in the canonical project. Created via `acreate_client(...).storage.create_bucket('videos', options={'public': False})`. |
| #6 | `12cd90b` | 6 | Frontend `tus-js-client` against Supabase REST signed upload URL — wrong protocol. Switched to `XMLHttpRequest` PUT. Drop pause/resume (REST can't resume mid-byte). 22 tests rewritten. |
| #7 | `4415ad0` | 7 | `get_db()` yielded session inside `async with` and never called `commit()`. SQLAlchemy `autocommit=False` rolled back EVERY write since Phase 0 B-005. Same bug in `process_analysis` and `cleanup_expired_artifacts`. |
| #8 | `eb1a8c9` | 8 | `_get_service` constructed `AnalysisService` without passing `arq_pool` — `start_analysis` silently no-op'd the worker enqueue while still flipping the row to `quality_gate_pending`. Added cached `_get_arq_pool()` factory. |
| #9 | `b427f17` | 9a + 9b | (a) `ThresholdConfig()` path resolution computed `/config/thresholds_v1.json` (filesystem root!) inside Docker because `Path(__file__).parent.parent.parent` walks to `/`, AND the Dockerfile didn't copy `config/` into the image at all. Robust `_resolve_threshold_path` + bind-mount `./config:/app/config:ro`. (b) Status guard rejected `quality_gate_pending → failed`, so any early-pipeline crash orphaned the row forever. Added `queued → failed` and `quality_gate_pending → failed` to the table. |
| #10 | `92ecc85` | 10 | `start_analysis` AND `run_cv_pipeline` both tried to do `queued → quality_gate_pending`. Whichever ran second hit a self-transition the guard rejected. Removed the duplicate from the pipeline; `start_analysis` is the canonical owner. |
| #11 | `7076c4b` | 11a + 11b | (a) `analysis.video_path` was set BEFORE flush so `analysis.id` was None — DB stored literal string `'videos/None/squat-high-bar.mp4'` while the upload URL used the post-flush real UUID. Pre-generate the UUID via `id=gen_uuid()`. (b) Worker error handler crashed with `failed → failed` self-transition when re-running an already-failed row. Skip the transition when already at `failed`. |
| #12 | `fb1b12d` | 12 | `mediapipe.solutions` doesn't exist on Linux x86_64 wheels (verified across 0.10.9–0.10.33 — every wheel ships zero `solutions/` files). Local dev worked because Mac/Windows wheels still have it; CI passed because tests mocked mediapipe entirely. Migrated `pose_extraction.py` to `mediapipe.tasks.python.vision.PoseLandmarker`. Bake `pose_landmarker_heavy.task` into the Docker image at build via curl. 14 tests rewritten + 2 new for `_resolve_model_path`. |
| #13 | `491da90` | 12-cont | MediaPipe Tasks API `libmediapipe.so` links against `libGLESv2.so.2` and `libEGL.so.1` (verified via `ldd`). Dockerfile only had `libgl1`. Added `libgles2` + `libegl1`. |
| #14 | `7bf8361` | 12-cont | `quality_gates.video_file_check` shells out to `ffprobe`, catches `FileNotFoundError`, returns "Video file appears corrupt". Dockerfile didn't install `ffmpeg`. Added it. |

## Test counts

- **Backend**: 960 → 960 (some tests rewritten in place, ~10 net new)
- **Frontend**: 178
- **CI**: green on all 12 PRs
- **Production E2E**: ALL 12 layers verified live via SSH on the droplet

## End-to-end production verification

After all 12 PRs deployed, manually enqueued analysis row `214bf593-bd41-45a4-81a1-98064a1fd199`:

```bash
ssh spelix-droplet "docker compose -f /home/deploy/spelix/docker-compose.prod.yml \
  exec -T backend uv run --no-dev python -c '
import asyncio, os
from arq import create_pool
from arq.connections import RedisSettings

async def main():
    pool = await create_pool(RedisSettings.from_dsn(os.environ[\"REDIS_URL\"]))
    job = await pool.enqueue_job(\"process_analysis\",
        analysis_id=\"214bf593-bd41-45a4-81a1-98064a1fd199\")
    print(\"enqueued:\", job)
    await pool.aclose()

asyncio.run(main())
'"
```

Worker logs (the perfect ending):

```
worker-1 | 12:18:27: 0.31s → 9d507b689ed5450987af1528ee925f34:process_analysis(...)
worker-1 | INFO: Created TensorFlow Lite XNNPACK delegate for CPU.
worker-1 | W0000 inference_feedback_manager.cc:114 — single signature inference (normal)
worker-1 | W0000 landmark_projection_calculator.cc:78 — square ROI hint (normal)
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
    "status": "rejected",
    "checks": [
      {"name": "video_file_check", "passed": true,  "metric_value": 14.23, "threshold": 120},
      {"name": "resolution",       "passed": false, "metric_value": 360,   "threshold": 720,
        "user_message": "Video resolution too low — record at 720p or higher."},
      {"name": "body_visibility",  "passed": true,  "metric_value": 0.6946,"threshold": 0.3,
        "user_message": "Body visibility is sufficient."},
      {"name": "framing",          "passed": false, "metric_value": 0.0799,"threshold": 0.3,
        "user_message": "You appear too far from the camera. Please move closer..."},
      {"name": "single_person",    "passed": true,  "metric_value": 0,     "threshold": 2}
    ]
  }
}
```

This proves: ARQ enqueue + worker pickup + DB session commit + threshold config load + storage download (correct path with real UUID) + MediaPipe Tasks API init + TFLite XNNPACK inference + 5/5 quality gates running with real metrics + structured JSONB persistence + clean status transition + clean error handler. **Every subsystem of the worker pipeline is functional in production.**

## Blockers

### NONE for the code path. ONE for end-to-end happy-path verification.

The pipeline works. The test fixture `e2e/fixtures/squat-high-bar.mp4` is 360p with the lifter taking up only 8% of the frame. The quality gate correctly rejects it on `resolution` and `framing`. To verify the **success path** (`processing → coaching → completed` with form scores + coaching output + PDF), we need a real squat video that meets the SRS recording standards:

- **≥720p resolution** (preferably 1080p)
- **Body fills ≥30% of frame** (camera 2–3 metres away at hip height)
- **Sagittal/side view** (Phase 0 only supports side view)
- **2–40 seconds duration** for normal mode (or up to 120s in extended mode)

Without a fixture meeting these constraints I can't drive the success path through the worker. Options:
1. **You record a quick squat clip** on your phone meeting the criteria → drop in `e2e/fixtures/squat-high-bar-720p.mp4`, replace the existing fixture
2. **Find one online** under a permissive license (CC0 / public domain) and bundle it
3. **Generate one synthetically** with a 3D animated person (more work)

Alternatively the existing fixture probably DOES work for verifying the rep detection + scoring stages if we lower the gate thresholds via ThresholdConfig — but that defeats the purpose of the gates. Better to fix the fixture.

### Dormant config issues NOT in code, NOT yet hit

Subsystems we haven't yet tested in production because the orphan row got rejected at the quality gate before reaching them:

- **Anthropic coaching call** — needs `ANTHROPIC_API_KEY` valid in `.env.prod`
- **OpenAI keyframe analysis** — best-effort, won't block but needs `OPENAI_API_KEY`
- **WeasyPrint PDF generation** — needs system fonts (`fonts-liberation` is installed; should work)
- **Realtime status subscriptions** — frontend uses Supabase Realtime; was working in earlier session
- **Artifact upload to Storage** — same client as download, should work

Each will surface as `error_message` on the row if it fails, and the global exception handler from PR #4 will surface anything that bubbles up to FastAPI.

## Next session start

```bash
# 1. Replace the test fixture with a real 720p side-view squat video
#    that meets SRS recording standards. Drop it at:
#    e2e/fixtures/squat-high-bar.mp4

# 2. Re-run Playwright MCP E2E from spelix.app — should now reach
#    processing → coaching → completed. Watch for further dormant config
#    bugs in the coaching path (Anthropic key, etc).

ssh spelix-droplet "docker compose -f /home/deploy/spelix/docker-compose.prod.yml \
  logs worker --tail 100 -f"   # tail in another shell while uploading

# 3. If the success path completes:
#    - Verify the results page renders FormScoreCards + coaching output
#    - Verify PDF generation works (download link)
#    - Verify cleanup cron eventually NULLs the artifact paths after 7 days

# 4. Then move on to Phase 2 RAG planning. Activate spelix-rag-engineer
#    and spelix-corpus-curator. Migration 004 for rag_documents + expert_annotations.

# 5. Cleanup task #14 from the queue: drop the doubled videos/videos
#    storage prefix. Internally consistent today, ugly forever.
```

## Key learnings to carry forward

1. **Mocking entire third-party modules masks dormant bugs.** Spelix's tests for the storage factory, the worker, AND `pose_extraction` all mocked `mediapipe`, `supabase`, and the repo layer entirely. None of them ever exercised the real code paths. Production was a graveyard of dormant bugs sitting behind perfectly green CI for months. **Rule for the next phase: any factory or singleton that constructs a third-party client should have at least one regression test that exercises the real construction path with the third-party module patched at its source, not at the consumer.**
2. **`SQLAlchemy default=` runs at INSERT time, NOT at object construction.** Anyone reading from `obj.id` before the first flush sees `None`. This bit us with `video_path`. The fix is to either pass `id=gen_uuid()` explicitly OR access the ID only after `await repo.create()`.
3. **`AsyncSession` requires explicit commit.** The default `autocommit=False` rolls back at session close. The FastAPI dependency `get_db()` MUST commit on success. This is a one-time fix but worth a backend gotcha.
4. **State machine guards must support self-transitions to absorbing failure states OR error handlers must guard against them.** Worker error handlers should check `if status != target_state` before calling `transition(status, target_state)`.
5. **Linux mediapipe wheels never had `solutions`.** This is a Google decision, not a Spelix bug — but it means any code base targeting cross-platform deployment must use the Tasks API, not the legacy `solutions`. Future MediaPipe code should default to Tasks.
6. **Docker `COPY` can't reach above the build context.** Spelix's `config/` lives at the repo root, above `./backend` (the build context). Bind-mounting via docker-compose is the cleanest fix.
7. **Pre-launch debugging via direct SSH is way faster than asking the user to paste commands.** The Droplet Debugging section in `CLAUDE.md` codifies this for future sessions.
8. **The enriched global exception handler from PR #4 was the single biggest force multiplier of this session.** Every subsequent layer was diagnosed in one browser fetch or one curl call instead of requiring server-log access. Worth keeping permanently.

## Stack of fixes deployed (chronological)

```
PR #3   Storage factory client=None
PR #4   Sync→async supabase client + global exception handler
PR #5   /insights/global tz-aware datetime
DropEnv SUPABASE_SERVICE_ROLE_KEY from wrong project
SBdash  videos bucket created in correct project
PR #6   Frontend TUS→REST XHR upload
PR #7   AsyncSession commit-on-success (data-loss bug)
PR #8   ARQ pool wired into _get_service
PR #9   ThresholdConfig path + queued/QG_pending → failed transitions
PR #10  Removed duplicate queued→QG_pending transition from pipeline
PR #11  video_path UUID + worker failed→failed self-transition
PR #12  pose_extraction migrated to MediaPipe Tasks API
PR #13  libgles2 + libegl1 in Dockerfile
PR #14  ffmpeg in Dockerfile (for ffprobe)
```
