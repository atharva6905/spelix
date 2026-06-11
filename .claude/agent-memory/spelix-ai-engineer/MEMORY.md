# Spelix AI Engineer — Memory Index

- [Sex-aware retrieval & prompt](insight-sex-aware-retrieval.md) — #225 pattern: papers-only hard filter, lifter_sex threading, BM25 leak fix, trace PII safety
- [Docling OCR artifacts_path](insight-docling-ocr-artifacts-path.md) — #263: RapidOCR writes model into site-packages unless artifacts_path pinned; prod read-only venv crashed every ingest_paper
- [quality_tier NULL floor](insight-quality-tier-null-floor.md) — #267: NULL tier flows end-to-end; floor None->L4_guideline at ingestion; NO L5_expert_opinion literal exists
