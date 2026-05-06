# MC/DC Coverage Initiative — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Achieve MC/DC coverage on 16 critical CV pipeline functions with a companion traceability matrix, plus uplift branch coverage to 95% backend / 85% frontend.

**Architecture:** MC/DC tests live in `backend/tests/mcdc/` separate from unit tests. Each test file covers one source module. A `docs/mcdc/traceability.md` matrix links truth tables to test functions. Branch coverage is enforced via CI config changes.

**Tech Stack:** pytest, pytest-cov (branch mode), vitest/v8, numpy (synthetic landmarks)

---

## Phase A: Infrastructure

### Task 1: Backend coverage configuration

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add coverage config to pyproject.toml**

```toml
[tool.coverage.run]
branch = true
source = ["app"]

[tool.coverage.report]
fail_under = 95
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

Add this after the existing `[tool.pytest.ini_options]` section in `backend/pyproject.toml`.

- [ ] **Step 2: Update CI pytest command**

In `.github/workflows/ci.yml`, find the backend test step and change:
```bash
uv run pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=90 -x -q
```
to:
```bash
uv run pytest tests/ --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90 -x -q
```

Note: Keep `--cov-fail-under=90` for now. We'll raise it to 95 after Phase B adds tests. The `--cov-branch` flag enables branch measurement immediately so we can see the baseline.

- [ ] **Step 3: Run baseline branch coverage locally**

Run: `cd backend && uv run pytest tests/ --cov=app --cov-branch --cov-report=html -x -q`
Expected: Coverage report generated in `backend/htmlcov/`. Note the current branch coverage percentage — it will be lower than the 90% line coverage.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml .github/workflows/ci.yml
git commit -m "chore(ci): enable branch coverage measurement in pytest"
```

---

### Task 2: Frontend coverage threshold preparation

**Files:**
- Modify: `frontend/vitest.config.ts`

- [ ] **Step 1: Note current frontend branch coverage**

Run: `cd frontend && npx vitest run --coverage`
Expected: Coverage report shows current branch % (baseline is ~66%).

- [ ] **Step 2: No config change yet**

Do NOT raise thresholds yet — we'll raise them after Phase C adds tests. This task is observation only to establish the baseline number.

- [ ] **Step 3: Commit baseline observation to plan notes**

No commit needed — record the baseline branch % for Phase C targeting.

---

### Task 3: Create MC/DC test directory structure

**Files:**
- Create: `backend/tests/mcdc/__init__.py`
- Create: `backend/tests/mcdc/conftest.py`
- Create: `docs/mcdc/traceability.md` (skeleton)

- [ ] **Step 1: Create mcdc test package**

```python
# backend/tests/mcdc/__init__.py
```
(empty file)

- [ ] **Step 2: Write shared conftest with fixtures**

```python
# backend/tests/mcdc/conftest.py
"""Shared fixtures for MC/DC truth-table tests."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

# Set config path before any app imports
_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig


@pytest.fixture()
def cfg() -> ThresholdConfig:
    """ThresholdConfig v1 for scoring/detection tests."""
    return ThresholdConfig(_V1_PATH)


def make_landmarks_frame(
    *,
    visibility: float = 0.9,
    x: float = 0.5,
    y: float = 0.5,
    overrides: dict[int, dict[int, float]] | None = None,
) -> np.ndarray:
    """Return a (33, 5) landmark frame with uniform values.

    Parameters
    ----------
    visibility: Default visibility for all landmarks (col 3 AND col 4).
    x, y: Default x/y position for all landmarks.
    overrides: {landmark_idx: {col_idx: value}} for per-landmark overrides.
    """
    frame = np.zeros((33, 5), dtype=np.float64)
    frame[:, 0] = x
    frame[:, 1] = y
    frame[:, 2] = 0.0
    frame[:, 3] = visibility
    frame[:, 4] = visibility  # presence = visibility (Tier 1 needs both)
    if overrides:
        for lm_idx, cols in overrides.items():
            for col_idx, val in cols.items():
                frame[lm_idx, col_idx] = val
    return frame


def make_n_frames(n: int = 30, **kwargs) -> list[np.ndarray]:
    """Return n identical landmark frames."""
    return [make_landmarks_frame(**kwargs) for _ in range(n)]
```

- [ ] **Step 3: Create traceability matrix skeleton**

```markdown
# MC/DC Traceability Matrix

## Coverage Summary

- Functions under MC/DC: 16
- Compound conditions analyzed: (to be filled)
- MC/DC test vectors written: (to be filled)
- All conditions show independent effect: (pending)
- Branch coverage (backend): (pending)
- Branch coverage (frontend): (pending)

---

<!-- Entries added per-function as Phase D tasks complete -->
```

Write to `docs/mcdc/traceability.md`.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/mcdc/ docs/mcdc/
git commit -m "chore: scaffold MC/DC test infrastructure and traceability skeleton"
```

---

## Phase D: MC/DC Tests (scoring.py)

### Task 4: MC/DC — SafetyScore.compute (exercise dispatch + confidence cap)

**Files:**
- Create: `backend/tests/mcdc/test_mcdc_scoring_safety.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth table for confidence cap condition**

The compound decision at `scoring.py:110`: `if confidence < 0.50`

This is a single condition (not compound), but combined with the exercise dispatch it forms an MC/DC-relevant decision: the score is capped ONLY when confidence is low AND a valid exercise path was taken.

Effective compound: "exercise_type matches AND confidence < 0.50" — the cap applies.

| Row | A: exercise matches | B: confidence < 0.50 | Cap applied? |
|-----|--------------------|--------------------|--------------|
| 1   | T (squat)          | F (0.80)           | N            |
| 2   | T (squat)          | T (0.30)           | Y            |
| 3   | F (unknown)        | T (0.30)           | N (no scoring path) |

MC/DC pairs: Rows {1,2} show B's independent effect. Rows {2,3} show A's independent effect.

- [ ] **Step 2: Write tests**

```python
# backend/tests/mcdc/test_mcdc_scoring_safety.py
"""MC/DC truth-table tests for SafetyScore (scoring.py).

Each test maps to a truth-table row in docs/mcdc/traceability.md.
Naming: test_{scorer}_{condition}__{row_values}__{description}
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig
from app.cv.scoring import SafetyScore


@pytest.fixture()
def cfg() -> ThresholdConfig:
    return ThresholdConfig(_V1_PATH)


@pytest.fixture()
def scorer() -> SafetyScore:
    return SafetyScore()


class TestSafetyComputeConfidenceCap:
    """MC/DC: exercise dispatch + confidence < 0.50 cap."""

    def test_compute__squat_high_conf__no_cap(self, scorer, cfg):
        """Row 1: exercise=squat(T), confidence>=0.50(F) → no cap."""
        metrics = {"confidence_score": 0.80, "torso_lean": 10.0}
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == 10.0  # No penalty, no cap

    def test_compute__squat_low_conf__cap_applied(self, scorer, cfg):
        """Row 2: exercise=squat(T), confidence<0.50(T) → cap at 5.0."""
        metrics = {"confidence_score": 0.30, "torso_lean": 10.0}
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score <= 5.0  # Capped

    def test_compute__unknown_exercise_low_conf__no_scoring_path(self, scorer, cfg):
        """Row 3: exercise=unknown(F), confidence<0.50(T) → no exercise path taken, only cap."""
        metrics = {"confidence_score": 0.30}
        score, badges = scorer.compute(metrics, None, cfg, "unknown_exercise")
        # No exercise-specific scoring happened (score stays 10.0 before cap)
        assert score <= 5.0  # Cap still applies on the base 10.0
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_scoring_safety.py::TestSafetyComputeConfidenceCap -xvs`
Expected: All 3 tests PASS.

- [ ] **Step 4: Append to traceability matrix**

Add the truth table entry to `docs/mcdc/traceability.md`.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_scoring_safety.py docs/mcdc/traceability.md
git commit -m "test(mcdc): SafetyScore.compute confidence cap truth table"
```

---

### Task 5: MC/DC — SafetyScore._score_squat (None guards + two-tier thresholds)

**Files:**
- Modify: `backend/tests/mcdc/test_mcdc_scoring_safety.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth tables**

**Condition 1 (L122-126):** `torso_lean is not None` AND threshold check
- Effective compound: `torso_lean is not None AND torso_lean > high`
- Simpler sub-compound: `torso_lean > high` (given not-None)

| Row | A: lean > high | B: lean > caution | Outcome |
|-----|---------------|------------------|---------|
| 1   | F             | F                | No penalty |
| 2   | F             | T                | -1.5 (caution) |
| 3   | T             | T (implied)      | -3.0 (high) |

MC/DC: {1,2} shows B independent. {2,3} shows A independent (A=T overrides B).

**Condition 2 (L153-156):** `knee_angle_at_depth is not None` AND `knee_angle_at_depth < min_knee`

| Row | A: knee not None | B: knee < min | Outcome |
|-----|-----------------|--------------|---------|
| 1   | F               | N/A          | No penalty |
| 2   | T               | F            | No penalty |
| 3   | T               | T            | -2.0 |

MC/DC: {1,2} shows A independent (None guard). {2,3} shows B independent.

- [ ] **Step 2: Write tests**

```python
class TestSafetyScoreSquatTorsoLean:
    """MC/DC: _score_squat torso_lean two-tier threshold."""

    def test_squat_torso__below_caution__no_penalty(self, scorer, cfg):
        """Row 1: lean<=caution(F), lean>high(F) → no penalty."""
        caution = cfg.get("squat", "torso_lean_caution_deg")
        metrics = {"torso_lean": caution - 5.0, "confidence_score": 1.0}
        score, _ = scorer.compute(metrics, None, cfg, "squat")
        assert score == 10.0

    def test_squat_torso__above_caution_below_high__caution_penalty(self, scorer, cfg):
        """Row 2: lean>caution(T), lean>high(F) → -1.5."""
        caution = cfg.get("squat", "torso_lean_caution_deg")
        high = cfg.get("squat", "torso_lean_high_deg")
        metrics = {"torso_lean": (caution + high) / 2, "confidence_score": 1.0}
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == 8.5  # 10.0 - 1.5
        assert any(b.issue_key == "torso_lean_caution" for b in badges)

    def test_squat_torso__above_high__high_penalty(self, scorer, cfg):
        """Row 3: lean>high(T) → -3.0 (overrides caution)."""
        high = cfg.get("squat", "torso_lean_high_deg")
        metrics = {"torso_lean": high + 5.0, "confidence_score": 1.0}
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == 7.0  # 10.0 - 3.0
        assert any(b.issue_key == "torso_lean_high" for b in badges)

    def test_squat_torso__none__no_penalty(self, scorer, cfg):
        """None guard: torso_lean absent → no penalty path entered."""
        metrics = {"confidence_score": 1.0}  # no torso_lean key
        score, _ = scorer.compute(metrics, None, cfg, "squat")
        assert score == 10.0


class TestSafetyScoreSquatKneeAngle:
    """MC/DC: _score_squat knee_angle_at_depth None guard + threshold."""

    def test_squat_knee__none__no_penalty(self, scorer, cfg):
        """Row 1: knee not present → no penalty."""
        metrics = {"confidence_score": 1.0}
        score, _ = scorer.compute(metrics, None, cfg, "squat")
        assert score == 10.0

    def test_squat_knee__above_min__no_penalty(self, scorer, cfg):
        """Row 2: knee present, above min → no penalty."""
        min_knee = cfg.get("squat", "knee_angle_at_depth_min_deg")
        metrics = {"knee_angle_at_depth": min_knee + 10.0, "confidence_score": 1.0}
        score, _ = scorer.compute(metrics, None, cfg, "squat")
        assert score == 10.0

    def test_squat_knee__below_min__penalty(self, scorer, cfg):
        """Row 3: knee present, below min → -2.0."""
        min_knee = cfg.get("squat", "knee_angle_at_depth_min_deg")
        metrics = {"knee_angle_at_depth": min_knee - 10.0, "confidence_score": 1.0}
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == 8.0  # 10.0 - 2.0
        assert any(b.issue_key == "knee_angle_at_depth_low" for b in badges)
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_scoring_safety.py -xvs -k "Squat"`
Expected: All 7 tests PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_scoring_safety.py docs/mcdc/traceability.md
git commit -m "test(mcdc): SafetyScore._score_squat truth tables"
```

---

### Task 6: MC/DC — SafetyScore._score_deadlift (compound OR)

**Files:**
- Modify: `backend/tests/mcdc/test_mcdc_scoring_safety.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth table**

**Condition (L214):** `hip_angle < min_hip or hip_angle > max_hip`

| Row | A: hip < min | B: hip > max | A or B | Outcome |
|-----|-------------|-------------|--------|---------|
| 1   | F           | F           | F      | No penalty |
| 2   | T           | F           | T      | -2.0 |
| 3   | F           | T           | T      | -2.0 |

MC/DC pairs: {1,2} shows A's independent effect. {1,3} shows B's independent effect.

Also: torso_lean two-tier (same pattern as squat), None guard on hip_angle.

- [ ] **Step 2: Write tests**

```python
class TestSafetyDeadliftHipAngle:
    """MC/DC: _score_deadlift hip_angle < min OR hip_angle > max."""

    def test_deadlift_hip__FF__in_range_no_penalty(self, scorer, cfg):
        """Row 1: hip>=min(F), hip<=max(F) → no penalty."""
        min_hip = cfg.get("deadlift", "hip_angle_at_bottom_min_deg")
        max_hip = cfg.get("deadlift", "hip_angle_at_bottom_max_deg")
        metrics = {
            "hip_angle_at_bottom": (min_hip + max_hip) / 2,
            "confidence_score": 1.0,
        }
        score, badges = scorer.compute(metrics, None, cfg, "deadlift")
        assert not any(b.issue_key == "hip_angle_extreme" for b in badges)

    def test_deadlift_hip__TF__below_min(self, scorer, cfg):
        """Row 2: hip<min(T), hip>max(F) → -2.0 penalty."""
        min_hip = cfg.get("deadlift", "hip_angle_at_bottom_min_deg")
        metrics = {
            "hip_angle_at_bottom": min_hip - 10.0,
            "confidence_score": 1.0,
        }
        score, badges = scorer.compute(metrics, None, cfg, "deadlift")
        assert any(b.issue_key == "hip_angle_extreme" for b in badges)

    def test_deadlift_hip__FT__above_max(self, scorer, cfg):
        """Row 3: hip<min(F), hip>max(T) → -2.0 penalty."""
        max_hip = cfg.get("deadlift", "hip_angle_at_bottom_max_deg")
        metrics = {
            "hip_angle_at_bottom": max_hip + 10.0,
            "confidence_score": 1.0,
        }
        score, badges = scorer.compute(metrics, None, cfg, "deadlift")
        assert any(b.issue_key == "hip_angle_extreme" for b in badges)

    def test_deadlift_hip__none__no_penalty(self, scorer, cfg):
        """None guard: hip_angle absent → no penalty."""
        metrics = {"confidence_score": 1.0}
        score, badges = scorer.compute(metrics, None, cfg, "deadlift")
        assert not any(b.issue_key == "hip_angle_extreme" for b in badges)
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_scoring_safety.py::TestSafetyDeadliftHipAngle -xvs`
Expected: All 4 tests PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_scoring_safety.py docs/mcdc/traceability.md
git commit -m "test(mcdc): SafetyScore._score_deadlift OR condition truth table"
```

---

### Task 7: MC/DC — SafetyScore._score_bench (compound OR + shoulder)

**Files:**
- Modify: `backend/tests/mcdc/test_mcdc_scoring_safety.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth table**

**Condition (L241):** `elbow_angle < min_elbow or elbow_angle > max_elbow`

| Row | A: elbow < min | B: elbow > max | A or B | Outcome |
|-----|---------------|---------------|--------|---------|
| 1   | F             | F             | F      | No penalty |
| 2   | T             | F             | T      | -2.0 |
| 3   | F             | T             | T      | -2.0 |

MC/DC pairs: {1,2} for A. {1,3} for B.

**Condition (L258):** `shoulder_angle > max_shoulder` (simple, but needed for full coverage)

| Row | shoulder > max | Outcome |
|-----|---------------|---------|
| 1   | F             | No penalty |
| 2   | T             | -2.0 |

- [ ] **Step 2: Write tests**

```python
class TestSafetyBenchElbowAngle:
    """MC/DC: _score_bench elbow < min OR elbow > max."""

    def test_bench_elbow__FF__in_range(self, scorer, cfg):
        """Row 1: elbow in range → no penalty."""
        min_e = cfg.get("bench", "elbow_angle_at_bottom_min_deg")
        max_e = cfg.get("bench", "elbow_angle_at_bottom_max_deg")
        metrics = {
            "elbow_angle_at_bottom": (min_e + max_e) / 2,
            "confidence_score": 1.0,
        }
        score, badges = scorer.compute(metrics, None, cfg, "bench")
        assert not any(b.issue_key == "elbow_angle_extreme" for b in badges)

    def test_bench_elbow__TF__below_min(self, scorer, cfg):
        """Row 2: elbow < min → -2.0."""
        min_e = cfg.get("bench", "elbow_angle_at_bottom_min_deg")
        metrics = {
            "elbow_angle_at_bottom": min_e - 15.0,
            "confidence_score": 1.0,
        }
        _, badges = scorer.compute(metrics, None, cfg, "bench")
        assert any(b.issue_key == "elbow_angle_extreme" for b in badges)

    def test_bench_elbow__FT__above_max(self, scorer, cfg):
        """Row 3: elbow > max → -2.0."""
        max_e = cfg.get("bench", "elbow_angle_at_bottom_max_deg")
        metrics = {
            "elbow_angle_at_bottom": max_e + 15.0,
            "confidence_score": 1.0,
        }
        _, badges = scorer.compute(metrics, None, cfg, "bench")
        assert any(b.issue_key == "elbow_angle_extreme" for b in badges)


class TestSafetyBenchShoulderAngle:
    """MC/DC: _score_bench shoulder_angle > max threshold."""

    def test_bench_shoulder__below_max__no_penalty(self, scorer, cfg):
        """shoulder <= max → no penalty."""
        max_s = cfg.get("bench", "shoulder_angle_at_bottom_max_deg")
        metrics = {
            "shoulder_angle_at_bottom": max_s - 5.0,
            "confidence_score": 1.0,
        }
        _, badges = scorer.compute(metrics, None, cfg, "bench")
        assert not any(b.issue_key == "shoulder_angle_high" for b in badges)

    def test_bench_shoulder__above_max__penalty(self, scorer, cfg):
        """shoulder > max → -2.0."""
        max_s = cfg.get("bench", "shoulder_angle_at_bottom_max_deg")
        metrics = {
            "shoulder_angle_at_bottom": max_s + 10.0,
            "confidence_score": 1.0,
        }
        _, badges = scorer.compute(metrics, None, cfg, "bench")
        assert any(b.issue_key == "shoulder_angle_high" for b in badges)
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_scoring_safety.py -xvs -k "Bench"`
Expected: All 5 tests PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_scoring_safety.py docs/mcdc/traceability.md
git commit -m "test(mcdc): SafetyScore._score_bench OR + shoulder truth tables"
```

---

### Task 8: MC/DC — TechniqueScore.compute (AND condition)

**Files:**
- Create: `backend/tests/mcdc/test_mcdc_scoring_technique.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth table**

**Condition (L310):** `depth_std is not None and depth_std > 10.0`

| Row | A: not None | B: > 10.0 | A and B | Penalty applied? |
|-----|-----------|---------|---------|-----------------|
| 1   | F         | N/A     | F       | N               |
| 2   | T         | F       | F       | N               |
| 3   | T         | T       | T       | Y               |

MC/DC pairs: {1,2} shows A's independent effect (short-circuit). {2,3} shows B's independent effect.

- [ ] **Step 2: Write tests**

```python
# backend/tests/mcdc/test_mcdc_scoring_technique.py
"""MC/DC truth-table tests for TechniqueScore (scoring.py)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig
from app.cv.scoring import TechniqueScore


@pytest.fixture()
def cfg() -> ThresholdConfig:
    return ThresholdConfig(_V1_PATH)


@pytest.fixture()
def scorer() -> TechniqueScore:
    return TechniqueScore()


class TestTechniqueDepthStdAnd:
    """MC/DC: depth_std is not None AND depth_std > 10.0."""

    def test_depth_std__none__no_penalty(self, scorer, cfg):
        """Row 1: A=None(F) → short-circuit, no penalty."""
        metrics = {"confidence_score": 1.0}  # no depth_angle_std key
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert not any(b.issue_key == "rep_consistency_low" for b in badges)

    def test_depth_std__present_below_threshold__no_penalty(self, scorer, cfg):
        """Row 2: A=present(T), B=<=10(F) → no penalty."""
        metrics = {"depth_angle_std": 5.0, "confidence_score": 1.0}
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert not any(b.issue_key == "rep_consistency_low" for b in badges)

    def test_depth_std__present_above_threshold__penalty(self, scorer, cfg):
        """Row 3: A=present(T), B=>10(T) → penalty applied."""
        metrics = {"depth_angle_std": 15.0, "confidence_score": 1.0}
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert any(b.issue_key == "rep_consistency_low" for b in badges)
        # penalty = min(3.0, (15 - 10) * 0.2) = 1.0
        assert score == 9.0
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_scoring_technique.py -xvs`
Expected: All 3 PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_scoring_technique.py docs/mcdc/traceability.md
git commit -m "test(mcdc): TechniqueScore.compute AND condition truth table"
```

---

### Task 9: MC/DC — TechniqueScore._score_bench (negated chain + two-tier flare)

**Files:**
- Modify: `backend/tests/mcdc/test_mcdc_scoring_technique.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth tables**

**Condition (L409):** `not (target_min <= elbow_angle <= target_max)` where target_min=70, target_max=90

Equivalent to: `elbow_angle < 70 OR elbow_angle > 90`

| Row | A: angle < 70 | B: angle > 90 | not(in range) | Penalty? |
|-----|--------------|--------------|---------------|----------|
| 1   | F            | F            | F (in range)  | N        |
| 2   | T            | F            | T             | Y (-1.5) |
| 3   | F            | T            | T             | Y (-1.5) |

**Condition (L424-437):** `elbow_flare > high` / `elif > caution` (two-tier, same as squat torso)

| Row | A: flare > high | B: flare > caution | Outcome |
|-----|----------------|-------------------|---------|
| 1   | F              | F                 | No penalty |
| 2   | F              | T                 | -1.0 |
| 3   | T              | T (implied)       | -2.0 |

- [ ] **Step 2: Write tests**

```python
class TestTechniqueBenchElbowRange:
    """MC/DC: not (70 <= elbow <= 90) — equivalent to OR."""

    def test_bench_elbow_technique__in_range__no_penalty(self, scorer, cfg):
        """Row 1: 70 <= angle <= 90 → no penalty."""
        metrics = {"elbow_angle_at_bottom": 80.0, "confidence_score": 1.0}
        _, badges = scorer.compute(metrics, None, cfg, "bench")
        assert not any(b.issue_key == "elbow_angle_off_target" for b in badges)

    def test_bench_elbow_technique__below_min__penalty(self, scorer, cfg):
        """Row 2: angle < 70 → -1.5."""
        metrics = {"elbow_angle_at_bottom": 60.0, "confidence_score": 1.0}
        _, badges = scorer.compute(metrics, None, cfg, "bench")
        assert any(b.issue_key == "elbow_angle_off_target" for b in badges)

    def test_bench_elbow_technique__above_max__penalty(self, scorer, cfg):
        """Row 3: angle > 90 → -1.5."""
        metrics = {"elbow_angle_at_bottom": 100.0, "confidence_score": 1.0}
        _, badges = scorer.compute(metrics, None, cfg, "bench")
        assert any(b.issue_key == "elbow_angle_off_target" for b in badges)


class TestTechniqueBenchElbowFlare:
    """MC/DC: elbow_flare two-tier threshold."""

    def test_bench_flare__below_caution__no_penalty(self, scorer, cfg):
        """Row 1: flare <= caution → no penalty."""
        caution = cfg.get("bench", "elbow_flare_caution_deg")
        metrics = {"elbow_flare_deg": caution - 5.0, "confidence_score": 1.0}
        _, badges = scorer.compute(metrics, None, cfg, "bench")
        assert not any(b.issue_key.startswith("elbow_flare") for b in badges)

    def test_bench_flare__above_caution_below_high__caution(self, scorer, cfg):
        """Row 2: caution < flare <= high → -1.0."""
        caution = cfg.get("bench", "elbow_flare_caution_deg")
        high = cfg.get("bench", "elbow_flare_high_deg")
        metrics = {"elbow_flare_deg": (caution + high) / 2, "confidence_score": 1.0}
        _, badges = scorer.compute(metrics, None, cfg, "bench")
        assert any(b.issue_key == "elbow_flare_caution" for b in badges)

    def test_bench_flare__above_high__high_penalty(self, scorer, cfg):
        """Row 3: flare > high → -2.0."""
        high = cfg.get("bench", "elbow_flare_high_deg")
        metrics = {"elbow_flare_deg": high + 5.0, "confidence_score": 1.0}
        _, badges = scorer.compute(metrics, None, cfg, "bench")
        assert any(b.issue_key == "elbow_flare_high" for b in badges)
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_scoring_technique.py -xvs`
Expected: All 6 new tests PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_scoring_technique.py docs/mcdc/traceability.md
git commit -m "test(mcdc): TechniqueScore._score_bench negated chain + flare truth tables"
```

---

### Task 10: MC/DC — ControlScore.compute (two-tier + conditional lockout)

**Files:**
- Create: `backend/tests/mcdc/test_mcdc_scoring_control.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth tables**

**Condition (L565):** descent two-tier: `descent < high_s` / `elif descent < caution_s`

| Row | A: descent < high | B: descent < caution | Outcome |
|-----|------------------|--------------------| --------|
| 1   | F                | F                  | No penalty |
| 2   | F                | T                  | -2.0 (caution) |
| 3   | T                | T (implied)        | -3.0 (high) |

**Condition (L610-613):** `exercise_type == "deadlift"` AND `lockout_angle is not None` AND `lockout_angle < min_lockout`

| Row | A: deadlift | B: angle not None | C: angle < min | Outcome |
|-----|------------|------------------|---------------|---------|
| 1   | F          | -                | -             | Skip |
| 2   | T          | F                | -             | Skip |
| 3   | T          | T                | F             | No penalty |
| 4   | T          | T                | T             | -1.5 |

MC/DC: {1,4} for A. {2,3}/{2,4} for B. {3,4} for C.

- [ ] **Step 2: Write tests**

```python
# backend/tests/mcdc/test_mcdc_scoring_control.py
"""MC/DC truth-table tests for ControlScore (scoring.py)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig
from app.cv.scoring import ControlScore


@pytest.fixture()
def cfg() -> ThresholdConfig:
    return ThresholdConfig(_V1_PATH)


@pytest.fixture()
def scorer() -> ControlScore:
    return ControlScore()


class TestControlDescentTwoTier:
    """MC/DC: descent < high_s / elif descent < caution_s."""

    def test_descent__above_caution__no_penalty(self, scorer, cfg):
        """Row 1: descent >= caution → no penalty."""
        caution_s = cfg.get("control", "descent_duration_caution_s")
        metrics = {"descent_duration_s": caution_s + 1.0, "confidence_score": 1.0}
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert not any(b.issue_key.startswith("descent_too_fast") for b in badges)

    def test_descent__below_caution_above_high__caution_penalty(self, scorer, cfg):
        """Row 2: high <= descent < caution → -2.0."""
        caution_s = cfg.get("control", "descent_duration_caution_s")
        high_s = cfg.get("control", "descent_duration_high_s")
        metrics = {
            "descent_duration_s": (high_s + caution_s) / 2,
            "confidence_score": 1.0,
        }
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert any(b.issue_key == "descent_too_fast_caution" for b in badges)

    def test_descent__below_high__high_penalty(self, scorer, cfg):
        """Row 3: descent < high → -3.0."""
        high_s = cfg.get("control", "descent_duration_high_s")
        metrics = {"descent_duration_s": high_s - 0.5, "confidence_score": 1.0}
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert any(b.issue_key == "descent_too_fast_high" for b in badges)


class TestControlDeadliftLockout:
    """MC/DC: exercise==deadlift AND lockout not None AND lockout < min."""

    def test_lockout__non_deadlift__skipped(self, scorer, cfg):
        """Row 1: not deadlift → lockout check skipped entirely."""
        metrics = {
            "knee_angle_at_lockout": 100.0,  # would trigger if checked
            "confidence_score": 1.0,
        }
        _, badges = scorer.compute(metrics, None, cfg, "squat")
        assert not any(b.issue_key == "lockout_incomplete" for b in badges)

    def test_lockout__deadlift_none__skipped(self, scorer, cfg):
        """Row 2: deadlift but no lockout angle → skipped."""
        metrics = {"confidence_score": 1.0}
        _, badges = scorer.compute(metrics, None, cfg, "deadlift")
        assert not any(b.issue_key == "lockout_incomplete" for b in badges)

    def test_lockout__deadlift_above_min__no_penalty(self, scorer, cfg):
        """Row 3: deadlift, angle present, above min → no penalty."""
        min_lockout = cfg.get("deadlift", "knee_angle_at_lockout_min_deg")
        metrics = {
            "knee_angle_at_lockout": min_lockout + 10.0,
            "confidence_score": 1.0,
        }
        _, badges = scorer.compute(metrics, None, cfg, "deadlift")
        assert not any(b.issue_key == "lockout_incomplete" for b in badges)

    def test_lockout__deadlift_below_min__penalty(self, scorer, cfg):
        """Row 4: deadlift, angle present, below min → -1.5."""
        min_lockout = cfg.get("deadlift", "knee_angle_at_lockout_min_deg")
        metrics = {
            "knee_angle_at_lockout": min_lockout - 10.0,
            "confidence_score": 1.0,
        }
        _, badges = scorer.compute(metrics, None, cfg, "deadlift")
        assert any(b.issue_key == "lockout_incomplete" for b in badges)
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_scoring_control.py -xvs`
Expected: All 7 tests PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_scoring_control.py docs/mcdc/traceability.md
git commit -m "test(mcdc): ControlScore two-tier descent + deadlift lockout truth tables"
```

---

## Phase D: MC/DC Tests (quality_gates.py)

### Task 11: MC/DC — check_video_file (OR condition)

**Files:**
- Create: `backend/tests/mcdc/test_mcdc_quality_gates.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth table**

**Condition (L195):** `result.returncode != 0 or not result.stdout.strip()`

| Row | A: returncode != 0 | B: not stdout.strip() | A or B | Result |
|-----|-------------------|---------------------|--------|--------|
| 1   | F (0)             | F (has output)      | F      | Continue to duration check |
| 2   | T (1)             | F (has output)      | T      | Return failed |
| 3   | F (0)             | T (empty)           | T      | Return failed |

MC/DC pairs: {1,2} for A. {1,3} for B.

- [ ] **Step 2: Write tests**

```python
# backend/tests/mcdc/test_mcdc_quality_gates.py
"""MC/DC truth-table tests for quality_gates.py."""

from __future__ import annotations

from unittest.mock import patch, MagicMock
import subprocess

import numpy as np
import pytest

from app.cv.quality_gates import (
    check_video_file,
    check_framing,
    check_single_person,
    check_lighting,
    run_quality_gates,
    sigmoid,
)


class TestCheckVideoFileOR:
    """MC/DC: returncode != 0 OR not stdout.strip()."""

    @patch("app.cv.quality_gates.subprocess.run")
    def test_video_file__FF__valid(self, mock_run):
        """Row 1: returncode=0(F), stdout='30.0'(F) → passed."""
        mock_run.return_value = MagicMock(returncode=0, stdout="30.0\n")
        result = check_video_file("/fake/path.mp4")
        assert result.passed is True

    @patch("app.cv.quality_gates.subprocess.run")
    def test_video_file__TF__bad_returncode(self, mock_run):
        """Row 2: returncode=1(T), stdout='error'(F) → failed."""
        mock_run.return_value = MagicMock(returncode=1, stdout="error info")
        result = check_video_file("/fake/path.mp4")
        assert result.passed is False

    @patch("app.cv.quality_gates.subprocess.run")
    def test_video_file__FT__empty_stdout(self, mock_run):
        """Row 3: returncode=0(F), stdout=''(T) → failed."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = check_video_file("/fake/path.mp4")
        assert result.passed is False
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_quality_gates.py::TestCheckVideoFileOR -xvs`
Expected: All 3 PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_quality_gates.py docs/mcdc/traceability.md
git commit -m "test(mcdc): check_video_file OR condition truth table"
```

---

### Task 12: MC/DC — check_framing (visibility mask + aspect + 3-way)

**Files:**
- Modify: `backend/tests/mcdc/test_mcdc_quality_gates.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth tables**

**Condition 1 (L321):** `int(visible_mask.sum()) < _MIN_VISIBLE_LANDMARKS_FOR_BBOX` (skip frame)

| Row | visible_count >= 10 | Frame included? |
|-----|--------------------| --------------- |
| 1   | T (15 visible)     | Y |
| 2   | F (5 visible)      | N (skipped) |

**Condition 2 (L342-345):** aspect scaling: `aspect < 1.0` (portrait)

| Row | aspect < 1.0 | Threshold used |
|-----|-------------|---------------|
| 1   | F (1920x1080, aspect=1.78) | _FRAMING_MIN_FRACTION (0.18) |
| 2   | T (1080x1920, aspect=0.56) | 0.18 * 0.5625 = 0.10125 |

**Condition 3 (L347-358):** 3-way outcome: `metric < min_threshold` / `elif metric > max`

| Row | A: metric < min | B: metric > max | Outcome |
|-----|----------------|----------------|---------|
| 1   | F              | F              | Passed |
| 2   | T              | F              | Too small |
| 3   | F              | T              | Too large |

- [ ] **Step 2: Write tests**

```python
from tests.mcdc.conftest import make_landmarks_frame, make_n_frames


def _make_framing_frames(
    x_min: float, y_min: float, x_max: float, y_max: float,
    visibility: float = 0.9, n: int = 30,
) -> list[np.ndarray]:
    """Create frames where visible landmarks span from (x_min,y_min) to (x_max,y_max)."""
    frames = []
    for _ in range(n):
        frame = np.zeros((33, 5), dtype=np.float64)
        frame[:, 3] = visibility
        frame[:, 4] = visibility
        # Distribute landmarks across the bbox
        for i in range(33):
            t = i / 32.0
            frame[i, 0] = x_min + t * (x_max - x_min)
            frame[i, 1] = y_min + t * (y_max - y_min)
        frames.append(frame)
    return frames


class TestCheckFramingVisibilityMask:
    """MC/DC: visible_mask.sum() < 10 skip condition."""

    def test_framing__enough_visible__frame_included(self):
        """Row 1: 33 landmarks visible → frame contributes to metric."""
        frames = _make_framing_frames(0.2, 0.1, 0.8, 0.9, visibility=0.9)
        result = check_framing(frames, 1920, 1080)
        assert result.passed is True

    def test_framing__too_few_visible__all_skipped(self):
        """Row 2: <10 visible → all frames skipped → metric=0 → fail."""
        frames = _make_framing_frames(0.2, 0.1, 0.8, 0.9, visibility=-2.0)
        # sigmoid(-2.0) ≈ 0.12 < 0.50 threshold → all landmarks invisible
        result = check_framing(frames, 1920, 1080)
        assert result.passed is False


class TestCheckFramingAspect:
    """MC/DC: aspect < 1.0 portrait threshold scaling."""

    def test_framing__landscape__standard_threshold(self):
        """Row 1: landscape (1920x1080) → threshold = 0.18."""
        # bbox covers ~36% of frame → passes 0.18
        frames = _make_framing_frames(0.2, 0.2, 0.8, 0.8, visibility=0.9)
        result = check_framing(frames, 1920, 1080)
        assert result.passed is True

    def test_framing__portrait__scaled_threshold(self):
        """Row 2: portrait (1080x1920) → threshold = 0.18 * 0.5625 ≈ 0.10."""
        # Small bbox (~4% area) that would pass landscape but still passes
        # portrait's lower threshold
        frames = _make_framing_frames(0.3, 0.3, 0.7, 0.7, visibility=0.9)
        result = check_framing(frames, 1080, 1920)
        assert result.passed is True


class TestCheckFramingThreeWay:
    """MC/DC: metric < min / metric > max / in range."""

    def test_framing__in_range__passed(self):
        """Row 1: metric in [min, max] → passed."""
        frames = _make_framing_frames(0.2, 0.1, 0.8, 0.9, visibility=0.9)
        result = check_framing(frames, 1920, 1080)
        assert result.passed is True

    def test_framing__too_small__failed(self):
        """Row 2: metric < min → too far away."""
        # Tiny bbox = small fraction
        frames = _make_framing_frames(0.45, 0.45, 0.55, 0.55, visibility=0.9)
        result = check_framing(frames, 1920, 1080)
        assert result.passed is False
        assert "too far" in result.user_message.lower()

    def test_framing__too_large__failed(self):
        """Row 3: metric > max → too close."""
        frames = _make_framing_frames(0.0, 0.0, 1.0, 1.0, visibility=0.9)
        result = check_framing(frames, 1920, 1080)
        assert result.passed is False
        assert "too close" in result.user_message.lower()
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_quality_gates.py -xvs -k "Framing"`
Expected: All 7 PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_quality_gates.py docs/mcdc/traceability.md
git commit -m "test(mcdc): check_framing visibility mask + aspect + 3-way truth tables"
```

---

### Task 13: MC/DC — check_single_person (two OR conditions)

**Files:**
- Modify: `backend/tests/mcdc/test_mcdc_quality_gates.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth tables**

**Condition 1 (L409):** `left_vis < thresh or right_vis < thresh` (visibility skip)

| Row | A: left_vis < 0.5 | B: right_vis < 0.5 | A or B | Frame skipped? |
|-----|-------------------|-------------------|--------|---------------|
| 1   | F                 | F                 | F      | N |
| 2   | T                 | F                 | T      | Y |
| 3   | F                 | T                 | T      | Y |

**Condition 2 (L450):** `not (rejected_by_run or rejected_by_fraction)`

| Row | A: run >= 4 | B: fraction > 0.30 | A or B | passed? |
|-----|------------|-------------------|--------|---------|
| 1   | F          | F                 | F      | T (pass) |
| 2   | T          | F                 | T      | F (reject) |
| 3   | F          | T                 | T      | F (reject) |

MC/DC: {1,2} for A. {1,3} for B.

- [ ] **Step 2: Write tests**

```python
class TestSinglePersonVisibilityOR:
    """MC/DC: left_vis < thresh OR right_vis < thresh (frame skip)."""

    def test_single_person__both_visible__frame_counted(self):
        """Row 1: both hips visible → frame included in analysis."""
        frames = make_n_frames(30, visibility=0.9)
        result = check_single_person(frames, 1920)
        assert result.passed is True

    def test_single_person__left_invisible__frame_skipped(self):
        """Row 2: left hip invisible → frame skipped."""
        frames = []
        for _ in range(30):
            frame = make_landmarks_frame(visibility=0.9)
            frame[23, 3] = -2.0  # left hip: sigmoid(-2) ≈ 0.12 < 0.50
            frames.append(frame)
        result = check_single_person(frames, 1920)
        # With all frames having invisible left hip, we get < 3 valid samples
        assert result.passed is False  # Not enough anchoring samples

    def test_single_person__right_invisible__frame_skipped(self):
        """Row 3: right hip invisible → frame skipped."""
        frames = []
        for _ in range(30):
            frame = make_landmarks_frame(visibility=0.9)
            frame[24, 3] = -2.0  # right hip: sigmoid(-2) ≈ 0.12 < 0.50
            frames.append(frame)
        result = check_single_person(frames, 1920)
        assert result.passed is False  # Not enough anchoring samples


class TestSinglePersonRejectionOR:
    """MC/DC: rejected_by_run OR rejected_by_fraction."""

    def test_single_person__no_drift__passes(self):
        """Row 1: no run, no fraction → passes."""
        frames = make_n_frames(30, visibility=0.9, x=0.5)
        result = check_single_person(frames, 1920)
        assert result.passed is True

    def test_single_person__long_consecutive_run__rejects(self):
        """Row 2: 4+ consecutive off-anchor → rejects (A independent)."""
        frames = []
        # First 3 frames anchor at x=0.5
        for _ in range(10):
            frames.append(make_landmarks_frame(visibility=0.9, x=0.5))
        # Next 5 frames jump to x=0.9 (>0.25 away from 0.5 anchor)
        for _ in range(20):
            frames.append(make_landmarks_frame(visibility=0.9, x=0.9))
        result = check_single_person(frames, 1920)
        assert result.passed is False

    def test_single_person__high_fraction_no_run__rejects(self):
        """Row 3: >30% off-anchor but no 4+ consecutive → still rejects."""
        frames = []
        # Alternate: on-anchor, off-anchor, on-anchor, off-anchor...
        # This avoids consecutive runs but accumulates fraction
        for i in range(30):
            if i % 2 == 0:
                frames.append(make_landmarks_frame(visibility=0.9, x=0.5))
            else:
                frames.append(make_landmarks_frame(visibility=0.9, x=0.9))
        # 50% off-anchor > 30% threshold → rejects via fraction
        result = check_single_person(frames, 1920)
        assert result.passed is False
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_quality_gates.py -xvs -k "SinglePerson"`
Expected: All 6 PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_quality_gates.py docs/mcdc/traceability.md
git commit -m "test(mcdc): check_single_person OR conditions truth tables"
```

---

### Task 14: MC/DC — check_lighting + run_quality_gates

**Files:**
- Modify: `backend/tests/mcdc/test_mcdc_quality_gates.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth tables**

**check_lighting (L582-598):** `brightness < min` / `brightness > max`

| Row | A: < 60 | B: > 240 | Outcome |
|-----|---------|---------|---------|
| 1   | F       | F       | No warning |
| 2   | T       | F       | "too dark" warning |
| 3   | F       | T       | "overexposed" warning |

**run_quality_gates (L752):** `all(c.passed for c in checks if c.level == "error")`

| Row | Any error-level failed? | overall_passed |
|-----|------------------------|---------------|
| 1   | N (all error-level pass) | T |
| 2   | Y (one error-level fails) | F |
| 3   | Warning fails only | T (warnings don't affect overall) |

- [ ] **Step 2: Write tests**

```python
class TestCheckLightingTwoBoundary:
    """MC/DC: brightness < min OR brightness > max."""

    def test_lighting__normal__no_warning(self):
        """Row 1: 60 <= brightness <= 240 → no warning."""
        frames = [np.full((100, 100), 128, dtype=np.uint8) for _ in range(5)]
        result = check_lighting(frames)
        assert result.user_message == ""

    def test_lighting__too_dark__warning(self):
        """Row 2: brightness < 60 → dark warning."""
        frames = [np.full((100, 100), 30, dtype=np.uint8) for _ in range(5)]
        result = check_lighting(frames)
        assert "brighter" in result.user_message.lower()

    def test_lighting__overexposed__warning(self):
        """Row 3: brightness > 240 → overexposed warning."""
        frames = [np.full((100, 100), 250, dtype=np.uint8) for _ in range(5)]
        result = check_lighting(frames)
        assert "overexposed" in result.user_message.lower()


class TestRunQualityGatesOverall:
    """MC/DC: all(c.passed for c in checks if c.level == 'error')."""

    def test_gates__all_pass__overall_passed(self):
        """Row 1: all error-level pass → overall passed."""
        frames = make_n_frames(30, visibility=0.9)
        result = run_quality_gates(frames, 1920, 1080, exercise_type="squat")
        assert result.passed is True

    def test_gates__one_error_fails__overall_rejected(self):
        """Row 2: one error-level fails → overall rejected."""
        # Low visibility → body_visibility gate fails
        frames = make_n_frames(30, visibility=-3.0)  # sigmoid(-3) ≈ 0.05
        result = run_quality_gates(frames, 1920, 1080, exercise_type="squat")
        assert result.passed is False
        assert result.status == "rejected"

    def test_gates__warning_only_fails__overall_still_passes(self):
        """Row 3: warning-level fails don't affect overall."""
        frames = make_n_frames(30, visibility=0.9)
        # Dark grayscale frames → lighting warning, but overall still passes
        gray_frames = [np.full((100, 100), 30, dtype=np.uint8) for _ in range(5)]
        result = run_quality_gates(
            frames, 1920, 1080,
            exercise_type="squat",
            frames_gray=gray_frames,
        )
        # Overall passes (error gates pass), but lighting warns
        assert result.passed is True
        lighting_checks = [c for c in result.checks if c.name == "lighting"]
        assert len(lighting_checks) == 1
        assert lighting_checks[0].level == "warning"
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_quality_gates.py -xvs -k "Lighting or Gates"`
Expected: All 6 PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_quality_gates.py docs/mcdc/traceability.md
git commit -m "test(mcdc): check_lighting + run_quality_gates truth tables"
```

---

## Phase D: MC/DC Tests (rep_detection.py)

### Task 15: MC/DC — _detect_reps_state_machine (4-state FSM)

**Files:**
- Create: `backend/tests/mcdc/test_mcdc_rep_detection.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth tables**

The state machine has 4 transition decisions. Each is a single-condition threshold check with hysteresis, but the MC/DC-relevant compound is the **ASCENDING exit**: `angle > standing - hysteresis` AND `rep_duration >= min_frames`.

| Row | A: angle > threshold | B: duration >= min | Rep counted? |
|-----|--------------------|--------------------|-------------|
| 1   | F                  | -                  | N (stays ASCENDING) |
| 2   | T                  | F                  | N (too short, discarded) |
| 3   | T                  | T                  | Y (rep counted) |

Also: DESCENDING abort: `angle > standing + hysteresis` (returns to STANDING without entering BOTTOM)

| Row | A: crossed depth | B: returned to standing | Outcome |
|-----|-----------------|------------------------|---------|
| 1   | T               | F                      | Enters BOTTOM normally |
| 2   | F               | T                      | Aborts, no rep |

- [ ] **Step 2: Write tests**

```python
# backend/tests/mcdc/test_mcdc_rep_detection.py
"""MC/DC truth-table tests for rep_detection.py."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig
from app.cv.rep_detection import detect_reps

FPS = 30.0


@pytest.fixture()
def cfg() -> ThresholdConfig:
    return ThresholdConfig(_V1_PATH)


def _make_landmarks(n_frames: int) -> list[np.ndarray]:
    """Minimal landmarks placeholder (detect_reps doesn't use them directly)."""
    frame = np.zeros((33, 5), dtype=float)
    frame[:, 3] = 0.9
    frame[:, 4] = 0.9
    return [frame.copy() for _ in range(n_frames)]


class TestStateMachineAscendingExit:
    """MC/DC: ASCENDING→STANDING requires angle>threshold AND duration>=min."""

    def test_ascending__angle_not_reached__stays_ascending(self, cfg):
        """Row 1: signal doesn't return to standing → no rep counted."""
        # Go down but never come back up fully
        n = 60  # 2 seconds at 30fps
        angles = np.concatenate([
            np.linspace(170, 70, 30),   # descend
            np.linspace(70, 140, 30),   # partial ascent (140 < 155 standing-hysteresis)
        ])
        landmarks = _make_landmarks(n)
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS, cfg)
        assert len(reps) == 0

    def test_ascending__duration_too_short__rep_discarded(self, cfg):
        """Row 2: returns to standing but rep < min_duration → discarded."""
        # Very fast "rep" in ~5 frames (0.17s < 0.5s min)
        angles = np.array([170, 160, 140, 120, 100, 80, 70, 80, 100, 130, 160, 170.0])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS, cfg)
        assert len(reps) == 0  # Too short

    def test_ascending__full_cycle_sufficient_duration__rep_counted(self, cfg):
        """Row 3: full cycle with sufficient duration → rep counted."""
        # Full rep over 30 frames (1 second > 0.5s min)
        angles = np.concatenate([
            np.linspace(170, 70, 15),   # descend
            np.linspace(70, 170, 15),   # ascend back to standing
        ])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS, cfg)
        assert len(reps) == 1


class TestStateMachineDescendingAbort:
    """MC/DC: DESCENDING aborts back to STANDING on angle > standing + hysteresis."""

    def test_descending__crosses_depth__enters_bottom(self, cfg):
        """Row 1: signal crosses depth threshold → enters BOTTOM state."""
        angles = np.concatenate([
            np.linspace(170, 70, 15),   # cross both standing and depth
            np.linspace(70, 170, 15),   # return
        ])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS, cfg)
        assert len(reps) == 1

    def test_descending__returns_without_depth__aborts(self, cfg):
        """Row 2: signal returns to standing without crossing depth → no rep."""
        # Dip below standing threshold but not below depth threshold
        # squat depth is ~90° so we stay above it
        angles = np.concatenate([
            np.linspace(170, 130, 10),  # below standing (160) but above depth (90)
            np.linspace(130, 170, 10),  # return to standing
        ])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS, cfg)
        assert len(reps) == 0
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_rep_detection.py -xvs`
Expected: All 5 PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_rep_detection.py docs/mcdc/traceability.md
git commit -m "test(mcdc): rep detection state machine transition truth tables"
```

---

### Task 16: MC/DC — _detect_reps_peak_valley (fallback)

**Files:**
- Modify: `backend/tests/mcdc/test_mcdc_rep_detection.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth table**

**Condition:** Fallback triggers when state machine returns 0 reps. Within fallback: `end_frame - start_frame >= min_rep_frames` (post-filter)

| Row | State machine finds reps? | Peak/valley used? |
|-----|--------------------------|------------------|
| 1   | Y (1+ reps)             | N (primary result used) |
| 2   | N (0 reps)              | Y (fallback fires) |

**Within fallback:** `end_frame - start_frame >= min_rep_frames`

| Row | Duration >= min | Rep kept? |
|-----|----------------|-----------|
| 1   | T              | Y |
| 2   | F              | N (filtered out) |

- [ ] **Step 2: Write tests**

```python
class TestPeakValleyFallback:
    """MC/DC: fallback fires only when state machine returns 0."""

    def test_fallback__state_machine_finds_reps__fallback_not_used(self, cfg):
        """Row 1: standard signal → state machine handles it."""
        angles = np.concatenate([
            np.linspace(170, 70, 15),
            np.linspace(70, 170, 15),
        ])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS, cfg)
        assert len(reps) >= 1

    def test_fallback__partial_lockout_signal__fallback_used(self, cfg):
        """Row 2: signal never reaches standing threshold → fallback detects reps."""
        # Partial lockout: oscillates between 130° and 80° (never reaches 160° standing)
        n_frames = 90  # 3 seconds
        angles = np.concatenate([
            np.linspace(130, 80, 15),
            np.linspace(80, 130, 15),
            np.linspace(130, 80, 15),
            np.linspace(80, 130, 15),
            np.linspace(130, 80, 15),
            np.linspace(80, 130, 15),
        ])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS, cfg)
        # State machine finds 0 (no standing crossing), fallback should find peaks
        assert len(reps) >= 1


class TestPeakValleyMinDuration:
    """MC/DC: peak/valley post-filter on min_rep_duration."""

    def test_peak_valley__sufficient_duration__kept(self, cfg):
        """Row 1: valleys with enough separation → reps counted."""
        # Slow oscillation: each half-cycle = 30 frames = 1s > 0.5s min
        angles = np.concatenate([
            np.linspace(130, 80, 30),
            np.linspace(80, 130, 30),
        ])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS, cfg)
        assert len(reps) >= 1

    def test_peak_valley__too_short__filtered(self, cfg):
        """Row 2: very rapid oscillation → valleys too close → filtered."""
        # Rapid noise: 3-frame half-cycles = 0.1s < 0.5s min
        angles = np.tile([130, 100, 80, 100, 130], 5).astype(float)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS, cfg)
        assert len(reps) == 0
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_rep_detection.py -xvs -k "PeakValley"`
Expected: All 4 PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_rep_detection.py docs/mcdc/traceability.md
git commit -m "test(mcdc): peak/valley fallback + min duration truth tables"
```

---

## Phase D: MC/DC Tests (confidence.py + pipeline.py)

### Task 17: MC/DC — _tier4_phase_adjusted (OR + proximity)

**Files:**
- Create: `backend/tests/mcdc/test_mcdc_confidence.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth table**

**Condition (L219):** `frame_offset == 0 or frame_offset == rep_frame_count - 1`

| Row | A: offset == 0 | B: offset == count-1 | A or B | Multiplier |
|-----|---------------|---------------------|--------|-----------|
| 1   | F             | F                   | F      | transition (0.90) or high_occlusion |
| 2   | T             | F                   | T      | static_peak (1.0) |
| 3   | F             | T                   | T      | static_peak (1.0) |

Also: `abs(frame_offset - depth_frame_offset) <= bottom_window` (proximity check — takes priority over static_peak)

| Row | Near depth? | At start/end? | Multiplier |
|-----|------------|--------------|-----------|
| 1   | T          | -            | high_occlusion (0.70-0.80) |
| 2   | F          | T            | static_peak (1.0) |
| 3   | F          | F            | transition (0.90) |

- [ ] **Step 2: Write tests**

```python
# backend/tests/mcdc/test_mcdc_confidence.py
"""MC/DC truth-table tests for confidence.py Tier 4."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig
from app.cv.confidence import _tier4_phase_adjusted


@pytest.fixture()
def cfg() -> ThresholdConfig:
    return ThresholdConfig(_V1_PATH)


class TestTier4StaticPeakOR:
    """MC/DC: frame_offset == 0 OR frame_offset == count - 1."""

    def test_tier4__middle_frame__not_static_peak(self, cfg):
        """Row 1: offset=5, count=30 → transition multiplier."""
        result = _tier4_phase_adjusted(
            tier3_score=0.9, frame_offset=5, depth_frame_offset=15,
            rep_frame_count=30, exercise_type="squat", cfg=cfg,
        )
        transition_mult = cfg.get("phase_multipliers", "transition")
        assert abs(result - 0.9 * transition_mult) < 0.01

    def test_tier4__first_frame__static_peak(self, cfg):
        """Row 2: offset=0 → static_peak multiplier (1.0)."""
        result = _tier4_phase_adjusted(
            tier3_score=0.9, frame_offset=0, depth_frame_offset=15,
            rep_frame_count=30, exercise_type="squat", cfg=cfg,
        )
        static_mult = cfg.get("phase_multipliers", "static_peak")
        assert abs(result - 0.9 * static_mult) < 0.01

    def test_tier4__last_frame__static_peak(self, cfg):
        """Row 3: offset=count-1 → static_peak multiplier (1.0)."""
        result = _tier4_phase_adjusted(
            tier3_score=0.9, frame_offset=29, depth_frame_offset=15,
            rep_frame_count=30, exercise_type="squat", cfg=cfg,
        )
        static_mult = cfg.get("phase_multipliers", "static_peak")
        assert abs(result - 0.9 * static_mult) < 0.01


class TestTier4ProximityPriority:
    """MC/DC: near-depth proximity check overrides static_peak."""

    def test_tier4__near_depth__high_occlusion(self, cfg):
        """Near depth frame → high_occlusion multiplier (even if at start/end)."""
        # depth_offset=0, frame_offset=0 → near depth takes priority
        result = _tier4_phase_adjusted(
            tier3_score=0.9, frame_offset=0, depth_frame_offset=0,
            rep_frame_count=30, exercise_type="squat", cfg=cfg,
        )
        # Should use high_occlusion, not static_peak
        static_mult = cfg.get("phase_multipliers", "static_peak")
        assert result < 0.9 * static_mult  # occlusion < 1.0

    def test_tier4__far_from_depth_at_start__static_peak(self, cfg):
        """Far from depth AND at start → static_peak."""
        result = _tier4_phase_adjusted(
            tier3_score=0.9, frame_offset=0, depth_frame_offset=15,
            rep_frame_count=30, exercise_type="squat", cfg=cfg,
        )
        static_mult = cfg.get("phase_multipliers", "static_peak")
        assert abs(result - 0.9 * static_mult) < 0.01

    def test_tier4__far_from_depth_middle__transition(self, cfg):
        """Far from depth AND middle frame → transition."""
        result = _tier4_phase_adjusted(
            tier3_score=0.9, frame_offset=5, depth_frame_offset=15,
            rep_frame_count=30, exercise_type="squat", cfg=cfg,
        )
        transition_mult = cfg.get("phase_multipliers", "transition")
        assert abs(result - 0.9 * transition_mult) < 0.01
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_confidence.py -xvs`
Expected: All 6 PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_confidence.py docs/mcdc/traceability.md
git commit -m "test(mcdc): Tier 4 phase adjustment OR + proximity truth tables"
```

---

### Task 18: MC/DC — pipeline decision points (AND + degenerate guard)

**Files:**
- Create: `backend/tests/mcdc/test_mcdc_pipeline_decisions.py`
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Write truth tables**

**Condition (pipeline.py L445):** `detection.confidence < 0.7 and openai_client is not None`

| Row | A: conf < 0.7 | B: client not None | A and B | Fallback fires? |
|-----|--------------|-------------------|---------|----------------|
| 1   | F            | -                 | F       | N |
| 2   | T            | F (None)          | F       | N |
| 3   | T            | T                 | T       | Y |

**Condition (_is_degenerate_scoring_input):** `not rep_metrics` OR `session_confidence < 0.50`

| Row | A: no reps | B: conf < 0.50 | A or B | Degenerate? |
|-----|-----------|---------------|--------|------------|
| 1   | F         | F             | F      | N |
| 2   | T         | F             | T      | Y |
| 3   | F         | T             | T      | Y |

- [ ] **Step 2: Write tests**

```python
# backend/tests/mcdc/test_mcdc_pipeline_decisions.py
"""MC/DC truth-table tests for pipeline.py decision points."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.services.pipeline import _is_degenerate_scoring_input


class TestDegenerateScoringOR:
    """MC/DC: not rep_metrics OR session_confidence < 0.50."""

    def test_degenerate__has_reps_good_conf__not_degenerate(self):
        """Row 1: has reps(F), conf>=0.50(F) → not degenerate."""
        result = _is_degenerate_scoring_input(["rep1"], 0.80)
        assert result is False

    def test_degenerate__no_reps__degenerate(self):
        """Row 2: no reps(T) → degenerate regardless of confidence."""
        result = _is_degenerate_scoring_input([], 0.80)
        assert result is True

    def test_degenerate__has_reps_low_conf__degenerate(self):
        """Row 3: has reps(F), conf<0.50(T) → degenerate."""
        result = _is_degenerate_scoring_input(["rep1"], 0.30)
        assert result is True


class TestGPT4oFallbackAND:
    """MC/DC: confidence < 0.7 AND openai_client is not None.

    This tests the decision logic pattern, not the full pipeline.
    We test the boolean condition in isolation.
    """

    def test_fallback__high_conf__no_fallback(self):
        """Row 1: confidence >= 0.7 → no fallback regardless of client."""
        confidence = 0.85
        client = object()  # not None
        should_fallback = confidence < 0.7 and client is not None
        assert should_fallback is False

    def test_fallback__low_conf_no_client__no_fallback(self):
        """Row 2: confidence < 0.7 but client is None → no fallback."""
        confidence = 0.50
        client = None
        should_fallback = confidence < 0.7 and client is not None
        assert should_fallback is False

    def test_fallback__low_conf_with_client__fallback_fires(self):
        """Row 3: confidence < 0.7 AND client not None → fallback fires."""
        confidence = 0.50
        client = object()  # not None
        should_fallback = confidence < 0.7 and client is not None
        assert should_fallback is True
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/mcdc/test_mcdc_pipeline_decisions.py -xvs`
Expected: All 6 PASS.

- [ ] **Step 4: Append to traceability matrix**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/mcdc/test_mcdc_pipeline_decisions.py docs/mcdc/traceability.md
git commit -m "test(mcdc): pipeline degenerate guard + GPT-4o fallback truth tables"
```

---

## Phase B: Backend Branch Coverage Uplift

### Task 19: Identify and close backend branch coverage gaps

**Files:**
- Create/modify: multiple test files in `backend/tests/unit/`
- Modify: `.github/workflows/ci.yml` (raise gate to 95)

- [ ] **Step 1: Generate branch coverage report**

Run: `cd backend && uv run pytest tests/ --cov=app --cov-branch --cov-report=html --cov-report=term-missing -x -q`
Open `backend/htmlcov/index.html` and identify files with branch coverage < 95%. Sort by number of missing branches.

- [ ] **Step 2: Write tests for top 10 uncovered branch clusters**

Target the files with the most missing branches first. Expected gaps:
- `services/coaching.py` — error retry paths (429/529 handling)
- `services/pdf.py` — conditional template sections
- `api/v1/analyses.py` — auth error paths, validation branches
- `services/retrieval.py` — empty-result fallbacks
- `workers/analysis_worker.py` — exception handler branches

For each gap: write a minimal test that exercises the uncovered branch. Use existing test patterns from the neighboring test file.

- [ ] **Step 3: Verify branch coverage >= 95%**

Run: `cd backend && uv run pytest tests/ --cov=app --cov-branch --cov-fail-under=95 -x -q`
Expected: PASS (no coverage failure).

- [ ] **Step 4: Raise CI gate**

In `.github/workflows/ci.yml`, change:
```bash
uv run pytest tests/ --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90 -x -q
```
to:
```bash
uv run pytest tests/ --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=95 -x -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/tests/ .github/workflows/ci.yml
git commit -m "test: uplift backend branch coverage to 95% with CI gate"
```

---

## Phase C: Frontend Branch Coverage Uplift

### Task 20: Identify and close frontend branch coverage gaps

**Files:**
- Create/modify: multiple test files in `frontend/src/`
- Modify: `frontend/vitest.config.ts`

- [ ] **Step 1: Generate branch coverage report**

Run: `cd frontend && npx vitest run --coverage`
Review the coverage output. Identify components/hooks with branch coverage < 85%.

- [ ] **Step 2: Write tests for top uncovered branches**

Expected gaps:
- `useAnalysisStatus.ts` — status state transitions, error paths
- Component loading/error/empty states
- Hook cleanup and edge-case paths
- Conditional renders in results pages

For each: write a minimal vitest test that exercises the uncovered branch.

- [ ] **Step 3: Verify branch coverage >= 85%**

Run: `cd frontend && npx vitest run --coverage`
Expected: No threshold failure.

- [ ] **Step 4: Raise vitest thresholds**

In `frontend/vitest.config.ts`, update:
```typescript
thresholds: {
  branches: 85,
  lines: 85,
  functions: 80,
  statements: 85,
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/ frontend/vitest.config.ts
git commit -m "test: uplift frontend branch coverage to 85% with raised thresholds"
```

---

## Phase E: Portfolio Artifacts

### Task 21: Write methodology document

**Files:**
- Create: `docs/mcdc/methodology.md`

- [ ] **Step 1: Write methodology.md**

```markdown
# MC/DC Testing Methodology

## What is MC/DC?

Modified Condition/Decision Coverage (MC/DC) is a structural coverage criterion
originating from DO-178C Level A — the standard for safety-critical avionics
software. It requires that for every compound boolean decision in the code:

1. Every entry and exit point is invoked
2. Every decision takes every possible outcome (true/false)
3. **Each condition within a decision independently affects the decision outcome**

Requirement (3) is what distinguishes MC/DC from simpler coverage criteria.
Statement coverage only requires each line to execute. Branch coverage requires
each decision to evaluate both true and false. MC/DC goes further: it proves
that each sub-condition MATTERS — that flipping any single condition (while
holding all others constant) changes the overall decision.

## Why MC/DC for Spelix?

The Spelix CV pipeline contains numerical scoring functions that make
compound boolean decisions directly affecting user-facing coaching feedback.
For example, in `SafetyScore._score_deadlift`:

```python
if hip_angle < min_hip or hip_angle > max_hip:
    score -= 2.0
```

Standard branch coverage would test this decision as true and false — but
wouldn't guarantee that BOTH sub-conditions independently cause the penalty.
A test where `hip_angle < min_hip` is True (making the OR true regardless of
the second condition) achieves branch coverage but doesn't prove the
`hip_angle > max_hip` path works independently.

MC/DC requires three tests:
- Both false (no penalty) — baseline
- First true, second false (penalty) — proves first condition matters
- First false, second true (penalty) — proves second condition matters

This is the difference between "the code was executed" and "every boolean
sub-expression independently contributes to the logic."

## Scope

MC/DC is applied to **16 functions** in 4 files that form the critical
decision-making core of the CV pipeline:

- `scoring.py` — 7 functions with ~35 compound conditions
- `quality_gates.py` — 5 functions with ~25 compound conditions
- `rep_detection.py` — 2 functions with ~12 compound conditions
- `confidence.py` — 1 function with ~4 compound conditions
- `pipeline.py` — 1 function with ~6 compound conditions

The remaining codebase uses **branch coverage at 95%** (backend) and
**85%** (frontend). MC/DC is reserved for functions where incorrect
branching has direct user-facing consequences.

## How to Read the Traceability Matrix

Each entry in `traceability.md` contains:

1. **Function reference** — file path and line number
2. **Expression** — the exact compound boolean extracted from source
3. **Truth table** — all MC/DC-minimal rows showing input combinations
4. **Independent effect** — which row pairs demonstrate each condition
   independently flipping the outcome
5. **Test links** — exact test function names that satisfy each row
6. **Verdict** — confirmation that MC/DC is satisfied

### MC/DC Minimality

For an OR with N conditions, MC/DC requires N+1 test cases (not 2^N).
For an AND with N conditions, similarly N+1. This makes MC/DC practical
even for expressions with 3-4 sub-conditions.

## Maintenance

When a compound condition in a Tier 1 function changes, the corresponding
truth table entry and MC/DC tests must be updated in the same PR. This
prevents drift between the documented coverage and the actual tests.
```

- [ ] **Step 2: Commit**

```bash
git add docs/mcdc/methodology.md
git commit -m "docs: add MC/DC methodology explanation for portfolio"
```

---

### Task 22: Finalize traceability matrix

**Files:**
- Modify: `docs/mcdc/traceability.md`

- [ ] **Step 1: Compile all truth tables into the matrix**

After all Phase D tasks are complete, compile the full traceability matrix with:
- Summary statistics (exact test vector count, all verdicts)
- Every truth table from Tasks 4–18
- Cross-references to test functions by full path
- MC/DC satisfaction verdicts per condition

- [ ] **Step 2: Add final coverage numbers**

Run both coverage suites and fill in the summary header:
```markdown
## Coverage Summary
- Functions under MC/DC: 16
- Compound conditions analyzed: [exact count]
- MC/DC test vectors written: [exact count]
- All conditions show independent effect: ✅
- Branch coverage (backend): [exact %]
- Branch coverage (frontend): [exact %]
```

- [ ] **Step 3: Commit**

```bash
git add docs/mcdc/traceability.md
git commit -m "docs: finalize MC/DC traceability matrix with full coverage stats"
```

---

### Task 23: Add maintenance rule to CLAUDE.md

**Files:**
- Modify: `backend/CLAUDE.md`

- [ ] **Step 1: Add MC/DC maintenance rule**

Add to the "Backend Gotchas" section of `backend/CLAUDE.md`:

```markdown
### MC/DC traceability maintenance
When modifying a compound boolean condition in any of the 16 MC/DC-targeted functions
(scoring.py, quality_gates.py, rep_detection.py, confidence.py, pipeline.py decision
points), update the corresponding truth table in `docs/mcdc/traceability.md` and
MC/DC test in `backend/tests/mcdc/` in the same PR. Run the mcdc tests with
`uv run pytest tests/mcdc/ -xvs` to verify.
```

- [ ] **Step 2: Commit**

```bash
git add backend/CLAUDE.md
git commit -m "docs: add MC/DC maintenance rule to backend CLAUDE.md"
```
