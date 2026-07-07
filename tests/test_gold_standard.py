# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for Gold Standard threshold matrix and certificate generation."""

from mas_eval.scoring.gold_certificate import (
    generate_compliance_report,
    generate_gold_certificate,
    verify_certificate,
)
from mas_eval.scoring.gold_thresholds import (
    GOLD_THRESHOLD_MATRIX,
    check_gold_standard_compliance,
    check_level_thresholds,
    get_level_requirements,
)


class TestGoldThresholds:
    def test_threshold_matrix_exists(self):
        assert "L0" in GOLD_THRESHOLD_MATRIX
        assert "L1" in GOLD_THRESHOLD_MATRIX
        assert "L2" in GOLD_THRESHOLD_MATRIX
        assert "L3" in GOLD_THRESHOLD_MATRIX
        assert "L4" in GOLD_THRESHOLD_MATRIX

    def test_l3_thresholds(self):
        l3 = GOLD_THRESHOLD_MATRIX["L3"]
        assert l3["level"] == "Comprehensive"
        assert l3["d2_task_completion"] == 90
        assert l3["d2_step_efficiency"] == 0.75
        assert l3["cost_efficiency"] == 0.65
        assert l3["overall_score"] == 78

    def test_check_level_pass(self):
        metrics = {
            "d2_task_completion": 95,
            "d2_step_efficiency": 0.8,
            "d2_tool_coverage": 96,
            "cost_efficiency": 0.7,
            "overall_score": 80,
        }

        result = check_level_thresholds(metrics, "L3")
        assert result["level"] == "L3"
        assert result["overall_pass"] is True
        assert result["passed_count"] == result["total_count"]

    def test_check_level_fail(self):
        metrics = {
            "d2_task_completion": 80,  # Below 90
            "d2_step_efficiency": 0.8,
            "d2_tool_coverage": 96,
            "cost_efficiency": 0.7,
            "overall_score": 80,
        }

        result = check_level_thresholds(metrics, "L3")
        assert result["overall_pass"] is False
        assert result["metrics"]["d2_task_completion"]["passed"] is False

    def test_get_level_requirements(self):
        reqs = get_level_requirements("L2")
        assert reqs["level"] == "Deep"
        assert "d2_task_completion" in reqs
        assert "cost_efficiency" in reqs

    def test_gold_standard_compliance(self):
        metrics = {
            "d2_task_completion": 95,
            "d2_step_efficiency": 0.8,
            "d2_tool_coverage": 96,
            "cost_efficiency": 0.7,
            "overall_score": 85,
            "d5_consistency_index": 0.8,
        }

        result = check_gold_standard_compliance(
            metrics,
            consistency_index=0.8,
            cost_efficiency=0.7,
        )

        assert "levels" in result
        assert "verdict" in result
        assert result["verdict"] in ["GOLD", "SILVER", "BRONZE", "FAIL"]

    def test_consistency_index_veto(self):
        metrics = {
            "d2_task_completion": 95,
            "overall_score": 85,
        }

        result = check_gold_standard_compliance(
            metrics,
            consistency_index=0.3,  # Below 0.4 → veto
        )

        assert result["verdict"] == "FAIL"
        assert "veto_reason" in result

    def test_check_level_unknown_level(self):
        import pytest

        with pytest.raises(ValueError, match="Unknown level"):
            check_level_thresholds({}, "L5")

    def test_check_level_lower_is_better(self):
        metrics = {
            "d3_message_efficiency": 2.5,  # Above threshold (2.0 for L2)
            "d3_comm_overhead_ratio": 0.5,  # Lower is better (0.35 for L2)
        }
        result = check_level_thresholds(metrics, "L2")
        assert (
            result["metrics"]["d3_message_efficiency"]["passed"] is False
        )  # 2.5 > 2.0
        # Gold Standard §9.2 — comm_overhead_ratio is a ceiling (lower is better).
        # This was previously mis-classified as "higher is better"; the fix makes
        # 0.5 > 0.35 correctly fail.
        assert result["metrics"]["d3_comm_overhead_ratio"]["passed"] is False

    def test_check_level_d3_conflict_resolution_higher_is_better(self):
        """Gold Standard §9.2 — d3_conflict_resolution is a capability metric
        (0-100, higher is better), NOT a lower-is-better rate. Renamed from the
        mis-specified d3_conflict_rate whose integer thresholds (8/5/3/1) were
        unit-incompatible with the 0-100 conflict subscore returned by run_d3.
        """
        # Below L2 threshold (60) → must fail.
        failing = {"d3_conflict_resolution": 50}
        result = check_level_thresholds(failing, "L2")
        assert result["metrics"]["d3_conflict_resolution"]["passed"] is False
        # At/above L2 threshold (60) → must pass.
        passing = {"d3_conflict_resolution": 65}
        result = check_level_thresholds(passing, "L2")
        assert result["metrics"]["d3_conflict_resolution"]["passed"] is True

    def test_check_level_lower_is_better_fixed_metrics(self):
        """Verify the previously-broken lower-is-better metrics now fail/pass
        correctly. These were all mis-classified as higher-is-better before
        the LOWER_IS_BETTER_METRICS fix (drift_fnr wasn't even reached by the
        old substring match)."""
        # All above their ceilings → must fail.
        failing = {
            "d5_drift_fnr": 12,  # L3 ceiling 8
            "d4_pentest": 2,  # L3 ceiling 0
            "d4_data_leakage": 1,  # L3 ceiling 0
            "d5_federation_cascade": 5,  # L3 ceiling 3
        }
        result = check_level_thresholds(failing, "L3")
        for metric in failing:
            assert result["metrics"][metric]["passed"] is False, metric

        # At/below ceiling → must pass.
        passing = {
            "d5_drift_fnr": 8,  # == ceiling 8
            "d4_pentest": 0,  # == ceiling 0
            "d4_data_leakage": 0,  # == ceiling 0
            "d5_federation_cascade": 3,  # == ceiling 3
        }
        result = check_level_thresholds(passing, "L3")
        for metric in passing:
            assert result["metrics"][metric]["passed"] is True, metric

    def test_get_level_requirements_unknown(self):
        import pytest

        with pytest.raises(ValueError, match="Unknown level"):
            get_level_requirements("L5")

    def test_gold_standard_compliance_l4_gold(self):
        metrics = {
            "d2_task_completion": 99,
            "overall_score": 99,
            "cost_efficiency": 0.99,
        }
        result = check_gold_standard_compliance(metrics)
        # L4 passes → verdict should be GOLD
        assert result["verdict"] == "GOLD"

    def test_gold_standard_compliance_l2_silver(self):
        metrics = {
            "d2_step_efficiency": 0.7,
            "cost_efficiency": 0.6,
            "overall_score": 75,
        }
        result = check_gold_standard_compliance(metrics)
        # L2 passes → verdict should be SILVER
        assert result["verdict"] == "SILVER"

    def test_gold_standard_compliance_l1_silver(self):
        metrics = {
            "d1_compliance": 100,
            "d2_step_efficiency": 0.55,
            "d2_tool_coverage": 75,
            "d3_spawn_rate": 95,
            "d2_task_completion": 78,  # Below L2(85) but above L1(75)
            "cost_efficiency": 0.45,  # Above L1(0.4) but below L2(0.5)
            "overall_score": 65,
        }
        result = check_gold_standard_compliance(metrics)
        # L1 passes, L2 fails → verdict should be SILVER
        assert result["verdict"] == "SILVER"

    def test_gold_standard_compliance_l0_bronze(self):
        metrics = {
            "d1_compliance": 100,
            "d2_step_efficiency": 0.52,
            "d2_tool_coverage": 60,
        }
        result = check_gold_standard_compliance(metrics)
        # Only L0 passes → verdict should be BRONZE
        assert result["verdict"] == "BRONZE"

    def test_gold_standard_compliance_fail(self):
        result = check_gold_standard_compliance({})
        # No levels pass → verdict should be FAIL
        assert result["verdict"] == "FAIL"

    def test_gold_standard_with_critical_findings(self):
        metrics = {"d2_task_completion": 95, "overall_score": 95}
        findings = [{"severity": "CRITICAL", "detail": "test"}]
        result = check_gold_standard_compliance(metrics, findings=findings)
        assert result["critical_findings"] == 1
        assert result["findings_count"] == 1


class TestGoldCertificate:
    def test_generate_gold_certificate(self):
        cert = generate_gold_certificate(
            agent_id="test-agent-001",
            score=87.3,
            grade="A",
            consistency_index=0.82,
            cost_efficiency=0.71,
        )

        assert cert["agent_id"] == "test-agent-001"
        assert cert["score"] == 87.3
        assert cert["grade"] == "A"
        assert cert["compliance_level"] == "GOLD"
        assert "badge" in cert
        assert "cert_id" in cert
        assert "valid_until" in cert

    def test_generate_silver_certificate(self):
        cert = generate_gold_certificate(
            agent_id="test-agent-002",
            score=75.0,
            grade="B+",
            consistency_index=0.65,
            cost_efficiency=0.60,
        )

        assert cert["compliance_level"] == "SILVER"
        assert "◆" in cert["badge"]

    def test_generate_bronze_certificate(self):
        cert = generate_gold_certificate(
            agent_id="test-agent-003",
            score=65.0,
            grade="C+",
            consistency_index=0.55,
            cost_efficiency=0.50,
        )

        assert cert["compliance_level"] == "BRONZE"
        assert "●" in cert["badge"]

    def test_generate_fail_certificate(self):
        cert = generate_gold_certificate(
            agent_id="test-agent-004",
            score=50.0,
            grade="D",
            consistency_index=0.40,
            cost_efficiency=0.30,
        )

        assert cert["compliance_level"] == "FAIL"
        assert "✗" in cert["badge"]

    def test_certificate_with_signature(self):
        cert = generate_gold_certificate(
            agent_id="test-agent-001",
            score=87.3,
            grade="A",
            signature_key="secret-key-123",
        )

        assert cert["verified"] is True
        assert len(cert["cert_id"]) > 0

    def test_verify_valid_certificate(self):
        cert = generate_gold_certificate(
            agent_id="test-agent-001",
            score=87.3,
            grade="A",
        )

        assert verify_certificate(cert) is True

    def test_verify_with_signature(self):
        key = "secret-key-123"
        cert = generate_gold_certificate(
            agent_id="test-agent-001",
            score=87.3,
            grade="A",
            signature_key=key,
        )

        assert verify_certificate(cert, key) is True
        assert verify_certificate(cert, "wrong-key") is False

    def test_verify_expired_certificate(self):
        cert = generate_gold_certificate(
            agent_id="test-agent-001",
            score=87.3,
            grade="A",
            valid_days=-1,  # Already expired
        )

        assert verify_certificate(cert) is False

    def test_verify_missing_field(self):
        assert verify_certificate({}) is False

    def test_verify_invalid_date_format(self):
        cert = {
            "agent_id": "test",
            "cert_id": "abc",
            "score": 80,
            "grade": "B",
            "valid_until": "not-a-date",
        }
        assert verify_certificate(cert) is False

    def test_generate_certificate_high_score_gold(self):
        cert = generate_gold_certificate(
            agent_id="test-agent",
            score=95.0,
            grade="A+",
            consistency_index=0.90,
        )
        assert cert["compliance_level"] == "GOLD"

    def test_generate_compliance_report(self):
        level_results = {
            "levels": {
                "L2": {"overall_pass": True, "passed_count": 5, "total_count": 5},
                "L3": {"overall_pass": False, "passed_count": 3, "total_count": 5},
            },
            "verdict": "SILVER",
            "findings_count": 2,
            "critical_findings": 0,
        }

        report = generate_compliance_report(
            agent_id="test-agent-001",
            level_results=level_results,
            overall_score=75.0,
            grade="B+",
        )

        assert "MAS-TS-001" in report
        assert "test-agent-001" in report
        assert "75.0" in report
        assert "SILVER" in report
        assert "✓ PASS" in report
        assert "✗ FAIL" in report
