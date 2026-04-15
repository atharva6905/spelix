"""Unit tests for composable agent tools (FR-AICP-18)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.state import make_initial_state
from app.agents.tools import get_rep_metrics, retrieve_papers


@pytest.mark.asyncio
async def test_get_rep_metrics_returns_flat_dicts_keyed_by_rep_number():
    analysis_id = uuid.uuid4()
    user_id = uuid.uuid4()
    state = make_initial_state(
        analysis_id=analysis_id,
        user_id=user_id,
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )

    # Mock the repo — RepMetric rows are SimpleNamespace for simplicity.
    rows = [
        SimpleNamespace(rep_index=0, metrics_json={"depth_angle": 92.0}),
        SimpleNamespace(rep_index=1, metrics_json={"depth_angle": 96.5}),
    ]
    rep_metric_repo = SimpleNamespace(get_by_analysis=AsyncMock(return_value=rows))

    update = await get_rep_metrics(state, rep_metric_repo=rep_metric_repo)

    assert update == {
        "rep_metrics": [
            {"rep_number": 1, "depth_angle": 92.0},
            {"rep_number": 2, "depth_angle": 96.5},
        ]
    }
    rep_metric_repo.get_by_analysis.assert_awaited_once_with(analysis_id)


@pytest.mark.asyncio
async def test_get_rep_metrics_handles_empty_result():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.8,
    )
    rep_metric_repo = SimpleNamespace(get_by_analysis=AsyncMock(return_value=[]))

    update = await get_rep_metrics(state, rep_metric_repo=rep_metric_repo)

    assert update == {"rep_metrics": []}


@pytest.mark.asyncio
async def test_retrieve_papers_queries_papers_rag_with_exercise_filter():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.82,
    )

    # Mock retrieval service returns a list with `.collection == "papers_rag"`.
    fake_ctx = SimpleNamespace(
        collection="papers_rag",
        score=0.9,
        chunk=SimpleNamespace(
            id="c1",
            text="Squat depth and knee flexion...",
            title="Sample",
        ),
    )
    retrieval_svc = SimpleNamespace(hybrid_search=AsyncMock(return_value=[fake_ctx]))

    update = await retrieve_papers(state, retrieval_svc=retrieval_svc)

    assert update["papers_contexts"] == [fake_ctx]
    retrieval_svc.hybrid_search.assert_awaited_once()
    call = retrieval_svc.hybrid_search.await_args
    assert call.kwargs["collection"] == "papers_rag"
    assert call.kwargs["exercise_filter"] == "squat"
    assert call.kwargs["rerank"] is True


@pytest.mark.asyncio
async def test_retrieve_papers_returns_empty_on_service_error():
    state = make_initial_state(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.82,
    )

    async def boom(*_a, **_kw):
        raise RuntimeError("qdrant unavailable")

    retrieval_svc = SimpleNamespace(hybrid_search=boom)

    update = await retrieve_papers(state, retrieval_svc=retrieval_svc)

    assert update == {"papers_contexts": [], "degraded_mode": True}
