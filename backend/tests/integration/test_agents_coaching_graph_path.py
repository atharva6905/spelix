"""Integration test for the feature-flagged _run_coaching_graph dispatcher
path, exercising every dependency import but mocking at the service boundary
so no network calls are made."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.coaching import CoachingOutput


def _make_coaching_output() -> CoachingOutput:
    return CoachingOutput(
        summary="Rep 1 shows strong bracing throughout descent.",
        strengths=["solid bar path"],
        correction_plan=["drive knees out on ascent"],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=100,
        raw_completion_tokens=50,
    )


def _make_fake_rep_metric_repo() -> MagicMock:
    """Return a mock RepMetricRepository whose get_by_analysis returns []."""
    fake = MagicMock()
    fake.get_by_analysis = AsyncMock(return_value=[])
    return fake


@pytest.mark.asyncio
async def test_run_coaching_graph_happy_path_persists_coaching_result():
    """Exercise _run_coaching_graph end-to-end with every service mocked.

    Verifies:
      - The graph runs and produces coaching_output.
      - CoachingResult is persisted with enriched agent_trace_json.
      - eval_scores and flagged_for_review are propagated to the analyses row.
    """
    from app.workers import analysis_worker

    user_id = uuid.uuid4()
    analysis_id = uuid.uuid4()

    analysis = SimpleNamespace(
        id=analysis_id,
        user_id=user_id,
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        eval_scores=None,
        flagged_for_review=False,
    )

    mock_db = MagicMock()
    repo = SimpleNamespace(db=mock_db, update=AsyncMock())
    redis = MagicMock()
    pipeline_result = SimpleNamespace(keyframes=None)

    fake_profile = SimpleNamespace(
        height_cm=180,
        weight_kg=82,
        age=28,
        experience_level="intermediate",
        arm_span_cm=None,
        femur_length_cm=None,
    )
    fake_profile_repo = MagicMock()
    fake_profile_repo.get_by_user_id = AsyncMock(return_value=fake_profile)

    fake_coaching_repo = MagicMock()
    fake_coaching_repo.create = AsyncMock()

    output = _make_coaching_output()
    fake_final_state = {
        "coaching_output": output,
        "cove_verified": True,
        "eval_scores": {
            "faithfulness": 0.91,
            "cove_verified": True,
            "faithfulness_passed": True,
        },
        "papers_contexts": [],
        "brain_contexts": [],
        "retrieval_source": None,
    }
    fake_trace_payload = {
        "mode": "deterministic",
        "nodes_executed": [],
        "eval_scores": fake_final_state["eval_scores"],
        "cove_iterations": [],
        "converged": True,
        "retrieval_source": None,
        "degraded_mode": False,
    }
    fake_run_graph = AsyncMock(
        return_value=(fake_final_state, fake_trace_payload, output)
    )

    mock_pubsub = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    with (
        patch(
            "app.repositories.user_profile.UserProfileRepository",
            return_value=fake_profile_repo,
        ),
        patch(
            "app.repositories.coaching_result.CoachingResultRepository",
            return_value=fake_coaching_repo,
        ),
        patch(
            "app.repositories.rep_metric.RepMetricRepository",
            return_value=_make_fake_rep_metric_repo(),
        ),
        patch("app.services.cohere_client.get_cohere_client", return_value=MagicMock()),
        patch(
            "app.services.qdrant.get_qdrant_client",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.langfuse_client.get_langfuse_client",
            new=AsyncMock(return_value=None),
        ),
        patch("app.services.coaching.CoachingService"),
        patch("app.services.cove.CoveVerificationService"),
        patch("app.services.faithfulness_gate.FaithfulnessGateService"),
        patch("app.config.ThresholdConfig"),
        patch("anthropic.AsyncAnthropic"),
        patch("redis.asyncio.from_url", return_value=mock_pubsub),
        patch("app.agents.graph.run_coaching_graph", new=fake_run_graph),
        patch(
            "app.services.sparse_retrieval.SparseRetrievalService",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.retrieval.RetrievalService",
            return_value=MagicMock(),
        ),
    ):
        result = await analysis_worker._run_coaching_graph(
            analysis=analysis,
            repo=repo,
            redis=redis,
            pipeline_result=pipeline_result,
        )

    coaching_output_result, rep_metrics_dicts, body_stats = result

    # run_coaching_graph was awaited once with the expected kwargs.
    fake_run_graph.assert_awaited_once()
    call_kwargs = fake_run_graph.await_args.kwargs
    assert call_kwargs["analysis_id"] == analysis_id
    assert call_kwargs["user_id"] == user_id
    assert call_kwargs["exercise_type"] == "squat"
    assert call_kwargs["exercise_variant"] == "high_bar"

    # CoachingResult was persisted with the enriched agent_trace_json.
    fake_coaching_repo.create.assert_awaited_once()
    coaching_row = fake_coaching_repo.create.await_args.args[0]
    assert coaching_row.analysis_id == analysis_id
    assert coaching_row.agent_trace_json == fake_trace_payload
    assert coaching_row.cove_verified is True
    assert coaching_row.stream_complete is True

    # eval_scores + flagged_for_review propagated to analyses row.
    assert analysis.eval_scores == fake_final_state["eval_scores"]
    assert analysis.flagged_for_review is False  # faithfulness_passed=True
    repo.update.assert_awaited()

    # pubsub_redis cleanup happened.
    mock_pubsub.aclose.assert_awaited_once()

    # body_stats populated from profile.
    assert body_stats is not None
    assert body_stats["height_cm"] == 180

    # rep_metrics_dicts is a list (empty since we mocked get_by_analysis=[]).
    assert isinstance(rep_metrics_dicts, list)


@pytest.mark.asyncio
async def test_run_coaching_graph_flags_for_review_when_faithfulness_fails():
    """When faithfulness_passed=False, analyses.flagged_for_review must be True."""
    from app.workers import analysis_worker

    analysis = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        eval_scores=None,
        flagged_for_review=False,
    )
    repo = SimpleNamespace(db=MagicMock(), update=AsyncMock())
    redis = MagicMock()
    pipeline_result = SimpleNamespace(keyframes=None)

    fake_profile_repo = MagicMock()
    fake_profile_repo.get_by_user_id = AsyncMock(return_value=None)

    fake_coaching_repo = MagicMock()
    fake_coaching_repo.create = AsyncMock()

    output = _make_coaching_output()
    fake_final_state = {
        "coaching_output": output,
        "cove_verified": False,
        "eval_scores": {"faithfulness": 0.65, "faithfulness_passed": False},
        "papers_contexts": [],
        "brain_contexts": [],
        "retrieval_source": None,
    }
    fake_trace_payload = {
        "mode": "deterministic",
        "nodes_executed": [],
        "eval_scores": fake_final_state["eval_scores"],
        "cove_iterations": [],
        "converged": False,
        "retrieval_source": None,
        "degraded_mode": False,
    }
    fake_run_graph = AsyncMock(
        return_value=(fake_final_state, fake_trace_payload, output)
    )

    mock_pubsub = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    with (
        patch(
            "app.repositories.user_profile.UserProfileRepository",
            return_value=fake_profile_repo,
        ),
        patch(
            "app.repositories.coaching_result.CoachingResultRepository",
            return_value=fake_coaching_repo,
        ),
        patch(
            "app.repositories.rep_metric.RepMetricRepository",
            return_value=_make_fake_rep_metric_repo(),
        ),
        patch("app.services.cohere_client.get_cohere_client", return_value=MagicMock()),
        patch(
            "app.services.qdrant.get_qdrant_client",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.langfuse_client.get_langfuse_client",
            new=AsyncMock(return_value=None),
        ),
        patch("app.services.coaching.CoachingService"),
        patch("app.services.cove.CoveVerificationService"),
        patch("app.services.faithfulness_gate.FaithfulnessGateService"),
        patch("app.config.ThresholdConfig"),
        patch("anthropic.AsyncAnthropic"),
        patch("redis.asyncio.from_url", return_value=mock_pubsub),
        patch("app.agents.graph.run_coaching_graph", new=fake_run_graph),
        patch(
            "app.services.sparse_retrieval.SparseRetrievalService",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.retrieval.RetrievalService",
            return_value=MagicMock(),
        ),
    ):
        await analysis_worker._run_coaching_graph(
            analysis=analysis,
            repo=repo,
            redis=redis,
            pipeline_result=pipeline_result,
        )

    assert analysis.flagged_for_review is True


@pytest.mark.asyncio
async def test_run_coaching_graph_qdrant_available_path():
    """When get_qdrant_client returns a non-None wrapper, SparseRetrievalService
    and RetrievalService are instantiated (lines 712-713)."""
    from app.workers import analysis_worker

    analysis = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="bench",
        exercise_variant="competition_grip",
        confidence_score=0.88,
        eval_scores=None,
        flagged_for_review=False,
    )
    repo = SimpleNamespace(db=MagicMock(), update=AsyncMock())
    redis = MagicMock()
    pipeline_result = SimpleNamespace(keyframes=None)

    fake_profile_repo = MagicMock()
    fake_profile_repo.get_by_user_id = AsyncMock(return_value=None)

    fake_coaching_repo = MagicMock()
    fake_coaching_repo.create = AsyncMock()

    output = _make_coaching_output()
    fake_final_state = {
        "coaching_output": output,
        "cove_verified": True,
        "eval_scores": {"faithfulness": 0.95, "faithfulness_passed": True},
        "papers_contexts": [],
        "brain_contexts": [],
        "retrieval_source": "papers",
    }
    fake_trace_payload = {"mode": "deterministic"}
    fake_run_graph = AsyncMock(
        return_value=(fake_final_state, fake_trace_payload, output)
    )

    mock_pubsub = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    # Return a non-None qdrant_wrapper so the if-branch at line 711 is taken.
    fake_qdrant = MagicMock()
    fake_sparse_svc = MagicMock()
    fake_retrieval_svc = MagicMock()

    with (
        patch(
            "app.repositories.user_profile.UserProfileRepository",
            return_value=fake_profile_repo,
        ),
        patch(
            "app.repositories.coaching_result.CoachingResultRepository",
            return_value=fake_coaching_repo,
        ),
        patch(
            "app.repositories.rep_metric.RepMetricRepository",
            return_value=_make_fake_rep_metric_repo(),
        ),
        patch("app.services.cohere_client.get_cohere_client", return_value=MagicMock()),
        patch(
            "app.services.qdrant.get_qdrant_client",
            new=AsyncMock(return_value=fake_qdrant),
        ),
        patch(
            "app.services.langfuse_client.get_langfuse_client",
            new=AsyncMock(return_value=None),
        ),
        patch("app.services.coaching.CoachingService"),
        patch("app.services.cove.CoveVerificationService"),
        patch("app.services.faithfulness_gate.FaithfulnessGateService"),
        patch("app.config.ThresholdConfig"),
        patch("anthropic.AsyncAnthropic"),
        patch("redis.asyncio.from_url", return_value=mock_pubsub),
        patch("app.agents.graph.run_coaching_graph", new=fake_run_graph),
        patch(
            "app.services.sparse_retrieval.SparseRetrievalService",
            return_value=fake_sparse_svc,
        ),
        patch(
            "app.services.retrieval.RetrievalService",
            return_value=fake_retrieval_svc,
        ),
    ):
        await analysis_worker._run_coaching_graph(
            analysis=analysis,
            repo=repo,
            redis=redis,
            pipeline_result=pipeline_result,
        )

    fake_coaching_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_coaching_graph_raises_when_coaching_output_is_none():
    """When run_coaching_graph returns None as coaching_output, RuntimeError is raised."""
    from app.workers import analysis_worker

    analysis = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        eval_scores=None,
        flagged_for_review=False,
    )
    repo = SimpleNamespace(db=MagicMock(), update=AsyncMock())
    redis = MagicMock()
    pipeline_result = SimpleNamespace(keyframes=None)

    fake_profile_repo = MagicMock()
    fake_profile_repo.get_by_user_id = AsyncMock(return_value=None)

    # Simulate graph returning None for coaching_output.
    fake_final_state = {
        "coaching_output": None,
        "cove_verified": False,
        "eval_scores": {},
        "papers_contexts": [],
        "brain_contexts": [],
        "retrieval_source": None,
    }
    fake_trace_payload = {"mode": "deterministic"}
    fake_run_graph = AsyncMock(
        return_value=(fake_final_state, fake_trace_payload, None)
    )

    mock_pubsub = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    with (
        patch(
            "app.repositories.user_profile.UserProfileRepository",
            return_value=fake_profile_repo,
        ),
        patch("app.repositories.coaching_result.CoachingResultRepository"),
        patch(
            "app.repositories.rep_metric.RepMetricRepository",
            return_value=_make_fake_rep_metric_repo(),
        ),
        patch("app.services.cohere_client.get_cohere_client", return_value=MagicMock()),
        patch(
            "app.services.qdrant.get_qdrant_client",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.langfuse_client.get_langfuse_client",
            new=AsyncMock(return_value=None),
        ),
        patch("app.services.coaching.CoachingService"),
        patch("app.services.cove.CoveVerificationService"),
        patch("app.services.faithfulness_gate.FaithfulnessGateService"),
        patch("app.config.ThresholdConfig"),
        patch("anthropic.AsyncAnthropic"),
        patch("redis.asyncio.from_url", return_value=mock_pubsub),
        patch("app.agents.graph.run_coaching_graph", new=fake_run_graph),
        patch("app.services.sparse_retrieval.SparseRetrievalService"),
        patch("app.services.retrieval.RetrievalService"),
    ):
        with pytest.raises(RuntimeError, match="graph completed without coaching_output"):
            await analysis_worker._run_coaching_graph(
                analysis=analysis,
                repo=repo,
                redis=redis,
                pipeline_result=pipeline_result,
            )


@pytest.mark.asyncio
async def test_run_coaching_graph_keyframes_path():
    """When pipeline_result.keyframes is non-empty, the keyframe analysis branch
    executes (lines 666-692). KeyframeAnalysisService is mocked to return a
    result so keyframe_analysis_text is populated."""
    from app.workers import analysis_worker

    analysis = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        eval_scores=None,
        flagged_for_review=False,
    )
    repo = SimpleNamespace(db=MagicMock(), update=AsyncMock())
    redis = MagicMock()
    # Non-empty keyframes triggers the branch.
    pipeline_result = SimpleNamespace(keyframes=["frame1.jpg", "frame2.jpg"])

    fake_profile_repo = MagicMock()
    fake_profile_repo.get_by_user_id = AsyncMock(return_value=None)

    fake_coaching_repo = MagicMock()
    fake_coaching_repo.create = AsyncMock()

    output = _make_coaching_output()
    fake_final_state = {
        "coaching_output": output,
        "cove_verified": True,
        "eval_scores": {"faithfulness": 0.92, "faithfulness_passed": True},
        "papers_contexts": [],
        "brain_contexts": [],
        "retrieval_source": None,
    }
    fake_trace_payload = {"mode": "deterministic"}
    fake_run_graph = AsyncMock(
        return_value=(fake_final_state, fake_trace_payload, output)
    )

    # Mock KeyframeAnalysisService.analyze_keyframes to return something with
    # model_dump_json so the assignment at line 690 runs.
    fake_kf_result = MagicMock()
    fake_kf_result.model_dump_json.return_value = '{"keyframes": []}'
    fake_kf_svc_instance = MagicMock()
    fake_kf_svc_instance.analyze_keyframes = AsyncMock(return_value=fake_kf_result)

    mock_pubsub = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    with (
        patch(
            "app.repositories.user_profile.UserProfileRepository",
            return_value=fake_profile_repo,
        ),
        patch(
            "app.repositories.coaching_result.CoachingResultRepository",
            return_value=fake_coaching_repo,
        ),
        patch(
            "app.repositories.rep_metric.RepMetricRepository",
            return_value=_make_fake_rep_metric_repo(),
        ),
        patch("app.services.cohere_client.get_cohere_client", return_value=MagicMock()),
        patch(
            "app.services.qdrant.get_qdrant_client",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.langfuse_client.get_langfuse_client",
            new=AsyncMock(return_value=None),
        ),
        patch("app.services.coaching.CoachingService"),
        patch("app.services.cove.CoveVerificationService"),
        patch("app.services.faithfulness_gate.FaithfulnessGateService"),
        patch("app.config.ThresholdConfig"),
        patch("anthropic.AsyncAnthropic"),
        patch("redis.asyncio.from_url", return_value=mock_pubsub),
        patch("app.agents.graph.run_coaching_graph", new=fake_run_graph),
        patch(
            "app.services.sparse_retrieval.SparseRetrievalService",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.retrieval.RetrievalService",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.keyframe_analysis.KeyframeAnalysisService",
            return_value=fake_kf_svc_instance,
        ),
    ):
        await analysis_worker._run_coaching_graph(
            analysis=analysis,
            repo=repo,
            redis=redis,
            pipeline_result=pipeline_result,
        )

    fake_kf_svc_instance.analyze_keyframes.assert_awaited_once()
    fake_coaching_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_coaching_graph_no_profile_gives_none_body_stats():
    """When no user profile exists, body_stats should be None."""
    from app.workers import analysis_worker

    analysis = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="deadlift",
        exercise_variant="conventional",
        confidence_score=0.9,
        eval_scores=None,
        flagged_for_review=False,
    )
    repo = SimpleNamespace(db=MagicMock(), update=AsyncMock())
    redis = MagicMock()
    pipeline_result = SimpleNamespace(keyframes=None)

    fake_profile_repo = MagicMock()
    fake_profile_repo.get_by_user_id = AsyncMock(return_value=None)

    fake_coaching_repo = MagicMock()
    fake_coaching_repo.create = AsyncMock()

    output = _make_coaching_output()
    fake_final_state = {
        "coaching_output": output,
        "cove_verified": True,
        "eval_scores": {"faithfulness": 0.95, "faithfulness_passed": True},
        "papers_contexts": [],
        "brain_contexts": [],
        "retrieval_source": None,
    }
    fake_trace_payload = {"mode": "deterministic"}
    fake_run_graph = AsyncMock(
        return_value=(fake_final_state, fake_trace_payload, output)
    )

    mock_pubsub = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    with (
        patch(
            "app.repositories.user_profile.UserProfileRepository",
            return_value=fake_profile_repo,
        ),
        patch(
            "app.repositories.coaching_result.CoachingResultRepository",
            return_value=fake_coaching_repo,
        ),
        patch(
            "app.repositories.rep_metric.RepMetricRepository",
            return_value=_make_fake_rep_metric_repo(),
        ),
        patch("app.services.cohere_client.get_cohere_client", return_value=MagicMock()),
        patch(
            "app.services.qdrant.get_qdrant_client",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.langfuse_client.get_langfuse_client",
            new=AsyncMock(return_value=None),
        ),
        patch("app.services.coaching.CoachingService"),
        patch("app.services.cove.CoveVerificationService"),
        patch("app.services.faithfulness_gate.FaithfulnessGateService"),
        patch("app.config.ThresholdConfig"),
        patch("anthropic.AsyncAnthropic"),
        patch("redis.asyncio.from_url", return_value=mock_pubsub),
        patch("app.agents.graph.run_coaching_graph", new=fake_run_graph),
        patch(
            "app.services.sparse_retrieval.SparseRetrievalService",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.retrieval.RetrievalService",
            return_value=MagicMock(),
        ),
    ):
        _coaching_out, _rep_metrics, body_stats = await analysis_worker._run_coaching_graph(
            analysis=analysis,
            repo=repo,
            redis=redis,
            pipeline_result=pipeline_result,
        )

    assert body_stats is None
