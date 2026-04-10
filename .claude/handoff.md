# Phase 1 Handoff — Session 10 (Batch 4 Complete)

## Completed this session

| Task | Commit | Description |
|------|--------|-------------|
| GPT-4o fallback wiring | `3831950` | FR-XDET-04 — heuristic conf < 0.7 triggers GPT-4o classify_exercise |
| SSE endpoint integration tests | `9a712ff` | FR-AICP-07 — 5 httpx AsyncClient tests for coaching SSE endpoint |
| PDF Phase 1 completion | `b221b9b` | FR-XPRT-02 — bar path chart, keyframe captures, user_info header |
| FR-XDET-07 detection display | `52a2b0b` | Backend schema + frontend UI for detected exercise on status page |

### Prior sessions (cumulative)
| Task | Commit | Description |
|------|--------|-------------|
| Fix confidence tier tests | `d3d6125` | Tier 4 transition multiplier + high-visibility label |
| Batch 3A: Exercise auto-detect | `561b1fd` | FR-XDET-03/04/07 — heuristic + GPT-4o + migration 003 |
| Batch 3B: PDF Phase 1 extension | `1c66408` | FR-XPRT-02 — score pills, warnings, cues, citations |
| Batch 3C: Body stats complete | `d8be6ff` | FR-PROF-06 — anthropometrics fetch |

## Test counts

- **Backend**: 865 passed, 2 skipped, 0 failures (excluding test_repositories)
- **Frontend**: 168 passed, 0 failures
- **Coverage**: 91% backend (exceeds 90% target)
- **New tests this session**: 4 (GPT-4o fallback) + 5 (SSE endpoint) + 8 (PDF blocks) + 2 (detection_result API) = 19

## Remaining

### Outstanding blockers (infra only)
| Task | Description |
|------|-------------|
| Run migration 003 | `alembic upgrade head` to add detection_result JSONB column to Supabase — required before test_repositories passes |

### Phase 1 — All MUST requirements now implemented in code
- [x] FR-XDET-03 (heuristic detection)
- [x] FR-XDET-04 (GPT-4o vision fallback)
- [x] FR-XDET-07 (display detected exercise)
- [x] FR-XPRT-02 (full Phase 1 PDF: scores, warnings, cues, citations, bar path, keyframes, user_info)
- [x] FR-AICP-07 (SSE streaming coaching — code and tests)

## Architecture Notes

### FR-XDET-07 Data Flow
```
Worker: pipeline.run_cv_pipeline()
  → Step 2b: detect_exercise_heuristic() → DetectionResult
  → If conf < 0.7: KeyframeAnalysisService.classify_exercise() (GPT-4o)
  → analysis.detection_result (JSONB)
API: GET /api/v1/analyses/{id}/status
  → AnalysisStatusResponse.detection_result: DetectionResultSchema
Frontend: useAnalysisStatus hook
  → exposes detectionResult
  → AnalysisStatusPage renders "Detected Exercise" card
```

### PDF Phase 1 Context Keys (worker → PDFService)
```python
context = {
  "scores": {...},                 # Batch 3B
  "coaching": {..., safety_warnings, recommended_cues, citations},  # Batch 3B
  "user_info": "Experience · cm · kg",  # Session 10
  "bar_path_plot_path": "/tmp/.../bar_path.png",  # Session 10 (matplotlib)
  "keyframes": [RepKeyframes(...)],  # Session 10 (JPEG base64 embedded)
}
```

## Blockers

- Migration 003 needs `alembic upgrade head` on Supabase before test_repositories passes (infra task)

## Next session start

```bash
# 1. Apply migration 003
alembic upgrade head

# 2. Verify test_repositories passes
uv run pytest tests/unit/test_repositories.py -x

# 3. End-to-end smoke test via Docker
docker compose up -d
# Upload a video, verify PDF + detection display work end-to-end

# 4. Consider Phase 1 → Phase 2 transition gate
# (RAG infrastructure, Qdrant, document ingestion)
```
