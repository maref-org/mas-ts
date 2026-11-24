# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Local CLI agent runners.

A runner executes a real agent process in a working tree, collects the diff it
produced, and returns an :class:`ExecutionRecord`. Only a runner with
``runner_kind="agent"`` may later claim ``live_run``.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mas_eval.evidence import ExecutionRecord

__all__ = ["LocalCLIRunner", "RunnerResult"]

UsageParser = Callable[[str], dict[str, Any] | None]


@dataclass(frozen=True)
class RunnerResult:
    """Outcome of one agent run."""

    patch: str
    log: str
    record: ExecutionRecord
    duration_s: float
    timed_out: bool = False
    usage: dict[str, Any] | None = None


class LocalCLIRunner:
    """Run a local agent CLI and capture its diff.

    ``command`` is the argv prefix; the prompt is appended as the final
    argument. Example::

        LocalCLIRunner(
            "claude-code",
            ["claude", "-p", "--bare", "--permission-mode", "acceptEdits"],
        )
    """

    def __init__(
        self,
        runner_id: str,
        command: list[str],
        timeout_seconds: int = 600,
        runner_kind: str = "agent",
        usage_parser: UsageParser | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        if not command:
            raise ValueError("command must not be empty")
        self.runner_id = runner_id
        self.command = list(command)
        self.timeout_seconds = timeout_seconds
        self.runner_kind = runner_kind
        self.usage_parser = usage_parser
        self.env = dict(env) if env else None

    def _subprocess_env(self) -> dict[str, str] | None:
        """Child environment: inherited plus any explicitly injected vars."""
        if not self.env:
            return None
        return {**os.environ, **self.env}

    def run(self, prompt: str, repo_dir: str | Path, task_id: str) -> RunnerResult:
        """Execute the agent and return the produced patch plus its record."""
        start = datetime.now(timezone.utc)
        started_monotonic = time.monotonic()
        timed_out = False

        try:
            proc = subprocess.run(
                [*self.command, prompt],
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=self._subprocess_env(),
            )
            exit_code = proc.returncode
            log = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            log = f"timeout after {self.timeout_seconds}s: {exc}"
        except OSError as exc:
            exit_code = 127
            log = f"runner failed to start: {exc}"

        end = datetime.now(timezone.utc)
        duration = round(time.monotonic() - started_monotonic, 2)
        patch = self._collect_patch(Path(repo_dir))
        digest = hashlib.sha256(patch.encode("utf-8")).hexdigest()
        usage = self.usage_parser(log) if self.usage_parser else None

        record = ExecutionRecord(
            runner_id=self.runner_id,
            task_id=task_id,
            started_at=start.isoformat(),
            finished_at=end.isoformat(),
            exit_code=exit_code,
            trajectory_sha256=digest,
            runner_kind=self.runner_kind,
        )
        return RunnerResult(
            patch=patch,
            log=log,
            record=record,
            duration_s=duration,
            timed_out=timed_out,
            usage=usage,
        )

    @staticmethod
    def _collect_patch(repo_dir: Path) -> str:
        """Capture tracked + newly created text changes as a unified diff."""
        subprocess.run(
            ["git", "add", "-N", "."],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        diff = subprocess.run(
            ["git", "diff", "--no-color"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return LocalCLIRunner._filter_patch(diff.stdout or "")

    @staticmethod
    def _filter_patch(patch: str) -> str:
        """Drop environment noise from the captured diff.

        Symlinks (e.g. an agent linking a host interpreter into the worktree)
        and bytecode caches are not part of a solution and must not be fed to
        the official evaluator.
        """
        sections = re.split(r"(?m)(?=^diff --git )", patch)
        kept = []
        for section in sections:
            if not section.strip():
                continue
            if "new file mode 120000" in section:
                continue
            if "__pycache__" in section or ".pyc" in section.splitlines()[0]:
                continue
            kept.append(section)
        return "".join(kept)
