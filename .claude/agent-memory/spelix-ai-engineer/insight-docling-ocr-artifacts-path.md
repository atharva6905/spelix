---
name: insight-docling-ocr-artifacts-path
description: #263 — Docling RapidOCR writes its OCR model into site-packages unless artifacts_path is pinned; prod read-only venv → every ingest_paper crashed
metadata:
  type: project
---

Docling 2.93 default `DocumentConverter()` runs OCR via the `auto` resolver →
RapidOCR. With NO explicit model paths, RapidOCR 3.x downloads its model into
its own package dir inside the venv. The prod container is non-root + read-only
venv → `PermissionError [Errno 13]` on the `.pth` OCR model → every
`ingest_paper` task failed since launch (all rag_documents had chunk_count=0).

**Why:** issue #263, found during the sex-aware deploy runbook (2026-06-11).

**How to apply (the fix mechanism, verified against installed docling source):**
- In `RapidOcrModel.__init__`, IF `artifacts_path` is set, docling builds
  explicit `Det/Cls/Rec.model_path` = `artifacts_path/RapidOcr/<file>` and
  passes them to `RapidOCR(params=...)`. RapidOCR then uses those local files
  and never triggers its own download. Setting `artifacts_path` is the lever.
- `app/services/pdf_extraction.py::_build_converter()` constructs the converter
  with `PdfPipelineOptions(artifacts_path=DOCLING_ARTIFACTS_PATH, ocr_options=RapidOcrOptions())`.
  `artifacts_path` must NEVER be None (None = the crash path). Default
  `/app/models/docling`.
- Dockerfile bakes models at build via `docling-tools models download layout
  tableformer rapidocr -o /app/models/docling` and sets
  `ENV DOCLING_ARTIFACTS_PATH=/app/models/docling`, chowned to `spelix`.
- Default docling lang is `["chinese"]`; onnxruntime model set lives under
  `<artifacts>/RapidOcr/onnx/PP-OCRv4/...`. `_model_repo_folder='RapidOcr'`.
- Regression test: `tests/unit/test_paper_ingestion.py` asserts the converter's
  PDF pipeline_options carries a non-site-packages `artifacts_path` and pins
  `ocr_options.kind == 'rapidocr'`. First run is slow (~85s) — app import cost.

**SECOND failure (same #263, fixed in commit 617034f):** once artifacts_path
pins the ONNX model set, Docling drives RapidOCR via its DEFAULT engine
`EngineType.ONNXRUNTIME` (from `RapidOcrOptions.backend == "onnxruntime"`) and
calls `RapidOCR(params={... 'Det.engine_type': onnxruntime ...})`. At reader
init RapidOCR does `get_engine(cfg.engine_type)` → raises
`ImportError("onnxruntime is not installed.")` if the wheel is absent. The OLD
broken path used torch `.pth` models so onnxruntime was never needed; pinning
ONNX artifacts made it mandatory.
- Fix: change `docling` → `docling[rapidocr]` in pyproject (the
  `feat-ocr-rapidocr-onnx` extra pins CPU `onnxruntime<2.0.0,>=1.7.0` on
  linux/win + rapidocr). Do NOT use `docling[onnxruntime]` — that extra
  (`models-onnxruntime`) pulls `onnxruntime-gpu` on linux. CPU wheel is right
  for the 4GB droplet. Then `uv lock`.
- TRAP that masked RED locally: `onnxruntime` was physically present in the
  LOCAL dev venv (stray ad-hoc install, v1.26.0) but ABSENT from `uv.lock`, so
  `importlib.util.find_spec('onnxruntime')` passed locally yet prod's
  `uv sync --frozen --no-dev` excluded it. Verify against `uv.lock`
  (grep onnxruntime), not the live venv, when reasoning about what prod gets.
- TRAP: ruff PostToolUse strips a just-added import if you add it in a separate
  edit BEFORE the edit that uses it. Add `import importlib.util` in the SAME
  edit as its first usage (cost one fix iteration here).

**Related:** #222 / #223 DB↔Qdrant identity work assumed papers exist; none did
on prod because of this bug. Orphan-seed sweep is #263 follow-up item 3.
