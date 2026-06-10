# spelix-security-reviewer — memory

(Persisted by the main agent on 2026-06-10 — the reviewer ran read-only and asked for these to be recorded.)

## Reviewed: issue #218 / PR #227 (DOI dedup, 2026-06-10) → PASS
- **Accepted risk**: `POST /expert/papers` 409 DUPLICATE_DOI leaks the existing paper's title + UUID to any expert/admin. Acceptable at single-partner private-beta scale; RE-FLAG if the expert role ever opens to multiple untrusted partners or the corpus becomes tenant-scoped.
- Reference: all `/expert/*` authz = `get_expert_reviewer_user` (`app/api/deps.py` ~221) — admits role ∈ {expert_reviewer, admin} from JWT `app_metadata.role` (service-role-write-only). JWT chain: ES256/RS256 JWKS + HS256 fallback, issuer check, guarded UUID parse.
- **Pre-existing, not regressed**: `complete_paper_upload` lacks an `uploaded_by` ownership check — any expert/admin can complete (or race-cleanup-delete) another's `uploading`-state row. Follow-up candidate if expert role multiplies.
- normalize_doi regexes are ReDoS-safe (anchored, bounded `\d{4,9}`, single `\S+`); input bounded by Field max_length=200.

## Reviewed: issue #219 (DOI required on expert upload form, frontend, 2026-06-10) → PASS
- Renders backend `error.message` for 409 DUPLICATE_DOI / 422 INVALID_DOI as a JSX text child at `ExpertPaperUploadPage.tsx` ~L323 — React-escaped, no HTML/attribute sink, XSS-safe. Re-escalate to CRITICAL only if a future PR moves this message into `dangerouslySetInnerHTML` or an `href`/attribute sink.
- The 409 message surfacing an existing paper's title client-side is the same #218 accepted-risk exposure (single-partner scale), now behind the page's expert/admin role gate (`isAuthorized` → `Navigate to="/"`); no UUID rendered.
- `doi` required is client-side gating only (submit-disable + trim); server-side `normalize_doi` validation remains authoritative.
- Re-verified fix2 (`0e4ddd3`) → PASS: `maxLength={200}` on the DOI input (mirrors backend `Field max_length=200`, defense-in-depth, backend authoritative) + in-handler empty-DOI guard rendering "DOI is required." through the same React-escaped `<p role="alert">{doiError}</p>` text-child sink — SaMD-clean, no new input sink, no weakening of prior guarantees.

## Reviewed: issue #220 (DOI display columns, 2026-06-10) → PASS
- DOI href-injection analysis: `https://doi.org/${doi}` is SAFE — scheme+host hardcoded literal, user input lands in path only; `javascript:` payloads become inert path text; React escapes text children. Re-escalate to CRITICAL only if a future PR removes the hardcoded prefix or drops `rel="noopener noreferrer"` (both cells have it: ExpertPortalPage.tsx ~298, AdminPage.tsx ~705).
- Standing HIGH (defense-in-depth, non-blocking): no DOI *schema-level* format validator on `rag_documents.doi` writers outside the expert API path — #218 validates at the API boundary (`normalize_doi`, 422 INVALID_DOI), but seed scripts/direct SQL bypass it. Resolves when seed script writes `normalize_doi(...)` to the column (follow-up flagged on PR #227).
- Role gates: ExpertPortalPage.tsx ~L407 (expert_reviewer/admin), AdminPage.tsx ~L1212 (admin only) — client-side checks; server-side scoping is authoritative. Display-only additions of fields already present in the rendered API response model introduce no new cross-tenant exposure.
