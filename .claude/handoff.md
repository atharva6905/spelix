# Phase 1 Handoff — Session 9

## Completed

| Task | Commit | Description |
|------|--------|-------------|
| Fix confidence tier tests | `d3d6125` | Tier 4 transition multiplier + high-visibility label + pipeline presence column |
| Batch 3A: Exercise auto-detect | `561b1fd` | FR-XDET-03/04/07 — heuristic detector + GPT-4o fallback + pipeline Step 2b + migration 003 |
| Batch 3B: PDF Phase 1 extension | `1c66408` | FR-XPRT-02 — score pills, safety warnings, recommended cues, citations, worker context |
| Batch 3C: Body stats complete | `d8be6ff` | FR-PROF-06 — add arm_span_cm + femur_length_cm to worker fetch |
| OPENAI_API_KEY env | `5299944` | Added to .env.example |

## Test counts

- **Backend**: ~848 tests (848 passed, 2 skipped, 0 failures — excluding test_repositories which needs migration 003)
- **test_repositories**: 1 failure expected until `alembic upgrade head` applies migration 003 (detection_result column)
- **New tests added this session**: 15 (exercise detection) + 6 (classify_exercise) + 1 (body stats anthropometrics) + 9 (PDF Phase 1) + pipeline/confidence fixes = 31+ new tests

## Remaining

### Batch 4 — Test Coverage & Polish (NOT STARTED)
| Task | Description |
|------|-------------|
| Run migration 003 | `alembic upgrade head` to add detection_result JSONB column |
| GPT-4o fallback wiring | Pipeline Step 2b currently runs heuristic only — need to wire fallback: if heuristic confidence < 0.7, call `classify_exercise()` with first 3 frame images |
| Integration tests for SSE endpoint | httpx AsyncClient end-to-end |
| GPT-4o mock integration tests | Full pipeline with mocked OpenAI |
| 95%+ coverage gate | Coverage sweep |
| Frontend FR-XDET-07 | Display detection_result on upload confirmation screen |

### Phase 1 — Remaining SRS items
- FR-XPRT-02 bar path chart (requires bar path coordinate data, not just summary scalars)
- FR-XPRT-02 keyframe captures in PDF (pipeline_result.keyframes → PDF context)
- FR-XPRT-02 user_info in PDF header (from user profile)

## Architecture Notes

### Exercise Auto-Detection Flow (new)
```
Pipeline Step 2: extract_landmarks() → landmarks_per_frame
Pipeline Step 2b: detect_exercise_heuristic(landmarks_per_frame)
  → DetectionResult(detected_type, detected_variant, confidence, method, details)
  → Stored as analysis.detection_result JSONB
  → If confidence < 0.7: TODO wire GPT-4o classify_exercise() fallback
Pipeline Step 3: quality_gates (uses original analysis.exercise_type, not detection)
```

### PDF Phase 1 Data Flow
```
Worker → _generate_and_upload_pdf():
  context["scores"] = {form_score_safety, technique, path_balance, control, overall}
  context["coaching"] includes safety_warnings, recommended_cues, citations
  → PDFService.render_html() builds:
    - _build_score_pills() → overall rating + 4 dimension pills
    - _build_safety_warnings() → Movement Quality Alerts banner
    - _build_recommended_cues() → coaching cues section
    - _build_sources_block() → formatted citations from coaching.citations
```

### Key design decisions
- Exercise detection runs AFTER pose extraction but BEFORE quality gates
- Detection result stored for FR-XDET-07 display but does NOT override user-selected exercise_type
- PDF score pills use same descriptor thresholds as scoring.py (Elite ≥9.0, Advanced ≥7.5, etc.)
- Sources block now renders coaching.citations (Phase 1) or falls back to context.sources
- Body stats fetch now includes all 6 profile fields (was missing arm_span_cm, femur_length_cm)

## Blockers

- Migration 003 needs `alembic upgrade head` on Supabase before test_repositories passes
- GPT-4o fallback in pipeline not yet wired (heuristic-only currently)

## Next session start

```bash
# 1. Apply migration 003
alembic upgrade head

# 2. Wire GPT-4o fallback in pipeline Step 2b (if heuristic confidence < 0.7)
# 3. Add keyframe captures + bar path chart to PDF (remaining FR-XPRT-02 items)
# 4. Start Batch 4: integration tests, coverage gate
```
