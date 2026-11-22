# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Official SWE-bench Lite integration tests (unit + mocked Docker).

The real Docker path is covered by tests/test_swe_bench_live.py (slow).
"""

from __future__ import annotations

import json
from unittest.mock import patch

from mas_eval.evidence import EVIDENCE_MODE_DECLARED, EVIDENCE_MODE_VERIFIED_PATCH
from mas_eval.oracle.oracle_base import OracleTask
from mas_eval.oracle.swe_bench import (
    DockerSandbox,
    SWEBenchOracle,
    load_lite_tasks,
    official_image_name,
)

INSTANCE = "astropy__astropy-12907"


def _row() -> dict:
    return {
        "instance_id": INSTANCE,
        "repo": "astropy/astropy",
        "version": "4.3",
        "problem_statement": "fix separable",
        "base_commit": "abc123",
        "patch": "diff --git a/x b/x\n",
        "test_patch": "diff --git a/t b/t\n",
        "FAIL_TO_PASS": json.dumps(["a::test_one"]),
        "PASS_TO_PASS": json.dumps(["b::test_two", "b::test_three"]),
    }


def _task() -> dict:
    return {
        "task_id": INSTANCE,
        "instance_id": INSTANCE,
        "image": official_image_name(INSTANCE),
        "platform": None,
        "workdir": "/testbed",
        "test_patch": "test-diff",
        "gold_patch": "gold-diff",
        "FAIL_TO_PASS": ["a::test_one"],
        "PASS_TO_PASS": ["b::test_two", "b::test_three"],
        "source": "swe-bench-lite",
    }


def test_official_image_name_escapes_double_underscore():
    assert official_image_name(INSTANCE) == (
        "swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest"
    )


def test_load_lite_tasks_normalises_rows(tmp_path):
    path = tmp_path / "lite.json"
    path.write_text(json.dumps([_row()]), encoding="utf-8")

    tasks = load_lite_tasks(path)

    assert len(tasks) == 1
    task = tasks[0]
    assert task["task_id"] == INSTANCE
    assert task["image"].endswith("astropy_1776_astropy-12907:latest")
    assert task["FAIL_TO_PASS"] == ["a::test_one"]
    assert task["PASS_TO_PASS"] == ["b::test_two", "b::test_three"]
    assert task["workdir"] == "/testbed"
    assert task["source"] == "swe-bench-lite"


def test_extract_model_patch_shapes():
    assert SWEBenchOracle._extract_model_patch({"model_patch": "d1"}) == "d1"
    event = {"events": [{"action": {"type": "apply_patch", "input": {"patch": "d2"}}}]}
    assert SWEBenchOracle._extract_model_patch(event) == "d2"
    assert SWEBenchOracle._extract_model_patch({"events": []}) is None


def test_score_routes_official_task_to_verifier():
    oracle = SWEBenchOracle()
    oracle._tasks_cache = [_task()]
    with patch.object(
        oracle, "_verify_official", return_value={"resolved": True}
    ) as verifier:
        score = oracle.score(
            OracleTask(INSTANCE, "fix"), {"model_patch": "diff"}
        )
    assert score == 100.0
    verifier.assert_called_once()


def test_verify_official_resolved_sets_verified_patch():
    oracle = SWEBenchOracle()
    with (
        patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
        patch.object(DockerSandbox, "start", return_value=True),
        patch.object(DockerSandbox, "apply_patch", return_value=(True, "ok")),
        patch.object(
            DockerSandbox, "run_pytest", return_value=(3, 0, 3, "3 passed in 0.3s")
        ),
        patch.object(DockerSandbox, "cleanup", return_value=None),
    ):
        result = oracle._verify_official(_task(), "model-diff")

    assert result["resolved"] is True
    assert result["passed"] == 3
    assert result["evidence_mode"] == EVIDENCE_MODE_VERIFIED_PATCH
    assert oracle.evidence_mode() == EVIDENCE_MODE_VERIFIED_PATCH


def test_verify_official_failed_tests_still_verified_patch():
    oracle = SWEBenchOracle()
    with (
        patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
        patch.object(DockerSandbox, "start", return_value=True),
        patch.object(DockerSandbox, "apply_patch", return_value=(True, "ok")),
        patch.object(
            DockerSandbox, "run_pytest", return_value=(1, 2, 3, "2 failed, 1 passed")
        ),
        patch.object(DockerSandbox, "cleanup", return_value=None),
    ):
        result = oracle._verify_official(_task(), "model-diff")

    assert result["resolved"] is False
    assert result["evidence_mode"] == EVIDENCE_MODE_VERIFIED_PATCH


def test_verify_official_patch_apply_failure_stays_declared():
    oracle = SWEBenchOracle()
    with (
        patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
        patch.object(DockerSandbox, "start", return_value=True),
        patch.object(
            DockerSandbox, "apply_patch", return_value=(False, "does not apply")
        ),
        patch.object(DockerSandbox, "cleanup", return_value=None),
    ):
        result = oracle._verify_official(_task(), "broken-diff")

    assert result["resolved"] is False
    assert result["evidence_mode"] == EVIDENCE_MODE_DECLARED
    assert "model_patch_apply_failed" in result["error"]


def test_verify_official_docker_unavailable_stays_declared():
    oracle = SWEBenchOracle()
    with patch(
        "mas_eval.oracle.swe_bench.check_docker", return_value=(False, "no docker")
    ):
        result = oracle._verify_official(_task(), "model-diff")

    assert result["resolved"] is False
    assert result["evidence_mode"] == EVIDENCE_MODE_DECLARED
    assert "docker unavailable" in result["error"]
