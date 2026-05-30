import importlib.util
import sys
from pathlib import Path

import pytest

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

ml = load_module("mock_llm", Path(__file__).parent.parent / "mock_llm.py")


class TestClassifyTask:
    def test_deterministic_query_order(self):
        assert ml.classify_task("query_order status") == "deterministic"

    def test_deterministic_read_file(self):
        assert ml.classify_task("read_file /etc/hosts") == "deterministic"

    def test_semi_deterministic_route_to(self):
        assert ml.classify_task("route_to billing") == "semi_deterministic"

    def test_semi_deterministic_classify(self):
        assert ml.classify_task("classify customer complaint") == "semi_deterministic"

    def test_non_deterministic_generate(self):
        assert ml.classify_task("generate a poem") == "non_deterministic"

    def test_non_deterministic_summarize(self):
        assert ml.classify_task("summarize the document") == "non_deterministic"

    def test_default_deterministic(self):
        assert ml.classify_task("unknown task type") == "deterministic"


class TestFindMatchingTool:
    def test_exact_match(self):
        tool_id, tool_def = ml.find_matching_tool("query_order")
        assert tool_id == "query_order"
        assert tool_def["tool_id"] == "query_order"

    def test_search_flight(self):
        tool_id, _ = ml.find_matching_tool("search_flight")
        assert tool_id == "search_flight"

    def test_no_match(self):
        tool_id, tool_def = ml.find_matching_tool("completely_unknown_tool_xyz")
        assert tool_id is None
        assert tool_def is None

    def test_case_insensitive(self):
        tool_id, _ = ml.find_matching_tool("READ_FILE")
        assert tool_id == "read_file"

    def test_partial_text(self):
        tool_id, _ = ml.find_matching_tool("please book_ticket for me")
        assert tool_id == "book_ticket"


class TestGenerateMockTrajectory:
    def test_deterministic_task_has_tool_call(self):
        result = ml.generate_mock_trajectory("query_order")
        events = result["events"]
        tool_events = [e for e in events if e["event_type"] == "agent_action" and e["action"]["type"] == "tool_call"]
        assert len(tool_events) >= 1

    def test_zero_cost(self):
        result = ml.generate_mock_trajectory("query_order")
        assert result["cost_usd"] == 0.0

    def test_trace_id_is_uuid(self):
        result = ml.generate_mock_trajectory("query_order")
        assert len(result["trace_id"]) == 36

    def test_non_deterministic_skips_tool(self):
        result = ml.generate_mock_trajectory("generate a creative story")
        assert result["task_type"] == "non_deterministic"
