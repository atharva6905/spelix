# Docling weight checksum manifest (issue #269 / PR #290) — 2026-06-13 → PASS

T2 deploy-infra security hardening. Quality gate (2nd of spec→quality→security). PASS with 1 MEDIUM + 1 LOW, **both fixed in-loop before merge**.

## The durable lesson: static-guard-vs-CRLF blind spot (the MEDIUM)
For any committed file whose correctness depends on byte-exact **LF** endings (checksum
manifests, here-doc fixtures, anything fed to a line-oriented Unix tool), a Python
format test that does `text.split("\n")` + a `re.match(r"...\.+$")` does **NOT** catch a
trailing `\r`: `.+` happily consumes the `\r` and `$` matches after it. So the guard
passes green locally while the real Linux `sha256sum -c` looks for `./path\r`, fails to
find it, and aborts the build — a failure that only surfaces at CI Deploy, not in the
unit suite. The robust guard is twofold:
1. A `.gitattributes` `eol=lf` pin on the file (prevents a Windows `core.autocrlf=true`
   re-commit from ever reintroducing CRLF) — this is the real fix.
2. A byte-level regression test (`raw = path.read_bytes(); assert b"\r" not in raw`) as
   a backstop so a regression trips a unit test, not the deploy build.
Found here as MEDIUM; fixed with `backend/.gitattributes` (`docling_models.sha256 text
eol=lf`) + `test_manifest_has_no_carriage_returns`.

## Verified-good architecture (cleared, do not re-flag)
- Dockerfile wiring: WORKDIR `/app` + `COPY docling_models.sha256 ./docling_models.sha256`
  → `/app/docling_models.sha256`; verify appended to the download RUN's `&&` chain with
  `cd /app/models/docling` first so the `./`-relative manifest paths resolve; non-zero
  exit aborts the build. Mirrors the BlazePose `sha256sum -c` precedent (Dockerfile ~L74).
- Determinism: excluding `*/.cache/huggingface/**` (timestamps/ETags) is the correct call;
  the 27 listed files are content-addressed weights/configs/vocab/font, byte-reproducible
  at the pinned docling revision. No listed file is plausibly non-reproducible.
- Test depth: static guard is the RIGHT tool — a real `docker build` can't run locally
  (no docling, no droplet); CI Deploy is the true gate. 7 tests: count==27, per-line
  well-formedness, `.cache/` exclusion, critical-weights-present (safetensors/onnx/pth +
  tableformer accurate+fast), no-`\r` bytes, and Dockerfile COPY + **ordered** verify
  (`cd` before the `sha256sum -c /app/...` command — matched by exact substring after the
  /code-review tightening, so it can't match the "sha256sum -c" mention in the comment).
- 4GB budget: build-time only, zero runtime RAM (model bake = disk, not memory).
- LOW (extra-unlisted-file gap): `sha256sum -c` detects substitution/corruption of listed
  files but not addition of unlisted ones — acceptable (docling loads only the manifested
  set) and now documented in ADR-DOCLING-WEIGHT-CHECKSUM Consequences.
- Commit scope `docker`/`test`: not in `git-github.md`'s allowed scope list (closest:
  `ci`/`config`) — cosmetic, not a finding.

## Coupling note (for future docling-bump reviews)
Manifest is coupled to the docling version pinned in uv.lock — a bump changing model
revisions WILL break the build until the manifest is regenerated. Intended forcing
function. A future docling-bump PR editing `docling_models.sha256` must regenerate from a
**trusted** freshly-built image (SSH-from-prod / CI build), not a dev laptop.
