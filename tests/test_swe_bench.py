# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 v3.0 SWE-bench Oracle."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.oracle.oracle_base import OracleRegistry, run_d2_with_oracle
from mas_eval.oracle.swe_bench import DockerSandbox, SWEBenchOracle, check_docker

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
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_read",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_edit",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-05-01",
        },
    ],
}

CORRECT_TRAJECTORY = {
    "events": [
        {
            "action": {
                "type": "tool_call",
                "tool_id": "file_read",
                "input": {"path": "src/flask/app.py"},
            }
        },
        {
            "action": {
                "type": "file_edit",
                "input": {
                    "path": "src/flask/app.py",
                    "old_str": "return render_template('404.html')",
                    "new_str": "return render_template('404.html'), 404",
                },
            }
        },
        {
            "action": {
                "type": "tool_call",
                "tool_id": "bash",
                "input": {"command": "pytest tests/test_routes.py"},
            }
        },
        {"action": {"type": "task_complete", "result": "success"}},
    ]
}

WRONG_TRAJECTORY = {
    "events": [
        {
            "action": {
                "type": "tool_call",
                "tool_id": "file_read",
                "input": {"path": "src/flask/app.py"},
            }
        },
        {
            "action": {
                "type": "file_edit",
                "input": {
                    "path": "src/flask/app.py",
                    "old_str": "return render_template('404.html')",
                    "new_str": "return 'ok'",
                },
            }
        },
    ]
}

EMPTY_TRAJECTORY = {"events": []}


class TestSWEBenchOracle:
    def setup_method(self):
        self.oracle = SWEBenchOracle()

    def test_name(self):
        assert self.oracle.name == "swe-bench"

    def test_list_tasks_returns_five(self):
        tasks = self.oracle.list_tasks()
        assert len(tasks) == 5

    def test_task_ids(self):
        tasks = self.oracle.list_tasks()
        ids = [t.task_id for t in tasks]
        assert len(ids) == len(set(ids))
        for tid in ids:
            assert tid.startswith("swe-bench-")

    def test_task_fields(self):
        tasks = self.oracle.list_tasks()
        for t in tasks:
            assert len(t.prompt) > 10
            assert isinstance(t.expected_tools, list)
            assert "repo" in t.metadata
            assert "file_path" in t.metadata
            assert "test_command" in t.metadata

    def test_execute_returns_golden(self):
        tasks = self.oracle.list_tasks()
        result = self.oracle.execute(tasks[0], SAMPLE_CARD)
        assert "events" in result
        assert len(result["events"]) >= 3

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
            task_id = "swe-bench-nonexistent"

        result = self.oracle.execute(FakeTask(), SAMPLE_CARD)
        assert result == {"events": []}

    def test_validate_environment(self):
        ok, msg = self.oracle.validate_environment()
        assert ok is True
        assert "tasks loaded" in msg

    def test_extract_edits_from_file_edit(self):
        edits = self.oracle._extract_edits(CORRECT_TRAJECTORY)
        assert len(edits) == 1
        assert edits[0][0] == "src/flask/app.py"
        assert "404" in edits[0][1]

    def test_extract_edits_empty(self):
        assert self.oracle._extract_edits(EMPTY_TRAJECTORY) == []

    def test_extract_edits_from_list(self):
        events = [
            {
                "action": {
                    "type": "file_write",
                    "input": {"path": "/x.py", "content": "print(1)"},
                }
            },
            {
                "action": {
                    "type": "file_edit",
                    "input": {"path": "/y.py", "new_str": "b"},
                }
            },
        ]
        edits = self.oracle._extract_edits(events)
        assert len(edits) == 2

    def test_score_empty_trajectory(self):
        task = self.oracle.list_tasks()[0]
        assert self.oracle.score(task, None) == 0.0
        assert self.oracle.score(task, []) == 0.0
        assert self.oracle.score(task, EMPTY_TRAJECTORY) == 0.0

    def test_score_no_edits_returns_zero(self):
        task = self.oracle.list_tasks()[0]
        no_edits = {
            "events": [
                {"action": {"type": "tool_call", "tool_id": "bash", "input": {}}}
            ]
        }
        assert self.oracle.score(task, no_edits) == 0.0


class TestSimulatedScore:
    def setup_method(self):
        self.oracle = SWEBenchOracle()

    def test_perfect_match_high_score(self):
        task = self.oracle.list_tasks()[0]
        score = self.oracle._simulate_score(
            task, [("src/flask/app.py", "return render_template('404.html'), 404")]
        )
        assert score == 95.0

    def test_partial_match_moderate_score(self):
        task = self.oracle.list_tasks()[0]
        score = self.oracle._simulate_score(
            task, [("src/flask/app.py", "return jsonify(error='not found'), 404")]
        )
        assert 30.0 < score < 95.0

    def test_wrong_path_low_score(self):
        task = self.oracle.list_tasks()[0]
        score = self.oracle._simulate_score(task, [("src/other.py", "print('hello')")])
        assert score <= 30.0

    def test_no_similarity_low_score(self):
        task = self.oracle.list_tasks()[0]
        score = self.oracle._simulate_score(
            task, [("src/flask/app.py", "totally unrelated content")]
        )
        assert score < 30.0

    def test_unknown_task_zero(self):
        class FakeTask:
            task_id = "swe-bench-nonexistent"

        score = self.oracle._simulate_score(FakeTask(), [("x.py", "y")])
        assert score == 0.0

    def test_django_task_scoring(self):
        task = self.oracle.list_tasks()[1]
        assert task.task_id == "swe-bench-django-001"
        fix = "def save(self, *args, **kwargs):\n    self.full_clean()\n    self._state.db = 'default'\n    super().save(*args, **kwargs)"
        score = self.oracle._simulate_score(
            task, [("src/django/db/models/base.py", fix)]
        )
        assert score == 95.0


class TestDockerSandbox:
    def test_init(self):
        sb = DockerSandbox("python:3.11-slim")
        assert sb.image == "python:3.11-slim"
        assert sb.container_id is None

    def test_start_returns_false_without_docker(self):
        docker_ok, _ = check_docker()
        if not docker_ok:
            sb = DockerSandbox()
            task = {"setup_commands": []}
            assert sb.start(task) is False

    def test_cleanup_no_container(self):
        sb = DockerSandbox()
        sb.cleanup()

    def test_exec_no_container(self):
        sb = DockerSandbox()
        stdout, stderr, rc = sb.exec("echo hello")
        assert rc == 1


class TestSWEBenchIntegration:
    def setup_method(self):
        OracleRegistry.clear()
        self.oracle = SWEBenchOracle()
        OracleRegistry.register(self.oracle)

    def teardown_method(self):
        OracleRegistry.clear()

    def test_registered(self):
        assert OracleRegistry.get("swe-bench") is self.oracle

    def test_run_d2_with_oracle_correct(self):
        result = run_d2_with_oracle(
            SAMPLE_CARD, "swe-bench", "swe-bench-flask-001", CORRECT_TRAJECTORY
        )
        assert result["domain"] == "D2"
        assert 0 <= result["score"] <= 100
        assert result["summary"]["oracle_name"] == "swe-bench"
        assert result["summary"]["oracle_task"] == "swe-bench-flask-001"

    def test_oracle_score_in_result(self):
        result = run_d2_with_oracle(
            SAMPLE_CARD, "swe-bench", "swe-bench-flask-001", CORRECT_TRAJECTORY
        )
        assert "oracle_score" in result["subscores"]
        assert result["subscores"]["oracle_score"] > 0

    def test_empty_trajectory_score_zero(self):
        result = run_d2_with_oracle(
            SAMPLE_CARD, "swe-bench", "swe-bench-flask-001", EMPTY_TRAJECTORY
        )
        assert result["subscores"]["oracle_score"] == 0.0

    def test_wrong_fix_score_lower(self):
        correct = run_d2_with_oracle(
            SAMPLE_CARD, "swe-bench", "swe-bench-flask-001", CORRECT_TRAJECTORY
        )
        wrong = run_d2_with_oracle(
            SAMPLE_CARD, "swe-bench", "swe-bench-flask-001", WRONG_TRAJECTORY
        )
        assert correct["subscores"]["oracle_score"] > wrong["subscores"]["oracle_score"]
