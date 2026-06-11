---
name: insight-quality-tier-null-floor
description: "#267: quality_tier is NULL-able end to end; floor None->L4_guideline at ingestion. No L5_expert_opinion literal exists."
metadata:
  type: project
---

NULL `quality_tier` flows end-to-end and must be floored, not required away.

**Why:** The upload schema (`RagDocumentUploadRequest.quality_tier: QualityTierLiteral | None`)
and the `rag_documents.quality_tier` column (`nullable=True`) both allow NULL. DOI-less
document types (#234) widened this path. `DocumentMetadata` is a plain dataclass (no runtime
validation) so it passes None straight through, but `ChunkPayload.quality_tier: QualityTier`
is a non-optional Pydantic literal → `ValidationError` → whole `ingest_paper` task fails (#267).

**How to apply:**
- The fix floors `None -> _DEFAULT_QUALITY_TIER = "L4_guideline"` in `IngestionService._build_payloads`
  (`metadata.quality_tier or _DEFAULT_QUALITY_TIER`). Ingestion-time handling (not require-at-upload)
  is correct because it also covers already-uploaded NULL-tier rows that require-at-upload would strand.
- `DocumentMetadata.quality_tier` is now annotated `QualityTier | None` to be honest about runtime.
- **TRAP:** `QualityTier` / `QualityTierLiteral` has ONLY L1-L4 (`L1_systematic_review`, `L2_rct`,
  `L3_observational`, `L4_guideline`). There is NO `L5_expert_opinion` despite issue text suggesting it —
  do not invent a new literal (would touch schema, raise tier, violate the no-invented-status-values rule).
- Read side already mirrors this: `retrieval.py` `payload.get("quality_tier", "L3_observational")`
  defaults missing tier on the way out. Two different defaults (L4 write, L3 read) is a known minor
  inconsistency — read-side only fires if a pre-fix NULL ever reached Qdrant; post-fix every chunk
  carries an explicit tier so the read default is dead for new ingests.
- There is currently NO rerank-side quality_tier weight multiplier in the codebase (searched
  app/services/*). The "quality_tier weight multiplier" in domain knowledge is not yet implemented.
