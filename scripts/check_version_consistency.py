#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Version ledger consistency check (v1.0.1).

One version number must be visible everywhere a consumer looks:
pyproject, CHANGELOG top entry, AGENTS.md header, package __version__, API
__version__, and the UAT signoff record for the release.

Usage:
    python scripts/check_version_consistency.py
    python scripts/check_version_consistency.py --require-tag

Exit codes:
    0 — core versions consistent (UAT gap is reported as WARNING)
    1 — one or more core versions disagree
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
AGENTS = ROOT / "AGENTS.md"
MAS_EVAL_INIT = ROOT / "mas_eval" / "__init__.py"
API_INIT = ROOT / "api" / "__init__.py"
UAT_DIR = ROOT / "docs" / "uat"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def get_pyproject_version() -> str | None:
    match = re.search(r'^version\s*=\s*"([^"]+)"', _read(PYPROJECT), re.MULTILINE)
    return match.group(1) if match else None


def get_changelog_version() -> str | None:
    match = re.search(r"^##\s*\[([^\]]+)\]", _read(CHANGELOG), re.MULTILINE)
    return match.group(1) if match else None


def get_agents_version() -> str | None:
    match = re.search(r"\(v(\d+\.\d+\.\d+)\)", _read(AGENTS))
    return match.group(1) if match else None


def get_init_version(path: Path) -> str | None:
    match = re.search(r'__version__\s*=\s*"([^"]+)"', _read(path))
    return match.group(1) if match else None


def find_uat_signoff(version: str) -> Path | None:
    if not UAT_DIR.is_dir():
        return None
    matches = sorted(UAT_DIR.glob(f"*UAT_Signoff_v{version}.md"))
    return matches[0] if matches else None


def get_git_tag() -> str | None:
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--exact-match", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip().lstrip("v") or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Version ledger consistency check")
    parser.add_argument(
        "--require-tag",
        action="store_true",
        help="Also require HEAD to carry an exact version tag (release workflow only)",
    )
    args = parser.parse_args(argv)

    entries = {
        "pyproject.toml": get_pyproject_version(),
        "CHANGELOG.md (top)": get_changelog_version(),
        "AGENTS.md (header)": get_agents_version(),
        "mas_eval/__init__.py": get_init_version(MAS_EVAL_INIT),
        "api/__init__.py": get_init_version(API_INIT),
    }

    for label, value in entries.items():
        print(f"{'OK ' if value else 'MISS'} {label}: {value or '<not found>'}")

    versions = {v for v in entries.values() if v}
    failed = False
    if len(versions) != 1:
        print(f"\nERROR: version mismatch across ledger: {sorted(versions)}")
        failed = True

    version = entries["pyproject.toml"]
    if version:
        signoff = find_uat_signoff(version)
        if signoff:
            print(f"OK  UAT signoff: {signoff.relative_to(ROOT)}")
        else:
            print(
                f"WARN UAT signoff for v{version} not found in docs/uat/ "
                "(human signature required; not auto-generated)"
            )

        if args.require_tag:
            tag = get_git_tag()
            if tag == version:
                print(f"OK  git tag: v{tag}")
            else:
                print(f"ERROR: HEAD tag {tag!r} != version {version!r}")
                failed = True

    if failed:
        print("\nVersion ledger: NOT CONSISTENT")
        return 1
    print("\nVersion ledger: CONSISTENT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
