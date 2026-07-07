# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Coverage report aggregator for MAS-TS-001.

Reads coverage.json output from pytest-cov, aggregates by mas_eval module,
and outputs both JSON and ASCII table formats.

Usage:
    report = generate_module_coverage("coverage.json")
    print(report["ascii_table"])
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

MAS_EVAL_PREFIX = "mas_eval/"
DEFAULT_COVERAGE_FILE = "coverage.json"


def _parse_coverage_json(path: str) -> dict[str, Any]:
    """Parse a coverage.json file and return raw data."""
    raw: dict[str, Any] = json.loads(Path(path).read_text())
    return raw


def _extract_module_name(file_path: str) -> str | None:
    """Extract the top-level mas_eval module name from a file path.

    e.g. 'mas_eval/domains/d1_compliance.py' -> 'domains'
         'mas_eval/scoring/absolute.py'      -> 'scoring'
         'mas_eval/reporting/dashboard.py'   -> 'reporting'
    """
    if not file_path.startswith(MAS_EVAL_PREFIX):
        return None
    parts = file_path.split("/")
    if len(parts) >= 2:
        return parts[1]
    return None


def generate_module_coverage(
    coverage_path: str | None = None,
    min_threshold: float = 80.0,
) -> dict[str, Any]:
    """Aggregate coverage data by mas_eval module.

    Args:
        coverage_path: Path to coverage.json. Defaults to 'coverage.json'.
        min_threshold: Minimum coverage percentage for a module to pass.

    Returns:
        Dict with keys: modules (list of module dicts), overall_coverage,
        passed_modules, failed_modules, ascii_table, json_output.
    """
    path = coverage_path or DEFAULT_COVERAGE_FILE
    if not os.path.exists(path):
        return {
            "error": f"Coverage file not found: {path}",
            "modules": [],
            "overall_coverage": 0.0,
            "passed_modules": 0,
            "failed_modules": 0,
            "ascii_table": f"[ERROR] Coverage file not found: {path}",
            "json_output": {},
        }

    try:
        raw = _parse_coverage_json(path)
    except (json.JSONDecodeError, ValueError):
        return {
            "error": f"Invalid JSON in coverage file: {path}",
            "modules": [],
            "overall_coverage": 0.0,
            "passed_modules": 0,
            "failed_modules": 0,
            "ascii_table": "[ERROR] Invalid coverage.json file",
            "json_output": {},
        }

    if "files" not in raw:
        return {
            "error": "Invalid coverage.json format: missing 'files' key",
            "modules": [],
            "overall_coverage": 0.0,
            "passed_modules": 0,
            "failed_modules": 0,
            "ascii_table": "[ERROR] Invalid coverage.json format",
            "json_output": raw,
        }

    module_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"files": [], "covered_lines": 0, "total_lines": 0}
    )

    for file_path, file_info in raw["files"].items():
        module_name = _extract_module_name(file_path)
        if module_name is None:
            continue

        if not isinstance(file_info, dict):
            continue

        summary = file_info.get("summary", {})
        if summary:
            covered_lines = summary.get("covered_lines", 0)
            num_statements = summary.get("num_statements", 0)
        else:
            line_rate = file_info.get("line_rate", 0.0) or 0.0
            total = file_info.get("total_lines", 0) or 0
            covered_lines = int(total * line_rate)
            num_statements = total

        md = module_data[module_name]
        md["files"].append(file_path)
        md["covered_lines"] += covered_lines
        md["total_lines"] += num_statements

    modules: list[dict[str, Any]] = []
    total_covered_all = 0
    total_lines_all = 0

    for mod_name in sorted(module_data.keys()):
        md = module_data[mod_name]
        avg_rate = (md["covered_lines"] / max(md["total_lines"], 1)) * 100
        total_covered_all += md["covered_lines"]
        total_lines_all += md["total_lines"]

        modules.append(
            {
                "module": mod_name,
                "file_count": len(md["files"]),
                "covered_lines": md["covered_lines"],
                "total_lines": md["total_lines"],
                "coverage_pct": round(avg_rate, 2),
                "passed": avg_rate >= min_threshold,
            }
        )

    overall_cov = (total_covered_all / max(total_lines_all, 1)) * 100

    passed = sum(1 for m in modules if m["passed"])
    failed = sum(1 for m in modules if not m["passed"])

    ascii_lines: list[str] = []
    ascii_lines.append(
        "┌─────────────────────────────────────────────────────────────┐"
    )
    ascii_lines.append(
        f"│        MAS-TS-001 Module Coverage Report (≥{min_threshold:.0f}%)      │"
    )
    ascii_lines.append(
        "├──────────┬───────────┬──────────────┬───────────────────────┤"
    )
    ascii_lines.append(
        "│ Module   │  Files    │  Coverage    │  Status               │"
    )
    ascii_lines.append(
        "├──────────┼───────────┼──────────────┼───────────────────────┤"
    )

    for m in modules:
        mod = m["module"]
        files = m["file_count"]
        cov = m["coverage_pct"]
        status = "✓ PASS" if m["passed"] else "✗ FAIL"
        ascii_lines.append(
            f"│ {mod:<8} │  {files:>3}     │  {cov:>6.2f}%   │  {status:<20} │"
        )

    ascii_lines.append(
        "├──────────┴───────────┴──────────────┴───────────────────────┤"
    )
    ascii_lines.append(
        f"│  Overall Coverage: {overall_cov:.2f}%  ({passed}/{passed + failed} modules pass)           │"
    )
    ascii_lines.append(
        "└─────────────────────────────────────────────────────────────┘"
    )

    return {
        "modules": modules,
        "overall_coverage": round(overall_cov, 2),
        "passed_modules": passed,
        "failed_modules": failed,
        "ascii_table": "\n".join(ascii_lines),
        "json_output": {"modules": modules, "overall_coverage": round(overall_cov, 2)},
    }


def save_coverage_report(
    report: dict[str, Any],
    output_path: str = "reports/coverage-report.json",
) -> str:
    """Save coverage report to a JSON file.

    Args:
        report: Report dict from generate_module_coverage().
        output_path: Output file path.

    Returns:
        The absolute path of the saved file.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report.get("json_output", report), f, indent=2)
    return os.path.abspath(output_path)


def main() -> None:
    """CLI entry point for coverage report."""
    import argparse

    parser = argparse.ArgumentParser(description="MAS-TS-001 Module Coverage Report")
    parser.add_argument(
        "coverage_file",
        nargs="?",
        default=DEFAULT_COVERAGE_FILE,
        help="Path to coverage.json",
    )
    parser.add_argument(
        "--min-threshold",
        "-t",
        type=float,
        default=80.0,
        help="Minimum coverage threshold",
    )
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument(
        "--table-only", action="store_true", help="Print ASCII table only"
    )

    args = parser.parse_args()

    report = generate_module_coverage(args.coverage_file, args.min_threshold)

    if "error" in report:
        print(f"Error: {report['error']}")
        return

    print(report["ascii_table"])

    if args.output:
        saved = save_coverage_report(report, args.output)
        print(f"\nReport saved to: {saved}")


if __name__ == "__main__":
    main()
