# MC/DC Testing Methodology

## What is MC/DC?

Modified Condition/Decision Coverage (MC/DC) is a structural testing criterion originally defined in DO-178C Level A, the avionics software safety standard used for flight-critical systems. It requires that each condition within a compound boolean decision independently affect the overall decision outcome at least once. This is a strictly stronger guarantee than statement coverage (which only verifies that a line executes), branch coverage (which verifies both true and false branches of each decision), and even full condition coverage (which only checks that each atomic condition takes both values). MC/DC adds the independence requirement: for every condition C in a decision, there must exist a pair of test vectors that differ only in C's value while the decision outcome flips. This pair is called the independent effect pair for C.

The practical consequence is that MC/DC catches a class of bugs that branch coverage misses: conditions that are always dominated by another condition in the same expression. For example, in `A or B`, branch coverage is satisfied by two tests — `(A=T, B=F)` and `(A=F, B=F)` — but neither test exercises B as a determining factor. MC/DC requires a third test `(A=F, B=T)` that proves B can independently trigger the branch. Without it, a bug where B is always False (silently returning incorrect output) would pass branch coverage undetected.

## Why MC/DC for Spelix?

The Spelix CV scoring pipeline makes safety-critical numerical decisions that flow directly into user-facing coaching feedback. Functions such as `SafetyScore._score_deadlift` determine whether a user receives a Movement Quality penalty based on compound range-check predicates (`hip_angle < min_hip or hip_angle > max_hip`). If one sub-condition in such a predicate were broken — always evaluating False due to a threshold misconfiguration or a wrong comparison operator — branch coverage would not detect it, because the branch can still fire via the other sub-condition. The user would receive incorrect coaching: either a false alarm (spurious penalty) or a missed warning (no penalty when form is dangerous). For a platform whose value proposition is science-based feedback, silent scoring errors are a primary reliability risk.

MC/DC is the appropriate response because the failure mode it detects is exactly the "dominated condition" class: a condition that can never independently influence the outcome because it is always overridden by another condition in the same expression. For scoring.py, quality_gates.py, and pipeline.py, this covers every compound predicate where a misconfigured threshold, wrong operator, or inverted boolean would produce incorrect user-visible scores while the overall branch still fires. The 16 functions selected for MC/DC treatment are those where incorrect branching has direct consequences visible to the end user: a wrong score, a wrong quality-gate rejection, a missed rep, or a missed fallback trigger.

## Scope

MC/DC coverage is applied to 16 functions across 5 files, covering approximately 82 compound conditions and 90 test vectors. The rest of the codebase is held to 90% branch coverage enforced in CI. MC/DC is reserved for functions where incorrect branching has a direct user-facing consequence — incorrect scoring, incorrect video rejection, missed rep detection, or a missed fallback. Repository, service, and API-layer code does not fall under this criterion because errors there produce API-level failures (HTTP errors, exceptions) that are immediately visible and caught by integration tests.

The five files under MC/DC:

- `backend/app/cv/scoring.py` — SafetyScore, TechniqueScore, ControlScore: compound predicates that determine form score penalties and Movement Quality badges visible to users
- `backend/app/cv/quality_gates.py` — video validation, framing, single_person, lighting, orchestrator: compound predicates that determine whether a video is accepted or rejected before processing
- `backend/app/cv/rep_detection.py` — state machine ascending/descending transitions, peak/valley fallback trigger: compound conditions that determine whether a rep is counted, aborted, or routed to the fallback detector
- `backend/app/cv/confidence.py` — Tier 4 phase adjustment: branching that selects the phase multiplier applied to every per-frame confidence score, affecting the pessimistic Tier 5 bound
- `backend/app/services/pipeline.py` — degenerate scoring guard (`_is_degenerate_scoring_input`) and GPT-4o fallback trigger: OR/AND conditions that route the pipeline to degraded or fallback modes

## How to Read the Traceability Matrix

Each entry in the traceability matrix records one compound boolean decision. The function name and source file reference are followed by the exact boolean expression under test and a truth table with MC/DC rows. Each row specifies the values of every atomic condition, the resulting decision value, and — where applicable — identifies which condition independently causes the flip. The independent effect pair for condition C is the pair of rows `{i, j}` such that: row i and row j differ only in C's value, and the decision outcome differs between row i and row j. MC/DC is satisfied for a decision when every condition in it has at least one such pair covered by the test suite.

Tests are referenced by the format `test_file.py::ClassName`. The class groups all MC/DC rows for a single compound decision. Some decisions use a None-guard as one row (e.g., `C4=F: key absent`) to cover the case where the compound expression is short-circuited by a missing metric; this is intentional — in Python, `.get()` returning `None` and a subsequent `is not None` check is itself a boolean condition that must be independently exercised. The MC/DC verdict at the end of each entry (`Rows {i,j} for A`, `{i,k} for B`) identifies the specific pairs that satisfy the criterion for each condition.

## Maintenance

When modifying a compound boolean condition in any of the 16 MC/DC-targeted functions, the corresponding truth table in this file and the MC/DC test class in `backend/tests/mcdc/` must be updated in the same PR. Specifically: if a threshold value changes only in `config/thresholds_v1.json`, no test update is required because the tests read config values dynamically. If the boolean structure of the expression changes (e.g., adding a third condition to an OR, replacing `<` with `<=`, or adding a new None-guard), the truth table must be rebuilt from scratch for that function, the independent effect pairs re-identified, and new or modified test rows added before the PR is merged. Run the MC/DC suite before opening the PR with: `uv run pytest tests/mcdc/ -xvs`.
