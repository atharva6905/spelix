# memory.md — Agent Persistent State

phase: 3
task: phase-3-batch-2-distillation-fully-verified-on-prod
status: done
last_modified: [.claude/handoff.md, backend/app/distillation/validate.py, backend/app/workers/analysis_worker.py, backend/app/services/retrieval.py, backend/app/services/dual_collection.py, backend/app/agents/tools.py, backend/app/services/qdrant.py, backend/scripts/seed_coach_brain.py, backend/scripts/oneoff/sanitize_seed_samd_content.py, backend/scripts/oneoff/create_papers_rag_exercise_index.py, decisions.md, backend/CLAUDE.md, backlog.md]
failing_tests: []
blockers: []
srs_deviations: []
next_action: "Phase 3 Batch 3 — P3-006 expert review queue UI. 11 real coach_brain_candidates rows pending review on prod. Read order: SRS FR-ADMN-12 + FR-BRAIN-07, backend/app/models/coach_brain_candidate.py, decisions.md ADR-DISTILL-01. Run /plan 'Phase 3 Batch 3 — review queue + reasoning sidebar'. See .claude/handoff.md Session 42 §6 for full kickoff."
session_count: 42
last_session: 2026-04-17

## decisions_since_plan
- Direct SSH droplet debugging via spelix-droplet alias (~/.ssh/config + ~/.ssh/claude_spelix). Codified in CLAUDE.md "Droplet Debugging (SSH)" section.
- Migrated pose_extraction.py from mediapipe.solutions.pose.Pose (legacy, not on Linux wheels) to mediapipe.tasks.python.vision.PoseLandmarker (modern, cross-platform). BlazePose Heavy .task file baked into Docker image at build via curl.
- Bind-mount ./config:/app/config:ro in docker-compose.prod.yml — cleanest way to get config/ into the container without restructuring repo (config/ lives at repo root, above the backend/ build context).
- start_analysis is the canonical owner of queued → quality_gate_pending transition. Pipeline picks up at quality_gate_pending and transitions to processing. (Was duplicated in both — removed from pipeline.)
- Status table now allows queued → failed and quality_gate_pending → failed for operational failures (distinct from quality_gate_rejected which is reserved for actual user-content quality rejection by the predicate).
- Pre-generate UUIDs at construction time (id=gen_uuid()) instead of relying on SQLAlchemy default=, because default= runs at INSERT time and any code that reads .id before flush sees None.
- The doubled "videos/videos/{id}/" storage path is a known cosmetic issue (task #14) — internally consistent so not blocking, defer to a follow-up PR.

## notes
- Session 13: cleared TWELVE layers of dormant Phase 0 bugs across PRs #3-#14. End-to-end worker pipeline now runs in production for the first time ever. Verified by manually re-enqueuing orphan analysis row 214bf593 — pipeline ran 100.48s, transitioned through states cleanly, produced structured quality_gate_result with real metrics from MediaPipe pose extraction.
- Test fixture e2e/fixtures/squat-high-bar.mp4 fails resolution (360p < 720p) and framing (8% < 30%) gates. This is a fixture quality issue, not a pipeline bug. Need a real 720p+ side-view squat video to test the full success path.
- Subsystems NOT yet exercised in production (because the orphan row got rejected before reaching them): Anthropic coaching call, OpenAI keyframe analysis, WeasyPrint PDF, Realtime status subscriptions, artifact upload to Storage. Each will surface as error_message on the row OR via the global exception handler if it fails.
- 960 backend tests, 178 frontend tests, ruff/pyright/tsc clean. CI green on all 12 PRs.
- Main key learning: mocking entire third-party modules (mediapipe, supabase, the repo layer) masked dormant bugs for months. Future tests should exercise real construction paths with the third-party modules patched at their source.
