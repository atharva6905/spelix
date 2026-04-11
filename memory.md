# memory.md — Agent Persistent State

phase: 2
task: post-storage-fix-config-block
status: blocked
last_modified: [backend/app/services/insights.py, backend/app/workers/cleanup.py, backend/tests/unit/test_insights.py, .claude/handoff.md, backend/app/api/v1/analyses.py]
failing_tests: []
blockers: [supabase_service_role_key_invalid_on_droplet]
srs_deviations: []
next_action: "USER ACTION: rotate SUPABASE_SERVICE_ROLE_KEY on DigitalOcean droplet (see .claude/handoff.md). Then re-run Playwright MCP E2E end-to-end on spelix.app — first time the worker pipeline will run on real Supabase Storage."
session_count: 12
last_session: 2026-04-11

## decisions_since_plan
- PR #3 (94dd0fa): wired StorageService factory + initial global exception handler
- PR #4 (754393c): switched _make_storage_service + worker _build_supabase_client to acreate_client (async). Module-level cache. Enriched exception envelope to include detail.type + detail.message.
- PR #5 (02fcc88): stripped tzinfo on InsightsService.global_insights cutoff and cleanup cron cutoff (asyncpg can't compare tz-aware to TIMESTAMP WITHOUT TIME ZONE column)

## notes
- Phase 1 was "complete" but production upload had been broken since Phase 0 — ALL tests mocked the storage factory at the dependency-override level, so no test ever exercised the real factory path
- Three-layer dormant bug uncovered this session via Playwright MCP E2E:
  - Layer 1: factory returned client=None (PR #3)
  - Layer 2: sync vs async supabase client (PR #4)
  - Layer 3 (separate): tz-aware vs tz-naive datetime in /insights/global (PR #5)
- 943 backend tests, 177 frontend tests, all green. Was 895 backend at session start.
- Production POST /analyses now reaches Supabase Storage successfully but gets 403 "signature verification failed" — droplet's SUPABASE_SERVICE_ROLE_KEY is wrong
- The enriched global exception handler is permanent — production crashes now show actual exception type+message in JSON envelope, no SSH required to debug
- Next session: confirm droplet env fix, then run end-to-end E2E (will be FIRST true end-to-end run on prod ever — watch for further dormant bugs in worker pipeline: ARQ Redis URL, MediaPipe model download, Anthropic key, OpenAI key, threshold config, WeasyPrint fonts)
