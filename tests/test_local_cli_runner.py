# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Local CLI runner tests (no model calls)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from mas_eval.evidence import (
    EVIDENCE_MODE_LIVE,
    resolve_evidence_mode,
)
from mas_eval.runner.local_cli import LocalCLIRunner


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "test_calc.py").write_text(
        "from calc import add\nassert add(1, 2) == 3\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


def test_runner_collects_patch_and_record(tmp_path):
    repo = _repo(tmp_path)
    fix = "import pathlib; pathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')"
    runner = LocalCLIRunner("fake-agent", [sys.executable, "-c", fix])

    result = runner.run("fix the bug", repo, "task-1")

    assert "diff --git a/calc.py b/calc.py" in result.patch
    assert "+    return a + b" in result.patch
    assert result.record.runner_id == "fake-agent"
    assert result.record.task_id == "task-1"
    assert result.record.exit_code == 0
    assert result.record.is_complete() is True
    assert result.timed_out is False


def test_runner_record_supports_live_run(tmp_path):
    repo = _repo(tmp_path)
    fix = "import pathlib; pathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')"
    runner = LocalCLIRunner("fake-agent", [sys.executable, "-c", fix])

    result = runner.run("fix", repo, "task-1")

    assert resolve_evidence_mode(EVIDENCE_MODE_LIVE, result.record) == EVIDENCE_MODE_LIVE


def test_scripted_runner_cannot_claim_live_run(tmp_path):
    repo = _repo(tmp_path)
    runner = LocalCLIRunner(
        "fixture", [sys.executable, "-c", "pass"], runner_kind="scripted"
    )

    result = runner.run("fix", repo, "task-1")

    with pytest.raises(ValueError, match="runner_kind='agent'"):
        resolve_evidence_mode(EVIDENCE_MODE_LIVE, result.record)


def test_runner_handles_timeout(tmp_path):
    repo = _repo(tmp_path)
    runner = LocalCLIRunner(
        "slow", [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout_seconds=1,
    )

    result = runner.run("fix", repo, "task-1")

    assert result.timed_out is True
    assert result.record.exit_code == 124


def test_empty_command_rejected():
    with pytest.raises(ValueError, match="command"):
        LocalCLIRunner("x", [])


def test_filter_patch_drops_symlinks_and_bytecode():
    patch = (
        "diff --git a/calc.py b/calc.py\n--- a/calc.py\n+++ b/calc.py\n"
        "@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/.venvpython b/.venvpython\nnew file mode 120000\n"
        "--- /dev/null\n+++ b/.venvpython\n@@ -0,0 +1 @@\n+/host/python\n"
        "diff --git a/__pycache__/x.pyc b/__pycache__/x.pyc\n"
        "new file mode 100644\n--- /dev/null\n+++ b/__pycache__/x.pyc\n"
    )
    filtered = LocalCLIRunner._filter_patch(patch)
    assert "calc.py" in filtered
    assert ".venvpython" not in filtered
    assert "__pycache__" not in filtered
