# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 v3.0 WebArena Oracle."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.oracle.oracle_base import OracleRegistry, run_d2_with_oracle
from mas_eval.oracle.web_arena import WebArenaOracle

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
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "web_fetch",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-05-01",
        },
    ],
}

SHOP_TRAJECTORY = {
    "events": [
        {
            "action": {
                "type": "tool_call",
                "tool_id": "web_fetch",
                "input": {"url": "https://example-shop.com"},
            }
        },
        {
            "action": {
                "type": "tool_call",
                "tool_id": "web_search",
                "input": {"query": "wireless headphones under $100"},
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

SHOP_NO_COMPLETE = {
    "events": [
        {
            "action": {
                "type": "tool_call",
                "tool_id": "web_fetch",
                "input": {"url": "https://example-shop.com"},
            }
        },
        {
            "action": {
                "type": "tool_call",
                "tool_id": "web_search",
                "input": {"query": "wireless headphones"},
            }
        },
    ]
}

SHOP_EMPTY_TRAJECTORY = {"events": []}

WRONG_TRAJECTORY = {
    "events": [
        {
            "action": {
                "type": "tool_call",
                "tool_id": "bash",
                "input": {"command": "ls"},
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


class TestWebArenaOracle:
    def setup_method(self):
        self.oracle = WebArenaOracle()

    def test_name(self):
        assert self.oracle.name == "web-arena"

    def test_list_tasks_returns_five(self):
        tasks = self.oracle.list_tasks()
        assert len(tasks) == 5

    def test_task_ids_are_unique(self):
        tasks = self.oracle.list_tasks()
        ids = [t.task_id for t in tasks]
        assert len(ids) == len(set(ids))
        for tid in ids:
            assert tid.startswith("web-arena-")

    def test_task_fields(self):
        tasks = self.oracle.list_tasks()
        for t in tasks:
            assert len(t.prompt) > 10
            assert isinstance(t.expected_tools, list)
            assert "domain" in t.metadata
            assert "url" in t.metadata
            assert "success_criteria" in t.rubric

    def test_execute_returns_golden(self):
        task = self.oracle.list_tasks()[0]
        result = self.oracle.execute(task, SAMPLE_CARD)
        assert "events" in result
        assert len(result["events"]) >= 2

    def test_execute_event_format(self):
        task = self.oracle.list_tasks()[0]
        result = self.oracle.execute(task, SAMPLE_CARD)
        for event in result["events"]:
            assert "action" in event
            assert "type" in event["action"]
            assert "tool_id" in event["action"]
            assert "input" in event["action"]

    def test_execute_unknown_task(self):
        class FakeTask:
            task_id = "web-arena-nonexistent"

        result = self.oracle.execute(FakeTask(), SAMPLE_CARD)
        assert result == {"events": []}

    def test_validate_environment(self):
        ok, msg = self.oracle.validate_environment()
        assert ok is True
        assert "tasks" in msg

    def test_score_empty_returns_zero(self):
        task = self.oracle.list_tasks()[0]
        assert self.oracle.score(task, None) == 0.0
        assert self.oracle.score(task, []) == 0.0
        assert self.oracle.score(task, SHOP_EMPTY_TRAJECTORY) == 0.0


class TestSimulatedScore:
    def setup_method(self):
        self.oracle = WebArenaOracle()

    def test_all_keywords_and_complete_high_score(self):
        task = self.oracle.list_tasks()[0]
        score = self.oracle._simulate_score(task, SHOP_TRAJECTORY["events"])
        assert score > 50.0

    def test_keywords_without_completion(self):
        task = self.oracle.list_tasks()[0]
        score = self.oracle._simulate_score(task, SHOP_NO_COMPLETE["events"])
        assert score < 80.0
        assert score > 0.0

    def test_no_keywords_no_completion_low_score(self):
        task = self.oracle.list_tasks()[0]
        events = [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "bash",
                    "input": {"command": "ls"},
                }
            }
        ]
        score = self.oracle._simulate_score(task, events)
        assert score < 30.0

    def test_task_has_keywords(self):
        task = self.oracle.list_tasks()[0]
        keywords = self.oracle._get_keywords(task)
        assert len(keywords) >= 2

    def test_all_domains_have_keywords(self):
        tasks = self.oracle.list_tasks()
        for t in tasks:
            keywords = self.oracle._get_keywords(t)
            assert len(keywords) >= 2, f"{t.task_id} has no keywords"

    def test_booking_keywords_score(self):
        task = self.oracle.list_tasks()[1]
        assert task.task_id == "web-arena-booking-001"
        good_events = [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "web_fetch",
                    "input": {"url": "https://example-booking.com"},
                }
            },
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "web_search",
                    "input": {"query": "Paris hotels free cancellation July"},
                }
            },
            {"action": {"type": "task_complete", "result": "success"}},
        ]
        score = self.oracle._simulate_score(task, good_events)
        assert score > 50.0

    def test_form_task_no_tools_low_score(self):
        task = self.oracle.list_tasks()[4]
        assert task.task_id == "web-arena-form-001"
        events = [{"action": {"type": "task_complete", "result": "success"}}]
        score = self.oracle._simulate_score(task, events)
        assert score > 0


class TestWebArenaIntegration:
    def setup_method(self):
        OracleRegistry.clear()
        self.oracle = WebArenaOracle()
        OracleRegistry.register(self.oracle)
        # Force simulated mode for deterministic tests
        import mas_eval.oracle.web_arena as wa

        self._real_check = wa.check_playwright
        wa.check_playwright = lambda: (False, "mocked for test")

    def teardown_method(self):
        import mas_eval.oracle.web_arena as wa

        wa.check_playwright = self._real_check
        OracleRegistry.clear()

    def test_registered(self):
        assert OracleRegistry.get("web-arena") is self.oracle

    def test_run_d2_with_oracle(self):
        result = run_d2_with_oracle(
            SAMPLE_CARD, "web-arena", mock_trajectory=SHOP_TRAJECTORY
        )
        assert result["domain"] == "D2"
        assert 0 <= result["score"] <= 100
        assert result["summary"]["oracle_name"] == "web-arena"
        assert result["summary"]["oracle_env_ok"] is True

    def test_oracle_score_in_result(self):
        result = run_d2_with_oracle(
            SAMPLE_CARD, "web-arena", mock_trajectory=SHOP_TRAJECTORY
        )
        assert "oracle_score" in result["subscores"]
        assert result["subscores"]["oracle_score"] > 0

    def test_good_vs_wrong_score(self):
        good = run_d2_with_oracle(
            SAMPLE_CARD, "web-arena", mock_trajectory=SHOP_TRAJECTORY
        )
        wrong = run_d2_with_oracle(
            SAMPLE_CARD, "web-arena", mock_trajectory=WRONG_TRAJECTORY
        )
        assert good["subscores"]["oracle_score"] > wrong["subscores"]["oracle_score"]

    def test_empty_score_zero(self):
        result = run_d2_with_oracle(
            SAMPLE_CARD, "web-arena", mock_trajectory=SHOP_EMPTY_TRAJECTORY
        )
        assert result["subscores"]["oracle_score"] == 0.0
