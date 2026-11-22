#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Run a local CLI agent on one official SWE-bench Lite instance (A).

Flow:
    base repo -> local agent edits -> patch -> official image verification
              -> ExecutionRecord + evidence_mode

The dataset and the repository clone stay outside this repo.

Usage:
    python scripts/swebench_live_run.py \
      --dataset /path/to/lite-astropy.json \
      --instance astropy__astropy-12907 \
      --agent-cmd "claude -p --bare --permission-mode acceptEdits --max-budget-usd 1.00"

Exit codes: 0 resolved, 1 not resolved / error.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

DEFAULT_AGENT = (
    "claude -p --bare --permission-mode acceptEdits "
    "--max-budget-usd 1.00 --output-format json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local CLI agent on SWE-bench Lite")
    parser.add_argument("--dataset", required=True, help="Local JSON list of instances")
    parser.add_argument("--instance", required=True)
    parser.add_argument(
        "--agent-cmd",
        default=DEFAULT_AGENT,
        help="Agent command prefix; the prompt is appended as the last argument",
    )
    parser.add_argument("--timeout", type=int, default=600, help="Agent timeout (s)")
    parser.add_argument("--workdir", help="Keep the repo clone here")
    parser.add_argument("--keep", action="store_true", help="Do not delete the temp clone")
    args = parser.parse_args(argv)

    os.environ["SWE_BENCH_LITE_PATH"] = args.dataset

    from mas_eval.evidence import (
        EVIDENCE_MODE_DECLARED,
        EVIDENCE_MODE_LIVE,
        EVIDENCE_MODE_VERIFIED_PATCH,
        resolve_evidence_mode,
    )
    from mas_eval.oracle.swe_bench import SWEBenchOracle, load_lite_tasks
    from mas_eval.runner.local_cli import LocalCLIRunner
    from mas_eval.runner.repo import prepare_repo

    tasks = load_lite_tasks(args.dataset)
    task = next((t for t in tasks if t["task_id"] == args.instance), None)
    if task is None:
        print(f"instance not found: {args.instance}", file=sys.stderr)
        return 1

    workdir = Path(args.workdir) if args.workdir else Path(
        tempfile.mkdtemp(prefix="swebench-agent-")
    )
    try:
        print(f"instance: {args.instance}")
        print(f"repo:     {task['repo']} @ {task['base_commit'][:12]}")
        print(f"workdir:  {workdir}")
        prepare_repo(task["repo"], task["base_commit"], workdir)

        prompt = (
            "You are solving a GitHub issue in the current repository.\n"
            f"Issue:\n{task['problem_statement']}\n\n"
            "Edit the repository to fix the issue. Do not modify tests. "
            "Keep the change minimal. Do not commit."
        )
        runner = LocalCLIRunner(
            "local-cli-agent",
            shlex.split(args.agent_cmd),
            timeout_seconds=args.timeout,
        )
        run_result = runner.run(prompt, workdir, args.instance)
        print(
            f"agent:    exit={run_result.record.exit_code} "
            f"duration={run_result.duration_s}s timed_out={run_result.timed_out}"
        )
        print(f"patch:    {len(run_result.patch)} bytes")

        verification = SWEBenchOracle().verify_instance(args.instance, run_result.patch)

        evidence_mode = EVIDENCE_MODE_DECLARED
        if verification.get("evidence_mode") == EVIDENCE_MODE_VERIFIED_PATCH:
            try:
                evidence_mode = resolve_evidence_mode(
                    EVIDENCE_MODE_LIVE, run_result.record
                )
            except ValueError:
                evidence_mode = EVIDENCE_MODE_VERIFIED_PATCH

        output = {
            "instance_id": args.instance,
            "resolved": verification.get("resolved", False),
            "evidence_mode": evidence_mode,
            "execution_record": run_result.record.__dict__,
            "verification": verification,
            "agent_log_tail": run_result.log[-1500:],
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0 if verification.get("resolved") else 1
    finally:
        if not args.keep and not args.workdir:
            subprocess.run(["rm", "-rf", str(workdir)], capture_output=True)


if __name__ == "__main__":
    sys.exit(main())
