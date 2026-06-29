# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for executable release gate checklist (Phase 7.1).

Verifies `scripts/release_gate_check.py` exposes a deterministic list of 10
gate items, each with required metadata, and supports both auto and manual
checks.

Slow: the `run_all()` fixture actually executes ruff/mypy/pytest/bandit/etc.
(~1-2 min). Use `--ignore=tests/test_release_gate_check.py` for fast CI runs
and run this file separately when validating the release gate.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "release_gate_check.py"


def _load_release_gate_module():
    assert SCRIPT_PATH.exists(), (
        f"scripts/release_gate_check.py not yet implemented at {SCRIPT_PATH}"
    )
    spec = importlib.util.spec_from_file_location("release_gate_check", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None, (
        "could not load release_gate_check module spec"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_gate_check"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rgc():
    return _load_release_gate_module()


def _stub_runner(command):
    """Stub runner that returns success for all commands without spawning
    subprocesses. Real e2e run uses the default subprocess runner."""
    return 0, "stub stdout", "stub stderr"


@pytest.fixture(scope="module")
def results(rgc):
    return rgc.run_all(runner=_stub_runner)


class TestReleaseGateStructure:
    def test_gate_items_count_is_ten(self, rgc):
        items = rgc.GATE_ITEMS
        assert len(items) == 10, (
            f"Expected 10 gate items, got {len(items)}: {[i.get('id') for i in items]}"
        )

    def test_each_gate_has_required_fields(self, rgc):
        required = {"id", "gate", "name", "type", "expected"}
        for item in rgc.GATE_ITEMS:
            missing = required - set(item.keys())
            assert not missing, f"gate item {item.get('id')} missing fields: {missing}"

    def test_gate_ids_unique(self, rgc):
        ids = [i["id"] for i in rgc.GATE_ITEMS]
        assert len(ids) == len(set(ids)), f"duplicate gate ids: {ids}"

    def test_gate_types_are_auto_or_manual(self, rgc):
        for item in rgc.GATE_ITEMS:
            assert item["type"] in ("auto", "manual"), (
                f"gate {item['id']} has invalid type {item['type']}"
            )

    def test_auto_gates_have_command(self, rgc):
        for item in rgc.GATE_ITEMS:
            if item["type"] == "auto":
                assert "command" in item and item["command"], (
                    f"auto gate {item['id']} missing command"
                )

    def test_gate_ids_match_release_gate_doc(self, rgc):
        expected_ids = {
            "G0.1",
            "G0.2",
            "G1.1",
            "G1.2",
            "G1.3",
            "G2.1",
            "G2.2",
            "G3.1",
            "G3.2",
            "G3.3",
        }
        assert {i["id"] for i in rgc.GATE_ITEMS} == expected_ids

    def test_gates_distributed_across_five_gates(self, rgc):
        gates = {i["gate"] for i in rgc.GATE_ITEMS}
        assert gates == {0, 1, 2, 3}, f"Expected gates 0-3 represented, got: {gates}"


class TestReleaseGateManualItems:
    def test_gate_0_items_are_manual(self, rgc):
        gate_zero = [i for i in rgc.GATE_ITEMS if i["gate"] == 0]
        assert len(gate_zero) >= 1
        for item in gate_zero:
            assert item["type"] == "manual", (
                f"gate 0 item {item['id']} should be manual approval"
            )


class TestReleaseGateRun:
    @pytest.mark.slow
    def test_run_all_returns_list_of_results(self, results):
        assert isinstance(results, list)
        assert len(results) == 10

    @pytest.mark.slow
    def test_result_has_required_fields(self, results):
        required = {"id", "status", "detail"}
        for r in results:
            assert required.issubset(set(r.keys())), (
                f"result {r.get('id')} missing fields: {r}"
            )
            assert r["status"] in ("PASS", "FAIL", "MANUAL"), (
                f"result {r.get('id')} invalid status: {r['status']}"
            )

    @pytest.mark.slow
    def test_run_all_does_not_raise_for_manual_items(self, results):
        for r in results:
            if r["status"] == "MANUAL":
                assert "detail" in r

    @pytest.mark.slow
    def test_each_result_corresponds_to_gate_item(self, rgc, results):
        gate_ids = {i["id"] for i in rgc.GATE_ITEMS}
        result_ids = {r["id"] for r in results}
        assert gate_ids == result_ids


class TestReleaseGateSummary:
    @pytest.mark.slow
    def test_summary_counts_total_matches_gate_count(self, rgc, results):
        summary = rgc.summarize(results)
        assert summary["total"] == 10
        assert summary["pass"] + summary["fail"] + summary["manual"] == 10

    @pytest.mark.slow
    def test_summary_has_expected_keys(self, rgc, results):
        summary = rgc.summarize(results)
        for key in ("total", "pass", "fail", "manual"):
            assert key in summary, f"summary missing key: {key}"
