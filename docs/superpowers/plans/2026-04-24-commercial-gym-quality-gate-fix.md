# Commercial-Gym Quality Gate Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Project routing rule: this plan touches `backend/app/cv/`; per `CLAUDE.md` "Delegation Rules", execution is dispatched to the **`spelix-cv-engineer`** specialist agent.

**Goal:** Fix `single_person` and `framing` quality-gate false rejections on commercial-gym videos so the 3 atharva fixtures (squat 19.88 s, bench 22.69 s, deadlift 25.40 s) pass the gate without re-shoot or re-trim, unblocking the L2 private-beta launch on 2026-05-03.

**Architecture:** Three changes inside `backend/app/cv/quality_gates.py` only. (1) `check_single_person` switches from "any large hip jump" to anchor-based identity-jump detection with hip-visibility gating. (2) `check_framing` builds the bbox only from landmarks with `sigmoid(visibility) ≥ 0.5`, skipping samples with too few visible landmarks. (3) `_FRAMING_MIN_FRACTION` lowered from 0.30 to 0.20. No new dependencies, no MediaPipe pipeline changes, no migrations. Reference spec: `docs/superpowers/specs/2026-04-24-commercial-gym-quality-gate-design.md`.

**Tech Stack:** Python 3.12, NumPy, MediaPipe BlazePose Heavy (Tasks API, RunningMode.VIDEO, num_poses=1), pytest.

---

## File Structure

**Branch:** `fix/commercial-gym-quality-gate`

- **Modify:** `backend/app/cv/quality_gates.py` — both checks + constants block
- **Modify:** `backend/tests/unit/test_quality_gates.py` — rewrite `single_person` tests, extend `framing` tests
- **Create:** `backend/tests/integration/test_quality_gates_atharva_fixtures.py` — `@pytest.mark.slow` real-video integration test, gated behind a CLI marker
- **Modify:** `backend/CLAUDE.md` — update the "Quality gate predicate" gotcha block to describe the new anchor rule
- **Modify:** `decisions.md` — append ADR-QGATE-COMMERCIAL-GYM
- **Modify:** `backlog.md` — add a row under a new "Completed — L2 Sprint Day 17 — Commercial-gym quality gate fix" header at session close

---

## Task 1: Branch + read existing tests for `check_single_person`

**Files:**
- Branch: `fix/commercial-gym-quality-gate`
- Read: `backend/tests/unit/test_quality_gates.py` (entire `check_single_person` test section)

- [ ] **Step 1.1: Create branch from current main, include the spec + plan**

```bash
git checkout main
git pull
git checkout -b fix/commercial-gym-quality-gate
# Spec + plan are already on disk (created during the brainstorming session) but untracked.
# Stage and commit them as the branch's first commit.
git add docs/superpowers/specs/2026-04-24-commercial-gym-quality-gate-design.md \
        docs/superpowers/plans/2026-04-24-commercial-gym-quality-gate-fix.md
git commit -m "docs(plan): commercial-gym quality gate design + implementation plan"
```

- [ ] **Step 1.2: Read existing `check_single_person` tests**

Run: `grep -n "single_person" backend/tests/unit/test_quality_gates.py | head -40`

Expected: list of test function names + line numbers. Read each with `Read` tool to understand what behaviour they assert against the old `_HIP_JUMP_THRESHOLD = 0.15`, `_MAX_JUMP_COUNT = 2` rule. List which need to be deleted (assert old constants directly), updated (still relevant under new semantics), or kept (e.g., NO_POSE-skip behaviour).

- [ ] **Step 1.3: Read existing `check_framing` tests**

Run: `grep -n "check_framing\|test_framing\|test_check_framing" backend/tests/unit/test_quality_gates.py | head -30`

Expected: list of `framing` tests. Note which assert specific `metric_value` values that may shift after visibility gating, and which assert the `0.30` or `0.169` threshold directly (these need updating to `0.20` and `0.1125`).

- [ ] **Step 1.4: Commit branch checkpoint (no files changed yet, just branch creation)**

```bash
git status
```

Expected: clean. No commit yet — branch is ready, but no edits.

---

## Task 2: Add new constants for anchor algorithm

**Files:**
- Modify: `backend/app/cv/quality_gates.py:46-49` (constants block for the single_person gate)

- [ ] **Step 2.1: Read current constants block**

Read `backend/app/cv/quality_gates.py:30-66`.

Expected: confirm current values

```
_FRAMING_MIN_FRACTION: float = 0.30
_FRAMING_MAX_FRACTION: float = 0.80
_LANDMARK_VISIBLE_THRESHOLD: float = 0.50
...
_HIP_JUMP_THRESHOLD: float = 0.15
_HIP_LANDMARKS: list[int] = [23, 24]
_MAX_JUMP_COUNT: int = 2
...
_FRAMING_SAMPLE_COUNT: int = 30
_FRAMING_PERCENTILE: float = 90.0
_VISIBILITY_SAMPLE_COUNT: int = 20
_SINGLE_PERSON_SAMPLE_COUNT: int = 30
```

- [ ] **Step 2.2: Replace the single_person constants block**

In `backend/app/cv/quality_gates.py`, replace the three lines

```python
_HIP_JUMP_THRESHOLD: float = 0.15
_HIP_LANDMARKS: list[int] = [23, 24]  # left hip, right hip
_MAX_JUMP_COUNT: int = 2
```

with

```python
# single_person gate (FR-CVPL-06) — anchor-based identity-jump detection.
# See docs/superpowers/specs/2026-04-24-commercial-gym-quality-gate-design.md
# and ADR-QGATE-COMMERCIAL-GYM. Replaces the prior "any large hip jump = multiple
# people" rule, which produced false positives on commercial-gym videos where
# MediaPipe re-acquires onto a clearly-visible bystander during tracking-loss
# events.
_HIP_LANDMARKS: list[int] = [23, 24]  # left hip, right hip (MediaPipe BlazePose)
_ANCHOR_FROM_FIRST_N_SAMPLES: int = 3
_OFF_ANCHOR_DISTANCE_FRAC: float = 0.25
_MAX_CONSECUTIVE_OFF_ANCHOR: int = 4
_MAX_OFF_ANCHOR_FRACTION: float = 0.30
```

- [ ] **Step 2.3: Lower the framing minimum**

Change

```python
_FRAMING_MIN_FRACTION: float = 0.30
```

to

```python
# Calibrated 2026-04-24 against commercial-gym fixtures (atharva-{squat,bench,deadlift}).
# Was 0.30 (lab fixtures, ~1.5 m camera distance). Real users at 3-4 m fill ~12-20 % of
# portrait frame. See ADR-QGATE-COMMERCIAL-GYM.
_FRAMING_MIN_FRACTION: float = 0.20
```

- [ ] **Step 2.4: Add the framing visibility-gate constant**

After the `_FRAMING_MAX_FRACTION` line, add:

```python
# Minimum number of post-sigmoid-visibility >= 0.5 landmarks needed to compute a
# meaningful bbox. Below this, the sample is dropped (mirrors check_body_visibility's
# NO_POSE skip pattern). Out of 33 BlazePose landmarks.
_MIN_VISIBLE_LANDMARKS_FOR_BBOX: int = 10
```

- [ ] **Step 2.5: Verify the file still parses**

Run: `cd backend && uv run python -c "from app.cv.quality_gates import check_single_person, check_framing; print('ok')"`

Expected: `ok` — no `ImportError` or `NameError`. (`check_single_person` will still reference the old constants in its body until Task 3, but module-level should parse.)

- [ ] **Step 2.6: Commit**

```bash
git add backend/app/cv/quality_gates.py
git commit -m "refactor(cv): replace single_person constants with anchor-rule constants

Spec: docs/superpowers/specs/2026-04-24-commercial-gym-quality-gate-design.md.
Adds _ANCHOR_FROM_FIRST_N_SAMPLES, _OFF_ANCHOR_DISTANCE_FRAC,
_MAX_CONSECUTIVE_OFF_ANCHOR, _MAX_OFF_ANCHOR_FRACTION; lowers
_FRAMING_MIN_FRACTION 0.30 -> 0.20; adds _MIN_VISIBLE_LANDMARKS_FOR_BBOX."
```

---

## Task 3: Rewrite `check_single_person` with anchor algorithm (TDD)

**Files:**
- Test: `backend/tests/unit/test_quality_gates.py` (new + updated tests)
- Modify: `backend/app/cv/quality_gates.py:345-392`

- [ ] **Step 3.1: Write failing test 1 — anchor tolerates brief bystander pickup**

In `backend/tests/unit/test_quality_gates.py`, add to a new `class TestCheckSinglePersonAnchorRule:` section (or below existing single_person tests):

```python
import numpy as np
import pytest
from app.cv.quality_gates import check_single_person

# Visibility-raw values: any positive float passes sigmoid >= 0.5 (sigmoid(0)=0.5).
# We use 4.0 for "high vis" (sigmoid ~0.98) and -4.0 for "low vis" (sigmoid ~0.02).
_HIGH_VIS = 4.0
_LOW_VIS = -4.0
_FRAME_W = 1080
_FRAME_H = 1920


def _frame_with_hips(left_x: float, right_x: float, vis: float = _HIGH_VIS) -> np.ndarray:
    """Build a 33x5 BlazePose-shaped frame with controlled hip x and visibility."""
    frame = np.zeros((33, 5), dtype=np.float64)
    # Set non-zero y on every landmark so _is_no_pose_frame returns False
    # (sentinel = ALL x AND y are 0.0).
    frame[:, 1] = 0.5
    frame[:, 0] = 0.5  # default x for non-hip landmarks
    frame[23, 0] = left_x
    frame[23, 3] = vis
    frame[23, 4] = vis  # presence
    frame[24, 0] = right_x
    frame[24, 3] = vis
    frame[24, 4] = vis
    return frame


def test_check_single_person_anchor_tolerates_brief_bystander_pickup() -> None:
    # 30 samples: 27 anchored at hip x=0.5, 3 transient (idx 10,11,12) at x=0.85 (bystander),
    # then back to anchor. Should pass — not sustained, not >30% off-anchor.
    samples = []
    for i in range(30):
        if i in (10, 11, 12):
            samples.append(_frame_with_hips(0.83, 0.87))
        else:
            samples.append(_frame_with_hips(0.48, 0.52))
    result = check_single_person(samples, _FRAME_W)
    assert result.passed is True, f"Expected pass, got user_message={result.user_message!r}"
```

- [ ] **Step 3.2: Run test to verify it fails (current code uses old jump rule)**

```bash
cd backend && uv run pytest tests/unit/test_quality_gates.py::TestCheckSinglePersonAnchorRule::test_check_single_person_anchor_tolerates_brief_bystander_pickup -v
```

Expected: FAIL — current `check_single_person` will count >= 2 jumps for the 3 transient samples and reject. Confirm the failure shows `assert result.passed is True` failing.

- [ ] **Step 3.3: Implement the anchor algorithm**

Replace the body of `check_single_person` in `backend/app/cv/quality_gates.py:345-392` with:

```python
def check_single_person(
    landmarks_per_frame: list[np.ndarray],
    frame_width: int,
) -> GateCheckResult:
    """Reject when MediaPipe is tracking different people across the clip.

    Anchors on the lifter from the first 3 high-visibility samples (median hip
    midpoint x), then counts samples whose hip midpoint drifts >25 % of frame
    width from the anchor. Rejects if 4+ consecutive off-anchor samples or
    >=30 % of valid samples are off-anchor. Skips samples where either hip's
    post-sigmoid visibility is below ``_LANDMARK_VISIBLE_THRESHOLD`` — those
    are MediaPipe guesses on occluded frames and would otherwise dominate the
    decision (see ADR-QGATE-COMMERCIAL-GYM).
    """
    indices = _sample_indices(len(landmarks_per_frame), _SINGLE_PERSON_SAMPLE_COUNT)

    midpoints: list[float] = []
    for i in indices:
        frame = landmarks_per_frame[i]
        if _is_no_pose_frame(frame):
            continue
        left_vis = sigmoid(float(frame[_HIP_LANDMARKS[0], _COL_VISIBILITY]))
        right_vis = sigmoid(float(frame[_HIP_LANDMARKS[1], _COL_VISIBILITY]))
        if left_vis < _LANDMARK_VISIBLE_THRESHOLD or right_vis < _LANDMARK_VISIBLE_THRESHOLD:
            continue
        left_x = float(frame[_HIP_LANDMARKS[0], _COL_X])
        right_x = float(frame[_HIP_LANDMARKS[1], _COL_X])
        midpoints.append((left_x + right_x) / 2.0)

    # Need at least N samples to anchor reliably. Fewer = cannot distinguish
    # single-lifter-with-occlusion from genuinely-no-lifter.
    if len(midpoints) < _ANCHOR_FROM_FIRST_N_SAMPLES:
        return GateCheckResult(
            passed=False,
            name="single_person",
            level="error",
            metric_value=float(len(midpoints)),
            threshold=float(_ANCHOR_FROM_FIRST_N_SAMPLES),
            user_message=(
                "Could not consistently track a single lifter — try filming "
                "side-on with your full body in frame."
            ),
        )

    anchor = float(np.median(midpoints[:_ANCHOR_FROM_FIRST_N_SAMPLES]))

    off_anchor_flags = [
        abs(m - anchor) > _OFF_ANCHOR_DISTANCE_FRAC for m in midpoints
    ]

    # Longest consecutive run of off-anchor samples
    longest_run = 0
    current_run = 0
    for flag in off_anchor_flags:
        if flag:
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 0

    off_anchor_fraction = sum(off_anchor_flags) / len(off_anchor_flags)
    rejected_by_run = longest_run >= _MAX_CONSECUTIVE_OFF_ANCHOR
    rejected_by_fraction = off_anchor_fraction > _MAX_OFF_ANCHOR_FRACTION

    passed = not (rejected_by_run or rejected_by_fraction)

    # Report whichever metric drove the decision (or longest_run when passing
    # — gives the operator a sense of margin). Threshold reported is the run
    # threshold; the fraction threshold is informational and lives in the spec.
    return GateCheckResult(
        passed=passed,
        name="single_person",
        level="error",
        metric_value=float(longest_run),
        threshold=float(_MAX_CONSECUTIVE_OFF_ANCHOR),
        user_message=(
            ""
            if passed
            else (
                "Could not consistently track a single lifter — try filming "
                "side-on with your full body in frame."
            )
        ),
    )
```

- [ ] **Step 3.4: Re-run the failing test — must now pass**

```bash
cd backend && uv run pytest tests/unit/test_quality_gates.py::TestCheckSinglePersonAnchorRule::test_check_single_person_anchor_tolerates_brief_bystander_pickup -v
```

Expected: PASS.

- [ ] **Step 3.5: Add the remaining 4 anchor-rule tests**

Append to `class TestCheckSinglePersonAnchorRule`:

```python
def test_check_single_person_anchor_rejects_sustained_swap() -> None:
    # 30 samples: first 10 anchored at x=0.5, last 20 at x=0.85 (different person sustained).
    # Should fail — sustained off-anchor run + fraction > 30%.
    samples = []
    for i in range(30):
        if i < 10:
            samples.append(_frame_with_hips(0.48, 0.52))
        else:
            samples.append(_frame_with_hips(0.83, 0.87))
    result = check_single_person(samples, _FRAME_W)
    assert result.passed is False


def test_check_single_person_anchor_skips_low_visibility_hips() -> None:
    # 30 samples, even idx anchored high-vis, odd idx wild-x but low-vis (must be skipped).
    # Should pass — low-vis frames don't influence the decision.
    samples = []
    for i in range(30):
        if i % 2 == 0:
            samples.append(_frame_with_hips(0.48, 0.52, vis=_HIGH_VIS))
        else:
            samples.append(_frame_with_hips(0.05, 0.95, vis=_LOW_VIS))
    result = check_single_person(samples, _FRAME_W)
    assert result.passed is True


def test_check_single_person_rejects_when_too_few_high_vis_samples() -> None:
    # 30 samples, only 2 are high-vis. Cannot anchor — rejects with new message.
    samples = []
    for i in range(30):
        if i < 2:
            samples.append(_frame_with_hips(0.48, 0.52, vis=_HIGH_VIS))
        else:
            samples.append(_frame_with_hips(0.48, 0.52, vis=_LOW_VIS))
    result = check_single_person(samples, _FRAME_W)
    assert result.passed is False
    assert "track a single lifter" in result.user_message


def test_check_single_person_user_message_text() -> None:
    # Force a sustained-swap rejection and check the exact wording.
    samples = []
    for i in range(30):
        samples.append(_frame_with_hips(0.05 if i >= 10 else 0.50,
                                        0.10 if i >= 10 else 0.50))
    result = check_single_person(samples, _FRAME_W)
    assert result.passed is False
    expected = (
        "Could not consistently track a single lifter — try filming "
        "side-on with your full body in frame."
    )
    assert result.user_message == expected
```

- [ ] **Step 3.6: Run all 5 new anchor tests, confirm green**

```bash
cd backend && uv run pytest tests/unit/test_quality_gates.py::TestCheckSinglePersonAnchorRule -v
```

Expected: 5 passed.

- [ ] **Step 3.7: Run the FULL `test_quality_gates.py` to find tests that broke under the new rule**

```bash
cd backend && uv run pytest tests/unit/test_quality_gates.py -v 2>&1 | tail -60
```

Expected: existing single_person tests under the OLD rule fail. Capture failure list (test names) into a scratch buffer for Task 4. Do NOT delete tests yet — Task 4 handles them.

- [ ] **Step 3.8: Commit**

```bash
git add backend/app/cv/quality_gates.py backend/tests/unit/test_quality_gates.py
git commit -m "feat(cv): anchor-based identity-jump detection in check_single_person

Replaces the 'any large hip jump = multiple people' rule with a lifter-
anchor centroid established from the first 3 high-visibility samples; flags
samples >25% off-anchor; rejects only on sustained runs (>=4 consecutive)
or >30% off-anchor fraction. Skips low-hip-visibility samples (sigmoid <
0.5) — those are MediaPipe guesses on occluded frames.

User message updated from 'film alone' to 'track a single lifter' — the old
text was impossible advice for commercial-gym users.

Adds 5 new TestCheckSinglePersonAnchorRule tests. Existing single_person
tests under the old rule will be rewritten in the next commit."
```

---

## Task 4: Update old `check_single_person` tests to the new rule

**Files:**
- Modify: `backend/tests/unit/test_quality_gates.py` — rewrite/delete tests using `_HIP_JUMP_THRESHOLD`, `_MAX_JUMP_COUNT`, or the old user_message

- [ ] **Step 4.1: List the tests captured in Step 3.7**

For each failing test, decide:
- **Delete:** asserts the literal old constant or old message text and is fully superseded by the anchor tests in Task 3.
- **Rewrite:** the underlying behaviour intent (e.g., "rejects when there are clearly two different lifters", "passes for a single quiet stander") is still relevant — restate it under the new rule.

Keep this list in your working memory only — no separate scratch file. The commit message in Step 4.4 records the migration.

- [ ] **Step 4.2: Delete or rewrite each test**

For each test in the list, edit `backend/tests/unit/test_quality_gates.py`. After each edit run

```bash
cd backend && uv run pytest tests/unit/test_quality_gates.py -v -k single_person 2>&1 | tail -30
```

to verify no regressions. Iterate until all `single_person` tests are green.

- [ ] **Step 4.3: Run the full unit suite to confirm no collateral damage**

```bash
cd backend && uv run pytest tests/unit/test_quality_gates.py -v 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 4.4: Commit**

```bash
git add backend/tests/unit/test_quality_gates.py
git commit -m "test(cv): migrate single_person tests to anchor rule

Removes asserts on retired _HIP_JUMP_THRESHOLD/_MAX_JUMP_COUNT and the old
'film alone' user message. Behaviour-intent tests rewritten under anchor
semantics. Per-test deletion/rewrite reasoning recorded inline in the test
docstrings."
```

---

## Task 5: Visibility-gated bbox in `check_framing` (TDD)

**Files:**
- Test: `backend/tests/unit/test_quality_gates.py`
- Modify: `backend/app/cv/quality_gates.py:275-337`

- [ ] **Step 5.1: Write failing test — visibility-gated bbox**

Append to `backend/tests/unit/test_quality_gates.py`:

```python
class TestCheckFramingVisibilityGate:
    """Bbox in check_framing should only consider landmarks with
    sigmoid(visibility) >= 0.5. Hallucinated low-confidence landmarks
    clustered near the body centre would otherwise shrink the bbox and
    cause false-negative framing rejections."""

    def _make_frame(self, visible_xs, low_vis_xs) -> np.ndarray:
        """Frame where `visible_xs` landmarks span the full frame at high vis,
        and `low_vis_xs` landmarks cluster at centre with low vis."""
        frame = np.zeros((33, 5), dtype=np.float64)
        # Ensure no NO_POSE sentinel: y always 0.5.
        frame[:, 1] = 0.5
        for slot, x in enumerate(visible_xs):
            frame[slot, 0] = x
            frame[slot, 1] = 0.05 + (slot % 10) * 0.09  # spread y
            frame[slot, 3] = 4.0  # high vis
            frame[slot, 4] = 4.0
        n_high = len(visible_xs)
        for slot, x in enumerate(low_vis_xs):
            frame[n_high + slot, 0] = x  # all clustered at center
            frame[n_high + slot, 1] = 0.5
            frame[n_high + slot, 3] = -4.0  # low vis
            frame[n_high + slot, 4] = -4.0
        return frame

    def test_bbox_uses_only_visible_landmarks(self) -> None:
        from app.cv.quality_gates import check_framing
        # 23 high-vis landmarks spanning x=[0.10, 0.90] (bbox_w = 0.80),
        # 10 low-vis landmarks all at x=0.50 (would shrink bbox if counted).
        # y-extent set wide for both groups so bbox_h is constant.
        visible_xs = list(np.linspace(0.10, 0.90, 23))
        low_vis_xs = [0.50] * 10
        frame = self._make_frame(visible_xs, low_vis_xs)
        # Override the y for low_vis to be at center too — simulating cluster.
        # (already 0.5 by default in helper.)
        samples = [frame] * 30
        result = check_framing(samples, frame_width=1080, frame_height=1920)
        # 0.20 * 0.5625 = 0.1125 portrait floor.
        # Expected metric: bbox of visible landmarks ~ 0.80 width
        # × actual y span. y was set across slots, so bbox y-span is ~0.85.
        # Visible-only bbox area >> 0.1125, must pass.
        assert result.passed is True, (
            f"metric={result.metric_value:.4f} threshold={result.threshold:.4f} "
            f"msg={result.user_message!r}"
        )

    def test_skip_samples_with_too_few_visible_landmarks(self) -> None:
        from app.cv.quality_gates import check_framing
        # 5 high-vis, 28 low-vis — below _MIN_VISIBLE_LANDMARKS_FOR_BBOX (10).
        # All samples skipped, framing rejects with metric_value=0.0.
        visible_xs = list(np.linspace(0.10, 0.90, 5))
        low_vis_xs = [0.50] * 28
        frame = self._make_frame(visible_xs, low_vis_xs)
        samples = [frame] * 30
        result = check_framing(samples, frame_width=1080, frame_height=1920)
        assert result.passed is False
        assert result.metric_value == 0.0

    def test_portrait_floor_is_0_1125(self) -> None:
        from app.cv.quality_gates import check_framing
        # Make the metric come back tiny so we can read .threshold.
        # 33 high-vis landmarks all clustered at x=0.50, y=0.50 (bbox = 0).
        frame = np.zeros((33, 5), dtype=np.float64)
        frame[:, 0] = 0.50
        frame[:, 1] = 0.50
        frame[:, 3] = 4.0
        frame[:, 4] = 4.0
        # Avoid NO_POSE sentinel: spread one landmark off-center.
        frame[0, 0] = 0.5001
        frame[0, 1] = 0.5001
        samples = [frame] * 30
        result = check_framing(samples, frame_width=1080, frame_height=1920)
        assert abs(result.threshold - (0.20 * (1080.0 / 1920.0))) < 1e-6
        assert abs(result.threshold - 0.1125) < 1e-6
```

- [ ] **Step 5.2: Run all 3 tests to confirm they fail under current code**

```bash
cd backend && uv run pytest tests/unit/test_quality_gates.py::TestCheckFramingVisibilityGate -v
```

Expected: at least `test_bbox_uses_only_visible_landmarks` and `test_portrait_floor_is_0_1125` fail (the bbox currently uses all 33 landmarks; the threshold is currently 0.169 not 0.1125 — though Task 2 already lowered `_FRAMING_MIN_FRACTION` so the threshold test should now pass on its own; if so, note it but do not skip the next steps).

- [ ] **Step 5.3: Modify `check_framing` to use visibility-gated bbox**

Replace the loop body in `check_framing` (`backend/app/cv/quality_gates.py:286-298`) — specifically the section between `for i in indices:` and the `fractions.append(...)` line — with:

```python
    fractions: list[float] = []
    for i in indices:
        frame = landmarks_per_frame[i]
        if _is_no_pose_frame(frame):
            continue

        # Visibility-gated bbox (ADR-QGATE-COMMERCIAL-GYM).
        # Hallucinated low-confidence landmarks cluster near body centre and
        # under-report the lifter's true frame coverage. Use only landmarks
        # with sigmoid(visibility) >= _LANDMARK_VISIBLE_THRESHOLD.
        visibilities = np.array(
            [sigmoid(float(v)) for v in frame[:, _COL_VISIBILITY]]
        )
        visible_mask = visibilities >= _LANDMARK_VISIBLE_THRESHOLD
        if int(visible_mask.sum()) < _MIN_VISIBLE_LANDMARKS_FOR_BBOX:
            continue

        xs = frame[visible_mask, _COL_X]
        ys = frame[visible_mask, _COL_Y]
        bbox_width = float(np.max(xs) - np.min(xs))
        bbox_height = float(np.max(ys) - np.min(ys))
        fractions.append(bbox_width * bbox_height)
```

- [ ] **Step 5.4: Run the 3 new framing tests — must now pass**

```bash
cd backend && uv run pytest tests/unit/test_quality_gates.py::TestCheckFramingVisibilityGate -v
```

Expected: 3 passed.

- [ ] **Step 5.5: Run the full unit suite — find any framing tests broken by visibility gating**

```bash
cd backend && uv run pytest tests/unit/test_quality_gates.py -v 2>&1 | tail -50
```

If any pre-existing framing tests fail due to changed metric values, update their expected values *only if* the underlying behaviour intent is preserved (i.e., the new value is geometrically correct given the fixture's visibility distribution). If any test fails for a real regression, STOP — return to Phase 1 and reassess.

- [ ] **Step 5.6: Commit**

```bash
git add backend/app/cv/quality_gates.py backend/tests/unit/test_quality_gates.py
git commit -m "feat(cv): visibility-gated bbox in check_framing

Bbox is now computed only from landmarks with sigmoid(visibility) >=
_LANDMARK_VISIBLE_THRESHOLD (0.5). Samples with fewer than 10 such landmarks
are skipped. Removes the systematic under-reporting caused by MediaPipe
hallucinating low-confidence landmarks at the body centre on occluded frames
(squat lockout face occluded by bar plate, deep-bottom positions, etc.).

Adds 3 TestCheckFramingVisibilityGate tests."
```

---

## Task 6: Integration test against the 3 atharva fixtures

**Files:**
- Create: `backend/tests/integration/test_quality_gates_atharva_fixtures.py`

- [ ] **Step 6.1: Write the integration test**

Create `backend/tests/integration/test_quality_gates_atharva_fixtures.py`:

```python
"""Real-video quality-gate integration test against atharva-* fixtures.

Marked ``@pytest.mark.slow`` — runs MediaPipe BlazePose Heavy on three
~20-26 s 1080p videos. ~3-5 min wall-clock on a laptop CPU. Skipped in CI
by default; run locally before merging the commercial-gym fix.

To run:
    uv run pytest tests/integration/test_quality_gates_atharva_fixtures.py -v -m slow
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.cv.pose_extraction import extract_landmarks
from app.cv.quality_gates import run_quality_gates

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "e2e" / "fixtures"

FIXTURE_TABLE = [
    ("atharva-squat.mov", "squat"),
    ("atharva-bench.mov", "bench"),
    ("atharva-deadlift.mov", "deadlift"),
]


@pytest.mark.slow
@pytest.mark.parametrize("filename,exercise_type", FIXTURE_TABLE)
def test_atharva_fixture_passes_quality_gate(
    filename: str, exercise_type: str
) -> None:
    """All 3 commercial-gym fixtures must pass the gate after the
    anchor + visibility-gated changes (ADR-QGATE-COMMERCIAL-GYM).
    Acceptance criterion AC-1 of the design spec."""
    video_path = FIXTURES_DIR / filename
    if not video_path.exists():
        pytest.skip(f"Missing fixture: {video_path}")

    landmarks, _fps, width, height = extract_landmarks(str(video_path))
    result = run_quality_gates(
        landmarks_per_frame=landmarks,
        frame_width=width,
        frame_height=height,
        video_duration_s=len(landmarks) / max(_fps, 1.0),
        exercise_type=exercise_type,
        video_path=str(video_path),
    )

    failed_checks = [c for c in result.checks if not c.passed and c.level == "error"]
    assert result.passed is True, (
        f"{filename} rejected by quality gate. Failing error-level checks:\n"
        + "\n".join(
            f"  {c.name}: metric={c.metric_value:.4f} thr={c.threshold:.4f} msg={c.user_message!r}"
            for c in failed_checks
        )
    )
```

- [ ] **Step 6.2: Verify the `slow` marker is configured**

Run: `grep -n "slow" backend/pyproject.toml backend/pytest.ini backend/conftest.py 2>&1 | head -10`

Expected: see how the project handles `@pytest.mark.slow`. If no config exists, add to `backend/pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]
```

If `[tool.pytest.ini_options].markers` already exists, append the `slow` line.

- [ ] **Step 6.3: Run the integration test**

```bash
cd backend && uv run pytest tests/integration/test_quality_gates_atharva_fixtures.py -v -m slow 2>&1 | tail -30
```

Expected: 3 passed. Capture full output to `_inspection/integration_run.log`.

If any fixture fails, **STOP**. Read the failing-check details. Decision tree:
- If `framing` fails by < 0.005 → consider lowering `_FRAMING_MIN_FRACTION` to 0.18 (follow-up commit). Re-run.
- If `single_person` fails → check whether the anchor algorithm rejected by run-length or fraction. Look at `longest_run` in the metric. If the fixture has genuine pose-tracking issues that the algorithm cannot solve, escalate via `/escalate` — do not weaken the rule below documented thresholds.

- [ ] **Step 6.4: Commit**

```bash
git add backend/tests/integration/test_quality_gates_atharva_fixtures.py
# Only commit pyproject.toml if it was modified:
git add backend/pyproject.toml 2>/dev/null || true
git commit -m "test(cv): integration test for 3 atharva fixtures passing quality gate

@pytest.mark.slow real-video test — runs MediaPipe on the actual 1080p
commercial-gym fixtures from e2e/fixtures/. Skipped in CI; run locally
before merging quality-gate changes. Acceptance criterion AC-1 of the
design spec."
```

---

## Task 7: Documentation — `backend/CLAUDE.md` + `decisions.md`

**Files:**
- Modify: `backend/CLAUDE.md`
- Modify: `decisions.md`

- [ ] **Step 7.1: Update `backend/CLAUDE.md` quality gate predicate gotcha**

Find the section labelled "Quality gate predicate" near the bottom under the "Backend Gotchas" header. Replace the existing block (currently states the body-visibility predicate only) with:

```markdown
### Quality gate predicate (post-2026-04-24, ADR-QGATE-COMMERCIAL-GYM)
Runs in streaq worker (not FastAPI). Three landmark-based error gates + warnings:

- **body_visibility** (FR-CVPL-04): `mean(sigmoid(visibility)[shoulders/elbows/hips/knees]) >= 0.30` over up to 20 evenly-spaced non-NO_POSE samples.
- **framing** (FR-CVPL-04): bbox built from landmarks with `sigmoid(visibility) >= 0.5` only. Sample skipped if fewer than 10 such landmarks. 90th percentile of bbox area must lie in [0.20 × min(1, aspect), 0.80].
- **single_person** (FR-CVPL-06): anchor-based identity-jump detection. Anchors on lifter from first 3 high-hip-visibility samples (median midpoint x). Reject if 4+ consecutive samples are >25 % off-anchor or >30 % of all valid samples are off-anchor.

Gate results stored in `analyses.quality_gate_result` JSONB.

**Why anchor-based, not "no jumps"**: commercial-gym videos always have bystanders. MediaPipe `RunningMode.VIDEO` re-runs the detector branch on tracking-loss events (deep squat, supine bench, deadlift hinge) and can re-acquire onto a clearly-visible bystander. Per-pair-jump rules false-rejected; anchor rule tolerates transient pickups, rejects sustained swaps.
```

- [ ] **Step 7.2: Append ADR to `decisions.md`**

Append a new ADR entry to `decisions.md` (always append, never edit prior ADRs — see CLAUDE.md). Use the next available ADR number after the current head. Body:

```markdown
## ADR-QGATE-COMMERCIAL-GYM — Anchor-based single_person + visibility-gated framing for commercial-gym videos

**Date:** 2026-04-24
**Status:** Accepted
**Context:** Three private-beta fixture videos (atharva-{squat,bench,deadlift}) all rejected by quality gate on prod. Investigation revealed: (1) all are commercial-gym shoots with 3-6 bystanders consistently visible in background; (2) MediaPipe `RunningMode.VIDEO` with `num_poses=1` re-runs the detector branch on tracking-loss events (occluded hips at deep squat/supine bench/deadlift hinge) and can re-acquire onto a bystander; (3) `check_single_person` interpreted these tracker swaps as "multiple people detected" and rejected with "please film alone" — impossible advice for the entire commercial-gym beta user base. Secondary: `check_framing` underweighted the lifter's true frame coverage by including hallucinated low-visibility landmarks clustered at body centre.

**Decision:** Three coordinated changes in `backend/app/cv/quality_gates.py`:
1. `check_single_person` switches to anchor-based identity-jump detection — anchors on the lifter from the first 3 high-hip-visibility samples; rejects only on sustained off-anchor runs (>=4 consecutive) or > 30 % off-anchor fraction. Skips low-hip-visibility samples (those are MediaPipe guesses on occluded frames).
2. `check_framing` builds the bbox only from landmarks with `sigmoid(visibility) >= 0.5`; skips samples with < 10 such landmarks.
3. `_FRAMING_MIN_FRACTION` lowered from 0.30 to 0.20.

User message updated from "Multiple people detected — please film alone" to "Could not consistently track a single lifter — try filming side-on with your full body in frame."

**Alternatives considered:**
- **YOLOv8 + primary-lifter crop:** architecturally correct but +1 dependency, +50 MB container, 3-4 days, infeasible for L2 sprint window. Tracked as post-beta follow-up.
- **Demote single_person to warning:** would let videos through but with garbage rep counts — bad coaching during the highest-stakes user period. Rejected.

**Consequences:**
- (+) 3 atharva fixtures pass without re-shoot.
- (+) Commercial-gym videos with single lifter pass even with bystanders in frame.
- (+) Quality-gate semantics now describe what's actually being measured.
- (–) False-negative risk on legitimate two-co-equal-lifters videos (e.g., training partner across the rack). Acceptable: scoring degrades visibly, user re-films.
- (–) Anchor can lock onto a bystander if MediaPipe gives them as the most-prominent person for the first 3 samples. Risk is real but small given lifter-foreground geometry. If observed, escalate to YOLOv8.

**References:** docs/superpowers/specs/2026-04-24-commercial-gym-quality-gate-design.md, docs/superpowers/plans/2026-04-24-commercial-gym-quality-gate-fix.md, ADR-053, ADR-054, ADR-058.
```

- [ ] **Step 7.3: Run check (lint + type)**

```bash
cd backend && uv run ruff check app/cv/quality_gates.py tests/unit/test_quality_gates.py tests/integration/test_quality_gates_atharva_fixtures.py
cd backend && uv run pyright app/cv/quality_gates.py
```

Expected: zero issues. If issues are reported, fix inline before commit.

- [ ] **Step 7.4: Commit**

```bash
git add backend/CLAUDE.md decisions.md
git commit -m "docs: ADR-QGATE-COMMERCIAL-GYM + backend CLAUDE.md gotcha update

Records the anchor-based single_person + visibility-gated framing decision
for commercial-gym private-beta fixtures."
```

---

## Task 8: Push, PR, CI, merge, deploy, E2E verify

**Files:**
- N/A (workflow only)

- [ ] **Step 8.1: Push branch**

```bash
git push -u origin fix/commercial-gym-quality-gate
```

- [ ] **Step 8.2: Create PR via GitHub MCP**

Use `mcp__github__create_pull_request` with:
- title: `fix(cv): commercial-gym quality gate — anchor + visibility-gated framing`
- body: copy from spec § "Goal" + § "Acceptance criteria" + the test plan summary
- base: `main`
- head: `fix/commercial-gym-quality-gate`

- [ ] **Step 8.3: Wait for CI to go green**

Use `mcp__github__get_pull_request_status` to poll until all required checks (Backend Tests, Backend Lint, Frontend Lint, Frontend Tests, Secret Scanning, Vercel) report success.

- [ ] **Step 8.4: Pre-merge security review**

Per `CLAUDE.md`, this PR touches user-facing strings (the new `single_person` message). Invoke `spelix-security-reviewer` to verify no SaMD / "injury risk" / "Movement Quality" language regressions in the new wording.

- [ ] **Step 8.5: Merge via MCP (merge_method=merge, never squash)**

Use `mcp__github__merge_pull_request` with `merge_method: "merge"`.

- [ ] **Step 8.6: Wait for "Deploy to Production" CI step**

Poll `mcp__github__get_pull_request_status` on `main` until the deploy step is green. Verify droplet HEAD matches the merge commit:

```bash
ssh spelix-droplet "git -C /home/deploy/spelix log --oneline -1"
ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"
```

Expected: HEAD matches; all containers `(healthy)`.

- [ ] **Step 8.7: E2E re-upload all 3 fixtures via Playwright MCP**

Per `CLAUDE.md` "E2E Verification via Playwright MCP":
1. `browser_navigate` → `https://spelix.app`
2. Login as `atharva6905@gmail.com`
3. For each of `atharva-squat.mov`, `atharva-bench.mov`, `atharva-deadlift.mov`: upload via the upload page, wait for status to reach `completed`, snapshot the results page.
4. Save screenshots to `e2e/screenshots/quality-gate-fix-prod-{squat,bench,deadlift}.png`.
5. `browser_console_messages` (level=error) and `browser_network_requests` (filter 4xx/5xx) — must be clean on the happy path.

- [ ] **Step 8.8: Update `backlog.md`**

Add a new "Completed — L2 Sprint Day 17 — Commercial-gym quality gate fix (2026-04-24)" header at the top of `backlog.md` with a single row table summarising the work, merge SHA, and the 3 fixture E2E screenshots. Commit on `main`:

```bash
git pull
git add backlog.md
git commit -m "docs(backlog): close commercial-gym quality gate fix"
git push
```

---

## Acceptance check (end of plan)

| AC | Verification step | Owner |
|----|-------------------|-------|
| AC-1 | Task 6 integration test green | spelix-cv-engineer |
| AC-2 | Task 8.7 Playwright E2E green | spelix-cv-engineer |
| AC-3 | Task 5.5 full unit suite green | spelix-cv-engineer |
| AC-4 | Task 8.7 — 7.87 s clip passes (re-upload as control) | spelix-cv-engineer |
| AC-5 | Task 3.5 `test_check_single_person_anchor_rejects_sustained_swap` green | spelix-cv-engineer |
| AC-6 | Task 8.4 security review pass | spelix-security-reviewer |
| AC-7 | Task 7.2 ADR appended | spelix-cv-engineer |
| AC-8 | Task 8.8 backlog row added | main agent |
