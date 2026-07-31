from api.tracing import TraceAdapter, inject_trace_id


def test_inject_trace_id_adds_field():
    data = {"event": "test"}
    result = inject_trace_id(data, "abc123")
    assert result["trace_id"] == "abc123"
    assert result["event"] == "test"


def test_inject_trace_id_mutates_original():
    data = {"event": "test"}
    result = inject_trace_id(data, "abc123")
    assert data["trace_id"] == "abc123"
    assert result is data


def test_trace_adapter_log_format():
    import logging
    adapter = TraceAdapter(logging.getLogger("test"), {"trace_id": "trace-001"})
    msg, kwargs = adapter.process("hello", {})
    assert "[trace-001] hello" == msg
