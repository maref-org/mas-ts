# SPDX-FileCopyrightText: 2026 MAREF Project Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for StressHarness L3 stress testing."""

from mas_eval.harness.stress_harness import (
    DEFAULT_FAULT_TYPES,
    STRESS_LEVELS,
    STRESS_PHASES,
    mock_stress_score,
    run_stress_harness,
)


class TestStressConstants:
    def test_stress_levels_defined(self):
        assert "L1" in STRESS_LEVELS
        assert "L3" in STRESS_LEVELS
        assert "L5" in STRESS_LEVELS

    def test_stress_phases_defined(self):
        assert "sustained_load" in STRESS_PHASES
        assert "fault_injection" in STRESS_PHASES
        assert "resource_exhaustion" in STRESS_PHASES

    def test_default_fault_types(self):
        assert "cpu_pressure" in DEFAULT_FAULT_TYPES
        assert "network_partition" in DEFAULT_FAULT_TYPES
        assert "mcp_disconnect" in DEFAULT_FAULT_TYPES

    def test_l3_load_rounds(self):
        assert STRESS_LEVELS["L3"]["load_rounds"] == 200

    def test_l3_fault_types(self):
        assert STRESS_LEVELS["L3"]["fault_types"] == 5

    def test_l5_max_rounds(self):
        assert STRESS_LEVELS["L5"]["load_rounds"] == 1000


class TestRunStressHarness:
    def test_returns_dict(self):
        result = run_stress_harness()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = run_stress_harness()
        assert "level" in result
        assert "name" in result
        assert "elapsed_seconds" in result
        assert "score" in result
        assert "grade" in result
        assert "verdict" in result
        assert "domain_scores" in result
        assert "domains" in result
        assert "findings" in result
        assert "phase_results" in result

    def test_level_is_l3(self):
        result = run_stress_harness()
        assert result["level"] == "L3"

    def test_name_is_stress(self):
        result = run_stress_harness()
        assert result["name"] == "Stress"

    def test_score_in_range(self):
        result = run_stress_harness()
        assert 0.0 <= result["score"] <= 100.0

    def test_domain_scores_has_stress(self):
        result = run_stress_harness()
        assert "stress" in result["domain_scores"]

    def test_domains_has_stress_detail(self):
        result = run_stress_harness()
        assert "stress_detail" in result["domains"]

    def test_stress_detail_has_required_fields(self):
        result = run_stress_harness()
        sd = result["domains"]["stress_detail"]
        assert "total_rounds" in sd
        assert "total_faults_injected" in sd
        assert "total_faults_healed" in sd
        assert "healing_rate" in sd
        assert "recovery_rate" in sd
        assert "phases" in sd

    def test_phase_results_has_all_phases(self):
        result = run_stress_harness()
        for phase in STRESS_PHASES:
            assert phase in result["phase_results"], f"Missing phase: {phase}"

    def test_sustained_load_produces_rounds(self):
        result = run_stress_harness()
        sl = result["phase_results"]["sustained_load"]
        assert sl["rounds_completed"] > 0

    def test_fault_injection_injects_faults(self):
        result = run_stress_harness()
        fi = result["phase_results"]["fault_injection"]
        assert fi["faults_injected"] > 0

    def test_resource_exhaustion_has_recovery(self):
        result = run_stress_harness()
        re = result["phase_results"]["resource_exhaustion"]
        assert "recovery_rate" in re
        assert re["attempts"] > 0

    def test_findings_list(self):
        result = run_stress_harness()
        assert isinstance(result["findings"], list)

    def test_custom_level_l1(self):
        result = run_stress_harness(level="L1")
        assert result["stress_config"]["load_rounds"] == 50

    def test_custom_level_l5(self):
        result = run_stress_harness(level="L5")
        assert result["stress_config"]["load_rounds"] == 1000

    def test_verdict_is_string(self):
        result = run_stress_harness()
        assert isinstance(result["verdict"], str)

    def test_grade_is_string(self):
        result = run_stress_harness()
        assert isinstance(result["grade"], str)

    def test_with_runner_fn(self):
        def mock_runner(**kwargs):
            return {"score": 85.0, "findings": []}

        result = run_stress_harness(runner_fn=mock_runner)
        assert result["score"] > 0

    def test_with_runner_fn_failure(self):
        call_count = [0]

        def failing_runner(**kwargs):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise RuntimeError("mock failure")
            return {"score": 80.0, "findings": []}

        result = run_stress_harness(runner_fn=failing_runner)
        assert result["score"] > 0

    def test_elapsed_seconds_non_negative(self):
        result = run_stress_harness()
        assert result["elapsed_seconds"] >= 0.0

    def test_stress_config_present(self):
        result = run_stress_harness()
        assert "stress_config" in result

    def test_different_seeds_produce_different_scores(self):
        r1 = run_stress_harness(seed=42)
        r2 = run_stress_harness(seed=999)
        # Scores may differ due to random jitter
        assert (
            r1["phase_results"]["sustained_load"]["avg_score"]
            != r2["phase_results"]["sustained_load"]["avg_score"]
        )

    def test_l3_healing_rate_bounded(self):
        result = run_stress_harness()
        sd = result["domains"]["stress_detail"]
        assert 0.0 <= sd["healing_rate"] <= 1.0

    def test_l3_recovery_rate_bounded(self):
        result = run_stress_harness()
        sd = result["domains"]["stress_detail"]
        assert 0.0 <= sd["recovery_rate"] <= 1.0


class TestMockStressScore:
    def test_returns_float(self):
        score = mock_stress_score(1)
        assert isinstance(score, float)

    def test_score_in_range(self):
        for rid in (1, 50, 100, 200, 500):
            score = mock_stress_score(rid)
            assert 0.0 <= score <= 100.0, f"Round {rid}: score={score}"

    def test_score_increases_with_round(self):
        s1 = mock_stress_score(10)
        s2 = mock_stress_score(100)
        s3 = mock_stress_score(200)
        assert s2 >= s1
        assert s3 >= s2

    def test_score_plateaus(self):
        s200 = mock_stress_score(200)
        s500 = mock_stress_score(500)
        assert abs(s500 - s200) < 10.0  # plateau near 0.9 after round 200

    def test_deterministic_with_seed(self):
        import random as rnd

        rng = rnd.Random(42)
        s1 = mock_stress_score(50, rng)
        rng2 = rnd.Random(42)
        s2 = mock_stress_score(50, rng2)
        assert s1 == s2
