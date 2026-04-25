# Commercial-Gym Quality Gate Fix — Design Spec

**Date:** 2026-04-24
**Status:** Approved (Approach A)
**Author:** Atharva (with Claude Code investigation)
**Related:** ADR-053, ADR-054, ADR-058, FR-CVPL-04, FR-CVPL-06, FR-CVPL-07

---

## Problem

The L2 private-beta launch (target 2026-05-03) requires `atharva-squat.mov`, `atharva-bench.mov`, and `atharva-deadlift.mov` to pass the upload quality gate without re-shoot or re-trim. They currently all reject.

### Production evidence (prod DB, atharva6905@gmail.com last 6 uploads)

| Date | Exercise | Duration | body_vis | framing | single_person | Status |
|------|----------|----------|----------|---------|---------------|--------|
| 04-24 21:12 | squat | 19.88 s | 0.65 ✓ | **0.112 ✗** (thr 0.169) | **5 jumps ✗** (thr 2) | rejected |
| 04-22 16:28 | bench | 22.69 s | 0.65 ✓ | 0.248 ✓ | **4 jumps ✗** | rejected |
| 04-22 10:16 | deadlift | 25.40 s | 0.66 ✓ | **0.167 ✗** (thr 0.169) | **3 jumps ✗** | rejected |
| 04-21 23:03 | squat (DIFFERENT 7.87 s clip) | 7.87 s | 0.66 ✓ | 0.219 ✓ | 0 jumps ✓ | completed |

### Root cause

All three failing clips are **commercial-gym shoots** (1080×1920 portrait, ~60 fps, 20-26 s) with **3-6 bystanders consistently visible in the background** — confirmed by visual inspection of frames at 0%, 20%, 50%, 80%, 100% of each clip.

1. **`single_person` failure**: MediaPipe `RunningMode.VIDEO` with `num_poses=1` (per `pose_extraction.py:177`, ADR-058) re-runs the detector branch on tracking-loss events (when `min_tracking_confidence=0.5` is breached during deep squat / supine bench / deadlift hinge). The detector then picks the most prominent person *in that frame*. With clearly-visible standing bystanders behind a partially-occluded main lifter, the re-acquired tracking target is sometimes a bystander. The current `check_single_person` measures hip-x jumps between sampled frames; bystander re-acquisitions produce jumps of 30-60 % frame width, far exceeding the 15 % threshold. The check is operating correctly for its narrow definition, but the user message ("Multiple people detected — please film alone") is impossible advice for the commercial-gym beta user base.

2. **`framing` failure (squat 0.112; deadlift 0.167)**: `check_framing` builds the lifter bbox from raw min/max of all 33 landmarks. When MediaPipe outputs low-visibility landmarks for occluded body parts (face occluded by bar plate during squat top, ankles cropped by the rack base), those landmarks cluster at the body centre rather than spreading to anatomical extremes. The resulting bbox under-reports the lifter's true frame coverage. Combined with portrait-scaled threshold `0.30 × 0.5625 = 0.169`, side-on commercial-rack shoots from a normal phone distance (~3 m) fail.

The check semantics were calibrated for short, isolated, single-person fixture videos (the 7.87 s squat that passes). They have not been validated against the real beta user pool: commercial gyms, bystanders, normal shooting distance, full rep sets.

---

## Goal

Make the 3 atharva fixtures pass the quality gate **as filmed**, without lowering the bar against genuinely bad uploads (no person visible, multiple co-equal lifters, severely under-framed). Ship before L2 launch (2026-05-03).

---

## Approach A — Anchor + visibility-gated quality gate

Three coordinated changes to `backend/app/cv/quality_gates.py`. No new dependencies. No MediaPipe pipeline changes.

### Change 1: Anchor-based identity-jump rule in `check_single_person`

Replace "any large hip jump = multiple people" with "sustained displacement to a far region = identity swap."

**New algorithm:**
1. Sample up to 30 evenly-spaced frames (unchanged).
2. **Skip samples where either hip's `sigmoid(visibility) < 0.5`** (these are MediaPipe guesses on occluded frames). Mirrors the visibility gate already used by `check_body_visibility`.
3. Compute a **lifter-anchor centroid** = median hip-midpoint x across the first 3 surviving high-visibility samples.
4. For each remaining sample, compute distance from anchor as fraction of frame width. Mark "off-anchor" if > 0.25 (current jump threshold is 0.15 between *adjacent* samples — a stricter test against real swaps).
5. Reject only if **≥ 4 consecutive off-anchor samples** OR **≥ 30 % of all valid samples are off-anchor**. A momentary bystander pickup that resolves on the next sample does not trip the gate.

**New constants** (added to the existing block at top of file):
- `_ANCHOR_FROM_FIRST_N_SAMPLES: int = 3`
- `_OFF_ANCHOR_DISTANCE_FRAC: float = 0.25`
- `_MAX_CONSECUTIVE_OFF_ANCHOR: int = 4`
- `_MAX_OFF_ANCHOR_FRACTION: float = 0.30`

**Reused constant** (already in the file at line 36):
- `_LANDMARK_VISIBLE_THRESHOLD: float = 0.50` — used to gate hip samples (`sigmoid(hip_vis) >= _LANDMARK_VISIBLE_THRESHOLD`)

**Retire:** `_HIP_JUMP_THRESHOLD = 0.15`, `_MAX_JUMP_COUNT = 2` (replaced by the new constants).

**New user message:** `"Could not consistently track a single lifter — try filming side-on with your full body in frame."` Replaces the "please film alone" text, which is impossible advice for commercial-gym users.

### Change 2: Visibility-gated bbox in `check_framing`

Build the bbox from only landmarks where `sigmoid(visibility) ≥ 0.5`. Hallucinated low-confidence landmarks no longer compress the bbox toward the body centre.

**Implementation sketch (replaces `xs/ys` extraction in `check_framing`):**
```python
visibilities_sig = np.array([sigmoid(v) for v in frame[:, _COL_VISIBILITY]])
visible_mask = visibilities_sig >= _LANDMARK_VISIBLE_THRESHOLD  # already 0.5 in the file
if visible_mask.sum() < _MIN_VISIBLE_LANDMARKS_FOR_BBOX:
    continue  # not enough reliable landmarks — skip this sample
xs = frame[visible_mask, _COL_X]
ys = frame[visible_mask, _COL_Y]
```

**New constant:** `_MIN_VISIBLE_LANDMARKS_FOR_BBOX: int = 10` (out of 33). At least a third of the body must be reliably visible to count the sample.

`_LANDMARK_VISIBLE_THRESHOLD = 0.50` already exists in the file (line 36) and is reused.

### Change 3: Lower portrait floor in `check_framing`

Reduce `_FRAMING_MIN_FRACTION` from `0.30` to `0.20`. The portrait-scaled floor becomes `0.20 × 0.5625 = 0.1125`. The 0.30 floor was calibrated on lab fixtures with the lifter ~1.5 m from the camera; commercial-rack shoots at 3-4 m naturally fill 12-20 % of a portrait frame. The 0.20 value is the smallest reduction expected to admit the squat case (current metric 0.112) once Change 2's visibility gating raises the metric — empirical confirmation runs through the integration test (Task 6 of the implementation plan) before merge. If the visibility-gated metric still falls under 0.1125, the floor is reduced further as a follow-up commit.

`_FRAMING_MAX_FRACTION = 0.80` is unchanged.

---

## Out of scope (deferred, post-beta)

- **YOLOv8 multi-person detection + primary-lifter cropping.** This is the architecturally correct fix and would obsolete most of `check_single_person`. ~3-4 days, +1 dependency, +50 MB container, not viable for the L2 sprint window. Tracked as future work in `decisions.md` ADR follow-up.
- **Lighting / stability gates.** Untouched.
- **Confidence pipeline.** Untouched.
- **Rep detection / scoring.** Untouched.

---

## Test plan

### Unit tests (new + updated in `backend/tests/unit/test_quality_gates.py`)

1. **`test_check_single_person_anchor_tolerates_brief_bystander_pickup`** — synthetic landmark fixture: 30 samples with anchor at x=0.5, three samples (#10, #11, #12) at x=0.85 (bystander) returning to anchor. Expected: `passed=True`.
2. **`test_check_single_person_anchor_rejects_sustained_swap`** — fixture: 30 samples with anchor at x=0.5 for first 10, then x=0.85 for last 20 (clearly two different people). Expected: `passed=False`.
3. **`test_check_single_person_skips_low_visibility_hips`** — fixture: alternate samples have hip visibility=0.3 (skipped), valid samples are all anchor-stable. Expected: `passed=True` even if skipped frames have wild x.
4. **`test_check_single_person_rejects_when_lt_threshold_high_vis_samples`** — fixture: < 3 high-visibility samples. Expected: `passed=False` with the right user_message (we cannot anchor reliably).
5. **`test_check_single_person_user_message_is_lifter_tracking`** — verify the new user_message text for failure cases.
6. **`test_check_framing_uses_only_visible_landmarks`** — fixture: 33 landmarks where 23 are visible (vis=0.9) spanning the full frame, 10 are low-vis (vis=0.1) clustered at center. Expected: `metric` reflects bbox of the 23 visible landmarks, not all 33.
7. **`test_check_framing_skips_samples_with_few_visible_landmarks`** — fixture: 30 samples, 28 with only 5 visible landmarks each. Expected: `passed=False`, "framing" metric=0.0 with `_FRAMING_TOO_SMALL_MSG` (cannot frame).
8. **`test_check_framing_portrait_floor_is_0_1125`** — assert that for `frame_width=1080, frame_height=1920`, the threshold reported in `GateCheckResult.threshold` equals `0.20 * 0.5625 == 0.1125` ± 1e-6.

### Existing-test updates

- `test_check_single_person_*` tests that assert on the old `_HIP_JUMP_THRESHOLD` / `_MAX_JUMP_COUNT` constants need rewriting around the new anchor algorithm. Any test that asserts the old user_message string updates to the new one.
- `test_check_framing_*` tests that assert `metric_value` of fixtures with mixed-visibility landmarks may shift; update expected values.

### Integration test (new)

`backend/tests/integration/test_quality_gates_atharva_fixtures.py`:
- Loads each of the 3 atharva fixtures from `e2e/fixtures/`, runs `extract_landmarks` + `run_quality_gates`, asserts `passed=True` for all three.
- Marked `@pytest.mark.slow` and skipped in CI by default (real video files, ~3-5 min runtime), but runnable locally before merge.

### E2E verification (manual, on prod after deploy)

Per CLAUDE.md "Post-Merge Deployment" + "E2E Verification":
1. Wait for "Deploy to Production" CI step.
2. Re-upload each of the 3 atharva fixtures via spelix.app.
3. Confirm `status=completed` on each.
4. Capture screenshots to `e2e/screenshots/quality-gate-fix-prod-{squat,bench,deadlift}.png`.

---

## Acceptance criteria

| AC | Criterion | Verification |
|----|-----------|--------------|
| AC-1 | All 3 atharva fixtures pass quality gate locally via integration test | `pytest backend/tests/integration/test_quality_gates_atharva_fixtures.py -v` green |
| AC-2 | All 3 atharva fixtures pass on prod after deploy | Manual E2E re-upload, all reach `status=completed` |
| AC-3 | Existing unit-test invariants for `check_single_person` and `check_framing` updated and green | `uv run pytest backend/tests/unit/test_quality_gates.py -v` green |
| AC-4 | The previously-passing 7.87 s squat clip continues to pass (regression guard) | Existing E2E flow unchanged |
| AC-5 | A 30-sample synthetic "two co-equal lifters at x=0.3 and x=0.7 with anchor swapping every 2 samples" video is still rejected | New unit test |
| AC-6 | No SaMD/FTC language regressions; new user_message reviewed by `spelix-security-reviewer` | Pre-merge review pass |
| AC-7 | `decisions.md` updated with ADR for "Anchor-based single_person + visibility-gated framing" | New ADR appended |
| AC-8 | `backlog.md` updated with the closed task ID | New row + `done` status |

---

## Risk + rollback

**Risk 1 — false negatives on legitimate two-lifter videos:** A user films their training partner from across the rack, lifter A in foreground at x=0.4 and lifter B in background at x=0.7, MediaPipe alternates. Under the new rule, this passes if MediaPipe locks onto one of them >70 % of samples. Acceptable: scoring will be wrong for that video, but coaching output will be visibly nonsensical (e.g., wrong rep count) and the user will re-film. Bad coaching is recoverable; rejected uploads block users entirely.

**Risk 2 — under-framed videos slip through:** Lowering portrait floor from 0.169 to 0.1125 admits videos where the lifter is genuinely too small. Mitigation: visibility-gating (Change 2) raises the metric for legitimate videos by removing hallucinated-cluster bias, so the *effective* tightness against bad input is preserved. Empirically: the deadlift at 0.167 is a marginal-pass case; if the visibility gate raises it to ~0.20, the 0.1125 floor is still meaningful guardrail.

**Risk 3 — anchor on the wrong person:** First 3 high-visibility samples could capture a bystander mid-squat-rack-walk. Mitigation: in commercial gym video the lifter is by far the dominant pose for the first ~1-2 s of the clip (rack approach, set up, descent start). Risk is real but small. If observed in the field, escalate to YOLOv8 (out of scope for this fix).

**Rollback:** Single-file revert. Regenerate the original constants and gate logic. No data migration. ~5 min revert.

---

## Out of code: documentation updates

1. `decisions.md` — append ADR (e.g., ADR-QGATE-COMMERCIAL-GYM): record the anchor + visibility-gating decision, link to this spec.
2. `backlog.md` — add row for this fix under a new "Completed — L2 Sprint Day 17 — Commercial-gym quality gate fix" header at session close.
3. `backend/CLAUDE.md` — update the "Quality gate predicate" gotcha block to reflect the new anchor rule.
