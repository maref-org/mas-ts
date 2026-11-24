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

PREFLIGHT_PROMPT = "Reply OK"
PREFLIGHT_TIMEOUT_SECONDS = 90

# Outcomes that mean "the run was stopped by a cap" — reported per row so a
# silent cap is visible, and still counted as spend because tokens were burned.
_ABORT_OUTCOMES = ("max_turns", "max_budget")

# Fixed order for the summary line.
_OUTCOMES = ("ok", "max_turns", "max_budget", "api_error", "error", "unknown")


def _parse_env(pairs: list[str] | None) -> dict[str, str]:
    """Turn repeated ``KEY=VALUE`` flags into a dict for the child process."""
    env: dict[str, str] = {}
    for raw in pairs or []:
        key, sep, value = raw.partition("=")
        if not sep or not key:
            raise SystemExit(f"--env expects KEY=VALUE, got {raw!r}")
        env[key] = value
    return env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch SWE-bench Lite agent runs")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--repo", default="astropy/astropy")
    parser.add_argument("--instances", help="Comma-separated instance ids")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--agent-cmd", default=DEFAULT_AGENT)
    parser.add_argument(
        "--env",
        action="append",
        metavar="KEY=VALUE",
        help="Environment variable for the agent process (repeatable)",
    )
    parser.add_argument(
        "--preflight",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Probe the agent once and abort unless its cost is measurable",
    )
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
    parser.add_argument(
        "--prompt-append-file",
        help=(
            "File with extra instructions appended to the baseline solver prompt "
            "(prompt experiments; the baseline text itself is unchanged)"
        ),
    )
    parser.add_argument(
        "--prompt-label",
        default="default",
        help="Label recorded on every row to identify the prompt variant",
    )
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)

    prompt_append = ""
    if args.prompt_append_file:
        prompt_append = Path(args.prompt_append_file).read_text(encoding="utf-8")

    os.environ["SWE_BENCH_LITE_PATH"] = args.dataset

    from mas_eval.evidence import (
        EVIDENCE_MODE_DECLARED,
        EVIDENCE_MODE_LIVE,
        EVIDENCE_MODE_VERIFIED_PATCH,
        resolve_evidence_mode,
    )
    from mas_eval.oracle.swe_bench import SWEBenchOracle, load_lite_tasks
    from mas_eval.runner.local_cli import LocalCLIRunner
    from mas_eval.runner.prompt import build_prompt, prompt_sha256
    from mas_eval.runner.repo import prepare_repo
    from mas_eval.runner.usage import parse_claude_usage, usage_is_trusted

    child_env = _parse_env(args.env)
    usage_parser = parse_claude_usage if "claude" in args.agent_cmd else None

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

    if args.preflight:
        # A dead API still reports subtype="success" with cost 0, so an
        # unverified batch yields N fake zeros. Probe once, abort cheaply.
        probe_dir = Path(tempfile.mkdtemp(prefix="swebench-preflight-"))
        try:
            probe = LocalCLIRunner(
                "preflight",
                shlex.split(args.agent_cmd),
                timeout_seconds=PREFLIGHT_TIMEOUT_SECONDS,
                usage_parser=usage_parser,
                env=child_env or None,
            ).run(PREFLIGHT_PROMPT, probe_dir, "preflight")
        finally:
            shutil.rmtree(probe_dir, ignore_errors=True)
        if not usage_is_trusted(probe.usage):
            usage = probe.usage or {}
            reason = usage.get("untrusted_reason") or "unparsed_usage"
            head = usage.get("result_head", "")
            print(
                f"preflight FAILED: cost not measurable ({reason})", file=sys.stderr
            )
            if head:
                print(f"preflight result_head: {head}", file=sys.stderr)
            print(
                "refusing to run instances: cost would be unknown, not zero",
                file=sys.stderr,
            )
            return 2
        assert probe.usage is not None
        print(
            f"preflight ok cost=${probe.usage['total_cost_usd']} "
            f"tokens={probe.usage['input_tokens']}+{probe.usage['output_tokens']}",
            flush=True,
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("", encoding="utf-8")

    # Variant fingerprint: the prompt *spec* (frozen template + this run's
    # append) built with an empty problem statement, so the id is identical
    # across instances and comparable between experiment runs. Per-row
    # prompt_sha256 below fingerprints the real, instance-specific prompt.
    prompt_spec_sha = prompt_sha256(build_prompt("", append=prompt_append))
    print(
        f"prompt: label={args.prompt_label} sha={prompt_spec_sha[:12]} "
        f"append_bytes={len(prompt_append.encode('utf-8'))}",
        flush=True,
    )

    artifacts = Path(args.artifacts) if args.artifacts else None
    if artifacts:
        artifacts.mkdir(parents=True, exist_ok=True)

    oracle = SWEBenchOracle()
    runner = LocalCLIRunner(
        "local-cli-agent",
        shlex.split(args.agent_cmd),
        timeout_seconds=args.timeout,
        usage_parser=usage_parser,
        env=child_env or None,
    )

    results = []
    plan = [(task, rep) for task in tasks for rep in range(1, args.repeat + 1)]
    total = len(plan)
    for index, (task, rep) in enumerate(plan, 1):
        instance_id = task["task_id"]
        label = f"{instance_id}" + (f" r{rep}" if args.repeat > 1 else "")
        workdir = Path(tempfile.mkdtemp(prefix="swebench-batch-"))
        started = time.time()
        prompt = build_prompt(task["problem_statement"], append=prompt_append)
        row = {
            "instance_id": instance_id,
            "rep": rep,
            "repo": task["repo"],
            "resolved": False,
            "evidence_mode": EVIDENCE_MODE_DECLARED,
            "error": "",
            "outcome": "unknown",
            "abort_reason": "",
            "usage": None,
            "prompt_label": args.prompt_label,
            "prompt_sha256": prompt_sha256(prompt),
        }
        try:
            print(f"[{index}/{total}] {label}: preparing repo ...", flush=True)
            prepare_repo(task["repo"], task["base_commit"], workdir)

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
                    "usage": run_result.usage,
                }
            )
        except Exception as exc:  # keep the batch alive
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"[{index}/{total}] {label}: ERROR {row['error']}", flush=True)
        finally:
            if not args.keep:
                shutil.rmtree(workdir, ignore_errors=True)

        row["wall_seconds"] = round(time.time() - started, 1)
        # Outcome is a result state, separate from whether the cost is
        # measurable: a run capped by --max-turns is an "abort" but still spent
        # tokens, so its cost stays in the ledger.
        usage = row.get("usage") or {}
        outcome = usage.get("outcome") or "unknown"
        row["outcome"] = outcome
        row["abort_reason"] = outcome if outcome in _ABORT_OUTCOMES else ""
        results.append(row)
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        abort_note = f" abort={row['abort_reason']}" if row["abort_reason"] else ""
        print(
            f"[{index}/{total}] {label}: resolved={row['resolved']} "
            f"evidence={row['evidence_mode']} {row['wall_seconds']}s{abort_note}",
            flush=True,
        )

    resolved = sum(1 for r in results if r["resolved"])
    live = sum(1 for r in results if r["evidence_mode"] == EVIDENCE_MODE_LIVE)
    measurable = [r["usage"] for r in results if usage_is_trusted(r["usage"])]
    unmeasurable_runs = len(results) - len(measurable)
    # Fail-closed: only measurable runs carry a cost, and a measurable run whose
    # cost is missing contributes nothing rather than a fake zero.
    total_cost = sum(
        u["total_cost_usd"] for u in measurable if u["total_cost_usd"] is not None
    )
    outcome_counts = {name: 0 for name in _OUTCOMES}
    for row in results:
        name = row.get("outcome") or "unknown"
        outcome_counts[name] = outcome_counts.get(name, 0) + 1
    print("\n=== summary ===")
    print(f"runs:      {len(results)}")
    print(f"resolved:  {resolved}/{len(results)}")
    print(f"live_run:  {live}/{len(results)}")
    print(
        "outcomes:  "
        + " ".join(f"{name}={outcome_counts.get(name, 0)}" for name in _OUTCOMES)
    )
    print(
        f"cost:      {total_cost:.4f} (trusted runs: {len(measurable)}/{len(results)})"
    )
    if unmeasurable_runs:
        print(f"unmeasurable: {unmeasurable_runs} (cost unknown, NOT zero)")
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
