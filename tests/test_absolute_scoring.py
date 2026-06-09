# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 Absolute Scoring Model."""

import pytest

from mas_eval.scoring.absolute import (
    DOMAIN_WEIGHTS,
    SEVERITY_PENALTIES,
    compute_overall,
    determine_verdict,
    grade_to_emoji,
    score_domain,
    score_to_grade,
)


class TestDomainWeights:
    def test_total_weight(self):
        assert sum(DOMAIN_WEIGHTS.values()) == pytest.approx(1.0)

    def test_has_all_domains(self):
        expected = {"d1", "d2", "d3", "d4", "d5"}
        assert set(DOMAIN_WEIGHTS.keys()) == expected

    def test_d2_and_d3_highest(self):
        assert DOMAIN_WEIGHTS["d2"] == 0.25
        assert DOMAIN_WEIGHTS["d3"] == 0.25


class TestSeverityPenalties:
    def test_critical_penalty(self):
        assert SEVERITY_PENALTIES["CRITICAL"] == -25

    def test_high_penalty(self):
        assert SEVERITY_PENALTIES["HIGH"] == -15

    def test_warning_penalty(self):
        assert SEVERITY_PENALTIES["WARNING"] == -5

    def test_info_no_penalty(self):
        assert SEVERITY_PENALTIES["INFO"] == 0


class TestScoreDomain:
    def test_raw_score_unchanged_no_findings(self):
        assert score_domain(85) == 85.0

    def test_critical_penalty_applied(self):
        result = score_domain(100, [{"severity": "CRITICAL"}])
        assert result == 75.0

    def test_multiple_penalties(self):
        result = score_domain(
            100,
            [
                {"severity": "CRITICAL"},
                {"severity": "HIGH"},
            ],
        )
        assert result == 60.0

    def test_floor_at_zero(self):
        result = score_domain(10, [{"severity": "CRITICAL"}])
        assert result == 0.0

    def test_ceiling_at_100(self):
        result = score_domain(110)
        assert result == 100.0

    def test_empty_findings(self):
        assert score_domain(75, []) == 75.0

    def test_mixed_severity(self):
        result = score_domain(
            90,
            [
                {"severity": "HIGH"},
                {"severity": "WARNING"},
                {"severity": "INFO"},
            ],
        )
        assert result == 70.0

    def test_unknown_severity_defaults_info(self):
        result = score_domain(80, [{"severity": "UNKNOWN"}])
        assert result == 80.0


class TestScoreToGrade:
    def test_a_plus(self):
        assert score_to_grade(98) == "A+"

    def test_a(self):
        assert score_to_grade(95) == "A"

    def test_a_minus(self):
        assert score_to_grade(91) == "A-"

    def test_b_plus(self):
        assert score_to_grade(88) == "B+"

    def test_b(self):
        assert score_to_grade(84) == "B"

    def test_b_minus(self):
        assert score_to_grade(81) == "B-"

    def test_c_plus(self):
        assert score_to_grade(78) == "C+"

    def test_c(self):
        assert score_to_grade(74) == "C"

    def test_c_minus(self):
        assert score_to_grade(71) == "C-"

    def test_d_plus(self):
        assert score_to_grade(68) == "D+"

    def test_d(self):
        assert score_to_grade(64) == "D"

    def test_d_minus(self):
        assert score_to_grade(61) == "D-"

    def test_f(self):
        assert score_to_grade(59) == "F"

    def test_f_zero(self):
        assert score_to_grade(0) == "F"

    def test_exact_boundaries(self):
        assert score_to_grade(97) == "A+"
        assert score_to_grade(93) == "A"
        assert score_to_grade(90) == "A-"
        assert score_to_grade(60) == "D-"


class TestGradeToEmoji:
    def test_a_grades_green(self):
        assert grade_to_emoji("A+") == "🟢"
        assert grade_to_emoji("A") == "🟢"
        assert grade_to_emoji("A-") == "🟢"

    def test_b_grades_green_or_yellow(self):
        assert grade_to_emoji("B+") == "🟢"
        assert grade_to_emoji("B") == "🟢"
        assert grade_to_emoji("B-") == "🟡"

    def test_c_grades_yellow(self):
        assert grade_to_emoji("C+") == "🟡"
        assert grade_to_emoji("C") == "🟡"
        assert grade_to_emoji("C-") == "🟡"

    def test_d_grades_orange(self):
        assert grade_to_emoji("D+") == "🟠"
        assert grade_to_emoji("D") == "🟠"
        assert grade_to_emoji("D-") == "🟠"

    def test_f_red(self):
        assert grade_to_emoji("F") == "🔴"

    def test_unknown_white(self):
        assert grade_to_emoji("Z") == "⚪"


class TestComputeOverall:
    def test_single_domain(self):
        assert compute_overall(d1=100) == 100.0

    def test_all_domains_equal(self):
        result = compute_overall(d1=80, d2=80, d3=80, d4=80, d5=80)
        assert result == 80.0

    def test_weighted_average(self):
        result = compute_overall(d1=100, d2=0, d3=0, d4=0, d5=0)
        assert result == pytest.approx(10.0, abs=0.01)

    def test_partial_domains(self):
        result = compute_overall(d2=100, d3=100)
        assert result == 100.0

    def test_no_domains(self):
        assert compute_overall() == 0.0

    def test_mixed_scores(self):
        result = compute_overall(d1=90, d2=80, d3=70, d4=60, d5=50)
        assert 60 < result < 80


class TestDetermineVerdict:
    def test_approved_high_score_no_critical(self):
        assert determine_verdict(85, [{"severity": "HIGH"}]) == "APPROVED"

    def test_approved_high_score_no_findings(self):
        assert determine_verdict(85) == "APPROVED"

    def test_blocked_by_critical(self):
        assert determine_verdict(85, [{"severity": "CRITICAL"}]) == "CONDITIONAL"

    def test_conditional_mid_score(self):
        assert determine_verdict(65, [{"severity": "WARNING"}]) == "CONDITIONAL"

    def test_conditional_mid_score_no_issues(self):
        assert determine_verdict(60) == "CONDITIONAL"

    def test_blocked_low_score(self):
        assert determine_verdict(40) == "BLOCKED"

    def test_blocked_low_score_with_critical(self):
        assert determine_verdict(40, [{"severity": "CRITICAL"}]) == "BLOCKED"

    def test_approved_edge_case(self):
        assert determine_verdict(70) == "APPROVED"

    def test_conditional_edge_case(self):
        assert determine_verdict(70, [{"severity": "CRITICAL"}]) == "CONDITIONAL"

    def test_blocked_edge_case(self):
        assert determine_verdict(49) == "BLOCKED"
