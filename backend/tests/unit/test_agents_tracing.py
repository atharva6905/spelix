"""Unit tests for LangSmith tracing integration."""

from __future__ import annotations



from app.agents.tracing import (
    langsmith_enabled,
    run_config_for_analysis,
    serialize_trace_for_storage,
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
