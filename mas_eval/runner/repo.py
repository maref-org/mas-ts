# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Repository preparation for agent runs."""

from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = ["prepare_repo"]


def prepare_repo(repo: str, base_commit: str, workdir: Path) -> None:
    """Fetch exactly ``base_commit`` from GitHub into ``workdir`` (shallow)."""
    workdir.mkdir(parents=True, exist_ok=True)

    def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd, cwd=workdir, capture_output=True, text=True, timeout=600
        )

    run(["git", "init", "-q"])
    run(["git", "remote", "add", "origin", f"https://github.com/{repo}.git"])

    fetched = run(["git", "fetch", "--depth", "1", "origin", base_commit])
    if fetched.returncode != 0:
        fetched = run(["git", "fetch", "--depth", "50", "origin"])
        if fetched.returncode != 0:
            raise RuntimeError(f"git fetch failed: {fetched.stderr[-400:]}")
        checked_out = run(["git", "checkout", "-q", base_commit])
    else:
        checked_out = run(["git", "checkout", "-q", "FETCH_HEAD"])

    if checked_out.returncode != 0:
        raise RuntimeError(f"git checkout failed: {checked_out.stderr[-400:]}")
