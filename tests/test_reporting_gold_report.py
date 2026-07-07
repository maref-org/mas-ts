# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for mas_eval.reporting.gold_report module."""

import json
import os
import tempfile

from mas_eval.reporting.gold_report import (
    generate_report,
    load_report,
    save_report,
)


class TestGenerateReport:
    def test_basic_report_structure(self):
        report = generate_report(
            agent_id="test-agent-001",
            domain_scores={"d1": 95.0, "d2": 88.0, "d3": 92.0, "d4": 85.0, "d5": 90.0},
            level="L3",
        )
        assert "certificate" in report
        assert "dimensions" in report
        assert "findings" in report
        assert "execution" in report

    def test_certificate_fields(self):
        report = generate_report(
            agent_id="test-agent-001",
            domain_scores={"d1": 100.0, "d2": 95.0, "d3": 90.0, "d4": 85.0, "d5": 80.0},
            consistency_index=0.8,
            cost_efficiency=0.7,
        )
        cert = report["certificate"]
        assert cert["agent_id"] == "test-agent-001"
        assert isinstance(cert["score"], float)
        assert cert["grade"] in (
            "A+",
            "A",
            "A-",
            "B+",
            "B",
            "B-",
            "C+",
            "C",
            "C-",
            "D+",
            "D",
            "D-",
            "F",
        )
        assert cert["ci"] == 0.8
        assert cert["ce"] == 0.7
        assert "cert_id" in cert
        assert "valid_until" in cert
        assert "badge" in cert

    def test_dimensions_in_report(self):
        domain_scores = {"d1": 95.0, "d2": 88.0, "d3": 92.0}
        report = generate_report(agent_id="a1", domain_scores=domain_scores)
        dims = report["dimensions"]
        assert set(dims.keys()) == {"d1", "d2", "d3"}
        for k in dims:
            assert "score" in dims[k]
            assert "threshold" in dims[k]
            assert "passed" in dims[k]

    def test_findings_included(self):
        findings = [
            {"severity": "CRITICAL", "category": "security", "detail": "Test finding"},
            {
                "severity": "WARNING",
                "category": "performance",
                "detail": "Slow response",
            },
        ]
        report = generate_report(
            agent_id="a1",
            domain_scores={"d1": 90.0},
            findings=findings,
        )
        assert len(report["findings"]) == 2
        assert report["findings"][0]["severity"] == "CRITICAL"

    def test_execution_metadata(self):
        meta = {
            "duration_ms": 1234,
            "tests_passed": 100,
            "tests_total": 100,
            "coverage_pct": 95.5,
        }
        report = generate_report(
            agent_id="a1",
            domain_scores={"d1": 90.0},
            execution_metadata=meta,
        )
        exec_data = report["execution"]
        assert exec_data["duration_ms"] == 1234
        assert exec_data["tests_passed"] == 100
        assert exec_data["tests_total"] == 100
        assert exec_data["coverage_pct"] == 95.5

    def test_report_with_ci_and_ce(self):
        report = generate_report(
            agent_id="a1",
            domain_scores={"d1": 95.0, "d2": 90.0, "d3": 85.0, "d4": 80.0, "d5": 75.0},
            consistency_index=0.9,
            cost_efficiency=0.8,
        )
        assert report["certificate"]["ci"] == 0.9
        assert report["certificate"]["ce"] == 0.8


class TestSaveLoadReport:
    def test_save_and_load(self):
        report = generate_report(
            agent_id="test-save",
            domain_scores={"d1": 90.0},
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            saved_path = save_report(report, tmp_path)
            assert os.path.exists(saved_path)

            loaded = load_report(tmp_path)
            assert loaded["certificate"]["agent_id"] == "test-save"
            assert loaded["certificate"]["score"] == report["certificate"]["score"]
        finally:
            os.unlink(tmp_path)

    def test_report_json_serializable(self):
        report = generate_report(
            agent_id="json-test",
            domain_scores={"d1": 85.0, "d2": 90.0},
            findings=[{"severity": "INFO", "category": "test", "detail": "check"}],
        )
        dumped = json.dumps(report)
        loaded = json.loads(dumped)
        assert loaded["certificate"]["agent_id"] == "json-test"
        assert len(loaded["findings"]) == 1
