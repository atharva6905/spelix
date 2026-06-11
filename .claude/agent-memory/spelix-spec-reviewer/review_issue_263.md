---
name: review_issue_263
description: Spec review of issue #263 — Docling RapidOCR PermissionError fix (bake models + writable artifacts path): PASS, 2026-06-11
metadata:
  type: project
---

## Reviewed: issue #263 (Docling OCR models baked at build time, 2026-06-11) → PASS

Branch: fix/issue-263-docling-ocr-models. Commit: 8d296f2.

**Requirements verified:**

Fix direction 1 only (scope given):
1. DOCLING_ARTIFACTS_PATH env set in Dockerfile (ENV DOCLING_ARTIFACTS_PATH=/app/models/docling) → DONE (Dockerfile:83)
2. Models pre-baked at build time (docling-tools models download layout tableformer rapidocr -o /app/models/docling) → DONE (Dockerfile:84-87)
3. /app/models/docling chowned to spelix user so runtime writes are allowed if ever needed → DONE (Dockerfile:94, -R flag added)
4. _build_converter() in pdf_extraction.py reads DOCLING_ARTIFACTS_PATH (never None — hardcoded /app/models/docling default) → DONE (pdf_extraction.py:36)
5. RapidOcrOptions() explicitly set (not 'auto' resolver) → DONE (pdf_extraction.py:53)
6. _extract_sync uses _build_converter() instead of bare DocumentConverter() → DONE (pdf_extraction.py:65)
7. TDD gate: uv run pytest tests/unit/test_paper_ingestion.py -x → 3 tests, all hit _build_converter() directly → DONE

**Test regression guard analysis:**
- test_build_converter_sets_writable_artifacts_path: sets env, calls _build_converter(), reads format_to_options[InputFormat.PDF].pipeline_options.artifacts_path → fails if artifacts_path dropped or None
- test_build_converter_configures_rapidocr_backend: checks ocr_options.kind == "rapidocr" → fails if RapidOcrOptions() removed
- test_build_converter_default_artifacts_path_is_not_site_packages: no env override, asserts artifacts_path not None and "site-packages" not in path → fails if default removed or set to None

All 3 tests would fail if the guard config were removed. Tests are direct unit tests of the function itself (no mocks of the function under test).

**Out-of-scope items correctly excluded:**
- Re-enqueue 4 approved chunk_count=0 rows — explicitly OUT OF SCOPE, not in diff
- Orphan seed point sweep — explicitly OUT OF SCOPE, not in diff

**No OVER-BUILT scope detected.** Only pdf_extraction.py, Dockerfile, and new test file changed.

**Patterns worth noting:**
- The test imports `pdf_extraction.InputFormat` (exposed via module-level `from docling.datamodel.base_models import InputFormat`) — works because the import is at module top, not deferred. This is an intentional design choice (base_models is cheap to import; it's the heavy pipeline that's deferred inside _build_converter).
- The third test (`test_build_converter_default_artifacts_path_is_not_site_packages`) does NOT unset DOCLING_ARTIFACTS_PATH before running. If a prior test in the same session sets the env var, this test could pass even with a broken default. However, monkeypatch in pytest is function-scoped and automatically undone between tests, so this is safe.
- `chown -R` on /app/models/docling is correct — the pre-baked models must be readable by the spelix user. /app/models/pose_landmarker_heavy.task is NOT in the chown list but that's pre-existing (not changed by this diff) and out of scope.
