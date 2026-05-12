"""PDF text extraction via Docling.

Runs the CPU-bound Docling converter inside asyncio.to_thread() to
avoid blocking the event loop. Returns (full_text, sections_or_None).
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

logger = logging.getLogger(__name__)

SECTION_HEADINGS = ("abstract", "introduction", "methods", "results", "discussion", "conclusion")


def _extract_sync(pdf_bytes: bytes) -> tuple[str, dict[str, str] | None]:
    from docling.datamodel.base_models import DocumentStream
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
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
