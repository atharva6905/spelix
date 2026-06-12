---
name: review-upload-ownership-guard
description: issue #231 — per-resource ownership guard on expert complete_paper_upload; inline-guard convention, predicate-triplication MEDIUM, sentinel-default factory refactor
metadata:
  type: project
---

# issue #231 / upload ownership guard on POST /expert/papers/{id}/complete (T2) — 2026-06-11 → PASS (1 MEDIUM non-blocking)

Bug: complete_paper_upload had no ownership check; any expert could complete/destroy
another expert's 'uploading' row (INVALID_PDF + DUPLICATE_DOI-race paths delete storage
object + DB row). Fix: +20-line inline guard in expert.py after get_by_id/404, before
state-check + cleanup paths. Rejects 403 NOT_PAPER_OWNER when
`(doc.extra_metadata or {}).get("uploaded_by") != str(user["id"])` unless role=="admin".

**Why PASS:** guard ordering honors the ADR-TXN-01 / [[review-profile-optional-field]]
rule from #223 — runs BEFORE any destructive op (verified line-level: 403 at 377-389,
INVALID_PDF delete at 427-428). Tests assert the destructive non-owner case explicitly
(`delete_object/repo.delete/download_head_bytes .assert_not_awaited()` with non-PDF bytes
staged) — the strongest possible negative assertion. No MagicMock+Pydantic-500 trap:
route returns RagDocumentCompleteResponse built from a REAL `pending` RagDocument, tests
use real ORM objects via `_make_uploading_doc`.

**Per-resource authz convention in expert.py = INLINE guard, not deps-level dependency.**
Existing precedent: ownership is set-at-write (`extra_metadata={"uploaded_by": str(user["id"])}`
in request_paper_upload ~L313) and filter-in-query (list_my_papers ~L785:
`RagDocument.extra_metadata["uploaded_by"].as_string() == str(user["id"])`). There is NO
deps.py per-paper dependency. So an inline guard is architecturally consistent — do NOT
flag "should be a dependency".

**MEDIUM (non-blocking) — ownership predicate now triplicated.** Same
`extra_metadata.uploaded_by == str(user["id"])` logic exists in 3 forms: write (L313),
query-filter (L785), now route-guard (L378). The issue itself foreshadows future
cancel/delete endpoints. Recommended (deferred, fine to defer): extract a
`_is_paper_owner(doc, user) -> bool` helper (and/or `_assert_paper_owner` raising the 403)
so the next destructive expert endpoint reuses it instead of a 4th copy. Not blocking —
single new call site, predicate is trivial.

**Fixture-factory refactor IMPROVES the suite (non-weakening).** `expert_app` fixture now
delegates to `_build_app(user_id, role)`; old fixture = `_build_app(TEST_EXPERT_ID,
"expert_reviewer")` → byte-identical app. `_make_uploading_doc` gained a `_SENTINEL`
default for `uploaded_by` that defaults to TEST_EXPERT_ID — so the existing `client`
(TEST_EXPERT_ID) stays the owner and all 6 pre-existing tests pass UNCHANGED. Distinct
None (extra_metadata=None) vs missing-key ({}) legacy cases both covered + parametrized,
both fail-closed 403. Admin test correctly uses OTHER_EXPERT_ID owner so it proves the
override, not a trivial match.

**Fail-closed legacy policy is deliberate + documented**: 'uploading' rows are transient
orphans that never lock a DOI (partial unique index is WHERE doi IS NOT NULL), so denying
non-admins on missing uploaded_by loses nothing; admins can still clean up. Sound.

Pre-existing (NOT this diff, do not re-flag here): list_my_papers does raw
`select(RagDocument)` + `db.execute` directly in the route — a Repository-bypass layer
violation. Out of scope for #231; worth a separate cleanup issue if ever touched.
