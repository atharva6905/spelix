---
name: frontend-gotcha-checklist
description: Fast pass/fail checklist for reviewing Spelix frontend diffs, sourced from frontend/CLAUDE.md gotchas section
metadata:
  type: reference
---

Run against every frontend diff (from frontend/CLAUDE.md gotchas):

1. Absolute imports only — `@/components`, `@/pages`, `@/hooks`, `@/api`, `@/lib`. Flag any `../` relative import.
2. No `"use client"` — Vite 8 + React 19 SPA, not Next.js. Hook may suggest it; false positive. Harmless but creates PR confusion -> MEDIUM.
3. No direct `fetch` in components — network goes through api/*.ts helpers. `fetch` belongs only inside the api-layer transport fn (e.g. expertFetch).
4. SaMD copy — NEVER "injury risk"/"injury prevention"/"safety score" in user-facing strings. form_score_safety -> "Movement Quality" only. (Also security-reviewer scope; note OUT-OF-SCOPE if it's the only finding.)
5. Supabase mock in tests — never connect to real Supabase. `vi.mock("@/lib/supabase", ...)`. Realtime channel string `analysis:{id}` is exact-match; don't change the prefix.
6. Never construct Storage URLs client-side — use signed URLs from the API.
7. TUS upload direct to Storage — FastAPI never handles video bytes; don't proxy uploads through FastAPI.

Note: Vitest green is NOT sufficient for user-facing PRs — frontend/CLAUDE.md mandates Playwright E2E against spelix.app because mocked mounts hide real-backend-shape crashes.
