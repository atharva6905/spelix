# FR-EXPV-08 Threshold Validation UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Expert Reviewer an in-portal view of every angle threshold in `config/thresholds_v1.json` and a lightweight workflow to flag thresholds that conflict with literature, submitting a proposed value + citation that an admin can review/resolve.

**Architecture:** Thresholds remain read-only in `config/thresholds_v1.json` (FR-SCOR-11 — PR review IS the approval flow). A new `threshold_flags` table stores reviewer-submitted flags with structured proposals. Backend exposes `GET /expert/thresholds` (returns live config) + `POST /expert/thresholds/flags` + `GET /expert/thresholds/flags` for the reviewer, plus `GET/PATCH /admin/threshold-flags/{id}` for admin resolution. Frontend adds `ThresholdValidationPage` under `/expert/thresholds` linked from the Expert portal header.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, React 19, Vite 8, TypeScript strict, Tailwind CSS 4, vitest, pytest.

---

## Prerequisites

- Current migration head: `021_coach_brain_status_idx`. New migration will be `022_threshold_flags`.
- Expert portal file: `frontend/src/pages/ExpertPortalPage.tsx`.
- Existing auth dependency: `get_expert_reviewer_user` in `backend/app/api/deps.py`, `get_admin_user` exists for admin routes.
- ThresholdConfig loader lives in `backend/app/config.py::ThresholdConfig`.
- Threshold file: `config/thresholds_v1.json` (read-only, never write from app).
- SRS reference: §3.15 FR-EXPV-08 ("Angle threshold validation interface: Expert Reviewer can review current angle thresholds per exercise/variant and flag any threshold that conflicts with literature, providing a citation for the correct value").

---

## File Structure

**Backend (Create):**
- `backend/alembic/versions/022_add_threshold_flags.py` — migration creating the table + RLS policies
- `backend/app/models/threshold_flag.py` — SQLAlchemy model
- `backend/app/repositories/threshold_flag.py` — async repo with `create`, `list_by_reviewer`, `list_all`, `get_by_id`, `update_status`
- `backend/app/schemas/threshold_flag.py` — Pydantic schemas: `ThresholdRow`, `ThresholdListing`, `ThresholdFlagCreate`, `ThresholdFlagResponse`, `ThresholdFlagResolveAction`
- `backend/app/services/threshold_flag.py` — business logic: load current from `ThresholdConfig`, assemble `ThresholdListing`, `create_flag` (validates section/key + snapshots current), `resolve_flag`
- `backend/tests/unit/test_threshold_flag_repo.py`
- `backend/tests/unit/test_threshold_flag_schemas.py`
- `backend/tests/unit/test_threshold_flag_service.py`
- `backend/tests/unit/test_expert_thresholds_api.py`
- `backend/tests/unit/test_admin_threshold_flags_api.py`

**Backend (Modify):**
- `backend/app/api/v1/expert.py` — add `GET /thresholds`, `POST /thresholds/flags`, `GET /thresholds/flags` sections (keep existing dependency pattern)
- `backend/app/api/v1/admin.py` — add `GET /admin/threshold-flags` and `PATCH /admin/threshold-flags/{id}`
- `backend/app/models/__init__.py` — register `ThresholdFlag` so Alembic autogen sees it (grep existing file for pattern — likely explicit import list)

**Frontend (Create):**
- `frontend/src/pages/ExpertThresholdsPage.tsx` — reviewer page
- `frontend/src/pages/__tests__/ExpertThresholdsPage.test.tsx`
- `frontend/src/api/__tests__/expert-thresholds.test.ts`
- `frontend/src/components/ThresholdFlagModal.tsx` — flag submission modal (separate file because modal state is self-contained)
- `frontend/src/components/__tests__/ThresholdFlagModal.test.tsx`

**Frontend (Modify):**
- `frontend/src/api/expert.ts` — add `getThresholdListing`, `createThresholdFlag`, `listMyThresholdFlags` + corresponding TS types
- `frontend/src/pages/ExpertPortalPage.tsx` — add "Validate Thresholds" header link next to "Upload Paper"
- `frontend/src/routes.tsx` — register `/expert/thresholds` route

**Docs:**
- `decisions.md` — ADR-EXPV-08 (persistence choice + PR-as-approval restated)
- `backlog.md` — close FR-EXPV-08 row with commit SHA once shipped

---

## Scope Boundaries (Out of Scope)

- **Editing threshold values from the UI.** Values remain governed by PR review of `config/thresholds_v1.json` (FR-SCOR-11). The UI only submits flags; it never mutates the config file.
- **Auto-creating GitHub issues.** A flag is a DB row only; an admin routes it to a PR manually. Automation is a future enhancement.
- **`experience_tolerance` / `scoring_weights` / `score_descriptors` / `confidence_landmark_weights` / `phase_multipliers` sections.** SRS FR-EXPV-08 scopes to **angle thresholds per exercise/variant**. We surface `squat`, `bench`, `deadlift`, and `control` sections. Other sections are filtered out of the listing.
- **Variant-specific rollup.** Keys like `rep_detection_depth_angle_romanian_deg` include the variant suffix in the key name itself; we surface them as-is without a separate "variant" axis.

---

## Task 1: Alembic migration for `threshold_flags`

**Files:**
- Create: `backend/alembic/versions/022_add_threshold_flags.py`
- Test: migration validated via `alembic upgrade head` + downgrade round-trip

- [ ] **Step 1: Write the migration file**

```python
"""add threshold_flags table for FR-EXPV-08

Revision ID: 022_threshold_flags
Revises: 021_coach_brain_status_idx
Create Date: 2026-04-21

Adds a lightweight audit table capturing Expert Reviewer flags against
angle thresholds in config/thresholds_v1.json. Values in the config file
remain the source of truth (FR-SCOR-11 — changes ship via PR review);
this table only records *proposals* for admin triage.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "022_threshold_flags"
down_revision = "021_coach_brain_status_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "threshold_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        # No DDL FK to auth.users — enforced via RLS (root CLAUDE.md rule).
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section", sa.String(length=30), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=False),
        sa.Column("current_citation", sa.Text(), nullable=True),
        sa.Column("proposed_value", sa.Float(), nullable=False),
        sa.Column("proposed_citation", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False,
                  server_default=sa.text("'open'")),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'rejected')",
            name="threshold_flags_status_check",
        ),
        sa.CheckConstraint(
            "char_length(rationale) >= 20",
            name="threshold_flags_rationale_min_len",
        ),
        sa.CheckConstraint(
            "char_length(proposed_citation) >= 5",
            name="threshold_flags_citation_min_len",
        ),
    )
    op.create_index(
        "ix_threshold_flags_reviewer_created",
        "threshold_flags", ["reviewer_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "ix_threshold_flags_status_created",
        "threshold_flags", ["status", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "ix_threshold_flags_section_key",
        "threshold_flags", ["section", "key"],
    )

    # RLS: reviewer sees own + admin sees all; insert by expert_reviewer/admin;
    # update restricted to admin.
    op.execute("ALTER TABLE threshold_flags ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY threshold_flags_select_own_or_admin ON threshold_flags
        FOR SELECT
        USING (
            reviewer_id = auth.uid()
            OR (auth.jwt() ->> 'role')::text IN ('admin', 'expert_reviewer')
        );
    """)
    op.execute("""
        CREATE POLICY threshold_flags_insert_expert_or_admin ON threshold_flags
        FOR INSERT
        WITH CHECK (
            (auth.jwt() ->> 'role')::text IN ('admin', 'expert_reviewer')
            AND reviewer_id = auth.uid()
        );
    """)
    op.execute("""
        CREATE POLICY threshold_flags_update_admin_only ON threshold_flags
        FOR UPDATE
        USING ((auth.jwt() ->> 'role')::text = 'admin');
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS threshold_flags_update_admin_only ON threshold_flags;")
    op.execute("DROP POLICY IF EXISTS threshold_flags_insert_expert_or_admin ON threshold_flags;")
    op.execute("DROP POLICY IF EXISTS threshold_flags_select_own_or_admin ON threshold_flags;")
    op.drop_index("ix_threshold_flags_section_key", table_name="threshold_flags")
    op.drop_index("ix_threshold_flags_status_created", table_name="threshold_flags")
    op.drop_index("ix_threshold_flags_reviewer_created", table_name="threshold_flags")
    op.drop_table("threshold_flags")
```

- [ ] **Step 2: Verify migration applies and reverts cleanly**

Run (from `backend/`):
```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

Expected: all three commands succeed. `alembic current` after last command shows `022_threshold_flags (head)`.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/022_add_threshold_flags.py
git commit -m "feat(models): add threshold_flags table for FR-EXPV-08"
```

---

## Task 2: SQLAlchemy model + repository

**Files:**
- Create: `backend/app/models/threshold_flag.py`
- Modify: `backend/app/models/__init__.py` — add `from .threshold_flag import ThresholdFlag`
- Create: `backend/app/repositories/threshold_flag.py`
- Test: `backend/tests/unit/test_threshold_flag_repo.py`

- [ ] **Step 1: Write failing repo test**

```python
# backend/tests/unit/test_threshold_flag_repo.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.threshold_flag import ThresholdFlag
from app.repositories.threshold_flag import ThresholdFlagRepository


pytestmark = pytest.mark.asyncio


async def _make_flag(reviewer_id):
    return ThresholdFlag(
        id=uuid4(),
        reviewer_id=reviewer_id,
        section="squat",
        key="knee_valgus_caution_deg",
        current_value=5.0,
        current_citation="Myer et al. 2010",
        proposed_value=8.0,
        proposed_citation="Krosshaug 2016 — 8° not replicated",
        rationale="Original Myer finding did not replicate in larger cohorts.",
        status="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


async def test_create_returns_persisted_flag(db_session: AsyncSession):
    repo = ThresholdFlagRepository(db_session)
    reviewer_id = uuid4()
    flag = await _make_flag(reviewer_id)

    created = await repo.create(flag)
    await db_session.flush()

    assert created.id == flag.id
    assert created.reviewer_id == reviewer_id
    assert created.status == "open"


async def test_list_by_reviewer_orders_created_desc(db_session: AsyncSession):
    repo = ThresholdFlagRepository(db_session)
    reviewer_id = uuid4()
    first = await _make_flag(reviewer_id)
    second = await _make_flag(reviewer_id)
    second.created_at = datetime.now(timezone.utc)
    await repo.create(first)
    await repo.create(second)
    await db_session.flush()

    rows = await repo.list_by_reviewer(reviewer_id, limit=10, offset=0)

    assert [r.id for r in rows] == [second.id, first.id]


async def test_update_status_sets_resolution_metadata(db_session: AsyncSession):
    repo = ThresholdFlagRepository(db_session)
    reviewer_id = uuid4()
    admin_id = uuid4()
    flag = await _make_flag(reviewer_id)
    await repo.create(flag)
    await db_session.flush()

    updated = await repo.update_status(
        flag.id,
        status="resolved",
        resolution_note="Merged in PR #XXX.",
        resolved_by=admin_id,
    )

    assert updated is not None
    assert updated.status == "resolved"
    assert updated.resolution_note == "Merged in PR #XXX."
    assert updated.resolved_by == admin_id
    assert updated.resolved_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_threshold_flag_repo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.threshold_flag'`.

- [ ] **Step 3: Write the model**

```python
# backend/app/models/threshold_flag.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ThresholdFlag(Base):
    __tablename__ = "threshold_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    section: Mapped[str] = mapped_column(String(30), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    current_citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_value: Mapped[float] = mapped_column(Float, nullable=False)
    proposed_citation: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'open'")
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'resolved', 'rejected')",
            name="threshold_flags_status_check",
        ),
        CheckConstraint(
            "char_length(rationale) >= 20", name="threshold_flags_rationale_min_len"
        ),
        CheckConstraint(
            "char_length(proposed_citation) >= 5",
            name="threshold_flags_citation_min_len",
        ),
        Index(
            "ix_threshold_flags_reviewer_created",
            "reviewer_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index(
            "ix_threshold_flags_status_created",
            "status",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index("ix_threshold_flags_section_key", "section", "key"),
    )
```

- [ ] **Step 4: Register model in `app/models/__init__.py`**

Read `backend/app/models/__init__.py` and add the import in the existing pattern (alphabetical if that's the convention):

```python
from .threshold_flag import ThresholdFlag  # noqa: F401
```

- [ ] **Step 5: Write the repository**

```python
# backend/app/repositories/threshold_flag.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.threshold_flag import ThresholdFlag


class ThresholdFlagRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, flag: ThresholdFlag) -> ThresholdFlag:
        self._db.add(flag)
        await self._db.flush()
        return flag

    async def get_by_id(self, flag_id: UUID) -> ThresholdFlag | None:
        result = await self._db.execute(
            select(ThresholdFlag).where(ThresholdFlag.id == flag_id)
        )
        return result.scalar_one_or_none()

    async def list_by_reviewer(
        self, reviewer_id: UUID, *, limit: int, offset: int
    ) -> list[ThresholdFlag]:
        stmt = (
            select(ThresholdFlag)
            .where(ThresholdFlag.reviewer_id == reviewer_id)
            .order_by(ThresholdFlag.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_all(
        self, *, status: str | None, limit: int, offset: int
    ) -> list[ThresholdFlag]:
        stmt = select(ThresholdFlag)
        if status is not None:
            stmt = stmt.where(ThresholdFlag.status == status)
        stmt = (
            stmt.order_by(ThresholdFlag.created_at.desc()).limit(limit).offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        flag_id: UUID,
        *,
        status: str,
        resolution_note: str | None,
        resolved_by: UUID,
    ) -> ThresholdFlag | None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(ThresholdFlag)
            .where(ThresholdFlag.id == flag_id)
            .values(
                status=status,
                resolution_note=resolution_note,
                resolved_by=resolved_by,
                resolved_at=now,
                updated_at=now,
            )
            .returning(ThresholdFlag)
        )
        result = await self._db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            await self._db.flush()
        return row
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest backend/tests/unit/test_threshold_flag_repo.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/threshold_flag.py backend/app/models/__init__.py \
        backend/app/repositories/threshold_flag.py \
        backend/tests/unit/test_threshold_flag_repo.py
git commit -m "feat(models): threshold_flag model + repository for FR-EXPV-08"
```

---

## Task 3: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/threshold_flag.py`
- Test: `backend/tests/unit/test_threshold_flag_schemas.py`

- [ ] **Step 1: Write failing schema tests**

```python
# backend/tests/unit/test_threshold_flag_schemas.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.threshold_flag import (
    ThresholdFlagCreate,
    ThresholdFlagResolveAction,
    ThresholdRow,
)


def test_threshold_row_requires_value_and_unit():
    row = ThresholdRow(
        section="squat",
        key="knee_valgus_caution_deg",
        value=5.0,
        unit="degrees",
        provenance_citation="Myer et al. 2010",
        last_modified_by="expert_reviewer",
    )
    assert row.section == "squat"
    assert row.value == 5.0


def test_flag_create_rejects_short_rationale():
    with pytest.raises(ValidationError):
        ThresholdFlagCreate(
            section="squat",
            key="knee_valgus_caution_deg",
            proposed_value=8.0,
            proposed_citation="Krosshaug 2016",
            rationale="too short",
        )


def test_flag_create_rejects_short_citation():
    with pytest.raises(ValidationError):
        ThresholdFlagCreate(
            section="squat",
            key="knee_valgus_caution_deg",
            proposed_value=8.0,
            proposed_citation="2016",
            rationale="An adequate-length rationale explaining the issue.",
        )


def test_flag_create_accepts_minimum_valid_payload():
    payload = ThresholdFlagCreate(
        section="bench",
        key="grip_width_biacromial_ratio_max",
        proposed_value=1.7,
        proposed_citation="Smith 2024 — wider grip safe",
        rationale="Recent evidence supports looser biacromial ratio limits.",
    )
    assert payload.proposed_value == 1.7


def test_flag_create_rejects_unknown_section():
    with pytest.raises(ValidationError):
        ThresholdFlagCreate(
            section="shoulder_press",
            key="elbow_flare_caution_deg",
            proposed_value=40.0,
            proposed_citation="Smith 2024",
            rationale="An adequate-length rationale explaining the issue.",
        )


def test_resolve_action_requires_valid_status():
    with pytest.raises(ValidationError):
        ThresholdFlagResolveAction(status="pending", resolution_note=None)

    action = ThresholdFlagResolveAction(
        status="resolved", resolution_note="Shipped in PR #999."
    )
    assert action.status == "resolved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_threshold_flag_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.threshold_flag'`.

- [ ] **Step 3: Write the schema module**

```python
# backend/app/schemas/threshold_flag.py
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Only angle/metric thresholds surface to the UI — see plan Scope Boundaries.
ALLOWED_SECTIONS: frozenset[str] = frozenset({"squat", "bench", "deadlift", "control"})

StatusLiteral = Literal["open", "resolved", "rejected"]


class ThresholdRow(BaseModel):
    """A single threshold entry as shown in the reviewer UI."""

    model_config = ConfigDict(from_attributes=True)

    section: str = Field(..., max_length=30)
    key: str = Field(..., max_length=100)
    value: float
    unit: str
    provenance_citation: str | None
    last_modified_by: str | None


class ThresholdListing(BaseModel):
    """Full listing grouped by section."""

    version: str
    sections: dict[str, list[ThresholdRow]]


class ThresholdFlagCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    section: Literal["squat", "bench", "deadlift", "control"]
    key: str = Field(..., min_length=1, max_length=100)
    proposed_value: float
    proposed_citation: str = Field(..., min_length=5, max_length=500)
    rationale: str = Field(..., min_length=20, max_length=2000)


class ThresholdFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reviewer_id: UUID
    section: str
    key: str
    current_value: float
    current_citation: str | None
    proposed_value: float
    proposed_citation: str
    rationale: str
    status: StatusLiteral
    resolution_note: str | None
    resolved_by: UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ThresholdFlagResolveAction(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: Literal["resolved", "rejected"]
    resolution_note: str | None = Field(default=None, max_length=2000)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_threshold_flag_schemas.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/threshold_flag.py backend/tests/unit/test_threshold_flag_schemas.py
git commit -m "feat(schemas): ThresholdFlag Pydantic schemas for FR-EXPV-08"
```

---

## Task 4: Service layer — listing + create_flag + resolve_flag

**Files:**
- Create: `backend/app/services/threshold_flag.py`
- Test: `backend/tests/unit/test_threshold_flag_service.py`

- [ ] **Step 1: Write failing service tests**

```python
# backend/tests/unit/test_threshold_flag_service.py
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.config import ThresholdConfig
from app.models.threshold_flag import ThresholdFlag
from app.services.threshold_flag import (
    InvalidThresholdKey,
    ThresholdFlagService,
)


pytestmark = pytest.mark.asyncio


def _make_service(repo: AsyncMock, cfg: ThresholdConfig | None = None) -> ThresholdFlagService:
    return ThresholdFlagService(repo=repo, config=cfg or ThresholdConfig())


async def test_get_listing_excludes_non_angle_sections():
    svc = _make_service(repo=AsyncMock())

    listing = svc.get_listing()

    assert listing.version == "v1"
    assert set(listing.sections.keys()) == {"squat", "bench", "deadlift", "control"}
    for rows in listing.sections.values():
        for row in rows:
            assert row.value is not None


async def test_get_listing_populates_provenance():
    svc = _make_service(repo=AsyncMock())

    listing = svc.get_listing()
    squat_rows = listing.sections["squat"]
    valgus = next(r for r in squat_rows if r.key == "knee_valgus_caution_deg")

    assert valgus.unit == "degrees"
    assert valgus.provenance_citation == "Myer et al. 2010"


async def test_create_flag_snapshots_current_value_and_citation():
    repo = AsyncMock()
    repo.create.side_effect = lambda flag: flag  # echo the persisted flag
    svc = _make_service(repo=repo)

    reviewer_id = uuid4()
    result = await svc.create_flag(
        reviewer_id=reviewer_id,
        section="squat",
        key="knee_valgus_caution_deg",
        proposed_value=8.0,
        proposed_citation="Krosshaug 2016 — 8° not replicated",
        rationale="Original Myer finding did not replicate in larger cohorts.",
    )

    assert result.current_value == 5.0
    assert result.current_citation == "Myer et al. 2010"
    assert result.proposed_value == 8.0
    assert result.reviewer_id == reviewer_id
    assert result.status == "open"
    repo.create.assert_awaited_once()


async def test_create_flag_rejects_unknown_key():
    repo = AsyncMock()
    svc = _make_service(repo=repo)

    with pytest.raises(InvalidThresholdKey):
        await svc.create_flag(
            reviewer_id=uuid4(),
            section="squat",
            key="not_a_real_threshold",
            proposed_value=1.0,
            proposed_citation="fake 2024",
            rationale="An adequate-length rationale explaining the issue.",
        )
    repo.create.assert_not_awaited()


async def test_resolve_flag_updates_status_and_resolver():
    repo = AsyncMock()
    flag_id = uuid4()
    admin_id = uuid4()
    resolved_flag = ThresholdFlag(
        id=flag_id,
        reviewer_id=uuid4(),
        section="squat",
        key="knee_valgus_caution_deg",
        current_value=5.0,
        current_citation="Myer et al. 2010",
        proposed_value=8.0,
        proposed_citation="Krosshaug 2016",
        rationale="An adequate-length rationale explaining the issue.",
        status="resolved",
    )
    repo.update_status.return_value = resolved_flag
    svc = _make_service(repo=repo)

    out = await svc.resolve_flag(
        flag_id=flag_id,
        status="resolved",
        resolution_note="Merged PR #999",
        resolver_id=admin_id,
    )

    assert out is resolved_flag
    repo.update_status.assert_awaited_once_with(
        flag_id,
        status="resolved",
        resolution_note="Merged PR #999",
        resolved_by=admin_id,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_threshold_flag_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.threshold_flag'`.

- [ ] **Step 3: Write the service**

```python
# backend/app/services/threshold_flag.py
from __future__ import annotations

from uuid import UUID, uuid4

from app.config import ThresholdConfig
from app.models.threshold_flag import ThresholdFlag
from app.repositories.threshold_flag import ThresholdFlagRepository
from app.schemas.threshold_flag import (
    ALLOWED_SECTIONS,
    ThresholdListing,
    ThresholdRow,
)


class InvalidThresholdKey(Exception):
    """Raised when (section, key) does not exist in the current ThresholdConfig."""


class ThresholdFlagService:
    """FR-EXPV-08: expose current thresholds + capture reviewer flags.

    Thresholds are read-only — the source of truth is the JSON file managed
    via PR review (FR-SCOR-11). This service never writes to that file.
    """

    def __init__(
        self,
        *,
        repo: ThresholdFlagRepository,
        config: ThresholdConfig | None = None,
    ) -> None:
        self._repo = repo
        self._config = config or ThresholdConfig()

    def get_listing(self) -> ThresholdListing:
        sections: dict[str, list[ThresholdRow]] = {}
        for section in ALLOWED_SECTIONS:
            block = self._config.get_section(section)
            rows: list[ThresholdRow] = []
            for key, raw in block.items():
                if key.startswith("_"):  # skip "_comment" entries
                    continue
                if not isinstance(raw, dict) or "value" not in raw:
                    continue
                rows.append(
                    ThresholdRow(
                        section=section,
                        key=key,
                        value=float(raw["value"]),
                        unit=str(raw.get("unit", "")),
                        provenance_citation=raw.get("provenance_citation"),
                        last_modified_by=raw.get("last_modified_by"),
                    )
                )
            rows.sort(key=lambda r: r.key)
            sections[section] = rows
        return ThresholdListing(version=self._config.version, sections=sections)

    async def create_flag(
        self,
        *,
        reviewer_id: UUID,
        section: str,
        key: str,
        proposed_value: float,
        proposed_citation: str,
        rationale: str,
    ) -> ThresholdFlag:
        # Snapshot current value + citation from the live config so the
        # flag records the threshold as-of submission (FR-EXPV-08).
        try:
            current_value = float(self._config.get(section, key))
        except KeyError as exc:
            raise InvalidThresholdKey(str(exc)) from exc
        current_citation = self._config.get_citation(section, key)

        flag = ThresholdFlag(
            id=uuid4(),
            reviewer_id=reviewer_id,
            section=section,
            key=key,
            current_value=current_value,
            current_citation=current_citation,
            proposed_value=proposed_value,
            proposed_citation=proposed_citation,
            rationale=rationale,
            status="open",
        )
        return await self._repo.create(flag)

    async def resolve_flag(
        self,
        *,
        flag_id: UUID,
        status: str,
        resolution_note: str | None,
        resolver_id: UUID,
    ) -> ThresholdFlag | None:
        return await self._repo.update_status(
            flag_id,
            status=status,
            resolution_note=resolution_note,
            resolved_by=resolver_id,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_threshold_flag_service.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/threshold_flag.py backend/tests/unit/test_threshold_flag_service.py
git commit -m "feat(services): ThresholdFlagService + listing + create_flag + resolve_flag"
```

---

## Task 5: Expert-side FastAPI endpoints

**Files:**
- Modify: `backend/app/api/v1/expert.py` — append 3 endpoints below the existing golden-dataset section
- Test: `backend/tests/unit/test_expert_thresholds_api.py`

- [ ] **Step 1: Write failing API tests**

```python
# backend/tests/unit/test_expert_thresholds_api.py
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_expert_reviewer_user
from app.main import app
from app.models.threshold_flag import ThresholdFlag
from app.services.threshold_flag import InvalidThresholdKey, ThresholdFlagService


@pytest.fixture
def reviewer_user():
    return {"id": uuid4(), "role": "expert_reviewer"}


@pytest.fixture
def client(reviewer_user):
    app.dependency_overrides[get_expert_reviewer_user] = lambda: reviewer_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_thresholds_returns_angle_sections_only(client):
    # Relies on real ThresholdConfig loader — no service override needed
    # because get_listing() is pure.
    resp = client.get("/api/v1/expert/thresholds")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "v1"
    assert set(body["sections"].keys()) == {"squat", "bench", "deadlift", "control"}
    squat_keys = {r["key"] for r in body["sections"]["squat"]}
    assert "knee_valgus_caution_deg" in squat_keys


def test_post_flag_creates_row(client, monkeypatch, reviewer_user):
    fake_service = AsyncMock(spec=ThresholdFlagService)
    fake_service.get_listing.return_value = None
    created = ThresholdFlag(
        id=uuid4(),
        reviewer_id=reviewer_user["id"],
        section="squat",
        key="knee_valgus_caution_deg",
        current_value=5.0,
        current_citation="Myer et al. 2010",
        proposed_value=8.0,
        proposed_citation="Krosshaug 2016 — 8° not replicated",
        rationale="Original Myer finding did not replicate in larger cohorts.",
        status="open",
    )
    fake_service.create_flag.return_value = created

    from app.api.v1 import expert as expert_module

    monkeypatch.setattr(
        expert_module, "_get_threshold_service", lambda db=None: fake_service
    )

    resp = client.post(
        "/api/v1/expert/thresholds/flags",
        json={
            "section": "squat",
            "key": "knee_valgus_caution_deg",
            "proposed_value": 8.0,
            "proposed_citation": "Krosshaug 2016 — 8° not replicated",
            "rationale": "Original Myer finding did not replicate in larger cohorts.",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["section"] == "squat"
    assert body["proposed_value"] == 8.0
    assert body["current_value"] == 5.0
    fake_service.create_flag.assert_awaited_once()


def test_post_flag_returns_422_for_unknown_key(client, monkeypatch):
    fake_service = AsyncMock(spec=ThresholdFlagService)
    fake_service.create_flag.side_effect = InvalidThresholdKey(
        "Unknown threshold key 'nope' for section 'squat'"
    )

    from app.api.v1 import expert as expert_module

    monkeypatch.setattr(
        expert_module, "_get_threshold_service", lambda db=None: fake_service
    )

    resp = client.post(
        "/api/v1/expert/thresholds/flags",
        json={
            "section": "squat",
            "key": "knee_valgus_caution_deg",
            "proposed_value": 8.0,
            "proposed_citation": "Krosshaug 2016",
            "rationale": "An adequate-length rationale explaining the issue.",
        },
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]["error"]["code"] == "UNKNOWN_THRESHOLD_KEY"


def test_get_my_flags_returns_reviewer_flags(client, monkeypatch, reviewer_user):
    flag = ThresholdFlag(
        id=uuid4(),
        reviewer_id=reviewer_user["id"],
        section="bench",
        key="elbow_flare_caution_deg",
        current_value=45.0,
        current_citation="Green & Comfort 2007",
        proposed_value=55.0,
        proposed_citation="Nuckols 2024",
        rationale="A more permissive flare may be biomechanically acceptable.",
        status="open",
    )
    fake_service = AsyncMock(spec=ThresholdFlagService)
    fake_service._repo = AsyncMock()  # not used
    fake_repo = AsyncMock()
    fake_repo.list_by_reviewer.return_value = [flag]

    from app.api.v1 import expert as expert_module

    monkeypatch.setattr(
        expert_module, "_get_threshold_flag_repo", lambda db=None: fake_repo
    )

    resp = client.get("/api/v1/expert/thresholds/flags?limit=10&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["key"] == "elbow_flare_caution_deg"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/unit/test_expert_thresholds_api.py -v`
Expected: FAIL with 404s because the routes don't exist yet.

- [ ] **Step 3: Wire the endpoints into `expert.py`**

Add to `backend/app/api/v1/expert.py`:

```python
# Near the existing imports
from app.repositories.threshold_flag import ThresholdFlagRepository
from app.schemas.threshold_flag import (
    ThresholdFlagCreate,
    ThresholdFlagResponse,
    ThresholdListing,
)
from app.services.threshold_flag import (
    InvalidThresholdKey,
    ThresholdFlagService,
)

# Next to the other Depends helpers at the top of the file
async def _get_threshold_flag_repo(
    db: AsyncSession = Depends(get_db),
) -> ThresholdFlagRepository:
    return ThresholdFlagRepository(db)


async def _get_threshold_service(
    db: AsyncSession = Depends(get_db),
) -> ThresholdFlagService:
    return ThresholdFlagService(repo=ThresholdFlagRepository(db))


# Appended at the bottom of the file, below label_golden_dataset:

# ---------------------------------------------------------------------------
# Threshold Validation (FR-EXPV-08)
# ---------------------------------------------------------------------------


@router.get("/thresholds", response_model=ThresholdListing)
async def get_thresholds(
    user: CurrentUser = Depends(get_expert_reviewer_user),
    service: ThresholdFlagService = Depends(_get_threshold_service),
) -> ThresholdListing:
    """Return current angle thresholds grouped by exercise section.

    Source: ``config/thresholds_v1.json``. This endpoint is read-only —
    edits to values happen via PR review (FR-SCOR-11).
    """
    return service.get_listing()


@router.post(
    "/thresholds/flags",
    response_model=ThresholdFlagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_threshold_flag(
    body: ThresholdFlagCreate,
    user: CurrentUser = Depends(get_expert_reviewer_user),
    service: ThresholdFlagService = Depends(_get_threshold_service),
) -> Any:
    try:
        flag = await service.create_flag(
            reviewer_id=user["id"],
            section=body.section,
            key=body.key,
            proposed_value=body.proposed_value,
            proposed_citation=body.proposed_citation,
            rationale=body.rationale,
        )
    except InvalidThresholdKey as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "UNKNOWN_THRESHOLD_KEY",
                    "message": str(err),
                    "detail": None,
                }
            },
        ) from err
    return ThresholdFlagResponse.model_validate(flag, from_attributes=True)


@router.get("/thresholds/flags", response_model=list[ThresholdFlagResponse])
async def list_my_threshold_flags(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_expert_reviewer_user),
    repo: ThresholdFlagRepository = Depends(_get_threshold_flag_repo),
) -> list[Any]:
    rows = await repo.list_by_reviewer(user["id"], limit=limit, offset=offset)
    return [ThresholdFlagResponse.model_validate(r, from_attributes=True) for r in rows]
```

- [ ] **Step 4: Run API tests to verify they pass**

Run: `uv run pytest backend/tests/unit/test_expert_thresholds_api.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/expert.py backend/tests/unit/test_expert_thresholds_api.py
git commit -m "feat(api): expert threshold listing + flag submission endpoints"
```

---

## Task 6: Admin-side FastAPI endpoints

**Files:**
- Modify: `backend/app/api/v1/admin.py` — add two endpoints
- Test: `backend/tests/unit/test_admin_threshold_flags_api.py`

- [ ] **Step 1: Write failing admin API tests**

```python
# backend/tests/unit/test_admin_threshold_flags_api.py
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_admin_user
from app.main import app
from app.models.threshold_flag import ThresholdFlag


@pytest.fixture
def admin_user():
    return {"id": uuid4(), "role": "admin"}


@pytest.fixture
def client(admin_user):
    app.dependency_overrides[get_admin_user] = lambda: admin_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_admin_list_threshold_flags_returns_rows(client, monkeypatch):
    flag = ThresholdFlag(
        id=uuid4(),
        reviewer_id=uuid4(),
        section="squat",
        key="knee_valgus_caution_deg",
        current_value=5.0,
        current_citation="Myer et al. 2010",
        proposed_value=8.0,
        proposed_citation="Krosshaug 2016",
        rationale="An adequate-length rationale explaining the issue.",
        status="open",
    )
    fake_repo = AsyncMock()
    fake_repo.list_all.return_value = [flag]
    from app.api.v1 import admin as admin_module

    monkeypatch.setattr(
        admin_module, "_get_threshold_flag_repo", lambda db=None: fake_repo
    )

    resp = client.get("/api/v1/admin/threshold-flags?status=open")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "open"
    fake_repo.list_all.assert_awaited_once_with(status="open", limit=50, offset=0)


def test_admin_resolve_threshold_flag_returns_updated(client, monkeypatch, admin_user):
    flag_id = uuid4()
    resolved = ThresholdFlag(
        id=flag_id,
        reviewer_id=uuid4(),
        section="squat",
        key="knee_valgus_caution_deg",
        current_value=5.0,
        current_citation="Myer et al. 2010",
        proposed_value=8.0,
        proposed_citation="Krosshaug 2016",
        rationale="An adequate-length rationale explaining the issue.",
        status="resolved",
        resolution_note="Merged PR #999",
        resolved_by=admin_user["id"],
    )
    fake_repo = AsyncMock()
    fake_repo.update_status.return_value = resolved
    from app.api.v1 import admin as admin_module

    monkeypatch.setattr(
        admin_module, "_get_threshold_flag_repo", lambda db=None: fake_repo
    )

    resp = client.patch(
        f"/api/v1/admin/threshold-flags/{flag_id}",
        json={"status": "resolved", "resolution_note": "Merged PR #999"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolution_note"] == "Merged PR #999"


def test_admin_resolve_returns_404_when_row_missing(client, monkeypatch):
    fake_repo = AsyncMock()
    fake_repo.update_status.return_value = None
    from app.api.v1 import admin as admin_module

    monkeypatch.setattr(
        admin_module, "_get_threshold_flag_repo", lambda db=None: fake_repo
    )

    resp = client.patch(
        f"/api/v1/admin/threshold-flags/{uuid4()}",
        json={"status": "rejected", "resolution_note": None},
    )

    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/unit/test_admin_threshold_flags_api.py -v`
Expected: FAIL with 404 route-not-found.

- [ ] **Step 3: Add admin endpoints**

Append to `backend/app/api/v1/admin.py`:

```python
# Near the top with other imports
from uuid import UUID

from app.repositories.threshold_flag import ThresholdFlagRepository
from app.schemas.threshold_flag import (
    ThresholdFlagResolveAction,
    ThresholdFlagResponse,
)


async def _get_threshold_flag_repo(
    db: AsyncSession = Depends(get_db),
) -> ThresholdFlagRepository:
    return ThresholdFlagRepository(db)


# Appended at the bottom of the admin router section:

# ---------------------------------------------------------------------------
# Threshold flags review (FR-EXPV-08)
# ---------------------------------------------------------------------------


@router.get(
    "/threshold-flags",
    response_model=list[ThresholdFlagResponse],
)
async def list_threshold_flags(
    status_filter: str | None = Query(None, alias="status", pattern="^(open|resolved|rejected)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_admin_user),
    repo: ThresholdFlagRepository = Depends(_get_threshold_flag_repo),
) -> list[Any]:
    rows = await repo.list_all(status=status_filter, limit=limit, offset=offset)
    return [ThresholdFlagResponse.model_validate(r, from_attributes=True) for r in rows]


@router.patch(
    "/threshold-flags/{flag_id}",
    response_model=ThresholdFlagResponse,
)
async def resolve_threshold_flag(
    flag_id: UUID,
    body: ThresholdFlagResolveAction,
    user: CurrentUser = Depends(get_admin_user),
    repo: ThresholdFlagRepository = Depends(_get_threshold_flag_repo),
) -> Any:
    updated = await repo.update_status(
        flag_id,
        status=body.status,
        resolution_note=body.resolution_note,
        resolved_by=user["id"],
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Threshold flag not found.", "detail": None}},
        )
    return ThresholdFlagResponse.model_validate(updated, from_attributes=True)
```

- [ ] **Step 4: Run admin API tests to verify they pass**

Run: `uv run pytest backend/tests/unit/test_admin_threshold_flags_api.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Regenerate frontend OpenAPI types**

Run (from `frontend/`): `npm run gen-types`

Expected: `src/api/types.ts` updated with new paths `/api/v1/expert/thresholds`, `/api/v1/expert/thresholds/flags`, `/api/v1/admin/threshold-flags`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/admin.py backend/tests/unit/test_admin_threshold_flags_api.py \
        frontend/src/api/types.ts
git commit -m "feat(api): admin threshold-flag list + resolve endpoints"
```

---

## Task 7: Frontend API client

**Files:**
- Modify: `frontend/src/api/expert.ts`
- Test: `frontend/src/api/__tests__/expert-thresholds.test.ts`

- [ ] **Step 1: Write failing API client tests**

```typescript
// frontend/src/api/__tests__/expert-thresholds.test.ts
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createThresholdFlag,
  getThresholdListing,
  listMyThresholdFlags,
} from "@/api/expert";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "tok" } },
      }),
    },
  },
}));

const makeFetchOk = (payload: unknown) =>
  vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve(payload),
  });

describe("threshold endpoints", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", makeFetchOk(null));
  });

  it("getThresholdListing fetches /expert/thresholds", async () => {
    const payload = {
      version: "v1",
      sections: { squat: [], bench: [], deadlift: [], control: [] },
    };
    vi.stubGlobal("fetch", makeFetchOk(payload));

    const listing = await getThresholdListing();

    expect(listing.version).toBe("v1");
    expect(Object.keys(listing.sections).sort()).toEqual([
      "bench",
      "control",
      "deadlift",
      "squat",
    ]);
  });

  it("createThresholdFlag posts the flag body", async () => {
    const flag = {
      id: "0000-0000-0000-0000",
      reviewer_id: "0000-0000-0000-0001",
      section: "squat",
      key: "knee_valgus_caution_deg",
      current_value: 5,
      current_citation: "Myer et al. 2010",
      proposed_value: 8,
      proposed_citation: "Krosshaug 2016",
      rationale: "An adequate-length rationale explaining the issue.",
      status: "open",
      resolution_note: null,
      resolved_by: null,
      resolved_at: null,
      created_at: "2026-04-21T00:00:00Z",
      updated_at: "2026-04-21T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: () => Promise.resolve(flag),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createThresholdFlag({
      section: "squat",
      key: "knee_valgus_caution_deg",
      proposed_value: 8,
      proposed_citation: "Krosshaug 2016",
      rationale: "An adequate-length rationale explaining the issue.",
    });

    expect(result.id).toBe(flag.id);
    const call = fetchMock.mock.calls[0]!;
    expect(call[0]).toContain("/api/v1/expert/thresholds/flags");
    expect((call[1] as RequestInit).method).toBe("POST");
  });

  it("listMyThresholdFlags passes limit/offset query", async () => {
    const fetchMock = makeFetchOk([]);
    vi.stubGlobal("fetch", fetchMock);

    await listMyThresholdFlags(25, 50);

    const url = fetchMock.mock.calls[0]![0] as string;
    expect(url).toContain("limit=25");
    expect(url).toContain("offset=50");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/api/__tests__/expert-thresholds.test.ts`
Expected: FAIL with import error for `createThresholdFlag`, `getThresholdListing`, `listMyThresholdFlags`.

- [ ] **Step 3: Add API client functions + types**

Append to `frontend/src/api/expert.ts` (add after the existing `labelGoldenDataset` export):

```typescript
// ---------------------------------------------------------------------------
// Threshold Validation (FR-EXPV-08)
// ---------------------------------------------------------------------------

export interface ThresholdRow {
  section: "squat" | "bench" | "deadlift" | "control";
  key: string;
  value: number;
  unit: string;
  provenance_citation: string | null;
  last_modified_by: string | null;
}

export interface ThresholdListing {
  version: string;
  sections: Record<ThresholdRow["section"], ThresholdRow[]>;
}

export interface ThresholdFlagCreate {
  section: ThresholdRow["section"];
  key: string;
  proposed_value: number;
  proposed_citation: string;
  rationale: string;
}

export interface ThresholdFlagResponse {
  id: string;
  reviewer_id: string;
  section: ThresholdRow["section"];
  key: string;
  current_value: number;
  current_citation: string | null;
  proposed_value: number;
  proposed_citation: string;
  rationale: string;
  status: "open" | "resolved" | "rejected";
  resolution_note: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export async function getThresholdListing(): Promise<ThresholdListing> {
  return expertFetch<ThresholdListing>("/api/v1/expert/thresholds");
}

export async function createThresholdFlag(
  payload: ThresholdFlagCreate,
): Promise<ThresholdFlagResponse> {
  return expertFetch<ThresholdFlagResponse>("/api/v1/expert/thresholds/flags", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listMyThresholdFlags(
  limit = 20,
  offset = 0,
): Promise<ThresholdFlagResponse[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return expertFetch<ThresholdFlagResponse[]>(
    `/api/v1/expert/thresholds/flags?${params}`,
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npx vitest run src/api/__tests__/expert-thresholds.test.ts`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/expert.ts frontend/src/api/__tests__/expert-thresholds.test.ts
git commit -m "feat(frontend): expert threshold API client + types"
```

---

## Task 8: Flag submission modal component

**Files:**
- Create: `frontend/src/components/ThresholdFlagModal.tsx`
- Test: `frontend/src/components/__tests__/ThresholdFlagModal.test.tsx`

- [ ] **Step 1: Write failing component test**

```typescript
// frontend/src/components/__tests__/ThresholdFlagModal.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ThresholdFlagModal from "@/components/ThresholdFlagModal";

const baseRow = {
  section: "squat" as const,
  key: "knee_valgus_caution_deg",
  value: 5,
  unit: "degrees",
  provenance_citation: "Myer et al. 2010",
  last_modified_by: "expert_reviewer",
};

describe("ThresholdFlagModal", () => {
  it("is hidden when row is null", () => {
    render(
      <ThresholdFlagModal row={null} onClose={() => {}} onSubmit={async () => {}} />,
    );
    expect(screen.queryByText(/Flag threshold/i)).toBeNull();
  });

  it("disables submit until rationale is 20+ chars and citation is 5+", () => {
    render(
      <ThresholdFlagModal row={baseRow} onClose={() => {}} onSubmit={async () => {}} />,
    );
    const submit = screen.getByRole("button", { name: /submit flag/i });
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/proposed value/i), {
      target: { value: "8" },
    });
    fireEvent.change(screen.getByLabelText(/proposed citation/i), {
      target: { value: "Krosshaug 2016" },
    });
    fireEvent.change(screen.getByLabelText(/rationale/i), {
      target: { value: "An adequate-length rationale explaining why." },
    });
    expect(submit).not.toBeDisabled();
  });

  it("calls onSubmit with the form payload", async () => {
    const handleSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ThresholdFlagModal
        row={baseRow}
        onClose={() => {}}
        onSubmit={handleSubmit}
      />,
    );

    fireEvent.change(screen.getByLabelText(/proposed value/i), {
      target: { value: "8" },
    });
    fireEvent.change(screen.getByLabelText(/proposed citation/i), {
      target: { value: "Krosshaug 2016" },
    });
    fireEvent.change(screen.getByLabelText(/rationale/i), {
      target: {
        value: "An adequate-length rationale explaining why.",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: /submit flag/i }));

    await vi.waitFor(() => {
      expect(handleSubmit).toHaveBeenCalledTimes(1);
    });
    expect(handleSubmit.mock.calls[0][0]).toMatchObject({
      section: "squat",
      key: "knee_valgus_caution_deg",
      proposed_value: 8,
      proposed_citation: "Krosshaug 2016",
      rationale: "An adequate-length rationale explaining why.",
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/components/__tests__/ThresholdFlagModal.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the component**

```tsx
// frontend/src/components/ThresholdFlagModal.tsx
import { useEffect, useState } from "react";

import type {
  ThresholdFlagCreate,
  ThresholdRow,
} from "@/api/expert";

interface Props {
  row: ThresholdRow | null;
  onClose: () => void;
  onSubmit: (payload: ThresholdFlagCreate) => Promise<void>;
}

const MIN_RATIONALE = 20;
const MIN_CITATION = 5;

export default function ThresholdFlagModal({ row, onClose, onSubmit }: Props) {
  const [proposedValue, setProposedValue] = useState<string>("");
  const [proposedCitation, setProposedCitation] = useState<string>("");
  const [rationale, setRationale] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setProposedValue("");
    setProposedCitation("");
    setRationale("");
    setError(null);
    setSubmitting(false);
  }, [row?.key]);

  if (!row) return null;

  const parsedValue = Number(proposedValue);
  const canSubmit =
    !Number.isNaN(parsedValue) &&
    proposedValue.trim().length > 0 &&
    proposedCitation.trim().length >= MIN_CITATION &&
    rationale.trim().length >= MIN_RATIONALE &&
    !submitting;

  async function handleSubmit() {
    if (!row) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        section: row.section,
        key: row.key,
        proposed_value: parsedValue,
        proposed_citation: proposedCitation.trim(),
        rationale: rationale.trim(),
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit flag");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Flag threshold
        </h2>

        <dl className="mb-4 text-sm text-gray-700">
          <div className="flex justify-between">
            <dt className="font-medium">Section</dt>
            <dd className="capitalize">{row.section}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Key</dt>
            <dd className="font-mono text-xs">{row.key}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Current value</dt>
            <dd>
              {row.value} {row.unit}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Current citation</dt>
            <dd className="text-right text-xs text-gray-500">
              {row.provenance_citation ?? "—"}
            </dd>
          </div>
        </dl>

        <label className="mb-3 block text-sm">
          <span className="mb-1 block font-medium text-gray-700">
            Proposed value ({row.unit})
          </span>
          <input
            type="number"
            step="any"
            value={proposedValue}
            onChange={(e) => setProposedValue(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>

        <label className="mb-3 block text-sm">
          <span className="mb-1 block font-medium text-gray-700">
            Proposed citation (≥ {MIN_CITATION} chars)
          </span>
          <input
            type="text"
            value={proposedCitation}
            onChange={(e) => setProposedCitation(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2"
            placeholder="Author year — finding"
          />
        </label>

        <label className="mb-3 block text-sm">
          <span className="mb-1 block font-medium text-gray-700">
            Rationale (≥ {MIN_RATIONALE} chars)
          </span>
          <textarea
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            rows={4}
            className="w-full rounded border border-gray-300 px-3 py-2"
            placeholder="Explain why the current value conflicts with literature."
          />
        </label>

        {error && (
          <p className="mb-3 text-sm text-red-600" role="alert">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!canSubmit}
            onClick={handleSubmit}
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            {submitting ? "Submitting…" : "Submit flag"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npx vitest run src/components/__tests__/ThresholdFlagModal.test.tsx`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ThresholdFlagModal.tsx \
        frontend/src/components/__tests__/ThresholdFlagModal.test.tsx
git commit -m "feat(frontend): ThresholdFlagModal form component"
```

---

## Task 9: Expert thresholds page

**Files:**
- Create: `frontend/src/pages/ExpertThresholdsPage.tsx`
- Test: `frontend/src/pages/__tests__/ExpertThresholdsPage.test.tsx`
- Modify: `frontend/src/routes.tsx` — register route `/expert/thresholds`
- Modify: `frontend/src/pages/ExpertPortalPage.tsx` — add link

- [ ] **Step 1: Write failing page test**

```tsx
// frontend/src/pages/__tests__/ExpertThresholdsPage.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ExpertThresholdsPage from "@/pages/ExpertThresholdsPage";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: {
          session: {
            access_token: "tok",
            user: { app_metadata: { role: "expert_reviewer" } },
          },
        },
      }),
    },
  },
}));

vi.mock("@/api/expert", async () => {
  const actual = await vi.importActual<typeof import("@/api/expert")>(
    "@/api/expert",
  );
  return {
    ...actual,
    getThresholdListing: vi.fn().mockResolvedValue({
      version: "v1",
      sections: {
        squat: [
          {
            section: "squat",
            key: "knee_valgus_caution_deg",
            value: 5,
            unit: "degrees",
            provenance_citation: "Myer et al. 2010",
            last_modified_by: "expert_reviewer",
          },
        ],
        bench: [],
        deadlift: [],
        control: [],
      },
    }),
    listMyThresholdFlags: vi.fn().mockResolvedValue([]),
    createThresholdFlag: vi.fn(),
  };
});

describe("ExpertThresholdsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders sections and threshold rows", async () => {
    render(
      <MemoryRouter>
        <ExpertThresholdsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("knee_valgus_caution_deg")).toBeTruthy();
    });
    expect(screen.getByText(/Myer et al. 2010/)).toBeTruthy();
    expect(screen.getByText(/Config version: v1/i)).toBeTruthy();
  });

  it("shows the My Flags tab with empty state", async () => {
    render(
      <MemoryRouter>
        <ExpertThresholdsPage />
      </MemoryRouter>,
    );
    const myFlagsBtn = await screen.findByRole("button", { name: /my flags/i });
    myFlagsBtn.click();

    await waitFor(() => {
      expect(screen.getByText(/No flags submitted yet/i)).toBeTruthy();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/pages/__tests__/ExpertThresholdsPage.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the page**

```tsx
// frontend/src/pages/ExpertThresholdsPage.tsx
/**
 * ExpertThresholdsPage — FR-EXPV-08 threshold validation portal.
 *
 * Read-only view of angle thresholds from config/thresholds_v1.json.
 * Reviewers flag thresholds that conflict with literature; admins
 * resolve flags via PR (FR-SCOR-11). Values are never edited here.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router";

import ThresholdFlagModal from "@/components/ThresholdFlagModal";
import {
  createThresholdFlag,
  getThresholdListing,
  listMyThresholdFlags,
  type ThresholdFlagCreate,
  type ThresholdFlagResponse,
  type ThresholdListing,
  type ThresholdRow,
} from "@/api/expert";
import { supabase } from "@/lib/supabase";

type Tab = "thresholds" | "my_flags";

const SECTION_LABELS: Record<ThresholdRow["section"], string> = {
  squat: "Squat",
  bench: "Bench",
  deadlift: "Deadlift",
  control: "Control",
};

export default function ExpertThresholdsPage() {
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [tab, setTab] = useState<Tab>("thresholds");
  const [listing, setListing] = useState<ThresholdListing | null>(null);
  const [flags, setFlags] = useState<ThresholdFlagResponse[]>([]);
  const [modalRow, setModalRow] = useState<ThresholdRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const session = data.session;
      if (!session) {
        setAuthorized(false);
        return;
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const payload = session.user as any;
      const role =
        payload?.app_metadata?.role ?? payload?.user_metadata?.role ?? null;
      setAuthorized(role === "expert_reviewer" || role === "admin");
    });
  }, []);

  const loadListing = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getThresholdListing();
      setListing(data);
    } catch {
      setError("Failed to load thresholds.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadFlags = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listMyThresholdFlags(50, 0);
      setFlags(data);
    } catch {
      setError("Failed to load flags.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authorized !== true) return;
    if (tab === "thresholds") {
      if (!listing) void loadListing();
    } else {
      void loadFlags();
    }
  }, [authorized, tab, listing, loadListing, loadFlags]);

  async function handleFlagSubmit(payload: ThresholdFlagCreate) {
    await createThresholdFlag(payload);
    setModalRow(null);
    // Refresh the My Flags list so a subsequent tab switch shows the new row.
    void loadFlags();
  }

  const sections = useMemo(() => {
    if (!listing) return [];
    return (Object.keys(SECTION_LABELS) as ThresholdRow["section"][]).map(
      (section) => ({
        section,
        label: SECTION_LABELS[section],
        rows: listing.sections[section] ?? [],
      }),
    );
  }, [listing]);

  if (authorized === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-500">Checking permissions…</p>
      </div>
    );
  }

  if (!authorized) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen bg-gray-50 py-10">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900">Threshold Validation</h1>
          <Link
            to="/expert"
            className="text-sm text-indigo-600 underline"
          >
            Back to portal
          </Link>
        </div>
        <p className="mb-6 text-sm text-gray-600">
          Thresholds are defined in <code>config/thresholds_v1.json</code> and
          changed via PR review (FR-SCOR-11). Flag any value that conflicts
          with current literature; an admin will review and, if appropriate,
          open a PR updating the config.
        </p>

        <div className="mb-6 flex gap-4 border-b border-gray-200">
          <button
            type="button"
            onClick={() => setTab("thresholds")}
            className={`-mb-px border-b-2 pb-2 text-sm font-medium ${
              tab === "thresholds"
                ? "border-indigo-500 text-indigo-600"
                : "border-transparent text-gray-500"
            }`}
          >
            Current thresholds
          </button>
          <button
            type="button"
            onClick={() => setTab("my_flags")}
            className={`-mb-px border-b-2 pb-2 text-sm font-medium ${
              tab === "my_flags"
                ? "border-indigo-500 text-indigo-600"
                : "border-transparent text-gray-500"
            }`}
          >
            My flags
          </button>
        </div>

        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        {tab === "thresholds" && listing && (
          <>
            <p className="mb-4 text-xs text-gray-500">
              Config version: {listing.version}
            </p>
            {sections.map(({ section, label, rows }) => (
              <section key={section} className="mb-8 rounded-lg bg-white p-4 shadow-sm">
                <h2 className="mb-3 text-lg font-semibold text-gray-900">
                  {label}
                </h2>
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                      <th className="pb-2 pr-4">Key</th>
                      <th className="pb-2 pr-4">Value</th>
                      <th className="pb-2 pr-4">Unit</th>
                      <th className="pb-2 pr-4">Citation</th>
                      <th className="pb-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr
                        key={row.key}
                        className="border-b border-gray-100 last:border-0"
                      >
                        <td className="py-2 pr-4 font-mono text-xs text-gray-700">
                          {row.key}
                        </td>
                        <td className="py-2 pr-4 text-gray-900">{row.value}</td>
                        <td className="py-2 pr-4 text-gray-500">{row.unit}</td>
                        <td className="py-2 pr-4 text-xs text-gray-600">
                          {row.provenance_citation ?? "—"}
                        </td>
                        <td className="py-2">
                          <button
                            type="button"
                            onClick={() => setModalRow(row)}
                            className="rounded bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                          >
                            Flag
                          </button>
                        </td>
                      </tr>
                    ))}
                    {rows.length === 0 && (
                      <tr>
                        <td colSpan={5} className="py-4 text-center text-xs text-gray-400">
                          No thresholds in this section.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </section>
            ))}
          </>
        )}

        {tab === "my_flags" && (
          <section className="rounded-lg bg-white p-4 shadow-sm">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                  <th className="pb-2 pr-4">Section</th>
                  <th className="pb-2 pr-4">Key</th>
                  <th className="pb-2 pr-4">Current</th>
                  <th className="pb-2 pr-4">Proposed</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2">Submitted</th>
                </tr>
              </thead>
              <tbody>
                {flags.map((f) => (
                  <tr key={f.id} className="border-b border-gray-100 last:border-0">
                    <td className="py-2 pr-4 capitalize">{f.section}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{f.key}</td>
                    <td className="py-2 pr-4">{f.current_value}</td>
                    <td className="py-2 pr-4">{f.proposed_value}</td>
                    <td className="py-2 pr-4 capitalize">{f.status}</td>
                    <td className="py-2 text-xs text-gray-500">
                      {new Date(f.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
                {flags.length === 0 && !loading && (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-sm text-gray-400">
                      No flags submitted yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>
        )}

        <ThresholdFlagModal
          row={modalRow}
          onClose={() => setModalRow(null)}
          onSubmit={handleFlagSubmit}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Register the route**

Open `frontend/src/routes.tsx`. Find the existing `/expert` route entries (there should be `/expert` and `/expert/papers/upload`). Add a sibling route following the same pattern:

```tsx
// At the top, near the other pages:
import ExpertThresholdsPage from "@/pages/ExpertThresholdsPage";

// In the routes array, next to the existing /expert/* routes:
{ path: "/expert/thresholds", element: <ExpertThresholdsPage /> },
```

If the existing pattern differs (e.g. nested routes), follow the existing structure — do not restructure.

- [ ] **Step 5: Link from the Expert portal header**

In `frontend/src/pages/ExpertPortalPage.tsx`, find the existing `<Link to="/expert/papers/upload" …>Upload Paper</Link>` button and add a sibling link before it:

```tsx
<div className="flex gap-2">
  <Link
    to="/expert/thresholds"
    className="rounded-md border border-indigo-200 bg-white px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50"
  >
    Validate Thresholds
  </Link>
  <Link
    to="/expert/papers/upload"
    className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
  >
    Upload Paper
  </Link>
</div>
```

Replace the existing single-Link block with the grouped flex container.

- [ ] **Step 6: Run tests to verify they pass**

Run (from `frontend/`):
```bash
npx vitest run src/pages/__tests__/ExpertThresholdsPage.test.tsx
npx tsc --noEmit
```

Expected: both tests PASS, tsc reports 0 errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ExpertThresholdsPage.tsx \
        frontend/src/pages/__tests__/ExpertThresholdsPage.test.tsx \
        frontend/src/routes.tsx \
        frontend/src/pages/ExpertPortalPage.tsx
git commit -m "feat(frontend): ExpertThresholdsPage + portal entry point"
```

---

## Task 10: ADR + backlog update

**Files:**
- Modify: `decisions.md` — append new ADR
- Modify: `backlog.md` — close FR-EXPV-08 row

- [ ] **Step 1: Append ADR-EXPV-08 to `decisions.md`**

Append (do not modify existing ADRs per CLAUDE.md append-only rule):

```markdown
## ADR-EXPV-08 — Threshold validation UI uses a flag-only DB table; PR review remains the approval path

**Date:** 2026-04-21
**Context:** FR-EXPV-08 requires the Expert Reviewer to flag angle thresholds that conflict with literature. FR-SCOR-11 already mandates that threshold changes ship via PR review of `config/thresholds_v1.json`. We need an in-portal workflow without breaking that approval model.

**Decision:** Add a `threshold_flags` table (migration 022) storing reviewer flags with `{section, key, current_value (snapshot), proposed_value, proposed_citation, rationale, status}`. Surface them in `ThresholdValidationPage` under `/expert/thresholds`. The UI never writes to `config/thresholds_v1.json`; an admin reviews flags via `/admin/threshold-flags` and, if accepted, opens a PR mutating the JSON. Flag rows are audit-only proposals.

**Alternatives considered:**
- Auto-opening a GitHub issue per flag: rejected — requires GitHub API credentials in prod, couples the product DB to external issue state, and duplicates the audit trail.
- Append-only JSON file of flags in the repo: rejected — harder to query, no per-user RLS, no resolution workflow.

**Consequences:** New table + 5 endpoints + 1 page. RLS enforces that reviewers see only their own flags, admins see all. `current_value` is snapshotted at submission so a later PR updating the config doesn't retroactively rewrite the flag context.
```

- [ ] **Step 2: Add FR-EXPV-08 close entry to `backlog.md`**

Append a new `## Completed — ...` section following the existing format at the top of the file (or under an appropriate L2 sprint day header). Example structure — exact SHA populated during the merge:

```markdown
## Completed — L2 Sprint — FR-EXPV-08 Threshold Validation UI (2026-04-21)

PR #XXX merged to `main` as `<SHA>`. Closes FR-EXPV-08 (Should, Phase 3).

| ID | Title | Status | Size | SRS | Commit | Files |
|----|-------|--------|------|-----|--------|-------|
| FR-EXPV-08 | Expert threshold validation UI with flag submission workflow | done | M | FR-EXPV-08 | `<SHA>` | backend/alembic/versions/022_add_threshold_flags.py, backend/app/models/threshold_flag.py, backend/app/repositories/threshold_flag.py, backend/app/schemas/threshold_flag.py, backend/app/services/threshold_flag.py, backend/app/api/v1/expert.py, backend/app/api/v1/admin.py, frontend/src/pages/ExpertThresholdsPage.tsx, frontend/src/components/ThresholdFlagModal.tsx, frontend/src/api/expert.ts |
```

- [ ] **Step 3: Commit the docs**

```bash
git add decisions.md backlog.md
git commit -m "docs: ADR-EXPV-08 + backlog close for threshold validation UI"
```

---

## Task 11: Full suite + PR + deploy + E2E

- [ ] **Step 1: Backend full suite**

Run (from `backend/`):
```bash
uv run ruff check .
uv run pyright app
uv run pytest tests/ -x
```

Expected: ruff clean, pyright 0 errors in `app/`, all tests pass (previous count + 17 new tests).

- [ ] **Step 2: Frontend full suite**

Run (from `frontend/`):
```bash
npx tsc --noEmit
npx vitest run
```

Expected: tsc 0 errors, all tests pass (previous count + 9 new tests across 3 files).

- [ ] **Step 3: Apply the migration locally**

Run (from `backend/`):
```bash
uv run alembic upgrade head
uv run alembic current
```

Expected: `022_threshold_flags (head)`.

- [ ] **Step 4: Specialist audits**

Invoke the `spelix-auditor` agent against the branch; resolve any CRITICAL/HIGH findings before proceeding. Invoke `spelix-security-reviewer` because the change touches a new user-facing auth-gated flow — confirm no SaMD language regressions, RLS correctness, no secret exposure.

- [ ] **Step 5: Push branch + open PR**

```bash
git push -u origin fr-expv-08-threshold-validation
```

Open PR via `mcp__github__create_pull_request` with title `feat: FR-EXPV-08 threshold validation UI` and a body summarizing the endpoints, the migration, the frontend route, and the ADR. Wait for CI to go fully green.

- [ ] **Step 6: Merge and deploy**

Merge via `mcp__github__merge_pull_request` with `merge_method="merge"` (never squash — CLAUDE.md rule). Wait for the "Deploy to Production" CI step to finish green. Do NOT SSH deploy.

- [ ] **Step 7: E2E verification via Playwright MCP**

Against `https://spelix.app`:
1. Navigate with a logged-in expert_reviewer user.
2. Click "Validate Thresholds" in the portal header.
3. Verify the Squat section renders with `knee_valgus_caution_deg = 5 degrees` and the Myer citation.
4. Click "Flag" on that row. Fill proposed value `8`, citation `Krosshaug 2016 — 8° not replicated`, rationale ≥20 chars. Submit.
5. Switch to "My flags" tab. Confirm the row appears with status `open` and the snapshotted current_value `5`.
6. `browser_console_messages(level=error)` empty; `browser_network_requests` filter for 4xx/5xx empty.
7. Record the screenshot path + the flag `id` in the handoff note. If anything is broken, write an `E2E Findings` block in `.claude/handoff.md` and stop.

---

## Self-Review

- **Spec coverage:** FR-EXPV-08 requires (1) view current thresholds — Task 5 + Task 9; (2) flag with citation for correct value — Task 8 (modal) + Task 5 POST endpoint; (3) admin-visible queue — Task 6. All three spec clauses are covered.
- **Placeholder scan:** No TBD/TODO/"handle error"/"similar to Task N". All code blocks are complete. The PR title and commit SHA at Task 10/11 are necessarily populated at merge time and are the only deferred values — which is unavoidable.
- **Type consistency check:**
  - `ThresholdRow`, `ThresholdListing`, `ThresholdFlagCreate`, `ThresholdFlagResponse`, `ThresholdFlagResolveAction` used consistently across Tasks 3, 4, 5, 6, 7, 8, 9.
  - `section` union `"squat" | "bench" | "deadlift" | "control"` consistent between Python `Literal` (Task 3) and TS types (Task 7).
  - Endpoint paths consistent: `/api/v1/expert/thresholds`, `/api/v1/expert/thresholds/flags`, `/api/v1/admin/threshold-flags`, `/api/v1/admin/threshold-flags/{id}` — used the same way across backend definition (Tasks 5/6), frontend client (Task 7), and tests.
  - Service method names consistent: `get_listing`, `create_flag`, `resolve_flag` used the same way in Task 4 and Task 5.
  - Repo method names consistent: `create`, `get_by_id`, `list_by_reviewer`, `list_all`, `update_status` used the same way in Task 2, Task 4, Task 5, Task 6.

All checks pass.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-21-fr-expv-08-threshold-validation-ui.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
