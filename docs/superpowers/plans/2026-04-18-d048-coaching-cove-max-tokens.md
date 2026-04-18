# D-048 — Coaching-path CoVe max_tokens bump Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the M-05-style `max_tokens` bump to the coaching-path `app/services/cove.py::CoveVerificationService` so `eval_scores.cove_verified` stops being spuriously `false` and `faithfulness` stops being `0.0` on completed analyses. Session 46 + session 47 prod E2E both reproduced truncation at `max_tokens` 1024 → 2048 → 3072; session 47 confirmed the failure survives the D-045 retrieval fix (analysis `de316a7a`), proving it is independent of retrieval routing.

**Architecture:** One surgical diff in `CoveVerificationService._run_cove_loop`: bump every `max_tokens=` argument to leave comfortable headroom above the observed truncation ceiling (3072 output tokens). The service aggregates N claims into a single `VerificationAnswers` response (one answer + one-sentence reasoning per claim), so the Step 3 answer call is the documented blow-out path. TDD gate: one failing-then-passing unit test asserts the exact `max_tokens` kwargs passed to `instructor.chat.completions.create` on all 5 call sites. Same TDD shape as the session-46 M-05 gate on `cove_brain.py`. No prompt-text, model, or response-model changes.

**Tech Stack:** Python 3.12, pytest-asyncio, `instructor` + Anthropic Haiku 4.5 (`claude-haiku-4-5-20251001`) + Anthropic Sonnet 4.6 (`claude-sonnet-4-6`), Playwright MCP for prod E2E, Supabase SQL MCP for DB inspection.

**File structure:**
- **Modify** `backend/app/services/cove.py` — five `max_tokens=` literals bumped. No other behavioral change.
- **Modify** `backend/tests/unit/test_cove.py` — append one test asserting all five calls pass sufficient `max_tokens` via call-kwargs introspection. Update any existing assertion that hardcoded an old value (none expected; `max_tokens` is not currently asserted in the test file — verified via `grep -n max_tokens backend/tests/unit/test_cove.py` returning 0 matches).
- **Modify** `backlog.md` — close D-048 with merge SHA, append a `## Completed —` section row.
- **Modify** `decisions.md` — append `ADR-COVE-01: CoveVerificationService max_tokens budget` (new ADR family; the coaching-path CoVe has no prior ADR and session-46 ADR-DISTILL-06 is scoped to the distillation path).
- **Modify** `.claude/handoff.md` — add a completion row, update Priority 2, append an "E2E Findings — D-048 verification" section with before/after `cove_verified` + `faithfulness` values from the analysis UUID used for verification.

**Abort / rollback:**
- If bumping `max_tokens` surfaces new test failures in `test_cove.py` (e.g., any existing test hardcoded the old values — unlikely per the grep, but double-check on Task 1 Step 2 local run): fix the assertions, do not relax the new gate.
- If prod E2E still shows `cove_verified=false, faithfulness=0.0` after the bump lands: the blow-out cap was wrong — root-cause by reading worker logs for `CoveVerificationService.verify failed unexpectedly` stack traces, file a D-### follow-up, and do NOT revert. A higher `max_tokens` cannot be worse than the prior budget — the prior budget was shipping `cove_verified=false` every run.
- If the Haiku 4.5 TPM ceiling starts issuing 429s on staging under the new budget (unlikely at L2 volume <10/day): lower the Step 3 answer cap to 3072 and re-verify. Stop before dropping below 2048 — that's the ceiling session 46 observed was still truncating.
- If Sonnet revision (Step 4) starts timing out at 3072 max_tokens: Sonnet emits JSON fast, so this is implausible, but if it happens, keep the Step 4 bump at 2048 and only bump Steps 1–3.

**Pre-flight baseline** (from `.claude/handoff.md` session 47):
- Local `main` at `811a6c3` (PR #87 merge commit). Origin matches.
- Backend test baseline: **1696 passed, 25 skipped, 0 failed**.
- `SPELIX_PHASE3_AGENT_ENABLED=1` on prod since session 32, `SPELIX_DISTILLATION_ENABLED=1` since session 42.
- D-048 observed active on analysis `de316a7a-b4fd-4fb4-afc4-a1d6be596fa2` (session 47 bench, post-D-045). `agent_trace_json.eval_scores.faithfulness=0.0`, `eval_scores.cove_verified=false`, `converged=false`.
- Session 46 PR #85 handoff observation: output_tokens 1024 → 2048 → 3072 all truncated for the aggregated Step 3 `VerificationAnswers` call.
- Test admin account: `atharva6905+admin-p3006@gmail.com` / `SpelixAdmin-P3006-Test-2026!` (UUID `cb18c043-5a16-4990-a3d3-02ed4890bf56`).
- Fixture `e2e/fixtures/atharva-bench-nw-10s-720p.mp4` already used by sessions 46 + 47 — re-use for deterministic comparison.

**Current `app/services/cove.py` max_tokens map** (from Read on file; confirm at Task 3 Step 1):
| Line | Step | Model | Response model | Current | Target |
|------|------|-------|----------------|---------|--------|
| 262  | 1: Claim extraction (pre-loop) | Haiku 4.5 | `ClaimList` | 512 | **1024** |
| 286  | 1: Claim extraction (iter > 1) | Haiku 4.5 | `ClaimList` | 512 | **1024** |
| 315  | 2: Question generation | Haiku 4.5 | `VerificationQuestions` | 512 | **1024** |
| 328  | 3: Independent verification (**blow-out path**) | Haiku 4.5 | `VerificationAnswers` | 1024 | **4096** |
| 371  | 4: Revision (iter < max) | Sonnet 4.6 | `CoachingOutput` | 2048 | **3072** |
| 389  | 4: Revision (iter == max) | Sonnet 4.6 | `CoachingOutput` | 2048 | **3072** |

**Bump rationale** (captured verbatim in ADR-COVE-01 at Task 9):
- ClaimList / VerificationQuestions: N short-list outputs. 512 → 1024 gives instructor headroom on schema-validation retries without meaningful cost impact.
- VerificationAnswers: N full `VerificationAnswer(question, answer, reasoning)` entries. For N=5 claims and ~60-token reasoning per claim, worst case is ~500 tokens payload; but session 46 observed truncation up to 3072 when Haiku emits verbose reasoning with source citations. 4096 is the next comfortable ceiling below Haiku 4.5's 8192 hard cap.
- Revision (Sonnet): regenerates a full `CoachingOutput` (summary + issues[] + correction_plan[] + cues[] + citations[] + disclaimer). 2048 was tight; 3072 gives the revisor room to preserve long issue descriptions without truncating mid-field.

---

## Task 1: Branch + baseline

**Files:** None modified.

**Context:** All backend changes ship via PR per root `CLAUDE.md` "Checkpoint Workflow". D-048 is a single-file code change plus one new test — trivial to bundle into its own PR. Keep the scope tight: this is NOT the place to also land D-046 (shared `_HAIKU_MODEL` constant) or D-047 (brain-path ValidationError regression test) — those are separate backlog rows and each deserves its own PR.

- [ ] **Step 1: Fetch latest main + create the feature branch**

Run from the repo root:
```bash
git fetch origin main
git checkout -b fix/d048-coaching-cove-max-tokens origin/main
```

Expected: branch created on `811a6c3` (or later if someone pushed to main since session 47).

- [ ] **Step 2: Confirm local baseline tests pass before any changes**

Run from `backend/`:
```bash
cd backend
uv run pytest -x -q --ignore=tests/e2e 2>&1 | tail -5
```

Expected: `1696 passed, 25 skipped in Ns`. If the suite is red before changes, STOP — the new test must go FAIL → PASS, which needs a green start.

- [ ] **Step 3: Confirm lint + type baseline**

Run from `backend/`:
```bash
uv run ruff check . && uv run pyright app/
```

Expected: `All checks passed` (ruff) and `0 errors, 0 warnings, 0 informations` (pyright). Fix any drift before proceeding.

- [ ] **Step 4: Confirm no existing test asserts the old max_tokens values**

Run from repo root:
```bash
grep -n max_tokens backend/tests/unit/test_cove.py
```

Expected: no matches. If matches DO exist (e.g., a previous contributor hardcoded an assertion), make a note — you'll need to update those assertions in Task 3 Step 4 to keep them passing after the bump.

---

## Task 2: Write the failing test for the bumped `CoveVerificationService` max_tokens

**Files:**
- Test: `backend/tests/unit/test_cove.py`

**Context:** The test introspects the `call_args_list` of the mocked `instructor_client.chat.completions.create` to verify every call site passes a sufficient `max_tokens` kwarg. The existing `_make_mock_instructor_client(side_effects)` helper at `tests/unit/test_cove.py:81` already wires up the mock — we reuse it. The test exercises the "all Yes on iteration 1" happy path because that path hits exactly three calls (claim extract + question gen + verification) — enough to assert the three Haiku call-site budgets. A second helper test covers the revision path (Steps 1–4, `max_iterations=2` with a No answer triggering revision) to assert the Sonnet Step 4 budget.

We write **two** tests:
1. `test_cove_max_tokens_meets_headroom_happy_path` — 3 calls, covers Steps 1, 2, 3.
2. `test_cove_max_tokens_meets_headroom_revision_path` — 4+ calls, covers Step 4 specifically.

Both must fail on current main before we ship the bump.

- [ ] **Step 1: Add both failing tests to `backend/tests/unit/test_cove.py`**

Append at the end of the file (after the last existing `@pytest.mark.asyncio` test):

```python
# ---------------------------------------------------------------------------
# D-048: max_tokens headroom tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cove_max_tokens_meets_headroom_happy_path() -> None:
    """D-048: Steps 1-3 max_tokens give Haiku 4.5 headroom against truncation.

    Session 46 + 47 prod E2E on bench-fixture analyses (6aa7b42b, de316a7a)
    both observed VerificationAnswers truncation at max_tokens 1024, 2048,
    and 3072. 4096 sits comfortably below Haiku 4.5's 8192 hard cap and
    leaves room for N=5 claims × ~60-token reasoning with source citations.
    Claim extraction and question generation are short-list outputs but are
    bumped 512 → 1024 as cheap headroom against instructor's structured-output
    retry loop.
    """
    initial_output = _make_coaching_output()
    contexts = [_make_retrieved_context()]

    claims_response = ClaimList(claims=["c1", "c2"])
    questions_response = VerificationQuestions(questions=["q1?", "q2?"])
    answers_response = VerificationAnswers(
        answers=[
            VerificationAnswer(question="q1?", answer="Yes", reasoning="r1"),
            VerificationAnswer(question="q2?", answer="Yes", reasoning="r2"),
        ]
    )
    mock_client = _make_mock_instructor_client(
        [claims_response, questions_response, answers_response]
    )

    with patch("app.services.cove.instructor.from_anthropic", return_value=mock_client):
        anthropic_client = MagicMock()
        svc = CoveVerificationService(anthropic_client=anthropic_client)
        result: CoveResult = await svc.verify(
            initial_output=initial_output,
            retrieved_contexts=contexts,
            max_iterations=2,
        )

    assert result.cove_verified is True, "happy path must converge on first iter"

    calls = mock_client.chat.completions.create.await_args_list
    assert len(calls) == 3, f"expected 3 calls (claim, question, answer); got {len(calls)}"

    # Step 1: claim extraction — response_model=ClaimList, max_tokens >= 1024.
    claim_kwargs = calls[0].kwargs
    assert claim_kwargs["response_model"] is ClaimList
    assert claim_kwargs["max_tokens"] >= 1024, (
        f"claim-extraction max_tokens {claim_kwargs['max_tokens']} < 1024 "
        "— cheap headroom against instructor structured-output retries (D-048)."
    )

    # Step 2: question generation — response_model=VerificationQuestions, max_tokens >= 1024.
    question_kwargs = calls[1].kwargs
    assert question_kwargs["response_model"] is VerificationQuestions
    assert question_kwargs["max_tokens"] >= 1024, (
        f"question-generation max_tokens {question_kwargs['max_tokens']} < 1024 "
        "— cheap headroom against instructor structured-output retries (D-048)."
    )

    # Step 3: verification answers — response_model=VerificationAnswers, max_tokens >= 4096.
    answer_kwargs = calls[2].kwargs
    assert answer_kwargs["response_model"] is VerificationAnswers
    assert answer_kwargs["max_tokens"] >= 4096, (
        f"verification-answer max_tokens {answer_kwargs['max_tokens']} < 4096 "
        "— session 46 + 47 observed truncation at 1024, 2048, and 3072 on prod "
        "aggregated N-claim VerificationAnswers output (D-048)."
    )


@pytest.mark.asyncio
async def test_cove_max_tokens_meets_headroom_revision_path() -> None:
    """D-048: Step 4 revision max_tokens >= 3072 so Sonnet can regenerate a
    full CoachingOutput (summary + issues + correction_plan + cues + citations
    + disclaimer) without mid-field truncation. Prior budget of 2048 was
    tight for multi-issue outputs.
    """
    initial_output = _make_coaching_output()
    contexts = [_make_retrieved_context()]

    claims_response = ClaimList(claims=["c1"])
    questions_response = VerificationQuestions(questions=["q1?"])
    # First verification answer is "No" → triggers revision.
    failed_answers = VerificationAnswers(
        answers=[
            VerificationAnswer(
                question="q1?",
                answer="No",
                reasoning="Evidence does not support this claim.",
            )
        ]
    )
    # After revision, second iteration's claim extraction returns no claims → converge.
    revised_output = _make_coaching_output(summary="Revised summary.")
    converged_claims = ClaimList(claims=[])

    mock_client = _make_mock_instructor_client(
        [
            claims_response,        # Step 1 pre-loop
            questions_response,      # Step 2 iter 1
            failed_answers,          # Step 3 iter 1 (No → revise)
            revised_output,          # Step 4 revision (Sonnet)
            converged_claims,        # Step 1 iter 2 → empty → converge
        ]
    )

    with patch("app.services.cove.instructor.from_anthropic", return_value=mock_client):
        anthropic_client = MagicMock()
        svc = CoveVerificationService(anthropic_client=anthropic_client)
        result: CoveResult = await svc.verify(
            initial_output=initial_output,
            retrieved_contexts=contexts,
            max_iterations=2,
        )

    assert result.cove_verified is True, (
        "revision + re-extract with empty claims must converge on iter 2"
    )

    calls = mock_client.chat.completions.create.await_args_list
    assert len(calls) == 5, (
        f"expected 5 calls (pre-loop claim, question, answer, revise, iter2 claim); "
        f"got {len(calls)}"
    )

    # Step 4 revision is the 4th call — response_model=CoachingOutput, max_tokens >= 3072.
    revision_kwargs = calls[3].kwargs
    assert revision_kwargs["model"] == SONNET_MODEL, (
        f"Step 4 revision must use Sonnet, got {revision_kwargs['model']}"
    )
    assert revision_kwargs["response_model"] is CoachingOutput
    assert revision_kwargs["max_tokens"] >= 3072, (
        f"revision max_tokens {revision_kwargs['max_tokens']} < 3072 "
        "— Sonnet needs room to regenerate a full CoachingOutput "
        "(summary + issues + correction_plan + cues + citations) (D-048)."
    )
```

- [ ] **Step 2: Run the new tests — verify they FAIL on current main**

From `backend/`:
```bash
uv run pytest tests/unit/test_cove.py::test_cove_max_tokens_meets_headroom_happy_path tests/unit/test_cove.py::test_cove_max_tokens_meets_headroom_revision_path -xvs
```

Expected: both `FAILED`, with assertion errors like:
- `verification-answer max_tokens 1024 < 4096 — session 46 + 47 observed truncation at 1024, 2048, and 3072 on prod aggregated N-claim VerificationAnswers output (D-048).`
- `revision max_tokens 2048 < 3072 — Sonnet needs room to regenerate ...`

If either test PASSES unexpectedly: re-check `cove.py` line 262, 286, 315, 328, 371, 389 — the budgets may have been pre-bumped in an unmerged branch. In that case, D-048 is a no-op — skip to Task 8 and proceed with documentation only.

- [ ] **Step 3: Commit the failing tests**

```bash
git add backend/tests/unit/test_cove.py
git commit -m "test(coaching): failing tests for CoveVerificationService max_tokens headroom (D-048)"
```

---

## Task 3: Bump `max_tokens` values in `cove.py`

**Files:**
- Modify: `backend/app/services/cove.py`

**Context:** Six `max_tokens=` literals across five logical call sites (Step 4 revision has two identical call blocks at line 371 and 389 — one for `iteration < max_iterations`, one for `iteration == max_iterations`). No other behavioral change — prompt text, model constants, response models, and messages are untouched.

- [ ] **Step 1: Verify line numbers by reading the file**

Run from repo root:
```bash
grep -n max_tokens backend/app/services/cove.py
```

Expected output (6 matches):
```
262:                max_tokens=512,
286:                    max_tokens=512,
315:                max_tokens=512,
328:                max_tokens=1024,
371:                    max_tokens=2048,
389:                    max_tokens=2048,
```

If line numbers differ, use Read on `backend/app/services/cove.py` to confirm the current layout and adjust your Edit operations accordingly. The logical sites are: pre-loop claim extraction (`ClaimList`), in-loop iteration>1 claim extraction (`ClaimList`), question generation (`VerificationQuestions`), verification answers (`VerificationAnswers`), and two Step 4 revision calls (`CoachingOutput`, Sonnet).

- [ ] **Step 2: Edit the pre-loop Step 1 claim extraction (around line 262)**

Find the first claim-extraction block, `model=HAIKU_MODEL, max_tokens=512, response_model=ClaimList` with messages calling `_build_claim_extraction_prompt(current_output)`. Replace `max_tokens=512` with `max_tokens=1024`.

```python
# BEFORE
        claim_list = await self._instructor_client.chat.completions.create(
            model=HAIKU_MODEL,
            max_tokens=512,
            response_model=ClaimList,
            messages=[
                {
                    "role": "user",
                    "content": _build_claim_extraction_prompt(current_output),
                }
            ],
        )
```

```python
# AFTER
        claim_list = await self._instructor_client.chat.completions.create(
            model=HAIKU_MODEL,
            # D-048: 1024 gives instructor structured-output retry headroom
            # over 512 with trivial Haiku 4.5 cost impact.
            max_tokens=1024,
            response_model=ClaimList,
            messages=[
                {
                    "role": "user",
                    "content": _build_claim_extraction_prompt(current_output),
                }
            ],
        )
```

- [ ] **Step 3: Edit the in-loop iteration>1 Step 1 claim extraction (around line 286)**

Find the second claim-extraction block (inside the `for iteration in range(1, max_iterations + 1):` loop, guarded by `if iteration > 1:`). Same replacement: `max_tokens=512` → `max_tokens=1024`. Use the exact same inline comment as Step 2 to keep the two sites consistent.

```python
# BEFORE
            if iteration > 1:
                claim_list = await self._instructor_client.chat.completions.create(
                    model=HAIKU_MODEL,
                    max_tokens=512,
                    response_model=ClaimList,
                    messages=[
                        {
                            "role": "user",
                            "content": _build_claim_extraction_prompt(current_output),
                        }
                    ],
                )
```

```python
# AFTER
            if iteration > 1:
                claim_list = await self._instructor_client.chat.completions.create(
                    model=HAIKU_MODEL,
                    # D-048: 1024 gives instructor structured-output retry headroom
                    # over 512 with trivial Haiku 4.5 cost impact.
                    max_tokens=1024,
                    response_model=ClaimList,
                    messages=[
                        {
                            "role": "user",
                            "content": _build_claim_extraction_prompt(current_output),
                        }
                    ],
                )
```

- [ ] **Step 4: Edit Step 2 question generation (around line 315)**

Find the `response_model=VerificationQuestions` call. Replace `max_tokens=512` with `max_tokens=1024`.

```python
# BEFORE
            verification_questions = await self._instructor_client.chat.completions.create(
                model=HAIKU_MODEL,
                max_tokens=512,
                response_model=VerificationQuestions,
                messages=[
                    {
                        "role": "user",
                        "content": _build_question_generation_prompt(claim_list.claims),
                    }
                ],
            )
```

```python
# AFTER
            verification_questions = await self._instructor_client.chat.completions.create(
                model=HAIKU_MODEL,
                # D-048: 1024 gives instructor structured-output retry headroom
                # over 512 with trivial Haiku 4.5 cost impact.
                max_tokens=1024,
                response_model=VerificationQuestions,
                messages=[
                    {
                        "role": "user",
                        "content": _build_question_generation_prompt(claim_list.claims),
                    }
                ],
            )
```

- [ ] **Step 5: Edit Step 3 verification answers (around line 328) — this is the documented blow-out path**

Find the `response_model=VerificationAnswers` call. Replace `max_tokens=1024` with `max_tokens=4096`. This is the line that sessions 46 and 47 observed truncating at 1024, 2048, and 3072 output tokens on prod.

```python
# BEFORE
            verification_answers = await self._instructor_client.chat.completions.create(
                model=HAIKU_MODEL,
                max_tokens=1024,
                response_model=VerificationAnswers,
                messages=[
                    {
                        "role": "user",
                        "content": _build_verification_prompt(
                            verification_questions.questions,
                            retrieved_contexts,
                        ),
                    }
                ],
            )
```

```python
# AFTER
            verification_answers = await self._instructor_client.chat.completions.create(
                model=HAIKU_MODEL,
                # D-048: session 46 + 47 prod E2E observed output_tokens
                # 1024 → 2048 → 3072 all truncated for aggregated N-claim
                # VerificationAnswers. 4096 sits comfortably below Haiku 4.5's
                # 8192 hard cap and gives N=5 claims × ~60-token reasoning
                # with source citations room without mid-field JSON truncation.
                max_tokens=4096,
                response_model=VerificationAnswers,
                messages=[
                    {
                        "role": "user",
                        "content": _build_verification_prompt(
                            verification_questions.questions,
                            retrieved_contexts,
                        ),
                    }
                ],
            )
```

- [ ] **Step 6: Edit Step 4 revision — `iteration < max_iterations` (around line 371)**

Find the first revision block (inside the `if iteration < max_iterations:` branch). Replace `max_tokens=2048` with `max_tokens=3072`.

```python
# BEFORE
            if iteration < max_iterations:
                revised_output = await self._instructor_client.chat.completions.create(
                    model=SONNET_MODEL,
                    max_tokens=2048,
                    response_model=CoachingOutput,
                    messages=[
                        {
                            "role": "user",
                            "content": _build_revision_prompt(
                                current_output,
                                failed,
                                retrieved_contexts,
                            ),
                        }
                    ],
                )
                current_output = revised_output
```

```python
# AFTER
            if iteration < max_iterations:
                revised_output = await self._instructor_client.chat.completions.create(
                    model=SONNET_MODEL,
                    # D-048: 3072 gives Sonnet 4.6 room to regenerate a full
                    # CoachingOutput (summary + issues + correction_plan +
                    # cues + citations + disclaimer) without mid-field
                    # truncation on multi-issue outputs.
                    max_tokens=3072,
                    response_model=CoachingOutput,
                    messages=[
                        {
                            "role": "user",
                            "content": _build_revision_prompt(
                                current_output,
                                failed,
                                retrieved_contexts,
                            ),
                        }
                    ],
                )
                current_output = revised_output
```

- [ ] **Step 7: Edit Step 4 revision — `iteration == max_iterations` (around line 389)**

Find the second revision block (inside the `else:` branch — "Final iteration exhausted — run revision anyway for latest output"). Replace `max_tokens=2048` with `max_tokens=3072`. Same inline comment as Step 6.

```python
# BEFORE
            else:
                # Final iteration exhausted — run revision anyway for latest output
                revised_output = await self._instructor_client.chat.completions.create(
                    model=SONNET_MODEL,
                    max_tokens=2048,
                    response_model=CoachingOutput,
                    messages=[
                        {
                            "role": "user",
                            "content": _build_revision_prompt(
                                current_output,
                                failed,
                                retrieved_contexts,
                            ),
                        }
                    ],
                )
                current_output = revised_output
```

```python
# AFTER
            else:
                # Final iteration exhausted — run revision anyway for latest output
                revised_output = await self._instructor_client.chat.completions.create(
                    model=SONNET_MODEL,
                    # D-048: 3072 gives Sonnet 4.6 room to regenerate a full
                    # CoachingOutput (summary + issues + correction_plan +
                    # cues + citations + disclaimer) without mid-field
                    # truncation on multi-issue outputs.
                    max_tokens=3072,
                    response_model=CoachingOutput,
                    messages=[
                        {
                            "role": "user",
                            "content": _build_revision_prompt(
                                current_output,
                                failed,
                                retrieved_contexts,
                            ),
                        }
                    ],
                )
                current_output = revised_output
```

- [ ] **Step 8: Run the two new tests — verify they PASS now**

From `backend/`:
```bash
uv run pytest tests/unit/test_cove.py::test_cove_max_tokens_meets_headroom_happy_path tests/unit/test_cove.py::test_cove_max_tokens_meets_headroom_revision_path -xvs
```

Expected: both `PASSED`.

- [ ] **Step 9: Run the full `test_cove.py` module — no regressions**

```bash
uv run pytest tests/unit/test_cove.py -xvs
```

Expected: all existing tests + the two new tests PASS (baseline 6 + new 2 = 8).

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/cove.py
git commit -m "fix(coaching): bump CoveVerificationService max_tokens across all 4 CoVe steps (D-048)

Session 46 + session 47 prod E2E on bench-fixture analyses (6aa7b42b,
de316a7a) both observed the Step 3 VerificationAnswers call truncating at
output_tokens 1024, 2048, and 3072. Session 47 confirmed the failure
survives the D-045 retrieval fix — independent of retrieval routing.

Effect: eval_scores.cove_verified was spuriously persisted as false and
faithfulness as 0.0 on every completed analysis, even when the underlying
coaching was valid. Fix lifts Step 3 to 4096 (below Haiku 4.5's 8192 cap)
and also bumps the cheap-to-raise Steps 1/2 from 512 to 1024 and Step 4
Sonnet revision from 2048 to 3072 so the revisor never truncates a full
CoachingOutput mid-field.

Analogous to session-46 M-05 bump on the brain-path BrainCoveService
(ADR-DISTILL-06). Introduces ADR-COVE-01 for the coaching-path decision.

Refs: D-048, FR-AICP-08, ADR-COVE-01"
```

---

## Task 4: Full suite green + lint clean

**Files:** None modified.

**Context:** Before pushing, run the full backend suite + ruff + pyright to catch anything the isolated module run missed. This is the gate for "ready to push" per root `CLAUDE.md` Checkpoint Workflow.

- [ ] **Step 1: Run the full backend test suite**

From `backend/`:
```bash
uv run pytest -x -q --ignore=tests/e2e 2>&1 | tail -10
```

Expected: `1698 passed, 25 skipped in Ns` (baseline 1696 + 2 new D-048 tests). If any test is unexpectedly red, STOP — diagnose before pushing. The most likely surprise: an existing test that patched the instructor mock and hardcoded an asserted `max_tokens` (would have been caught at Task 1 Step 4 grep if present, but re-check if red).

- [ ] **Step 2: Run ruff + pyright**

```bash
uv run ruff check .
uv run pyright app/
```

Expected: clean. If ruff complains about the inline `# D-048:` comments being too long, wrap them to stay under the project's configured line length. If pyright complains, re-check that no stray typo was introduced in the edits.

- [ ] **Step 3: Run frontend type-check for parity with handoff baseline (quick sanity)**

From repo root:
```bash
cd frontend
npx tsc --noEmit
```

Expected: 0 errors. (Skip vitest run — D-048 is backend-only.)

---

## Task 5: Push + open PR

**Files:** None modified.

**Context:** GitHub MCP tools per root `CLAUDE.md` "GitHub Operations — Use GitHub MCP First". Do NOT merge yet — wait for CI green and spelix-auditor clearance in Task 6.

- [ ] **Step 1: Push the branch to origin**

```bash
git push -u origin fix/d048-coaching-cove-max-tokens
```

- [ ] **Step 2: Create the PR via GitHub MCP**

Use `mcp__github__create_pull_request` with:

- **title**: `fix(coaching): D-048 bump CoveVerificationService max_tokens across all 4 CoVe steps`
- **head**: `fix/d048-coaching-cove-max-tokens`
- **base**: `main`
- **body**:

```markdown
## Summary

Closes D-048. Coaching-path Chain-of-Verification was silently truncating the Step 3 `VerificationAnswers` call on prod, persisting `eval_scores.cove_verified=false` and `faithfulness=0.0` on every completed analysis — regardless of underlying coaching quality.

- Session 46 observed output_tokens 1024 → 2048 → 3072 all truncated on bench analysis `6aa7b42b`.
- Session 47 reproduced the exact same failure on `de316a7a` *after* the D-045 retrieval fix landed — proving independence from retrieval routing.
- Fix: bump `CoveVerificationService` `max_tokens` across every call site. Step 3 (the documented blow-out path) goes 1024 → **4096** (well below Haiku 4.5's 8192 cap). Claim extraction and question generation (Steps 1, 2) go 512 → **1024** for cheap instructor-retry headroom. Sonnet revision (Step 4) goes 2048 → **3072** to preserve multi-issue `CoachingOutput` regenerations without mid-field truncation.

Analogous to the session-46 M-05 bump on the brain-path `BrainCoveService` (ADR-DISTILL-06). Introduces **ADR-COVE-01** documenting the coaching-path decision.

## SRS + ADR refs

- FR-AICP-08 Stage 2 (CoVe loop; `app/services/cove.py`)
- ADR-COVE-01 (new — max_tokens budget rationale; added in this PR to `decisions.md`)
- ADR-DISTILL-06 (precedent — distillation-path max_tokens; session 46)

## Test changes

- `test_cove_max_tokens_meets_headroom_happy_path` — asserts `instructor.chat.completions.create` receives `max_tokens >= 1024` on the claim + question calls and `max_tokens >= 4096` on the answer call via call-kwargs introspection. FAIL → PASS gate.
- `test_cove_max_tokens_meets_headroom_revision_path` — asserts Step 4 revision (Sonnet) passes `max_tokens >= 3072`. FAIL → PASS gate.
- No other test changes. Baseline `grep -n max_tokens backend/tests/unit/test_cove.py` returned zero matches pre-PR — nothing hardcoded the old values.

## Test plan

- [x] `uv run pytest -x -q --ignore=tests/e2e` → 1698/1698 passed locally
- [x] `uv run ruff check . && uv run pyright app/` → clean
- [x] `npx tsc --noEmit` → 0 errors
- [ ] CI green (6 gate checks)
- [ ] `spelix-auditor` clean (pre-merge)
- [ ] `spelix-security-reviewer` clean (pre-merge)
- [ ] Deploy to Production step green
- [ ] Playwright MCP upload of `atharva-bench-nw-10s-720p.mp4` under admin test account: inspect `coaching_results.agent_trace_json.eval_scores.cove_verified` (expect `true`) and `eval_scores.faithfulness` (expect > 0.0). Side-by-side against session 47 baseline `de316a7a` which observed `cove_verified=false, faithfulness=0.0`.

## Rollback

- If prod still shows `cove_verified=false, faithfulness=0.0` post-merge: the 4096 cap on Step 3 was insufficient (unlikely — session 46 max observed was 3072). Root-cause via worker logs for `CoveVerificationService.verify failed unexpectedly` stack traces, file D-### follow-up, do NOT revert (prior budget was strictly worse).
- If Haiku 4.5 429 rate limits surface on staging at the new budget: lower Step 3 to 3072 and re-verify. Do NOT drop below 2048 — that's the ceiling session 46 observed still truncating.
```

Record the PR number.

- [ ] **Step 3: Wait for CI**

Use `mcp__github__get_pull_request_status` with the PR number every ~60s until all 6 gate checks (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel) show `success`. Usually completes in 4–5 minutes. If any check fails, fix in place — do NOT merge with red CI.

---

## Task 6: Pre-merge audits

**Files:** None modified. Agent-generated reports only.

**Context:** Per root `CLAUDE.md` General Rules: "Run `spelix-auditor` after every batch merge, not just at phase gates". Also invoke `spelix-security-reviewer` — this PR modifies LLM config in a coaching path that produces user-facing content, so the SaMD/FTC language layer must re-pass even though no prompt text changed.

- [ ] **Step 1: Run `spelix-auditor`**

Invoke the `spelix-auditor` agent with:

> Audit PR #<number> for SRS compliance. Scope: D-048 max_tokens bump on `CoveVerificationService` (FR-AICP-08 Stage 2). Verify: (1) max_tokens changes do not break the CoVe loop contract (claim → question → answer → revise), (2) no prompt text, response model, or model constant changed, (3) ADR-COVE-01 is consistent with existing ADR-DISTILL-06 precedent, (4) the new tests cover all five logical call sites, (5) nothing else was smuggled into the diff. Flag anything not addressed. Read-only — do not modify files.

Expected: PASS or PASS_WITH_FINDINGS. Address all HIGH/CRITICAL findings before merge. MEDIUM findings can become follow-up D-### backlog rows.

- [ ] **Step 2: Run `spelix-security-reviewer`**

Invoke with:

> Security review PR #<number>. D-048 bumps `CoveVerificationService` max_tokens across 6 call sites in `app/services/cove.py`. Check: (1) no new user-facing strings (no SaMD/FTC-forbidden language introduced); (2) no logging of LLM responses that could leak PII via longer output; (3) `CoveResult` error-path trace payload (`{"error": str(exc)}`) unchanged — still safe per existing behavior; (4) no secret exposure in inline comments or commit messages; (5) no JWT/RLS/auth touch. Read-only.

Expected: PASS. Any failure → fix in-branch before merge.

- [ ] **Step 3: Address findings if any, push fix-up commits, re-run CI**

If findings need code changes, commit them on the same branch, push, wait for CI green again before Task 7.

---

## Task 7: Merge + wait for Deploy to Production

**Files:** None modified.

**Context:** Per root `CLAUDE.md` + `feedback_no_squash_merge.md`: use merge commit via GitHub MCP with `merge_method="merge"`, NOT squash. Per `feedback_no_manual_deploy.md`: do NOT SSH deploy — CI handles it.

- [ ] **Step 1: Merge via GitHub MCP**

Use `mcp__github__merge_pull_request` with:
- pull_number: the PR number
- merge_method: `"merge"` (NOT `"squash"`)

Record the merge commit SHA.

- [ ] **Step 2: Pull main locally**

```bash
git checkout main
git pull origin main
```

Expected: local `main` at the new merge commit.

- [ ] **Step 3: Wait for "Deploy to Production" CI step**

Monitor with `mcp__github__get_pull_request_status` until `Deploy to Production` shows `success`. Usually 3–5 minutes.

- [ ] **Step 4: Verify droplet HEAD matches merge commit**

```bash
ssh spelix-droplet "git -C /srv/spelix log --oneline -1"
```

Expected: matches the merge commit SHA from Step 1.

- [ ] **Step 5: Verify containers are healthy**

```bash
ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"
```

Expected: all containers (`spelix-backend`, `spelix-worker`, `spelix-caddy`, `spelix-redis`) show `(healthy)` status. If any is not healthy, STOP and diagnose before running the prod E2E.

---

## Task 8: E2E verification on prod

**Files:** Screenshots saved to `e2e/screenshots/d048-post-fix-cove-verified-<short-hash>.png`.

**Context:** Per root `CLAUDE.md` "E2E Verification via Playwright MCP": this PR touches the coaching pipeline and changes `eval_scores` behavior. E2E is required. Re-use the exact same fixture sessions 46 and 47 used (`atharva-bench-nw-10s-720p.mp4`) under the same admin test account for side-by-side comparability.

- [ ] **Step 1: Log in as admin test account via Playwright MCP**

Use `mcp__playwright__browser_navigate` to `https://spelix.app`. Log in with:
- email: `atharva6905+admin-p3006@gmail.com`
- password: `SpelixAdmin-P3006-Test-2026!`

Use `mcp__playwright__browser_snapshot` to confirm login succeeded (dashboard visible).

- [ ] **Step 2: Upload `atharva-bench-nw-10s-720p.mp4` (same fixture as sessions 46 + 47)**

Use `mcp__playwright__browser_file_upload` with absolute path:
```
C:\Users\athar\projects\spelix\e2e\fixtures\atharva-bench-nw-10s-720p.mp4
```

Pick `bench` as exercise. Wait for upload to complete, then click "Start analysis". This keeps the analysis deterministically comparable against session-46 baseline `6aa7b42b` and session-47 baseline `de316a7a`.

- [ ] **Step 3: Wait for analysis to complete**

Poll the results page via `browser_snapshot` until the coaching feedback renders (typically ~90–120s). Record the analysis UUID from the URL.

- [ ] **Step 4: Inspect `eval_scores` via Supabase SQL MCP**

Use `mcp__supabase__execute_sql`:
```sql
select
  id,
  status,
  jsonb_extract_path_text(agent_trace_json, 'eval_scores', 'cove_verified') as cove_verified,
  jsonb_extract_path_text(agent_trace_json, 'eval_scores', 'faithfulness')  as faithfulness,
  jsonb_extract_path_text(agent_trace_json, 'retrieval_source')             as retrieval_source,
  jsonb_extract_path_text(agent_trace_json, 'degraded_mode')                as degraded_mode,
  jsonb_extract_path_text(agent_trace_json, 'converged')                    as converged
from coaching_results
where analysis_id = '<analysis UUID from Step 3>';
```

Expected (success criteria — all three must hold):
- `cove_verified = 'true'` (was `false` on sessions 46 + 47)
- `faithfulness` > `'0.0'` (was `'0.0'` on sessions 46 + 47)
- `retrieval_source = 'coach_brain_primary'` (carry-over from D-045, should NOT regress)

Expected unchanged from session 47:
- `degraded_mode = 'false'`

If `cove_verified` is still `'false'`:
- Run `ssh spelix-droplet "docker logs spelix-worker --tail 400 | grep -i cove"` — look for `CoveVerificationService.verify failed unexpectedly` stack traces. The exception message in `trace[0].error` will say whether it's still a max_tokens truncation (instructor `ValidationError`) or a different failure (rate limit, auth, network).
- Do NOT revert. The new budget cannot be strictly worse than the prior one — file a D-### follow-up with the worker log excerpt.

- [ ] **Step 5: Side-by-side comparison table for handoff**

Record this table for Task 9 Step 3 to paste into `.claude/handoff.md`:

| Check | Session 46 `6aa7b42b` | Session 47 `de316a7a` | Session 48 `<new UUID>` |
|---|---|---|---|
| `retrieval_source` | `papers_only_fallback` | `coach_brain_primary` | (Step 4 value) |
| `cove_verified` | `false` | `false` | (Step 4 value) |
| `faithfulness` | `0.0` | `0.0` | (Step 4 value) |
| `converged` | `false` | `false` | (Step 4 value) |
| `degraded_mode` | `false` | `false` | (Step 4 value) |

- [ ] **Step 6: Take a screenshot for the handoff**

Use `mcp__playwright__browser_take_screenshot` on the results page. Save to `e2e/screenshots/d048-post-fix-cove-verified-<short-hash>.png` where `<short-hash>` is the first 8 chars of the analysis UUID.

- [ ] **Step 7: Check console + network errors**

```python
# via Playwright MCP
browser_console_messages(level="error")  # expect []
browser_network_requests()  # filter for 4xx/5xx — expect 0 in the upload/status/coaching-stream path
```

---

## Task 9: Docs — ADR + backlog + handoff

**Files:**
- Modify: `decisions.md`
- Modify: `backlog.md`
- Modify: `.claude/handoff.md`

**Context:** Per root `CLAUDE.md` "decisions.md & backlog.md Update Protocol": "Do NOT batch updates at end-of-session; run inline with the code changes that triggered them." D-048 introduces a durable choice (max_tokens budgets per CoVe step on the coaching path) — that's an ADR. Use the new **ADR-COVE-01** ID family; the coaching-path CoVe has no prior ADR, and ADR-DISTILL-06 is scoped to the brain-path `BrainCoveService`.

- [ ] **Step 1: Append ADR-COVE-01 to `decisions.md`**

Append at the end of the file (decisions.md is append-only across phases):

```markdown
## ADR-COVE-01: CoveVerificationService Haiku 4.5 / Sonnet 4.6 max_tokens budgets (Session 48)

**Context**: Sessions 46 and 47 prod E2E on bench-fixture analyses (`6aa7b42b`, `de316a7a`) both observed `eval_scores.cove_verified=false` and `faithfulness=0.0` on completed analyses despite valid coaching output. Root cause: `CoveVerificationService._run_cove_loop` Step 3 `VerificationAnswers` call was capped at `max_tokens=1024` — too tight for Haiku 4.5's aggregated N-claim response (one `{question, answer, reasoning}` entry per claim, with reasoning citing source numbers). Instructor's structured-output retry loop failed three times; the service's top-level `try/except` swallowed the `ValidationError` and persisted `CoveResult(cove_verified=false, iterations_run=0, trace=[{"error": ...}])`. The faithfulness gate downstream read the swallowed result and stored `faithfulness=0.0`. Session 47 confirmed the failure survives the D-045 retrieval fix (Coach Brain retrieval now routes correctly; coaching-path CoVe still blew up) — proving independence from retrieval routing. D-048 bumps every `max_tokens=` in the CoVe loop.

**Decision**: Adopt the following per-step budgets in `app/services/cove.py::CoveVerificationService._run_cove_loop`:

| Step | Model | Response model | Budget | Rationale |
|------|-------|----------------|--------|-----------|
| 1: Claim extraction (pre-loop + iter > 1) | Haiku 4.5 | `ClaimList` | **1024** | Short-list output; cheap headroom against instructor retries. |
| 2: Question generation | Haiku 4.5 | `VerificationQuestions` | **1024** | Short-list output; cheap headroom against instructor retries. |
| 3: Independent verification | Haiku 4.5 | `VerificationAnswers` | **4096** | Documented blow-out path. N aggregated answers × ~60-token reasoning. Sessions 46 + 47 observed truncation at 1024, 2048, 3072. 4096 sits below Haiku 4.5's 8192 hard cap. |
| 4: Revision (both branches) | Sonnet 4.6 | `CoachingOutput` | **3072** | Regenerates full coaching output (summary + issues + correction_plan + cues + citations + disclaimer). 2048 was tight for multi-issue outputs. |

**Consequences**:
- `cove_verified` now reflects the actual coaching-vs-evidence verdict, not silent instructor failure. Downstream `faithfulness` scoring will reflect real alignment.
- Cost impact at L2-beta volume (<10 analyses/day × ≤2 iterations × worst-case 4096 output × $1.25/MTok Haiku output): ~$0.10/day delta. Negligible.
- If Haiku 4.5 ever legitimately emits >4096 tokens of verification reasoning, the existing top-level `try/except` in `verify()` catches the `ValidationError` and falls back to `cove_verified=false, trace=[{"error": ...}]` — same loud signal the prior budget would have produced, just at a higher ceiling. If this becomes common, iterate (8192 is the Haiku hard cap) rather than dropping the budget back.
- Precedent: session-46 M-05 bump on the brain-path `BrainCoveService` (ADR-DISTILL-06). Coaching path and distillation path are intentionally separate services per ADR-DISTILL-03 — the budgets differ because they verify different input shapes (full `CoachingOutput` vs single atomic cue), but the design principle ("pay cheap Haiku 4.5 output tokens to avoid instructor retry pathology") is the same.
- Do NOT drop any budget below its prior value — that's the known-broken state.
```

- [ ] **Step 2: Update `backlog.md` — close D-048, add completion row**

Edit `backlog.md` in place: find the D-048 row (search string `| D-048 |`) and change the rightmost `| open |` to `| done — <merge SHA> |`. Keep everything else on that row the same.

At the top of the `## Completed` section (after the most recent session-47 D-045 row), add a new section:

```markdown
## Completed — L2 Sprint Day 10 — D-048 coaching-path CoVe max_tokens bump (2026-04-18, session 48)

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| D-048 | Bump CoveVerificationService max_tokens across all 4 CoVe steps (claim 1024, question 1024, answer 4096, revision 3072) | done | S | M-05 | FR-AICP-08, ADR-COVE-01 | `<merge SHA>` | `backend/app/services/cove.py`, `backend/tests/unit/test_cove.py` |
```

Substitute `<merge SHA>` with the Task 7 Step 1 value.

- [ ] **Step 3: Update `.claude/handoff.md`**

Append to the handoff file (session 48 is authoring handoff to session 49):

- In `## 1. Completed`, add a PR table entry: title, merge SHA, list of the commits from this plan (failing tests, max_tokens bump, any audit-finding fix-ups, docs commit).
- In `## 2. Remaining`, cross off D-048 from Priority 2. If prod E2E Step 4 still observed `cove_verified=false` unexpectedly (see Task 8 Step 4 fallback), file a new `D-050 — investigate residual CoVe failure despite D-048 budget bump` row under Priority 3.
- Append `## N. E2E Findings — D-048 verification` with: the side-by-side table from Task 8 Step 5, new analysis UUID, screenshot path, a one-line summary of whether `cove_verified` flipped to `true`.
- In `## 3. Test counts`, update the backend count to `1698 passed, 25 skipped, 0 failed`.
- In `## 7. Next session start`, remove D-048 from Priority 2. Promote D-046 (hoist `_HAIKU_MODEL`), D-047 (ValidationError regression test), D-049 (Citation serializer warnings) to Priority 2 head of list. Shift Priority 3 / Priority 4 blocks accordingly.

- [ ] **Step 4: Commit the docs**

```bash
git add decisions.md backlog.md .claude/handoff.md
git commit -m "docs(decisions,backlog,handoff): close D-048 + ADR-COVE-01 + session 48 handoff"
git push origin main
```

- [ ] **Step 5: Final sanity — confirm `git status` clean and main matches origin + droplet**

```bash
git status
git log --oneline -3
ssh spelix-droplet "git -C /srv/spelix log --oneline -1"
```

Expected: clean working tree; local + origin + droplet all at the new docs commit (after CI re-deploys docs; docs-only changes may skip Deploy to Production — that's fine).

---

## Self-review — spec coverage check

**D-048 coverage:**
- Task 2 writes two failing tests covering Steps 1–3 (happy path) and Step 4 (revision path). ✓
- Task 3 Steps 2–7 bump all 6 `max_tokens=` literals across the 5 logical call sites. ✓
- Task 3 Step 8–9 verify tests pass + no regressions. ✓
- Task 4 full suite + lint + type + frontend tsc. ✓
- Task 5 PR via GitHub MCP with merge commit strategy. ✓
- Task 6 `spelix-auditor` + `spelix-security-reviewer` per CLAUDE.md General Rule. ✓
- Task 7 merge via `merge_method="merge"` per `feedback_no_squash_merge.md`. ✓
- Task 7 no manual deploy per `feedback_no_manual_deploy.md`. ✓
- Task 8 E2E via Playwright MCP per CLAUDE.md, same fixture sessions 46/47 used for comparability. ✓
- Task 8 Step 5 records side-by-side table to validate fix against prior baselines. ✓
- Task 9 Step 1 adds ADR-COVE-01 documenting the decision. ✓
- Task 9 Step 2 closes backlog D-048 row + appends completion section. ✓
- Task 9 Step 3 handoff updated inline per General Rule. ✓

**Placeholder scan:** No "TBD", "TODO", "implement later", "fill in details", or "Similar to Task N" in any step. Every step has exact commands, exact code blocks, and exact expected output. ✓

**Type consistency:** `ClaimList`, `VerificationQuestions`, `VerificationAnswers`, `CoachingOutput`, `HAIKU_MODEL`, `SONNET_MODEL` all match the actual symbols defined in `app/services/cove.py`. `_make_mock_instructor_client`, `_make_coaching_output`, `_make_retrieved_context` helpers match the existing `test_cove.py` module. Test names are unique and don't collide with existing tests. ✓
