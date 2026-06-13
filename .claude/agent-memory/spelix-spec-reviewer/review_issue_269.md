---
name: review_issue_269
description: Spec review of issue #269 — Docling model-weight checksum manifest (supply-chain integrity, no-FR): PASS, 2026-06-13
metadata:
  type: project
---

## Reviewed: issue #269 (Docling model-weight sha256 manifest, 2026-06-13) → PASS

Branch: fix+issue-269-docling-checksum-verify. Commit: af72599.

**Requirements verified (all PASS):**

1. Post-download `sha256sum -c` verification in Dockerfile — chained via `&&` in same RUN layer; exits non-zero on mismatch, aborting the build. DONE (Dockerfile:97-102).
2. Verification ordered AFTER the download command (same `&&` chain). DONE.
3. Committed manifest referenced by the verify step (`sha256sum -c /app/docling_models.sha256`). DONE.
4. Manifest COPYed into the image before the RUN layer that verifies it (`COPY docling_models.sha256 ./docling_models.sha256` at line 95). DONE.
5. BlazePose pattern mirrored (`sha256sum -c` semantics, fails on mismatch). DONE.
6. Docling download command unchanged (`layout tableformer rapidocr -o /app/models/docling`). DONE.
7. BlazePose line untouched (line 74 not in diff). DONE.
8. Manifest: exactly 27 lines, all valid `[0-9a-f]{64}  ./...` format, no `.cache/huggingface` paths,
   critical weight files present (layout safetensors, tableformer accurate + fast safetensors, onnx, pth). DONE.
9. Scope: exactly 4 files (Dockerfile, docling_models.sha256, test file, decisions.md). DONE.
10. Tests: 6 non-vacuous tests covering manifest well-formedness, 27-entry count, no HF cache paths,
    critical weight files, and Dockerfile COPY+verify ordering. DONE.
11. ADR index row under "Infra & Ops" + ADR body section. DONE.

**No OVER-BUILT scope.** No app code, CI, schemas, hooks, or settings touched.

**Pattern notes:**
- The verify step runs `cd /app/models/docling && sha256sum -c /app/docling_models.sha256` because
  manifest paths are `./`-relative, so the CWD must be the model dir. This is correct.
- The decisions.md cross-link rule (superseded ADRs must back-reference) does NOT apply here —
  this is a new ADR, not superseding an existing one.
- The task explicitly stated no FR-ID; absence of FR-ID is not a finding for this issue type.
- Manifest is coupled to docling version in uv.lock by design (forcing function for version bumps).
  Documented in both Dockerfile comment and ADR consequences section.

**Related:** [[review_issue_263]] (original Docling bake-at-build fix), [[docling-ocr-fix-pattern]]
