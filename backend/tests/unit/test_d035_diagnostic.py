"""Tests for D-035 pose extraction diagnostic helper."""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def fake_extract_landmarks(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch `extract_landmarks` at its definition module AND any re-export."""
    fake_frames: list[np.ndarray] = [
        np.zeros((33, 5), dtype=np.float64) for _ in range(50)
    ]
    fake = MagicMock(return_value=(fake_frames, 30.0, 1080, 1920))
    # Give the mock a real __name__ so run_in_executor name-recording works.
    fake.__name__ = "extract_landmarks"

    # Patch at definition module AND the diagnostic module's already-bound
    # local name (module may have been imported before the fixture runs, in
    # which case `from app.cv.pose_extraction import extract_landmarks` already
    # bound the original function and the source-module patch won't reach it).
    monkeypatch.setattr(
        "app.cv.pose_extraction.extract_landmarks",
        fake,
    )
    # Force-import so the module exists in sys.modules, then patch its binding.
    import importlib
    import app.services.d035_diagnostic as _diag_mod  # noqa: PLC0415
    importlib.import_module("app.services.d035_diagnostic")
    monkeypatch.setattr(_diag_mod, "extract_landmarks", fake)
    return fake


async def test_runs_both_variants_and_returns_structured_timings(
    fake_extract_landmarks: MagicMock,
) -> None:
    from app.services.d035_diagnostic import _run_pose_extraction_diagnostic

    result = await _run_pose_extraction_diagnostic("/tmp/dummy.mov")

    assert set(result.keys()) == {"executor", "inline"}, (
        f"expected {{executor, inline}} keys; got {sorted(result)}"
    )
    for variant in ("executor", "inline"):
        assert result[variant]["frame_count"] == 50, (
            f"{variant} frame_count mismatch: {result[variant]}"
        )
        assert result[variant]["fps"] == 30.0
        assert result[variant]["wall_ms"] >= 0.0
        assert isinstance(result[variant]["wall_ms"], float)
    assert fake_extract_landmarks.call_count == 2, (
        f"extract_landmarks must be called once per variant; got "
        f"{fake_extract_landmarks.call_count} calls"
    )


async def test_executor_variant_uses_run_in_executor(
    fake_extract_landmarks: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The executor variant must go through loop.run_in_executor so it
    matches the production pipeline's call path (pipeline.py line 348)."""
    import asyncio

    from app.services import d035_diagnostic

    executor_calls: list[str] = []
    # Patch the concrete BaseEventLoop — AbstractEventLoop.run_in_executor is
    # shadowed by BaseEventLoop on every platform (Linux SelectorEventLoop,
    # Windows ProactorEventLoop both inherit from BaseEventLoop, not directly
    # from AbstractEventLoop for this method).
    real_run = asyncio.BaseEventLoop.run_in_executor

    async def recording_run_in_executor(self, executor, func, *args):  # type: ignore[no-untyped-def]
        executor_calls.append(getattr(func, "__name__", repr(func)))
        return await real_run(self, executor, func, *args)

    monkeypatch.setattr(
        asyncio.BaseEventLoop,
        "run_in_executor",
        recording_run_in_executor,
    )

    await d035_diagnostic._run_pose_extraction_diagnostic("/tmp/dummy.mov")

    assert any(
        "extract_landmarks" in name for name in executor_calls
    ), f"executor variant must invoke extract_landmarks via run_in_executor; calls: {executor_calls}"
