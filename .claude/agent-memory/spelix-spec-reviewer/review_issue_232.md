---
name: review_issue_232
description: Spec review of issue #232 — DoiLink component extraction (triplication fix) + testid-based em-dash tests: PASS, 2026-06-11
metadata:
  type: project
---

## Reviewed: issue #232 (DoiLink extraction, 2026-06-11) → PASS

Branch: refactor/issue-232-doilink. Commits: 01d3674 + 6f248a0.

**Requirements verified:**
1. DoiLink.tsx created with: anchor when doi truthy, standardized gray span fallback → DONE (DoiLink.tsx:24-29 / 32-43)
2. Fallback has data-testid="doi-empty" → DONE (DoiLink.tsx:26)
3. Fallback className="text-gray-400" → DONE (DoiLink.tsx:26)
4. props: doi, className (extra), children, aria-label → DONE; children+aria-label are JUSTIFIED (CitationTooltip needs both to replicate prior "DOI: {doi}" text + "DOI link" aria-label behavior — not YAGNI)
5. All 3 sites replaced — CitationTooltip.tsx, AdminPage.tsx, ExpertPortalPage.tsx → DONE; no hand-rolled doi.org anchor JSX remains in src/
6. anchor keeps target="_blank" + rel="noopener noreferrer" + https://doi.org/${doi} → DONE (DoiLink.tsx:34-36)
7. CitationTooltip null case renders NOTHING (guard {citation.doi && <DoiLink>} kept) → DONE (CitationTooltip.tsx:34); DoiLink's own fallback never fires here
8. hover:underline preserved for CitationTooltip — original had it in className; new usage passes "mt-1 inline-block text-blue-600" and DoiLink prepends "hover:underline" → visually equivalent
9. ExpertPortalPage.test.tsx em-dash test updated to getByTestId("doi-empty") → DONE
10. AdminPagePanels.test.tsx em-dash test updated to getByTestId("doi-empty") → DONE
11. DoiLink.test.tsx added with 6 unit tests covering anchor attrs, children label, className merge, aria-label, null fallback, undefined fallback → DONE
12. CitationTooltip test: null-doi case still verifies no DOI link rendered → DONE (line 121-124); visually equivalent check passes
13. TDD gate files all covered by test changes

**No OVER-BUILT scope detected** — only the 3 call-site files + new component + test files touched.

**Patterns noted:**
- CitationTooltip uses the outer `{citation.doi && ...}` guard so DoiLink's own fallback span never renders in CitationTooltip context — correct behavior, null case still renders nothing for the tooltip.
- "hover:underline" is a base class in DoiLink prepended to the passed className, so all 3 call sites get it without explicitly passing it.
- children prop justified: CitationTooltip renders "DOI: {citation.doi}" as children, not the raw DOI value.
