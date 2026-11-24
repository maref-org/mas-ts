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
    parser.add_argument(
        "--prompt-append-file",
        help="File with extra instructions appended to the baseline solver prompt",
    )
    args = parser.parse_args(argv)

    os.environ["SWE_BENCH_LITE_PATH"] = args.dataset

    from mas_eval.oracle.swe_bench import SWEBenchOracle, load_lite_tasks
    from mas_eval.runner.evidence_upgrade import upgrade_evidence_mode
    from mas_eval.runner.local_cli import LocalCLIRunner
    from mas_eval.runner.prompt import build_prompt, prompt_sha256
    from mas_eval.runner.provenance import runner_metadata
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

        prompt_append = ""
        if args.prompt_append_file:
            prompt_append = Path(args.prompt_append_file).read_text(encoding="utf-8")
        prompt = build_prompt(task["problem_statement"], append=prompt_append)
        prompt_sha = prompt_sha256(prompt)
        runner_meta = runner_metadata(args.agent_cmd, args.timeout, "default")

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

        evidence_mode, downgrade_reason = upgrade_evidence_mode(verification, run_result.record)

        if downgrade_reason:
            print(f"WARNING: evidence downgraded: {downgrade_reason}", file=sys.stderr)

        output = {
            "instance_id": args.instance,
            "resolved": verification.get("resolved", False),
            "evidence_mode": evidence_mode,
            "execution_record": run_result.record.__dict__,
            "verification": verification,
            "agent_log_tail": run_result.log[-1500:],
            "prompt_sha256": prompt_sha,
            "prompt_label": "default",
            "runner": runner_meta,
        }
        if downgrade_reason:
            output["evidence_downgrade_reason"] = downgrade_reason

        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0 if verification.get("resolved") else 1
    finally:
        if not args.keep and not args.workdir:
            subprocess.run(["rm", "-rf", str(workdir)], capture_output=True)


if __name__ == "__main__":
    sys.exit(main())
