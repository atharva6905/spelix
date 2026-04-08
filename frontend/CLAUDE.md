# Frontend — CLAUDE.md

## Stack

React 19, Vite 8, TypeScript strict mode, Tailwind CSS 3, shadcn/ui, Recharts.
State: React hooks only (no Redux, no Zustand) — local component state for UI, server state via React Query or direct fetch.
Types: auto-generated from FastAPI OpenAPI schema via `openapi-typescript` — run `npm run gen-types` after any API change. Never hand-write API types.
Forms: controlled components with React state — no `<form>` tags.
Package manager: npm. Node 20+.

## Pages and Routing

React Router v6, all routes in `src/routes.tsx`.
Pages: `UploadPage`, `AnalysisStatusPage`, `ResultsPage`, `HistoryPage`, `ProfilePage`, `AdminPage`.
Protected routes: wrap with `RequireAuth` component that checks Supabase session.
Public routes: `/`, `/login`, `/signup`.

## Key Components

**UploadForm**: exercise type + variant dropdowns + file input. Upload button `aria-disabled=true` until both exercise type AND variant selected (FR-XDET-09). Exercise-specific filming guidance displayed before file selection (NFR-USAB-01). Exercises: squat (high-bar/low-bar), bench (flat/incline/decline), deadlift (conventional/sumo/Romanian). Barbell only — no dumbbell/machine options.
**AnalysisStatus**: subscribes to Supabase Realtime `postgres_changes` on `analyses` filtered by `id`. On disconnect: show reconnecting indicator, fall back to polling `GET /analyses/{id}/status` every 10s. Display user-facing status labels from SRS Appendix B (e.g. "Preparing to analyse…" not "quality_gate_pending"). On `quality_gate_rejected`: show specific corrective guidance from `quality_gate_result.checks[].user_message` + re-upload prompt.
**ResultsPage**: Phase 0 shows exercise/variant + rep count + confidence label + static coaching markdown. Layout uses responsive grid that accommodates Phase 1 expansion to four dimension score pills (Movement Quality, Technique, Path & Balance, Control) without structural rework. Annotated video player, angle plot image, and CSV download link.
**CoachingOutput**: renders `structured_output_json` — Phase 0 static, Phase 1 SSE stream. Same component interface; streaming mode is additive. Issues sorted by severity (High first per SRS Appendix D).
**ConfidenceLabel**: displays High/Moderate/Low/Very Low with tailored guidance text — never displays raw decimal. Low/Very Low shows caution banner per NFR-USAB-03.
**HistoryPage**: reverse-chronological analysis list with status badge, exercise/variant, confidence label, date. Per-exercise insights: 7-session rolling average confidence, rep count trend, most common quality gate warning, personal best confidence (FR-HIST-02). Global insights panel (FR-HIST-03).
**AdminPage**: user management, analysis metadata log, confidence audit panel, system health (ARQ queue depth, job success/failure rate). Phase 0 Tier 1 + Tier 2 features only (FR-ADMN-01 through FR-ADMN-05).

## Supabase Integration

Client: `@supabase/supabase-js` v2, configured with `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (public, safe to expose).
Auth: session from `supabase.auth.getSession()`, persist via built-in `@supabase/supabase-js` localStorage persistence.
Realtime channel pattern: `supabase.channel("analysis:{id}").on("postgres_changes", {event: "UPDATE", schema: "public", table: "analyses", filter: "id=eq.{id}"}, cb).subscribe()`. Unsubscribe on component unmount or analysis completion.
Artifacts (annotated video, PDF, angle plots): served from Supabase Storage CDN — use signed read URLs returned by API. Never construct Storage URLs manually on the client.

## Testing

Vitest + React Testing Library. 90% coverage minimum.
Test components in isolation with mock Supabase client.
E2E (Phase 1+): Playwright via MCP — navigate, screenshot, fill, click — covers upload flow, status polling, results rendering.
Run: `npm run test` (watch), `npm run test:coverage` (CI), `npx vitest run` (single pass).
Mock Supabase Realtime channel in tests — never connect to real Supabase in unit tests.
Test upload button disabled state, status label mapping, confidence label rendering, coaching output structure.

## Error Handling

Upload connection drop: TUS protocol handles resume natively. Show "Upload paused — tap to resume" with byte-level progress.
Corrupt video: display message from API error response — "Video file appears corrupt or unsupported. Please re-export and try again."
Pipeline failure (`status=failed`): show clean failure state with retry button (if `retry_count < 3`) and diagnosed cause from `error_message`.

## Conventions

Absolute imports only: `@/components/`, `@/pages/`, `@/hooks/`, `@/api/` — configured in `vite.config.ts` + `tsconfig.json`.
Component files: PascalCase (`AnalysisStatus.tsx`). Hooks: camelCase prefixed with `use` (`useAnalysisStatus.ts`).
API calls: centralized in `src/api/` — one file per resource (`analyses.ts`, `profiles.ts`). No direct `fetch` calls in components.
Never use "injury risk", "injury prevention", or "safety score" in any user-facing string — see SRS Appendix B.
Confidence displayed as categorical label only — never as decimal number.
`form_score_safety` field maps to "Movement Quality" in all UI copy.
All user-facing status labels use SRS Appendix B mapping — internal status strings never shown to users.
Error responses from API always follow `{error: {code, message, detail}}` — parse and display `message` to user, log `detail` to console.
Scores displayed with textual descriptor always (NFR-USAB-02) — never numbers alone.
