# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Real Docker verification for the SWE-bench oracle (B, step 1).

These tests actually start a container and run a test command against the
supplied patch. They are marked ``slow`` and skip when Docker or the
``python:3.11-slim`` image is unavailable — a skipped test is not evidence.

Run explicitly:
    pytest tests/test_swe_bench_live.py -m slow -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from mas_eval.evidence import EVIDENCE_MODE_DECLARED, EVIDENCE_MODE_VERIFIED_PATCH
from mas_eval.oracle.oracle_base import OracleTask
from mas_eval.oracle.swe_bench import SWEBenchOracle, official_image_name

IMAGE = "python:3.11-slim"


def _docker_ready() -> tuple[bool, str]:
    if shutil.which("docker") is None:
        return False, "docker CLI not found"
    try:
        info = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=15
        )
        if info.returncode != 0:
            return False, "docker daemon not running"
        image = subprocess.run(
            ["docker", "image", "inspect", IMAGE],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if image.returncode != 0:
            return False, f"image {IMAGE} not present locally"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return True, "ready"


def _task(patch_marker: str) -> dict:
    return {
        "task_id": "docker-smoke",
        "repo": "local/fixture",
        "problem_statement": "make add return a+b",
        "file_path": "/workspace/calc.py",
        "test_command": "python /workspace/test_calc.py",
        "expected_old_str": "return a - b",
        "expected_new_str": "return a + b",
        "golden_trajectory": {"events": []},
        "setup_commands": [],
        "patch_marker": patch_marker,
    }


def _trajectory(add_body: str) -> list[dict]:
    return [
        {
            "action": {
                "type": "file_write",
                "input": {
                    "path": "/workspace/calc.py",
                    "content": f"def add(a, b):\n    {add_body}\n",
                },
            }
        },
        {
            "action": {
                "type": "file_write",
                "input": {
                    "path": "/workspace/test_calc.py",
                    "content": "from calc import add\nassert add(1, 2) == 3\n",
                },
            }
        },
    ]


@pytest.mark.slow
def test_real_docker_verifies_correct_patch():
    ready, reason = _docker_ready()
    if not ready:
        pytest.skip(reason)

    oracle = SWEBenchOracle()
    oracle._tasks_cache = [_task("correct")]
    score = oracle.score(
        OracleTask("docker-smoke", "make add return a+b"),
        _trajectory("return a + b"),
    )

    assert score == 100.0
    assert oracle.evidence_mode() == EVIDENCE_MODE_VERIFIED_PATCH


@pytest.mark.slow
def test_real_docker_still_reports_verified_when_tests_fail():
    """verified_patch means the tests ran, not that they passed."""
    ready, reason = _docker_ready()
    if not ready:
        pytest.skip(reason)

    oracle = SWEBenchOracle()
    oracle._tasks_cache = [_task("wrong")]
    score = oracle.score(
        OracleTask("docker-smoke", "make add return a+b"),
        _trajectory("return a - b"),
    )

    assert score == 0.0
    assert oracle.evidence_mode() == EVIDENCE_MODE_VERIFIED_PATCH


@pytest.mark.slow
def test_declared_when_docker_unavailable(monkeypatch):
    """A simulated fallback must never upgrade the evidence claim."""
    from mas_eval.oracle import swe_bench

    oracle = SWEBenchOracle()
    oracle._tasks_cache = [_task("simulated")]
    monkeypatch.setattr(swe_bench, "check_docker", lambda: (False, "no docker"))

    score = oracle.score(
        OracleTask("docker-smoke", "make add return a+b"),
        _trajectory("return a + b"),
    )

    assert score >= 0.0
    assert oracle.evidence_mode() == EVIDENCE_MODE_DECLARED


@pytest.mark.slow
def test_official_lite_gold_patch_resolves(monkeypatch):
    """Real official image + official test_patch + gold patch -> resolved.

    Requires SWE_BENCH_LITE_FIXTURE to point at an exported JSON list and the
    official image to be present locally; otherwise the test skips (a skip is
    not evidence).
    """
    fixture = os.environ.get("SWE_BENCH_LITE_FIXTURE")
    if not fixture or not os.path.exists(fixture):
        pytest.skip("SWE_BENCH_LITE_FIXTURE not set")

    instance_id = "astropy__astropy-12907"
    rows = json.loads(open(fixture, encoding="utf-8").read())
    row = next((r for r in rows if r["instance_id"] == instance_id), None)
    if row is None:
        pytest.skip(f"{instance_id} not in fixture")

    ready, reason = _docker_ready()
    if not ready:
        pytest.skip(reason)

    image = official_image_name(instance_id)
    inspect = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if inspect.returncode != 0:
        pytest.skip(f"official image not present locally: {image}")

    monkeypatch.setenv("SWE_BENCH_LITE_PATH", fixture)
    oracle = SWEBenchOracle()
    result = oracle.verify_instance(instance_id, row["patch"])

    assert result["resolved"] is True
    assert result["evidence_mode"] == EVIDENCE_MODE_VERIFIED_PATCH
    assert oracle.evidence_mode() == EVIDENCE_MODE_VERIFIED_PATCH
