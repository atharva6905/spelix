# memory.md — Agent Persistent State

phase: 2
task: phase-2-planning-kickoff
status: ready
last_modified: [.claude/commands/adr.md, .claude/commands/backlog.md, CLAUDE.md, .claude/handoff.md, decisions.md]
failing_tests: []
blockers: [test_fixture_quality_below_gate_thresholds]
srs_deviations: []
next_action: "Start Phase 2 planning in a new session: re-read SRS Phase 2 Must filter (rg pattern in CLAUDE.md general rules), seed backlog.md Phase 2 section, activate spelix-rag-engineer + spelix-corpus-curator agents, run /phase transition gate, then /plan P2-001 (Migration 004 — rag_documents + expert_annotations). See .claude/handoff.md for full kickoff sequence."
session_count: 13
last_session: 2026-04-11

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
