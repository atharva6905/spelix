---
name: project-chunkpayload-construction
description: ChunkPayload is constructed in exactly one place — ingestion.py _build_payloads
metadata:
  type: project
---

`ChunkPayload(...)` is constructed in exactly one location: `backend/app/services/ingestion.py` in `IngestionService._build_payloads`. No other callsite exists (verified via grep across the backend codebase, issue #267 review).

**Why:** Important to know when auditing quality_tier None-handling — only one fix point needed.
**How to apply:** If a future issue involves ChunkPayload field validation, audit only `_build_payloads`.
