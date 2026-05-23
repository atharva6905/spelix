# Session 7 — Complex Metrics Design Plan

**Date:** 2026-05-23
**Author:** spelix-cv-engineer (design spike)
**Status:** approved — ready for TDD expansion
**Skeleton plan:** `docs/superpowers/plans/2026-05-22-session-7-complex-multi-frame.md`
**Design spec:** `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-7 + Section 4
**Implements:** design-only document; no FR-IDs are implemented here — implementations carry
FR-REPM-02 / FR-REPM-03 (per-rep metric extraction) as the upstream SRS hooks.

---

## Summary

Three metrics remain unimplemented after Session 6: `lumbar_flexion_proxy_delta_deg` (#2),
`bar_path_classification` (#6), and `technique_consistency_std` (#16). All are compute-only
(no scoring, no threshold config entries). Each introduces a pattern not seen in Sessions 4–6:

- #2 requires a cross-rep baseline frame — a reference measured at one point in the session
  and compared to a per-rep bottom frame.
- #6 requires shape classification over an entire bar-x trajectory within one rep.
- #16 aggregates across all reps and produces a single per-session value.

This document resolves all open design questions so the TDD expansion can proceed without
further design discussion.

---

## Decision 1 — Standing Baseline Frame Identification for #2

### 1A. Squat baseline

**Decision: one global baseline per session = `reps[0].start_frame`.**

Biomechanical justification: the standing position for a squat set is established once before
the first rep. Using the first frame of the first rep (before any descent) captures the
lifter's natural upright torso with maximal hip extension. Every subsequent rep's start frame
is also a valid standing position, but using a single global baseline has two practical
advantages:

1. Drift across the set is meaningful signal — if the lifter progressively increases forward
   lean across reps, computing delta against each rep's own start frame would suppress that
   information entirely.
2. Rep start frames for later reps may capture partial descent if rep detection fires slightly
   late. The first rep's start frame is the cleanest standing posture in the clip.

For single-rep sessions, the global baseline is identical to the per-rep option, so the two
approaches converge.

**Edge cases:**

- If `reps[0].start_frame` is out-of-bounds for `landmarks_per_frame`, return `None` for all
  reps (degenerate input).
- If landmark visibility at `reps[0].start_frame` is below `_S5_MIN_VIS` for either
  `side_idx.shoulder` or `side_idx.hip`, return `None` for all reps (cannot trust the
  baseline).

### 1B. Deadlift baseline

**Decision: previous rep's `end_frame` (the lockout frame of the rep immediately before the
current one). For the first rep (rep_position = 0), use option (a): the last frame before
`identify_liftoff_frame`.**

Full first-rep logic:

1. Call `identify_liftoff_frame(bar_y_series, setup_frame=rep.start_frame, end_frame=rep.end_frame)`.
   The bar-y series is the wrist-midpoint y (already computed by `_wrist_midpoint_trajectory`
   and available in the caller because `_deadlift_metrics` already computes it for `#4`).
2. If `liftoff_frame is None` (bar never rises enough), use `rep.start_frame` directly as the
   baseline — this is the best available standing proxy.
3. If `liftoff_frame is not None`, set `baseline_frame = liftoff_frame - 1` (clamped to
   `>= rep.start_frame`). The frame just before liftoff is the last frame where the lifter
   is set and stationary over the bar — hips are still in the starting position and lumbar is
   loaded but not yet in motion.

**Why not option (b) — hip-y stability heuristic?**

A hip-y stability scan across the entire first-rep window is a second pass over the landmark
stream that complicates the extraction without strong biomechanical benefit. The pre-liftoff
frame captures the same information (the lifter is standing/set) without additional scanning.

**Why not option (c) — skip first-rep entirely?**

Skipping the first DL rep would mean a 5-rep session loses 20% of its data for a metric that
is already only compute-only. The pre-liftoff baseline is biomechanically sound: it represents
the set position, which IS a valid standing reference for a deadlift.

**ADR note:** this DL first-rep decision (pre-liftoff baseline, fallback to rep.start_frame
when liftoff undetectable) goes verbatim into ADR-LUMBAR-FLEXION-PROXY-NAMING.

### 1C. Signature change: how the analyzer gets cross-rep context

Add two optional parameters with defaults to `_squat_metrics` and `_deadlift_metrics`,
mirroring the Session 5 pattern for `lifter_side`:

```python
all_reps: list[DetectedRep] | None = None,
rep_position: int = 0,
```

- `all_reps` enables DL to access `all_reps[rep_position - 1].end_frame` for the
  previous-rep lockout baseline on non-first reps.
- `rep_position` is the 0-based index of the current rep within `all_reps`.
- Default `None` / `0` means existing unit tests that call `_squat_metrics` or
  `_deadlift_metrics` directly without these args continue to work without modification.

`extract_rep_metrics` passes these through:

```python
for i, rep in enumerate(reps):
    metrics = analyzer(
        rep, landmarks_per_frame, angle_timeseries, fps, side_idx, lifter_side,
        all_reps=reps, rep_position=i,
    )
```

### 1D. Helper function

```python
def identify_standing_baseline_frame(
    exercise_type: str,
    rep: DetectedRep,
    rep_position: int,
    all_reps: list[DetectedRep] | None,
    bar_y_series: np.ndarray | None,
) -> int | None:
```

Returns the baseline frame index, or `None` if one cannot be determined. The `bar_y_series`
argument is only used by the DL path (passed as `None` for squat). Single function, two
branches keyed on `exercise_type`.

---

## Decision 2 — J-Curve Heuristic Boundaries for #6

### 2A. Definitions of trajectory anchor points

All x-coordinates are from the wrist-midpoint trajectory (`_wrist_midpoint_trajectory`),
already available in `_bench_metrics` as the same proxy used by `#4 bar_to_hip_distance`
in deadlift.

- `descent_start_x`: bar-x at `rep.start_frame` (first frame of the rep, bar at the top
  before descent begins).
- `bottom_x`: bar-x at the bottom frame, defined as `_find_depth_frame(elbow_series, start, end)`.
  This reuses the identical bottom-frame already computed for `elbow_angle_at_bottom` — no
  new bottom-frame computation.
- `ascent_end_x`: bar-x at `rep.end_frame` (final frame of the rep, bar back at top after
  ascent completes).

Frame-width normalization: MediaPipe normalizes x to [0, 1], so `frame_width = 1.0`.
The design thresholds are already stated as fractions of frame_width, so `0.03 * 1.0 = 0.03`
and `0.02 * 1.0 = 0.02`. No additional normalization step is needed.

### 2B. Classification logic (confirmed — design v0 boundaries unchanged)

```
if ascent_end_x < bottom_x - 0.03:
    label = "j_curve"
elif abs(descent_start_x - ascent_end_x) < 0.02:
    label = "vertical"
else:
    label = "drift"
```

**Rationale for confirming design boundaries:**

- `0.03` for j-curve is a 3% frame-width displacement. In a typical 720p frame, 1% is ~7px,
  so 3% is ~21px. A bench bar swept 21px rightward in normalized space during the press is
  genuinely non-trivial and reliably distinguishes a real j-curve from noise.
- `0.02` for vertical is a 2% dead-band around the net start-end horizontal displacement.
  A lifter whose bar drifts 1% over the course of a rep is essentially vertical. Widening
  this threshold would misclassify mild drift as vertical.
- The ordering matters: j-curve is checked first (a j-curve can also have a small
  start-to-end offset and would otherwise fall through to "vertical"). Checking j-curve
  first correctly prioritizes the stronger morphological signal.

**Why not larger j-curve threshold (e.g. 0.05)?**

Normalized coordinates compress the visible path more than pixel counts suggest. A 0.05
threshold would miss moderate j-curves on wider frames or when the subject is not centered
in the frame. 0.03 is more sensitive and appropriate for a compute-only (unscored) metric
where false positives are inexpensive.

### 2C. Degenerate handling

If `bottom_frame == rep.start_frame == rep.end_frame` (single-point trajectory, or
`start_frame == end_frame`), all three anchor points are identical. The heuristic would
produce a division-by-zero-free but semantically meaningless result. Rule: if
`rep.end_frame - rep.start_frame < 2` (fewer than 3 frames), return `None` from the
classifier. `None` is stored in the per-rep dict (see Architecture section) and the
session-modal label is computed only from non-None reps.

### 2D. Synthetic trajectory confirmation (prose, no fixtures)

**Clean vertical.** Imagined trajectory: 10-frame rep, bar starts at x=0.50, descends in a
perfectly straight line to x=0.50 at bottom, returns straight to x=0.50 at end.
- `descent_start_x = 0.50`, `bottom_x = 0.50`, `ascent_end_x = 0.50`
- `ascent_end_x < bottom_x - 0.03` → `0.50 < 0.47` → False
- `|descent_start_x - ascent_end_x|` → `|0.50 - 0.50| = 0.0 < 0.02` → True
- Result: `"vertical"`. Correct.

**J-curve (bar sweeps back during ascent).** Imagined trajectory: bar starts x=0.50 at
top, descends to x=0.50 at bottom (straight path down), but on ascent sweeps to x=0.44
at end (back toward face/rack).
- `descent_start_x = 0.50`, `bottom_x = 0.50`, `ascent_end_x = 0.44`
- `ascent_end_x < bottom_x - 0.03` → `0.44 < 0.47` → True
- Result: `"j_curve"`. Correct. The bar returned to a position behind (lower x for
  right-facing lifter) the bottom position by more than 3%.

**Drift (bar shifts forward throughout).** Imagined trajectory: bar starts x=0.50,
bottom x=0.52 (slight forward shift), ascent end x=0.54 (continues drifting forward).
- `descent_start_x = 0.50`, `bottom_x = 0.52`, `ascent_end_x = 0.54`
- `ascent_end_x < bottom_x - 0.03` → `0.54 < 0.49` → False
- `|descent_start_x - ascent_end_x|` → `|0.50 - 0.54| = 0.04`, not < 0.02 → False
- Result: `"drift"`. Correct.

**J-curve precedence over near-zero net drift.** Bar starts x=0.50, bottom x=0.50,
ascent end x=0.46. Net start-to-end: 0.04 > 0.02, so not vertical. But ascent_end_x
(0.46) < bottom_x - 0.03 (0.47). Result: `"j_curve"`. Correct — the j-curve check fires
first and correctly captures the archetypical bench j-curve where the bar is pressed
back over the face.

### 2E. Side-agnosticism note

The wrist-midpoint trajectory is computed from both wrists (landmarks 15 and 16) and is
already bilateral — `_wrist_midpoint_trajectory` does not use `side_idx`. However, the
j-curve classification uses relative x-comparisons (`ascent_end_x < bottom_x - 0.03`),
not absolute x-values. The sign of "j-curve" (bar goes toward face = lower-x for a
right-facing lifter) is the same regardless of which side is filmed because x=0 is
always left and x=1 is always right in normalized MediaPipe coords.

One subtlety: for a left-facing lifter, the j-curve direction in normalized x is reversed
(bar sweeps toward higher x on the j-curve ascent). The current heuristic checks only
`ascent_end_x < bottom_x - 0.03` which catches the rightward direction. A left-facing
lifter's j-curve sweeps in the opposite x-direction.

**Resolution:** check both directions symmetrically:

```python
if abs(ascent_end_x - bottom_x) > 0.03:
    label = "j_curve"
elif abs(descent_start_x - ascent_end_x) < 0.02:
    label = "vertical"
else:
    label = "drift"
```

This replaces the one-directional `<` with `abs(...)`, making the classifier side-agnostic.
This is a correction to the design's v0 formula — the design assumed a right-facing lifter.
The symmetrized form is strictly better and the thresholds (0.03, 0.02) are unchanged.

**Mirror test implication:** a synthetic right-facing j-curve trajectory with x-coordinates
flipped to simulate a left-facing lifter (x' = 1 - x) must produce the same `"j_curve"`
label. The symmetrized formula satisfies this.

---

## Decision 3 — Consistency Metric Choice for #16

### 3A. Per-exercise metric confirmed

- **Squat:** `depth_angle` (minimum hip angle per rep, already in `metrics["depth_angle"]`).
- **Deadlift:** `lockout_torso_lean_deg` (torso-vertical angle at lockout, already in
  `metrics["lockout_torso_lean_deg"]`).

**Why not rep-duration std?**

Rep duration captures tempo variation, which is distinct from technique variation. Two reps
can have identical form but different tempos due to fatigue, intentional pause, etc.
The coaching cue for "inconsistent depth" is different from "inconsistent tempo". The
existing registry description explicitly says "chosen technique metric", and depth_angle
(squat) and lockout_torso_lean_deg (DL) are the most direct single-value indicators of
technique on each exercise.

**Why these two specifically?**

Squat: `depth_angle` is the single most important technique variable in the squat — it
determines whether a rep counts and captures any hip-hinge variation across the set.
Deadlift: `lockout_torso_lean_deg` captures the quality of the lockout, which is where
most technique breakdown is observable on the DL from the sagittal view. `hip_angle_at_bottom`
would be an alternative but is more affected by anthropometry than by consistency per se.

### 3B. Population std (ddof=0)

Use `np.std(values, ddof=0)` (population std, the numpy default). Justification:

- The reps in a set are the entire population of observations, not a sample from a larger
  population. We are not inferring a population parameter — we are describing this specific
  set. Population std is the appropriate measure.
- For very small n (2–3 reps), Bessel's correction (ddof=1) inflates the std estimate
  significantly and would produce misleading large values. A 2-rep set with reps at 85° and
  87° has population std 1.0° but sample std 1.41°; the population measure is more
  interpretable.
- The expert-portal display is compute-only and unvalidated; the smaller/more intuitive
  measure is preferred until a threshold is established.

### 3C. Single-rep → None

If only one rep is detected, `np.std([x]) = 0.0`. However, `0.0` is a misleading sentinel
in this context — it would mean "perfectly consistent" for a single rep, which is
semantically wrong (no consistency can be assessed from one observation). Return `None`
for single-rep sessions. The None-storage decision (next section) governs how this is written.

---

## Architecture & Storage

### Per-rep dict storage

The return type of all three analyzer functions is `dict[str, RepMetricValue]`, and
`extract_rep_metrics` builds a `list[RepMetrics]` from per-rep calls. Session-level values
(#16, and the session-modal label for #6) do not map naturally to per-rep storage, but the
expert panel reads `rep_metrics[key]` per row.

**Decision: write session-level values onto every rep's dict.** This is the same documented
simplification used by Session 5's single-per-session metrics (`setup_shoulder_x_offset`,
`setup_knee_angle_deg`, `arch_deg`), which are computed per-rep using that rep's own frames.

For #16, the value cannot be computed inside the per-rep analyzer call because it requires
all reps' values. A post-pass inside `extract_rep_metrics` computes it after all per-rep
metrics are available and injects the same value into every rep's dict:

```python
# Post-pass: inject session-level metrics that require cross-rep aggregation.
if ex in ("squat", "deadlift") and len(result) >= 2:
    _inject_technique_consistency_std(result, ex)
# single-rep or bench: key absent (stored as None → see None-handling below)
```

`_inject_technique_consistency_std` reads `metrics["depth_angle"]` (squat) or
`metrics["lockout_torso_lean_deg"]` (DL) from each `RepMetrics.metrics` dict in `result`,
computes `np.std(values, ddof=0)`, and writes `technique_consistency_std` into every rep.

For #6 session-modal label: the per-rep label is computed in the per-rep analyzer call.
The session-modal label is a derived value used only in smoke scripts and is NOT persisted
as a separate JSONB key. The registry has a single key `bar_path_classification` — that key
holds the per-rep label only. The session-modal is a helper for human calibration:

```python
def session_modal_bar_path_classification(rep_metrics_list: list[RepMetrics]) -> str | None:
    """Return the most common non-None bar_path_classification across reps."""
    labels = [
        rm.metrics.get("bar_path_classification")
        for rm in rep_metrics_list
        if rm.metrics.get("bar_path_classification") is not None
    ]
    if not labels:
        return None
    from collections import Counter
    return Counter(labels).most_common(1)[0][0]
```

This helper lives in `metric_extraction.py` and is called from the smoke script. It is NOT
called by `extract_rep_metrics` and does NOT write to any JSONB key.

### None-handling convention

**Decision: store `None` as JSON null (do not use 0.0 sentinel for #2 or #16). Omit the
key entirely when the exercise is not applicable.**

Rationale:

- `0.0` for `lumbar_flexion_proxy_delta_deg` means "no torso flexion change vs baseline",
  which is a valid biomechanical outcome. Storing `0.0` to signal "could not compute"
  makes these two states indistinguishable — a silent correctness bug.
- `0.0` for `technique_consistency_std` means "perfectly consistent", which is also a valid
  outcome. Using it as a "could not compute" sentinel has the same problem.
- The existing per-rep None convention (`float(x) if x is not None else 0.0`) was adopted
  for metrics where `0.0` is always a degenerate or impossible real value (e.g., angle = 0°
  is not a physically achievable rep). That convention does NOT apply to these two metrics.
- The expert panel already handles missing keys with "Not yet computed" / "—" display. The
  same display logic already handles JSON null values — the frontend `??` nullish coalescing
  in the panel's value renderer treats both missing key and null value as "no data".
- The integration test assertion "key populated (not None, not missing)" means: for the three
  atharva fixtures (which are multi-rep), `technique_consistency_std` WILL be populated with
  a non-None float, satisfying the assertion. `lumbar_flexion_proxy_delta_deg` will be
  populated for reps 2+ (DL) and all reps (squat, using global baseline from rep 0 start).

**Concrete storage rules per metric:**

- `lumbar_flexion_proxy_delta_deg`:
  - Non-None float: store as float in dict.
  - None (landmark visibility fail, degenerate geometry, or first-rep DL where liftoff also
    undetectable and start_frame landmarks are also low-vis): store `None` in dict (will
    serialize as JSON null).
  - Exercise not applicable (bench): key is absent from dict entirely.

- `bar_path_classification`:
  - Non-None string (`"vertical"`, `"j_curve"`, `"drift"`): store as str in dict.
  - None (degenerate single-point trajectory): store `None` in dict.
  - Exercise not applicable (squat, DL): key is absent from dict entirely.

- `technique_consistency_std`:
  - Non-None float (2+ reps): store as float in dict (same value in every rep's dict).
  - None (single-rep session): store `None` in dict (every rep's dict gets `None`).
  - Exercise not applicable (bench): key is absent from dict entirely.

**`RepMetricValue` type update:** the type alias is currently `float | str | dict[str, float | None]`.
The `None` sentinel for per-rep top-level keys requires widening to
`float | str | dict[str, float | None] | None`. This is a single-line type change in
`metric_extraction.py` and the corresponding test invariant
`test_all_*_metric_values_are_floats` must be updated to allow None for the three Session 7 keys.

---

## Side-Agnosticism

**#2 `lumbar_flexion_proxy_delta_deg`:**

The formula is `atan2(shoulder_x - hip_x, hip_y - shoulder_y)`. The x-component
`(shoulder_x - hip_x)` is positive when the shoulder is to the right of the hip.

For a right-facing lifter leaning forward, shoulder is anterior (to the right of hip
in the image), so `shoulder_x > hip_x` → positive numerator. For a left-facing lifter in
the same physical posture, shoulder is anterior (to the LEFT of hip in the image), so
`shoulder_x < hip_x` → negative numerator. The angle would flip sign.

**Apply `_facing_sign(lifter_side)`** to the x-component:

```python
dx = (float(shoulder[0]) - float(hip[0])) * _facing_sign(lifter_side)
dy = float(hip[1]) - float(shoulder[1])  # y increases downward; hip below shoulder → positive
angle_deg = math.degrees(math.atan2(dx, dy))
```

This gives positive values for forward lean regardless of which side is filmed.

The delta `= angle_at_bottom - angle_at_baseline` cancels any consistent offset, so the
sign-correction only matters for the raw proxy angles, but it is still correct practice to
apply it so the raw proxy angles have consistent sign across lifters filmed from either side.

**#6 `bar_path_classification`:**

Uses `abs(ascent_end_x - bottom_x)` (after the symmetrization in Decision 2E). The
`_wrist_midpoint_trajectory` is bilateral and side-agnostic by construction. The symmetrized
classifier does not require `_facing_sign`. No further action needed.

**#16 `technique_consistency_std`:**

Uses `depth_angle` (squat) and `lockout_torso_lean_deg` (DL). Both are joint-angle or
cosine-derived magnitudes — no x-component. Side-agnostic by construction.

---

## Open Risks Deferred to Calibration Mini-Session

Per design Section 5 and skeleton plan Task 12, the following are NOT resolved in this spike
but must be documented in the post-merge handoff:

**R-CAL-1 (lumbar proxy sign interpretation):**
The proxy angle measures composite trunk flexion, not true lumbar flexion. For some
exercises/anthropometries, a high-visibility lifter may show a non-zero baseline proxy angle
(e.g., natural lordosis creates a small `shoulder_x != hip_x` even while standing upright).
The delta should still be interpretable (change from standing to bottom), but if the standing
baseline posture is unusual, the delta magnitude may be larger or smaller than expected.
Calibration acceptance criterion: delta for a textbook clean squat (the Atharva squat
fixture) should be between 0° and 25°. If delta > 40° on a visually clean squat, escalate.

**R-CAL-2 (j-curve direction for left-facing lifter on Atharva bench fixture):**
The Atharva bench fixture's lifter_side must be confirmed as "right" by Session 2's
`detect_lifter_side`. If it is "left", the symmetrized formula in Decision 2E must produce
the same classification. The smoke script should dump `lifter_side` alongside the label.

**R-CAL-3 (consistency std units):**
`lockout_torso_lean_deg` has a meaningful std only if there are 2+ reps with reliably
measured lockout lean. If the Atharva deadlift fixture has only 1 detected rep (check
fixture), the metric returns `None` and the integration test assertion "key populated (not
None, not missing)" would fail. Mitigation: confirm fixture has 2+ reps before writing the
integration test assertion.

**R-CAL-4 (wrist-midpoint as bar-x proxy for bench):**
The j-curve heuristic uses wrist-midpoint x, not a detected barbell circle center. On the
Atharva bench fixture, if the lifter's grip is unusually wide or the wrist midpoint tracks
differently from the bar, the classification may be unreliable. Document the actual wrist-x
trajectories in the smoke script output.

---

## Cross-References

- Skeleton plan: `docs/superpowers/plans/2026-05-22-session-7-complex-multi-frame.md` Tasks
  1–3 (spike), 3 (`identify_standing_baseline_frame`), 4 (lumbar extractor), 5 (j-curve
  classifier), 6 (bar-path extractor), 7 (consistency extractor), 8 (mirror tests), 9
  (registry flags), 10 (integration tests), 11 (smoke script).
- Design spec Section 4: metric math definitions for #2, #6, #16.
- Design spec Section 5: testing strategy (synthetic unit tests + integration + smoke).
- ADR-LUMBAR-FLEXION-PROXY-NAMING (to be created in Session 7 Task 17): must capture the
  DL first-rep decision (pre-liftoff baseline, fallback to start_frame) and the naming
  honesty constraint.
- `backend/app/cv/metric_extraction.py`: all changes land here.
- `backend/app/cv/sagittal_metrics_registry.py`: flip `computed_yet=True` for the three
  Session 7 entries.

---

## Implementation Checklist (for TDD expansion)

In order, matching skeleton plan tasks:

1. `identify_standing_baseline_frame(exercise_type, rep, rep_position, all_reps, bar_y_series)` — helper.
2. `extract_lumbar_flexion_proxy_delta_deg(landmarks_per_frame, rep, rep_position, all_reps, bar_y_series, side_idx, lifter_side)` — returns `float | None`.
3. `_classify_bar_path(descent_start_x, bottom_x, ascent_end_x)` — returns `str | None`. Symmetrized formula.
4. Integrate `bar_path_classification` into `_bench_metrics` (call with wrist-midpoint x at the three anchor frames).
5. `_inject_technique_consistency_std(result: list[RepMetrics], exercise_type: str)` — post-pass, in-place mutation of each rep's metrics dict.
6. Wire `lumbar_flexion_proxy_delta_deg` into `_squat_metrics` and `_deadlift_metrics` (new optional args `all_reps`, `rep_position`).
7. Wire `_inject_technique_consistency_std` into `extract_rep_metrics` post-loop.
8. Update `extract_rep_metrics` to pass `all_reps=reps, rep_position=i` to squat/DL analyzers.
9. Widen `RepMetricValue` to include `None`.
10. Flip registry flags.
