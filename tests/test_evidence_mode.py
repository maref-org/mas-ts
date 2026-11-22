# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Evidence-mode contract tests (P0-2 option A).

The harness must never present caller-supplied artifacts as proof that an agent
performed a task. Every result carries an explicit ``evidence_mode`` so reports
and consumers can tell the difference.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from api.schemas import EvaluationResponse
from mas_eval.evidence import (
    CURRENT_EVIDENCE_MODE,
    EVIDENCE_MODE_DECLARED,
    EVIDENCE_MODE_LIVE,
    EVIDENCE_MODE_VERIFIED_PATCH,
    VALID_EVIDENCE_MODES,
    strongest_evidence_mode,
)
from mas_eval.harness.aggregation import aggregate_level, compute_gold_report
from mas_eval.harness.l0_fast_screen import run_l0_fast_screen
from mas_eval.oracle.swe_bench import SWEBenchOracle

ROOT = Path(__file__).parent.parent
CARD_PATH = next((ROOT / "mas_eval" / "data" / "sample_cards").glob("*_athena_card.json"))


def _load_card() -> dict:
    return json.loads(CARD_PATH.read_text(encoding="utf-8"))


def test_evidence_mode_constants():
    assert EVIDENCE_MODE_DECLARED == "declared_input"
    assert EVIDENCE_MODE_VERIFIED_PATCH == "verified_patch"
    assert EVIDENCE_MODE_LIVE == "live_run"
    assert VALID_EVIDENCE_MODES == {
        EVIDENCE_MODE_DECLARED,
        EVIDENCE_MODE_VERIFIED_PATCH,
        EVIDENCE_MODE_LIVE,
    }
    assert CURRENT_EVIDENCE_MODE in VALID_EVIDENCE_MODES


def test_strongest_evidence_mode_ranking():
    assert (
        strongest_evidence_mode([EVIDENCE_MODE_DECLARED, EVIDENCE_MODE_VERIFIED_PATCH])
        == EVIDENCE_MODE_VERIFIED_PATCH
    )
    assert (
        strongest_evidence_mode([EVIDENCE_MODE_VERIFIED_PATCH, EVIDENCE_MODE_LIVE])
        == EVIDENCE_MODE_LIVE
    )
    assert strongest_evidence_mode([]) == EVIDENCE_MODE_DECLARED
    assert strongest_evidence_mode(["bogus"]) == EVIDENCE_MODE_DECLARED


def test_l0_result_declares_evidence_mode():
    result = run_l0_fast_screen(_load_card(), as_of_date="2026-11-22")
    assert result["evidence_mode"] == EVIDENCE_MODE_DECLARED


def test_aggregate_level_declares_evidence_mode():
    domain_results = {
        "d1": {"score": 100.0, "findings": []},
        "d2": {"score": 90.0, "findings": []},
        "d3": {"score": 90.0, "findings": []},
    }
    result = aggregate_level("L1", "Standard", 0.0, domain_results)
    assert result["evidence_mode"] == EVIDENCE_MODE_DECLARED


def test_gold_report_declares_evidence_mode():
    domain_results = {
        "d1": {"score": 100.0, "findings": []},
        "d2": {"score": 90.0, "findings": []},
        "d3": {"score": 90.0, "findings": []},
        "d4": {"score": 90.0, "findings": []},
        "d5": {"score": 90.0, "findings": []},
    }
    result = compute_gold_report(domain_results)
    assert result["evidence_mode"] == EVIDENCE_MODE_DECLARED


def test_api_schema_exposes_evidence_mode():
    model = EvaluationResponse(
        level="L0",
        name="Fast-Screen",
        status="PASS",
        elapsed_seconds=1.0,
        evidence_mode=EVIDENCE_MODE_DECLARED,
    )
    assert model.evidence_mode == EVIDENCE_MODE_DECLARED


def test_aggregate_level_uses_strongest_domain_evidence():
    domain_results = {
        "d1": {"score": 100.0, "findings": [], "evidence_mode": "declared_input"},
        "d2": {"score": 90.0, "findings": [], "evidence_mode": "verified_patch"},
        "d3": {"score": 90.0, "findings": []},
    }
    result = aggregate_level("L1", "Standard", 0.0, domain_results)
    assert result["evidence_mode"] == EVIDENCE_MODE_VERIFIED_PATCH


def _swe_task():
    return {
        "task_id": "unit-task",
        "repo": "local/fixture",
        "problem_statement": "fix add",
        "file_path": "/workspace/calc.py",
        "test_command": "python /workspace/test_calc.py",
        "expected_old_str": "return a-b",
        "expected_new_str": "return a+b",
        "golden_trajectory": {"events": []},
        "setup_commands": [],
    }


_TRAJECTORY = [
    {
        "action": {
            "type": "file_write",
            "input": {"path": "/workspace/calc.py", "content": "def add(a, b):\n    return a + b\n"},
        }
    }
]


def test_swe_bench_simulated_patch_stays_declared():
    oracle = SWEBenchOracle()
    oracle._tasks_cache = [_swe_task()]
    from mas_eval.oracle.oracle_base import OracleTask

    with patch("mas_eval.oracle.swe_bench.check_docker", return_value=(False, "no")):
        oracle.score(OracleTask("unit-task", "fix add"), _TRAJECTORY)
    assert oracle.evidence_mode() == EVIDENCE_MODE_DECLARED


def test_swe_bench_real_docker_path_reports_verified_patch():
    from mas_eval.oracle.oracle_base import OracleTask
    from mas_eval.oracle.swe_bench import DockerSandbox

    oracle = SWEBenchOracle()
    oracle._tasks_cache = [_swe_task()]

    with (
        patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
        patch.object(DockerSandbox, "start", return_value=True),
        patch.object(DockerSandbox, "write_file", return_value=("", "", 0)),
        patch.object(DockerSandbox, "run_tests", return_value=(2, 2)),
        patch.object(DockerSandbox, "cleanup", return_value=None),
    ):
        score = oracle.score(OracleTask("unit-task", "fix add"), _TRAJECTORY)

    assert score == 100.0
    assert oracle.evidence_mode() == EVIDENCE_MODE_VERIFIED_PATCH


def test_swe_bench_failed_sandbox_falls_back_to_declared():
    from mas_eval.oracle.oracle_base import OracleTask
    from mas_eval.oracle.swe_bench import DockerSandbox

    oracle = SWEBenchOracle()
    oracle._tasks_cache = [_swe_task()]

    with (
        patch("mas_eval.oracle.swe_bench.check_docker", return_value=(True, "ok")),
        patch.object(DockerSandbox, "start", return_value=False),
    ):
        oracle.score(OracleTask("unit-task", "fix add"), _TRAJECTORY)

    assert oracle.evidence_mode() == EVIDENCE_MODE_DECLARED
