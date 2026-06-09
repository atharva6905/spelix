"""Unit tests for LangSmith tracing integration."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.tracing import (
    langsmith_enabled,
    run_config_for_analysis,
    sanitize_error_message,
    sanitize_trace_errors,
    serialize_trace_for_storage,
)


# ---------------------------------------------------------------------------
# sanitize_error_message — issue #188 / ADR-DISTILL-05
# ---------------------------------------------------------------------------


def test_sanitize_error_message_strips_unix_path():
    """A Unix absolute path with ≥2 segments is replaced with <path>."""
    result = sanitize_error_message("failed to open /tmp/spelix/abc123.mp4")
    assert "<path>" in result
    assert "/tmp/spelix/abc123.mp4" not in result


def test_sanitize_error_message_strips_windows_path():
    """A Windows drive-letter absolute path is replaced with <path>."""
    result = sanitize_error_message(r"file not found: C:\Users\spelix\video.mp4")
    assert "<path>" in result
    assert "C:\\" not in result


def test_sanitize_error_message_strips_multiple_paths():
    """All paths in a message containing more than one are replaced."""
    msg = "copied /app/foo/bar.py to /usr/lib/x/y.so"
    result = sanitize_error_message(msg)
    assert result.count("<path>") == 2
    assert "/app/foo/bar.py" not in result
    assert "/usr/lib/x/y.so" not in result


def test_sanitize_error_message_leaves_non_path_unchanged():
    """Plain error messages that contain no filesystem paths pass through unchanged."""
    for msg in [
        "division by zero",
        "HTTP 429 from api.anthropic.com",
        "value 1/2 is out of range",
        "a/b single segment relative token",
    ]:
        assert sanitize_error_message(msg) == msg, f"unexpectedly mutated: {msg!r}"


def test_sanitize_error_message_leaves_urls_unchanged():
    """URL path components are not filesystem paths — full URLs pass through."""
    msg = "HTTP 429 from https://api.anthropic.com/v1/messages"
    assert sanitize_error_message(msg) == msg


def test_sanitize_error_message_strips_unc_path():
    """Windows UNC paths (\\\\server\\share\\...) are replaced with <path>."""
    result = sanitize_error_message(r"cannot read \\fileserver\share\video.mp4")
    assert "<path>" in result
    assert "fileserver" not in result


def test_sanitize_trace_errors_sanitizes_error_values():
    """sanitize_trace_errors replaces paths in string error values, leaves rest intact."""
    events = [
        {"iteration": 1, "converged": False, "error": "open /tmp/spelix/x.mp4 failed"},
        {"iteration": 2, "converged": True, "error": None},
        {"iteration": 3, "converged": True},
    ]
    cleaned = sanitize_trace_errors(events)
    assert "/tmp/spelix/x.mp4" not in cleaned[0]["error"]
    assert "<path>" in cleaned[0]["error"]
    assert cleaned[0]["iteration"] == 1
    assert cleaned[1] == events[1]
    assert cleaned[2] == events[2]
    # Input events must not be mutated.
    assert "/tmp/spelix/x.mp4" in events[0]["error"]


def test_serialize_trace_for_storage_sanitizes_error_before_write():
    """serialize_trace_for_storage replaces a path in the error field before returning."""
    trace = [
        {
            "node": "cv_node",
            "duration_ms": 5.0,
            "error": "open /tmp/spelix/abc.mp4 permission denied",
            "started_at": "2024-01-01T00:00:00",
            "output_keys": [],
        }
    ]
    result = serialize_trace_for_storage(trace)
    assert "/tmp/spelix/abc.mp4" not in result[0]["error"]
    assert "<path>" in result[0]["error"]


def test_serialize_trace_for_storage_null_error_untouched():
    """Events with error=None are not modified by sanitization."""
    trace = [{"node": "ok_node", "duration_ms": 1.0, "error": None, "output_keys": []}]
    result = serialize_trace_for_storage(trace)
    assert result[0]["error"] is None


def test_serialize_sanitized_error_survives_hard_cap():
    """The sanitized error value is an essential field and survives the hard-cap path."""

    raw_path = "/tmp/spelix/video_abcdef.mp4"
    # Pack non-essential fields so the hard-cap is triggered.
    trace = [
        {
            "node": "pipeline_node",
            "duration_ms": 3.0,
            "error": f"failed to read {raw_path}",
            "started_at": "2024-01-01T00:00:00",
            "output_keys": [],
            "field1": "x" * 3000,
            "field2": "y" * 3000,
            "field3": "z" * 3000,
        }
    ]
    # Tiny cap forces the hard-cap branch (drops non-essential fields).
    result = serialize_trace_for_storage(trace, max_bytes=50)
    surviving_error = result[0].get("error")
    # error is essential — must survive.
    assert surviving_error is not None
    # The surviving value must be sanitized — raw path must not appear.
    assert raw_path not in surviving_error
    assert "<path>" in surviving_error
    # Verify the hard-cap was actually triggered (non-essential fields gone).
    assert "field1" not in result[0]


# ---------------------------------------------------------------------------
# FR-AICP-20 / P3-007: run_id captured in config and surfaced in trace_payload
# ---------------------------------------------------------------------------


def test_run_config_for_analysis_returns_run_id():
    """run_config_for_analysis must include a uuid.UUID run_id in its returned dict."""
    cfg = run_config_for_analysis(
        analysis_id="abc-123",
        user_id="user-456",
        mode="deterministic",
    )
    assert "run_id" in cfg, "run_id must be present in the config dict"
    assert isinstance(cfg["run_id"], uuid.UUID), (
        f"run_id must be a uuid.UUID, got {type(cfg['run_id'])}"
    )


def _make_graph_deps():
    """Minimal dep stubs for run_coaching_graph tests."""
    from app.schemas.coaching import CoachingOutput

    output = CoachingOutput(
        summary="ok",
        strengths=["good"],
        correction_plan=["fix"],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=10,
        raw_completion_tokens=5,
    )

    class _FakeCoveResult:
        def __init__(self, o):
            self.output = o
            self.cove_verified = True
            self.iterations_run = 1
            self.trace = [{"iteration": 1, "converged": True}]

    rep_row = SimpleNamespace(rep_index=0, metrics_json={"depth_angle": 90.0})
    return {
        "rep_metric_repo": SimpleNamespace(get_by_analysis=AsyncMock(return_value=[rep_row])),
        "retrieval_svc": SimpleNamespace(
            hybrid_search=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        collection="papers_rag",
                        score=0.9,
                        chunk=SimpleNamespace(
                            id="p1", text="research", title="t",
                            authors=[], year=2024, doi=None,
                        ),
                    )
                ]
            )
        ),
        "thresholds": SimpleNamespace(all_for_exercise=lambda e: {}),
        "analysis_repo": SimpleNamespace(list_recent_by_user=AsyncMock(return_value=[])),
        "coaching_svc": SimpleNamespace(
            generate_coaching_streaming=AsyncMock(return_value=output)
        ),
        "cove_svc": SimpleNamespace(verify=AsyncMock(return_value=_FakeCoveResult(output))),
        "fg_svc": SimpleNamespace(
            evaluate=AsyncMock(
                return_value=SimpleNamespace(score=0.91, passed=True, unsupported_claims=[])
            )
        ),
        "pubsub_redis": SimpleNamespace(publish=AsyncMock()),
    }


@pytest.mark.asyncio
async def test_trace_payload_includes_langsmith_run_id_when_enabled(monkeypatch):
    """trace_payload must contain langsmith_run_id when LangSmith is enabled."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "ls-test-key")

    from app.agents.graph import run_coaching_graph

    deps = _make_graph_deps()
    _, trace_payload, _ = await run_coaching_graph(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        body_stats=None,
        keyframe_analysis_text=None,
        mode="deterministic",
        **deps,
    )

    assert "langsmith_run_id" in trace_payload, (
        "trace_payload must include langsmith_run_id when LangSmith is enabled"
    )
    # Must be a valid UUID string
    parsed = uuid.UUID(trace_payload["langsmith_run_id"])
    assert isinstance(parsed, uuid.UUID)


@pytest.mark.asyncio
async def test_trace_payload_omits_langsmith_run_id_when_disabled(monkeypatch):
    """trace_payload must NOT contain langsmith_run_id when LangSmith is disabled."""
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    from app.agents.graph import run_coaching_graph

    deps = _make_graph_deps()
    _, trace_payload, _ = await run_coaching_graph(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        body_stats=None,
        keyframe_analysis_text=None,
        mode="deterministic",
        **deps,
    )

    assert "langsmith_run_id" not in trace_payload, (
        "trace_payload must NOT include langsmith_run_id when LangSmith is disabled"
    )


def test_langsmith_enabled_reads_env_flag(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "ls-test-key")
    assert langsmith_enabled() is True

    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    assert langsmith_enabled() is False


def test_langsmith_enabled_false_when_api_key_missing(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    assert langsmith_enabled() is False


def test_run_config_for_analysis_builds_tagged_config():
    cfg = run_config_for_analysis(
        analysis_id="abc-123",
        user_id="user-456",
        mode="deterministic",
    )
    assert cfg["run_name"] == "coaching_analysis_abc-123"
    assert "analysis_id:abc-123" in cfg["tags"]
    assert "user_id:user-456" in cfg["tags"]
    assert "mode:deterministic" in cfg["tags"]
    assert cfg["metadata"]["analysis_id"] == "abc-123"


def test_serialize_trace_for_storage_truncates_large_fields():
    trace = [
        {"node": "a", "duration_ms": 1.0, "output_keys": ["x"], "error": None},
        {
            "node": "b",
            "duration_ms": 2.0,
            "output_keys": ["y"],
            "error": None,
            "huge_field": "x" * 50_000,
        },
    ]
    serialized = serialize_trace_for_storage(trace, max_bytes=4096)
    import json
    assert len(json.dumps(serialized).encode("utf-8")) <= 4096
    # First event preserved verbatim.
    assert serialized[0] == trace[0]
    # Second event present with huge_field truncated.
    assert "huge_field" in serialized[1]
    assert len(serialized[1]["huge_field"]) < 50_000


def test_serialize_trace_for_storage_small_trace_returned_as_is():
    """A small trace that fits within max_bytes is returned without modification."""
    trace = [{"node": "a", "duration_ms": 1.0, "error": None}]
    result = serialize_trace_for_storage(trace, max_bytes=8192)
    assert result == trace


def test_serialize_trace_for_storage_truncates_large_list_field():
    """A non-essential field containing a large list is truncated as serialized JSON."""

    # Build a trace with a large list field that serializes to > 1024 chars
    large_list = list(range(500))  # serialized: "[0, 1, 2, ...]" >> 1024 chars
    trace = [
        {
            "node": "node_x",
            "duration_ms": 5.0,
            "error": None,
            "started_at": "2024-01-01T00:00:00",
            "output_keys": ["result"],
            "big_list": large_list,
        }
    ]
    # Shrink max_bytes to force truncation
    serialized = serialize_trace_for_storage(trace, max_bytes=512)
    result = serialized[0]
    # big_list should have been replaced with a truncated string
    if "big_list" in result:
        assert isinstance(result["big_list"], str)
        assert "truncated" in result["big_list"]


def test_serialize_trace_for_storage_hard_cap_drops_non_essential():
    """When truncation alone is not enough, non-essential fields are dropped entirely."""

    # Build a trace that will STILL exceed max_bytes even after truncating to 1024 chars.
    # Use many non-essential large fields so truncation to 1024 still exceeds a tiny max_bytes.
    trace = [
        {
            "node": "critical_node",
            "duration_ms": 10.0,
            "error": None,
            "started_at": "2024-01-01T00:00:00",
            "output_keys": ["a", "b"],
            # These non-essential fields will be truncated but the trace stays over tiny max
            "field1": "a" * 2000,
            "field2": "b" * 2000,
            "field3": "c" * 2000,
            "field4": "d" * 2000,
        }
    ]
    # Very small max_bytes so even after string truncation it exceeds the limit
    serialized = serialize_trace_for_storage(trace, max_bytes=50)
    result = serialized[0]
    # After hard cap, only essential fields remain
    assert "node" in result
    assert result["node"] == "critical_node"
    # Non-essential fields should have been dropped
    assert "field1" not in result
    assert "field2" not in result


# ---------------------------------------------------------------------------
# FR-AICP-19 / FR-RESL-07: tool_calls_invoked field on NodeEvent
# ---------------------------------------------------------------------------


def test_node_event_tool_calls_invoked_defaults_to_none():
    """NodeEvent.tool_calls_invoked defaults to None (deterministic traces unchanged)."""
    event = {
        "node": "get_rep_metrics",
        "started_at": "2026-01-01T00:00:00Z",
        "duration_ms": 10.0,
        "output_keys": [],
        "error": None,
    }
    from app.agents.state import NodeEvent
    ne = NodeEvent(**event)
    assert ne.tool_calls_invoked is None


def test_node_event_tool_calls_invoked_accepts_list():
    """NodeEvent.tool_calls_invoked accepts a list of tool name strings."""
    from app.agents.state import NodeEvent
    ne = NodeEvent(
        node="reasoner",
        started_at="2026-01-01T00:00:00Z",
        duration_ms=50.0,
        output_keys=[],
        error=None,
        tool_calls_invoked=["get_rep_metrics", "retrieve_papers"],
    )
    assert ne.tool_calls_invoked == ["get_rep_metrics", "retrieve_papers"]


def test_serialize_trace_preserves_tool_calls_invoked_in_essential_fields():
    """tool_calls_invoked survives serialize_trace_for_storage without truncation
    (it is in ESSENTIAL so it is never dropped by the hard cap)."""
    trace = [
        {
            "node": "reasoner",
            "started_at": "2026-01-01T00:00:00Z",
            "duration_ms": 50.0,
            "output_keys": [],
            "error": None,
            "tool_calls_invoked": ["get_rep_metrics", "retrieve_papers"],
            # large field to trigger the hard-cap path
            "big": "x" * 10000,
        }
    ]
    result = serialize_trace_for_storage(trace, max_bytes=50)
    assert result[0].get("tool_calls_invoked") == ["get_rep_metrics", "retrieve_papers"]
    # Non-essential field should be dropped
    assert "big" not in result[0]


def test_serialize_trace_tool_calls_invoked_none_passes_through():
    """When tool_calls_invoked is None, it passes through serialize_trace_for_storage unchanged."""
    trace = [
        {
            "node": "get_rep_metrics",
            "started_at": "2026-01-01T00:00:00Z",
            "duration_ms": 10.0,
            "output_keys": ["rep_metrics"],
            "error": None,
            "tool_calls_invoked": None,
        }
    ]
    result = serialize_trace_for_storage(trace)
    assert result[0]["tool_calls_invoked"] is None


@pytest.mark.asyncio
async def test_adaptive_reasoner_records_tool_calls_invoked_in_trace():
    """In adaptive mode, each reasoner NodeEvent in state['trace'] includes
    tool_calls_invoked listing the tool names called during that LLM turn
    (FR-AICP-19 / FR-RESL-07)."""
    import uuid as _uuid
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock
    from app.agents.graph import build_adaptive_graph
    from app.agents.state import make_initial_state

    fake_llm = MagicMock()
    fake_llm.bind_tools = MagicMock(return_value=fake_llm)

    call_count = {"n": 0}

    async def _fake_ainvoke(messages):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return SimpleNamespace(
                content="",
                tool_calls=[{"name": "get_rep_metrics", "id": "tc-001"}],
            )
        return SimpleNamespace(content="done", tool_calls=[])

    fake_llm.ainvoke = _fake_ainvoke
    rep_row = SimpleNamespace(rep_index=0, metrics_json={"depth_angle": 90.0})

    deps = {
        "rep_metric_repo": SimpleNamespace(get_by_analysis=AsyncMock(return_value=[rep_row])),
        "retrieval_svc": SimpleNamespace(hybrid_search=AsyncMock(return_value=[])),
        "thresholds": SimpleNamespace(all_for_exercise=lambda e: {}),
        "analysis_repo": SimpleNamespace(list_recent_by_user=AsyncMock(return_value=[])),
        "coaching_svc": SimpleNamespace(generate_coaching_streaming=AsyncMock()),
        "cove_svc": SimpleNamespace(verify=AsyncMock()),
        "fg_svc": SimpleNamespace(evaluate=AsyncMock()),
        "pubsub_redis": SimpleNamespace(publish=AsyncMock()),
        "reasoner_llm": fake_llm,
    }

    graph = build_adaptive_graph(**deps)
    initial = make_initial_state(
        analysis_id=_uuid.uuid4(),
        user_id=_uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        mode="adaptive",
    )

    final_state = await graph.ainvoke(initial, {"recursion_limit": 10})

    # Find all reasoner NodeEvents in the trace
    trace = final_state.get("trace") or []
    reasoner_events = [ev for ev in trace if ev.get("node") == "reasoner"]
    assert len(reasoner_events) >= 1, "Expected at least one reasoner NodeEvent"

    # The first reasoner turn called get_rep_metrics — it must be recorded
    first_reasoner = reasoner_events[0]
    assert "tool_calls_invoked" in first_reasoner, (
        "reasoner NodeEvent must include tool_calls_invoked"
    )
    assert "get_rep_metrics" in (first_reasoner["tool_calls_invoked"] or []), (
        "get_rep_metrics must appear in tool_calls_invoked for the first reasoner turn"
    )


@pytest.mark.asyncio
async def test_deterministic_graph_trace_has_no_tool_calls_invoked():
    """In deterministic mode, NodeEvents do NOT have tool_calls_invoked set
    (must remain None to leave deterministic trace shape unchanged)."""
    import uuid as _uuid
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.agents.graph import build_deterministic_graph
    from app.agents.state import make_initial_state
    from app.schemas.coaching import CoachingOutput

    output = CoachingOutput(
        summary="ok",
        strengths=["good"],
        correction_plan=["fix"],
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=10,
        raw_completion_tokens=5,
    )

    class _FakeCoveResult:
        def __init__(self, o):
            self.output = o
            self.cove_verified = True
            self.iterations_run = 1
            self.trace = [{"iteration": 1, "converged": True}]

    rep_row = SimpleNamespace(rep_index=0, metrics_json={"depth_angle": 90.0})
    deps = {
        "rep_metric_repo": SimpleNamespace(get_by_analysis=AsyncMock(return_value=[rep_row])),
        "retrieval_svc": SimpleNamespace(
            hybrid_search=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        collection="papers_rag",
                        score=0.9,
                        chunk=SimpleNamespace(
                            id="p1", text="research", title="t",
                            authors=[], year=2024, doi=None,
                        ),
                    )
                ]
            )
        ),
        "thresholds": SimpleNamespace(all_for_exercise=lambda e: {}),
        "analysis_repo": SimpleNamespace(list_recent_by_user=AsyncMock(return_value=[])),
        "coaching_svc": SimpleNamespace(
            generate_coaching_streaming=AsyncMock(return_value=output)
        ),
        "cove_svc": SimpleNamespace(verify=AsyncMock(return_value=_FakeCoveResult(output))),
        "fg_svc": SimpleNamespace(
            evaluate=AsyncMock(
                return_value=SimpleNamespace(score=0.91, passed=True, unsupported_claims=[])
            )
        ),
        "pubsub_redis": SimpleNamespace(publish=AsyncMock()),
    }

    graph = build_deterministic_graph(**deps)
    initial = make_initial_state(
        analysis_id=_uuid.uuid4(),
        user_id=_uuid.uuid4(),
        exercise_type="squat",
        exercise_variant="high_bar",
        confidence_score=0.85,
        mode="deterministic",
    )

    final_state = await graph.ainvoke(initial, {"recursion_limit": 25})
    trace = final_state.get("trace") or []
    assert len(trace) > 0, "Expected trace entries"
    # All deterministic events must NOT have tool_calls_invoked populated
    for ev in trace:
        assert ev.get("tool_calls_invoked") is None, (
            f"Deterministic node '{ev.get('node')}' must have tool_calls_invoked=None"
        )
