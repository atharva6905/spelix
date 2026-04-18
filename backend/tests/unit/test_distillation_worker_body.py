"""Unit tests for distill_analysis_body + build_distillation_ctx.

These tests cover the worker-side entry points that make the distillation
pipeline fire on real analyses: `distill_analysis_body` (loads
analysis+coaching, runs the graph, commits) and `build_distillation_ctx`
(constructs the heavyweight client dict).

All external services (Anthropic, Cohere, Qdrant, async_session) are
mocked — no network or DB I/O.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.distillation_worker import (
    _build_papers_contexts,
    distill_analysis_body,
)


def _disclaimer() -> str:
    return (
        "This feedback is for educational purposes only and is not a "
        "substitute for in-person coaching or medical advice."
    )


def _valid_structured_output_json() -> dict:
    return {
        "summary": "Solid session with one knee cave on rep 2.",
        "strengths": ["Consistent tempo"],
        "issues": [],
        "correction_plan": ["Drive knees out as you descend."],
        "recommended_cues": [],
        "citations": [],
        "safety_warnings": [],
        "confidence_level": "High",
        "dimension_addressed": "Movement Quality",
        "disclaimer": _disclaimer(),
        "raw_prompt_tokens": 0,
        "raw_completion_tokens": 0,
    }


# ---------------------------------------------------------------------------
# _build_papers_contexts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_papers_contexts_filters_to_papers_rag_only() -> None:
    """Only collection=papers_rag contexts survive; coach_brain filtered out."""
    coaching_result = MagicMock()
    coaching_result.retrieved_sources_json = {
        "contexts": [
            {
                "chunk": {
                    "id": "c1", "text": "biomechanics text", "paper_id": "p1",
                    "chunk_index": 0, "section": "results", "token_count": 10,
                    "quality_tier": "L2_rct", "title": "Paper A", "authors": ["X"],
                    "year": 2024, "doi": None,
                },
                "score": 0.9,
                "collection": "papers_rag",
            },
            {
                "chunk": {
                    "id": "c2", "text": "a cue", "paper_id": "", "chunk_index": 0,
                    "section": None, "token_count": 0, "quality_tier": "L4_guideline",
                    "title": "Brain Entry", "authors": [], "year": None, "doi": None,
                },
                "score": 0.8,
                "collection": "coach_brain",
            },
        ]
    }
    ctxs = await _build_papers_contexts(coaching_result)
    assert len(ctxs) == 1
    assert ctxs[0].collection == "papers_rag"


@pytest.mark.asyncio
async def test_build_papers_contexts_handles_malformed_rows() -> None:
    """Pydantic validation errors on malformed rows are swallowed."""
    coaching_result = MagicMock()
    coaching_result.retrieved_sources_json = {
        "contexts": [
            {"not": "a valid RetrievedContext"},
            {
                "chunk": {
                    "id": "c1", "text": "ok", "paper_id": "p1", "chunk_index": 0,
                    "section": None, "token_count": 5, "quality_tier": "L3_observational",
                    "title": "T", "authors": ["A"], "year": 2020, "doi": None,
                },
                "score": 0.5,
                "collection": "papers_rag",
            },
        ]
    }
    ctxs = await _build_papers_contexts(coaching_result)
    assert len(ctxs) == 1


@pytest.mark.asyncio
async def test_build_papers_contexts_handles_empty_retrieved_sources() -> None:
    coaching_result = MagicMock()
    coaching_result.retrieved_sources_json = None
    assert await _build_papers_contexts(coaching_result) == []


# ---------------------------------------------------------------------------
# distill_analysis_body
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_body_aborts_when_session_maker_is_none() -> None:
    result = await distill_analysis_body(
        ctx={"db_session_maker": None}, analysis_id=uuid.uuid4()
    )
    assert result == {"status": "skipped_no_session"}


@pytest.mark.asyncio
async def test_body_skipped_when_analysis_not_found() -> None:
    fake_session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    session_maker = MagicMock(return_value=session_cm)

    with patch(
        "app.workers.distillation_worker.AnalysisRepository"
    ) as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = None
        mock_repo_cls.return_value = mock_repo

        result = await distill_analysis_body(
            ctx={"db_session_maker": session_maker},
            analysis_id=uuid.uuid4(),
        )
    assert result == {"status": "skipped_no_analysis"}


@pytest.mark.asyncio
async def test_body_skipped_when_coaching_result_missing() -> None:
    fake_session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    session_maker = MagicMock(return_value=session_cm)

    analysis = MagicMock()
    analysis.eval_scores = {"overall": 0.9}

    with patch(
        "app.workers.distillation_worker.AnalysisRepository"
    ) as mock_analysis_cls, patch(
        "app.workers.distillation_worker.CoachingResultRepository"
    ) as mock_coaching_cls:
        mock_analysis_cls.return_value = AsyncMock(
            get_by_id=AsyncMock(return_value=analysis)
        )
        mock_coaching_cls.return_value = AsyncMock(
            get_by_analysis=AsyncMock(return_value=None)
        )

        result = await distill_analysis_body(
            ctx={"db_session_maker": session_maker},
            analysis_id=uuid.uuid4(),
        )
    assert result == {"status": "skipped_no_coaching"}


@pytest.mark.asyncio
async def test_body_happy_path_commits_and_returns_ok() -> None:
    fake_session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    session_maker = MagicMock(return_value=session_cm)

    analysis = MagicMock()
    analysis.eval_scores = {"overall": 0.9, "correctness": 0.85}
    analysis.exercise_type = "squat"

    coaching_result = MagicMock()
    coaching_result.structured_output_json = _valid_structured_output_json()
    coaching_result.retrieved_sources_json = None

    with patch(
        "app.workers.distillation_worker.AnalysisRepository"
    ) as mock_analysis_cls, patch(
        "app.workers.distillation_worker.CoachingResultRepository"
    ) as mock_coaching_cls, patch(
        "app.workers.distillation_worker.run_distillation_graph",
        new_callable=AsyncMock,
    ) as mock_run:
        mock_analysis_cls.return_value = AsyncMock(
            get_by_id=AsyncMock(return_value=analysis)
        )
        mock_coaching_cls.return_value = AsyncMock(
            get_by_analysis=AsyncMock(return_value=coaching_result)
        )
        mock_run.return_value = (
            {
                "validation_decision": "pass",
                "stored_ids": [uuid.uuid4()],
                "trace": [{"node": "extract_insights"}],
            },
            {"nodes_executed": [{"node": "extract_insights"}]},
        )

        result = await distill_analysis_body(
            ctx={
                "db_session_maker": session_maker,
                "anthropic_client": MagicMock(),
                "instructor_client": MagicMock(),
                "cohere_client": MagicMock(),
                "qdrant_client": MagicMock(),
                "brain_embedding_svc": MagicMock(),
            },
            analysis_id=uuid.uuid4(),
        )

    assert result["status"] == "ok"
    assert result["validation_decision"] == "pass"
    assert len(result["stored_ids"]) == 1
    assert result["trace_summary"]["nodes_count"] == 1
    fake_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# build_distillation_ctx (deps.py)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_distillation_ctx_returns_expected_keys() -> None:
    """Smoke test: the dict shape is what distill_analysis_body expects."""
    from app.workers import deps as deps_mod

    fake_anthropic = MagicMock()
    fake_cohere = MagicMock()
    fake_qdrant_wrapper = MagicMock()
    fake_qdrant_wrapper._client = MagicMock(name="raw_qdrant_client")

    with patch.object(
        deps_mod, "anthropic",
        MagicMock(AsyncAnthropic=MagicMock(return_value=fake_anthropic)),
    ), patch.object(
        deps_mod, "instructor",
        MagicMock(from_anthropic=MagicMock(return_value=MagicMock())),
    ), patch.object(
        deps_mod, "get_cohere_client", return_value=fake_cohere,
    ), patch.object(
        deps_mod, "get_qdrant_client",
        new_callable=AsyncMock, return_value=fake_qdrant_wrapper,
    ):
        ctx = await deps_mod.build_distillation_ctx()

    assert set(ctx.keys()) == {
        "anthropic_client",
        "instructor_client",
        "cohere_client",
        "qdrant_client",
        "brain_embedding_svc",
        "db_session_maker",
    }
    assert ctx["cohere_client"] is fake_cohere
    assert ctx["qdrant_client"] is fake_qdrant_wrapper


@pytest.mark.asyncio
async def test_build_distillation_ctx_handles_none_qdrant() -> None:
    """When Qdrant is unavailable (cold-start), qdrant_client is None."""
    from app.workers import deps as deps_mod

    with patch.object(
        deps_mod, "anthropic",
        MagicMock(AsyncAnthropic=MagicMock(return_value=MagicMock())),
    ), patch.object(
        deps_mod, "instructor",
        MagicMock(from_anthropic=MagicMock(return_value=MagicMock())),
    ), patch.object(
        deps_mod, "get_cohere_client", return_value=MagicMock(),
    ), patch.object(
        deps_mod, "get_qdrant_client",
        new_callable=AsyncMock, return_value=None,
    ):
        ctx = await deps_mod.build_distillation_ctx()
    assert ctx["qdrant_client"] is None
