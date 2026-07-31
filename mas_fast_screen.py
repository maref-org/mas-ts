#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""
MAS-TS-001 Fast-Screen Runner
Usage:
  python mas_fast_screen.py --cards-dir ./mas_eval/data/sample_cards --block
  python mas_fast_screen.py --cards-dir ./agent_cards --policy mock_policy.yaml --block --output reports/fast_screen.json

Orchestrates the complete Fast-Screen pipeline:
  Stage 1: Layer 1 - Agent Card compliance scan (static audit)
  Stage 2: Layer 3 - Mock LLM action test (process logic only)
  Stage 3: Mock drift calibration (if golden trajectories available)
  Output: Traffic-light report, fail -> block commit
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import argcomplete
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from mas_eval import __version__ as VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

console = Console()


def run_stage(name, cmd, timeout=120):
    start = time.perf_counter()
    result = {
        "stage": name,
        "command": " ".join(cmd),
        "status": "UNKNOWN",
        "duration_ms": 0,
        "output": None,
        "error": None,
    }
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(__file__).parent),
        )
        elapsed = int((time.perf_counter() - start) * 1000)
        result["duration_ms"] = elapsed
        result["returncode"] = proc.returncode

        if proc.stdout:
            try:
                parsed = json.loads(proc.stdout)
                result["output"] = parsed
                if isinstance(parsed, dict) and "overall_passed" in parsed:
                    if not parsed["overall_passed"]:
                        result["status"] = "FAIL"
                        result["error"] = "overall_passed=false in output"
                    else:
                        result["status"] = "PASS"
                elif proc.returncode != 0:
                    result["status"] = "FAIL"
                    result["error"] = proc.stderr[:2000] if proc.stderr else None
                else:
                    result["status"] = "PASS"
            except json.JSONDecodeError:
                result["output"] = proc.stdout[:2000]
                if proc.returncode != 0:
                    result["status"] = "FAIL"
                    result["error"] = proc.stderr[:2000] if proc.stderr else None
                else:
                    result["status"] = "PASS"
        else:
            if proc.returncode != 0:
                result["status"] = "FAIL"
                result["error"] = proc.stderr[:2000] if proc.stderr else None
            else:
                result["status"] = "PASS"

    except subprocess.TimeoutExpired:
        elapsed = int((time.perf_counter() - start) * 1000)
        result["duration_ms"] = elapsed
        result["status"] = "TIMEOUT"
        result["error"] = f"Stage timed out after {timeout}s"
    except Exception as e:
        elapsed = int((time.perf_counter() - start) * 1000)
        result["duration_ms"] = elapsed
        result["status"] = "ERROR"
        result["error"] = str(e)

    return result


def run_compliance_scan(cards_dir, schema_path=None, block=False):
    cmd = [sys.executable, "compliance_scan.py", "--dir", cards_dir]
    if schema_path:
        cmd.extend(["--schema", schema_path])
    if block:
        cmd.append("--block")
    return run_stage("Layer 1: Compliance Scan", cmd, timeout=60)


def run_mock_llm_test(task_file, policy_path=None):
    cmd = [sys.executable, "mock_llm.py", "--task-file", task_file]
    if policy_path:
        cmd.extend(["--policy", policy_path])
    return run_stage("Layer 3: Mock LLM Action Test", cmd, timeout=60)


def run_mock_calibration(golden_dir, mock_dir, thresholds=None):
    cmd = [
        sys.executable,
        "mock_calibrate.py",
        "--golden-dir",
        golden_dir,
        "--mock-dir",
        mock_dir,
    ]
    if thresholds:
        if "sequence_similarity" in thresholds:
            cmd.extend(["--threshold-seq", str(thresholds["sequence_similarity"])])
        if "set_similarity" in thresholds:
            cmd.extend(["--threshold-set", str(thresholds["set_similarity"])])
        if "param_match_rate" in thresholds:
            cmd.extend(["--threshold-param", str(thresholds["param_match_rate"])])
    return run_stage("Mock Drift Calibration", cmd, timeout=60)


def determine_overall_status(stages):
    for stage in stages:
        if stage["status"] in ["FAIL", "TIMEOUT", "ERROR"]:
            return "FAIL"
    return "PASS"


def generate_traffic_light(status):
    if status == "PASS":
        return "🟢 PASS"
    elif status == "FAIL":
        return "🔴 FAIL"
    else:
        return "🟡 WARNING"


def print_summary(report):
    status_color = {
        "PASS": "green",
        "FAIL": "red",
        "TIMEOUT": "yellow",
        "ERROR": "red",
        "WARNING": "yellow",
    }
    table = Table(title="MAS-TS-001 Fast-Screen Report", show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    table.add_row("Standard", report["standard"])
    table.add_row("Version", report["version"])
    table.add_row("Mode", report["mode"])
    table.add_row("Time", report["started_at"])
    table.add_row("Duration", f"{report['total_duration_ms']}ms")

    stages_table = Table(show_header=True)
    stages_table.add_column("Stage", style="cyan")
    stages_table.add_column("Status")
    stages_table.add_column("Duration")
    for stage in report["stages"]:
        color = status_color.get(stage["status"], "white")
        stage_status = f"[{color}]{stage['status']}[/]"
        stages_table.add_row(stage["stage"], stage_status, f"{stage['duration_ms']}ms")
        if stage.get("error"):
            stages_table.add_row("", f"[red]{stage['error'][:200]}[/]", "")

    overall_color = status_color.get(report["overall_status"], "white")
    overall_icon = {"PASS": "✅", "FAIL": "❌", "WARNING": "⚠️"}.get(
        report["overall_status"], "❓"
    )

    panel = Panel.fit(
        f"[bold {overall_color}]{overall_icon} Overall: {report['overall_status']}[/]",
        border_style=overall_color,
    )

    console.print()
    console.print(table)
    console.print()
    console.print(stages_table)
    console.print()
    console.print(panel)
    console.print()

    if report["overall_status"] == "FAIL":
        logger.error("Fast-Screen FAILED. Commit blocked.")
    elif report["overall_status"] == "WARNING":
        logger.warning("Fast-Screen passed with warnings.")
    else:
        logger.info("Fast-Screen passed. Commit allowed.")


def main():
    parser = argparse.ArgumentParser(description="MAS-TS-001 Fast-Screen Runner")
    parser.add_argument(
        "--version", action="version", version=f"mas-eval-harness {VERSION}"
    )
    parser.add_argument(
        "--engine", default="v3", choices=["v3"], help="Engine version (default: v3)"
    )
    parser.add_argument(
        "--card", help="Single Agent Card JSON path (alternative to --cards-dir)"
    )
    parser.add_argument("--cards-dir", help="Directory containing Agent Card JSONs")
    parser.add_argument("--task-file", help="Task descriptions JSON for Mock LLM test")
    parser.add_argument(
        "--policy", default="mock_policy.yaml", help="Mock policy YAML path"
    )
    parser.add_argument(
        "--schema",
        default=str(
            Path(__file__).parent / "mas_eval" / "schemas" / "agent_card_v1.1.json"
        ),
        help="Agent Card JSON Schema path",
    )
    parser.add_argument(
        "--golden-dir", help="Golden Trajectories directory for drift calibration"
    )
    parser.add_argument(
        "--mock-dir", help="Mock output directory for drift calibration"
    )
    parser.add_argument(
        "--block", action="store_true", help="Exit with error code on failure"
    )
    parser.add_argument("--output", help="Save report to JSON file")
    parser.add_argument(
        "--timeout", type=int, default=300, help="Total pipeline timeout in seconds"
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if not args.cards_dir and not args.card:
        parser.error("one of --cards-dir or --card is required")

    cards_dir = args.cards_dir
    if args.card:
        card_path = Path(args.card)
        if not card_path.exists():
            parser.error(f"card file not found: {args.card}")
        cards_dir = str(card_path.parent)

    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    pipeline_start = time.perf_counter()

    stages = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task1 = progress.add_task("[cyan]Layer 1: Compliance Scan...", total=None)
        stage1 = run_compliance_scan(cards_dir, args.schema, block=False)
        stages.append(stage1)
        progress.update(
            task1,
            description=f"[{'green' if stage1['status'] == 'PASS' else 'red'}]{stage1['status']} ({stage1['duration_ms']}ms)",
        )

        if args.task_file and Path(args.task_file).exists():
            task2 = progress.add_task(
                "[cyan]Layer 3: Mock LLM Action Test...", total=None
            )
            stage2 = run_mock_llm_test(args.task_file, args.policy)
            stages.append(stage2)
            progress.update(
                task2,
                description=f"[{'green' if stage2['status'] == 'PASS' else 'red'}]{stage2['status']} ({stage2['duration_ms']}ms)",
            )
        else:
            progress.add_task(
                "[yellow]Skipped: Mock LLM test (no --task-file)", total=None
            )

        if args.golden_dir and args.mock_dir:
            task3 = progress.add_task("[cyan]Mock Drift Calibration...", total=None)
            stage3 = run_mock_calibration(args.golden_dir, args.mock_dir)
            stages.append(stage3)
            progress.update(
                task3,
                description=f"[{'green' if stage3['status'] == 'PASS' else 'red'}]{stage3['status']} ({stage3['duration_ms']}ms)",
            )
        else:
            progress.add_task("[yellow]Skipped: Drift calibration", total=None)

    total_duration = int((time.perf_counter() - pipeline_start) * 1000)
    overall_status = determine_overall_status(stages)

    report = {
        "standard": "MAS-TS-001",
        "version": "v3.0",
        "mode": "fast-screen",
        "started_at": started_at,
        "total_duration_ms": total_duration,
        "overall_status": overall_status,
        "stages": stages,
        "config": {
            "cards_dir": args.cards_dir,
            "task_file": args.task_file,
            "policy": args.policy,
            "schema": args.schema,
            "golden_dir": args.golden_dir,
            "mock_dir": args.mock_dir,
        },
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    print_summary(report)

    if overall_status == "FAIL" and args.block:
        sys.exit(1)
    elif overall_status == "FAIL":
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
