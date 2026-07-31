# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Deterministic federation scan threshold policy (Phase 7.2).

Parses a federation scan JSON report (either mas_full_run.py --multi-vendor
v1 shape OR run_v4_federation_scan_v2.py v2 shape) and applies the v0.4.0
release threshold:

    meets_threshold(report) iff
        blocked_count <= MAX_BLOCKED AND
        (critical_count == 0 OR allow_critical) AND
        (total_agents - blocked_count) >= MIN_PASSING

Defaults:
    MAX_BLOCKED     = 0  (override via --max-blocked)
    MIN_PASSING     = 3
    ALLOW_CRITICAL  = False  (override via --allow-critical)

Exit codes:
    0 = threshold met
    1 = threshold not met (print reason to stderr)
    2 = report parse error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_MAX_BLOCKED = 0
DEFAULT_MIN_PASSING = 3
DEFAULT_ALLOW_CRITICAL = False


def _extract_blocked_v1(report: dict[str, Any]) -> tuple[int, int]:
    """v1 shape (mas_full_run.py --multi-vendor): {agents: {name: {d1: {verdict}}}}."""
    agents = report.get("agents", {})
    if not isinstance(agents, dict):
        return 0, 0
    blocked = sum(
        1
        for a in agents.values()
        if isinstance(a, dict)
        and a.get("d1", {}).get("verdict") == "NON-COMPLIANT (blocked)"
    )
    return blocked, len(agents)


def _extract_critical_v1(report: dict[str, Any]) -> int:
    """CRITICAL findings from v1 shape: count from top-level `findings` list
    plus per-agent findings (covers both mas_full_run variants)."""
    critical = 0
    top_findings = report.get("findings", [])
    if isinstance(top_findings, list):
        critical += sum(
            1
            for f in top_findings
            if isinstance(f, dict) and f.get("severity") == "CRITICAL"
        )
    agents = report.get("agents", {})
    if isinstance(agents, dict):
        for a in agents.values():
            if not isinstance(a, dict):
                continue
            for f in a.get("findings", []):
                if isinstance(f, dict) and f.get("severity") == "CRITICAL":
                    critical += 1
    return critical


def _extract_blocked_v2(report: dict[str, Any]) -> tuple[int, int]:
    """v2 shape (run_v4_federation_scan_v2): v2 reports have no per-agent
    blocked flag; blocked_count is always 0 unless a CRITICAL finding is
    present, in which case all agents are considered blocked."""
    return 0, len(report.get("results", {}))


def _extract_critical_v2(report: dict[str, Any]) -> int:
    fed = report.get("federation", {}).get("d4_federation", {})
    return sum(
        1
        for f in fed.get("findings", [])
        if isinstance(f, dict) and f.get("severity") == "CRITICAL"
    )


def _is_v2_shape(report: dict[str, Any]) -> bool:
    return "results" in report and "federation" in report


def parse_federation_report(report: dict[str, Any]) -> dict[str, Any]:
    """Parse a federation scan report into a normalized summary dict."""
    if _is_v2_shape(report):
        blocked, total = _extract_blocked_v2(report)
        critical = _extract_critical_v2(report)
        score = report.get("federation", {}).get("d4_federation", {}).get("score", 0.0)
    else:
        blocked, total = _extract_blocked_v1(report)
        critical = _extract_critical_v1(report)
        score = report.get("federation_score") or report.get("federation", {}).get(
            "score", 0.0
        )
    passing = max(0, total - blocked)
    compliance_rate = passing
    return {
        "blocked_count": blocked,
        "critical_count": critical,
        "total_agents": total,
        "passing_count": passing,
        "compliance_rate": compliance_rate,
        "federation_score": float(score) if score is not None else 0.0,
    }


def meets_threshold(
    parsed: dict[str, Any],
    max_blocked: int = DEFAULT_MAX_BLOCKED,
    min_passing: int = DEFAULT_MIN_PASSING,
    allow_critical: bool = DEFAULT_ALLOW_CRITICAL,
) -> dict[str, Any]:
    """Apply threshold policy to a parsed report.

    Returns dict with `meets` (bool) and `reason` (str).
    """
    reasons: list[str] = []
    if parsed["blocked_count"] > max_blocked:
        reasons.append(
            f"blocked_count={parsed['blocked_count']} exceeds max_blocked={max_blocked}"
        )
    if not allow_critical and parsed["critical_count"] > 0:
        reasons.append(
            f"critical_count={parsed['critical_count']} > 0 (set allow_critical=true to override)"
        )
    if parsed["passing_count"] < min_passing:
        reasons.append(
            f"passing_count={parsed['passing_count']} below min_passing={min_passing}"
        )
    return {
        "meets": len(reasons) == 0,
        "reason": "; ".join(reasons) if reasons else "threshold met",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Federation scan threshold policy")
    parser.add_argument("report", help="Path to federation scan JSON report")
    parser.add_argument(
        "--max-blocked",
        type=int,
        default=DEFAULT_MAX_BLOCKED,
        help=f"Max allowed blocked agents (default {DEFAULT_MAX_BLOCKED})",
    )
    parser.add_argument(
        "--min-passing",
        type=int,
        default=DEFAULT_MIN_PASSING,
        help=f"Min required passing agents (default {DEFAULT_MIN_PASSING})",
    )
    parser.add_argument(
        "--allow-critical",
        action="store_true",
        help=f"Allow CRITICAL findings to pass (default {DEFAULT_ALLOW_CRITICAL})",
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"error: report not found: {report_path}", file=sys.stderr)
        return 2
    try:
        report = json.loads(report_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in report: {exc}", file=sys.stderr)
        return 2

    parsed = parse_federation_report(report)
    decision = meets_threshold(
        parsed,
        max_blocked=args.max_blocked,
        min_passing=args.min_passing,
        allow_critical=args.allow_critical,
    )

    print(
        f"federation_score={parsed['federation_score']} "
        f"total={parsed['total_agents']} "
        f"passing={parsed['passing_count']} "
        f"blocked={parsed['blocked_count']} "
        f"critical={parsed['critical_count']}"
    )
    if decision["meets"]:
        print(f"threshold MET ({decision['reason']})")
        return 0
    print(f"threshold NOT MET: {decision['reason']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
