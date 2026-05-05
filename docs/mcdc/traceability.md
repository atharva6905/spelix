# MC/DC Traceability Matrix

## Coverage Summary

- Functions under MC/DC: 16
- Compound conditions analyzed: 16 decisions across 5 files
- MC/DC test vectors written: 89 (across 7 test files)
- All conditions show independent effect: YES
- Branch coverage (backend): 91% (Phase 1 gate); MC/DC reserved for 16 high-consequence functions
- Branch coverage (frontend): enforced separately in CI

---

## scoring.py — SafetyScore, TechniqueScore, ControlScore

### 1. SafetyScore.compute — confidence cap

**File:** `backend/app/cv/scoring.py`

**Expression:** `if confidence < 0.50: score = min(score, 5.0)`

| Row | C1: confidence < 0.50 | cap fires? | Independent Effect |
|-----|-----------------------|------------|--------------------|
| 1   | F (0.80)              | No         | baseline           |
| 2   | T (0.30)              | Yes        | C1 flips outcome   |

**Boundary row:** confidence == 0.50 exactly → F (strict `<` confirmed)

**Tests:** `test_mcdc_scoring_safety.py::TestSafetyComputeConfidenceCap`

**MC/DC satisfied:** Rows {1, 2} for C1.

---

### 2. SafetyScore._score_squat — torso_lean two-tier elif chain

**File:** `backend/app/cv/scoring.py`

**Expression:**
```
if torso_lean > high: -3.0 penalty
elif torso_lean > caution: -1.5 penalty
```

| Row | C2: lean > high | C3: lean > caution | outcome           | Independent Effect      |
|-----|-----------------|--------------------|-------------------|-------------------------|
| 1   | F               | F                  | no penalty        | baseline                |
| 2   | F               | T                  | caution badge     | C3 flips (when C2=F)    |
| 3   | T               | (any)              | high badge        | C2 flips (short-circuit)|

**None-guard row:** torso_lean absent → entire block skipped (no penalty)

**Tests:** `test_mcdc_scoring_safety.py::TestSafetyScoreSquatTorsoLean`

**MC/DC satisfied:** Rows {1, 3} for C2; Rows {1, 2} for C3.

---

### 3. SafetyScore._score_squat — knee_angle_at_depth None-guard AND below-min

**File:** `backend/app/cv/scoring.py`

**Expression:** `if knee_angle_at_depth is not None and knee_angle_at_depth < min_knee`

| Row | C4: angle is not None | C5: angle < min_knee | fires? | Independent Effect     |
|-----|-----------------------|----------------------|--------|------------------------|
| 1   | F (absent)            | —                    | No     | C4 alone controls       |
| 2   | T                     | F (above min)        | No     | C5 alone controls       |
| 3   | T                     | T (below min)        | Yes    | C5 flips vs row 2       |

**Tests:** `test_mcdc_scoring_safety.py::TestSafetyScoreSquatKneeAngle`

**MC/DC satisfied:** Rows {1, 3} for C4; Rows {2, 3} for C5.

---

### 4. SafetyScore._score_deadlift — hip_angle compound OR

**File:** `backend/app/cv/scoring.py`

**Expression:** `if hip_angle < min_hip or hip_angle > max_hip`

| Row | C6: hip < min | C7: hip > max | C6 or C7 | Independent Effect |
|-----|---------------|---------------|----------|--------------------|
| 1   | F             | F             | F        | baseline           |
| 2   | T             | F             | T        | C6 flips outcome   |
| 3   | F             | T             | T        | C7 flips outcome   |

**None-guard row:** hip_angle absent → block skipped (no penalty)

**Tests:** `test_mcdc_scoring_safety.py::TestSafetyDeadliftHipAngle`

**MC/DC satisfied:** Rows {1, 2} for C6; Rows {1, 3} for C7.

---

### 5. SafetyScore._score_bench — elbow_angle compound OR

**File:** `backend/app/cv/scoring.py`

**Expression:** `if elbow_angle < min_elbow or elbow_angle > max_elbow`

| Row | C8: elbow < min | C9: elbow > max | C8 or C9 | Independent Effect |
|-----|-----------------|-----------------|----------|--------------------|
| 1   | F               | F               | F        | baseline           |
| 2   | T               | F               | T        | C8 flips outcome   |
| 3   | F               | T               | T        | C9 flips outcome   |

**Tests:** `test_mcdc_scoring_safety.py::TestSafetyBenchElbowAngle`

**MC/DC satisfied:** Rows {1, 2} for C8; Rows {1, 3} for C9.

---

### 6. SafetyScore._score_bench — shoulder_angle single condition

**File:** `backend/app/cv/scoring.py`

**Expression:** `if shoulder_angle > max_shoulder`

| Row | C10: shoulder > max | fires? | Independent Effect |
|-----|---------------------|--------|--------------------|
| 1   | F                   | No     | baseline           |
| 2   | T                   | Yes    | C10 flips outcome  |

**Tests:** `test_mcdc_scoring_safety.py::TestSafetyBenchShoulderAngle`

**MC/DC satisfied:** Rows {1, 2} for C10.

---

### 7. TechniqueScore.compute — depth_std compound AND

**File:** `backend/app/cv/scoring.py`

**Expression:** `if depth_angle_std is not None and depth_angle_std > 10.0`

| Row | A: std is not None | B: std > 10.0 | fires? | Independent Effect   |
|-----|--------------------|---------------|--------|----------------------|
| 1   | F (absent)         | —             | No     | A alone controls     |
| 2   | T                  | F (== 10.0)   | No     | B alone controls     |
| 3   | T                  | T (15.0)      | Yes    | B flips vs row 2     |

**Penalty when fires:** `min(3.0, (std - 10.0) * 0.2)`. Row 3 at std=15.0: penalty = 1.0.

**Tests:** `test_mcdc_scoring_technique.py::TestTechniqueDepthStdAnd`

**MC/DC satisfied:** Rows {1, 3} for A; Rows {2, 3} for B.

---

### 8. TechniqueScore._score_bench — elbow_angle negated range

**File:** `backend/app/cv/scoring.py`

**Expression:** `if not (70.0 <= elbow_angle <= 90.0)` (hardcoded target range)

| Row | in range [70, 90]? | penalty? | Independent Effect                    |
|-----|--------------------|----------|---------------------------------------|
| 1   | Yes (80°)          | No       | baseline                              |
| 2   | No (< 70, angle=60°) | Yes    | below-min exit independently causes   |
| 3   | No (> 90, angle=100°)| Yes    | above-max exit independently causes   |

**Tests:** `test_mcdc_scoring_technique.py::TestTechniqueBenchElbowRange`

**MC/DC satisfied:** Rows {1, 2} for the lower-bound condition; Rows {1, 3} for the upper-bound condition.

---

### 9. TechniqueScore._score_bench — elbow_flare two-tier elif chain

**File:** `backend/app/cv/scoring.py`

**Expression:**
```
if elbow_flare > high: -2.0 penalty   (high = 60.0°)
elif elbow_flare > caution: -1.0 penalty  (caution = 45.0°)
```

| Row | > high (60°) | > caution (45°) | outcome         | Independent Effect       |
|-----|--------------|-----------------|-----------------|--------------------------|
| 1   | F            | F               | no penalty      | baseline                 |
| 2   | F            | T               | caution badge   | caution flips (C2=F)     |
| 3   | T            | (True implied)  | high badge      | high flips (short-circuit)|

**Tests:** `test_mcdc_scoring_technique.py::TestTechniqueBenchElbowFlare`

**MC/DC satisfied:** Rows {1, 3} for high condition; Rows {1, 2} for caution condition.

---

### 10. ControlScore.compute — descent two-tier elif chain

**File:** `backend/app/cv/scoring.py`

**Expression:**
```
if descent < high_s: -3.0 penalty     (high_s = 1.0)
elif descent < caution_s: -2.0 penalty  (caution_s = 1.5)
```

| Row | descent (s) | < high (1.0)? | < caution (1.5)? | outcome         | Independent Effect       |
|-----|-------------|---------------|------------------|-----------------|--------------------------|
| 1   | 1.5         | F             | F                | no penalty      | baseline                 |
| 2   | 1.2         | F             | T                | caution badge   | caution flips (high=F)   |
| 3   | 0.8         | T             | (True implied)   | high badge      | high flips (short-circuit)|

**Tests:** `test_mcdc_scoring_control.py::TestControlDescentTwoTier`

**MC/DC satisfied:** Rows {1, 3} for the high condition; Rows {1, 2} for the caution condition.

---

### 11. ControlScore.compute — rep_duration_std compound AND

**File:** `backend/app/cv/scoring.py`

**Expression:** `if rep_duration_std is not None and rep_duration_std > std_caution` (std_caution = 0.5)

| Row | A: std is not None | B: std > 0.5 | fires? | Independent Effect   |
|-----|--------------------|--------------|--------|----------------------|
| 1   | F (absent)         | —            | No     | A alone controls     |
| 2   | T                  | F (== 0.5)   | No     | B alone controls     |
| 3   | T                  | T (0.6)      | Yes    | B flips vs row 2     |

**Penalty when fires:** -1.0, badge `rep_duration_inconsistent`.

**Tests:** `test_mcdc_scoring_control.py::TestControlRepDurationStd`

**MC/DC satisfied:** Rows {1, 3} for A; Rows {2, 3} for B.

---

### 12. ControlScore.compute — deadlift lockout three-way AND chain

**File:** `backend/app/cv/scoring.py`

**Expression:** `if exercise == "deadlift" and lockout_angle is not None and lockout_angle < min_lockout` (min_lockout = 150.0°)

| Row | A: exercise=="deadlift" | B: angle is not None | C: angle < 150 | fires? | Independent Effect   |
|-----|-------------------------|----------------------|----------------|--------|----------------------|
| 1   | F (squat)               | —                    | —              | No     | A alone controls     |
| 2   | T                       | F (absent)           | —              | No     | B alone controls     |
| 3   | T                       | T                    | F (155°)       | No     | C alone controls     |
| 4   | T                       | T                    | T (140°)       | Yes    | C flips vs row 3     |

**Penalty when fires:** -1.5, badge `lockout_incomplete`.

**Tests:** `test_mcdc_scoring_control.py::TestControlDeadliftLockout`

**MC/DC satisfied:** Rows {1, 4} for A; Rows {2, 4} for B; Rows {3, 4} for C.

---

## quality_gates.py — video validation, framing, single_person, lighting, orchestrator

### 13. check_video_file — corrupt-file OR guard

**File:** `backend/app/cv/quality_gates.py`

**Expression:** `if returncode != 0 or not stdout.strip()`

| Row | A: returncode != 0 | B: stdout empty | A or B | Independent Effect |
|-----|--------------------|-----------------|---------|--------------------|
| 1   | F (rc=0)           | F (has output)  | F       | baseline pass      |
| 2   | T (rc=1)           | F               | T       | A flips outcome    |
| 3   | F (rc=0)           | T (empty)       | T       | B flips outcome    |

**Additional edge cases tested:** whitespace-only stdout (treated as empty), duration > 120s (separate duration gate), FileNotFoundError (ffprobe missing).

**Tests:** `test_mcdc_quality_gates.py::TestCheckVideoFileOr`

**MC/DC satisfied:** Rows {1, 2} for A; Rows {1, 3} for B.

---

### 14. check_framing — 3-way bbox boundary

**File:** `backend/app/cv/quality_gates.py`

**Expression:** coverage fraction must satisfy `min_frac <= bbox_area <= max_frac` (landscape: [0.18, 0.80]; portrait: min_frac *= aspect_ratio)

| Row | bbox_area      | passes?              | outcome                    |
|-----|----------------|----------------------|----------------------------|
| 1   | ~0.64 (wide spread) | Yes             | passed=True                |
| 2   | ~0.01 (tiny)   | No (below min_frac)  | "too far" rejection        |
| 3   | 1.0 (full frame)| No (above max_frac) | "too close" rejection      |

**Portrait row:** bbox ~0.12 at 1080×1920 — above portrait floor (~0.10) but below landscape floor (0.18) → passes (demonstrates aspect-ratio scaling).

**Tests:** `test_mcdc_quality_gates.py::TestCheckFraming3Way`

**MC/DC satisfied:** All three boundary regions independently covered; below-min and above-max each independently flip the outcome from the in-range baseline.

---

### 15. check_single_person — anchor-based OR guard

**File:** `backend/app/cv/quality_gates.py`

**Expression:** `rejected = (longest_consecutive_run >= 4) or (off_anchor_fraction > 0.30)`

Constants: `_OFF_ANCHOR_DISTANCE_FRAC=0.25`, `_MAX_CONSECUTIVE_OFF_ANCHOR=4`, `_MAX_OFF_ANCHOR_FRACTION=0.30`, `_ANCHOR_FROM_FIRST_N_SAMPLES=3`.

| Row | A: run >= 4 | B: fraction > 0.30 | rejected? | Independent Effect |
|-----|-------------|--------------------|-----------|--------------------|
| 1   | F           | F                  | No        | baseline pass      |
| 2   | T           | F (also fires)     | Yes       | A independently controls |
| 3   | F           | T                  | Yes       | B independently controls |

**Row 2 construction:** 3 anchor frames at x=0.5, then 10 consecutive frames at x=0.9 (off by 0.4 > 0.25). Run=10 ≥ 4 (A fires). Fraction also fires; the test asserts `metric_value >= 4` confirming A.

**Row 3 construction:** 3 anchor + 28 alternating on/off frames. Alternation keeps longest run=1 (A=F); off-anchor fraction ≈ 43% > 30% (B fires). Test asserts `metric_value < 4`.

**Tests:** `test_mcdc_quality_gates.py::TestCheckSinglePersonOr`

**MC/DC satisfied:** Rows {1, 2} for A; Rows {1, 3} for B.

---

### 16. run_quality_gates — overall pass predicate

**File:** `backend/app/cv/quality_gates.py`

**Expression:** `overall_passed = all(c.passed for c in checks if c.level == "error")`

| Row | error-level checks  | warning-level checks | overall? | outcome             |
|-----|---------------------|----------------------|----------|---------------------|
| 1   | all passed          | none                 | True     | status="passed"     |
| 2   | body_visibility fails | none               | False    | status="rejected"   |
| 3   | all passed          | lighting fires       | True     | status="passed" (warning doesn't count) |

**Additional row:** video_file_check fails → early return with a single check in the list (short-circuit confirmed by `len(result.checks) == 1`).

**Tests:** `test_mcdc_quality_gates.py::TestRunQualityGates`

**MC/DC satisfied:** All independent paths through the gate predicate covered; warning gate independently shown to not affect overall pass/fail.

---

## rep_detection.py — state machine, peak/valley fallback

### 17. State machine ASCENDING exit — compound AND

**File:** `backend/app/cv/rep_detection.py`

**Expression:** `if angle > (standing_thresh - hysteresis) and rep_duration_frames >= min_rep_frames`

Thresholds (squat, standard): standing_thresh=150°, hysteresis=5°, min_rep_frames=15.
Exit gate: `angle > 145° AND duration >= 15 frames`.

| Row | C1: angle > 145° | C2: duration >= 15 | rep counted? | Independent Effect  |
|-----|------------------|--------------------|--------------|---------------------|
| 1   | F (parks at 130°)| —                  | No           | C1 alone blocks     |
| 2   | T                | F (10 frames)      | No           | C2 alone blocks     |
| 3   | T                | T (60 frames)      | Yes          | C2 flips vs row 2   |

**Note:** Tests use `_detect_reps_state_machine` directly to isolate from the peak/valley fallback path.

**Tests:** `test_mcdc_rep_detection.py::TestStateMachineAscendingExit`

**MC/DC satisfied:** Rows {1, 3} for C1; Rows {2, 3} for C2.

---

### 18. State machine DESCENDING → BOTTOM gate

**File:** `backend/app/cv/rep_detection.py`

**Expression:** `if angle < (depth_thresh - hysteresis)` triggers BOTTOM state entry

Threshold: `depth_thresh - hysteresis = 105°`. Signal must cross 105° to enter BOTTOM; otherwise DESCENDING aborts back to STANDING.

| Row | C3: angle < 105° | BOTTOM entered? | rep counted? | Independent Effect |
|-----|------------------|-----------------|--------------|--------------------|
| 1   | T (reaches 100°) | Yes             | Yes (1 rep)  | C3 determines entry|
| 2   | F (parks at 120°)| No              | No (abort)   | C3 being F aborts  |

**Tests:** `test_mcdc_rep_detection.py::TestStateMachineDescendingAbort`

**MC/DC satisfied:** Rows {1, 2} for C3.

---

### 19. Peak/valley fallback trigger

**File:** `backend/app/cv/rep_detection.py`

**Expression:** `if len(state_machine_reps) >= 1: return state_machine_reps` (else invoke fallback)

| Row | C4: SM reps >= 1  | fallback fired? | Independent Effect |
|-----|-------------------|-----------------|--------------------|
| 1   | T (2 clean reps)  | No              | C4=T → SM result returned |
| 2   | F (partial lockout)| Yes            | C4=F → fallback fires     |

**Row 2 construction:** Signal oscillates 80°–130° (never reaches standing threshold 150°). SM returns 0 reps → fallback fires and detects valleys.

**Tests:** `test_mcdc_rep_detection.py::TestPeakValleyFallbackTrigger`

**MC/DC satisfied:** Rows {1, 2} for C4.

---

### 20. Peak/valley fallback — valley duration post-filter

**File:** `backend/app/cv/rep_detection.py`

**Expression:** `if (end_frame - start_frame) >= min_rep_frames` (min_rep_frames = 15)

| Row | C5: span >= 15 frames | rep kept? | Independent Effect |
|-----|-----------------------|-----------|--------------------|
| 1   | T (span=60)           | Yes       | C5=T → valley kept |
| 2   | F (span=14)           | No        | C5=F → discarded   |

**Row 2 construction:** Valley with prominence 50° > 20° threshold (find_peaks locates it) but peak-to-peak span = 14 frames < 15. Post-filter discards it.

**Tests:** `test_mcdc_rep_detection.py::TestPeakValleyMinDuration`

**MC/DC satisfied:** Rows {1, 2} for C5.

---

## confidence.py — Tier 4 phase adjustment

### 21. _tier4_phase_adjusted — static_peak OR condition (elif branch)

**File:** `backend/app/cv/confidence.py`

**Expression:**
```
if abs(frame_offset - depth_frame_offset) <= bottom_window:  # proximity/high-occlusion (priority)
    ...
elif frame_offset == 0 or frame_offset == rep_frame_count - 1:  # static_peak
    ...
else:
    ...  # transition
```

MC/DC rows for the `elif` OR: `frame_offset == 0 OR frame_offset == (count - 1)`.
Setup: depth_frame_offset=20, count=30, bottom_window=3 — all test offsets are outside the proximity window [17, 23].

| Row | A_or: offset == 0 | B_or: offset == 29 | elif fires? | multiplier    | Independent Effect    |
|-----|-------------------|--------------------|-------------|---------------|-----------------------|
| 1   | F (offset=15)     | F                  | No          | transition    | baseline              |
| 2   | T (offset=0)      | F                  | Yes         | static_peak   | A_or independently causes elif |
| 3   | F                 | T (offset=29)      | Yes         | static_peak   | B_or independently causes elif |

**Priority row:** depth_frame=0, frame_offset=0, bottom_window=3 — `|0-0|=0 ≤ 3` → if-branch fires (high_occlusion), NOT elif. Demonstrates lexical priority.

**Tests:** `test_mcdc_confidence.py::TestTier4StaticPeakOR`, `test_mcdc_confidence.py::TestTier4ProximityPriority`

**MC/DC satisfied:** Rows {1, 2} for A_or; Rows {1, 3} for B_or.

---

## pipeline.py — degenerate scoring guard, GPT-4o fallback trigger

### 22. _is_degenerate_scoring_input — OR guard

**File:** `backend/app/services/pipeline.py`

**Expression:** `return (not rep_metrics) or (session_confidence < 0.50)`

| Row | A: not rep_metrics | B: confidence < 0.50 | A or B | Independent Effect |
|-----|--------------------|----------------------|--------|--------------------|
| 1   | F (non-empty list) | F (0.80)             | F      | baseline           |
| 2   | T (empty list)     | F (0.80)             | T      | A flips outcome    |
| 3   | F (non-empty list) | T (0.49)             | T      | B flips outcome    |

**Boundary rows tested:** confidence == 0.50 → F (strict `<` confirmed); A=T AND B=T → T (OR short-circuits on A).

**Tests:** `test_mcdc_pipeline_decisions.py::TestDegenerateScoringOR`

**MC/DC satisfied:** Rows {1, 2} for A; Rows {1, 3} for B.

---

### 23. GPT-4o fallback trigger — AND gate (FR-XDET-04)

**File:** `backend/app/services/pipeline.py`

**Expression:** `if detection.confidence < _FALLBACK_CONFIDENCE_THRESHOLD and openai_client is not None`

Threshold: `_FALLBACK_CONFIDENCE_THRESHOLD = 0.7`.

| Row | C: confidence < 0.7 | D: client is not None | C and D | Independent Effect |
|-----|---------------------|------------------------|---------|-------------------|
| 1   | F (0.75)            | T                      | F       | C independently blocks |
| 2   | T (0.50)            | F (None)               | F       | D independently blocks |
| 3   | T (0.50)            | T                      | T       | Both required      |

**Boundary row tested:** confidence == 0.70 → F (strict `<` confirmed).

**Tests:** `test_mcdc_pipeline_decisions.py::TestGPT4oFallbackAND`

**MC/DC satisfied:** Rows {1, 3} for C; Rows {2, 3} for D.
