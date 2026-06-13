"""Static/regression guard for the Docling model-weight checksum manifest.

Defense-in-depth supply-chain integrity (GitHub issue #269; origin:
security-reviewer HIGH on #263/#268). ``backend/Dockerfile`` pre-bakes Docling
OCR/layout/tableformer model *weights* at build time. The docling *packages* are
sha256-pinned in ``uv.lock``, but the downloaded *weights* (pulled from
HuggingFace at build) had no integrity verification — asymmetric with the
BlazePose download right above it, which verifies via ``sha256sum -c``.

This test cannot run a real ``docker build`` locally (no docling install, no
droplet); CI's Deploy step is the true build gate. This guards the *wiring*
against regression: the committed manifest stays well-formed and the Dockerfile
keeps the COPY + verify steps in the correct order.
"""

import re
from pathlib import Path

# This file lives at backend/tests/unit/; parents[2] == backend/.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = BACKEND_ROOT / "docling_models.sha256"
DOCKERFILE_PATH = BACKEND_ROOT / "Dockerfile"

# ``sha256sum`` output format: 64-hex, exactly two spaces, then a ``./``-relative
# path. No blank lines, no comment lines — ``sha256sum -c`` rejects both.
_MANIFEST_LINE = re.compile(r"^[0-9a-f]{64}  \./.+$")

_EXPECTED_ENTRY_COUNT = 27


def _manifest_lines() -> list[str]:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    # Preserve every physical line so we catch stray blanks; drop only a single
    # trailing newline at EOF (the file ends with one newline, standard POSIX).
    return text.split("\n")[:-1] if text.endswith("\n") else text.split("\n")


def _manifest_paths() -> list[str]:
    return [line.split("  ", 1)[1] for line in _manifest_lines()]


def test_manifest_exists_and_non_empty() -> None:
    assert MANIFEST_PATH.exists(), f"missing manifest: {MANIFEST_PATH}"
    assert MANIFEST_PATH.read_text(encoding="utf-8").strip(), "manifest is empty"


def test_every_line_is_well_formed_sha256sum_output() -> None:
    for i, line in enumerate(_manifest_lines(), start=1):
        assert _MANIFEST_LINE.match(line), (
            f"line {i} is not valid sha256sum output "
            f"(64-hex + two spaces + ./path): {line!r}"
        )


def test_manifest_has_exactly_27_entries() -> None:
    assert len(_manifest_lines()) == _EXPECTED_ENTRY_COUNT


def test_no_manifest_path_is_in_huggingface_cache() -> None:
    # The HF local download cache (*/.cache/huggingface/**) embeds download
    # timestamps/ETags and is non-deterministic build-to-build; it is
    # deliberately excluded so the build does not flake. Guard the exclusion.
    offenders = [p for p in _manifest_paths() if "/.cache/" in p]
    assert not offenders, f"manifest must not include HF cache paths: {offenders}"


def test_manifest_contains_critical_weight_files() -> None:
    paths = _manifest_paths()
    assert any(p.endswith(".safetensors") for p in paths), "missing layout safetensors"
    assert any(
        p.endswith("model_artifacts/tableformer/accurate/tableformer_accurate.safetensors")
        for p in paths
    ), "missing tableformer accurate weights"
    assert any(
        p.endswith("model_artifacts/tableformer/fast/tableformer_fast.safetensors")
        for p in paths
    ), "missing tableformer fast weights"
    assert any(p.endswith(".onnx") for p in paths), "missing RapidOCR onnx weights"
    assert any(p.endswith(".pth") for p in paths), "missing RapidOCR torch weights"


def test_dockerfile_copies_and_verifies_the_manifest() -> None:
    content = DOCKERFILE_PATH.read_text(encoding="utf-8")

    # The download itself must remain unchanged.
    assert "docling-tools models download" in content, "docling download removed"

    # The manifest is copied into the image.
    copy_re = re.compile(r"^COPY\s+.*docling_models\.sha256.*$", re.MULTILINE)
    assert copy_re.search(content), "no COPY line for docling_models.sha256"

    # The verification runs sha256sum -c against the copied manifest. Match the
    # actual check *command* (referencing the manifest path), not an incidental
    # "sha256sum -c" mention in the surrounding comment block.
    assert "sha256sum -c" in content, "no sha256sum -c verification step"
    check_re = re.compile(r"sha256sum -c\s+\S*docling_models\.sha256")
    check_match = check_re.search(content)
    assert check_match, "sha256sum -c does not reference docling_models.sha256"

    # The check must run from the model dir so the ./-relative paths resolve.
    # Compare against the real check command's position (check_match), not the
    # first "sha256sum -c" substring, which also appears in the comment above.
    cd_idx = content.find("cd /app/models/docling")
    assert cd_idx != -1, "missing 'cd /app/models/docling' before the checksum step"
    assert cd_idx < check_match.start(), (
        "'cd /app/models/docling' must precede the 'sha256sum -c ...docling_models.sha256' check"
    )
