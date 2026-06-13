---
name: pattern-vimock-guard-redeclare
description: When a page test vi.mock()s an api module, re-declaring an exported guard inline is acceptable if it duck-types the real contract; the transport-level test remains the authoritative pin
metadata:
  type: feedback
---

When reviewing frontend tests where a page test does `vi.mock("@/api/expert", ...)`,
the whole module is replaced, so the test must re-declare exported helpers (guards,
consts) it needs. Re-declaring `isExpertApiError` inline in the mock is NOT a finding
PROVIDED it duck-types on the same contract as the real guard (here: name ===
"ExpertApiError" && typeof status === "number").

**Why:** The real guard/class is pinned authoritatively by the transport-level test
(expert-upload.test.ts) which drives real expertFetch and asserts instanceof + guard true.
The page test only needs behavioral parity, not the real implementation.

**How to apply:** Don't flag a re-declared mock guard as drift IF (a) a separate transport
test pins the real thing, and (b) the mock's predicate matches the real one's contract.
DO flag it if the only test of the guard is a hand-mocked object literal with no real-shape pin.
