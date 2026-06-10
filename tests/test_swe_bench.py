# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 v3.0 SWE-bench Oracle."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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

EMPTY_TRAJECTORY: dict = {"events": []}


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


class TestDockerSandboxFull:
    """DockerSandbox method tests with mocked subprocess."""

    def test_start_docker_unavailable(self):
        sb = DockerSandbox()
        with patch(
            "mas_eval.oracle.swe_bench.check_docker", return_value=(False, "no docker")
        ):
            assert sb.start({"setup_commands": []}) is False

    def test_start_with_docker_success(self):
        sb = DockerSandbox()
        with (
            patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
            patch("mas_eval.oracle.swe_bench.subprocess.run") as mock_run,
            patch(
                "mas_eval.oracle.swe_bench.tempfile.mkdtemp",
                return_value="/tmp/swetest",
            ),
        ):
            mock_result = MagicMock(returncode=0, stdout="c123\n", stderr="")
            mock_run.return_value = mock_result
            assert sb.start({"setup_commands": []}) is True
            assert sb.container_id == "c123"
        sb.cleanup()

    def test_start_runs_setup_commands(self):
        sb = DockerSandbox()
        with (
            patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
            patch("mas_eval.oracle.swe_bench.subprocess.run") as mock_run,
            patch(
                "mas_eval.oracle.swe_bench.tempfile.mkdtemp",
                return_value="/tmp/swetest",
            ),
        ):
            mock_result = MagicMock(returncode=0, stdout="c456\n", stderr="")
            mock_run.return_value = mock_result
            with patch.object(sb, "exec") as mock_exec:
                task = {"setup_commands": ["pip install pytest", "apt-get update"]}
                assert sb.start(task) is True
                assert mock_exec.call_count == 2

    def test_start_docker_run_fails(self):
        sb = DockerSandbox()
        with (
            patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
            patch("mas_eval.oracle.swe_bench.subprocess.run") as mock_run,
            patch(
                "mas_eval.oracle.swe_bench.tempfile.mkdtemp",
                return_value="/tmp/swetest",
            ),
        ):
            mock_result = MagicMock(returncode=1, stdout="", stderr="error")
            mock_run.return_value = mock_result
            assert sb.start({"setup_commands": []}) is False

    def test_start_timeout(self):
        sb = DockerSandbox()
        with (
            patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
            patch("mas_eval.oracle.swe_bench.subprocess.run") as mock_run,
            patch(
                "mas_eval.oracle.swe_bench.tempfile.mkdtemp",
                return_value="/tmp/swetest",
            ),
        ):
            mock_run.side_effect = subprocess.TimeoutExpired("docker run", 30)
            assert sb.start({"setup_commands": []}) is False

    def test_exec_with_container(self):
        sb = DockerSandbox()
        sb.container_id = "c123"
        with patch("mas_eval.oracle.swe_bench.subprocess.run") as mock_run:
            mock_result = MagicMock(returncode=0, stdout="hello\n", stderr="")
            mock_run.return_value = mock_result
            stdout, stderr, rc = sb.exec("echo hello")
            assert rc == 0
            assert stdout == "hello\n"

    def test_exec_subprocess_error(self):
        sb = DockerSandbox()
        sb.container_id = "c123"
        with patch("mas_eval.oracle.swe_bench.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("docker exec", 60)
            stdout, stderr, rc = sb.exec("echo hello")
            assert rc == 1

    def test_write_file_success(self):
        sb = DockerSandbox()
        sb.container_id = "c123"
        with (
            patch("mas_eval.oracle.swe_bench.subprocess.run") as mock_run,
            patch("mas_eval.oracle.swe_bench.tempfile.NamedTemporaryFile") as mock_tmp,
            patch("mas_eval.oracle.swe_bench.os.path.exists", return_value=True),
            patch("mas_eval.oracle.swe_bench.os.unlink") as mock_unlink,
        ):
            mock_tmp.return_value.__enter__.return_value.name = "/tmp/t.py"
            mock_tmp.return_value.__enter__.return_value.write = MagicMock()
            mock_tmp.return_value.__enter__.return_value.close = MagicMock()
            mock_result = MagicMock(returncode=0, stdout="", stderr="")
            mock_run.return_value = mock_result
            stdout, stderr, rc = sb.write_file("/x.py", "content")
            assert rc == 0
            mock_unlink.assert_called_once()

    def test_write_file_error(self):
        sb = DockerSandbox()
        sb.container_id = "c123"
        with (
            patch("mas_eval.oracle.swe_bench.subprocess.run") as mock_run,
            patch("mas_eval.oracle.swe_bench.tempfile.NamedTemporaryFile") as mock_tmp,
            patch("mas_eval.oracle.swe_bench.os.path.exists", return_value=True),
            patch("mas_eval.oracle.swe_bench.os.unlink"),
        ):
            mock_tmp.return_value.__enter__.return_value.name = "/tmp/t.py"
            mock_tmp.return_value.__enter__.return_value.write = MagicMock()
            mock_tmp.return_value.__enter__.return_value.close = MagicMock()
            mock_run.side_effect = subprocess.TimeoutExpired("docker cp", 15)
            stdout, stderr, rc = sb.write_file("/x.py", "content")
            assert rc == 1

    def test_run_tests_parses_output(self):
        sb = DockerSandbox()
        sb.container_id = "c123"
        with patch.object(
            sb, "exec", return_value=("2 passed 1 failed in 0.5s", "", 0)
        ):
            passed, total = sb.run_tests("pytest")
            assert passed == 2
            assert total == 3

    def test_run_tests_rc0_no_output(self):
        sb = DockerSandbox()
        sb.container_id = "c123"
        with patch.object(sb, "exec", return_value=("", "", 0)):
            passed, total = sb.run_tests("pytest")
            assert passed == 1
            assert total == 1

    def test_run_tests_rc_nonzero_no_output(self):
        sb = DockerSandbox()
        sb.container_id = "c123"
        with patch.object(sb, "exec", return_value=("", "", 1)):
            passed, total = sb.run_tests("pytest")
            assert passed == 0
            assert total == 1

    def test_cleanup_with_container(self):
        sb = DockerSandbox()
        sb.container_id = "c123"
        sb._tmpdir = "/tmp/swebench_test"
        with (
            patch("mas_eval.oracle.swe_bench.subprocess.run") as mock_run,
            patch("mas_eval.oracle.swe_bench.os.path.exists", return_value=True),
            patch("mas_eval.oracle.swe_bench.shutil.rmtree") as mock_rm,
        ):
            mock_result = MagicMock(returncode=0, stdout="", stderr="")
            mock_run.return_value = mock_result
            sb.cleanup()
            assert sb.container_id is None
            assert sb._tmpdir is None
            mock_run.assert_called_once()
            mock_rm.assert_called_once()

    def test_cleanup_skip_if_no_container(self):
        sb = DockerSandbox()
        sb.cleanup()

    def test_cleanup_docker_stop_exception(self):
        sb = DockerSandbox()
        sb.container_id = "c123"
        with patch("mas_eval.oracle.swe_bench.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("docker stop", 15)
            sb.cleanup()
        assert sb.container_id is None


class TestSWEBenchOracleEdgeCases:
    def setup_method(self):
        self.oracle = SWEBenchOracle()

    def test_validate_env_file_missing(self):
        with patch("mas_eval.oracle.swe_bench.TASKS_FILE") as mock_file:
            mock_file.exists.return_value = False
            mock_file.name = "swe_bench_tasks.json"
            ok, msg = self.oracle.validate_environment()
            assert ok is False
            assert "not found" in msg

    def test_validate_env_docker_available(self):
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.name = "swe_bench_tasks.json"
        with (
            patch("mas_eval.oracle.swe_bench.TASKS_FILE", mock_file),
            patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
        ):
            ok, msg = self.oracle.validate_environment()
            assert ok is True
            assert "Docker available" in msg

    def test_load_tasks_file_missing(self):
        with patch("mas_eval.oracle.swe_bench.TASKS_FILE") as mock_file:
            mock_file.exists.return_value = False
            self.oracle._tasks_cache = None
            tasks = self.oracle._load_tasks()
            assert tasks == []

    def test_find_task_returns_none(self):
        result = self.oracle._find_task("nonexistent")
        assert result is None

    def test_score_docker_path_uses_real_score(self):
        with patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")):
            with patch.object(
                self.oracle, "_real_score", return_value=85.0
            ) as mock_real:
                task = self.oracle.list_tasks()[0]
                score = self.oracle.score(task, CORRECT_TRAJECTORY)
                assert score == 85.0
                mock_real.assert_called_once()

    def test_real_score_no_task_data(self):
        with patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")):
            from mas_eval.oracle.oracle_base import OracleTask

            task = OracleTask(task_id="nonexistent", prompt="test")
            score = self.oracle._real_score(task, [("x.py", "content")])
            assert score == 0.0

    def test_real_score_falls_back_on_sandbox_failure(self):
        with (
            patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
            patch.object(self.oracle, "_simulate_score", return_value=30.0),
        ):
            task = self.oracle.list_tasks()[0]
            score = self.oracle._real_score(task, [("src/flask/app.py", "content")])
            assert score == 30.0

    def test_real_score_exception_triggers_simulate(self):
        with (
            patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
            patch.object(self.oracle, "_simulate_score", return_value=25.0) as mock_sim,
            patch("mas_eval.oracle.swe_bench.DockerSandbox") as mock_sb_cls,
        ):
            mock_sb = MagicMock()
            mock_sb.start.side_effect = Exception("Boom")
            mock_sb_cls.return_value = mock_sb
            task = self.oracle.list_tasks()[0]
            score = self.oracle._real_score(task, [("src/flask/app.py", "content")])
            assert score == 25.0
            mock_sim.assert_called_once()

    def test_real_score_successful_run(self):
        with (
            patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
            patch("mas_eval.oracle.swe_bench.DockerSandbox") as mock_sb_cls,
        ):
            mock_sb = MagicMock()
            mock_sb.start.return_value = True
            mock_sb.run_tests.return_value = (4, 5)
            mock_sb_cls.return_value = mock_sb
            task = self.oracle.list_tasks()[0]
            score = self.oracle._real_score(task, [("src/flask/app.py", "content")])
            assert score == 80.0
            mock_sb.write_file.assert_called_once()
            mock_sb.run_tests.assert_called_once()
            mock_sb.cleanup.assert_called_once()

    def test_simulate_score_high_sim(self):
        """Cover 0.7 <= best_sim < 0.9 branch (line 276)."""
        task = self.oracle.list_tasks()[0]
        content = "return render_template('not_found.html'), 404"
        score = self.oracle._simulate_score(task, [("src/flask/app.py", content)])
        assert score == 68.0 or 60.0 <= score < 95.0

    def test_simulate_score_wrong_path_few_edits(self):
        task = self.oracle.list_tasks()[0]
        score = self.oracle._simulate_score(task, [("src/other.py", "content")])
        assert score == 10.0

    def test_simulate_score_wrong_path_many_edits(self):
        task = self.oracle.list_tasks()[0]
        edits = [("src/other1.py", "a"), ("src/other2.py", "b"), ("src/other3.py", "c")]
        score = self.oracle._simulate_score(task, edits)
        assert score == 30.0
