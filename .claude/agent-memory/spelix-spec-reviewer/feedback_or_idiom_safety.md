---
name: feedback-or-idiom-safety
description: or-idiom safety for QualityTier fields — empty string not a risk
metadata:
  type: feedback
---

For `quality_tier` fields in Spelix, the `or` idiom (`metadata.quality_tier or _DEFAULT_QUALITY_TIER`) is safe because `QualityTier` values come from a constrained `String(30)` ORM column populated only via `QualityTierLiteral` (4 specific non-empty strings). Empty string is not a valid DB value. Only `None` (NULL) reaches ingestion without a tier.

**Why:** Verified in issue #267 review — `app/models/rag_document.py:52` maps `Mapped[Optional[str]]`, values are always a valid tier string or None.
**How to apply:** When reviewing code that uses `x or default` for QualityTier, confirm `or` is safe — no empty-string risk from this column.
