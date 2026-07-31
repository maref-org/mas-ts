# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS-001 v3.0 — Environment Detection Utilities.

Probes the runtime environment for tool availability used by
executable oracles (Docker, Playwright, stress-ng).
"""

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


def check_docker():
    """Check if Docker daemon is accessible.

    Returns:
        (ok: bool, message: str)
    """
    if not shutil.which("docker"):
        return False, "docker binary not found"

    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "Docker daemon accessible"
        return False, f"docker ps failed: {result.stderr.strip()}"
    except FileNotFoundError:
        return False, "docker not found"
    except subprocess.TimeoutExpired:
        return False, "docker ps timed out"
    except OSError as e:
        return False, f"docker error: {e}"


def check_playwright():
    """Check if Playwright Python package is available.

    Returns:
        (ok: bool, message: str)
    """
    try:
        import playwright  # noqa: F401

        return True, "playwright package installed"
    except ImportError:
        return False, "playwright package not installed"


def check_stress_ng():
    """Check if stress-ng is available.

    Returns:
        (ok: bool, message: str)
    """
    if not shutil.which("stress-ng"):
        return False, "stress-ng not found in PATH"

    try:
        result = subprocess.run(
            ["stress-ng", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True, f"stress-ng available: {result.stdout.strip()}"
        return False, f"stress-ng error: {result.stderr.strip()}"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        return False, f"stress-ng check failed: {e}"


def get_environment_summary():
    """Probe all known tools and return a summary dict.

    Returns:
        dict with tool names as keys, (ok, message) tuples as values.
    """
    return {
        "docker": check_docker(),
        "playwright": check_playwright(),
        "stress_ng": check_stress_ng(),
    }
