# Squat deep-bottom occlusion — root cause + oblique/3D direction (2026-05-25)

**Status:** Investigation complete. Direction validated and **parked** (build deferred — competes with mid-May internship apps; see decision below).

**TL;DR.** The squat-bottom metric dropout that R1/R2/R5 mitigated is caused by the **loaded barbell plate occluding the lifter's torso/hips from a sagittal (pure-side) camera** — not limb self-occlusion, and not a pose-model weakness. No 2D pose model (BlazePose or RTMPose) can see through the plate. The fix is a **capture-angle change (front-oblique ~45°) + accurate monocular 3D pose**. BlazePose's own 3D is too weak (~10.6° body-angle error, depth-compressed, inconsistent bone lengths); **MeTRAbs** gives anatomically-stable 3D (bone-length CV <1–2% at good resolution) and was validated across 7 clips / multiple angles. The only blocker is compute: MeTRAbs is ~3 s/frame on CPU → needs a **serverless-GPU offload** (cost ≈ free at beta scale; effort ~2–3 weeks, dominated by a 2D→3D scoring rewrite).

---

## 1. The problem

Deep-squat reps lose every bottom-anchored metric (depth angle, knee-at-depth, lumbar proxy). R1 (dropout-aware depth-frame), R2 (angle-series validity gate + interpolation), R5 (surface the interpolation fraction) all *mitigate* downstream — none recover the lost joint positions. This investigation asked whether the loss is recoverable at all.

## 2. What was already tried (R1–R6, prior sessions)
- **R1** dropout-aware depth-frame selection; **R2** NaN-gate + linear-interpolate + clamp; **R5** surface per-rep confidence + interpolation fraction; **R6** deadlift first-rep baseline; **R3** bench bar-path None-interim. All downstream/gating. See `decisions.md` ADR-DEPTHFRAME-DROPOUT-GATE, ADR-ANGLE-SERIES-VALIDITY-GATE, ADR-R5-CONFIDENCE-INTERP-SURFACING.

## 3. This session's findings

### 3a. R4 — MediaPipe VIDEO vs IMAGE running mode → no change
Hypothesis: VIDEO mode's inter-frame bbox tracker drops the pose at the bottom; IMAGE mode would re-acquire. **Falsified.** Local sniff test (`scripts/oneoff/r4_running_mode_sniff.py`) on the real fixtures:

| fixture | mode | fully-dropped | invalid-frame % (R2 predicate) |
|---|---|---|---|
| squat | VIDEO | 13.8% | 47.6% |
| squat | **IMAGE** | **45.1%** | **69.0%** |
| bench / deadlift | either | ≈equal | ≈equal |

IMAGE is **worse** (the tracker is actually *mitigating* occlusion), and no latency win. → keep VIDEO. See ADR-CV-RUNNING-MODE-NO-CHANGE.

### 3b. RTMPose (Halpe-26) swap → dead end, and it revealed the real root cause
`scripts/oneoff/rtmpose_squat_sniff.py` (rtmlib, CPU). Top-down RTMPose never "drops" (0% fully-dropped) but at the deep bottom its confidence collapses to ~0.15 — and the **overlay showed why: the 45 lb bumper plate completely occludes the torso/hips from the side; only the shoes are visible.** This is plate occlusion, not limb self-occlusion or model weakness. RTMPose also ran ~8× slower than BlazePose on CPU. → no model swap fixes a pure-side view.

### 3c. Oblique (~45°) camera clears the plate
On a front-oblique clip (`olympic-squat-sample.mp4`, a 260 kg ATG squat), `scripts/oneoff/squat_3d_oblique_sniff.py`: **0% dropout, joint visibility 0.90–1.00 at the deepest frame** (vs ~0.15 collapse on pure-side). The camera sees around the plate to the full leg/torso chain. 2D angles from the oblique view are perspective-biased (~6° drift), but the depth channel is recoverable.

### 3d. BlazePose 3D is too weak; MeTRAbs is the right model
BlazePose `pose_world_landmarks` are depth-compressed/tangled (literature: ~10.6° body-angle error, inconsistent bone lengths, weak at the movement apex). **MeTRAbs** (`metrabs_l`, h36m_17) on the same frames gave a clean, anatomically-stable 3D pose.

**Validation across 7 clips** (`scripts/oneoff/metrabs_spike.py`, `metrabs_spike_multi.py`):

| clip set | angle / res | detection | bone-length CV |
|---|---|---|---|
| olympic-squat-sample | front-oblique 360p (narrow window) | 100% | **<1%** |
| 3 corpus (side/oblique/rear) | mixed 360p | 100% | 2–10% (full rep range) |
| 3 front-oblique (2×360p, 1×720p) | front-oblique | 100% | **0.8–5%** (720p best) |

Consistent: 100% detection across angle/lighting/lifter (incl. dark rear), anatomically coherent 3D, smooth descent→bottom→ascent angle traces. **Higher input resolution tightens 3D** (720p → <2% CV vs 4–10% at 360p). Residual weak spot: the far/occluded-side thigh (~5% CV) — the known monocular limitation, improvable with temporal/biomechanical smoothing.

## 4. Cost & effort to productionize (Phase 2 — serverless-GPU MeTRAbs offload)
- **Compute cost ≈ free.** MeTRAbs ~28 FPS on a 3090, ~10–15 FPS (more batched) on a T4 (~$0.000164/s). ~$0.01–0.02/analysis; ~$3–6/month at <10/day, covered by Modal's $30/mo free credits. Cold start adds ~10–30 s latency (fine — coaching is already async). Sources: modal.com/pricing, github.com/isarandi/metrabs#25.
- **Engineering effort ~2–3 weeks**, dominated by **risk**: (a) build+deploy the Modal GPU service [~1–2 d], (b) async worker integration [~1–2 d], (c) **2D→3D angle computation** in `metric_extraction`/`signal_processing`/`rep_detection` [~3–5 d, high risk], (d) **threshold + 4-dimension scoring recalibration** for 3D angles [~2–4 d, high risk], (e) front-oblique capture guidance + angle quality gate [~1–2 d], (f) rep-detection retune + fixtures + tests [~2–3 d]. The hard part is that 3D angles change the meaning of every metric → the scoring foundation must be re-derived/re-validated. Best done as a **squat-only 3D path behind a feature flag** to limit blast radius.

## 5. Decision (2026-05-25)
**Document & pause.** Cost is a non-issue; the ~2–3-week core-pipeline rewrite competes directly with the mid-May internship-application window. The direction is fully de-risked and ready to build post-internship or in a dedicated block. See ADR-CV-OBLIQUE-3D-DIRECTION.

## 6. Reproduction
Throwaway scripts in `backend/scripts/oneoff/` (ad-hoc deps `rtmlib`, `onnxruntime`, `tensorflow`, `tensorflow_hub`, `yt-dlp` installed via `uv pip install` — venv-only, `pyproject.toml`/`uv.lock` untouched; `uv sync` prunes them; run with `uv run --no-sync`):
- `r4_running_mode_sniff.py` — VIDEO vs IMAGE dropout.
- `rtmpose_squat_sniff.py` — RTMPose Halpe-26 CPU; revealed plate occlusion.
- `squat_3d_oblique_sniff.py` / `render_full_skeleton.py` — BlazePose 3D world-landmarks on the oblique clip.
- `metrabs_probe.py` / `metrabs_spike.py` / `metrabs_spike_multi.py` — MeTRAbs validation (set `TFHUB_DISABLE_CERT_VALIDATION=true` on Windows; model `https://bit.ly/metrabs_l`, skeleton `h36m_17`).
- Test-clip corpus: see `e2e/fixtures/CORPUS.md`.
