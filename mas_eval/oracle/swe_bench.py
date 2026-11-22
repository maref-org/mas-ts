# SPDX-FileCopyrightText: 2026 maref-org
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
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from difflib import SequenceMatcher
from pathlib import Path

from mas_eval.evidence import (
    EVIDENCE_MODE_DECLARED,
    EVIDENCE_MODE_VERIFIED_PATCH,
)
from mas_eval.oracle.env import check_docker as check_docker
from mas_eval.oracle.oracle_base import Oracle, OracleTask

logger = logging.getLogger(__name__)

TASKS_FILE = Path(__file__).parent / "data" / "swe_bench_tasks.json"

# Official SWE-bench images are published for linux/amd64 only. On arm64 hosts
# Docker must emulate them; set SWE_BENCH_DOCKER_PLATFORM="" to disable.
DEFAULT_PLATFORM = os.environ.get("SWE_BENCH_DOCKER_PLATFORM", "linux/amd64")
DEFAULT_TEST_TIMEOUT = int(os.environ.get("SWE_BENCH_TEST_TIMEOUT", "600"))
LITE_PATH_ENV = "SWE_BENCH_LITE_PATH"


def official_image_name(instance_id, namespace="swebench", tag="latest"):
    """Map an SWE-bench instance id to its official image name.

    ``astropy__astropy-12907`` -> ``swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest``
    (``1776`` is the official escape for ``__``, not a version.)
    """
    mapped = instance_id.replace("__", "_1776_")
    return f"{namespace}/sweb.eval.x86_64.{mapped}:{tag}"


def _as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _count(output, word):
    match = re.search(rf"(\d+)\s+{word}", output)
    return int(match.group(1)) if match else 0


def load_lite_tasks(path, namespace="swebench"):
    """Normalise official SWE-bench Lite rows into the oracle task schema.

    Accepted input: a JSON list of rows, or ``{"instances": [...]}``.
    The dataset itself is never stored in this repository; pass a local path
    via ``--dataset`` / ``SWE_BENCH_LITE_PATH``.
    """
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("instances", [])
    tasks = []
    for row in rows:
        instance_id = row["instance_id"]
        tasks.append(
            {
                "task_id": instance_id,
                "instance_id": instance_id,
                "problem_statement": row.get("problem_statement", ""),
                "repo": row.get("repo", ""),
                "version": row.get("version", ""),
                "base_commit": row.get("base_commit", ""),
                "image": row.get("image")
                or official_image_name(instance_id, namespace=namespace),
                "platform": row.get("platform", DEFAULT_PLATFORM),
                "workdir": row.get("workdir", "/testbed"),
                "test_patch": row.get("test_patch", ""),
                "gold_patch": row.get("patch", ""),
                "FAIL_TO_PASS": _as_list(row.get("FAIL_TO_PASS")),
                "PASS_TO_PASS": _as_list(row.get("PASS_TO_PASS")),
                "source": "swe-bench-lite",
                "setup_commands": [],
                "expected_tools": row.get("expected_tools", []),
            }
        )
    return tasks


class DockerSandbox:
    """Manages isolated Docker containers for SWE-bench task execution.

    Handles container lifecycle: start → exec → stop → cleanup.
    Gracefully degrades when Docker is unavailable.
    """

    def __init__(self, image="python:3.11-slim", platform=None):
        self.image = image
        self.platform = platform
        self.container_id = None
        self._tmpdir = None

    def start(self, task, workdir="/workspace"):
        """Start a container and prepare it for task execution."""
        docker_ok, _ = check_docker()
        if not docker_ok:
            logger.warning("Docker unavailable, sandbox start skipped")
            return False

        self._tmpdir = tempfile.mkdtemp(prefix="swebench_")
        image = task.get("image", self.image)
        platform = task.get("platform", self.platform)

        cmd = ["docker", "run", "--rm", "-d"]
        if platform:
            cmd += ["--platform", platform]
        cmd += [
            "--name",
            f"swebench_{os.getpid()}_{int(time.time() * 1000)}",
            "-w",
            workdir,
            image,
            "tail",
            "-f",
            "/dev/null",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                logger.error("Docker start failed: %s", result.stderr)
                return False
            self.container_id = result.stdout.strip()

            for cmd_str in task.get("setup_commands", []):
                self.exec(cmd_str)
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

    def exec_shell(self, command, timeout=60):
        """Run a shell command (supports &&, source, quoting) in the container."""
        if not self.container_id:
            logger.warning("No active container")
            return "", "no active container", 1
        try:
            result = subprocess.run(
                ["docker", "exec", self.container_id, "bash", "-lc", command],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout, result.stderr, result.returncode
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.error("Docker exec_shell error: %s", e)
            return "", str(e), 1

    def write_file(self, path, content, suffix=".py"):
        """Write content to a file inside the container using docker cp."""
        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=suffix)
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

    def apply_patch(self, patch_text, cwd="/testbed"):
        """Apply a unified diff inside the container.

        Returns (ok, detail). Tries ``git apply`` first, then ``patch -p1``.
        """
        if not patch_text.strip():
            return True, "empty patch (no-op)"
        _, err, rc = self.write_file("/tmp/model.patch", patch_text, suffix=".patch")
        if rc != 0:
            return False, f"write failed: {err}"

        cmds = [
            f"cd {shlex.quote(cwd)} && git apply --whitespace=nowarn /tmp/model.patch",
            f"cd {shlex.quote(cwd)} && patch -p1 --batch --forward < /tmp/model.patch",
        ]
        last_err = ""
        for cmd in cmds:
            _, err, rc = self.exec_shell(cmd)
            if rc == 0:
                return True, cmd
            last_err = err
        return False, last_err[-400:]

    def run_pytest(self, test_ids, cwd="/testbed", timeout=DEFAULT_TEST_TIMEOUT):
        """Run pytest on explicit test ids; return (passed, failed, total, output).

        Uses the image's conda env (``testbed``), matching the official harness.
        """
        if not test_ids:
            return 0, 0, 0, ""
        quoted = " ".join(shlex.quote(t) for t in test_ids)
        command = (
            "source /opt/miniconda3/etc/profile.d/conda.sh && "
            f"conda activate testbed && cd {shlex.quote(cwd)} && "
            f"python -m pytest -q {quoted}"
        )
        stdout, stderr, rc = self.exec_shell(command, timeout=timeout)
        output = (stdout or "") + (stderr or "")
        passed = _count(output, "passed")
        failed = _count(output, "failed")
        errors = _count(output, "error")
        total = len(test_ids)
        if passed == 0 and failed == 0 and errors == 0:
            # pytest crashed before reporting; treat as one failure
            failed = 1 if rc != 0 else 0
        return passed, failed + errors, total, output

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
        self._last_evidence_mode = EVIDENCE_MODE_DECLARED

    @property
    def name(self):
        return "swe-bench"

    def evidence_mode(self):
        """``verified_patch`` only when Docker actually ran the tests."""
        return self._last_evidence_mode

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
        if match.get("source") == "swe-bench-lite":
            # Golden trajectory for official tasks: the reference patch.
            return {
                "events": [
                    {
                        "action": {
                            "type": "apply_patch",
                            "input": {"patch": match.get("gold_patch", "")},
                        }
                    }
                ]
            }
        return match.get("golden_trajectory", {"events": []})

    def validate_environment(self):
        lite_path = os.environ.get(LITE_PATH_ENV)
        if lite_path:
            if not Path(lite_path).exists():
                return False, f"{LITE_PATH_ENV} points to a missing file"
            docker_ok, docker_msg = check_docker()
            tasks = self._load_tasks()
            if not docker_ok:
                return False, f"Docker unavailable: {docker_msg}"
            return True, f"{len(tasks)} official instances loaded, {docker_msg}"
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

        # Reset per call: a simulated fallback must not inherit a previous
        # verified_patch claim.
        self._last_evidence_mode = EVIDENCE_MODE_DECLARED

        task_data = self._find_task(task.task_id)
        if task_data is not None and task_data.get("source") == "swe-bench-lite":
            model_patch = self._extract_model_patch(agent_trajectory)
            if not model_patch:
                return 0.0
            result = self._verify_official(task_data, model_patch)
            return 100.0 if result["resolved"] else 0.0

        edits = self._extract_edits(agent_trajectory)
        if not edits:
            return 0.0

        docker_ok, _ = check_docker()
        if docker_ok:
            return self._real_score(task, edits)
        return self._simulate_score(task, edits)

    @staticmethod
    def _extract_model_patch(trajectory):
        """Extract a unified diff from a trajectory.

        Accepted shapes: ``{"model_patch": "..."}`` or an event with
        ``action.type == "apply_patch"`` and ``action.input.patch``.
        """
        if isinstance(trajectory, dict):
            if isinstance(trajectory.get("model_patch"), str):
                return trajectory["model_patch"]
            events = trajectory.get("events", [])
        else:
            events = trajectory or []
        for event in events:
            action = event.get("action", {})
            if action.get("type") == "apply_patch":
                patch = action.get("input", {}).get("patch", "")
                if isinstance(patch, str):
                    return patch
        return None

    def verify_instance(self, instance_id, model_patch):
        """Verify a unified diff against one official SWE-bench Lite instance."""
        task_data = self._find_task(instance_id)
        if task_data is None:
            raise ValueError(f"Instance {instance_id!r} not found in loaded tasks")
        if task_data.get("source") != "swe-bench-lite":
            raise ValueError(f"Instance {instance_id!r} is not an official Lite task")
        return self._verify_official(task_data, model_patch)

    def _verify_official(self, task_data, model_patch):
        """Run the official image: model patch -> test patch -> pytest."""
        self._last_evidence_mode = EVIDENCE_MODE_DECLARED
        instance_id = task_data.get("instance_id", task_data.get("task_id", "?"))
        workdir = task_data.get("workdir", "/testbed")
        tests = list(task_data.get("FAIL_TO_PASS", [])) + list(
            task_data.get("PASS_TO_PASS", [])
        )
        start = time.time()

        docker_ok, docker_msg = check_docker()
        if not docker_ok:
            return self._official_result(
                instance_id, False, 0, 0, len(tests), f"docker unavailable: {docker_msg}"
            )

        sandbox = DockerSandbox(
            image=task_data.get("image", "python:3.11-slim"),
            platform=task_data.get("platform"),
        )
        try:
            if not sandbox.start(task_data, workdir=workdir):
                return self._official_result(
                    instance_id, False, 0, 0, len(tests), "sandbox_start_failed"
                )

            if model_patch:
                ok, detail = sandbox.apply_patch(model_patch, cwd=workdir)
                if not ok:
                    return self._official_result(
                        instance_id,
                        False,
                        0,
                        0,
                        len(tests),
                        f"model_patch_apply_failed: {detail}",
                    )

            if task_data.get("test_patch"):
                ok, detail = sandbox.apply_patch(task_data["test_patch"], cwd=workdir)
                if not ok:
                    return self._official_result(
                        instance_id,
                        False,
                        0,
                        0,
                        len(tests),
                        f"test_patch_apply_failed: {detail}",
                    )

            passed, failed, total, output = sandbox.run_pytest(tests, cwd=workdir)
            self._last_evidence_mode = EVIDENCE_MODE_VERIFIED_PATCH
            resolved = failed == 0 and total > 0 and passed >= total
            result = self._official_result(
                instance_id, resolved, passed, failed, total, ""
            )
            result["duration_s"] = round(time.time() - start, 1)
            result["output_tail"] = output[-2000:]
            return result
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Official verification failed: %s", e)
            return self._official_result(
                instance_id, False, 0, 0, len(tests), f"exception: {e}"
            )
        finally:
            sandbox.cleanup()

    @staticmethod
    def _official_result(instance_id, resolved, passed, failed, total, error):
        return {
            "instance_id": instance_id,
            "resolved": resolved,
            "passed": passed,
            "failed": failed,
            "total": total,
            "evidence_mode": (
                EVIDENCE_MODE_VERIFIED_PATCH
                if passed + failed > 0
                else EVIDENCE_MODE_DECLARED
            ),
            "error": error,
        }

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
            if total > 0:
                self._last_evidence_mode = EVIDENCE_MODE_VERIFIED_PATCH
                return round(passed / total * 100, 1)
            return self._simulate_score(task, edits)
        except Exception as e:
            logger.error("Real scoring failed: %s", e)
            return self._simulate_score(task, edits)
        finally:
            sandbox.cleanup()

    def _simulate_score(self, task, edits):
        """Score based on patch similarity when Docker is unavailable."""
        self._last_evidence_mode = EVIDENCE_MODE_DECLARED
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
        lite_path = os.environ.get(LITE_PATH_ENV)
        if lite_path:
            self._tasks_cache = load_lite_tasks(lite_path)
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
