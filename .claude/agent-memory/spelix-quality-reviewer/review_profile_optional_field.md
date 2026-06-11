---
name: review-profile-optional-field
description: Quality-review pattern for adding an optional field to UserProfile (ProfileService.upsert + ProfilePage select) — reusable across the sex_applicability series and any future optional profile attribute
metadata:
  type: project
---

# Adding an optional field to UserProfile — quality-review checklist

**Why:** Issue #224 (profile `sex`) added an optional enum field across the full stack. The pattern recurs for any optional profile attribute and across the sex_applicability series (#221–#225).

**How to apply** — when reviewing a diff that adds an optional column to UserProfile:

- **ProfileService.upsert is overwrite-all on BOTH paths.** Mirrors `arm_span_cm`/`femur_length_cm`: create-path passes the field as a constructor kwarg, update-path assigns `existing.field = data.field` unconditionally. Omitted-in-payload ⇒ schema default (None) ⇒ overwrites existing DB value. Intentional, not a bug — but every new optional field MUST follow it on both branches or partial-update data loss results. Verify both lines exist.
- **MagicMock+Pydantic trap (recurring):** the factory `_make_orm_profile` in `backend/tests/unit/test_profile_api.py` MUST set the new field as a real constructor kwarg (`field=kwargs.get("field", None)`), because `ProfileResponse` reads it via `from_attributes`. A bare MagicMock attribute serializes as a Mock and passes vacuously. Service-level tests should use `repo.create/update.side_effect = lambda p: p` to return the real ORM object, never a mock.
- **Frontend hydration:** loaded-null must fall to the form default via a type-guard predicate, not a cast. `isSex(profile.field) ? profile.field : "<default>"` is correct narrowing. `handleChange` uses `{ ...prev, [field]: value }` spread, so an unrelated edit+save round-trip preserves a previously-loaded value — confirm a test covers it.
- **Always-send semantics:** the select always sends `form.field` (no special-casing default vs DB-null). For the sex series this is acceptable because #225 normalizes default-sentinel and NULL to None downstream. Confirm the page itself does not branch on the two.
- **Response schema is permissive (`string | null`), request schema is strict (union).** Hand-adding `field: string | null` to ProfileResponse rather than the strict union matches the `experience_level` convention — not a Supabase-types-regen violation.

Reviewed #224 (commits b8943b5, fe38865) on 2026-06-10 → PASS, zero findings. Only low-value gap: no explicit "update path preserves other fields while changing the new one" test, but covered transitively by existing TestPutProfile multi-field echo.
