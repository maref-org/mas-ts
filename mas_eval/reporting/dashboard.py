# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Terminal ASCII Dashboard for MAS-TS-001 Gold Standard reports.

Renders JSON report data as an ASCII dashboard with colour-coded badges,
domain score tables, and threshold violation highlighting.

Usage:
    from mas_eval.reporting.dashboard import render_dashboard
    print(render_dashboard(report))
"""

import argparse
import time
from typing import Any

from mas_eval.reporting.gold_report import load_report


def _colour(val: float, threshold: float, text: str) -> str:
    """Apply terminal colour codes based on pass/fail status."""
    if val >= threshold:
        return f"\033[32m{text}\033[0m"
    if val >= threshold * 0.8:
        return f"\033[33m{text}\033[0m"
    return f"\033[31m{text}\033[0m"


def _severity_colour(severity: str, text: str) -> str:
    mapping = {
        "CRITICAL": "\033[31m",
        "HIGH": "\033[33m",
        "WARNING": "\033[93m",
        "INFO": "\033[90m",
    }
    code = mapping.get(severity, "\033[0m")
    return f"{code}{text}\033[0m"


def render_dashboard(report: dict[str, Any]) -> str:
    """Render a gold report as an ASCII terminal dashboard.

    Args:
        report: Report dict from gold_report.generate_report().

    Returns:
        Formatted ASCII dashboard string.
    """
    cert = report.get("certificate", {})
    dims = report.get("dimensions", {})
    execution = report.get("execution", {})
    findings = report.get("findings", [])

    lines: list[str] = []

    lines.append("")
    lines.append("╔══════════════════════════════════════════════════════╗")
    lines.append("║       MAS-TS-001 Gold Standard Dashboard          ║")
    lines.append("╚══════════════════════════════════════════════════════╝")
    lines.append("")

    lines.append(cert.get("badge", ""))

    lines.append("")
    lines.append("┌─────────────────────────────────────────────────────┐")
    lines.append("│                 Domain Scores                      │")
    lines.append("├──────┬─────────┬────────────┬──────────────────────┤")
    lines.append("│ Dom  │  Score  │ Threshold  │       Status        │")
    lines.append("├──────┼─────────┼────────────┼──────────────────────┤")

    for dom_key in sorted(dims.keys()):
        d = dims[dom_key]
        score = d["score"]
        threshold = d["threshold"]
        passed = d["passed"]
        status = "✓ PASS" if passed else "✗ FAIL"
        coloured_status = _colour(score, threshold, f"{status:>8}")
        lines.append(
            f"│  {dom_key:<2} │  {score:>5.1f}  │    {threshold:>5.1f}   │  {coloured_status}              │"
        )

    lines.append("├──────┴─────────┴────────────┴──────────────────────┤")

    overall_score = cert.get("score", 0)
    grade = cert.get("grade", "F")
    verdict = cert.get("verdict", "FAIL")
    ci = cert.get("ci")
    ce = cert.get("ce")

    lines.append(
        f"│  Overall Score: {overall_score:>5.1f}  Grade: {grade:<2}  Verdict: {verdict:<8}  │"
    )

    if ci is not None:
        lines.append(
            f"│  Consistency Index: {ci:.2f}                                        │"
        )
    if ce is not None:
        lines.append(
            f"│  Cost Efficiency:   {ce:.2f}                                        │"
        )

    lines.append("└─────────────────────────────────────────────────────┘")
    lines.append("")

    if findings:
        lines.append("┌─────────────────────────────────────────────────────┐")
        lines.append("│                 Findings                           │")
        lines.append("├──────────┬────────────────────────────────────────┤")
        lines.append("│ Severity │ Detail                                  │")
        lines.append("├──────────┼────────────────────────────────────────┤")
        for f in findings:
            sev = f.get("severity", "INFO")
            detail = f.get("detail", "")[:38]
            coloured_sev = _severity_colour(sev, f"{sev:<8}")
            lines.append(f"│ {coloured_sev} │ {detail:<38} │")
        lines.append("└──────────┴────────────────────────────────────────┘")
        lines.append("")

    lines.append("┌─────────────────────────────────────────────────────┐")
    lines.append("│                 Execution                           │")
    lines.append("├─────────────────────────────────────────────────────┤")
    lines.append(f"│  Timestamp:   {str(execution.get('timestamp', 'N/A')):<29} │")
    lines.append(f"│  Duration:    {execution.get('duration_ms', 0):>6} ms{'':>26} │")
    tests_passed = execution.get("tests_passed", 0)
    tests_total = execution.get("tests_total", 0)
    coverage = execution.get("coverage_pct", 0.0)
    lines.append(f"│  Tests:       {tests_passed}/{tests_total} passed{'':>24} │")
    lines.append(f"│  Coverage:    {coverage:.2f}%{'':>30} │")
    level_name = execution.get("level", "L3")
    lines.append(f"│  Level:       {level_name:<30} │")
    lines.append("└─────────────────────────────────────────────────────┘")
    lines.append("")

    return "\n".join(lines)


def render_domain_table(report: dict[str, Any]) -> str:
    """Render only the domain scores table (compact).

    Args:
        report: Report dict from gold_report.generate_report().

    Returns:
        Formatted ASCII table string.
    """
    dims = report.get("dimensions", {})
    lines: list[str] = []

    lines.append("┌──────┬─────────┬────────────┬──────────┐")
    lines.append("│ Dom  │  Score  │ Threshold  │ Status   │")
    lines.append("├──────┼─────────┼────────────┼──────────┤")

    for dom_key in sorted(dims.keys()):
        d = dims[dom_key]
        score = d["score"]
        threshold = d["threshold"]
        status = "✓" if d["passed"] else "✗"
        coloured_score = _colour(score, threshold, f"{score:>5.1f}")
        lines.append(
            f"│  {dom_key:<2} │  {coloured_score}  │    {threshold:>5.1f}   │   {status}    │"
        )

    lines.append("└──────┴─────────┴────────────┴──────────┘")

    return "\n".join(lines)


def watch_mode(path: str, interval: float = 5.0) -> None:
    """Continuously reload and render the report at a given interval.

    Args:
        path: Path to the JSON report file.
        interval: Refresh interval in seconds.
    """
    try:
        while True:
            report = load_report(path)
            print("\033[2J\033[H", end="")
            print(render_dashboard(report))
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


def main() -> None:
    """CLI entry point for the dashboard."""
    parser = argparse.ArgumentParser(description="MAS-TS-001 Gold Standard Dashboard")
    parser.add_argument(
        "report",
        nargs="?",
        default="reports/gold-report.json",
        help="Path to gold report JSON",
    )
    parser.add_argument(
        "--watch", "-w", action="store_true", help="Watch mode: auto-refresh"
    )
    parser.add_argument(
        "--interval", "-i", type=float, default=5.0, help="Refresh interval in seconds"
    )
    parser.add_argument(
        "--compact", "-c", action="store_true", help="Render compact domain table only"
    )

    args = parser.parse_args()

    report = load_report(args.report)

    if args.compact:
        print(render_domain_table(report))
    elif args.watch:
        watch_mode(args.report, args.interval)
    else:
        print(render_dashboard(report))


if __name__ == "__main__":
    main()
