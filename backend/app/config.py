"""ThresholdConfig — loads exercise thresholds from config/thresholds_v{N}.json.

Requirements: FR-SCOR-00 (B-025)

Phase 0 uses config/thresholds_v0.json (hardcoded named constants, no magic
numbers scattered through the codebase). Phase 1+ reads the version field from
the file path specified by THRESHOLD_CONFIG_PATH env var.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

# Resolve the repo root from this file's location:
#   backend/app/config.py  →  ../../config/thresholds_v0.json
_REPO_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_THRESHOLD_PATH = _REPO_ROOT / "config" / "thresholds_v0.json"


def _resolve_threshold_path() -> Path:
    """Return the threshold config path, honouring THRESHOLD_CONFIG_PATH env var."""
    env_path = os.environ.get("THRESHOLD_CONFIG_PATH")
    if env_path:
        return Path(env_path)
    return _DEFAULT_THRESHOLD_PATH


# ---------------------------------------------------------------------------
# ThresholdConfig
# ---------------------------------------------------------------------------


class ThresholdConfig:
    """Loads thresholds from config/thresholds_v{N}.json.

    Usage::

        cfg = ThresholdConfig()
        caution = cfg.get("squat", "knee_valgus_caution_deg")  # → 5
        print(cfg.version)  # → "v0"

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
        # Store the entire payload except the "version" key
        self._thresholds: dict[str, dict[str, Any]] = {
            k: v for k, v in data.items() if k != "version"
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def version(self) -> str:
        """Version string from the JSON file (e.g. "v0")."""
        return self._version

    def get(self, exercise: str, key: str) -> Any:
        """Return a threshold value.

        Parameters
        ----------
        exercise:
            Top-level key in the JSON (e.g. "squat", "bench", "deadlift",
            "experience_tolerance").
        key:
            The threshold name within that exercise block.

        Raises
        ------
        KeyError
            If ``exercise`` or ``key`` is not found in the loaded config.
        """
        try:
            exercise_block = self._thresholds[exercise]
        except KeyError:
            raise KeyError(
                f"Unknown exercise '{exercise}' in threshold config {self._version!r}. "
                f"Available: {list(self._thresholds.keys())}"
            )
        try:
            return exercise_block[key]
        except KeyError:
            raise KeyError(
                f"Unknown threshold key '{key}' for exercise '{exercise}' "
                f"in threshold config {self._version!r}. "
                f"Available: {list(exercise_block.keys())}"
            )

    def all_for_exercise(self, exercise: str) -> dict[str, Any]:
        """Return the full threshold block for an exercise (read-only copy)."""
        try:
            return dict(self._thresholds[exercise])
        except KeyError:
            raise KeyError(
                f"Unknown exercise '{exercise}' in threshold config {self._version!r}."
            )
