# spelix-security-reviewer — memory

(Persisted by the main agent on 2026-06-10 — the reviewer ran read-only and asked for these to be recorded.)

- [Hooks guardrail integrity](hooks_guardrail_integrity.md) — which hooks BLOCK vs warn, the worktree-skip invariant, and the post-edit-lint JSON.stringify shell-quoting caveat (#237 → PASS)
- [Issue #239 T1/T2 approval gate](harness_governance_t1_t2_approval_gate.md) — control-weakening analysis: recorded-approval precondition in both files, all non-approve paths fail-safe → PASS

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

## Reviewed: issue #221 (sex-aware coaching CONTRACT task, T2 models/schemas/alembic+SRS, 2026-06-10) → PASS
- Scope: migration `9fffb59ba45f` (down_rev cf685bd7e8f8) adds `rag_documents.sex_applicability` VARCHAR(30) NOT NULL DEFAULT 'both' + CHECK IN ('male','female','both'); `user_profiles.sex` VARCHAR(30) NULLABLE + CHECK IN ('male','female','prefer_not_to_say'). Plus Pydantic `SexLiteral`/`SexApplicabilityLiteral`, schema fields on profile/rag_document, `ChunkPayload.exercise`+`.sex_applicability`, SRS amendments FR-RAGK-05/EXPV-05/PROF-03/AICP-05/AICP-09/AICP-12. No endpoints/RLS/logging changed in this diff.
- SaMD/FTC: CLEAN. All new wording = "sex applicability"/"lifter sex"/"coaching evidence"/"Movement Quality". No injury/diagnose/treat/prevent/clinical in any new Field desc or SRS amendment. Profile `sex` desc = "Sex (optional) — used to match coaching evidence". (Pre-existing FR-AICP-03 "risk level"/FR-AICP-04 "dangerous patterns" are NOT in this diff and are internal-spec, not user-facing.)
- Migration safety: CLEAN. No DDL FK to auth.users. CHECK can't lock out rows: rag_documents backfilled by server_default='both'; user_profiles.sex nullable so existing NULL rows pass IN-list CHECK (Postgres CHECK passes on NULL). No destructive ops. CHECK SQL = static literals, no injection. Model CheckConstraint names match DDL.
- Sensitive PII (`user_profiles.sex`): posture preserved — optional+nullable+'prefer_not_to_say' opt-out, no new log/serialize sink, RLS untouched (rides existing user_profiles auth.uid()=user_id, migration 002); ProfileResponse owner-only.
- DOWNSTREAM WATCH for the IMPL issue (not blocking contract): (1) analysis_worker.py body-stats COACHING_FIELDS/getattr loop — ensure `sex` not leaked into agent_trace_json/LangSmith/admin-or-expert-visible columns; (2) new endpoints surfacing sex_applicability joined to user `sex` must not cross-tenant-leak; (3) ChunkPayload.sex_applicability → Qdrant payload is corpus metadata, not user PII — fine.

## Reviewed: issue #223 (sex_applicability expert metadata edit, 2026-06-10) → PASS
- New `PATCH /expert/papers/{doc_id}/metadata` (`expert.py` ~L525) — gated by `get_expert_reviewer_user`, same as review/complete. Experts may edit ANY paper's metadata (no uploaded_by ownership check) — consistent with existing review_paper power; same accepted-risk class as #218/#231, OK at single-partner scale. RE-FLAG if expert role opens to multiple untrusted partners.
- `doc_id: UUID` typed path param (422 on malformed). 404 returns generic "Document not found." — no existence/contents leak.
- Injection-safe: `str(doc_id)` (validated UUID) → Qdrant structured `Filter`/`MatchValue`, no string interp; DB write via SQLAlchemy ORM (parameterized). No f-string SQL.
- Best-effort Qdrant restamp wrapped in `except Exception`, DB commit precedes it (Qdrant failure never rolls back the edit). Logs only doc_id UUID — no str(exc), no secrets (ADR-DISTILL-05 analog clean).
- SaMD-clean: all new strings wellness/neutral — "Applicable population" label/column/aria-labels, Male/Female/Both options (`expert.ts` SEX_APPLICABILITY_OPTIONS), static error banner "Failed to update applicable population." No injury/diagnose/treat/prevent.
- `sex_applicability` validated by `SexApplicabilityLiteral` on every API write path (upload + this PATCH) — corpus metadata, not user PII.

## Reviewed: issue #224 (profile sex field wiring, 2026-06-10) → PASS
- Resolves the #221 PII downstream watch item for the `/profiles/me` path: this diff wires optional `sex` into the OWNER-SCOPED `ProfileService.upsert` (create+update) and owner-scoped `ProfileResponse` only. Route auth unchanged (`get_current_user` → `user["id"]`, profiles.py L29/L43); no new endpoint, no widened response, no admin/expert/RLS/migration file in diff. No new logging/analytics sink — frontend logs only `err`, never `form.sex` (ProfilePage.tsx L77/L129).
- SaMD-clean: label "Sex (optional)", options Prefer not to say/Male/Female, helper "Used to match coaching evidence to you." — no injury/diagnose/treat/prevent.
- No dark pattern: genuine opt-out, default = `prefer_not_to_say`, save never blocks on sex.
- Always-send-default persists `'prefer_not_to_say'` string for untouched users — allowed by #221 CHECK `ck_user_profiles_sex` (sex IN male/female/prefer_not_to_say); column also nullable. `ProfileUpdate.sex` is a closed Literal → out-of-enum rejected at Pydantic boundary (422), server-side authoritative.
- STILL OPEN (belongs to #221, NOT this PR): pre-existing admin read path `UserProfileRepository.list_with_analysis_count` (services/admin.py) selects full UserProfile ORM — re-check whether `sex` is serialized to admins under #221's schema review, not here. Not regressed by #224.
