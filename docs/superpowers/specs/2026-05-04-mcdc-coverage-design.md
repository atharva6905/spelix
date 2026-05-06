# MC/DC Coverage Initiative — Design Spec

## Goal

Achieve Modified Condition/Decision Coverage (MC/DC) on the 16 most safety-critical functions in the Spelix CV pipeline, plus uplift branch coverage to 95% (backend) and 85% (frontend) across the rest of the codebase. Produce a portfolio-quality traceability matrix linking every compound boolean condition to the test vectors that demonstrate independent effect.

## Motivation

**Quality confidence:** The CV scoring pipeline (`scoring.py`, `quality_gates.py`, `rep_detection.py`, `confidence.py`) makes numerical decisions that directly affect user-facing coaching feedback. A wrong branch in `SafetyScore._score_deadlift` means incorrect movement quality scores. MC/DC ensures every boolean sub-condition independently affects outcomes — the strongest practical coverage criterion.

**Portfolio/demonstration:** MC/DC originates from DO-178C Level A (avionics safety-critical software). Demonstrating MC/DC methodology on a real CV pipeline — with truth tables, traceability, and independent effect proof — is a differentiator for AI lab internship applications. The traceability matrix is the artifact reviewers inspect.

## Architecture

**Hybrid approach:** Full MC/DC with truth tables on 16 critical functions (~82 compound conditions, ~280 test vectors). Standard branch coverage uplift for everything else. A standalone traceability matrix as the portfolio artifact.

**Artifact style:** Companion traceability matrix in `docs/mcdc/traceability.md` — not inline with tests. Test files stay clean; the matrix cross-references test functions by name. A methodology document in `docs/mcdc/methodology.md` explains MC/DC for reviewers unfamiliar with the concept.

---

## Section 1: MC/DC Test Architecture

### File structure

```
backend/tests/mcdc/                    # MC/DC test suite (separate from unit/)
  __init__.py
  conftest.py                          # Shared fixtures (ThresholdConfig, landmark factories)
  test_mcdc_scoring_safety.py          # SafetyScore truth tables (4 functions)
  test_mcdc_scoring_technique.py       # TechniqueScore truth tables (2 functions)
  test_mcdc_scoring_control.py         # ControlScore truth tables (1 function)
  test_mcdc_quality_gates.py           # Quality gate truth tables (5 functions)
  test_mcdc_rep_detection.py           # State machine truth tables (2 functions)
  test_mcdc_confidence.py              # Tier 4 phase adjustment (1 function)
  test_mcdc_pipeline_decisions.py      # Pipeline orchestration decisions (1 function)

docs/mcdc/                             # Portfolio artifacts
  methodology.md                       # MC/DC methodology explanation
  traceability.md                      # Master traceability matrix
```

### Test naming convention

Each test maps to a truth table row. Names encode the condition values and the expected independent effect:

```python
def test_safety_deadlift_hip_angle__TF__hip_below_min_only():
    """TT Row 2: A=hip<min(T), B=hip>max(F) → penalty applied (A independently flips)"""

def test_safety_deadlift_hip_angle__FT__hip_above_max_only():
    """TT Row 3: A=hip<min(F), B=hip>max(T) → penalty applied (B independently flips)"""

def test_safety_deadlift_hip_angle__FF__no_penalty():
    """TT Row 1: A=hip<min(F), B=hip>max(F) → no penalty (baseline)"""
```

Pattern: `test_{scorer}_{function}_{condition}__{TF_values}__{description}`

### MC/DC target functions (Tier 1)

**`backend/app/cv/scoring.py`** — 7 functions, ~35 compound conditions:

| # | Function | Key compound conditions |
|---|----------|------------------------|
| 1 | `SafetyScore.compute` | 3-way exercise dispatch + `confidence < 0.50` cap |
| 2 | `SafetyScore._score_squat` | None-guard + two-tier threshold (high/caution) + knee guard |
| 3 | `SafetyScore._score_deadlift` | `hip_angle < min_hip or hip_angle > max_hip` (OR) |
| 4 | `SafetyScore._score_bench` | `elbow < min or elbow > max` (OR) + shoulder threshold |
| 5 | `TechniqueScore.compute` | `depth_std is not None and depth_std > 10.0` (AND) |
| 6 | `TechniqueScore._score_bench` | `not (min <= angle <= max)` (negated chain) + two-tier flare |
| 7 | `ControlScore.compute` | Two-tier descent + exercise-conditional lockout chain |

**`backend/app/cv/quality_gates.py`** — 5 functions, ~25 compound conditions:

| # | Function | Key compound conditions |
|---|----------|------------------------|
| 8 | `check_video_file` | `returncode != 0 or not stdout.strip()` (OR) |
| 9 | `check_framing` | Visibility mask + aspect-conditional threshold + 3-way outcome |
| 10 | `check_single_person` | `left_vis < thresh or right_vis < thresh` (OR), `rejected_by_run or rejected_by_fraction` (OR) |
| 11 | `run_quality_gates` | `all(c.passed for c in checks if c.level == "error")` (compound generator) |
| 12 | `check_lighting` | Two-boundary brightness (min/max) |

**`backend/app/cv/rep_detection.py`** — 2 functions, ~12 compound conditions:

| # | Function | Key compound conditions |
|---|----------|------------------------|
| 13 | `_detect_reps_state_machine` | 4-state FSM with hysteresis thresholds + min-duration guard |
| 14 | `_detect_reps_peak_valley` | Boundary checks + min-duration filter |

**`backend/app/cv/confidence.py`** — 1 function, ~4 compound conditions:

| # | Function | Key compound conditions |
|---|----------|------------------------|
| 15 | `_tier4_phase_adjusted` | `frame_offset == 0 or frame_offset == count - 1` (OR) + proximity check |

**`backend/app/services/pipeline.py`** — 1 function, ~6 compound conditions:

| # | Function | Key compound conditions |
|---|----------|------------------------|
| 16 | `run_cv_pipeline` decisions | `confidence < threshold and client is not None` (AND), `detection_rate > 0.50`, degenerate guard |

---

## Section 2: Branch Coverage Uplift

### Backend: 90% → 95% branch coverage

**Configuration changes:**
- Add `[tool.coverage.run]` to `pyproject.toml`: `branch = true`
- Update CI: `--cov-branch --cov-fail-under=95` (from `--cov-fail-under=90`)

**Gap analysis process:**
1. Run `uv run pytest --cov=app --cov-branch --cov-report=html` locally
2. Identify uncovered branches in the HTML report
3. Write targeted tests for the biggest gaps (expected: service error paths, API auth guards, edge cases in PDF generation)

### Frontend: 66% → 85% branch coverage

**Configuration changes in `vitest.config.ts`:**
```typescript
thresholds: {
  branches: 85,   // from 66
  lines: 85,      // from 76
  functions: 80,  // from 66
  statements: 85, // from 73
}
```

**Focus areas:**
- `useAnalysisStatus.ts` — 10+ branches in the status state machine
- Component conditional renders (loading/error/empty states)
- Hook error and edge-case paths

No MC/DC on frontend — standard branch coverage only.

---

## Section 3: Portfolio Artifacts

### `docs/mcdc/methodology.md`

Structure:
1. **What is MC/DC** — Modified Condition/Decision Coverage definition, origin in DO-178C Level A, difference from statement/branch/condition coverage
2. **Why MC/DC for Spelix** — The CV scoring pipeline makes numerical decisions affecting user-facing coaching. Wrong branches = incorrect movement quality feedback.
3. **Scope** — 16 functions, ~82 compound conditions, ~280 test vectors. Why the rest uses branch coverage.
4. **How to read the traceability matrix** — Truth table format, row naming, test linking, independent effect demonstration

### `docs/mcdc/traceability.md`

**Header:**
```markdown
## Coverage Summary
- Functions under MC/DC: 16
- Compound conditions analyzed: 82
- MC/DC test vectors written: [exact count]
- All conditions show independent effect: ✅
- Branch coverage (backend): 95%+
- Branch coverage (frontend): 85%+
```

**Per-function entry format:**

```markdown
### SafetyScore._score_deadlift — scoring.py:172

**Expression (L214):** `hip_angle < min_hip or hip_angle > max_hip`

| Row | A: hip < min | B: hip > max | A or B | Independent Effect |
|-----|-------------|-------------|--------|-------------------|
| 1   | F           | F           | F      | baseline          |
| 2   | T           | F           | T      | A flips outcome   |
| 3   | F           | T           | T      | B flips outcome   |

| Row | Test |
|-----|------|
| 1   | `test_mcdc_scoring_safety::test_safety_deadlift_hip__FF__no_penalty` |
| 2   | `test_mcdc_scoring_safety::test_safety_deadlift_hip__TF__below_min` |
| 3   | `test_mcdc_scoring_safety::test_safety_deadlift_hip__FT__above_max` |

**MC/DC satisfied:** ✅ Rows {1,2} show A's independent effect. Rows {1,3} show B's independent effect.
```

---

## Section 4: Execution Order & CI Integration

### Phase ordering

| Phase | Description | Deliverables |
|-------|-------------|-------------|
| A | Infrastructure | `pyproject.toml` branch config, baseline coverage reports, `docs/mcdc/` directory |
| B | Backend branch uplift | Tests closing 90%→95% gap, CI gate raised |
| C | Frontend branch uplift | Tests closing 66%→85% gap, vitest thresholds raised |
| D | MC/DC tests | Truth tables + test vectors for all 16 functions, `traceability.md` built incrementally |
| E | Portfolio artifacts | `methodology.md`, traceability summary stats, final review |

### CI integration

- MC/DC tests in `backend/tests/mcdc/` run as part of normal `pytest` — no separate CI job
- Branch coverage enforced via `--cov-branch --cov-fail-under=95` (backend) and vitest thresholds (frontend)
- MC/DC coverage is NOT machine-enforced in CI (no Python MC/DC gating tool exists). Enforced by traceability matrix review.

### Maintenance rule

When a compound condition in a Tier 1 function changes, the traceability matrix entry and its MC/DC tests must be updated in the same PR. This rule will be documented in `backend/CLAUDE.md`.
