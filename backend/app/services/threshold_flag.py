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
