# Groom Digest

## 2026-06-13 cycle 3 — quiet/healthy steady state; ship-loop PRs all merged

Mode: REPORT-ONLY, /loop cycle 3. `reclaim-stale` still stood down (#293).
- **PRs:** 0 open — #290 (#269), #291 (#258), #292 (#283) all **merged**; origin/main → `dbbb99c`. CI all green (no flaky).
- **Claims:** board `[]` (no live claims); `gc-labels` removed orphan `claim:sl-3a30` def. Empty + clean.
- **No-harm note:** despite cycle-1/2 reclaim-stale stripping the #258/#269/#283 claims, all three still merged cleanly — the #293 bug was a latent risk that wasn't exploited this run. Fix still warranted.
- **Worktrees:** the 3 just-merged branches (`feat+issue-258-restamp-retry`, `fix+issue-269-docling-checksum-verify`, `refactor+issue-283-shared-apierror`) are now also prunable (~15 merged total). Full rescan deferred — cycle-1 list + these 3 stands.
- Sweeps 1/3/4 nominal (no new unlabeled issues beyond my #293; deps cadence-skip; flaky none).

## 2026-06-13 cycle 2 — claims bug CONFIRMED + issue #293 filed; reclaim-stale stood down

Mode: REPORT-ONLY, /loop cycle 2 (~25min after cycle 1). 3 parallel ship-loops now at PR stage.

- **Sweep 2 (PRs):** 3 new open PRs, **all T2**, all from the parallel ship-loops — **#290** docling weight checksums (#269, sl-3a30), **#291** restamp reliability (#258, sl-aa0c), **#292** shared ApiError (#283, sl-ff44). All fresh (<30min), all T2 → groom never touches T2 / never merges T1+ → **report-only, no action.** The ship-loop sessions own these.
- **Sweep 6 (claims) — BUG CONFIRMED:** this cycle reclaim-stale stripped `claim:sl-3a30` from #269 **while sl-3a30 was alive and had just opened PR #290** (same pattern as cycle 1's #258/#283 → PRs #291/#292). Read `.claude/lib/claims.mjs`: claims store `worktree: CLAIMS_WORKTREE||null` (ship-loop claims in step-0 *before* the worktree exists → null); `heartbeat()` never backfills it; so `reclaimStale()`'s `worktreeGone` is **always true** and the guard degrades to heartbeat-staleness only. `readyQueue()` doesn't exclude open-PR issues, so a premature reclaim → duplicate-implementation risk. **Filed as issue #293** (bug/tech-debt/infra/size/S, deliberately NO tier label so a ship-loop won't auto-grab a claim-engine change).
- **DECISION:** for the remainder of this groom session, **STOP running `reclaim-stale`** (it is actively stripping live claims). Continue `board` (read) + `gc-labels` (harmless) only. `.claims.json` is now `{}`.
- Sweeps 1/3/4/5 unchanged from cycle 1 (no new issues; deps cadence-skip; flaky none; worktrees same 12 prunable).

## 2026-06-13 — REPORT-ONLY run alongside active ship-loops (no --merge, sweeps 1–6, /loop dynamic)

Mode: REPORT-ONLY. Zero merges, zero PRs, zero Tier 2 paths touched. Run **simultaneously with ~17 active parallel ship-loop sessions** (per user) — non-interference prioritized: no commits/pushes to main, digest written locally only.

### Sweep 1 — Issue triage
- **Actions taken:** none.
- **Findings:** 21 open issues, **all already labeled** (type + `size/*`; tier where a diff exists). No new/unlabeled issues, no missing-type labels. Older issues #180–#226 lack `T*` tier labels by design — tier is computed from the actual diff at PR time, so triage does not fabricate them. `needs-design`/`designed`/`blocked` already applied where appropriate (#259, #226, #270–#273). **Clean no-op.**

### Sweep 2 — Stale-PR babysitting
- **Actions taken:** none.
- **Findings:** **0 open PRs** (list_pull_requests state=open → empty). Clean no-op.

### Sweep 3 — Dep bumps (weekly cadence)
- **Actions taken:** none. **SKIPPED on cadence:** `87a593f chore(config): bump ruff 0.15.9 → 0.15.16` merged within the trailing 6-day window → cadence not due, candidate enumeration deferred to next eligible run.

### Sweep 4 — Flaky-test detection
- **Actions taken:** none.
- **Findings:** last 30 CI runs all `success`. No same-SHA fail→pass. **No flaky pattern → no issue filed.**

### Sweep 5 — Hygiene
- **handoff.md:** stamp is today (2026-06-13) → fresh, no refresh.
- **backlog.md / decisions.md:** NOT audited/edited this run — ship-loop release path owns its own backlog rows at merge, and 17 sessions are actively merging; editing now would race. Deferred to a quiet run. (Open question 2.)
- **Stale worktrees (REPORT only — never auto-removed):** **12 merged branches still have worktrees**, prunable manually (none locked):
  `worktree-agent-a22a7e9c531c25af6`, `fix/issue-204-account-storage-purge`, `fix/issue-203-brain16-cascade-predicate`, `feat/issue-220-doi-columns`, `worktree-agent-a4dc10706163c08a4`, `worktree-agent-ad64e71e910a52b60`, `feat/issue-219-doi-required-form`, `fix/issue-205-pdf-confidence-label`, `feat/issue-218-doi-dedup`, `feat/issue-225-sex-retrieval`, `fix/issue-263-docling-ocr-models`, `feat/landing-page`.
  17 worktrees still active (5 locked). `feat/landing-page` is the external spelix-landing dir — verify before pruning.

### Sweep 6 — Claims (self-healing hygiene; NEVER claims)
- **Board snapshot:** #258 (sl-aa0c, 50min, stale), #269 (sl-3a30, 11min, **live**), #283 (sl-ff44, 41min, stale).
- **reclaim-stale:** reclaimed **#258** and **#283** (heartbeat >30min) → returned to ready pool.
- **gc-labels:** nothing to delete (no orphan `claim:*` label definitions).
- ⚠️ **Possible bug:** board reported `worktreePresent:false` for **all three** claims, including the live #269 — yet the OS `git worktree list` shows worktrees present for all three (`feat+issue-258-restamp-retry`, `fix+issue-269-docling-checksum-verify`, `refactor+issue-283-shared-apierror`). If `worktreePresent` always returns false, the reclaim-stale "AND worktree gone" guard is effectively a no-op and reclaim runs on heartbeat staleness alone — more aggressive than the protocol intends. **Open question 1.**

### Open questions for the human
1. **claims.mjs `worktreePresent` detection** appears to universally return false (path-matching mismatch between stored `.claims.json` worktree path and actual worktree path on Windows?). Verify and fix, or the "worktree gone" reclaim guard is bypassed.
2. **backlog/decisions hygiene** deferred to avoid racing the 17 active ship-loop sessions. Run a quiet groom (or let each ship-loop's release handle its own rows) to confirm the recently-merged issues (#203/#204/#205/#218/#219/#220/#225/#263) have archive rows.
3. **12 merged worktrees** ready for manual prune (`git worktree remove <path>`).
4. **Digest not committed** this run (non-interference with parallel main pushes). Fold into the next clean commit point.

## 2026-06-09 — REPORT-ONLY validation run (no --merge, all 5 sweeps)

Mode: REPORT-ONLY. Zero merges, zero PRs created, zero Tier 2 paths touched. Not run under /loop (no ScheduleWakeup).

### Sweep 1 — Issue triage
- **Actions taken:** none.
- **Findings:** 8 open issues (#180, #181, #182, #183, #184, #186, #187, #191). All were migrated from backlog.md on 2026-05-30 and are **already labeled** (cv / tech-debt / infra / eval / parked / frontend as appropriate) and several already carry SRS IDs in their bodies (FR-SCOR-*, FR-CVPL-14, FR-AICP-08, NFR-OPER-02). No new/unlabeled issues. No likely duplicates. **Nothing to do — sweep is a clean no-op.**
- **Skipped:** size labels (S/M/L) not added — sizes are already stated inline in each issue body (e.g. "Size: M"), and the repo has no `size/*` label scheme to apply against. Recorded as a proposal rather than acted on (see open questions).

### Sweep 2 — Stale-PR babysitting
- **Actions taken:** none.
- **Findings:** **0 open PRs** (mcp__github__list_pull_requests state=open → empty). No red CI to diagnose, no conflicts to rebase, no idle PRs to nudge. Clean no-op.

### Sweep 3 — Dep bumps (weekly cadence)
- **Actions taken:** none (REPORT-ONLY + cadence + no-PR constraint).
- **Cadence check:** No `chore(deps)`/bump/upgrade commit in the dependency-manifest sense landed on main in the trailing window. The most recent dependency-adjacent change was a **docs-only** third-party dependency *inventory* (`70aedae`, 2026-05-30) — not a lockfile bump. So the strict "skip if a dep-bump PR merged in the last 6 days" rule does **not** auto-skip on a real bump.
- **Decision:** Did **not** run `uv lock --upgrade --dry-run` / `npm outdated` to enumerate candidates this run, because the validation constraints explicitly forbid creating any dep-bump PR and note a recent dep-bump merged "recently enough that the weekly cadence likely says skip." Candidate enumeration without PR creation is deferred to a real (non-validation) groom run. **No candidates listed.** (See open questions — this is the one place the run intentionally diverged from the literal sweep text per the binding validation constraints.)

### Sweep 4 — Flaky-test detection
- **Actions taken:** none.
- **Findings:** Pulled last 30 CI runs (`gh run list --json conclusion,name,headSha,status,createdAt`). 29/30 `success`, 1 `failure` at SHA `3ea7ad0` (2026-06-06 21:21Z). That SHA has **no passing run on the same SHA** — it was followed by a *new* commit `98b400f`, i.e. a genuine red-then-fixed-forward, not a same-SHA fail→pass. **No flaky pattern detected → no issue filed.**

### Sweep 5 — Hygiene
- **handoff.md:** stamped `2026-06-09T18:55:10Z` (today) — **not stale (<7d). No refresh.**
- **backlog.md:** archive rows for #198/#190/#185 already present (commit `b32912c`); the "Open work → Issues" table accurately mirrors all 8 open issues. **No gap, no duplicate rows added.**
- **decisions.md:** Decision Index rows = 134, ADR body headers = 134 — **balanced, no missing index rows.**
- **Stale worktrees:** reported below for **manual** pruning. **None auto-removed.**
- **Direct commits:** none — no genuine docs/T0 hygiene gap found.

### Stale worktrees flagged (branch merged into origin/main — safe for MANUAL prune; NOT removed)
Worktree path → branch:
- `.claude/worktrees/agent-a3b90ac01802d294a` → `worktree-agent-a3b90ac01802d294a` (locked)
- `.claude/worktrees/agent-acebf29654e1f0ad8` → `worktree-agent-acebf29654e1f0ad8` (locked)
- `.claude/worktrees/agent-add1d3ec5afe5999b` → `worktree-agent-add1d3ec5afe5999b` (locked)
- `.claude/worktrees/agent-adda6b22d144db40f` → `worktree-agent-adda6b22d144db40f` (locked)
- `.claude/worktrees/agent-ae54bc55046bde772` → `worktree-agent-ae54bc55046bde772` (locked)
- `.claude/worktrees/agent-ae67bf5827b21baf2` → `worktree-agent-ae67bf5827b21baf2` (locked)
- `.claude/worktrees/fix+d035-early-writes-and-diagnostic` → `fix/d035-early-writes-and-diagnostic`
- `.claude/worktrees/issue-185-test-consolidation` → `test/issue-185-distillation-validate-consolidation`
- `.claude/worktrees/issue-190-sidebar-adaptive-polish` → `feat/issue-190-sidebar-adaptive-polish`
- `../spelix-d037-d038-review-card-completeness` → `feat/d037-d038-review-card-completeness`
- `../spelix-d042-d043` → `fix/d042-d043-rep-detection-thresholdconfig`
- `../spelix-landing` → `feat/landing-page`
- `../spelix-p3-006-review-queue` → `feat/p3-006-review-queue`
- `../spelix-phase3-batch1` → `feat/phase3-batch1-langgraph-agent`

(14 worktrees on branches fully merged into `origin/main`. Six locked agent worktrees require `git worktree unlock` before `git worktree remove`. The remaining ~15 agent worktrees are on **unmerged** branches and are NOT flagged.)

### Merges this run
None.

### Open questions for the human
1. **Issue sizing labels:** Sweep 1 says "add labels (… size S/M/L)" but the repo uses inline `Size:` body text, not `size/*` labels. Create a `size/S|M|L` label scheme and backfill, or leave sizes inline? (No action taken.)
2. **Dep-bump cadence ambiguity:** the last "dependency" change on main was a docs-only inventory (`70aedae`), not a real lockfile bump. Under the literal rule the sweep would NOT skip. For this validation run I deferred candidate enumeration per the no-PR constraint — confirm that's the intended behavior, or whether enumerate-only (dry-run list, no PR) should always run.
3. **Stale-worktree prune:** 14 merged worktrees (6 locked) are ready to prune manually. Confirm before any `git worktree remove`.

## 2026-06-09 — `/groom --merge` validation run 2 (WITH --merge, all 5 sweeps)

Mode: **--merge** (T0 self-merge enabled, cap 2 of skill's 3). Not under /loop — no ScheduleWakeup. Always finished back on a clean `main`. Zero Tier 2 paths modified.

### Sweep 1 — Issue triage
- **Actions taken:** none. **Clean no-op.**
- **Findings:** 13 open issues (#180–#187, #191, #203–#207). Every one carries BOTH a category label (cv/bug/tech-debt/eval/infra/frontend/parked) AND a `size/*` label (XS–XL) — the 12-issue backfill landed today as expected, and the 5 newer bug issues (#203–#207) are also fully labeled. No unlabeled issues, no SRS-ID gaps to link, no duplicate candidates.

### Sweep 2 — Stale-PR babysitting
- **Actions taken:** none. **Clean no-op.**
- **Findings:** `mcp__github__list_pull_requests state=open` → `[]`. No open PRs at sweep start.

### Sweep 3 — Dep bumps (PRIMARY T0 candidate) → **1 self-merge**
- **Cadence:** no dep-bump commit (pyproject/uv.lock or package.json/lock) on main in the trailing 6 days → cadence permits a bump.
- **Enumeration (always runs):**
  - Backend `uv lock --upgrade --dry-run`: ~90 candidates. PATCH examples: `ruff 0.15.9→0.15.16`, `pyright 1.1.408→1.1.410`, `numpy 2.4.4→2.4.6`, `matplotlib 3.10.8→3.10.9`, `orjson 3.11.8→3.11.9`, `lxml 6.1.0→6.1.1`, `rich 14.3.3→14.3.4`, `fastapi 0.135.3→0.135.4`, `sqlalchemy 2.0.49→2.0.50` (forbidden — skipped), `soupsieve`, `marko`, `filelock`, `zopfli`. MINOR (digest-only this run, no T1 PR): `coverage 7.13→7.14`, `faker 40.15→40.21`, `pytest-asyncio 1.3→1.4`, `anthropic 0.91→0.109`, `openai 2.30→2.41`, `huggingface-hub 1.10→1.18`, `qdrant-client 1.17→1.18`, `streaq 6.4.0→6.5.2`, `supabase 2.28→2.31`, `uvicorn 0.44→0.49`, `cryptography 46→48`, `starlette 1.0.0→1.2.1`, `weasyprint 68.1→69.0`. MAJOR (digest/issue-only): `torch 2.11→2.12`, `torchvision 0.26→0.27`, `rpds-py 0.30→2026.5.1`, `docling-parse 5→6`.
  - Frontend `npm outdated`: node_modules not installed locally (all rows show Current=MISSING), so no reliable local PATCH target; only `react-markdown 9→10` shows a real MAJOR gap (digest-only). No frontend PR this run.
- **Picked (safest single PATCH):** `ruff 0.15.9 → 0.15.16` — dev-only linter, pure PATCH within 0.15.x, zero runtime impact. Avoided all forbidden deps (mediapipe/opencv/sqlalchemy/langgraph-adjacent).
- **Local check:** `uv run ruff check .` → "All checks passed!" on 0.15.16.
- **PR #210** (`chore/deps-bump-ruff-0-15-16`), branch SHA `87a593f`.
- **Diff:** `backend/pyproject.toml` pin + `backend/uv.lock`. Only `version =` change in the whole diff is ruff; remaining uv.lock hunks are version-less platform-marker normalization on transitive CUDA/nvidia packages (re-resolution churn, no version change).
- **T0 GATE EVIDENCE (all four conditions):**
  1. **CI fully green** — Backend Tests pass, Backend/Frontend Lint pass, Frontend Tests pass, Secret Scanning pass, Vercel pass (combined status `success`). "Deploy to Production" shows `skipping` pre-merge (runs only post-merge on main).
  2. **Fresh-context reviewer PASS** — spawned a fresh headless `claude -p` (clean cwd, tools disabled) fed ONLY governance.md + the PR diff, no session context. Verdict: `VERDICT: PASS (Tier 0) — single dev-dependency ruff PATCH bump confined to pyproject.toml pin + uv.lock (remaining lock hunks are version-less platform-marker normalization), touching zero Tier 2 paths and introducing no user-facing injury language.`
  3. **Diff re-validated T0 at merge time** — re-pulled combined status `success`; confirmed only ruff version changed, no Tier 2 path.
  4. **Merge via `merge_method: "merge"`** — merged through `mcp__github__merge_pull_request`, NOT squash.
- **MERGE SHA: `016a102`** (Merge pull request #210).
- **Post-merge deploy verification (required after deploy-triggering merge):** post-merge CI run `27233441767` reported **`failure`** — BUT the failure is a post-start `uv sync` step (dev deps pyright/ruff/nodeenv into `/app/.venv`) hitting `Permission denied (os error 13)` + SSH "Run Command Timeout", AFTER the runtime containers had already rebuilt + recreated + started. Direct droplet check (governance-sanctioned SSH-to-diagnose, NOT manual deploy): `ssh spelix-droplet` → HEAD `016a102` (matches merge), `spelix-backend-1 Up (healthy)`, `spelix-worker-1 Up (healthy)`, `spelix-redis-1 (healthy)`; `curl -sL https://spelix.app/api/v1/health` → **200**. Deploy genuinely succeeded; CI red is a false-negative. Filed **issue #211** (infra/tech-debt/size-S) documenting the deploy-step flaw + fix options (`uv sync --no-dev` / fix `.venv` perms / drop post-start sync). Did NOT SSH-deploy manually.

### Sweep 4 — Flaky-test detection
- **Actions taken:** none. **No flaky pattern.**
- **Findings:** grouped last 30 CI runs by headSha (per workflow). No SHA has a same-workflow fail-then-pass (re-run) pattern. The single `failure` at SHA `3ea7ad0` has one run and was followed by a distinct fix-forward commit `98b400f` (success) — not a same-SHA re-run flake. No issue filed.

### Sweep 5 — Hygiene (SECOND T0 candidate) → **1 self-merge (this PR)**
- **handoff.md:** stamped today (<7d) — not stale, no refresh.
- **decisions.md:** Decision Index rows = ADR body headers (balanced last run; no new ADRs added this run) — no index fix.
- **backlog.md gap FIXED:** added `## Completed — Harness v2 "Gated Autopilot" (2026-06-06 → 2026-06-09)` ABOVE the `/ship-loop run 1` section (newest-first), recording Batch 1 #195 `cbbf0f3`, Batch 2 #196 `964b3a4`, Batch 3 #197 `250b90e` (+supervised run PRs #199/#200/#201), Batch 4 #208 `dafd350`, follow-up #209 `e1f220d`; spec/plan noted local-only in `docs/internal/`. Added a matching Contents bullet (newest-first).
- **This digest update** bundled into the same docs/T0 PR (`chore/groom-hygiene-harness-v2-backlog`), written BEFORE committing the PR.
- **Stale worktrees:** unchanged from run 1 — 14 merged worktrees (6 locked) flagged for MANUAL prune; none auto-removed.

### Merges this run (2 of cap-2)
1. **PR #210** `chore(config): bump ruff 0.15.9 -> 0.15.16` — T0 dep-bump, merge SHA `016a102`. Gate evidence above.
2. **PR (hygiene)** `chore: backlog Harness v2 archive + groom digest run 2` — T0 docs (`backlog.md` + `.claude/groom-digest.md`), merge SHA recorded post-merge. Gate evidence: CI green + fresh-context reviewer PASS + diff re-validated T0 (docs-only, no Tier 2) + merge_method=merge.

### Candidates deferred
- All MINOR/MAJOR backend bumps (listed in Sweep 3) — not actioned this run per constraints (MINOR=digest-only, MAJOR=digest-only).
- Frontend bumps — deferred (no local node_modules to validate; `react-markdown` 9→10 is a MAJOR for a future T1/issue).
- Forbidden-list deps (sqlalchemy 2.0.50, plus any mediapipe/opencv/langgraph-adjacent) — never touched.

### Open questions for the human
1. **Deploy CI false-negative (issue #211):** post-merge "Deploy to Production" is red despite a healthy deploy because of a post-start dev-dep `uv sync` perms failure. Pick a fix (recommend `uv sync --no-dev` on the droplet). Until fixed, post-merge CI will go red on any lockfile-changing merge even though prod is fine.
2. **Frontend dep bumps:** local `npm outdated` is uninformative without `npm ci` first. Should groom run a frontend install in CI/locally before enumerating, or skip frontend enumeration in groom and leave it to Dependabot?
3. **Stale-worktree prune:** still 14 merged worktrees (6 locked) ready for manual prune — unchanged from run 1.
