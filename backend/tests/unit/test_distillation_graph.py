"""M-14: distillation graph must pass RunnableConfig, not bare untyped dict."""

from unittest.mock import AsyncMock, patch
import uuid

import pytest


@pytest.mark.asyncio
async def test_distillation_ainvoke_receives_runnable_config_fields():
    """The config passed to ainvoke must carry run_name and tags for LangSmith tracing."""
    captured_configs: list = []

    async def fake_ainvoke(state, config):
        captured_configs.append(config)
        return {
            "stored_ids": [],
            "formatted": [],
            "trace": [],
            "validation_decision": "pass",
            "decisions": [],
            "candidates": [],
        }

    mock_graph = AsyncMock()
    mock_graph.ainvoke.side_effect = fake_ainvoke

    with patch(
        "app.distillation.graph.build_distillation_graph", return_value=mock_graph
    ):
        from app.distillation.graph import run_distillation_graph
        from app.schemas.coaching import CoachingOutput

        coaching_output = CoachingOutput(
            summary="Test summary",
            strengths=["Good depth"],
            issues=[],
            correction_plan=["Keep chest up"],
            disclaimer=(
                "This feedback is for educational purposes only and is not a "
                "substitute for in-person coaching or medical advice."
            ),
            raw_prompt_tokens=0,
            raw_completion_tokens=0,
        )

        analysis_id = uuid.uuid4()

        await run_distillation_graph(
            analysis_id=analysis_id,
            exercise_type="squat",
            coaching_output=coaching_output,
            retrieved_papers_contexts=[],
            eval_scores={"overall": 0.8},
            anthropic_client=AsyncMock(),
            instructor_client=AsyncMock(),
            cohere_client=AsyncMock(),
            qdrant_client=AsyncMock(),
            brain_embedding_svc=AsyncMock(),
            cove_service_factory=AsyncMock,
            db_session=AsyncMock(),
        )

    assert len(captured_configs) == 1
    config = captured_configs[0]
    assert "run_name" in config, "RunnableConfig must include run_name for LangSmith"
    assert config["run_name"] == "spelix-distillation"
    assert "tags" in config, "RunnableConfig must include tags for LangSmith"
    assert "distillation" in config["tags"]
    assert f"analysis:{analysis_id}" in config["tags"]
    assert "recursion_limit" in config
