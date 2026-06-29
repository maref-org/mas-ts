# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 Absolute Scoring Model."""

import pytest

from mas_eval.scoring.absolute import (
    DOMAIN_WEIGHTS,
    GOLD_DOMAIN_WEIGHTS,
    SEVERITY_PENALTIES,
    compute_gold_overall,
    compute_overall,
    determine_gold_verdict,
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
        result = score_domain(100, [{"severity": "CRITICAL"}], apply_penalties=True)
        assert result == 75.0

    def test_multiple_penalties(self):
        result = score_domain(
            100,
            [
                {"severity": "CRITICAL"},
                {"severity": "HIGH"},
            ],
            apply_penalties=True,
        )
        assert result == 60.0

    def test_floor_at_zero(self):
        result = score_domain(10, [{"severity": "CRITICAL"}], apply_penalties=True)
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
            apply_penalties=True,
        )
        assert result == 70.0

    def test_unknown_severity_defaults_info(self):
        result = score_domain(80, [{"severity": "UNKNOWN"}], apply_penalties=True)
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


class TestScoreDomainNoDoubleDeduction:
    """Phase 6.1: domain scores already incorporate findings; scoring layer must not
    re-apply SEVERITY_PENALTIES unless explicitly requested via apply_penalties=True."""

    def test_findings_not_applied_by_default(self):
        result = score_domain(85, [{"severity": "CRITICAL"}])
        assert result == 85.0

    def test_mixed_severity_findings_ignored_by_default(self):
        result = score_domain(
            90,
            [
                {"severity": "HIGH"},
                {"severity": "WARNING"},
                {"severity": "INFO"},
            ],
        )
        assert result == 90.0

    def test_explicit_opt_in_applies_penalties(self):
        result = score_domain(85, [{"severity": "CRITICAL"}], apply_penalties=True)
        assert result == 60.0

    def test_explicit_opt_in_mixed_severity(self):
        result = score_domain(
            90,
            [
                {"severity": "HIGH"},
                {"severity": "WARNING"},
                {"severity": "INFO"},
            ],
            apply_penalties=True,
        )
        assert result == 70.0

    def test_apply_penalties_default_is_false(self):
        import inspect

        sig = inspect.signature(score_domain)
        assert sig.parameters["apply_penalties"].default is False

    def test_aggregation_does_not_double_deduct(self):
        from mas_eval.harness.aggregation import aggregate_level

        domain_results = {
            "d1": {
                "score": 85,
                "findings": [{"severity": "CRITICAL", "category": "test"}],
                "domain": "D1",
            },
        }
        agg = aggregate_level(
            level="L1",
            name="test",
            start_time=0.0,
            domain_results=domain_results,
        )
        assert agg["score"] == 85.0
        assert agg["domain_scores"]["d1"] == 85.0


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


# ═══════════════════════════════════════════════════════════════
# Gold Standard Scoring tests (v3.0-GA)
# ═══════════════════════════════════════════════════════════════


class TestGoldDomainWeights:
    def test_gold_total_weight(self):
        assert sum(GOLD_DOMAIN_WEIGHTS.values()) == pytest.approx(1.0)

    def test_gold_has_all_domains(self):
        expected = {"d1", "d2", "d3", "d4", "d5"}
        assert set(GOLD_DOMAIN_WEIGHTS.keys()) == expected

    def test_gold_d4_d5_highest(self):
        assert GOLD_DOMAIN_WEIGHTS["d4"] == 0.25
        assert GOLD_DOMAIN_WEIGHTS["d5"] == 0.25


class TestComputeGoldOverall:
    def test_single_domain(self):
        assert compute_gold_overall(d1=100) == 100.0

    def test_all_domains_equal(self):
        result = compute_gold_overall(d1=80, d2=80, d3=80, d4=80, d5=80)
        assert result == 80.0

    def test_weighted_average(self):
        result = compute_gold_overall(d1=100, d2=0, d3=0, d4=0, d5=0)
        assert result == pytest.approx(8.0, abs=0.1)

    def test_good_consistency_no_penalty(self):
        result = compute_gold_overall(
            d1=90,
            d2=80,
            d3=80,
            d4=80,
            d5=80,
            consistency_index=0.80,
            cost_efficiency=0.70,
        )
        assert result > 75, f"Expected >75, got {result}"

    def test_low_consistency_penalty(self):
        result = compute_gold_overall(
            d1=90,
            d2=80,
            d3=80,
            d4=80,
            d5=80,
            consistency_index=0.55,
            cost_efficiency=0.70,
        )
        assert 70 < result < 82

    def test_very_low_consistency_veto(self):
        result = compute_gold_overall(
            d1=90,
            d2=80,
            d3=80,
            d4=80,
            d5=80,
            consistency_index=0.30,
            cost_efficiency=0.70,
        )
        assert result == 0.0

    def test_low_cost_efficiency_penalty(self):
        result = compute_gold_overall(
            d1=90,
            d2=80,
            d3=80,
            d4=80,
            d5=80,
            consistency_index=0.80,
            cost_efficiency=0.30,
        )
        assert result < 82

    def test_no_domains(self):
        assert compute_gold_overall() == 0.0


class TestDetermineGoldVerdict:
    def test_gold_full(self):
        verdict = determine_gold_verdict(85, consistency_index=0.80)
        assert verdict == "GOLD"

    def test_gold_with_critical_downgrades(self):
        """CRITICAL finding → cannot be GOLD."""
        verdict = determine_gold_verdict(
            85,
            findings=[{"severity": "CRITICAL", "category": "test", "layer": "tool"}],
            consistency_index=0.80,
        )
        assert verdict != "GOLD"

    def test_silver_good_score_low_ci(self):
        verdict = determine_gold_verdict(75, consistency_index=0.65)
        assert verdict == "SILVER"

    def test_silver_critical_security_downgraded(self):
        """CRITICAL safety finding → demoted to BRONZE."""
        verdict = determine_gold_verdict(
            75,
            findings=[{"severity": "CRITICAL", "category": "test", "layer": "safety"}],
            consistency_index=0.65,
        )
        assert verdict == "BRONZE"

    def test_bronze_low_score(self):
        verdict = determine_gold_verdict(65, consistency_index=0.55)
        assert verdict == "BRONZE"

    def test_fail_very_low_score(self):
        verdict = determine_gold_verdict(40, consistency_index=0.3)
        assert verdict == "FAIL"

    def test_fail_low_ci(self):
        verdict = determine_gold_verdict(85, consistency_index=0.3)
        assert verdict == "FAIL"
