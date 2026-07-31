# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for mas_eval.reporting.dashboard module."""

from mas_eval.reporting.dashboard import (
    render_dashboard,
    render_domain_table,
)
from mas_eval.reporting.gold_report import generate_report


def _sample_report():
    return generate_report(
        agent_id="test-agent",
        domain_scores={"d1": 95.0, "d2": 88.0, "d3": 92.0, "d4": 78.0, "d5": 85.0},
        level="L3",
        consistency_index=0.82,
        cost_efficiency=0.71,
        findings=[
            {
                "severity": "INFO",
                "category": "compliance",
                "detail": "All checks passed",
            },
            {
                "severity": "WARNING",
                "category": "performance",
                "detail": "Latency above threshold",
            },
        ],
        execution_metadata={
            "duration_ms": 1234,
            "tests_passed": 100,
            "tests_total": 100,
            "coverage_pct": 93.77,
        },
    )


class TestRenderDashboard:
    def test_dashboard_contains_badge(self):
        report = _sample_report()
        output = render_dashboard(report)
        assert "MAS-TS-001" in output
        assert "Gold Standard" in output or "GOLD" in output

    def test_dashboard_contains_domain_scores(self):
        output = render_dashboard(_sample_report())
        for dom in ("d1", "d2", "d3", "d4", "d5"):
            assert dom in output

    def test_dashboard_contains_certificate_info(self):
        output = render_dashboard(_sample_report())
        assert "Overall Score" in output
        assert "Grade" in output
        assert "Verdict" in output

    def test_dashboard_contains_findings_table(self):
        output = render_dashboard(_sample_report())
        assert "Findings" in output
        assert "INFO" in output
        assert "WARNING" in output

    def test_dashboard_contains_execution_metadata(self):
        output = render_dashboard(_sample_report())
        assert "Duration" in output
        assert "Tests" in output
        assert "Coverage" in output
        assert "93.77" in output

    def test_dashboard_empty_findings(self):
        report = generate_report(
            agent_id="a1",
            domain_scores={"d1": 90.0},
        )
        output = render_dashboard(report)
        assert "Findings" not in output

    def test_dashboard_no_ci_ce(self):
        report = generate_report(
            agent_id="a1",
            domain_scores={"d1": 90.0},
        )
        output = render_dashboard(report)
        assert "Consistency Index" not in output
        assert "Cost Efficiency" not in output


class TestRenderDomainTable:
    def test_domain_table_has_headers(self):
        output = render_domain_table(_sample_report())
        assert "Dom" in output
        assert "Score" in output
        assert "Threshold" in output
        assert "Status" in output

    def test_domain_table_contains_all_domains(self):
        output = render_domain_table(_sample_report())
        for dom in ("d1", "d2", "d3", "d4", "d5"):
            assert dom in output

    def test_domain_table_compact(self):
        report = generate_report(agent_id="a1", domain_scores={"d1": 100.0, "d2": 80.0})
        output = render_domain_table(report)
        assert "d1" in output
        assert "d2" in output
        assert output.count("┌") >= 1
        assert output.count("└") >= 1
