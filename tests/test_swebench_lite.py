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
    _count,
    _parse_failed,
    _parse_traceback,
    compare_patches,
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


def test_parse_failed_extracts_test_and_reason():
    output = (
        "FAILED tests/test_x.py::test_one - assert 1 == 2\n"
        "FAILED tests/test_x.py::test_two\n"
        "1 passed\n"
    )
    assert _parse_failed(output) == [
        {"test": "tests/test_x.py::test_one", "reason": "assert 1 == 2"},
        {"test": "tests/test_x.py::test_two", "reason": ""},
    ]


def test_parse_failed_ignores_ansi_colour_and_counts():
    output = (
        "\x1b[31m\x1b[1mFAILED\x1b[0m tests/test_y.py::test_z - \x1b[1massert\x1b[0m 0\n"
        "\x1b[31m\x1b[1m1 failed\x1b[0m, \x1b[32m2 passed\x1b[0m\n"
    )
    assert _parse_failed(output) == [
        {"test": "tests/test_y.py::test_z", "reason": "assert 0"}
    ]
    assert _count(output, "passed") == 2
    assert _count(output, "failed") == 1


def test_parse_traceback_finds_assertion_site():
    output = (
        "F                                                                        [100%]\n"
        "=================================== FAILURES ===================================\n"
        "/testbed/astropy/wcs/tests/test_wcs.py:1109: AssertionError:\n"
        "1 failed, 1 warnings in 0.33 seconds\n"
    )
    assert _parse_traceback(output) == [
        {
            "location": "/testbed/astropy/wcs/tests/test_wcs.py:1109",
            "reason": "AssertionError:",
        }
    ]


def test_compare_patches_reports_overlap_and_gaps():
    model = "diff --git a/pkg/a.py b/pkg/a.py\n--- a/pkg/a.py\n+++ b/pkg/a.py\n"
    gold = (
        "diff --git a/pkg/a.py b/pkg/a.py\n--- a/pkg/a.py\n+++ b/pkg/a.py\n"
        "diff --git a/pkg/b.py b/pkg/b.py\n--- a/pkg/b.py\n+++ b/pkg/b.py\n"
    )
    diff = compare_patches(model, gold)
    assert diff["overlap"] == ["pkg/a.py"]
    assert diff["only_gold"] == ["pkg/b.py"]
    assert diff["only_model"] == []


def test_diagnose_instance_reports_failing_test_and_patch_gap():
    oracle = SWEBenchOracle()
    oracle._tasks_cache = [_task()]
    pytest_output = "FAILED a::test_one - assert 0 == 1\n1 failed, 2 passed in 0.1s\n"
    with (
        patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
        patch.object(DockerSandbox, "start", return_value=True),
        patch.object(DockerSandbox, "apply_patch", return_value=(True, "ok")),
        patch.object(
            DockerSandbox, "run_pytest", return_value=(2, 1, 3, pytest_output)
        ),
        patch.object(DockerSandbox, "cleanup", return_value=None),
    ):
        result = oracle.diagnose_instance(INSTANCE, "diff --git a/other.py b/other.py\n")

    assert result["failed"] == 1
    assert result["failing"] == [{"test": "a::test_one", "reason": "assert 0 == 1"}]
    assert result["patch_diff"]["only_model"] == ["other.py"]
    assert result["error"] == ""
    # Diagnosis must not move the evidence claim.
    assert oracle.evidence_mode() == EVIDENCE_MODE_DECLARED


def test_diagnose_instance_patch_failure_is_reported():
    oracle = SWEBenchOracle()
    oracle._tasks_cache = [_task()]
    with (
        patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
        patch.object(DockerSandbox, "start", return_value=True),
        patch.object(
            DockerSandbox, "apply_patch", return_value=(False, "does not apply")
        ),
        patch.object(DockerSandbox, "cleanup", return_value=None),
    ):
        result = oracle.diagnose_instance(INSTANCE, "broken")

    assert result["error"].startswith("model_patch_apply_failed")
    assert result["failing"] == []
