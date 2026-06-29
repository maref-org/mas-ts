"""Tests for Federation Compliance Report Formatters (MAS-TS-001 v5.0)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.scoring.compliance_formatter import (
    format_report,
    report_to_html,
    report_to_markdown,
)

SAMPLE_REPORT = {
    "report_type": "federation_compliance_report",
    "report_version": "1.0",
    "generated_at": "2026-06-12T12:00:00.000Z",
    "agents": [
        {
            "name": "Agent Alpha",
            "agent_id": "urn:agent:alpha",
            "vendor_id": "test-vendor",
            "schema_version": "1.2",
            "scores": {"D1": 95.0, "D2": 80.0, "D3": 70.0, "D4": 85.0, "D5": 75.0},
            "verdict": "PASS",
            "federation_details": {
                "trust": 0.75,
                "compatibility_matrix": 85.0,
            },
            "federation_role": "primary",
            "trust_score": 0.75,
        },
        {
            "name": "Agent Beta",
            "agent_id": "urn:agent:beta",
            "vendor_id": "another-vendor",
            "schema_version": "1.2",
            "scores": {"D1": 90.0, "D2": 75.0, "D3": 65.0, "D4": 80.0, "D5": 70.0},
            "verdict": "REVIEW",
            "federation_details": {"trust": 0.50},
            "federation_role": "secondary",
            "trust_score": 0.50,
        },
    ],
    "federation": {
        "agent_count": 2,
        "compliance_rate": "1/2",
        "overall_health": 78.5,
        "domain_averages": {"D1": 92.5, "D2": 77.5, "D3": 67.5, "D4": 82.5, "D5": 72.5},
    },
    "gaps": [
        {
            "severity": "HIGH",
            "description": "Low trust score on Agent Beta",
            "check": "trust_score",
            "affected_agents": ["urn:agent:beta"],
        },
    ],
    "recommendations": [
        "Enable trace_id audit chain on 1 agent(s)",
        "Improve trust score on Agent Beta to >=0.7",
    ],
    "summary": {
        "total_agents": 2,
        "agents_passing": 1,
        "agents_blocked": 0,
        "agents_needing_review": 1,
        "total_gaps": 1,
        "total_recommendations": 2,
        "federation_health": 78.5,
    },
}


class TestReportToMarkdown:
    def test_returns_string(self):
        md = report_to_markdown(SAMPLE_REPORT)
        assert isinstance(md, str)
        assert len(md) > 100

    def test_contains_title(self):
        md = report_to_markdown(SAMPLE_REPORT)
        assert "# Federation Compliance Report" in md

    def test_contains_summary_table(self):
        md = report_to_markdown(SAMPLE_REPORT)
        assert "Total Agents" in md
        assert "Federation Health" in md

    def test_contains_agent_names(self):
        md = report_to_markdown(SAMPLE_REPORT)
        assert "Agent Alpha" in md
        assert "Agent Beta" in md

    def test_contains_gap_section(self):
        md = report_to_markdown(SAMPLE_REPORT)
        assert "Gap Analysis" in md

    def test_contains_recommendations(self):
        md = report_to_markdown(SAMPLE_REPORT)
        assert "Recommendations" in md

    def test_score_bar_renders(self):
        md = report_to_markdown(SAMPLE_REPORT)
        assert "█" in md

    def test_empty_gaps_omitted(self):
        r = dict(SAMPLE_REPORT, gaps=[])
        md = report_to_markdown(r)
        assert "Gap Analysis" not in md

    def test_empty_recs_omitted(self):
        r = dict(SAMPLE_REPORT, recommendations=[])
        md = report_to_markdown(r)
        assert "## Recommendations" not in md

    def test_federation_overview_section(self):
        md = report_to_markdown(SAMPLE_REPORT)
        assert "Federation Overview" in md


class TestReportToHTML:
    def test_returns_string(self):
        html = report_to_html(SAMPLE_REPORT)
        assert isinstance(html, str)
        assert len(html) > 200

    def test_contains_doctype(self):
        html = report_to_html(SAMPLE_REPORT)
        assert "<!DOCTYPE html>" in html

    def test_contains_styles(self):
        html = report_to_html(SAMPLE_REPORT)
        assert "<style>" in html

    def test_contains_agent_names(self):
        html = report_to_html(SAMPLE_REPORT)
        assert "Agent Alpha" in html
        assert "Agent Beta" in html

    def test_contains_summary_cards(self):
        html = report_to_html(SAMPLE_REPORT)
        assert "summary-card" in html

    def test_contains_gaps_table(self):
        html = report_to_html(SAMPLE_REPORT)
        assert "Gap Analysis" in html

    def test_contains_recommendations_list(self):
        html = report_to_html(SAMPLE_REPORT)
        assert "<ol>" in html

    def test_empty_gaps_omitted(self):
        r = dict(SAMPLE_REPORT, gaps=[])
        html = report_to_html(r)
        assert "Gap Analysis" not in html

    def test_empty_recs_omitted(self):
        r = dict(SAMPLE_REPORT, recommendations=[])
        html = report_to_html(r)
        assert "<ol>" not in html

    def test_html_escapes_report_fields(self):
        report = dict(SAMPLE_REPORT)
        report["agents"] = [
            dict(SAMPLE_REPORT["agents"][0], name="<script>alert(1)</script>")
        ]
        report["gaps"] = [
            {
                "severity": "HIGH",
                "description": "<img src=x onerror=alert(1)>",
                "check": "<b>bad</b>",
                "affected_agents": ["<svg onload=alert(1)>"],
            }
        ]
        report["recommendations"] = ["<iframe src=javascript:alert(1)>"]
        html = report_to_html(report)
        assert "<script>alert(1)</script>" not in html
        assert "<img src=x onerror=alert(1)>" not in html
        assert "<iframe src=javascript:alert(1)>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


class TestFormatReport:
    def test_markdown_format(self):
        result = format_report(SAMPLE_REPORT, "markdown")
        assert "# Federation Compliance Report" in result

    def test_html_format(self):
        result = format_report(SAMPLE_REPORT, "html")
        assert "<!DOCTYPE html>" in result

    def test_invalid_format(self):
        import pytest

        with pytest.raises(ValueError, match="Unknown format"):
            format_report(SAMPLE_REPORT, "pdf")
