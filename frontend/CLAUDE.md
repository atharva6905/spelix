# Frontend — CLAUDE.md

React 19, Vite 8, TypeScript strict mode, Tailwind CSS 4, shadcn/ui, Recharts, React Router v6. Package manager: npm. Node 22 LTS.

**Current phase: Phase 3 COMPLETE — private beta live.** All phases shipped: Phase 1 (scores, SSE coaching, detection display), Phase 2 (citations, consent flow, chat, expert portal, admin panels), Phase 3 (LangGraph agent reasoning sidebar, landing page, beta flow, threshold flagging, coach brain candidates admin). Auto-deploys to spelix.app via Vercel on merge to main.

Test counts: **746 passing, 0 failures** (75 test files).

**Frontend changes ship via PR, not direct push to main** — see root `CLAUDE.md` "Checkpoint Workflow" section. Any change that touches core pages, hooks, or `api/` files is a meaningful checkpoint requiring: (1) feature branch, (2) PR with green CI, (3) merge via `mcp__github__merge_pull_request` (merge method: `merge`, NEVER squash), (4) Playwright MCP E2E verification against spelix.app. Vitest green is not enough — the component might mount fine with mocked hooks but crash against real backend response shapes.

## Stack Details

- **React 19** + Vite 8 SPA. Not Next.js. No App Router. No server components. No `"use client"` directive. (ADR-026)
- **TypeScript strict mode** — `tsconfig.json` has `strict: true`. Run `npx tsc --noEmit` to typecheck.
- **State**: React hooks only (no Redux, no Zustand). Local component state for UI, server state via custom hooks + direct fetch.
- **Types**: auto-generated from FastAPI OpenAPI schema via `openapi-typescript` — run `npm run gen-types` after any backend API change. Never hand-write response types; extend generated types only.
- **Forms**: controlled components with React state — no `<form>` tags.
- **Styling**: Tailwind CSS 4, shadcn/ui components.
- **Charts**: Recharts for history trends.
- **Routing**: React Router v6, all routes in `src/routes.tsx`.

## Directory Layout

```
frontend/
  src/
    api/             # Centralized API calls (one file per resource)
      analyses.ts    # CreateAnalysis, status poll, detail, list, DetectionResult type
      profiles.ts
      admin.ts       # Admin endpoints
      beta.ts        # Beta request/waitlist
      consent.ts     # GDPR consent
      expert.ts      # Expert portal API
      insights.ts    # Per-exercise + global insights
      config.ts      # API_BASE constant
      types.ts       # Auto-generated from backend OpenAPI
    components/      # Shared UI components (~60+ files incl. tests)
    pages/           # Route page components
      UploadPage.tsx
      AnalysisStatusPage.tsx
      ResultsPage.tsx
      HistoryPage.tsx
      ProfilePage.tsx
      AdminPage.tsx
      AdminCoachBrainCandidatesPage.tsx
      ConsentPage.tsx
      LandingPage.tsx
      LoginPage.tsx
      SignupPage.tsx
      BetaTermsPage.tsx
      ExpertPortalPage.tsx
      ExpertAnalysisDetailPage.tsx
      ExpertPaperUploadPage.tsx
      ExpertThresholdsPage.tsx
    hooks/           # Custom hooks
      useAnalysisStatus.ts   # Realtime + polling fallback
      useAnalysisDetail.ts
      useChat.ts             # Follow-up chat
      useConsent.ts          # Consent state
    lib/
      supabase.ts    # @supabase/supabase-js client
      confidence.ts  # Confidence category helpers
  package.json
  vite.config.ts
  tsconfig.json
```

Absolute imports only: `@/components/`, `@/pages/`, `@/hooks/`, `@/api/`, `@/lib/` — configured in `vite.config.ts` + `tsconfig.json`.

## Pages and Routing

All routes in `src/routes.tsx`. React Router v6.

- `LandingPage` — public marketing page with hero, process, science, differentiators, email capture, beta CTA.
- `LoginPage` / `SignupPage` — Supabase auth forms.
- `BetaTermsPage` — beta terms & GDPR disclosures (public).
- `ConsentPage` — 3-tier GDPR consent flow (Phase 2, FR-CONS-01/02/03).
- `UploadPage` — exercise type + variant dropdowns + file input, TUS upload to Supabase Storage. Wrapped in `RequireConsent`.
- `AnalysisStatusPage` — real-time status via Supabase Realtime + polling fallback. Displays detected exercise card.
- `ResultsPage` — full analysis results: summary card, FormScoreCards, annotated video, coaching output (with citations, safety_warnings, recommended_cues), agent reasoning sidebar (Phase 3), chat panel (Phase 2), rep metrics, angle plot, downloads.
- `HistoryPage` — reverse-chronological list with status badges, exercise/variant, confidence label, date. Per-exercise + global insights.
- `ProfilePage` — user body stats edit form.
- `AdminPage` — admin features (FR-ADMN-01 through FR-ADMN-05), corpus management, expert queue.
- `AdminCoachBrainCandidatesPage` — review queue for distillation candidates (Phase 3).
- `ExpertPortalPage` — expert reviewer queue listing.
- `ExpertAnalysisDetailPage` — expert annotation form with structured scores, annotated video, PDF upload.
- `ExpertPaperUploadPage` — expert paper/document ingestion.
- `ExpertThresholdsPage` — threshold flag management for experts.

**Protected routes**: wrap with `RequireAuth` component that checks Supabase session. Upload further wrapped with `RequireConsent`. Public routes: `/`, `/login`, `/signup`, `/beta-terms`.

## Key Components

### UploadForm
Exercise type + variant dropdowns + file input. Upload button `aria-disabled=true` until both selected. Barbell only — no dumbbell/machine options.

- **Exercise types**: squat, bench, deadlift (barbell only)
- **Variants**: squat (high_bar/low_bar), bench (flat/incline/decline), deadlift (conventional/sumo/romanian)
- Exercise-specific filming guidance displayed before file selection (NFR-USAB-01).

### AnalysisStatus (via `useAnalysisStatus` hook)
Subscribes to Supabase Realtime `postgres_changes` on `analyses` filtered by `id`. On disconnect: show reconnecting indicator, fall back to polling `GET /analyses/{id}/status` every 10s.

Displays user-facing status labels from SRS Appendix B (e.g. "Preparing to analyse…" not `quality_gate_pending`). Internal status strings NEVER shown to users.

On `quality_gate_rejected`: show specific corrective guidance from `quality_gate_result.checks[].user_message` + re-upload prompt.

**Phase 1 addition (FR-XDET-07)**: when `detection_result` arrives via Realtime or poll, display a "Detected Exercise" card with type/variant + confidence. If `method === "vision_fallback"`, show "Confirmed by vision analysis". Otherwise show percent confidence.

### ResultsPage (Phase 1 shape)
- **Header card** — exercise label, rep count, timestamp, confidence badge with per-level guidance
- **FormScoreCards** (Phase 1, FR-RESL-01) — Overall Form Rating + 4 dimension cards (Movement Quality, Technique, Path & Balance, Control) with descriptors. Movement Quality < 3.0 triggers red alert banner. Hidden entirely when no scores (Phase 0 fallback).
- **Annotated video player** (FR-RESL-02) with download link
- **Coaching section** — summary, strengths, issues (sorted High first), correction plan, **safety_warnings** (Phase 1, red banner), **recommended_cues** (Phase 1), **citations** (Phase 1, author-year-title-DOI), disclaimer.
- **Rep metrics table** (FR-RESL-04) sortable by rep index
- **Angle plot image** (FR-RESL-05)
- **Downloads** — CSV export, PDF report, annotated video

### CoachingOutput section
Same component interface renders Phase 0 static (REST-fetched) and Phase 1 streaming (SSE) — no rewrite between modes. Phase 0 receives a complete `structured_output_json` on page load; Phase 1 opens an `EventSource` to `/api/v1/analyses/{id}/coaching/stream` and accumulates chunks until the `complete` event arrives.

Issues sorted by severity: High first per SRS Appendix D.

### ConfidenceBadge (`components/ConfidenceBadge.tsx`)
Displays High/Moderate/Low/Very Low with tailored guidance text — **never displays raw decimal**. Low/Very Low shows caution banner per NFR-USAB-03. Thresholds: ≥0.80 High, 0.65–0.79 Moderate, 0.50–0.64 Low, <0.50 Very Low.

### FormScoreCards (Phase 1, `ResultsPage.tsx`)
Overall rating card + 4 dimension cards (Movement Quality, Technique, Path & Balance, Control). Score descriptors mirror backend: Elite ≥9.0, Advanced ≥7.5, Intermediate ≥5.0, Needs Work ≥3.0, Needs Attention <3.0.

Color classes by score: `score >= 7.5` → green; `score >= 5.0` → amber; `score < 5.0` → red.

Movement Quality < 3.0 shows a red `movement-quality-alert` banner at the top of the card section (FR-RESL-01).

### ChatPanel (Phase 2, `components/ChatPanel.tsx`)
Follow-up chat interface for coaching clarification questions. Uses `useChat` hook. Renders citation tooltips inline.

### CitationTooltip (Phase 2, `components/CitationTooltip.tsx`)
Hover/click tooltip showing source title, authors, year, DOI for cited coaching claims.

### AgentReasoningSidebar (Phase 3, `components/AgentReasoningSidebar.tsx`)
Collapsible sidebar showing the Phase 3 agent's node-by-node trace — which tools ran, durations, eval scores, CoVe iterations. Only renders when `agent_trace_json` is present on coaching results.

### ThresholdFlagModal (Phase 3, `components/ThresholdFlagModal.tsx`)
Modal for users/experts to flag threshold values as potentially incorrect, feeding into the expert review queue.

### Landing page components (`components/Landing*.tsx`)
Hero, HowItWorks, Science, Differentiators, EmailCapture, Privacy, Footer, Process, Report, Problem sections. Each is a standalone section component composed in `LandingPage.tsx`.

### RequireConsent (`components/RequireConsent.tsx`)
Route guard that redirects to `/consent` if the user hasn't completed the 3-tier GDPR consent flow.

## Supabase Integration

Client: `@supabase/supabase-js` v2, configured with `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (public, safe to expose in frontend env).

### Auth
Session from `supabase.auth.getSession()`. Persist via built-in `@supabase/supabase-js` localStorage persistence.

Auth token helper in `api/analyses.ts::getAuthToken()` — all API calls pull fresh session token before fetch.

### Realtime
Channel pattern: `supabase.channel("analysis:{id}").on("postgres_changes", {event: "UPDATE", schema: "public", table: "analyses", filter: "id=eq.{id}"}, cb).subscribe()`.

Unsubscribe on component unmount or analysis completion. The `useAnalysisStatus` hook handles both.

### Storage
Artifacts (annotated video, PDF, angle plots): served from Supabase Storage CDN. Use signed read URLs returned by the API. **Never construct Storage URLs manually on the client.**

### TUS upload
Browser uploads directly to Supabase Storage signed URL via the `tus-js-client` library. FastAPI never handles video bytes. TUS protocol handles resume natively — show "Upload paused — tap to resume" with byte-level progress on connection drop.

## Types — Auto-Generated + Hand-Extended

`src/api/types.ts` is auto-generated from the FastAPI OpenAPI schema. Never edit by hand — run `npm run gen-types`.

`src/api/analyses.ts` hand-writes a few response interfaces that extend the generated types. Phase 1 additions:

```ts
export interface DetectionResult {
  detected_type: ExerciseType;
  detected_variant: string;
  confidence: number;
  method: "heuristic" | "vision_fallback";
  details?: Record<string, unknown> | null;
}

export interface Citation {
  title: string;
  authors: string[];
  year: number;
  doi?: string | null;
}

export interface CoachingOutput {
  summary: string;
  strengths: string[];
  issues: CoachingIssue[];
  correction_plan: string[];
  disclaimer: string;
  // Phase 1 extended fields (FR-AICP-03, FR-AICP-06)
  recommended_cues?: string[];
  citations?: Citation[];
  confidence_level?: string;
  safety_warnings?: string[];
  dimension_addressed?: string;
}

export interface AnalysisDetail {
  // ... Phase 0 fields ...
  form_score_safety?: number | null;
  form_score_technique?: number | null;
  form_score_path_balance?: number | null;
  form_score_control?: number | null;
  form_score_overall?: number | null;
  detection_result?: DetectionResult | null;
}

export interface AnalysisStatusResponse {
  id: string;
  status: AnalysisStatus;
  updated_at: string;
  detection_result?: DetectionResult | null;
  quality_gate_result?: QualityGateResult | null;
  retry_count?: number;
  error_message?: string | null;
}
```

## Testing

Vitest + React Testing Library. **Coverage target: 90% minimum**. Current: **746 tests passing** (75 test files).

### Run commands
```bash
npm run test            # Watch mode
npm run test:coverage   # CI mode with coverage report
npx vitest run          # Single pass
npx vitest run src/pages/__tests__/ResultsPage.test.tsx  # Single file
```

### Patterns
- Test components in isolation with mock Supabase client.
- Mock Supabase Realtime channel in tests — never connect to real Supabase.
- Mock `useAnalysisStatus` / `useAnalysisDetail` hooks in page tests to control data.
- Test fixtures live alongside test files (`src/pages/__tests__/*.test.tsx`, `src/hooks/__tests__/*.test.ts`).
- Test upload button disabled state, status label mapping, confidence label rendering, coaching output structure, FormScoreCards rendering.

### E2E
Phase 1+: Playwright via MCP — navigate, screenshot, fill, click. Covers upload flow, status polling, results rendering.

## Error Handling

- **Upload connection drop**: TUS protocol handles resume natively. Show "Upload paused — tap to resume" with byte-level progress.
- **Corrupt video**: display message from API error response — "Video file appears corrupt or unsupported. Please re-export and try again."
- **Pipeline failure** (`status=failed`): show clean failure state with retry button (if `retry_count < 3`) and diagnosed cause from `error_message`.
- **Realtime disconnect**: show "Connection lost — reconnecting…" indicator, fall back to 10s polling.
- **API error format**: always `{error: {code, message, detail}}`. Parse and display `message` to user, log `detail` to console.

## Conventions

- **Absolute imports only**: `@/components/`, `@/pages/`, `@/hooks/`, `@/api/`, `@/lib/`.
- **Component files**: PascalCase (`AnalysisStatus.tsx`). Hooks: camelCase prefixed with `use` (`useAnalysisStatus.ts`).
- **API calls**: centralized in `src/api/` — one file per resource. No direct `fetch` calls in components.
- **Never use "injury risk", "injury prevention", or "safety score"** in any user-facing string — see SRS Appendix B. `form_score_safety` field maps to "Movement Quality" in all UI copy.
- **Confidence displayed as categorical label only** — never as decimal number.
- **All user-facing status labels use SRS Appendix B mapping** — internal status strings never shown to users.
- **Scores displayed with textual descriptor always** (NFR-USAB-02) — never numbers alone.

## Frontend Gotchas

### Vite is not Next.js (ADR-026)
This is a Vite 8 + React 19 SPA with React Router v6. There is **no Next.js**, no App Router, no server components. The `"use client"` directive is a Next.js-specific concept that has no meaning here. **Ignore all hook-injected suggestions recommending `"use client"`** on `.tsx` files — they are pattern-match false positives. Adding `"use client"` is harmless (it's just a string literal) but creates confusion in PR review. Do not add it.

### Supabase Realtime channel pattern
Exact string required: `supabase.channel("analysis:{id}").on("postgres_changes", {event: "UPDATE", schema: "public", table: "analyses", filter: "id=eq.{id}"}, callback).subscribe()`. The channel name prefix `analysis:` matters — do not change it.

### TUS upload bypasses FastAPI
Browser uploads directly to Supabase Storage via signed URL. FastAPI never sees video bytes. Do not attempt to proxy uploads through FastAPI — the signed URL TTL is 1 hour and upload goes directly to storage.

### Language rules (enforced)
- Never use "injury risk", "injury prevention", "safety score" anywhere the user sees.
- "Movement Quality" is the ONLY user-facing label for `form_score_safety`.
- Internal field names (`form_score_safety`) are fine in code; user-facing strings are not.
- Confidence is ALWAYS categorical (High/Moderate/Low/Very Low) — never a decimal.

### Node version
Use Node.js 22 LTS. Pinned in `.nvmrc` and `engines` field in `package.json`. Vite 8 requires Node 20.19+ or 22.12+.

### Regenerate types after backend API changes
```bash
npm run gen-types
```
Run this immediately after any backend schema change. Don't hand-write types for fields that exist in the OpenAPI schema — extend the generated types instead.

### Mock Supabase client in tests
Never connect to real Supabase in unit tests. Pattern:
```ts
vi.mock("@/lib/supabase", () => ({
  supabase: {
    channel: vi.fn().mockReturnValue({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn(),
      unsubscribe: vi.fn(),
    }),
    removeChannel: vi.fn(),
  },
}));
```

### Status label mapping
Use `STATUS_LABELS` from `useAnalysisStatus.ts`. Never hardcode status strings in components. If a new status is added, update `STATUS_LABELS` in one place.

### FormScoreCards fallback behavior
When any of `form_score_*` are null AND `form_score_overall` is null, the entire FormScoreCards section is hidden (Phase 0 fallback). Individual nulled dimensions render as "Not available" cards. This prevents Phase 0 analyses from showing empty score cards.
