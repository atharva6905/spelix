"""Regression tests for #263 — Docling OCR must use a writable artifacts path.

On prod the container runs non-root with a read-only venv. Docling's RapidOCR
backend, when given no explicit model paths, falls back to downloading its OCR
model into ``site-packages`` at first use, which raises ``PermissionError`` and
makes every ``ingest_paper`` task fail (all rag_documents end with chunk_count=0).

The fix points Docling at a writable ``artifacts_path`` (from
``DOCLING_ARTIFACTS_PATH``) and configures RapidOCR explicitly so that a cache
miss can never attempt a site-packages write. These tests guard that config so a
future refactor that drops it fails loudly.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.services import pdf_extraction


def test_build_converter_sets_writable_artifacts_path(monkeypatch) -> None:
    """The Docling converter must be built with the configured artifacts_path.

    Regression for #263: without an explicit artifacts_path, RapidOCR downloads
    its model into the read-only venv site-packages and the task crashes.
    """
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", "/some/writable/models")

    converter = pdf_extraction._build_converter()

    pdf_opts = converter.format_to_options[pdf_extraction.InputFormat.PDF]
    artifacts_path = pdf_opts.pipeline_options.artifacts_path

    assert artifacts_path is not None, (
        "artifacts_path must be set so RapidOCR never writes into site-packages"
    )
    assert Path(artifacts_path) == Path("/some/writable/models")


def test_build_converter_configures_rapidocr_backend(monkeypatch) -> None:
    """OCR must be explicitly configured as RapidOCR so its model paths are pinned."""
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", "/some/writable/models")

    converter = pdf_extraction._build_converter()

    pdf_opts = converter.format_to_options[pdf_extraction.InputFormat.PDF]
    ocr_options = pdf_opts.pipeline_options.ocr_options

    assert ocr_options.kind == "rapidocr", (
        "OCR backend must be pinned to RapidOCR, not the 'auto' resolver"
    )


def test_build_converter_default_artifacts_path_is_not_site_packages() -> None:
    """With no env override, the default artifacts path must still be writable.

    It must never be None (which lets RapidOCR fall back to its site-packages
    download) and must not point inside the installed package tree.
    """
    converter = pdf_extraction._build_converter()

    pdf_opts = converter.format_to_options[pdf_extraction.InputFormat.PDF]
    artifacts_path = pdf_opts.pipeline_options.artifacts_path

    assert artifacts_path is not None
    assert "site-packages" not in str(artifacts_path)


def test_rapidocr_onnx_inference_engine_is_installed() -> None:
    """The onnxruntime inference engine must be installed for RapidOCR (#263).

    Docling pins the RapidOCR backend to ``EngineType.ONNXRUNTIME`` (it builds
    ``Det/Cls/Rec.engine_type = onnxruntime`` from the default
    ``RapidOcrOptions.backend == "onnxruntime"``) and we pre-bake the ONNX model
    set (RapidOcr/onnx/PP-OCRv4/*.onnx). At reader init RapidOCR calls
    ``get_engine(cfg.engine_type)`` which raises
    ``ImportError("onnxruntime is not installed.")`` if the engine wheel is
    absent. The old broken code path used torch ``.pth`` models, so onnxruntime
    was never required; once we pinned ONNX artifacts it became mandatory.

    Guard: ``docling[rapidocr]`` (feat-ocr-rapidocr-onnx) must keep pulling the
    CPU onnxruntime wheel into the dependency set.
    """
    assert importlib.util.find_spec("onnxruntime") is not None, (
        "onnxruntime missing: RapidOCR's onnxruntime engine cannot load the "
        "pre-baked ONNX OCR models — ingest_paper will fail at reader init"
    )


def test_docling_rapidocr_backend_default_is_onnxruntime() -> None:
    """Pin the assumption that docling drives RapidOCR via the onnxruntime engine.

    If a docling upgrade changed the default backend away from onnxruntime, the
    onnxruntime dependency guard above would no longer match the engine docling
    actually configures — this test makes that drift loud.
    """
    from docling.datamodel.pipeline_options import RapidOcrOptions

    assert RapidOcrOptions.model_fields["backend"].default == "onnxruntime"
