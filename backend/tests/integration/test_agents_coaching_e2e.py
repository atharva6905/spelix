"""Integration test: analysis worker dispatches to the agent graph when the
feature flag is on, and to the imperative path when off."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_worker_calls_agent_graph_when_flag_enabled(monkeypatch):
    """When SPELIX_PHASE3_AGENT_ENABLED=1, the worker must route to run_coaching_graph."""
    monkeypatch.setenv("SPELIX_PHASE3_AGENT_ENABLED", "1")
    monkeypatch.setenv("SPELIX_AGENT_MODE", "deterministic")

    from app.workers import analysis_worker

    # Patch the two dispatch helpers; the worker should call the graph
    # variant, not the imperative variant.
    with (
        patch.object(
            analysis_worker,
            "_run_coaching_graph",
            new=AsyncMock(return_value=None),
        ) as mock_graph,
        patch.object(
            analysis_worker,
            "_run_coaching_imperative",
            new=AsyncMock(return_value=None),
        ) as mock_imp,
    ):
        # Call the dispatch helper directly with minimal inputs.
        await analysis_worker._dispatch_coaching(
            analysis=object(),
            repo=object(),
            redis=object(),
            pipeline_result=object(),
        )

        mock_graph.assert_awaited_once()
        mock_imp.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_calls_imperative_when_flag_disabled(monkeypatch):
    monkeypatch.setenv("SPELIX_PHASE3_AGENT_ENABLED", "0")

    from app.workers import analysis_worker

    with (
        patch.object(
            analysis_worker,
            "_run_coaching_graph",
            new=AsyncMock(return_value=None),
        ) as mock_graph,
        patch.object(
            analysis_worker,
            "_run_coaching_imperative",
            new=AsyncMock(return_value=None),
        ) as mock_imp,
    ):
        await analysis_worker._dispatch_coaching(
            analysis=object(),
            repo=object(),
            redis=object(),
            pipeline_result=object(),
        )

        mock_imp.assert_awaited_once()
        mock_graph.assert_not_awaited()
