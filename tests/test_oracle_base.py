# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 v3.0 Oracle Base Framework (Phase 1)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.oracle.env import (
    check_docker,
    check_playwright,
    check_stress_ng,
    get_environment_summary,
)
from mas_eval.oracle.oracle_base import (
    Oracle,
    OracleRegistry,
    OracleTask,
    run_d2_with_oracle,
)

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
            "skill_id": "bash",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_read",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["r"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_edit",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["e"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_write",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["w"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "glob",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["g"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "grep",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["gr"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "web_search",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["s"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "web_fetch",
            "description": "x",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "examples": ["f"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "agent_tool",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["a"],
            "business_rule_version": "2026-05-01",
        },
    ],
}

GOLDEN_EVENTS = [
    {
        "action": {"type": "tool_call", "tool_id": "grep", "input": {"pattern": "foo"}},
        "orchestration": {
            "routing_decision": "auto",
            "routing_reason": "capability_match",
        },
    },
    {
        "action": {
            "type": "tool_call",
            "tool_id": "file_read",
            "input": {"path": "/x.py"},
        },
        "orchestration": {
            "routing_decision": "auto",
            "routing_reason": "capability_match",
        },
    },
    {
        "action": {
            "type": "tool_call",
            "tool_id": "file_edit",
            "input": {"path": "/x.py", "old_str": "foo", "new_str": "bar"},
        },
        "orchestration": {
            "routing_decision": "auto",
            "routing_reason": "capability_match",
        },
    },
]

MOCK_EVENTS = [
    {
        "action": {"type": "tool_call", "tool_id": "grep", "input": {"pattern": "foo"}},
        "orchestration": {
            "routing_decision": "auto",
            "routing_reason": "capability_match",
        },
    },
    {
        "action": {
            "type": "tool_call",
            "tool_id": "file_read",
            "input": {"path": "/x.py"},
        },
        "orchestration": {
            "routing_decision": "auto",
            "routing_reason": "capability_match",
        },
    },
]


class TestOracleTask:
    def test_creation(self):
        task = OracleTask("task-1", "Do something")
        assert task.task_id == "task-1"
        assert task.prompt == "Do something"

    def test_defaults(self):
        task = OracleTask("t1", "p1")
        assert task.expected_tools == []
        assert task.rubric == {}
        assert task.metadata == {}

    def test_with_all_fields(self):
        task = OracleTask(
            "t1", "p1", ["bash", "grep"], {"accuracy": 0.9}, {"source": "test"}
        )
        assert task.expected_tools == ["bash", "grep"]
        assert task.rubric == {"accuracy": 0.9}
        assert task.metadata == {"source": "test"}

    def test_repr(self):
        task = OracleTask("x42", "prompt")
        assert "x42" in repr(task)


class TestOracleABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Oracle()

    def test_concrete_oracle(self):
        class TestOracle(Oracle):
            @property
            def name(self):
                return "test-bench"

            def list_tasks(self):
                return [OracleTask("t1", "Do X")]

            def execute(self, task, card):
                return {"events": GOLDEN_EVENTS}

            def validate_environment(self):
                return True, "ready"

        oracle = TestOracle()
        assert oracle.name == "test-bench"
        assert len(oracle.list_tasks()) == 1
        assert oracle.list_tasks()[0].task_id == "t1"
        assert oracle.validate_environment() == (True, "ready")

        result = oracle.execute(oracle.list_tasks()[0], {})
        assert "events" in result
        assert result["events"] == GOLDEN_EVENTS

    def test_score_default(self):
        class TestOracle(Oracle):
            @property
            def name(self):
                return "test-bench"

            def list_tasks(self):
                return []

            def execute(self, task, card):
                return {"events": []}

            def validate_environment(self):
                return True, "ok"

        oracle = TestOracle()
        assert oracle.score(None, None) is None

    def test_score_override(self):
        class ScoringOracle(Oracle):
            @property
            def name(self):
                return "scoring-bench"

            def list_tasks(self):
                return [OracleTask("t1", "Do X")]

            def execute(self, task, card):
                return {"events": []}

            def validate_environment(self):
                return True, "ok"

            def score(self, task, agent_trajectory, golden_trajectory=None):
                return 85.0

        oracle = ScoringOracle()
        assert oracle.score(None, None) == 85.0


class TestOracleRegistry:
    def setup_method(self):
        OracleRegistry.clear()

    def test_register_and_get(self):
        class TestOracle(Oracle):
            @property
            def name(self):
                return "test-1"

            def list_tasks(self):
                return []

            def execute(self, task, card):
                return {"events": []}

            def validate_environment(self):
                return True, "ok"

        oracle = TestOracle()
        OracleRegistry.register(oracle)
        assert OracleRegistry.get("test-1") is oracle

    def test_list(self):
        class O1(Oracle):
            @property
            def name(self):
                return "o1"

            def list_tasks(self):
                return []

            def execute(self, t, c):
                return {"events": []}

            def validate_environment(self):
                return True, "ok"

        class O2(Oracle):
            @property
            def name(self):
                return "o2"

            def list_tasks(self):
                return []

            def execute(self, t, c):
                return {"events": []}

            def validate_environment(self):
                return True, "ok"

        OracleRegistry.register(O1())
        OracleRegistry.register(O2())
        assert "o1" in OracleRegistry.list()
        assert "o2" in OracleRegistry.list()

    def test_get_unknown(self):
        assert OracleRegistry.get("nonexistent") is None

    def test_clear(self):
        class TestOracle(Oracle):
            @property
            def name(self):
                return "to-clear"

            def list_tasks(self):
                return []

            def execute(self, t, c):
                return {"events": []}

            def validate_environment(self):
                return True, "ok"

        OracleRegistry.register(TestOracle())
        assert len(OracleRegistry.list()) == 1
        OracleRegistry.clear()
        assert OracleRegistry.list() == []

    def test_overwrite(self):
        class O1(Oracle):
            @property
            def name(self):
                return "dup"

            def list_tasks(self):
                return [OracleTask("a", "A")]

            def execute(self, t, c):
                return {"events": []}

            def validate_environment(self):
                return True, "ok"

        class O2(Oracle):
            @property
            def name(self):
                return "dup"

            def list_tasks(self):
                return [OracleTask("b", "B")]

            def execute(self, t, c):
                return {"events": []}

            def validate_environment(self):
                return True, "ok"

        OracleRegistry.register(O1())
        OracleRegistry.register(O2())
        retrieved = OracleRegistry.get("dup")
        assert retrieved.list_tasks()[0].task_id == "b"


class TestRunD2WithOracle:
    def setup_method(self):
        OracleRegistry.clear()
        self._register_test_oracle()

    def _register_test_oracle(self):
        class TestOracle(Oracle):
            @property
            def name(self):
                return "test-d2"

            def list_tasks(self):
                return [
                    OracleTask(
                        "golden-task",
                        "Fix the bug",
                        expected_tools=["grep", "file_read", "file_edit"],
                    ),
                    OracleTask("second-task", "Do other thing"),
                ]

            def execute(self, task, card):
                return {"events": GOLDEN_EVENTS}

            def validate_environment(self):
                return True, "all systems go"

        OracleRegistry.register(TestOracle())

    def test_success(self):
        mock = {"events": MOCK_EVENTS}
        result = run_d2_with_oracle(SAMPLE_CARD, "test-d2", "golden-task", mock)
        assert result["domain"] == "D2"
        assert 0 <= result["score"] <= 100
        assert result["summary"]["oracle_name"] == "test-d2"
        assert result["summary"]["oracle_task"] == "golden-task"
        assert result["summary"]["oracle_env_ok"] is True

    def test_uses_default_task(self):
        mock = {"events": MOCK_EVENTS}
        result = run_d2_with_oracle(SAMPLE_CARD, "test-d2", mock_trajectory=mock)
        assert result["summary"]["oracle_task"] == "golden-task"

    def test_oracle_unknown(self):
        with pytest.raises(ValueError, match="not registered"):
            run_d2_with_oracle(SAMPLE_CARD, "no-such-oracle")

    def test_task_unknown(self):
        with pytest.raises(ValueError, match="not found"):
            run_d2_with_oracle(SAMPLE_CARD, "test-d2", task_id="no-such-task")

    def test_oracle_score_included(self):
        class ScoringOracle(Oracle):
            @property
            def name(self):
                return "scoring-d2"

            def list_tasks(self):
                return [OracleTask("t1", "Do X")]

            def execute(self, t, c):
                return {"events": GOLDEN_EVENTS}

            def validate_environment(self):
                return True, "ok"

            def score(self, task, agent_traj, golden_traj=None):
                return 92.5

        OracleRegistry.register(ScoringOracle())
        result = run_d2_with_oracle(
            SAMPLE_CARD, "scoring-d2", "t1", {"events": MOCK_EVENTS}
        )
        assert result["subscores"]["oracle_score"] == 92.5

    def test_oracle_finding_appended(self):
        mock = {"events": MOCK_EVENTS}
        result = run_d2_with_oracle(SAMPLE_CARD, "test-d2", "golden-task", mock)
        oracle_findings = [f for f in result["findings"] if f["category"] == "oracle"]
        assert len(oracle_findings) >= 1
        assert "test-d2" in oracle_findings[0]["detail"]

    def test_no_mock_trajectory(self):
        result = run_d2_with_oracle(SAMPLE_CARD, "test-d2", "golden-task")
        assert result["subscores"]["task_completion"] == 0.0

    def test_oracle_with_no_tasks(self):
        class EmptyOracle(Oracle):
            @property
            def name(self):
                return "empty-oracle"

            def list_tasks(self):
                return []

            def execute(self, task, card):
                return {"events": []}

            def get_golden_trajectory(self, task):
                return {}

            def validate_environment(self):
                return True, "no tasks but ok"

        OracleRegistry.register(EmptyOracle())
        with pytest.raises(ValueError, match="has no tasks"):
            run_d2_with_oracle(SAMPLE_CARD, "empty-oracle")


class TestEnvDetection:
    def test_check_docker_returns_tuple(self):
        ok, msg = check_docker()
        assert isinstance(ok, bool)
        assert isinstance(msg, str)

    def test_check_playwright_returns_tuple(self):
        ok, msg = check_playwright()
        assert isinstance(ok, bool)
        assert isinstance(msg, str)

    def test_check_stress_ng_returns_tuple(self):
        ok, msg = check_stress_ng()
        assert isinstance(ok, bool)
        assert isinstance(msg, str)

    def test_get_environment_summary_returns_dict(self):
        summary = get_environment_summary()
        assert isinstance(summary, dict)
        for key in ("docker", "playwright", "stress_ng"):
            assert key in summary
            ok, msg = summary[key]
            assert isinstance(ok, bool)
            assert isinstance(msg, str)
