"""ThresholdConfig — loads exercise thresholds from config/thresholds_v{N}.json.

Requirements: FR-SCOR-00 (B-025), FR-SCOR-11 (Phase 1)

Phase 0 uses config/thresholds_v0.json (hardcoded named constants, no magic
numbers scattered through the codebase). Phase 1 uses config/thresholds_v1.json
with nested objects containing value, unit, provenance_citation, last_modified_by.
ThresholdConfigLoader reads the version field from the file at startup.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

# Local-dev candidate: backend/app/config.py → ../../config/thresholds_v{N}.json.
# This works when running pytest or uvicorn from a checkout where the file
# tree is <repo>/backend/app/config.py and the threshold file lives at
# <repo>/config/thresholds_v1.json.
_REPO_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_THRESHOLD_PATH = _REPO_ROOT / "config" / "thresholds_v1.json"


def _resolve_threshold_path() -> Path:
    """Locate ``thresholds_v1.json`` in any supported filesystem layout.

    Resolution order:

    1. ``THRESHOLD_CONFIG_PATH`` env var, if set — returned unconditionally
       even if the file doesn't exist (so the operator gets an explicit
       FileNotFoundError pointing at the value they configured, not a
       confusing fallback).
    2. ``_DEFAULT_THRESHOLD_PATH`` — local-dev layout via ``parent.parent.parent``.
    3. ``Path.cwd() / "config" / "thresholds_v1.json"`` — works in any
       container or shell where the working directory is the project root.
    4. ``/app/config/thresholds_v1.json`` — explicit Docker default for
       the spelix-backend image (WORKDIR=/app, config/ is bind-mounted
       into /app/config via docker-compose.prod.yml).

    Returns the first existing candidate. Raises ``FileNotFoundError``
    listing every candidate that was tried so deploy issues are
    diagnosable from the worker logs alone.

    Regression for the production worker crash where the path
    resolution computed ``/config/thresholds_v1.json`` (filesystem root)
    inside the Docker container because ``parent.parent.parent`` from
    ``/app/app/config.py`` walks up to ``/``. Tests:
    ``tests/unit/test_config_path_resolution.py``.
    """
    env_path = os.environ.get("THRESHOLD_CONFIG_PATH")
    if env_path:
        return Path(env_path)

    candidates: list[Path] = [
        _DEFAULT_THRESHOLD_PATH,
        Path.cwd() / "config" / "thresholds_v1.json",
        Path("/app/config/thresholds_v1.json"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "thresholds_v1.json not found. Tried: "
        + ", ".join(str(c) for c in candidates)
        + ". Set THRESHOLD_CONFIG_PATH env var to override."
    )


# ---------------------------------------------------------------------------
# ThresholdConfig
# ---------------------------------------------------------------------------


class ThresholdConfig:
    """Loads thresholds from config/thresholds_v{N}.json.

    Supports both v0 (flat values) and v1+ (nested objects with provenance).

    Usage::

        cfg = ThresholdConfig()
        caution = cfg.get("squat", "knee_valgus_caution_deg")  # → 5.0
        print(cfg.version)  # → "v1"

        # v1-only: access provenance metadata
        citation = cfg.get_citation("squat", "knee_valgus_caution_deg")
        # → "Myer et al. 2010"

    The file is loaded once at construction time and held in memory. All
    keys are accessed by exercise name (top-level key) and threshold name.

    Raises ``KeyError`` for unknown exercises or threshold names so that
    call sites catch missing config immediately rather than silently using
    wrong defaults.
    """

    def __init__(self, path: Path | None = None) -> None:
        resolved = path or _resolve_threshold_path()
        with resolved.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)

        self._version: str = data["version"]
        self._is_v1 = self._version >= "v1"
        # Store the entire payload except the "version" key
        self._data: dict[str, Any] = {
            k: v for k, v in data.items() if k != "version"
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def version(self) -> str:
        """Version string from the JSON file (e.g. "v0", "v1")."""
        return self._version

    def get(self, section: str, key: str) -> Any:
        """Return a threshold value (unwrapped from v1 nested objects).

        For v0: returns the raw value (number, string, etc.).
        For v1: if the value is a dict with a "value" key, returns that;
                otherwise returns the raw value (for non-threshold sections
                like scoring_weights, score_descriptors).

        Parameters
        ----------
        section:
            Top-level key in the JSON (e.g. "squat", "bench", "deadlift",
            "experience_tolerance", "scoring_weights", "phase_multipliers").
        key:
            The threshold name within that section block.

        Raises
        ------
        KeyError
            If ``section`` or ``key`` is not found in the loaded config.
        """
        block = self._get_section(section)
        raw = self._get_key(block, section, key)
        # v1 nested threshold object: unwrap to just the value
        if isinstance(raw, dict) and "value" in raw:
            return raw["value"]
        return raw

    def get_raw(self, section: str, key: str) -> Any:
        """Return the raw config entry (full dict for v1 nested objects)."""
        block = self._get_section(section)
        return self._get_key(block, section, key)

    def get_citation(self, section: str, key: str) -> str | None:
        """Return the provenance_citation for a v1 nested threshold, or None."""
        block = self._get_section(section)
        raw = self._get_key(block, section, key)
        if isinstance(raw, dict):
            return raw.get("provenance_citation")
        return None

    def get_section(self, section: str) -> dict[str, Any]:
        """Return the full section block (read-only copy).

        For v1 nested thresholds, values are NOT unwrapped — use get() for
        individual unwrapped values.
        """
        return dict(self._get_section(section))

    def all_for_exercise(self, exercise: str) -> dict[str, Any]:
        """Return the full threshold block for an exercise (read-only copy).

        Alias for get_section() — kept for backward compatibility.
        """
        return self.get_section(exercise)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_section(self, section: str) -> dict[str, Any]:
        try:
            return self._data[section]
        except KeyError:
            raise KeyError(
                f"Unknown section '{section}' in threshold config {self._version!r}. "
                f"Available: {list(self._data.keys())}"
            )

    def _get_key(self, block: dict[str, Any], section: str, key: str) -> Any:
        try:
            return block[key]
        except KeyError:
            raise KeyError(
                f"Unknown threshold key '{key}' for section '{section}' "
                f"in threshold config {self._version!r}. "
                f"Available: {list(block.keys())}"
            )
