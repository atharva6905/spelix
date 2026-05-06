"""Shared fixtures for MC/DC truth-table tests."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig  # noqa: E402


@pytest.fixture()
def cfg() -> ThresholdConfig:
    """ThresholdConfig v1 for scoring/detection tests."""
    return ThresholdConfig(_V1_PATH)


def make_landmarks_frame(
    *,
    visibility: float = 0.9,
    x: float = 0.5,
    y: float = 0.5,
    overrides: dict[int, dict[int, float]] | None = None,
) -> np.ndarray:
    """Return a (33, 5) landmark frame with uniform values.

    Parameters
    ----------
    visibility: Default visibility for all landmarks (col 3 AND col 4).
    x, y: Default x/y position for all landmarks.
    overrides: {landmark_idx: {col_idx: value}} for per-landmark overrides.
    """
    frame = np.zeros((33, 5), dtype=np.float64)
    frame[:, 0] = x
    frame[:, 1] = y
    frame[:, 2] = 0.0
    frame[:, 3] = visibility
    frame[:, 4] = visibility
    if overrides:
        for lm_idx, cols in overrides.items():
            for col_idx, val in cols.items():
                frame[lm_idx, col_idx] = val
    return frame


def make_n_frames(n: int = 30, **kwargs) -> list[np.ndarray]:
    """Return n identical landmark frames."""
    return [make_landmarks_frame(**kwargs) for _ in range(n)]
