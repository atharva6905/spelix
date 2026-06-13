# Docling model-weight checksum (issue #269 / PR #290) — 2026-06-13 → PASS

Final security gate (spec→quality→security) on the 5-file diff (merge dbbb99c). PASS, no CRITICAL/HIGH. CI Deploy build passed → the verify ran against a real download end-to-end.

## RESOLVES the standing HIGH from #263/#268
The build-time `docling-tools models download layout tableformer rapidocr` had NO hash
verification (asymmetric with BlazePose `sha256sum -c`). PR #290 closes it:
- `Dockerfile` (~L95-102): `COPY docling_models.sha256 ./docling_models.sha256` (lands at
  `/app/docling_models.sha256`) + appended `&& cd /app/models/docling && sha256sum -c
  /app/docling_models.sha256` as the LAST clause of the download `RUN`'s `&&` chain.
- Not bypassable: verify runs AFTER download, `cd` first so `./`-relative manifest paths
  resolve, absolute manifest path in the check. `sha256sum -c` exits non-zero on ANY
  mismatch/missing file → Docker `RUN` fails the build. No `|| true`, no leading-check,
  no no-op path.
- The #263 standing HIGH is CLOSED — do NOT re-report unless this verify clause is removed,
  reordered before the download, or rendered non-failing.

## Standing note (NON-blocking, accepted-as-ratchet)
The 27 expected hashes were captured from the CURRENT PROD image
(`sha256sum /app/models/docling/**`, excluding `.cache/`, in live `spelix-worker-1`). The
prod image was itself built from the same unverified download → this is trust-on-first-use
(TOFU): it FREEZES the current state, it does NOT prove the baseline is pristine. Honest
judgment: genuine improvement against the *stated* threat (FUTURE substitution / corruption
/ MITM of the download), NOT theater, but the TOFU caveat is real. Same posture as the
BlazePose hash (also hand-captured once). The ADR documents the limitation honestly
(extra-unlisted-file gap, docling-version coupling, regenerate-from-trusted-run).
RECOMMENDATION (future, not blocking): move to an upstream-published hash anchor if
HuggingFace ever exposes one for these docling model revisions — would replace TOFU with a
real provenance anchor.

## Clean dimensions
- Completeness: all loaded weights covered — layout `model.safetensors`, BOTH tableformer
  safetensors (accurate+fast), all RapidOCR onnx (5) + pth (5) + vocab txt + font. `.cache/`
  exclusion correct (non-deterministic ETags/timestamps, not loaded). Extra-unlisted-file
  gap documented + correctly judged acceptable (docling loads only the manifested set; an
  unreferenced dropped file is never executed). Count 27 = manifest = test = ADR.
- Secrets: NONE. sha256 digests are public, not secret. No keys in any of the 5 files.
- SaMD: N/A — infra-only, zero injury/medical language in ADR/comment/test.
- `.gitattributes`: scoped to the single file (`docling_models.sha256 text eol=lf`), NOT a
  broad `* text=auto` — correct. Closes the Windows CRLF-reintroduction risk; byte-level
  `test_manifest_has_no_carriage_returns` backstops it.
- DOCLING coupling: manifest is coupled to the docling version pinned in uv.lock — a bump
  that changes model revisions WILL (by design) break this build step until the manifest is
  regenerated from a trusted run. Intended forcing function. RE-REVIEW trigger: any docling
  version bump PR must regenerate the manifest from a trusted freshly-built image, NOT from
  a dev laptop. If a docling-bump PR edits docling_models.sha256 without an SSH-from-prod /
  trusted-build provenance note, FLAG it (manifest could be poisoned at regeneration time).
