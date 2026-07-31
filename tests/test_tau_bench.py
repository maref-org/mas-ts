# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 v3.0 Tau-Bench Oracle."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

# Must register before each test class
from mas_eval.oracle.oracle_base import OracleRegistry, run_d2_with_oracle
from mas_eval.oracle.tau_bench import TauBenchOracle

SAMPLE_CARD = {
    "agent_id": "test-agent-001",
    "name": "TestAgent",
    "version": "1.0.0",
    "card_version": "1.2",
    "model_backend": {
        "provider": "test",
        "model": "claude-sonnet-4",
        "deployment": "cloud",
        "endpoint": "https://api.anthropic.com/v1/messages",
    },
    "capabilities": [
        {
            "skill_id": "web_search",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "web_fetch",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "bash",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "file_read",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
    ],
}


class TestTauBenchOracle:
    def setup_method(self):
        self.oracle = TauBenchOracle()

    def test_name(self):
        assert self.oracle.name == "tau-bench"

    def test_list_tasks_returns_seven(self):
        tasks = self.oracle.list_tasks()
        assert len(tasks) == 7

    def test_task_ids_are_unique(self):
        tasks = self.oracle.list_tasks()
        ids = [t.task_id for t in tasks]
        assert len(ids) == len(set(ids))

    def test_task_fields(self):
        tasks = self.oracle.list_tasks()
        for t in tasks:
            assert t.task_id.startswith("tau-bench-")
            assert isinstance(t.prompt, str) and len(t.prompt) > 10
            assert isinstance(t.expected_tools, list)
            assert isinstance(t.metadata, dict)
            assert "domain" in t.metadata

    def test_execute_returns_golden_trajectory(self):
        tasks = self.oracle.list_tasks()
        task = tasks[0]
        result = self.oracle.execute(task, SAMPLE_CARD)
        assert "events" in result
        assert len(result["events"]) >= 2

    def test_execute_event_format(self):
        tasks = self.oracle.list_tasks()
        task = tasks[0]
        result = self.oracle.execute(task, SAMPLE_CARD)
        for event in result["events"]:
            assert "action" in event
            action = event["action"]
            assert "type" in action
            assert "tool_id" in action
            assert "input" in action

    def test_execute_unknown_task_returns_empty(self):
        class FakeTask:
            task_id = "tau-bench-nonexistent"
            expected_tools = []
            prompt = ""

        result = self.oracle.execute(FakeTask(), SAMPLE_CARD)
        assert result == {"events": []}

    def test_validate_environment_true(self):
        ok, msg = self.oracle.validate_environment()
        assert ok is True
        assert "tau_bench_tasks" in msg

    def test_score_perfect(self):
        tasks = self.oracle.list_tasks()
        task = tasks[0]
        golden = self.oracle.execute(task, SAMPLE_CARD)
        score = self.oracle.score(task, golden, golden)
        assert score == 100.0

    def test_score_empty_returns_zero(self):
        task = self.oracle.list_tasks()[0]
        assert self.oracle.score(task, None) == 0.0
        assert self.oracle.score(task, []) == 0.0
        assert self.oracle.score(task, {"events": []}) == 0.0

    def test_score_task_complete_without_tools(self):
        class NoToolTask:
            task_id = "no-tools"
            expected_tools = []
            prompt = ""

        trajectory = {
            "events": [
                {
                    "action": {
                        "type": "task_complete",
                        "result": "success",
                        "tool_id": "",
                        "input": {},
                    }
                }
            ]
        }
        score = self.oracle.score(NoToolTask(), trajectory)
        assert score == 100.0

    def test_score_incomplete_task(self):
        tasks = self.oracle.list_tasks()
        task = tasks[0]
        trajectory = {
            "events": [
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "web_search",
                        "input": {"query": "x"},
                    }
                }
            ]
        }
        score = self.oracle.score(task, trajectory)
        assert score < 100.0
        assert score > 0.0

    def test_score_partial_tools(self):
        task = self.oracle.list_tasks()[0]
        half_tools = {
            "events": [
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "web_search",
                        "input": {"query": "x"},
                    }
                },
                {
                    "action": {
                        "type": "task_complete",
                        "result": "success",
                        "tool_id": "",
                        "input": {},
                    }
                },
            ]
        }
        score = self.oracle.score(task, half_tools)
        assert score > 0.0

    def test_score_with_list_trajectory(self):
        task = self.oracle.list_tasks()[0]
        golden = self.oracle.execute(task, {})
        score = self.oracle.score(task, golden["events"], golden["events"])
        assert score == 100.0

    def test_score_with_invalid_trajectory_type(self):
        task = self.oracle.list_tasks()[0]
        score = self.oracle.score(task, "not-a-trajectory")
        assert score == 0.0

    def test_validate_environment_file_missing(self, monkeypatch):
        fake = MagicMock()
        fake.exists.return_value = False
        fake.name = "tau_bench_tasks.json"
        monkeypatch.setattr("mas_eval.oracle.tau_bench.TASKS_FILE", fake)
        oracle = TauBenchOracle()
        ok, msg = oracle.validate_environment()
        assert ok is False
        assert "not found" in msg

    def test_load_tasks_file_missing(self):
        oracle = TauBenchOracle()
        oracle._tasks_cache = None
        with patch("mas_eval.oracle.tau_bench.TASKS_FILE") as mock_file:
            mock_file.exists.return_value = False
            tasks = oracle._load_tasks()
            assert tasks == []


class TestTauBenchIntegration:
    def setup_method(self):
        OracleRegistry.clear()
        self.oracle = TauBenchOracle()
        OracleRegistry.register(self.oracle)

    def teardown_method(self):
        OracleRegistry.clear()

    def test_registered_in_registry(self):
        assert OracleRegistry.get("tau-bench") is self.oracle

    def test_run_d2_with_oracle(self):
        golden = self.oracle.execute(self.oracle.list_tasks()[0], SAMPLE_CARD)
        mock = {"events": golden["events"][:2]}
        result = run_d2_with_oracle(SAMPLE_CARD, "tau-bench", mock_trajectory=mock)
        assert result["domain"] == "D2"
        assert 0 <= result["score"] <= 100
        assert result["summary"]["oracle_name"] == "tau-bench"
        assert result["summary"]["oracle_env_ok"] is True

    def test_oracle_score_in_d2_result(self):
        golden = self.oracle.execute(self.oracle.list_tasks()[0], SAMPLE_CARD)
        result = run_d2_with_oracle(SAMPLE_CARD, "tau-bench", mock_trajectory=golden)
        assert "oracle_score" in result["subscores"]
        assert result["subscores"]["oracle_score"] == 100.0

    def test_zero_mock_score(self):
        result = run_d2_with_oracle(SAMPLE_CARD, "tau-bench")
        assert result["subscores"]["oracle_score"] == 0.0
