"""PDF text extraction via Docling.

Runs the CPU-bound Docling converter inside asyncio.to_thread() to
avoid blocking the event loop. Returns (full_text, sections_or_None).
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
from typing import Any

from docling.datamodel.base_models import InputFormat

logger = logging.getLogger(__name__)

SECTION_HEADINGS = ("abstract", "introduction", "methods", "results", "discussion", "conclusion")

# Default writable location for Docling/RapidOCR model artifacts. The prod
# container runs non-root with a read-only venv, so Docling MUST NOT fall back
# to RapidOCR's default behaviour of downloading its OCR model into
# ``site-packages`` (raises PermissionError → every ingest_paper task fails;
# see #263). The Dockerfile pre-bakes the models here at build time and sets
# DOCLING_ARTIFACTS_PATH to match.
_DEFAULT_ARTIFACTS_PATH = "/app/models/docling"


def _artifacts_path() -> str:
    """Resolve the writable Docling artifacts directory.

    Never returns None: a None ``artifacts_path`` lets RapidOCR download into
    site-packages, which is exactly the #263 crash we are guarding against.
    """
    return os.environ.get("DOCLING_ARTIFACTS_PATH") or _DEFAULT_ARTIFACTS_PATH


def _build_converter() -> Any:
    """Construct a DocumentConverter pinned to a writable artifacts path.

    Setting ``artifacts_path`` makes Docling pass explicit ``Det/Cls/Rec``
    model paths to RapidOCR, so RapidOCR uses the pre-baked local files instead
    of attempting a download into the read-only venv (#263). OCR is pinned to
    the RapidOCR backend explicitly rather than the ``auto`` resolver so the
    model paths are always pinned.
    """
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions(
        artifacts_path=_artifacts_path(),
        ocr_options=RapidOcrOptions(),
    )
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        },
    )


def _extract_sync(pdf_bytes: bytes) -> tuple[str, dict[str, str] | None]:
    from docling.datamodel.base_models import DocumentStream

    converter = _build_converter()
    source = DocumentStream(name="paper.pdf", stream=io.BytesIO(pdf_bytes))
    result = converter.convert(source)

    doc: Any = result.document
    full_text = doc.export_to_markdown()

    sections: dict[str, str] = {}
    if hasattr(doc, "texts"):
        current_section: str | None = None
        section_lines: list[str] = []

        for item in doc.texts:
            text = getattr(item, "text", "")
            label = getattr(item, "label", "")

            if label and "heading" in label.lower():
                if current_section and section_lines:
                    sections[current_section] = "\n".join(section_lines)
                    section_lines = []

                heading_lower = text.strip().lower()
                matched = next(
                    (h for h in SECTION_HEADINGS if heading_lower.startswith(h)),
                    None,
                )
                current_section = matched
            elif current_section:
                section_lines.append(text)

        if current_section and section_lines:
            sections[current_section] = "\n".join(section_lines)

    return full_text, sections if sections else None


async def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, dict[str, str] | None]:
    """Extract text and optional sections from PDF bytes using Docling."""
    return await asyncio.to_thread(_extract_sync, pdf_bytes)
