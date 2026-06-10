# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS-001 v3.0 — SWE-bench Oracle.

Executable benchmark for software engineering task completion.
Evaluates agent-generated code patches by running actual test suites
in isolated Docker sandboxes.

Usage:
    from mas_eval.oracle.swe_bench import SWEBenchOracle
    OracleRegistry.register(SWEBenchOracle())
    result = run_d2_with_oracle(card, "swe-bench", "swe-bench-flask-001")
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from difflib import SequenceMatcher
from pathlib import Path

from mas_eval.oracle.env import check_docker
from mas_eval.oracle.oracle_base import Oracle, OracleTask

logger = logging.getLogger(__name__)

TASKS_FILE = Path(__file__).parent / "data" / "swe_bench_tasks.json"


class DockerSandbox:
    """Manages isolated Docker containers for SWE-bench task execution.

    Handles container lifecycle: start → exec → stop → cleanup.
    Gracefully degrades when Docker is unavailable.
    """

    def __init__(self, image="python:3.11-slim"):
        self.image = image
        self.container_id = None
        self._tmpdir = None

    def start(self, task, workdir="/workspace"):
        """Start a container and prepare it for task execution."""
        docker_ok, _ = check_docker()
        if not docker_ok:
            logger.warning("Docker unavailable, sandbox start skipped")
            return False

        self._tmpdir = tempfile.mkdtemp(prefix="swebench_")

        try:
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-d",
                    "--name",
                    f"swebench_{int(time.time())}",
                    "-w",
                    workdir,
                    self.image,
                    "tail",
                    "-f",
                    "/dev/null",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.error("Docker start failed: %s", result.stderr)
                return False
            self.container_id = result.stdout.strip()

            for cmd in task.get("setup_commands", []):
                self.exec(cmd)
            return True

        except (subprocess.TimeoutExpired, OSError) as e:
            logger.error("Docker start error: %s", e)
            return False

    def exec(self, command):
        """Run a command inside the container."""
        if not self.container_id:
            logger.warning("No active container")
            return "", "", 1

        try:
            result = subprocess.run(
                ["docker", "exec", self.container_id] + command.split(),
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.stdout, result.stderr, result.returncode
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.error("Docker exec error: %s", e)
            return "", str(e), 1

    def write_file(self, path, content):
        """Write content to a file inside the container using docker cp."""
        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py")
        try:
            tmp.write(content)
            tmp.close()
            result = subprocess.run(
                ["docker", "cp", tmp.name, f"{self.container_id}:{path}"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.stdout, result.stderr, result.returncode
        except (subprocess.TimeoutExpired, OSError) as e:
            return "", str(e), 1
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    def run_tests(self, test_command):
        """Execute test suite and return (passed, total)."""
        stdout, stderr, rc = self.exec(test_command)

        passed = 0
        total = 0
        for line in stdout.splitlines():
            if "passed" in line and "failed" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "passed":
                        passed = int(parts[i - 1]) if i > 0 else 0
                    if p == "failed":
                        total = passed + (int(parts[i - 1]) if i > 0 else 0)

        if total == 0 and rc == 0:
            passed = 1
            total = 1
        elif total == 0 and rc != 0:
            total = 1

        return passed, total

    def cleanup(self):
        """Stop and remove the container, clean up temp files."""
        if self.container_id:
            try:
                subprocess.run(
                    ["docker", "stop", self.container_id],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except (subprocess.TimeoutExpired, OSError):
                pass
            self.container_id = None

        if self._tmpdir and os.path.exists(self._tmpdir):
            shutil.rmtree(self._tmpdir, ignore_errors=True)
            self._tmpdir = None


class SWEBenchOracle(Oracle):
    """Executable benchmark for software engineering fix tasks.

    Evaluates agent patches via test execution in Docker sandboxes,
    falling back to patch similarity scoring when Docker is unavailable.
    """

    def __init__(self):
        self._tasks_cache = None

    @property
    def name(self):
        return "swe-bench"

    def list_tasks(self):
        return [
            OracleTask(
                task_id=t["task_id"],
                prompt=t["problem_statement"],
                expected_tools=t.get("expected_tools", []),
                rubric={},
                metadata={
                    "repo": t.get("repo", ""),
                    "file_path": t.get("file_path", ""),
                    "test_command": t.get("test_command", ""),
                },
            )
            for t in self._load_tasks()
        ]

    def execute(self, task, agent_card):
        tasks = self._load_tasks()
        match = next((t for t in tasks if t["task_id"] == task.task_id), None)
        if match is None:
            logger.warning("Task %r not found in swe-bench tasks", task.task_id)
            return {"events": []}
        return match.get("golden_trajectory", {"events": []})

    def validate_environment(self):
        if not TASKS_FILE.exists():
            return False, f"{TASKS_FILE.name} not found"
        docker_ok, docker_msg = check_docker()
        if docker_ok:
            return True, f"Docker available, {TASKS_FILE.name} loaded"
        tasks = self._load_tasks()
        return True, f"Docker unavailable (simulated mode), {len(tasks)} tasks loaded"

    def score(self, task, agent_trajectory, golden_trajectory=None):
        """SWE-bench scoring: resolve_rate via test execution or simulation.

        Returns resolve_rate * 100 (0-100).
        """
        if not agent_trajectory:
            return 0.0

        edits = self._extract_edits(agent_trajectory)
        if not edits:
            return 0.0

        docker_ok, _ = check_docker()
        if docker_ok:
            return self._real_score(task, edits)
        return self._simulate_score(task, edits)

    def _real_score(self, task, edits):
        """Execute agent's patches in Docker and compute resolve_rate."""
        task_data = self._find_task(task.task_id)
        if task_data is None:
            return 0.0

        sandbox = DockerSandbox()
        try:
            if not sandbox.start(task_data):
                return self._simulate_score(task, edits)

            for path, new_content in edits:
                sandbox.write_file(path, new_content)

            passed, total = sandbox.run_tests(task_data.get("test_command", "pytest"))
            return round(passed / total * 100, 1) if total > 0 else 0.0
        except Exception as e:
            logger.error("Real scoring failed: %s", e)
            return self._simulate_score(task, edits)
        finally:
            sandbox.cleanup()

    def _simulate_score(self, task, edits):
        """Score based on patch similarity when Docker is unavailable."""
        task_data = self._find_task(task.task_id)
        if task_data is None:
            return 0.0

        expected_path = task_data.get("file_path", "")
        expected_new = task_data.get("expected_new_str", "")
        expected_old = task_data.get("expected_old_str", "")

        matching_paths = sum(1 for p, _ in edits if p == expected_path)
        if matching_paths == 0:
            return round(30.0 * min(1.0, len(edits) / 3), 1)

        best_sim = 0.0
        for path, content in edits:
            if path == expected_path:
                old_sim = SequenceMatcher(None, content, expected_old).ratio()
                new_sim = SequenceMatcher(None, content, expected_new).ratio()
                best_sim = max(best_sim, old_sim, new_sim)

        if best_sim >= 0.9:
            return 95.0
        elif best_sim >= 0.7:
            return round(60.0 + (best_sim - 0.7) / 0.2 * 30.0, 1)
        elif best_sim >= 0.4:
            return round(30.0 + (best_sim - 0.4) / 0.3 * 30.0, 1)
        else:
            return round(best_sim * 30.0, 1)

    def _find_task(self, task_id):
        tasks = self._load_tasks()
        return next((t for t in tasks if t["task_id"] == task_id), None)

    def _load_tasks(self):
        if self._tasks_cache is not None:
            return self._tasks_cache
        if not TASKS_FILE.exists():
            logger.warning("Tasks file not found: %s", TASKS_FILE)
            self._tasks_cache = []
            return self._tasks_cache
        with open(TASKS_FILE) as f:
            self._tasks_cache = json.load(f)
        return self._tasks_cache

    @staticmethod
    def _extract_edits(trajectory):
        """Extract file_edit operations from a trajectory.

        Returns list of (file_path, new_content) tuples.
        """
        events = trajectory
        if isinstance(trajectory, dict):
            events = trajectory.get("events", [])

        edits = []
        for event in events:
            action = event.get("action", {})
            if action.get("type") == "file_edit":
                path = action.get("input", {}).get("path", "")
                new_str = action.get("input", {}).get("new_str", "")
                if path:
                    edits.append((path, new_str))
            elif action.get("type") == "file_write":
                path = action.get("input", {}).get("path", "")
                content = action.get("input", {}).get("content", "")
                if path:
                    edits.append((path, content))
        return edits
