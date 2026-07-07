"""Tests for reporting modules (full_report.py, html_report.py)"""

import os
import tempfile
from pathlib import Path

from mas_eval.reporting.full_report import (
    _inline_md,
    _md_to_html,
    _read_md,
    generate_full_report,
)
from mas_eval.reporting.html_report import (
    _compliance_level_stars,
    _grade_color,
    _score_bar,
    _verdict_badge,
    generate_html_report,
    save_html_report,
)


class TestHtmlReportHelpers:
    def test_grade_color(self) -> None:
        assert _grade_color("A") == "#1a7f37"
        assert _grade_color("B") == "#9a6700"
        assert _grade_color("C") == "#bf8700"
        assert _grade_color("D") == "#cf222e"
        assert _grade_color("A+") == "#1a7f37"
        assert _grade_color("UNKNOWN") == "#cf222e"

    def test_verdict_badge(self) -> None:
        gold = _verdict_badge("GOLD")
        assert "GOLD" in gold
        assert "#d4af37" in gold

        silver = _verdict_badge("SILVER")
        assert "SILVER" in silver
        assert "#c0c0c0" in silver

        bronze = _verdict_badge("BRONZE")
        assert "BRONZE" in bronze
        assert "#cd7f32" in bronze

        fail = _verdict_badge("FAIL")
        assert "FAIL" in fail
        assert "#cf222e" in fail

    def test_score_bar(self) -> None:
        bar = _score_bar(80.0, 80.0)
        assert "width:100%" in bar
        assert "#1a7f37" in bar

        bar = _score_bar(60.0, 80.0)
        assert "#cf222e" in bar

        bar = _score_bar(70.0, 80.0)
        assert "#9a6700" in bar

    def test_compliance_level_stars(self) -> None:
        assert _compliance_level_stars("GOLD") == "⭐⭐⭐"
        assert _compliance_level_stars("SILVER") == "⭐⭐"
        assert _compliance_level_stars("BRONZE") == "⭐"
        assert _compliance_level_stars("FAIL") == "—"
        assert _compliance_level_stars("UNKNOWN") == "—"


class TestHtmlReportGeneration:
    def test_generate_html_report_basic(self) -> None:
        html = generate_html_report(
            agent_id="test-agent",
            domain_scores={"d1": 90.0, "d2": 85.0},
        )
        assert isinstance(html, str)
        assert "test-agent" in html
        assert "MAS-TS-001" in html
        assert "D1" in html
        assert "D2" in html

    def test_generate_html_report_with_findings(self) -> None:
        html = generate_html_report(
            agent_id="test-agent",
            domain_scores={"d1": 90.0},
            findings=[
                {"severity": "WARNING", "category": "test", "detail": "Test finding"},
            ],
        )
        assert "WARNING" in html
        assert "Test finding" in html

    def test_generate_html_report_with_metadata(self) -> None:
        html = generate_html_report(
            agent_id="test-agent",
            domain_scores={},
            consistency_index=0.85,
            cost_efficiency=0.75,
            execution_metadata={"duration_ms": 1234, "tests_passed": 100},
        )
        assert "0.85" in html
        assert "0.75" in html
        assert "1234" in html

    def test_save_html_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html = generate_html_report(agent_id="test-agent")
            path = save_html_report(html, os.path.join(tmpdir, "test-report.html"))
            assert os.path.exists(path)
            saved_content = Path(path).read_text()
            assert "test-agent" in saved_content


class TestFullReportHelpers:
    def test_inline_md(self) -> None:
        assert _inline_md("**bold**") == "<strong>bold</strong>"
        assert _inline_md("`code`") == "<code>code</code>"
        assert (
            _inline_md("[link](url)") == '<a href="url" style="color:#58a6ff">link</a>'
        )
        assert _inline_md("normal text") == "normal text"

    def test_md_to_html_headers(self) -> None:
        md = "# Heading 1\n## Heading 2\n### Heading 3"
        html = _md_to_html(md)
        assert "<h2>Heading 1</h2>" in html
        assert "<h2>Heading 2</h2>" in html
        assert "<h3>Heading 3</h3>" in html

    def test_md_to_html_list(self) -> None:
        md = "- Item 1\n- Item 2\n1. Ordered 1\n2. Ordered 2"
        html = _md_to_html(md)
        assert "<li>Item 1</li>" in html
        assert "<li>Item 2</li>" in html
        assert "<li>Ordered 1</li>" in html

    def test_md_to_html_table(self) -> None:
        md = "| Col1 | Col2 |\n|------|------|\n| Val1 | Val2 |"
        html = _md_to_html(md)
        assert "<table" in html
        assert "<th>Col1</th>" in html
        assert "<td>Val1</td>" in html

    def test_md_to_html_code_block(self) -> None:
        md = "```\ncode here\n```"
        html = _md_to_html(md)
        assert "<pre" in html
        assert "code here" in html

    def test_md_to_html_horizontal_rule(self) -> None:
        md = "before\n-----\nafter"
        html = _md_to_html(md)
        assert "<hr>" in html
        assert "<p>before</p>" in html
        assert "<p>after</p>" in html

    def test_read_md_not_found(self) -> None:
        result = _read_md("non_existent_file.md")
        assert "File not found" in result


class TestFullReportGeneration:
    def test_generate_full_report_basic(self) -> None:
        html = generate_full_report(
            agent_id="test-agent",
            domain_scores={"d1": 90.0, "d2": 85.0},
        )
        assert isinstance(html, str)
        assert "test-agent" in html
        assert "MAS-TS-001" in html
        assert "<!DOCTYPE html>" in html

    def test_generate_full_report_with_ci_ce(self) -> None:
        html = generate_full_report(
            agent_id="test-agent",
            domain_scores={"d1": 90.0},
            consistency_index=0.82,
            cost_efficiency=0.71,
        )
        assert "0.82" in html
        assert "0.71" in html

    def test_generate_full_report_with_metadata(self) -> None:
        html = generate_full_report(
            agent_id="test-agent",
            domain_scores={},
            execution_metadata={"duration_ms": 3456, "tests_passed": 1569},
        )
        assert "3456" in html
        assert "1569" in html
