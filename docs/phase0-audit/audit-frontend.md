# Frontend Audit Report — Phase 0

*Audited: 2026-04-09 | Auditor: Claude Sonnet 4.6 subagent*
*Scope: All files under `frontend/src/` cross-referenced against `docs/SRS.md`*

---

## SRS Compliance

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| **FR-XDET-09** | Upload button `aria-disabled=true` until both exercise type AND variant selected | **FAIL** | `aria-disabled` is toggled correctly but the `disabled` HTML attribute on the `<button>` is bound to `submitting` only, not to `uploadDisabled`. When `selectionComplete` is false the button is NOT natively disabled — only `aria-disabled="true"` is set. A user can tab-focus and press Enter/Space to invoke `handleSubmit`, which exits early via guard but the button itself is not truly disabled. SRS requires `aria-disabled=true` **and** the button must not be activatable. Fix: also set `disabled={uploadDisabled \|\| submitting}`. |
| **FR-UPLD-08** | Upload progress indicator visible during upload | **FAIL** | No TUS upload is performed at all. `createAnalysis()` calls `POST /analyses` and immediately navigates to `/analysis/:id` — the `upload_url` returned by the backend is never used client-side. No byte-level progress indicator exists. This is a partial implementation gap: the upload step (TUS) and progress UI are missing entirely. |
| **FR-UPLD-09** | Filming guidance displayed BEFORE file selection, per exercise | **PASS** | Guidance box is rendered before the file input and updates when exercise type changes. Default guidance shown before any selection. |
| **FR-UPLD-19** | 7-day download banner on results page | **WARN** | Banner text reads: *"Artifacts (video, plot, PDF) are available for 7 days from the date of analysis."* SRS FR-UPLD-19 requires verbatim: *"Your results and video are available for 7 days. Download your PDF or annotated video before they expire."* The implemented text is a paraphrase; consider aligning to SRS wording. |
| **FR-RESL-01a** | Phase 0 summary card: exercise/variant + rep count + confidence label + timestamp | **FAIL** | The summary card shows exercise/variant and confidence badge. **Rep count is never displayed.** `AnalysisDetail` has `rep_metrics[]` so count is derivable via `analysis.rep_metrics.length`, but neither the card nor any other element shows rep count. Timestamp (`created_at`) is also absent from the card — only the analysis ID is shown. Both are required by FR-RESL-01a. |
| **FR-RESL-02** | Annotated video playable inline + downloadable | **WARN** | Video is playable inline (`<video controls>`). However there is **no MP4 download link** for the annotated video. FR-RESL-02 and FR-XPRT-01 both require a downloadable MP4. The Downloads section only has CSV and PDF links. The `annotated_video_path` from the API is only used as the `<video src>`, not wrapped in an `<a download>` link. |
| **FR-RESL-03** | Coaching rendered as static markdown (Phase 0) | **WARN** | Coaching is rendered as structured React JSX (summary, strengths, issues, correction plan), not as markdown. The SRS says "rendered as static markdown" but the structured JSON approach is arguably better UX and the CLAUDE.md describes `structured_output_json` rendering. However no markdown renderer is used at all — if the backend ever returns raw markdown strings these will render as plain text. Low risk for Phase 0 given structured output, but flag. |
| **FR-RESL-04** | Per-rep metrics table, sortable by rep index | **FAIL** | `RepMetricsTable` renders a table sorted by render order (which is the API order) but there is **no sort control**. SRS requires the table to be sortable by rep index. No `<th>` has a click handler or sort indicator. |
| **FR-RESL-08** | Confidence as categorical label only, never raw decimal; guidance text per level | **FAIL (partial)** | Confidence is displayed as a categorical label (High/Moderate/Low/Very Low) — raw decimals are never shown to end users. **However** the SRS-required guidance text per level is incomplete: the `ConfidenceBadge` only shows a generic caution banner for Low/Very Low. SRS FR-RESL-08 requires specific text: High → "results are reliable"; Moderate → "partial occlusion detected"; Low → "results may be unreliable — try better lighting or camera position"; Very Low → "unable to score reliably — please re-record." The current banner says *"Results may be less accurate — ensure your full body is visible and well-lit"* which covers Low but not the distinct Very Low message, and High/Moderate have no guidance text at all. |
| **FR-RESL-08 (thresholds)** | Confidence buckets: ≥0.80 High, 0.65–0.79 Moderate, 0.50–0.64 Low, <0.50 Very Low | **FAIL** | The implemented thresholds are: ≥0.8 High, ≥0.6 Moderate, ≥0.4 Low, <0.4 Very Low. SRS Phase 0 buckets per FR-CVPL-16 are ≥0.80 High, **0.65–0.79** Moderate, **0.50–0.64** Low, **<0.50** Very Low. The boundary between Moderate and Low is 0.65 in SRS but 0.60 in code; Low/Very Low boundary is 0.50 in SRS but 0.40 in code. This miscategorises a score of 0.60 as "Moderate" when it should be "Low", and 0.40–0.49 as "Low" when SRS says "Very Low". This same bug exists in three places: `ResultsPage.tsx`, `HistoryPage.tsx`, and `InsightsPanel.tsx`. |
| **FR-RESL-11** | Three-tier disclaimer visible on results page | **FAIL** | A coaching-level disclaimer appears inside `CoachingOutputSection` (verbatim SRS Appendix D text). However the **three-tier page-level disclaimer framework** from FR-RESL-11 is completely absent. Required: (a) Primary fitness/not medical advice; (b) AI transparency/probabilistic estimates; (c) Assumption of risk. None of these three panels are rendered anywhere on ResultsPage. |
| **FR-RESL-13** | Realtime subscription + reconnection indicator + 10s polling fallback | **PASS** | `useAnalysisStatus.ts` subscribes via Supabase Realtime `postgres_changes` with correct channel pattern. On `CHANNEL_ERROR`/`TIMED_OUT`/`CLOSED`: sets `isReconnecting=true` and starts 10s polling. `AnalysisStatusPage` shows *"Connection lost — reconnecting…"* banner when `isReconnecting`. Polling stops when terminal status received. Compliant. |
| **FR-HIST-01** | Reverse-chronological list with status badge, exercise/variant, confidence, date | **PASS** | `HistoryPage` renders analysis list in API order (backend is responsible for ordering), with status badge, exercise/variant labels, confidence category badge, and formatted date. |
| **FR-HIST-06** | Recharts trend charts | **PASS** | `TrendChart` uses Recharts `LineChart`/`BarChart` for confidence trend and rep count trend. Renders via `InsightsPanel`. |
| **NFR-USAB-01** | Filming guidance before file selection | **PASS** | Guidance block appears in DOM above the file input unconditionally. |
| **NFR-USAB-02** | Scores always with textual descriptor, never numbers alone | **PASS** | Confidence is always shown as a label ("High", "Moderate", etc.). No raw scores exposed to users in the user-facing interface. |
| **NFR-USAB-03** | Low-confidence actionable guidance (not generic "try again") | **WARN** | Low/Very Low shows: *"ensure your full body is visible and well-lit when recording"* — actionable but generic. The SRS specifies distinct messages per level (see FR-RESL-08 row above). |
| **NFR-USAB-08** | WCAG 2.1 AA: contrast ≥4.5:1, keyboard nav, ARIA labels on score cards | **WARN** | No automated contrast check possible from code review alone. Structural observations: (1) `ConfidenceBadge` has no `aria-label` on the score card itself — only text content. (2) `RepMetricsTable` confidence cell has no ARIA label. (3) Severity badges in coaching issues use color + text (compliant). (4) `AnalysisRow` in history uses `role="button"` with `tabIndex=0` and `onKeyDown` for Enter/Space — keyboard compliant. (5) Annotated `<video>` has no captions (`eslint-disable-next-line jsx-a11y/media-has-caption` suppresses the check). Flag for manual contrast audit. |
| **NFR-USAB-09** | Error boundaries at component level | **FAIL** | `ErrorBoundary` component exists and is well-implemented, but it is **never used** anywhere in the app. `routes.tsx`, `App.tsx`, and all page components import it zero times. The SRS requires boundaries at the component level — SSE stream interruption, malformed analysis data, etc. should be caught locally. Currently no error boundary wraps any route or component. |
| **Appendix B — status labels** | Internal status strings never shown to users | **FAIL (partial)** | `useAnalysisStatus.ts` STATUS_LABELS map is correct for the status page. However `AdminPage.tsx` renders raw internal status values directly in the Analysis Log table (line 397: `{analysis.status}` — e.g. "quality_gate_pending" shown verbatim in admin UI). While admin-only, the SRS Appendix B says internal names should only appear in code. Minor: `ANALYSIS_STATUSES` in AdminPage also includes `"quality_gate_passed"` which is not a valid status per the SRS (valid are: queued, quality_gate_pending, quality_gate_rejected, processing, coaching, completed, failed). |
| **Appendix B — quality_gate_pending label** | Should be "Preparing to analyse…" | **FAIL** | SRS Appendix B specifies: `quality_gate_pending` → "Preparing to analyse…". The implementation in `useAnalysisStatus.ts` maps `quality_gate_pending` → "Checking video quality…" and `queued` → "Preparing to analyse…". The mapping is swapped relative to SRS. |
| **Appendix B — quality_gate_rejected label** | Should be "Video could not be processed" | **FAIL** | SRS Appendix B specifies `quality_gate_rejected` → "Video could not be processed". Implementation maps it to "Video quality check failed". |
| **NFR-USAB-06** | Medical disclaimer visible on results page | **WARN** | Coaching disclaimer (Appendix D text) is shown inside CoachingOutputSection. However this is only visible if there is coaching data. The page-level three-tier disclaimer (FR-RESL-11) is absent (see that row). |

---

## Type Safety Findings

### `as any` Casts

Two instances found:

1. **`frontend/src/pages/AdminPage.tsx` line 544:**
   ```ts
   const payload = session.user as any;
   ```
   Used to access `app_metadata.role`. The Supabase `User` type does expose `app_metadata` as `Record<string, unknown>` — the `as any` is unnecessary; access via `session.user.app_metadata?.role as string` with a proper guard is type-safe. This also duplicates the same logic in `AppLayout.tsx` which uses `data.session?.user?.app_metadata?.role` without an `as any` cast — inconsistent.

2. **`frontend/src/hooks/useAnalysisStatus.ts` line 104:**
   ```ts
   "postgres_changes" as any,
   ```
   Required because `@supabase/supabase-js` v2 `.on()` method has strict overloads that don't always accept the string literal via TypeScript inference. This is a known Supabase JS typing limitation; the cast is pragmatic. Document why.

### `@ts-ignore` Directives

None found. Clean.

### API Types: Generated vs Hand-Written

**CRITICAL TECH DEBT.** `frontend/src/api/types.ts` is nominally auto-generated by `openapi-typescript` (script: `npm run generate-types`) but its current content is:
```ts
export type paths = Record<string, never>;
export type webhooks = Record<string, never>;
export type components = { schemas: Record<string, never>; };
export type $defs = Record<string, never>;
export type operations = Record<string, never>;
```
All types are **empty stubs**. The actual API types used throughout the codebase (`AnalysisDetail`, `RepMetricDetail`, `CoachingOutput`, etc.) are hand-written in `src/api/analyses.ts`, `src/api/insights.ts`, `src/api/profiles.ts`, and `src/api/admin.ts`. This means:

- Types are not validated against the real backend schema.
- Any backend contract change will silently break the frontend.
- The `generate-types` script only works if the backend is running — it has never been run against a live backend, or the output was discarded.

**Risk:** If the backend `AnalysisDetail` shape diverges (e.g., `rep_metrics` key rename, `coaching_result` becomes `coaching_results`), TypeScript will not catch it — the hand-written types will still compile.

**Recommendation:** Run `npm run generate-types` against a live backend and commit the generated file. Replace hand-written types in `api/*.ts` with references to the generated types.

### `CoachingOutputSection` Type Cast

In `ResultsPage.tsx` line 413:
```ts
structured={
  coachingData as Parameters<typeof CoachingOutputSection>[0]["structured"]
}
```
`coachingData` is typed as `CoachingOutput | null` which should be directly assignable to the `structured` prop interface — this cast suggests the types are slightly misaligned. The `CoachingOutput` interface has `summary: string` (required) but the component prop interface has `summary?: string` (optional). The cast papers over the mismatch rather than fixing the root type definition.

---

## Dependency Check

### `package.json` Analysis

All versions use `^` (caret) semver ranges — floating to the next minor/patch. No pinned versions.

| Package | Version Range | Concern |
|---------|--------------|---------|
| `react` | `^19.2.4` | Current stable. OK. |
| `react-dom` | `^19.2.4` | OK. |
| `react-router` | `^7.14.0` | React Router v7 (not v6). Correct. |
| `@supabase/supabase-js` | `^2.102.1` | Supabase JS v2. Correct. |
| `recharts` | `^3.8.1` | v3 is current. OK. |
| `typescript` | `~6.0.2` | Tilde range (patch-only). Correct for compiler. |
| `vite` | `^8.0.4` | Vite 8 (Rolldown). Matches stack spec. |
| `vitest` | `^4.1.3` | OK. |
| `tailwindcss` | `^4.2.2` | Tailwind CSS v4. Matches stack spec. |

**Floating version concern:** Production dependencies (`react`, `react-router`, `recharts`, `@supabase/supabase-js`) float to next minor. In a private personal project this is acceptable; for a production app, consider pinning exact versions and using `npm ci` in CI.

**Missing from `package.json`:** No TUS client library (e.g., `tus-js-client`) is installed anywhere. FR-UPLD-06 requires TUS resumable upload. Since `upload_url` is never used client-side (see FR-UPLD-08 finding), TUS upload is entirely unimplemented.

**Missing:** No `openapi-typescript` in devDependencies. The `generate-types` script in `scripts` references it but it is not listed as a dev dependency — the script would fail with `command not found`. This confirms the types were never actually generated.

**`package-lock.json`:** Present and committed. ✓

**`shadcn/ui`:** Listed in the stack spec (CLAUDE.md) but no shadcn/ui package appears in `package.json`. Components appear to be custom Tailwind instead. Not a defect but note the divergence from stated stack.

---

## Forbidden Strings

### "injury risk", "injury prevention", "safety score"
**PASS — None found** in `frontend/src/`.

### Hardcoded `localhost:8000`
**WARN — Found in 5 files:**
- `src/api/types.ts` — comment only (`// Run ... requires backend running at http://localhost:8000`). Not runtime code. Acceptable.
- `src/api/analyses.ts` — `import.meta.env.VITE_API_URL ?? "http://localhost:8000"` — runtime fallback. This is intentional dev fallback; production sets `VITE_API_URL` via `.env.production`. Low risk but note.
- `src/api/profiles.ts` — same pattern.
- `src/api/admin.ts` — same pattern.
- `src/api/insights.ts` — same pattern.
- `src/pages/ResultsPage.tsx` line 450 — inline `import.meta.env.VITE_API_URL ?? "http://localhost:8000"` inside JSX. The other files define `API_BASE` as a module-level constant; this inline usage is inconsistent and should use a shared constant.

**Recommendation:** Extract a single `API_BASE` constant into `src/lib/api.ts` and import it in all API files and pages. Eliminates duplication and the inline JSX usage.

### Raw confidence decimals displayed to users
**PASS** in user-facing UI. All confidence values shown to end users are categorical labels.

**WARN** in admin UI: `AdminPage.tsx` line 407 displays `analysis.confidence_score.toFixed(2)` as a decimal in the Analysis Log table. This is admin-only visibility, not an end-user surface. The SRS prohibition targets user-facing strings; admin panels are operational tooling. Acceptable, but document the exception.

**NOTE in TrendChart:** `TrendChart.tsx` Tooltip formatter shows `value.toFixed(2)` for the confidence trend chart. This is a hover tooltip on internal charts in the InsightsPanel — potentially user-visible. If the confidence trend chart is shown to end users (it is, via HistoryPage), the tooltip would display a raw decimal like "0.72" which violates FR-RESL-08 / NFR-USAB-02. **This is a violation.**

### "TODO" / "FIXME"
**PASS — None found** in `frontend/src/`.

---

## Summary of Critical Defects (Must Fix Before Phase 1)

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1 | **Critical** | `UploadPage.tsx` | TUS upload entirely missing — `upload_url` unused, no file transfer happens, FR-UPLD-06/08 unimplemented |
| 2 | **Critical** | `ResultsPage.tsx`, `HistoryPage.tsx`, `InsightsPanel.tsx` | Confidence thresholds wrong (0.60/0.40 vs SRS 0.65/0.50) — miscategorises ~15% of scores |
| 3 | **Critical** | `ResultsPage.tsx` | FR-RESL-11 three-tier disclaimer completely absent |
| 4 | **Critical** | `ResultsPage.tsx` | FR-RESL-01a missing rep count and timestamp from summary card |
| 5 | **High** | `useAnalysisStatus.ts` | Appendix B label mapping wrong: `quality_gate_pending` shows "Checking video quality…" (should be "Preparing to analyse…"), `quality_gate_rejected` shows "Video quality check failed" (should be "Video could not be processed") |
| 6 | **High** | All routes | `ErrorBoundary` component exists but is never used — NFR-USAB-09 unimplemented |
| 7 | **High** | `UploadPage.tsx` | `aria-disabled=true` set but button is still activatable via keyboard — FR-XDET-09 partially broken |
| 8 | **High** | `ResultsPage.tsx` | FR-RESL-04 rep metrics table is not sortable |
| 9 | **High** | `ResultsPage.tsx` | FR-RESL-08 per-category guidance text missing for High/Moderate; Low/Very Low use generic text |
| 10 | **High** | `ResultsPage.tsx` | FR-RESL-02 / FR-XPRT-01 no annotated video MP4 download link |
| 11 | **High** | `src/api/types.ts` | Generated types are empty stubs — all API types are hand-written with no contract validation |
| 12 | **Medium** | `TrendChart.tsx` | Tooltip shows raw decimal confidence to users — violates FR-RESL-08 |
| 13 | **Medium** | `AdminPage.tsx` | Raw status strings shown in analysis log; includes invalid status `quality_gate_passed` |
| 14 | **Medium** | `package.json` | `openapi-typescript` not listed as devDependency — `npm run generate-types` is broken |
| 15 | **Low** | Multiple `api/*.ts` files | `localhost:8000` fallback duplicated in 4 files + 1 inline JSX — extract to shared constant |
| 16 | **Low** | `AdminPage.tsx` | `as any` cast for `session.user` is unnecessary; inconsistent with `AppLayout.tsx` |
| 17 | **Low** | `FR-UPLD-19` | 7-day banner text is a paraphrase; SRS specifies verbatim wording |
