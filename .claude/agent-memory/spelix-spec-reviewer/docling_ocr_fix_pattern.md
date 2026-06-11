---
name: docling-ocr-fix-pattern
description: Issue #263 two-step fix — artifacts_path (PR #268) + onnxruntime dep (617034f); CPU-only wheel via docling[rapidocr] extra
metadata:
  type: project
---

Issue #263 was fixed in two commits:
- PR #268: set DOCLING_ARTIFACTS_PATH so RapidOCR doesn't write into read-only site-packages.
- Commit 617034f: add `docling[rapidocr]` extra so onnxruntime CPU wheel is in the locked dep set.

The `[rapidocr]` extra maps to `docling-slim[feat-ocr-rapidocr-onnx]` which pulls
`onnxruntime>=1.7.0,<2.0.0` (plain CPU, NOT onnxruntime-gpu).
uv.lock confirms: package name is `onnxruntime` (not `onnxruntime-gpu`), version 1.26.0,
marker `python_full_version < '3.14'`.

Regression tests use `importlib.util.find_spec("onnxruntime")` — correct guard;
returns None only when the wheel is absent from the venv.
Second test pins `RapidOcrOptions.model_fields["backend"].default == "onnxruntime"` — drift guard.

**Why:** Lock-only fix means the test would fail in CI if onnxruntime is ever dropped from the lock.
**How to apply:** When reviewing similar "missing dep" fixes, verify (1) package name is CPU not GPU wheel,
(2) lock churn is scoped to new dep + its transitive deps only, (3) test uses find_spec not a try/import.
