#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Batch-run a local CLI agent over SWE-bench Lite instances.

Each instance: prepare repo -> agent edit -> patch -> official image verify ->
JSONL row with ExecutionRecord and evidence_mode. Results are written
incrementally so an interrupted run keeps completed rows.

Usage:
    python scripts/swebench_batch.py \
      --dataset /path/to/lite-astropy.json \
      --repo astropy/astropy \
      --output /path/to/results.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
import tempfile
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

DEFAULT_AGENT = (
    "claude -p --bare --permission-mode acceptEdits "
    "--max-budget-usd 1.00 --output-format json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch SWE-bench Lite agent runs")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--repo", default="astropy/astropy")
    parser.add_argument("--instances", help="Comma-separated instance ids")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--agent-cmd", default=DEFAULT_AGENT)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Independent agent runs per instance (repeated sampling)",
    )
    parser.add_argument(
        "--artifacts",
        help="Directory to keep each instance's model patch (for later diagnosis)",
    )
    parser.add_argument("--keep", action="store_true")
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
    if args.instances:
        wanted = {x.strip() for x in args.instances.split(",") if x.strip()}
        tasks = [t for t in tasks if t["task_id"] in wanted]
    else:
        tasks = [t for t in tasks if t["repo"] == args.repo]
    if args.limit:
        tasks = tasks[: args.limit]

    if not tasks:
        print("no instances selected", file=sys.stderr)
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("", encoding="utf-8")

    artifacts = Path(args.artifacts) if args.artifacts else None
    if artifacts:
        artifacts.mkdir(parents=True, exist_ok=True)

    oracle = SWEBenchOracle()
    runner = LocalCLIRunner(
        "local-cli-agent", shlex.split(args.agent_cmd), timeout_seconds=args.timeout
    )

    results = []
    plan = [(task, rep) for task in tasks for rep in range(1, args.repeat + 1)]
    total = len(plan)
    for index, (task, rep) in enumerate(plan, 1):
        instance_id = task["task_id"]
        label = f"{instance_id}" + (f" r{rep}" if args.repeat > 1 else "")
        workdir = Path(tempfile.mkdtemp(prefix="swebench-batch-"))
        started = time.time()
        row = {
            "instance_id": instance_id,
            "rep": rep,
            "repo": task["repo"],
            "resolved": False,
            "evidence_mode": EVIDENCE_MODE_DECLARED,
            "error": "",
        }
        try:
            print(f"[{index}/{total}] {label}: preparing repo ...", flush=True)
            prepare_repo(task["repo"], task["base_commit"], workdir)

            prompt = (
                "You are solving a GitHub issue in the current repository.\n"
                f"Issue:\n{task['problem_statement']}\n\n"
                "Edit the repository to fix the issue. Do not modify tests. "
                "Keep the change minimal. Do not commit."
            )
            run_result = runner.run(prompt, workdir, instance_id)
            print(
                f"[{index}/{total}] {label}: agent exit={run_result.record.exit_code} "
                f"{run_result.duration_s}s patch={len(run_result.patch)}B",
                flush=True,
            )

            verification = oracle.verify_instance(instance_id, run_result.patch)
            if artifacts:
                name = (
                    f"{instance_id}.patch"
                    if args.repeat == 1
                    else f"{instance_id}__r{rep}.patch"
                )
                (artifacts / name).write_text(run_result.patch, encoding="utf-8")
            evidence_mode = EVIDENCE_MODE_DECLARED
            if verification.get("evidence_mode") == EVIDENCE_MODE_VERIFIED_PATCH:
                try:
                    evidence_mode = resolve_evidence_mode(
                        EVIDENCE_MODE_LIVE, run_result.record
                    )
                except ValueError:
                    evidence_mode = EVIDENCE_MODE_VERIFIED_PATCH

            row.update(
                {
                    "resolved": bool(verification.get("resolved")),
                    "evidence_mode": evidence_mode,
                    "execution_record": run_result.record.__dict__,
                    "verification": {
                        "passed": verification.get("passed"),
                        "failed": verification.get("failed"),
                        "total": verification.get("total"),
                        "duration_s": verification.get("duration_s"),
                        "error": verification.get("error", ""),
                    },
                    "agent_duration_s": run_result.duration_s,
                    "patch_bytes": len(run_result.patch),
                    "output_tail": (verification.get("output_tail") or "")[-500:],
                }
            )
        except Exception as exc:  # keep the batch alive
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"[{index}/{total}] {label}: ERROR {row['error']}", flush=True)
        finally:
            if not args.keep:
                shutil.rmtree(workdir, ignore_errors=True)

        row["wall_seconds"] = round(time.time() - started, 1)
        results.append(row)
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(
            f"[{index}/{total}] {label}: resolved={row['resolved']} "
            f"evidence={row['evidence_mode']} {row['wall_seconds']}s",
            flush=True,
        )

    resolved = sum(1 for r in results if r["resolved"])
    live = sum(1 for r in results if r["evidence_mode"] == EVIDENCE_MODE_LIVE)
    print("\n=== summary ===")
    print(f"runs:      {len(results)}")
    print(f"resolved:  {resolved}/{len(results)}")
    print(f"live_run:  {live}/{len(results)}")
    if args.repeat > 1:
        print("\n=== per instance ===")
        print("| instance | resolved | runs |")
        for task in tasks:
            runs = [r for r in results if r["instance_id"] == task["task_id"]]
            hits = sum(1 for r in runs if r["resolved"])
            print(f"| {task['task_id']} | {hits}/{len(runs)} | {len(runs)} |")
    print(f"results:   {output}")
    return 0 if resolved == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
