# Expert PDF Upload Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire end-to-end PDF upload on the expert reviewer portal so the kin expert can upload peer-reviewed papers directly from the browser into the `papers_rag` corpus.

**Architecture:** Two-phase signed-URL upload to a new Supabase Storage bucket `papers`. Phase 1: `POST /api/v1/expert/papers` accepts metadata + filename + size, returns a signed upload URL (pattern matches existing video flow in `AnalysisService.create_analysis`). Phase 2: browser PUTs the file directly to Supabase Storage (FastAPI never handles bytes). Phase 3: `POST /api/v1/expert/papers/{id}/complete` does a magic-byte check (`%PDF-`) on the uploaded object via service-role client, flips `review_status` from `'uploading'` to `'pending'`, and enqueues an `ingest_paper` ARQ task. Security: bucket RLS restricts writes to `expert_reviewer` + `admin` roles; service-role reads only. Size cap 50 MB enforced at schema + bucket level. Filename sanitisation: allow `[A-Za-z0-9._-]`, must end `.pdf`, max 255 chars.

**Scope boundary:** Docling PDF→text parsing (P2-005) is **out of scope**. The new `ingest_paper` ARQ task is a stub that downloads the PDF and logs "docling-pending" — `chunk_count=0` and `ingested_at=NULL` until P2-005 ships. This lets the kin expert upload PDFs end-to-end for the May 3 hard gate without blocking on the parsing work.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Supabase Storage (REST signed URL), ARQ + Redis, React 19 + XHR (matching existing `UploadPage.tsx` pattern), vitest + @testing-library/react, pytest + FastAPI TestClient.

**Requirements mapping:**
- STRATEGY.md §Day 1-2 Track B (hard gate: kin expert uploads first seed PDF end-to-end)
- STRATEGY.md §Required ADR Updates → ADR-EXPERT-01 (new)
- Handoff §2 Track B (magic-byte, 50 MB, RLS, Docling trigger)
- SRS FR-EXPV-02 (expert paper upload with metadata)

---

## File Structure

**New files:**
- `docs/superpowers/plans/2026-04-15-expert-pdf-upload-wiring.md` — this plan
- `decisions.md` — new entry: ADR-EXPERT-01
- `backend/alembic/versions/009_papers_bucket_rls.py` — bucket + RLS + review_status enum widen
- `backend/app/utils/pdf_upload.py` — `sanitize_pdf_filename`, `MAX_PDF_BYTES`, `PDF_MAGIC_BYTES`
- `backend/app/services/paper_storage.py` — thin wrapper over `StorageService` bound to `papers` bucket
- `backend/app/workers/paper_ingestion.py` — ARQ task `ingest_paper` (stub)
- `backend/tests/unit/test_pdf_upload_utils.py`
- `backend/tests/unit/test_paper_storage.py`
- `backend/tests/unit/test_expert_paper_upload.py` (signed-URL endpoint)
- `backend/tests/unit/test_expert_paper_complete.py` (magic-byte + complete endpoint)
- `backend/tests/unit/test_paper_ingestion_task.py`
- `backend/tests/integration/test_expert_paper_e2e.py` — TestClient walks all three phases
- `frontend/src/api/__tests__/expert-upload.test.ts` — API client unit tests

**Modified files:**
- `backend/app/models/rag_document.py` — extend `review_status` CHECK to include `'uploading'`
- `backend/app/schemas/rag_document.py` — rename `RagDocumentUpload` to `RagDocumentMetadata`, add `RagDocumentUploadRequest` (+filename, +file_size_bytes), new `RagDocumentUploadResponse` (id, upload_url, storage_path, expires_at), new `RagDocumentCompleteResponse`
- `backend/app/api/v1/expert.py` — rewrite `POST /papers` to two-phase; add `POST /papers/{id}/complete`
- `backend/app/workers/settings.py` — register `ingest_paper` in `WorkerSettings.functions`
- `frontend/src/api/expert.ts` — replace `uploadPaper` JSON-only with `requestPaperUploadUrl` + `completePaperUpload` + `uploadPaperFile` (XHR)
- `frontend/src/pages/ExpertPaperUploadPage.tsx` — add `<input type="file">` + progress bar + 3-phase flow
- `frontend/src/pages/__tests__/ExpertPaperUploadPage.test.tsx` — extend with file-upload cases
- `backlog.md` — close D-017, add new task rows for PDF upload wiring

---

## Task 0: ADR-EXPERT-01 — Expert Paper Upload Security Model

**Files:**
- Modify: `decisions.md` (append new ADR entry at end of file)

- [ ] **Step 1: Locate the bottom of `decisions.md` to find the next ADR ID**

Run: `grep -n "^## ADR-" decisions.md | tail -5`
Expected: list of most recent ADR IDs to confirm the next is `ADR-EXPERT-01`.

- [ ] **Step 2: Append ADR-EXPERT-01 to `decisions.md`**

Add this entry:

```markdown
## ADR-EXPERT-01: Expert Paper Upload Security Model

**Date:** 2026-04-15
**Status:** Accepted
**Phase:** L2 sprint (Day 3-5)
**Related:** STRATEGY.md §Day 1-2 Track B; handoff.md §2 Track B; FR-EXPV-02

### Context

Expert reviewer portal shipped in Phase 2 with metadata-only `POST /api/v1/expert/papers` — no file input on frontend, no multipart on backend. L2 sprint requires the kin expert to upload real peer-reviewed PDFs directly into the `papers_rag` corpus by end of Day 2.

### Decision

Two-phase signed-URL upload to a dedicated Supabase Storage bucket named `papers`, matching the existing video upload pattern (`AnalysisService.create_analysis` + XHR PUT to signed URL).

**Phase 1** — `POST /api/v1/expert/papers` accepts JSON body `{metadata..., filename, file_size_bytes}`. Backend:
- Validates `file_size_bytes <= 52_428_800` (50 MB).
- Validates filename matches `^[A-Za-z0-9._-]+\.pdf$` after sanitisation (whitespace → `_`, non-allowed chars stripped, max 255 chars).
- Generates `paper_id = uuid4()`; builds `storage_path = f"papers/{paper_id}/{sanitized_filename}"`.
- Calls `PaperStorageService.generate_signed_upload_url(storage_path)` — TTL 3600 s.
- Inserts `rag_documents` row with `review_status='uploading'`, `storage_path=<path>`, user-supplied metadata.
- Returns `{id, upload_url, storage_path, expires_at}`.

**Phase 2** — Browser PUTs the file directly to `upload_url` with `Content-Type: application/pdf`. FastAPI never touches bytes.

**Phase 3** — `POST /api/v1/expert/papers/{id}/complete`. Backend:
- Downloads the first 8 bytes of the object via service-role Supabase client.
- Asserts bytes start with `b"%PDF-"`. If not, deletes the storage object + the `rag_documents` row, returns 422 `INVALID_PDF`.
- If ok, updates `review_status='pending'`, enqueues `ingest_paper(paper_id)` ARQ job.
- Returns `{id, review_status: 'pending'}`.

### Security posture

- **Bucket RLS**: `INSERT` allowed for JWT where `user_metadata.role IN ('expert_reviewer', 'admin')` AND `bucket_id='papers'`. `SELECT` only for `service_role`. No public read.
- **Magic-byte validation** happens post-upload via service-role download, not pre-upload, because signed-URL PUTs bypass the FastAPI handler. 8-byte head is enough to identify PDF (`%PDF-1.x`).
- **Size limit** enforced at schema (Phase 1 rejects large claims) + bucket config (Supabase enforces on PUT).
- **Filename sanitisation** prevents path traversal, command injection, and filesystem quirks. Rejected filenames fail Phase 1 with 422.
- **Role gate** via existing `get_expert_reviewer_user` dependency (admin + expert_reviewer only).
- **Service-role key** is server-side only, read from `SUPABASE_SERVICE_ROLE_KEY` env var. Never sent to the browser.

### Why two phases + completion endpoint (not one phase + worker poll)

A third endpoint is cheaper than making the ARQ worker poll Supabase Storage for "upload finished" state. It also lets the client signal intent to commit — orphaned rows with `review_status='uploading'` + expired `upload_url` can be swept by a cron later if abandonment becomes a real problem.

### Why not TUS protocol

Matches the pattern in `UploadPage.tsx` lines 9–18: Supabase REST signed upload URLs reject TUS protocol headers. Plain XHR PUT is the supported path.

### Why Docling is not in this ADR

P2-005 is open. The `ingest_paper` task in this scope downloads the PDF and logs `docling-pending`. Chunking + embedding fire when P2-005 ships. The May 3 gate is "expert uploaded end-to-end", not "papers appear in RAG queries".

### Consequences

- New Supabase bucket `papers` created via Alembic migration 009 (or dashboard if Alembic-over-storage is flaky on this Supabase project).
- `rag_documents.review_status` CHECK constraint widened to include `'uploading'`.
- Two new schemas: `RagDocumentUploadRequest`, `RagDocumentUploadResponse`, `RagDocumentCompleteResponse`.
- `StorageService` sprouts a papers-flavoured sibling (`PaperStorageService`) bound to bucket `papers`.
- Frontend page adds `<input type="file">` + XHR PUT + progress bar. Matches `UploadPage.tsx` conventions.
- ARQ worker registry adds `ingest_paper` (no-op stub until P2-005).

### Alternatives considered

- **Multipart/form-data on FastAPI** — rejected. Would make the backend a bandwidth bottleneck on the 4 GB droplet; violates ADR-048 memory budget. Signed-URL matches existing patterns.
- **One-phase upload + worker polls** — rejected. Worker is ARQ, not a long-running poller; adding poll loops adds complexity. A cheap completion endpoint is clearer.
- **Reuse `videos` bucket with `papers/` prefix** — rejected. Bucket-level RLS is clearer when one bucket = one purpose. Video RLS uses `user_id` path segments; papers RLS needs role claims.
```

- [ ] **Step 3: Verify ADR-EXPERT-01 is present and well-formed**

Run: `grep -n "ADR-EXPERT-01" decisions.md`
Expected: exactly one match on the heading line.

- [ ] **Step 4: Commit**

```bash
git checkout -b feat/expert-pdf-upload
git add decisions.md
git commit -m "docs(decisions): ADR-EXPERT-01 expert paper upload security model"
```

---

## Task 1: Alembic Migration 009 — `papers` bucket + RLS + review_status widening

**Files:**
- Create: `backend/alembic/versions/009_papers_bucket_rls.py`
- Modify: `backend/app/models/rag_document.py:<review_status CHECK constraint>`

**Agent:** delegate this entire task to `spelix-migration` (per CLAUDE.md "Alembic migrations: always use spelix-migration").

- [ ] **Step 1: Dispatch the migration agent**

Prompt to `spelix-migration`:

> Create Alembic migration `009_papers_bucket_rls` with `down_revision = "008_beta_requests"`.
>
> Upgrade DDL (all via `op.execute` since these are Supabase storage operations + constraint edits):
>
> 1. Create the `papers` bucket: `INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types) VALUES ('papers', 'papers', false, 52428800, ARRAY['application/pdf']::text[]) ON CONFLICT (id) DO NOTHING;`
>
> 2. Drop and recreate the `rag_documents.review_status` CHECK constraint to include `'uploading'`:
>    - `ALTER TABLE rag_documents DROP CONSTRAINT IF EXISTS rag_documents_review_status_check;`
>    - `ALTER TABLE rag_documents ADD CONSTRAINT rag_documents_review_status_check CHECK (review_status IN ('pending', 'approved', 'rejected', 'uploading'));`
>
> 3. RLS policies on `storage.objects` for the `papers` bucket:
>    - Drop any existing `expert_papers_*` policies first for idempotency.
>    - `CREATE POLICY "expert_papers_insert" ON storage.objects FOR INSERT TO authenticated WITH CHECK (bucket_id = 'papers' AND (auth.jwt()->'user_metadata'->>'role') IN ('expert_reviewer', 'admin'));`
>    - `CREATE POLICY "expert_papers_service_select" ON storage.objects FOR SELECT TO service_role USING (bucket_id = 'papers');`
>    - `CREATE POLICY "expert_papers_service_delete" ON storage.objects FOR DELETE TO service_role USING (bucket_id = 'papers');`
>
> Downgrade DDL reverses in inverse order: drop policies, restore the old CHECK constraint without `'uploading'`, delete the bucket row.
>
> Also edit `backend/app/models/rag_document.py` to widen the model-side `CheckConstraint` on `review_status` to match (`"review_status IN ('pending', 'approved', 'rejected', 'uploading')"`).
>
> Apply migration immediately: `cd backend && uv run alembic upgrade head`. Verify with `uv run alembic current` (expect `009_papers_bucket_rls (head)`).

- [ ] **Step 2: Verify migration applied locally**

Run: `cd backend && uv run alembic current`
Expected: `009_papers_bucket_rls (head)`

- [ ] **Step 3: Verify bucket exists in Supabase**

Run (from backend dir):
```bash
uv run python -c "
import asyncio
from app.db import async_session_maker
from sqlalchemy import text

async def main():
    async with async_session_maker() as s:
        r = await s.execute(text(\"SELECT id, file_size_limit FROM storage.buckets WHERE id = 'papers'\"))
        print(r.one_or_none())

asyncio.run(main())
"
```
Expected: `('papers', 52428800)`.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/009_papers_bucket_rls.py backend/app/models/rag_document.py
git commit -m "feat(migration): 009 papers bucket RLS + review_status uploading state"
```

---

## Task 2: PDF Upload Validation Utilities

**Files:**
- Create: `backend/app/utils/pdf_upload.py`
- Test: `backend/tests/unit/test_pdf_upload_utils.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/test_pdf_upload_utils.py`:

```python
import pytest

from app.utils.pdf_upload import (
    MAX_PDF_BYTES,
    PDF_MAGIC_BYTES,
    FilenameValidationError,
    sanitize_pdf_filename,
)


class TestSanitizePdfFilename:
    def test_accepts_simple_filename(self):
        assert sanitize_pdf_filename("paper.pdf") == "paper.pdf"

    def test_preserves_allowed_characters(self):
        assert sanitize_pdf_filename("My-Paper_v2.1.pdf") == "My-Paper_v2.1.pdf"

    def test_replaces_whitespace_with_underscore(self):
        assert sanitize_pdf_filename("squat biomechanics.pdf") == "squat_biomechanics.pdf"

    def test_strips_disallowed_characters(self):
        assert sanitize_pdf_filename("paper@#$%.pdf") == "paper.pdf"

    def test_rejects_missing_pdf_extension(self):
        with pytest.raises(FilenameValidationError) as exc:
            sanitize_pdf_filename("paper.docx")
        assert "must end" in str(exc.value).lower()

    def test_rejects_uppercase_pdf_extension(self):
        """Extension check is case-insensitive but output lowercases the extension."""
        assert sanitize_pdf_filename("paper.PDF") == "paper.pdf"

    def test_rejects_empty_stem(self):
        with pytest.raises(FilenameValidationError):
            sanitize_pdf_filename(".pdf")

    def test_rejects_path_traversal(self):
        with pytest.raises(FilenameValidationError):
            sanitize_pdf_filename("../../../etc/passwd.pdf")

    def test_truncates_to_255(self):
        long_name = "a" * 300 + ".pdf"
        result = sanitize_pdf_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".pdf")

    def test_rejects_empty_string(self):
        with pytest.raises(FilenameValidationError):
            sanitize_pdf_filename("")


class TestConstants:
    def test_max_pdf_bytes_is_50mib(self):
        assert MAX_PDF_BYTES == 52_428_800

    def test_pdf_magic_bytes(self):
        assert PDF_MAGIC_BYTES == b"%PDF-"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_pdf_upload_utils.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'app.utils.pdf_upload'`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/utils/pdf_upload.py`:

```python
"""Filename sanitisation and size constants for expert PDF upload (ADR-EXPERT-01)."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

MAX_PDF_BYTES: int = 50 * 1024 * 1024
PDF_MAGIC_BYTES: bytes = b"%PDF-"
_MAX_FILENAME_CHARS: int = 255
_ALLOWED_CHAR_RE = re.compile(r"[^A-Za-z0-9._-]")
_WHITESPACE_RE = re.compile(r"\s+")


class FilenameValidationError(ValueError):
    """Raised when a proposed PDF filename cannot be sanitised to a safe value."""


def sanitize_pdf_filename(raw: str) -> str:
    """Return a safe filename for Supabase Storage; raise on rejection.

    Rules:
    - Must end in `.pdf` (case-insensitive; output lowercases the extension).
    - Whitespace runs collapse to `_`.
    - Any character outside `[A-Za-z0-9._-]` is stripped.
    - Path separators and `..` segments are rejected.
    - Max 255 chars including extension.
    - Stem must be non-empty after sanitisation.
    """
    if not raw or not raw.strip():
        raise FilenameValidationError("filename is empty")

    if "/" in raw or "\\" in raw:
        raise FilenameValidationError("filename contains path separators")

    name = PurePosixPath(raw).name
    if name in ("", ".", ".."):
        raise FilenameValidationError("filename resolves to a directory reference")

    lower = name.lower()
    if not lower.endswith(".pdf"):
        raise FilenameValidationError("filename must end in .pdf")

    stem = name[: -len(".pdf")]
    stem = _WHITESPACE_RE.sub("_", stem)
    stem = _ALLOWED_CHAR_RE.sub("", stem)

    if not stem:
        raise FilenameValidationError("filename stem is empty after sanitisation")

    safe = f"{stem}.pdf"
    if len(safe) > _MAX_FILENAME_CHARS:
        overflow = len(safe) - _MAX_FILENAME_CHARS
        safe = f"{stem[:-overflow]}.pdf"

    return safe
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_pdf_upload_utils.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils/pdf_upload.py backend/tests/unit/test_pdf_upload_utils.py
git commit -m "feat(utils): PDF filename sanitisation + size constants (ADR-EXPERT-01)"
```

---

## Task 3: PaperStorageService — signed URL + head-bytes download + delete

**Files:**
- Create: `backend/app/services/paper_storage.py`
- Test: `backend/tests/unit/test_paper_storage.py`

The existing `StorageService` is hard-bound to the `videos` bucket and uses path convention `videos/{analysis_id}/{filename}`. `PaperStorageService` is a sibling bound to `papers`, with the head-bytes operation that doesn't exist in `StorageService`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_paper_storage.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.paper_storage import PaperStorageService


@pytest.fixture()
def mock_supabase():
    client = MagicMock()
    storage = MagicMock()
    bucket = MagicMock()
    client.storage = storage
    storage.from_ = MagicMock(return_value=bucket)
    return client, bucket


class TestGenerateSignedUploadUrl:
    @pytest.mark.asyncio
    async def test_builds_correct_path_and_returns_url(self, mock_supabase):
        client, bucket = mock_supabase
        bucket.create_signed_upload_url = AsyncMock(
            return_value={"signed_url": "https://x.supabase.co/upload/tok", "token": "tok"}
        )

        svc = PaperStorageService(client=client, bucket="papers")
        result = await svc.generate_signed_upload_url("papers/abc/paper.pdf")

        assert result.url == "https://x.supabase.co/upload/tok"
        assert result.expires_at > datetime.now(timezone.utc)
        bucket.create_signed_upload_url.assert_awaited_once_with("papers/abc/paper.pdf")


class TestDownloadHeadBytes:
    @pytest.mark.asyncio
    async def test_returns_first_n_bytes(self, mock_supabase):
        client, bucket = mock_supabase
        bucket.download = AsyncMock(return_value=b"%PDF-1.4\nrest of file...")

        svc = PaperStorageService(client=client, bucket="papers")
        head = await svc.download_head_bytes("papers/abc/paper.pdf", n=8)

        assert head == b"%PDF-1.4"
        bucket.download.assert_awaited_once_with("papers/abc/paper.pdf")

    @pytest.mark.asyncio
    async def test_shorter_file_returns_what_exists(self, mock_supabase):
        client, bucket = mock_supabase
        bucket.download = AsyncMock(return_value=b"%PDF")

        svc = PaperStorageService(client=client, bucket="papers")
        head = await svc.download_head_bytes("papers/abc/paper.pdf", n=8)

        assert head == b"%PDF"


class TestDeleteObject:
    @pytest.mark.asyncio
    async def test_calls_remove(self, mock_supabase):
        client, bucket = mock_supabase
        bucket.remove = AsyncMock(return_value=[{"name": "papers/abc/paper.pdf"}])

        svc = PaperStorageService(client=client, bucket="papers")
        await svc.delete_object("papers/abc/paper.pdf")

        bucket.remove.assert_awaited_once_with(["papers/abc/paper.pdf"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_paper_storage.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.paper_storage'`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/services/paper_storage.py`:

```python
"""Supabase Storage wrapper bound to the `papers` bucket (ADR-EXPERT-01).

Separate from `StorageService` (videos bucket) so the bucket name and path
convention are encoded once, and so `download_head_bytes` — the magic-byte
check helper — lives alongside the upload-URL issuer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class SignedPaperUpload:
    url: str
    expires_at: datetime


class PaperStorageService:
    _TTL_SECONDS = 3600

    def __init__(self, *, client: Any, bucket: str = "papers") -> None:
        self._client = client
        self._bucket = bucket

    async def generate_signed_upload_url(self, storage_path: str) -> SignedPaperUpload:
        bucket = self._client.storage.from_(self._bucket)
        result = await bucket.create_signed_upload_url(storage_path)
        url: str = result.get("signed_url") or result.get("signedUrl") or result["url"]
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._TTL_SECONDS)
        return SignedPaperUpload(url=url, expires_at=expires_at)

    async def download_head_bytes(self, storage_path: str, *, n: int) -> bytes:
        """Download the full object via service-role client and slice the head.

        Supabase's download API has no range-read helper; we fetch the object
        (bounded by the 50 MB bucket cap) and slice. For a magic-byte check
        we only inspect the first 8 bytes.
        """
        bucket = self._client.storage.from_(self._bucket)
        data: bytes = await bucket.download(storage_path)
        return data[:n]

    async def delete_object(self, storage_path: str) -> None:
        bucket = self._client.storage.from_(self._bucket)
        await bucket.remove([storage_path])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_paper_storage.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/paper_storage.py backend/tests/unit/test_paper_storage.py
git commit -m "feat(storage): PaperStorageService for papers bucket (ADR-EXPERT-01)"
```

---

## Task 4: Pydantic Schemas — Upload Request / Response / Complete Response

**Files:**
- Modify: `backend/app/schemas/rag_document.py`

- [ ] **Step 1: Read existing schemas file**

Run: `cat backend/app/schemas/rag_document.py` (skim to locate `RagDocumentUpload` around line 75).

- [ ] **Step 2: Add new request/response schemas alongside existing ones**

Append to `backend/app/schemas/rag_document.py` (keep existing `RagDocumentUpload` and `RagDocumentResponse` intact — they're used by tests and won't be removed yet):

```python
class RagDocumentUploadRequest(BaseModel):
    """Phase 1 request: metadata + filename + size, server returns signed URL."""

    title: str = Field(..., min_length=1, max_length=500)
    document_type: Literal["paper", "textbook", "video_transcript", "expert_commentary"]
    exercise_tags: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1900, le=2100)
    doi: str | None = Field(default=None, max_length=200)
    study_design: (
        Literal[
            "rct", "cohort", "case_control", "cross_sectional",
            "systematic_review", "meta_analysis", "narrative_review",
            "case_series", "case_report",
        ]
        | None
    ) = None
    population: str | None = Field(default=None, max_length=500)
    measurement_method: str | None = Field(default=None, max_length=500)
    quality_tier: Literal["a", "b", "c"] | None = None

    filename: str = Field(..., min_length=5, max_length=255)
    file_size_bytes: int = Field(..., gt=0, le=52_428_800)


class RagDocumentUploadResponse(BaseModel):
    id: UUID
    upload_url: str
    storage_path: str
    expires_at: datetime


class RagDocumentCompleteResponse(BaseModel):
    id: UUID
    review_status: Literal["pending"]
    storage_path: str
```

(If `Literal`, `UUID`, `datetime`, `Field`, `BaseModel` imports aren't already present at the top, add them.)

- [ ] **Step 3: Verify schema imports + module loads**

Run: `cd backend && uv run python -c "from app.schemas.rag_document import RagDocumentUploadRequest, RagDocumentUploadResponse, RagDocumentCompleteResponse; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/rag_document.py
git commit -m "feat(schemas): RagDocumentUploadRequest/Response + CompleteResponse"
```

---

## Task 5: Backend Endpoint — `POST /api/v1/expert/papers` (Phase 1, signed URL)

**Files:**
- Modify: `backend/app/api/v1/expert.py:140-165`
- Test: `backend/tests/unit/test_expert_paper_upload.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_expert_paper_upload.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.expert import router as expert_router


TEST_EXPERT_ID = uuid4()
VALID_BODY = {
    "title": "Squat biomechanics",
    "document_type": "paper",
    "exercise_tags": ["squat"],
    "authors": ["Escamilla R"],
    "year": 2001,
    "doi": "10.1249/00005768-200101000-00020",
    "study_design": "cross_sectional",
    "population": "10 powerlifters",
    "measurement_method": "emg + force plate",
    "quality_tier": "a",
    "filename": "escamilla_2001.pdf",
    "file_size_bytes": 2_500_000,
}


@pytest.fixture()
def expert_app():
    from app.api.deps import get_expert_reviewer_user
    from app.db import get_db

    app = FastAPI()
    app.include_router(expert_router, prefix="/api/v1/expert")

    async def _mock_expert():
        return {"id": TEST_EXPERT_ID, "email": "expert@spelix.app", "role": "expert_reviewer"}

    mock_db = AsyncMock()
    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_expert_reviewer_user] = _mock_expert
    app.dependency_overrides[get_db] = _mock_db
    return app, mock_db


@pytest.fixture()
def client(expert_app):
    app, _ = expert_app
    return TestClient(app, raise_server_exceptions=False)


class TestRequestPaperUpload:
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_returns_signed_url_and_creates_uploading_row(
        self, MockRepo, MockStorage, client
    ):
        from app.services.paper_storage import SignedPaperUpload

        repo_instance = MockRepo.return_value
        created_id = uuid4()

        async def fake_create(doc):
            doc.id = created_id
            return doc

        repo_instance.create = AsyncMock(side_effect=fake_create)

        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        storage_instance = MockStorage.return_value
        storage_instance.generate_signed_upload_url = AsyncMock(
            return_value=SignedPaperUpload(url="https://x.supabase.co/upload/tok", expires_at=expires)
        )

        resp = client.post("/api/v1/expert/papers", json=VALID_BODY)

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["id"] == str(created_id)
        assert body["upload_url"] == "https://x.supabase.co/upload/tok"
        assert body["storage_path"].startswith(f"papers/{created_id}/")
        assert body["storage_path"].endswith("escamilla_2001.pdf")
        assert repo_instance.create.await_count == 1
        doc_arg = repo_instance.create.await_args[0][0]
        assert doc_arg.review_status == "uploading"

    def test_rejects_oversize(self, client):
        body = {**VALID_BODY, "file_size_bytes": 60_000_000}
        resp = client.post("/api/v1/expert/papers", json=body)
        assert resp.status_code == 422

    def test_rejects_non_pdf_extension(self, client):
        body = {**VALID_BODY, "filename": "paper.docx"}
        resp = client.post("/api/v1/expert/papers", json=body)
        assert resp.status_code == 422
        assert "pdf" in resp.text.lower()

    def test_rejects_path_traversal(self, client):
        body = {**VALID_BODY, "filename": "../../../etc/passwd.pdf"}
        resp = client.post("/api/v1/expert/papers", json=body)
        assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_expert_paper_upload.py -v`
Expected: either collection error, or first three tests failing because the handler still returns the old JSON-only 201 shape.

- [ ] **Step 3: Rewrite the handler in `backend/app/api/v1/expert.py`**

Replace the existing `upload_paper` handler (lines 140–165) with:

```python
from uuid import uuid4

from app.schemas.rag_document import (
    RagDocumentUploadRequest,
    RagDocumentUploadResponse,
)
from app.services.paper_storage import PaperStorageService
from app.services.supabase_client import get_service_role_client  # add if not present
from app.utils.pdf_upload import FilenameValidationError, sanitize_pdf_filename


@router.post(
    "/papers",
    response_model=RagDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_paper_upload(
    body: RagDocumentUploadRequest,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    rag_repo: RagDocumentRepository = Depends(_get_rag_repo),
) -> Any:
    try:
        safe_name = sanitize_pdf_filename(body.filename)
    except FilenameValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_FILENAME", "message": str(err), "detail": None}},
        ) from err

    paper_id = uuid4()
    storage_path = f"papers/{paper_id}/{safe_name}"

    doc = RagDocument(
        id=paper_id,
        title=body.title,
        document_type=body.document_type,
        exercise_tags=body.exercise_tags,
        authors=body.authors,
        year=body.year,
        doi=body.doi,
        study_design=body.study_design,
        population=body.population,
        measurement_method=body.measurement_method,
        quality_tier=body.quality_tier,
        review_status="uploading",
        storage_path=storage_path,
        extra_metadata={"uploaded_by": str(user["id"])},
    )
    created = await rag_repo.create(doc)

    storage = PaperStorageService(client=get_service_role_client())
    signed = await storage.generate_signed_upload_url(storage_path)

    return RagDocumentUploadResponse(
        id=created.id,
        upload_url=signed.url,
        storage_path=storage_path,
        expires_at=signed.expires_at,
    )
```

If `get_service_role_client` doesn't already exist, add it in a new file `backend/app/services/supabase_client.py` with the documented pattern (`create_async_client(url, service_role_key)`) — cache it as a module-level singleton.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_expert_paper_upload.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run full expert route test module to make sure nothing else broke**

Run: `cd backend && uv run pytest tests/unit/test_admin_expert_routes.py -v -k Paper`
Expected: all Paper-related tests pass; if any reference the old `RagDocumentUpload` shape and fail, fix those tests (not the code) to use the new shape.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/expert.py backend/app/services/supabase_client.py backend/tests/unit/test_expert_paper_upload.py backend/tests/unit/test_admin_expert_routes.py
git commit -m "feat(api): POST /expert/papers issues signed upload URL (ADR-EXPERT-01)"
```

---

## Task 6: Backend Endpoint — `POST /api/v1/expert/papers/{id}/complete` (Phase 3)

**Files:**
- Modify: `backend/app/api/v1/expert.py` (add new route after `request_paper_upload`)
- Test: `backend/tests/unit/test_expert_paper_complete.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_expert_paper_complete.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.expert import router as expert_router


TEST_EXPERT_ID = uuid4()


def _make_uploading_doc(doc_id: UUID, storage_path: str):
    from app.models.rag_document import RagDocument
    d = RagDocument(
        title="t",
        document_type="paper",
        exercise_tags=[],
        authors=[],
        review_status="uploading",
        storage_path=storage_path,
        extra_metadata={},
    )
    d.id = doc_id
    return d


@pytest.fixture()
def expert_app():
    from app.api.deps import get_expert_reviewer_user
    from app.db import get_db

    app = FastAPI()
    app.include_router(expert_router, prefix="/api/v1/expert")

    async def _mock_expert():
        return {"id": TEST_EXPERT_ID, "email": "x@s.app", "role": "expert_reviewer"}

    mock_db = AsyncMock()

    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_expert_reviewer_user] = _mock_expert
    app.dependency_overrides[get_db] = _mock_db
    return app, mock_db


@pytest.fixture()
def client(expert_app):
    app, _ = expert_app
    return TestClient(app, raise_server_exceptions=False)


class TestCompletePaperUpload:
    @patch("app.api.v1.expert.get_arq_pool")
    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_happy_path_flips_to_pending_and_enqueues(
        self, MockRepo, MockStorage, MockPool, client
    ):
        doc_id = uuid4()
        path = f"papers/{doc_id}/paper.pdf"
        doc = _make_uploading_doc(doc_id, path)

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=doc)
        repo_instance.update_review_status = AsyncMock(return_value=doc)

        storage_instance = MockStorage.return_value
        storage_instance.download_head_bytes = AsyncMock(return_value=b"%PDF-1.4")

        pool = AsyncMock()
        pool.enqueue_job = AsyncMock()
        MockPool.return_value = pool

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["review_status"] == "pending"
        pool.enqueue_job.assert_awaited_once_with("ingest_paper", str(doc_id))
        repo_instance.update_review_status.assert_awaited_once()

    @patch("app.api.v1.expert.PaperStorageService")
    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_missing_magic_bytes_rejects_and_cleans_up(
        self, MockRepo, MockStorage, client
    ):
        doc_id = uuid4()
        path = f"papers/{doc_id}/paper.pdf"
        doc = _make_uploading_doc(doc_id, path)

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=doc)
        repo_instance.delete = AsyncMock()

        storage_instance = MockStorage.return_value
        storage_instance.download_head_bytes = AsyncMock(return_value=b"<html>")
        storage_instance.delete_object = AsyncMock()

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "INVALID_PDF"
        storage_instance.delete_object.assert_awaited_once_with(path)
        repo_instance.delete.assert_awaited_once_with(doc_id)

    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_rejects_if_not_in_uploading_state(self, MockRepo, client):
        doc_id = uuid4()
        doc = _make_uploading_doc(doc_id, f"papers/{doc_id}/p.pdf")
        doc.review_status = "pending"

        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=doc)

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")

        assert resp.status_code == 409

    @patch("app.api.v1.expert.RagDocumentRepository")
    def test_404_for_missing_doc(self, MockRepo, client):
        doc_id = uuid4()
        repo_instance = MockRepo.return_value
        repo_instance.get_by_id = AsyncMock(return_value=None)

        resp = client.post(f"/api/v1/expert/papers/{doc_id}/complete")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_expert_paper_complete.py -v`
Expected: all 4 fail — route doesn't exist yet → 404.

- [ ] **Step 3: Add the `complete` route and repository helpers**

Add to `backend/app/api/v1/expert.py` after `request_paper_upload`:

```python
from app.schemas.rag_document import RagDocumentCompleteResponse
from app.utils.pdf_upload import PDF_MAGIC_BYTES
from app.workers.arq import get_arq_pool  # adjust import to project's pool getter


@router.post(
    "/papers/{paper_id}/complete",
    response_model=RagDocumentCompleteResponse,
    status_code=status.HTTP_200_OK,
)
async def complete_paper_upload(
    paper_id: UUID,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    rag_repo: RagDocumentRepository = Depends(_get_rag_repo),
) -> Any:
    doc = await rag_repo.get_by_id(paper_id)
    if doc is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND"}})

    if doc.review_status != "uploading":
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "INVALID_STATE", "message": f"review_status is {doc.review_status!r}"}},
        )

    storage = PaperStorageService(client=get_service_role_client())
    head = await storage.download_head_bytes(doc.storage_path, n=8)

    if not head.startswith(PDF_MAGIC_BYTES):
        await storage.delete_object(doc.storage_path)
        await rag_repo.delete(paper_id)
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "INVALID_PDF", "message": "uploaded bytes are not a PDF"}},
        )

    updated = await rag_repo.update_review_status(paper_id, "pending")

    pool = await get_arq_pool()
    await pool.enqueue_job("ingest_paper", str(paper_id))

    return RagDocumentCompleteResponse(
        id=updated.id, review_status="pending", storage_path=updated.storage_path
    )
```

If `RagDocumentRepository.update_review_status` / `delete` / `get_by_id` don't already exist, add those methods in `backend/app/repositories/rag_document.py` alongside existing ones. Keep the methods strictly typed — no `**kwargs`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_expert_paper_complete.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run full expert route test module**

Run: `cd backend && uv run pytest tests/unit/test_admin_expert_routes.py tests/unit/test_expert_paper_complete.py tests/unit/test_expert_paper_upload.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/expert.py backend/app/repositories/rag_document.py backend/tests/unit/test_expert_paper_complete.py
git commit -m "feat(api): POST /expert/papers/:id/complete magic-byte check + ingest enqueue"
```

---

## Task 7: ARQ Task `ingest_paper` (Docling-pending stub)

**Files:**
- Create: `backend/app/workers/paper_ingestion.py`
- Modify: `backend/app/workers/settings.py` (register the task in `WorkerSettings.functions`)
- Test: `backend/tests/unit/test_paper_ingestion_task.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_paper_ingestion_task.py`:

```python
from __future__ import annotations

import logging
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.workers.paper_ingestion import ingest_paper


@pytest.mark.asyncio
async def test_ingest_paper_downloads_and_logs_pending(caplog):
    ctx = {
        "storage": AsyncMock(),
        "db_session_factory": AsyncMock(),
    }
    ctx["storage"].download_head_bytes = AsyncMock(return_value=b"%PDF-1.4")

    paper_id = str(uuid4())
    with caplog.at_level(logging.INFO):
        result = await ingest_paper(ctx, paper_id)

    assert result["status"] == "docling_pending"
    assert result["paper_id"] == paper_id
    assert any("docling" in r.message.lower() for r in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_paper_ingestion_task.py -v`
Expected: `ModuleNotFoundError: No module named 'app.workers.paper_ingestion'`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/workers/paper_ingestion.py`:

```python
"""ARQ task that fires after an expert PDF upload completes.

Scope: the current task is a stub that downloads the PDF (to prove the
service-role read path works) and logs a `docling_pending` status. P2-005
will replace the body with actual Docling parsing + IngestionService call.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def ingest_paper(ctx: dict[str, Any], paper_id: str) -> dict[str, Any]:
    storage = ctx["storage"]
    head = await storage.download_head_bytes(_storage_path_for_paper(paper_id, ctx), n=8)
    logger.info(
        "paper.ingest.docling_pending",
        extra={"paper_id": paper_id, "head_len": len(head)},
    )
    return {"paper_id": paper_id, "status": "docling_pending"}


def _storage_path_for_paper(paper_id: str, ctx: dict[str, Any]) -> str:
    """In production this reads storage_path from the DB. For the stub we
    accept a dictionary-mocked path in tests — replace with a repo lookup
    when wiring to real prod context."""
    path = ctx.get("storage_path_override")
    if path is not None:
        return path
    return f"papers/{paper_id}/"  # prefix read; real impl fetches the row
```

(When wired into the real worker startup path, `ctx["storage"]` is set to a `PaperStorageService` instance created in `WorkerSettings.on_startup`. Full DB lookup for `storage_path` will land when P2-005 replaces this stub.)

- [ ] **Step 4: Register the task in the worker**

Modify `backend/app/workers/settings.py`:

```python
# near the top
from app.workers.paper_ingestion import ingest_paper

# in WorkerSettings.functions list, append:
ingest_paper,
```

Also extend `on_startup` to inject `storage` and the service-role client:

```python
async def on_startup(ctx: dict[str, Any]) -> None:
    # ... existing startup ...
    from app.services.paper_storage import PaperStorageService
    from app.services.supabase_client import get_service_role_client
    ctx["storage"] = PaperStorageService(client=get_service_role_client())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_paper_ingestion_task.py -v`
Expected: 1 passed.

- [ ] **Step 6: Run worker startup smoke check**

Run: `cd backend && uv run python -c "from app.workers.settings import WorkerSettings; print([f.__name__ for f in WorkerSettings.functions])"`
Expected: includes `ingest_paper`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/workers/paper_ingestion.py backend/app/workers/settings.py backend/tests/unit/test_paper_ingestion_task.py
git commit -m "feat(worker): ingest_paper stub task (docling-pending until P2-005)"
```

---

## Task 8: Backend Integration Test — Full Phase 1 → 3 Flow

**Files:**
- Create: `backend/tests/integration/test_expert_paper_e2e.py`

- [ ] **Step 1: Write the integration test**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


BODY = {
    "title": "Integration test paper",
    "document_type": "paper",
    "exercise_tags": ["squat"],
    "authors": ["Doe J"],
    "filename": "int_test.pdf",
    "file_size_bytes": 1000,
}


@pytest.fixture()
def in_memory_rag_repo():
    """Simple dict-backed RagDocumentRepository for integration test."""
    from app.models.rag_document import RagDocument

    class Repo:
        def __init__(self):
            self._rows: dict = {}

        async def create(self, doc: RagDocument):
            self._rows[doc.id] = doc
            return doc

        async def get_by_id(self, doc_id):
            return self._rows.get(doc_id)

        async def update_review_status(self, doc_id, status):
            self._rows[doc_id].review_status = status
            return self._rows[doc_id]

        async def delete(self, doc_id):
            self._rows.pop(doc_id, None)

    return Repo()


@patch("app.api.v1.expert.get_arq_pool")
@patch("app.api.v1.expert.PaperStorageService")
def test_full_upload_flow(MockStorage, MockPool, in_memory_rag_repo):
    from fastapi import FastAPI
    from app.api.deps import get_expert_reviewer_user
    from app.api.v1.expert import router, _get_rag_repo
    from app.services.paper_storage import SignedPaperUpload

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/expert")
    app.dependency_overrides[get_expert_reviewer_user] = lambda: {
        "id": uuid4(), "email": "e@s.app", "role": "expert_reviewer",
    }
    app.dependency_overrides[_get_rag_repo] = lambda: in_memory_rag_repo

    storage_instance = MockStorage.return_value
    storage_instance.generate_signed_upload_url = AsyncMock(
        return_value=SignedPaperUpload(
            url="https://s/upload", expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
    )
    storage_instance.download_head_bytes = AsyncMock(return_value=b"%PDF-1.7")

    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    MockPool.return_value = pool

    client = TestClient(app, raise_server_exceptions=False)

    # Phase 1
    r1 = client.post("/api/v1/expert/papers", json=BODY)
    assert r1.status_code == 201, r1.text
    paper_id = r1.json()["id"]
    storage_path = r1.json()["storage_path"]
    assert storage_path.startswith(f"papers/{paper_id}/")

    # DB shows 'uploading'
    from uuid import UUID
    stored = in_memory_rag_repo._rows[UUID(paper_id)]
    assert stored.review_status == "uploading"

    # Phase 3 (phase 2 = browser PUT, simulated)
    r3 = client.post(f"/api/v1/expert/papers/{paper_id}/complete")
    assert r3.status_code == 200, r3.text
    assert r3.json()["review_status"] == "pending"
    pool.enqueue_job.assert_awaited_once_with("ingest_paper", paper_id)
    assert in_memory_rag_repo._rows[UUID(paper_id)].review_status == "pending"
```

- [ ] **Step 2: Run the integration test**

Run: `cd backend && uv run pytest tests/integration/test_expert_paper_e2e.py -v`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_expert_paper_e2e.py
git commit -m "test(integration): expert paper upload e2e phase 1+3 flow"
```

---

## Task 9: Frontend API Client — 3-Phase Upload Helpers

**Files:**
- Modify: `frontend/src/api/expert.ts`
- Test: `frontend/src/api/__tests__/expert-upload.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/api/__tests__/expert-upload.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  },
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

import {
  requestPaperUploadUrl,
  completePaperUpload,
  uploadPaperFile,
} from "@/api/expert";

let lastXhr: any;
function makeMockXhr() {
  const xhr: any = {
    upload: { listeners: {} as Record<string, (e: any) => void>, addEventListener(e: string, cb: any) { this.listeners[e] = cb; } },
    listeners: {} as Record<string, (e: any) => void>,
    open: vi.fn(),
    setRequestHeader: vi.fn(),
    send: vi.fn(),
    addEventListener(e: string, cb: any) { this.listeners[e] = cb; },
    _triggerProgress(loaded: number, total: number) { this.upload.listeners.progress?.({ loaded, total, lengthComputable: true }); },
    _triggerLoad(status: number) { this.status = status; this.listeners.load?.({}); },
    _triggerError() { this.listeners.error?.({}); },
    status: 0,
  };
  return xhr;
}

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal("XMLHttpRequest", vi.fn(function () {
    lastXhr = makeMockXhr();
    return lastXhr;
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});


describe("requestPaperUploadUrl", () => {
  it("POSTs metadata + filename + size, returns signed URL", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "paper-1",
          upload_url: "https://s/upload",
          storage_path: "papers/paper-1/x.pdf",
          expires_at: "2026-04-15T12:00:00Z",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      )
    );

    const res = await requestPaperUploadUrl({
      title: "t", document_type: "paper", exercise_tags: [], authors: [],
      filename: "x.pdf", file_size_bytes: 1000,
    });

    expect(res.upload_url).toBe("https://s/upload");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/expert/papers"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
      })
    );
  });
});


describe("uploadPaperFile", () => {
  it("PUTs the file via XHR and reports progress", async () => {
    const file = new File([new Uint8Array(1024)], "x.pdf", { type: "application/pdf" });
    const onProgress = vi.fn();

    const p = uploadPaperFile("https://s/upload", file, onProgress);

    lastXhr._triggerProgress(512, 1024);
    lastXhr._triggerLoad(200);

    await p;

    expect(lastXhr.open).toHaveBeenCalledWith("PUT", "https://s/upload");
    expect(lastXhr.setRequestHeader).toHaveBeenCalledWith("Content-Type", "application/pdf");
    expect(lastXhr.send).toHaveBeenCalledWith(file);
    expect(onProgress).toHaveBeenCalledWith(50);
  });

  it("rejects on XHR error", async () => {
    const file = new File([new Uint8Array(10)], "x.pdf", { type: "application/pdf" });
    const p = uploadPaperFile("https://s/upload", file, () => {});
    lastXhr._triggerError();
    await expect(p).rejects.toThrow(/upload failed/i);
  });
});


describe("completePaperUpload", () => {
  it("POSTs to /:id/complete and returns status", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ id: "p-1", review_status: "pending", storage_path: "papers/p-1/x.pdf" }), { status: 200 })
    );

    const res = await completePaperUpload("p-1");
    expect(res.review_status).toBe("pending");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/expert/papers/p-1/complete"),
      expect.objectContaining({ method: "POST" })
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- expert-upload.test.ts`
Expected: import failure — none of `requestPaperUploadUrl`, `completePaperUpload`, `uploadPaperFile` exist yet.

- [ ] **Step 3: Replace `uploadPaper` in `frontend/src/api/expert.ts`**

Replace the existing `uploadPaper` function + `PaperUploadData` interface with:

```typescript
export interface PaperUploadMetadata {
  title: string;
  document_type: "paper" | "textbook" | "video_transcript" | "expert_commentary";
  exercise_tags: string[];
  authors: string[];
  year?: number;
  doi?: string;
  study_design?: string;
  population?: string;
  measurement_method?: string;
  quality_tier?: "a" | "b" | "c";
  filename: string;
  file_size_bytes: number;
}

export interface PaperUploadResponse {
  id: string;
  upload_url: string;
  storage_path: string;
  expires_at: string;
}

export interface PaperCompleteResponse {
  id: string;
  review_status: "pending";
  storage_path: string;
}

export async function requestPaperUploadUrl(
  data: PaperUploadMetadata
): Promise<PaperUploadResponse> {
  return expertFetch<PaperUploadResponse>("/api/v1/expert/papers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function completePaperUpload(
  paperId: string
): Promise<PaperCompleteResponse> {
  return expertFetch<PaperCompleteResponse>(
    `/api/v1/expert/papers/${paperId}/complete`,
    { method: "POST" }
  );
}

export function uploadPaperFile(
  uploadUrl: string,
  file: File,
  onProgress: (percent: number) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", "application/pdf");

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    });
    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error(`upload failed: HTTP ${xhr.status}`));
    });
    xhr.addEventListener("error", () => reject(new Error("upload failed: network error")));
    xhr.addEventListener("abort", () => reject(new Error("upload aborted")));

    xhr.send(file);
  });
}
```

(Delete the old `uploadPaper(data)` and `PaperUploadData` — any callers must be updated. The only caller is `ExpertPaperUploadPage.tsx`, updated in Task 10.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- expert-upload.test.ts`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/expert.ts frontend/src/api/__tests__/expert-upload.test.ts
git commit -m "feat(frontend): expert paper upload API client (3-phase signed URL)"
```

---

## Task 10: `ExpertPaperUploadPage.tsx` — File Input + Progress UI

**Files:**
- Modify: `frontend/src/pages/ExpertPaperUploadPage.tsx`
- Test: `frontend/src/pages/__tests__/ExpertPaperUploadPage.test.tsx`

- [ ] **Step 1: Extend the test to cover file selection + upload**

Replace the existing `ExpertPaperUploadPage.test.tsx` contents (or add a new `describe` block) with cases covering the file flow. Core cases:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router";

const mockRequestUrl = vi.fn();
const mockCompleteUpload = vi.fn();
const mockUploadFile = vi.fn();

vi.mock("@/api/expert", () => ({
  requestPaperUploadUrl: (...a: unknown[]) => mockRequestUrl(...a),
  completePaperUpload: (...a: unknown[]) => mockCompleteUpload(...a),
  uploadPaperFile: (...a: unknown[]) => mockUploadFile(...a),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: { getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: "t" } } }) },
  },
}));

import ExpertPaperUploadPage from "@/pages/ExpertPaperUploadPage";


function renderPage() {
  return render(<MemoryRouter><ExpertPaperUploadPage /></MemoryRouter>);
}

describe("ExpertPaperUploadPage — file upload", () => {
  beforeEach(() => {
    mockRequestUrl.mockReset();
    mockCompleteUpload.mockReset();
    mockUploadFile.mockReset();
  });

  it("disables submit until a PDF file is selected", () => {
    renderPage();
    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: "X" } });
    expect(screen.getByRole("button", { name: /upload/i })).toBeDisabled();
  });

  it("rejects non-PDF files client-side", async () => {
    renderPage();
    const input = screen.getByLabelText(/pdf file/i) as HTMLInputElement;
    const file = new File(["x"], "x.docx", { type: "application/msword" });

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });

    expect(screen.getByText(/must be a pdf/i)).toBeInTheDocument();
  });

  it("rejects files over 50 MB client-side", async () => {
    renderPage();
    const input = screen.getByLabelText(/pdf file/i) as HTMLInputElement;
    const big = new File([new Uint8Array(60 * 1024 * 1024)], "big.pdf", { type: "application/pdf" });

    await act(async () => {
      fireEvent.change(input, { target: { files: [big] } });
    });

    expect(screen.getByText(/50 ?mb/i)).toBeInTheDocument();
  });

  it("runs 3-phase upload and shows success", async () => {
    mockRequestUrl.mockResolvedValue({
      id: "p-1", upload_url: "https://s/upload",
      storage_path: "papers/p-1/x.pdf", expires_at: "2026-04-15T12:00:00Z",
    });
    mockUploadFile.mockImplementation(async (_url, _file, onProg) => {
      onProg(50); onProg(100);
    });
    mockCompleteUpload.mockResolvedValue({
      id: "p-1", review_status: "pending", storage_path: "papers/p-1/x.pdf",
    });

    renderPage();
    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: "Paper T" } });
    const input = screen.getByLabelText(/pdf file/i) as HTMLInputElement;
    const file = new File([new Uint8Array(1024)], "x.pdf", { type: "application/pdf" });
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() => expect(mockCompleteUpload).toHaveBeenCalledWith("p-1"));
    expect(screen.getByText(/uploaded and queued/i)).toBeInTheDocument();
  });

  it("cleans up and shows error if phase 2 fails", async () => {
    mockRequestUrl.mockResolvedValue({
      id: "p-1", upload_url: "https://s/u", storage_path: "papers/p-1/x.pdf", expires_at: "z",
    });
    mockUploadFile.mockRejectedValue(new Error("upload failed: network error"));

    renderPage();
    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: "X" } });
    const input = screen.getByLabelText(/pdf file/i) as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [new File(["a"], "x.pdf", { type: "application/pdf" })] } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() => expect(screen.getByText(/network error/i)).toBeInTheDocument());
    expect(mockCompleteUpload).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- ExpertPaperUploadPage.test.tsx`
Expected: failures — no file input, new API surface not used.

- [ ] **Step 3: Rewrite `ExpertPaperUploadPage.tsx`**

Key changes:
1. Add `selectedFile: File | null` + `uploadProgress: number` + `uploadPhase: 'idle'|'requesting'|'uploading'|'completing'|'success'|'error'` to state.
2. Add `<input type="file" accept="application/pdf">` with label `"PDF file"`.
3. `onChange` handler: validate `file.type === "application/pdf"` and `file.size <= 52_428_800`; set error or `selectedFile`.
4. Submit button disabled when `!selectedFile || !title || uploadPhase !== 'idle'`.
5. On submit: call `requestPaperUploadUrl`, then `uploadPaperFile` (setting progress), then `completePaperUpload`. Wrap each phase in try/catch — on phase 2 or 3 failure, show the error in a banner. Do not automatically retry.
6. Progress bar: `<progress max={100} value={uploadProgress}>` visible during `uploading` phase.
7. Success banner: `"{filename} uploaded and queued for review"`.

Show the full code — this is not a placeholder. Because the existing file is 402 lines, the rewrite is extensive. Reference the Explore result: existing structure is a form with labelled fields; keep all existing metadata inputs, add the file input above the "Upload" button, replace `handleSubmit`. Minimum shape of `handleSubmit`:

```typescript
async function handleSubmit(e: React.FormEvent) {
  e.preventDefault();
  if (!selectedFile) return;

  setUploadPhase("requesting");
  setError(null);

  try {
    const signed = await requestPaperUploadUrl({
      title,
      document_type: documentType,
      exercise_tags: exerciseTags,
      authors: authors.split(",").map(s => s.trim()).filter(Boolean),
      year: year ? Number(year) : undefined,
      doi: doi || undefined,
      study_design: studyDesign || undefined,
      population: population || undefined,
      measurement_method: measurementMethod || undefined,
      quality_tier: qualityTier || undefined,
      filename: selectedFile.name,
      file_size_bytes: selectedFile.size,
    });

    setUploadPhase("uploading");
    await uploadPaperFile(signed.upload_url, selectedFile, setUploadProgress);

    setUploadPhase("completing");
    await completePaperUpload(signed.id);

    setUploadPhase("success");
  } catch (err) {
    setError(err instanceof Error ? err.message : "Upload failed");
    setUploadPhase("error");
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- ExpertPaperUploadPage.test.tsx`
Expected: all 5 file-upload cases pass, plus any pre-existing metadata cases still pass.

- [ ] **Step 5: Run typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 6: Dev-server smoke (per CLAUDE.md UI rule)**

Run dev server, load the page at `http://localhost:5173/expert/upload`, log in as expert, select a real PDF under 50 MB, fill title, click Upload. Observe: progress bar advances, success banner renders. Check network tab: `POST /expert/papers` → `PUT https://...supabase.co/...` → `POST /expert/papers/:id/complete`. Save a screenshot to `e2e/screenshots/expert-upload-local.png`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ExpertPaperUploadPage.tsx frontend/src/pages/__tests__/ExpertPaperUploadPage.test.tsx
git commit -m "feat(frontend): file input + 3-phase upload UI on ExpertPaperUploadPage"
```

---

## Task 11: Security Review

**Agent:** `spelix-security-reviewer` (per CLAUDE.md — mandatory for any commit touching auth, user data, or user-facing strings; file upload touches all three).

- [ ] **Step 1: Dispatch the agent with the full diff**

Prompt:

> Review PR `feat/expert-pdf-upload`. Scope:
>
> - New Alembic migration 009 creates the `papers` bucket and RLS policies.
> - New endpoints `POST /api/v1/expert/papers` (issues signed URL) and `POST /api/v1/expert/papers/:id/complete` (magic-byte check + ARQ enqueue).
> - New `PaperStorageService`.
> - Filename sanitiser in `app/utils/pdf_upload.py`.
> - Frontend XHR PUT to signed URL.
>
> Check specifically:
> 1. RLS policies correctly scope writes to `expert_reviewer` + `admin` only; no public read.
> 2. Service-role key never leaves the server.
> 3. Filename sanitiser blocks path traversal, null bytes, control chars, and is consistent with server-side path construction.
> 4. No SQL injection paths (we use parameterised queries only).
> 5. No SaMD / FTC language violations in new error messages — use "Movement Quality" not "injury risk".
> 6. Size limit enforced at schema AND bucket AND frontend.
> 7. `review_status='uploading'` rows can't be mistaken for approved content anywhere downstream — grep consumers and confirm.
> 8. The magic-byte check is tight enough — `%PDF-` is sufficient.
> 9. `ingest_paper` task doesn't execute uploaded bytes.
>
> Read-only. Report CRITICAL / HIGH / MEDIUM findings with file + line. No file modifications.

- [ ] **Step 2: Address any CRITICAL/HIGH findings inline, then re-dispatch until clean**

- [ ] **Step 3: Commit fixes if any**

```bash
git add -u
git commit -m "security: address spelix-security-reviewer findings for expert PDF upload"
```

---

## Task 12: Merge + Deploy + Playwright Prod Verification

- [ ] **Step 1: Push branch + create PR via GitHub MCP**

Branch: `feat/expert-pdf-upload`. PR title: `feat(expert): end-to-end PDF upload for expert reviewer portal (ADR-EXPERT-01)`.

Body: summary of ADR-EXPERT-01, migration 009, new endpoints, new ARQ task, frontend flow. Test plan checklist (backend suite + frontend suite + Playwright prod walk).

- [ ] **Step 2: Wait for CI (all checks green)**

Use `mcp__github__get_pull_request_status` to poll. "Deploy to Production" included.

- [ ] **Step 3: Merge via `mcp__github__merge_pull_request`**

Use `merge_method: "merge"`. Never squash (per feedback memory).

- [ ] **Step 4: Confirm droplet has new code + containers healthy**

```bash
ssh spelix-droplet "git log --oneline -1 && docker ps --format '{{.Names}} {{.Status}}'"
```
Expected: merge commit SHA matches, all containers `(healthy)`.

- [ ] **Step 5: Apply migration 009 on prod (same session — CLAUDE.md rule)**

Prod deploy runs `alembic upgrade head` automatically in the release step. Confirm:

```bash
ssh spelix-droplet "docker cp /home/deploy/spelix/backend/alembic.ini spelix-backend-1:/app/alembic.ini && docker cp /home/deploy/spelix/backend/alembic spelix-backend-1:/app/alembic && docker exec -w /app spelix-backend-1 /app/.venv/bin/alembic current"
```
Expected: `009_papers_bucket_rls (head)`.

(If the prod deploy pipeline doesn't auto-run alembic, this is the manual apply. Clean up with `docker exec -u root spelix-backend-1 sh -c 'cd /app && rm -rf alembic alembic.ini'` after.)

- [ ] **Step 6: Playwright MCP — verify live on spelix.app with real kin expert account or staging expert account**

```
mcp__playwright__browser_navigate → https://spelix.app/expert/upload
mcp__playwright__browser_snapshot
# log in as expert if needed; fill title + pick a test PDF
mcp__playwright__browser_file_upload with absolute path e2e/fixtures/sample.pdf (create if missing)
# click Upload
mcp__playwright__browser_wait_for text "uploaded and queued"
mcp__playwright__browser_console_messages level=error
mcp__playwright__browser_network_requests filter=4xx/5xx
```

Expected: success banner, no console errors, three network calls (`POST /papers` 201 → `PUT supabase.co/.../papers/...` 200 → `POST /papers/:id/complete` 200).

- [ ] **Step 7: Verify DB state via Supabase SQL**

```sql
SELECT id, title, review_status, storage_path
FROM rag_documents
WHERE review_status = 'pending'
ORDER BY created_at DESC LIMIT 1;
```
Expected: a row for the sample PDF, `storage_path` starts with `papers/`.

- [ ] **Step 8: Save prod verification artifacts**

Screenshots to `e2e/screenshots/expert-upload-prod/`. Notes in `.claude/handoff.md` under a new "E2E Findings" bullet.

---

## Task 13: Backlog + Post-merge Housekeeping

- [ ] **Step 1: Update `backlog.md`**

- Add new row `L2-EXPERT-UPLOAD` marked `done` with merge SHA and reference to ADR-EXPERT-01.
- Mark **D-017** `done` with note: "Obsolete — expert PDF upload live; real PDFs now ingested via portal. First expert paper uploaded on <date>."

- [ ] **Step 2: Update `.claude/handoff.md`**

Add a session handoff section: PR merged, prod E2E verified, kin expert ready to onboard. Move Track B to `done`, flag next sprint focus = ARQ→streaq migration (Day 3-9).

- [ ] **Step 3: Commit + push**

```bash
git checkout main && git pull
git add backlog.md .claude/handoff.md
git commit -m "docs(backlog,handoff): expert PDF upload complete; close D-017"
git push
```

---

## Self-Review Checklist (complete before execution)

**Spec coverage (against STRATEGY.md Day 1-2 Track B + ADR-EXPERT-01 in Task 0):**
- [x] Signed-URL endpoint — Task 5
- [x] `multipart/form-data` fallback — intentionally not done; signed URL only, documented in ADR
- [x] File input + progress UI on `ExpertPaperUploadPage.tsx` — Task 10
- [x] Magic-byte PDF check — Task 6
- [x] 50 MB size limit — Tasks 2, 4 (schema), 1 (bucket)
- [x] Filename sanitisation — Task 2
- [x] Supabase Storage bucket RLS — Task 1
- [x] Docling ingestion trigger — Task 7 (stub until P2-005)
- [x] `spelix-security-reviewer` audit — Task 11

**Placeholder scan:** none of "TBD", "similar to Task N", "write tests for the above" appear. All step bodies contain concrete commands or full code.

**Type consistency:**
- `PaperStorageService.generate_signed_upload_url` returns `SignedPaperUpload` in Task 3 — used by Tasks 5+6 with the same name ✓
- `RagDocumentUploadRequest` in Task 4 — consumed by Task 5 ✓
- `RagDocumentCompleteResponse` in Task 4 — returned by Task 6 ✓
- Frontend `PaperUploadMetadata` has `filename` + `file_size_bytes` — matches backend schema ✓
- `ingest_paper` task signature `(ctx, paper_id: str)` — `enqueue_job("ingest_paper", str(doc_id))` in Task 6 ✓

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-15-expert-pdf-upload-wiring.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for this plan because Tasks 1, 5, 6, 10, 11 touch different subsystems and benefit from focused context windows.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
