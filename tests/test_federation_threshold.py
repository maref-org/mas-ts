# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for federation scan threshold policy parser (Phase 7.2).

Verifies `scripts/federation_threshold.py` deterministically parses a
federation scan JSON report and applies the v0.4.0 threshold:
    - blocked_count <= MAX_BLOCKED (default 0)
    - critical_count == 0  (or ALLOW_CRITICAL=true)
    - compliance_rate >= MIN_PASSING/total  (default 3/5)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "federation_threshold.py"


def _load_threshold_module():
    assert SCRIPT_PATH.exists(), (
        f"scripts/federation_threshold.py not yet implemented at {SCRIPT_PATH}"
    )
    spec = importlib.util.spec_from_file_location("federation_threshold", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["federation_threshold"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ft():
    return _load_threshold_module()


def _v1_report(blocked=0, critical=0, total=5, score=50.0):
    """Build a v1-style federation report (mas_full_run --multi-vendor).
    CRITICAL findings live in a top-level `findings` list (cleaner contract
    than per-agent findings)."""
    agents = {}
    for i in range(total):
        verdict = "NON-COMPLIANT (blocked)" if i < blocked else "COMPLIANT"
        agents[f"agent_{i}"] = {
            "d1": {"verdict": verdict, "score": 80.0},
            "findings": [],
        }
    return {
        "agents": agents,
        "federation_score": score,
        "findings": [{"severity": "CRITICAL"} for _ in range(critical)],
    }


def _v2_report(blocked=0, critical=0, total=5, score=50.0):
    """Build a v2-style federation report (run_v4_federation_scan_v2)."""
    findings = [{"severity": "CRITICAL"} for _ in range(critical)]
    return {
        "results": {f"a{i}": {"d1": {"score": 80.0}} for i in range(total)},
        "federation": {
            "d4_federation": {
                "score": score,
                "findings": findings,
                "summary": {"total_findings": len(findings)},
            }
        },
    }


class TestParseFederationReport:
    def test_parse_v1_style_report_returns_blocked_count(self, ft):
        report = _v1_report(blocked=2, critical=0, total=5)
        parsed = ft.parse_federation_report(report)
        assert parsed["blocked_count"] == 2
        assert parsed["total_agents"] == 5
        assert parsed["compliance_rate"] == 3

    def test_parse_v1_style_report_critical_count(self, ft):
        report = _v1_report(blocked=2, critical=3, total=5)
        parsed = ft.parse_federation_report(report)
        assert parsed["critical_count"] == 3

    def test_parse_v2_style_report_returns_blocked_zero(self, ft):
        report = _v2_report(blocked=0, critical=0, total=5, score=25.1)
        parsed = ft.parse_federation_report(report)
        assert parsed["blocked_count"] == 0
        assert parsed["federation_score"] == 25.1

    def test_parse_v2_style_report_critical_count(self, ft):
        report = _v2_report(blocked=0, critical=4, total=5)
        parsed = ft.parse_federation_report(report)
        assert parsed["critical_count"] == 4

    def test_parse_handles_missing_federation_block(self, ft):
        report = {"agents": {"a1": {"d1": {"verdict": "COMPLIANT"}}}}
        parsed = ft.parse_federation_report(report)
        assert parsed["blocked_count"] == 0
        assert parsed["critical_count"] == 0


class TestMeetsThreshold:
    def test_passes_when_zero_blocked_zero_critical(self, ft):
        report = _v1_report(blocked=0, critical=0, total=5)
        result = ft.meets_threshold(ft.parse_federation_report(report))
        assert result["meets"] is True

    def test_fails_when_blocked_exceeds_max(self, ft):
        report = _v1_report(blocked=2, critical=0, total=5)
        result = ft.meets_threshold(ft.parse_federation_report(report), max_blocked=1)
        assert result["meets"] is False
        assert "blocked_count" in result["reason"]

    def test_passes_with_documented_exceptions(self, ft):
        report = _v1_report(blocked=2, critical=0, total=5)
        result = ft.meets_threshold(ft.parse_federation_report(report), max_blocked=2)
        assert result["meets"] is True

    def test_fails_when_critical_present(self, ft):
        report = _v1_report(blocked=0, critical=1, total=5)
        result = ft.meets_threshold(ft.parse_federation_report(report))
        assert result["meets"] is False
        assert "critical" in result["reason"]

    def test_passes_critical_when_allow_critical(self, ft):
        report = _v1_report(blocked=0, critical=2, total=5)
        result = ft.meets_threshold(
            ft.parse_federation_report(report), allow_critical=True
        )
        assert result["meets"] is True

    def test_fails_when_compliance_rate_below_min(self, ft):
        report = _v1_report(blocked=4, critical=0, total=5)  # 1 passing
        result = ft.meets_threshold(
            ft.parse_federation_report(report),
            max_blocked=4,
            min_passing=3,
        )
        assert result["meets"] is False
        assert "passing_count" in result["reason"]

        report2 = _v1_report(blocked=2, critical=0, total=5)  # 3 passing
        result2 = ft.meets_threshold(
            ft.parse_federation_report(report2),
            max_blocked=2,
            min_passing=3,
        )
        assert result2["meets"] is True


class TestThresholdDefaults:
    def test_default_max_blocked_is_zero(self, ft):
        assert ft.DEFAULT_MAX_BLOCKED == 0

    def test_default_min_passing_is_three(self, ft):
        assert ft.DEFAULT_MIN_PASSING == 3

    def test_default_allow_critical_is_false(self, ft):
        assert ft.DEFAULT_ALLOW_CRITICAL is False


class TestMainEntryPoint:
    def test_main_returns_zero_when_meets_threshold(self, ft, tmp_path, monkeypatch):
        report = _v2_report(blocked=0, critical=0, total=5, score=50.0)
        report_path = tmp_path / "federation-scan.json"
        report_path.write_text(json.dumps(report))
        rc = ft.main([str(report_path)])
        assert rc == 0

    def test_main_returns_one_when_blocked_exceeds(self, ft, tmp_path):
        report = _v1_report(blocked=2, critical=0, total=5)
        report_path = tmp_path / "federation-scan.json"
        report_path.write_text(json.dumps(report))
        rc = ft.main([str(report_path)])
        assert rc == 1

    def test_main_max_blocked_env_override(self, ft, tmp_path, monkeypatch):
        report = _v1_report(blocked=2, critical=0, total=5)
        report_path = tmp_path / "federation-scan.json"
        report_path.write_text(json.dumps(report))
        rc = ft.main([str(report_path), "--max-blocked", "2"])
        assert rc == 0
