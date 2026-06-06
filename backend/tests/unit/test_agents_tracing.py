"""Unit tests for LangSmith tracing integration."""

from __future__ import annotations


from app.agents.tracing import (
    langsmith_enabled,
    run_config_for_analysis,
    sanitize_error_message,
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
