---
description: CV pipeline hard invariants
paths:
  - "backend/app/cv/**"
---
# CV Pipeline Invariants

- Always use the `spelix-cv-engineer` agent for tasks in this directory.
- MediaPipe: Tasks API only (never legacy `solutions`), BlazePose Heavy, all calls via `run_in_executor` — never block the worker loop.
- VIDEO mode over IMAGE mode for squat occlusion (do not retry IMAGE).
- Memory budget: 4GB droplet — stream tracking, 720p annotation, 480p HoughCircles (ADR-056/057 lineage).
- Gate rep-bottom argmin on visibility (dropout frames); NaN-gate+interpolate+clamp angle series upstream of rep detection (squat+DL only).
- Rep-detection knobs flow through ThresholdConfig, never hardcoded (ADR-REPDET-04).
- Scope is sagittal-observable only; frontal-plane metrics are deferred to multi-camera.
- Sub-agents skip the slow MediaPipe integration suite; main agent runs it before merge.
