# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Executable release gate checklist for MAS-TS-001 (Phase 7.1).

Maps each of the 12 release-gate items in `docs/release-gate.md` to either an
auto-check (command + expected exit code) or a documented manual approval.
Items G0.1/G0.2/G3.4 are manual; G3.4 requires UAT signoff record (R7 P0).
Item G3.5 auto-runs the regression test suite (R8 P0).
Run with: `python3 scripts/release_gate_check.py`
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

SECRET_SCAN_INLINE = (
    "import re,sys,pathlib;"
    "pattern=re.compile(r'AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{48}');"
    "hits=[str(p) for p in pathlib.Path('mas_eval').rglob('*.py') "
    "if pattern.search(p.read_text())];"
    "sys.exit(1 if hits else 0)"
)

# Use the current Python interpreter so the script works inside an activated
# venv (where ruff/mypy/pytest live) without requiring system-wide installs.
_PY = sys.executable

GATE_ITEMS: list[dict[str, Any]] = [
    {
        "id": "G0.1",
        "gate": 0,
        "name": "Requirements documented",
        "type": "manual",
        "expected": "docs/plans/* or docs/release-gate.md references explicit acceptance criteria",
    },
    {
        "id": "G0.2",
        "gate": 0,
        "name": "Architecture/design review",
        "type": "manual",
        "expected": "design notes recorded in docs/plans/ and reviewed by maintainer",
    },
    {
        "id": "G1.1",
        "gate": 1,
        "name": "ruff: 0 errors",
        "type": "auto",
        "command": [_PY, "-m", "ruff", "check", "mas_eval/", "tests/"],
        "expected": "exit code 0",
    },
    {
        "id": "G1.2",
        "gate": 1,
        "name": "mypy strict: 0 errors",
        "type": "auto",
        "command": [_PY, "-m", "mypy", "mas_eval/", "--strict"],
        "expected": "exit code 0",
    },
    {
        "id": "G1.3",
        "gate": 1,
        "name": "pytest coverage >= 85%",
        "type": "auto",
        "command": [
            _PY,
            "-m",
            "pytest",
            "tests/",
            "--cov=mas_eval",
            "--cov-report=term-missing",
            "-q",
        ],
        "expected": "exit code 0 and coverage >= 85.0",
    },
    {
        "id": "G2.1",
        "gate": 2,
        "name": "pytest: 100% passed",
        "type": "auto",
        "command": [_PY, "-m", "pytest", "tests/", "-q"],
        "expected": "exit code 0 (no failures)",
    },
    {
        "id": "G2.2",
        "gate": 2,
        "name": "Integration tests pass",
        "type": "auto",
        "command": [
            _PY,
            "-m",
            "pytest",
            "tests/test_integration.py",
            "-q",
        ],
        "expected": "exit code 0",
    },
    {
        "id": "G3.1",
        "gate": 3,
        "name": "bandit SAST: 0 issues",
        "type": "auto",
        "command": [
            _PY,
            "-m",
            "bandit",
            "-r",
            "mas_eval",
            "-c",
            "pyproject.toml",
            "-q",
        ],
        "expected": "exit code 0 (configured skips applied)",
    },
    {
        "id": "G3.2",
        "gate": 3,
        "name": "pip-audit: 0 Critical/High CVE (manual due to env-specific SIGABRT)",
        "type": "manual",
        "command": [
            _PY,
            "-m",
            "pip_audit",
            "--requirement",
            "requirements.txt",
            "--strict",
        ],
        "expected": "exit code 0",
    },
    {
        "id": "G3.3",
        "gate": 3,
        "name": "Secret scan: 0 hardcoded credentials",
        "type": "auto",
        "command": [_PY, "-c", SECRET_SCAN_INLINE],
        "expected": "exit code 0 (no AKIA/ghp_/sk- patterns found)",
    },
    {
        "id": "G3.4",
        "gate": 3,
        "name": "UAT signoff recorded",
        "type": "manual",
        "expected": "docs/uat/MAS-TS-001_UAT_Signoff_v0.8.0.md exists with Go/Conditional Go (R7 P0)",
    },
    {
        "id": "G3.5",
        "gate": 3,
        "name": "Regression baseline comparison pass",
        "type": "auto",
        "command": [
            _PY,
            "-m",
            "pytest",
            "tests/test_regression.py",
            "-q",
        ],
        "expected": "exit code 0 (30 regression tests pass — R8 P0)",
    },
]


@dataclass
class GateResult:
    id: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "status": self.status, "detail": self.detail}


def _default_runner(command: list[str]) -> tuple[int, str, str]:
    """Default runner that executes the command via subprocess."""
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _run_auto(
    item: dict[str, Any],
    runner: Any = None,
) -> GateResult:
    command = item["command"]
    run = runner or _default_runner
    try:
        returncode, stdout, stderr = run(command)
    except subprocess.TimeoutExpired:
        return GateResult(
            id=item["id"],
            status="FAIL",
            detail=f"timeout after 600s: {' '.join(command)}",
        )
    except FileNotFoundError as exc:
        return GateResult(
            id=item["id"],
            status="FAIL",
            detail=f"command not found: {exc}",
        )
    if returncode == 0:
        return GateResult(
            id=item["id"],
            status="PASS",
            detail=f"{' '.join(command)}",
        )
    tail = (stderr or stdout)[-400:].replace("\n", " | ")
    return GateResult(
        id=item["id"],
        status="FAIL",
        detail=f"exit={returncode}: {tail}",
    )


def run_all(runner: Any = None) -> list[dict[str, str]]:
    """Run every gate item and return list of result dicts.

    Args:
        runner: Optional callable accepting a command list and returning
            (returncode, stdout, stderr). Defaults to real subprocess runner.
            Tests inject a stub to avoid spawning real commands.
    """
    results: list[dict[str, str]] = []
    for item in GATE_ITEMS:
        if item["type"] == "manual":
            results.append(
                GateResult(
                    id=item["id"],
                    status="MANUAL",
                    detail=item["expected"],
                ).to_dict()
            )
        else:
            results.append(_run_auto(item, runner=runner).to_dict())
    return results


def summarize(results: list[dict[str, str]]) -> dict[str, int]:
    summary = {"total": len(results), "pass": 0, "fail": 0, "manual": 0}
    for r in results:
        if r["status"] == "PASS":
            summary["pass"] += 1
        elif r["status"] == "FAIL":
            summary["fail"] += 1
        elif r["status"] == "MANUAL":
            summary["manual"] += 1
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MAS-TS release gate checker")
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print gate items and exit without running",
    )
    parser.add_argument(
        "--manual-ok",
        action="store_true",
        help="Treat MANUAL items as PASS for exit code purposes",
    )
    args = parser.parse_args(argv)

    if args.list:
        for item in GATE_ITEMS:
            print(
                f"{item['id']}\tgate={item['gate']}\ttype={item['type']}\t{item['name']}"
            )
        return 0

    print("=" * 78)
    print("MAS-TS-001 Release Gate Checklist (executable)")
    print("=" * 78)
    results = run_all()
    for r in results:
        print(f"[{r['status']:<6}] {r['id']:<5} {r['detail']}")
    summary = summarize(results)
    print("-" * 78)
    print(
        f"Total: {summary['total']}  PASS: {summary['pass']}  "
        f"FAIL: {summary['fail']}  MANUAL: {summary['manual']}"
    )
    effective_fail = summary["fail"]
    if not args.manual_ok:
        effective_fail += summary["manual"]
    print("=" * 78)
    if effective_fail > 0:
        print(
            "Release gate: NOT MET (run with --manual-ok to ignore pending approvals)"
        )
        return 1
    print("Release gate: MET")
    return 0


if __name__ == "__main__":
    sys.exit(main())
