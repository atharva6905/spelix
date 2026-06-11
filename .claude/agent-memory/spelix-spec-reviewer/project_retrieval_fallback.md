---
name: project-retrieval-fallback
description: retrieval.py:246 has read-side quality_tier fallback to L3_observational
metadata:
  type: project
---

`backend/app/services/retrieval.py:246` uses `payload.get("quality_tier", "L3_observational")` as a read-side fallback. The write-side (ingestion) floors to `L4_guideline` (lowest tier). These are intentionally different defaults — write-side uses lowest authority; read-side was set independently.

**Why:** Verified during issue #267 review. Both defaults exist; neither conflicts with the other since they operate at different pipeline stages.
**How to apply:** When reviewing ingestion/retrieval consistency, note the asymmetry is documented and intentional (write=L4, read=L3).
