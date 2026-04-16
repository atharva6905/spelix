"""StageTimer — per-stage wall-time accumulator for pipeline observability.

Used by ``app.services.pipeline.run_cv_pipeline`` to record how long each
step of the analysis pipeline takes in production. The collected dict is
written to ``analyses.timing_json`` so we can diagnose where the budget
goes per analysis (D-035).

Designed for use in synchronous and asynchronous code — the context
manager body may itself be async or sync; we measure wall time via
``time.perf_counter`` regardless.
"""
from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager


class StageTimer:
    """Accumulates ``{stage_name: elapsed_ms}`` across a pipeline run.

    Last-write-wins on duplicate stage names — pipelines that re-enter the
    same logical stage (e.g. a retry loop) record the final attempt only.

    Not thread-safe; instantiate one timer per pipeline run.
    """

    def __init__(self) -> None:
        self._records: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str) -> Generator[None, None, None]:
        """Context manager that records wall time of the enclosed block.

        Records elapsed even if the block raises, so failed stages still
        appear in ``timing_json`` for triage.
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self._records[name] = elapsed_ms

    def as_dict(self) -> dict[str, float]:
        """Return a SHALLOW COPY of the recorded timings."""
        return dict(self._records)
