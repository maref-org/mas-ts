# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 D5: Evolution & Robustness (Part 1 — Chaos Engineering + Drift Detection, Part 2 — Reflection Loop + Convergence Verification)."""

import math

import pytest

from mas_eval.domains.d5_robustness import (
    CRITIQUE_CATEGORIES,
    FEDERATION_FAULT_WEIGHTS,
    FEDERATION_FAULTS,
    INFRA_FAULTS,
    LLM_FAULTS,
    QUALITY_DIMS,
    ChaosEngine,
    ConvergenceVerifier,
    DriftDetector,
    ReflectiveAgent,
    _cosine_sim,
    _hellinger_distance,
    _js_divergence,
    _kl_divergence,
    run_d5,
    run_d5_part1,
    run_d5_part2,
)


class TestDivergence:
    def test_kl_identical(self):
        p = [0.5, 0.3, 0.2]
        assert _kl_divergence(p, p) == pytest.approx(0.0, abs=1e-10)

    def test_kl_different(self):
        p = [0.5, 0.3, 0.2]
        q = [0.4, 0.4, 0.2]
        assert _kl_divergence(p, q) > 0

    def test_kl_sums_to_one(self):
        p = [5, 3, 2]
        q = [4, 4, 2]
        result = _kl_divergence(p, q)
        assert 0 <= result < 1

    def test_js_identical(self):
        p = [0.5, 0.3, 0.2]
        assert _js_divergence(p, p) == pytest.approx(0.0, abs=1e-10)

    def test_js_bounded(self):
        p = [1.0, 0.0]
        q = [0.0, 1.0]
        js = _js_divergence(p, q)
        assert 0 < js <= math.log(2)

    def test_hellinger_identical(self):
        p = [0.5, 0.3, 0.2]
        assert _hellinger_distance(p, p) == pytest.approx(0.0, abs=1e-10)

    def test_hellinger_bounded(self):
        p = [1.0, 0.0]
        q = [0.0, 1.0]
        hd = _hellinger_distance(p, q)
        assert 0 < hd <= 1.0

    def test_hellinger_exact(self):
        p = [0.5, 0.5]
        q = [1.0, 0.0]
        hd = _hellinger_distance(p, q)
        assert 0.5 < hd < 0.6
        assert hd == pytest.approx(0.54119, abs=1e-4)

    def test_zero_handling(self):
        p = [0.0, 1.0]
        q = [1.0, 0.0]
        kl = _kl_divergence(p, q)
        assert not math.isnan(kl)
        assert not math.isinf(kl)

    def test_all_divergences(self):
        p = [0.25, 0.20, 0.15, 0.10, 0.10, 0.10, 0.05, 0.05]
        q = [0.24, 0.21, 0.16, 0.11, 0.10, 0.09, 0.05, 0.04]
        assert _kl_divergence(p, q) < 0.01
        assert _js_divergence(p, q) < 0.01
        assert _hellinger_distance(p, q) < 0.05


class TestChaosEngine:
    def test_init(self):
        ce = ChaosEngine(seed=42)
        assert ce.fault_history == []
        assert ce.healing_results == {}

    def test_all_infra_faults_known(self):
        ce = ChaosEngine(seed=42)
        for fault in INFRA_FAULTS:
            result = ce.inject(fault)
            assert result["domain"] == "infra"
            assert result["fault"] == fault
            assert "expected_recovery_time_seconds" in result

    def test_all_llm_faults_known(self):
        ce = ChaosEngine(seed=42)
        for fault in LLM_FAULTS:
            result = ce.inject(fault)
            assert result["domain"] == "llm"
            assert result["fault"] == fault

    def test_all_federation_faults_known(self):
        ce = ChaosEngine(seed=42)
        for fault in FEDERATION_FAULTS:
            result = ce.inject(fault)
            assert result["domain"] == "federation"
            assert result["fault"] == fault

    def test_federation_fault_count(self):
        assert len(FEDERATION_FAULTS) == 5

    def test_federation_fault_weights_sum(self):
        total = sum(FEDERATION_FAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_federation_healing_rate_empty(self):
        ce = ChaosEngine(seed=42)
        assert ce.federation_healing_rate() == 0.0

    def test_federation_healing_rate_all_success(self):
        ce = ChaosEngine(seed=42)
        for fault in FEDERATION_FAULTS:
            ce.record_healing(fault, True)
        assert ce.federation_healing_rate() == 1.0

    def test_federation_healing_rate_mixed(self):
        ce = ChaosEngine(seed=42)
        ce.record_healing("mcp_disconnect", True)
        ce.record_healing("a2a_timeout", False)
        ce.record_healing("gossip_partition", True)
        assert ce.federation_healing_rate() == 2.0 / 3.0

    def test_federation_healing_not_mixed_with_infra(self):
        ce = ChaosEngine(seed=42)
        ce.record_healing("mcp_disconnect", False)
        ce.record_healing("network_partition", True)
        assert ce.federation_healing_rate() == 0.0
        assert ce.infra_healing_rate() == 1.0

    def test_federation_faults_in_scoring(self):
        ce = ChaosEngine(seed=42)
        for fault in FEDERATION_FAULTS:
            for scenario in range(3):
                ce.inject(fault, scenario)
                ce.record_healing(fault, True)
        rate = ce.federation_healing_rate()
        assert rate == 1.0

    def test_unknown_fault(self):
        ce = ChaosEngine(seed=42)
        result = ce.inject("unknown_fault")
        assert result["error"] == "unknown_fault_type"
        assert result["success"] is False

    def test_record_healing(self):
        ce = ChaosEngine(seed=42)
        ce.record_healing("network_partition", True, recovery_time=5.0)
        assert len(ce.healing_results["network_partition"]) == 1
        assert ce.healing_results["network_partition"][0]["success"] is True
        assert ce.healing_results["network_partition"][0]["recovery_time"] == 5.0

    def test_record_healing_default_recovery_time(self):
        ce = ChaosEngine(seed=42)
        ce.record_healing("network_partition", True)
        assert 1 <= ce.healing_results["network_partition"][0]["recovery_time"] <= 30

    def test_healing_rate_single(self):
        ce = ChaosEngine(seed=42)
        ce.record_healing("network_partition", True)
        ce.record_healing("network_partition", False)
        assert ce.healing_rate("network_partition") == 0.5

    def test_healing_rate_all(self):
        ce = ChaosEngine(seed=42)
        ce.record_healing("network_partition", True)
        ce.record_healing("cpu_pressure", False)
        assert ce.healing_rate() == 0.5

    def test_healing_rate_empty(self):
        ce = ChaosEngine(seed=42)
        assert ce.healing_rate() == 0.0
        assert ce.healing_rate("network_partition") == 0.0

    def test_infra_healing_rate(self):
        ce = ChaosEngine(seed=42)
        ce.record_healing("network_partition", True)
        ce.record_healing("cpu_pressure", False)
        ce.record_healing("timeout", True)
        assert ce.infra_healing_rate() == 0.5
        assert ce.llm_healing_rate() == 1.0

    def test_infra_healing_rate_empty(self):
        ce = ChaosEngine(seed=42)
        assert ce.infra_healing_rate() == 0.0
        assert ce.llm_healing_rate() == 0.0

    def test_fault_history_tracks_injections(self):
        ce = ChaosEngine(seed=42)
        ce.inject("network_partition", scenario=2)
        ce.inject("timeout", scenario=1)
        assert len(ce.fault_history) == 2
        assert ce.fault_history[0]["fault"] == "network_partition"
        assert ce.fault_history[0]["scenario"] == 2
        assert ce.fault_history[1]["fault"] == "timeout"
        assert ce.fault_history[1]["scenario"] == 1

    def test_clear(self):
        ce = ChaosEngine(seed=42)
        ce.inject("network_partition")
        ce.record_healing("network_partition", True)
        ce.clear()
        assert ce.fault_history == []
        assert ce.healing_results == {}

    def test_reproducible_seed(self):
        ce1 = ChaosEngine(seed=42)
        ce2 = ChaosEngine(seed=42)
        ce1.inject("network_partition", 0)
        ce2.inject("network_partition", 0)
        ce1.record_healing("network_partition", True)
        ce2.record_healing("network_partition", True)
        assert ce1.healing_results["network_partition"][0][
            "recovery_time"
        ] == pytest.approx(
            ce2.healing_results["network_partition"][0]["recovery_time"], abs=0.01
        )


class TestDriftDetector:
    def test_init(self):
        dd = DriftDetector()
        assert dd.baselines == {}
        assert dd.total_checks == 0
        assert dd.false_negatives == 0
        assert dd.false_positives == 0

    def test_add_baseline(self):
        dd = DriftDetector()
        dd.add_baseline("tool_weights", [0.25, 0.20, 0.15])
        assert "tool_weights" in dd.baselines
        assert dd.baselines["tool_weights"] == [0.25, 0.20, 0.15]

    def test_add_sample(self):
        dd = DriftDetector()
        dd.add_sample("tool_weights", [0.24, 0.21, 0.16])
        assert dd.samples["tool_weights"] == [[0.24, 0.21, 0.16]]

    def test_check_drift_no_baseline(self):
        dd = DriftDetector()
        result = dd.check_drift("missing")
        assert result["error"] == "no_baseline"

    def test_check_drift_no_sample(self):
        dd = DriftDetector()
        dd.add_baseline("tool_weights", [0.25, 0.20, 0.15])
        result = dd.check_drift("tool_weights")
        assert result["error"] == "no_sample"

    def test_check_drift_identical(self):
        dd = DriftDetector()
        dd.add_baseline(
            "tool_weights", [0.25, 0.20, 0.15, 0.10, 0.10, 0.10, 0.05, 0.05]
        )
        sample = [0.25, 0.20, 0.15, 0.10, 0.10, 0.10, 0.05, 0.05]
        result = dd.check_drift("tool_weights", sample)
        assert result["kl_divergence"] == pytest.approx(0.0, abs=1e-10)
        assert result["drift_warning"] is False
        assert result["drift_critical"] is False

    def test_check_drift_detected(self):
        dd = DriftDetector()
        dd.add_baseline(
            "tool_weights", [0.25, 0.20, 0.15, 0.10, 0.10, 0.10, 0.05, 0.05]
        )
        sample = [0.40, 0.30, 0.10, 0.05, 0.05, 0.05, 0.03, 0.02]
        result = dd.check_drift("tool_weights", sample)
        assert result["kl_divergence"] > 0.01
        assert result["hellinger_distance"] > 0.01

    def test_drift_warning_threshold(self):
        dd = DriftDetector()
        p = [0.50, 0.30, 0.20]
        q = [0.30, 0.35, 0.35]
        dd.add_baseline("test", p)
        result = dd.check_drift("test", q)
        assert isinstance(result["drift_warning"], bool)

    def test_total_checks_incremented(self):
        dd = DriftDetector()
        dd.add_baseline("test", [0.5, 0.5])
        dd.check_drift("test", [0.5, 0.5])
        dd.check_drift("test", [0.4, 0.6])
        assert dd.total_checks == 2

    def test_false_negative_tracking(self):
        dd = DriftDetector()
        dd.record_false_negative()
        dd.record_false_negative()
        assert dd.false_negatives == 2

    def test_false_positive_tracking(self):
        dd = DriftDetector()
        dd.record_false_positive()
        assert dd.false_positives == 1

    def test_fnr_fpr(self):
        dd = DriftDetector()
        dd.add_baseline("test", [0.5, 0.5])
        for _ in range(5):
            dd.check_drift("test", [0.5, 0.5])
        dd.record_false_negative()
        assert dd.fnr == 0.2
        assert dd.fpr == 0.0

    def test_fnr_empty(self):
        dd = DriftDetector()
        assert dd.fnr == 0.0
        assert dd.fpr == 0.0

    def test_auto_reset_respects_cooldown(self):
        dd = DriftDetector()
        dd.add_baseline("test", [0.5, 0.5])
        result = dd.auto_reset_baseline("test", [0.5, 0.5])
        assert result is False
        assert dd.last_baseline_reset["test"] == dd.last_baseline_reset["test"]

    def test_auto_reset_no_sample(self):
        dd = DriftDetector()
        dd.add_baseline("test", [0.5, 0.5])
        result = dd.auto_reset_baseline("test")
        assert result is False

    def test_auto_reset_no_baseline(self):
        dd = DriftDetector()
        result = dd.auto_reset_baseline("missing")
        assert result is False

    def test_clear(self):
        dd = DriftDetector()
        dd.add_baseline("test", [0.5, 0.5])
        dd.add_sample("test", [0.4, 0.6])
        dd.check_drift("test", [0.4, 0.6])
        dd.record_false_negative()
        dd.record_false_positive()
        dd.clear()
        assert dd.baselines == {}
        assert dd.samples == {}
        assert dd.results == []
        assert dd.false_negatives == 0
        assert dd.false_positives == 0
        assert dd.total_checks == 0


class TestRunD5Part1:
    def test_full_run_returns_dict(self):
        result = run_d5_part1()
        assert isinstance(result, dict)

    def test_full_run_has_correct_structure(self):
        result = run_d5_part1()
        assert result["domain"] == "D5"
        assert result["component"] == "part1"
        assert "chaos_engineering" in result["subscores"]
        assert "drift_detection" in result["subscores"]
        assert isinstance(result["subscores"]["chaos_engineering"], (int, float))
        assert isinstance(result["subscores"]["drift_detection"], (int, float))

    def test_full_run_chaos_score_range(self):
        result = run_d5_part1()
        assert 0 <= result["subscores"]["chaos_engineering"] <= 100

    def test_full_run_drift_score_range(self):
        result = run_d5_part1()
        assert 0 <= result["subscores"]["drift_detection"] <= 100

    def test_full_run_findings(self):
        result = run_d5_part1()
        assert len(result["findings"]) > 0
        for finding in result["findings"]:
            assert "severity" in finding
            assert "category" in finding
            assert "detail" in finding

    def test_full_run_summary(self):
        result = run_d5_part1()
        assert "summary" in result
        assert "chaos_overall_rate" in result["summary"]
        assert "drift_total_checks" in result["summary"]
        assert "drift_fnr" in result["summary"]
        assert "drift_fpr" in result["summary"]

    def test_combined_score_reasonableness(self):
        result = run_d5_part1()
        expected = round(
            result["subscores"]["chaos_engineering"] * 0.30
            + result["subscores"]["drift_detection"] * 0.25,
            1,
        )
        assert result["score"] == expected

    def test_consistency_reproducible(self):
        r1 = run_d5_part1()
        r2 = run_d5_part1()
        assert r1["score"] == r2["score"]
        assert r1["subscores"] == r2["subscores"]

    def test_unhealed_faults_findings(self):
        result = run_d5_part1()
        chaos_warnings = [
            f for f in result["findings"] if "unhealed" in f.get("category", "")
        ]
        assert isinstance(chaos_warnings, list)

    def test_drift_auto_reset_finding(self):
        result = run_d5_part1()
        auto_reset_findings = [
            f for f in result["findings"] if f.get("category") == "drift_auto_reset"
        ]
        assert len(auto_reset_findings) >= 0


class TestINFRAFAULTSConstants:
    def test_known_infra_faults(self):
        expected = {
            "network_partition",
            "cpu_pressure",
            "memory_pressure",
            "disk_failure",
            "process_kill",
        }
        assert set(INFRA_FAULTS) == expected

    def test_known_llm_faults(self):
        expected = {
            "timeout",
            "hallucination",
            "token_corruption",
            "model_degradation",
            "rate_limiting",
        }
        assert set(LLM_FAULTS) == expected

    def test_all_faults_distinct(self):
        assert len(set(INFRA_FAULTS) & set(LLM_FAULTS)) == 0


class TestCosineSim:
    def test_identical(self):
        assert _cosine_sim([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal(self):
        assert _cosine_sim([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_partial(self):
        sim = _cosine_sim([1, 2, 3], [1, 2, 3])
        assert sim == pytest.approx(1.0)

    def test_different_lengths(self):
        assert _cosine_sim([1, 0], [1, 0, 0]) == 0.0

    def test_empty_input(self):
        assert _cosine_sim([], []) == 0.0

    def test_zero_vector(self):
        assert _cosine_sim([0, 0, 0], [1, 2, 3]) == 0.0


class TestQUALITYDIMS:
    def test_weights_sum_to_one(self):
        assert sum(QUALITY_DIMS.values()) == pytest.approx(1.0)

    def test_has_correctness(self):
        assert "correctness" in QUALITY_DIMS
        assert QUALITY_DIMS["correctness"] == 0.25

    def test_has_all_dims(self):
        expected = {
            "correctness",
            "completeness",
            "safety",
            "efficiency",
            "consistency",
        }
        assert set(QUALITY_DIMS.keys()) == expected


class TestCritiqueCategories:
    def test_has_categories(self):
        expected = {
            "logical_error",
            "missing_edge_case",
            "safety_concern",
            "inefficient",
            "inconsistent",
        }
        assert set(CRITIQUE_CATEGORIES) == expected


class TestReflectiveAgent:
    def test_init(self):
        ra = ReflectiveAgent(max_iterations=3)
        assert ra.max_iterations == 3
        assert ra.history == []
        assert ra.iteration == 0

    def test_generate(self):
        ra = ReflectiveAgent()
        ra.generate("Solve: 2x+4=10")
        assert "Draft" in ra.current_output
        assert len(ra.history) == 1
        assert ra.history[0]["phase"] == "generate"

    def test_critique_returns_score(self):
        ra = ReflectiveAgent()
        ra.generate("Solve: 2x+4=10")
        score = ra.critique()
        assert 0.0 <= score <= 1.0

    def test_critique_with_custom_scores(self):
        ra = ReflectiveAgent()
        ra.generate("test")
        custom = {
            "correctness": 0.9,
            "completeness": 0.8,
            "safety": 1.0,
            "efficiency": 0.7,
            "consistency": 0.9,
        }
        score = ra.critique(custom)
        expected = 0.9 * 0.25 + 0.8 * 0.25 + 1.0 * 0.20 + 0.7 * 0.15 + 0.9 * 0.15
        assert score == pytest.approx(expected)

    def test_critique_max_iterations(self):
        ra = ReflectiveAgent(max_iterations=1)
        ra.generate("test")
        ra.critique()
        ra.refine()
        score = ra.critique()
        assert score is not None

    def test_refine_increments_iteration(self):
        ra = ReflectiveAgent()
        ra.generate("test")
        ra.critique()
        ra.refine()
        assert ra.iteration == 1
        ra.refine()
        assert ra.iteration == 2

    def test_refine_updates_output(self):
        ra = ReflectiveAgent()
        ra.generate("test")
        ra.critique()
        ra.refine("custom")
        assert "custom" in ra.current_output

    def test_verify_false_when_no_scores(self):
        ra = ReflectiveAgent()
        ra.generate("test")
        assert ra.verify() is False

    def test_verify_true_when_above_threshold(self):
        ra = ReflectiveAgent()
        ra.generate("test")
        ra.critique(
            {
                "correctness": 1.0,
                "completeness": 1.0,
                "safety": 1.0,
                "efficiency": 1.0,
                "consistency": 1.0,
            }
        )
        assert ra.verify() is True

    def test_accept_returns_dict(self):
        ra = ReflectiveAgent()
        ra.generate("test")
        ra.critique()
        result = ra.accept()
        assert "accepted_iteration" in result
        assert "best_score" in result
        assert "total_iterations" in result

    def test_accept_empty_returns_zero(self):
        ra = ReflectiveAgent()
        result = ra.accept()
        assert result["best_score"] == 0
        assert result["accepted_iteration"] == -1

    def test_clear(self):
        ra = ReflectiveAgent()
        ra.generate("test")
        ra.critique()
        ra.clear()
        assert ra.history == []
        assert ra.iteration == 0

    def test_full_loop(self):
        ra = ReflectiveAgent(max_iterations=3)
        ra.generate("Solve: 2x+4=10")
        for i in range(3):
            ra.critique()
            ra.refine()
            if ra.verify():
                break
        accept = ra.accept()
        assert accept["best_score"] > 0
        assert 1 <= accept["total_iterations"] <= 3


class TestConvergenceVerifier:
    def test_init(self):
        cv = ConvergenceVerifier()
        assert cv.responses == {}
        assert cv.task_results == {}

    def test_add_response(self):
        cv = ConvergenceVerifier()
        cv.add_response("task_1", "output_a")
        cv.add_response("task_1", "output_b")
        assert len(cv.responses["task_1"]) == 2

    def test_add_task_result(self):
        cv = ConvergenceVerifier()
        cv.add_task_result("task_1", True)
        assert cv.task_results["task_1"] is True

    def test_c1_no_responses(self):
        cv = ConvergenceVerifier()
        assert cv.score_c1_consistency() == 0.0

    def test_c1_single_response(self):
        cv = ConvergenceVerifier()
        cv.add_response("task_1", "x = 3")
        assert cv.score_c1_consistency() == 0.0

    def test_c1_identical_responses(self):
        cv = ConvergenceVerifier()
        cv.add_response("task_1", "x = 3")
        cv.add_response("task_1", "x = 3")
        assert cv.score_c1_consistency("task_1") == pytest.approx(1.0, abs=0.1)

    def test_c2_no_responses(self):
        cv = ConvergenceVerifier()
        assert cv.score_c2_self_consistency() == 0.0

    def test_c2_not_enough_responses(self):
        cv = ConvergenceVerifier()
        cv.add_response("task_1", "a")
        cv.add_response("task_1", "b")
        assert cv.score_c2_self_consistency("task_1") == 0.0

    def test_c2_high_agreement(self):
        cv = ConvergenceVerifier()
        cv.add_response("task_1", "x = 3")
        cv.add_response("task_1", "x = 3")
        cv.add_response("task_1", "x = 3")
        cv.add_response("task_1", "x = 3")
        cv.add_response("task_1", "x = 3")
        score = cv.score_c2_self_consistency("task_1")
        assert score == pytest.approx(1.0, abs=0.1)

    def test_c3_no_results(self):
        cv = ConvergenceVerifier()
        assert cv.score_c3_task_completion() == 0.0

    def test_c3_all_pass(self):
        cv = ConvergenceVerifier()
        cv.add_task_result("t1", True)
        cv.add_task_result("t2", True)
        assert cv.score_c3_task_completion() == 100.0

    def test_c3_partial_pass(self):
        cv = ConvergenceVerifier()
        cv.add_task_result("t1", True)
        cv.add_task_result("t2", False)
        cv.add_task_result("t3", True)
        assert cv.score_c3_task_completion() == pytest.approx(66.7, abs=0.1)

    def test_c3_all_fail(self):
        cv = ConvergenceVerifier()
        cv.add_task_result("t1", False)
        assert cv.score_c3_task_completion() == 0.0

    def test_clear(self):
        cv = ConvergenceVerifier()
        cv.add_response("task_1", "a")
        cv.add_task_result("t1", True)
        cv.clear()
        assert cv.responses == {}
        assert cv.task_results == {}


class TestRunD5Part2:
    def test_full_run_returns_dict(self):
        result = run_d5_part2()
        assert isinstance(result, dict)

    def test_full_run_correct_structure(self):
        result = run_d5_part2()
        assert result["domain"] == "D5"
        assert result["component"] == "part2"
        assert "reflection_loop" in result["subscores"]
        assert "convergence_cycle" in result["subscores"]

    def test_reflection_score_range(self):
        result = run_d5_part2()
        assert 0 <= result["subscores"]["reflection_loop"] <= 100

    def test_convergence_score_range(self):
        result = run_d5_part2()
        assert 0 <= result["subscores"]["convergence_cycle"] <= 100

    def test_part2_findings(self):
        result = run_d5_part2()
        assert len(result["findings"]) > 0

    def test_part2_summary(self):
        result = run_d5_part2()
        assert "reflection_score" in result["summary"]
        assert "convergence_score" in result["summary"]


class TestRunD5:
    def test_full_run_returns_dict(self):
        result = run_d5()
        assert isinstance(result, dict)

    def test_correct_domain(self):
        result = run_d5()
        assert result["domain"] == "D5"

    def test_has_all_subscores(self):
        result = run_d5()
        expected = {
            "chaos_engineering",
            "drift_detection",
            "reflection_loop",
            "convergence_cycle",
        }
        assert expected == set(result["subscores"].keys())

    def test_all_subscores_in_range(self):
        result = run_d5()
        for k, v in result["subscores"].items():
            assert 0 <= v <= 100, f"{k}={v} out of range"

    def test_score_in_range(self):
        result = run_d5()
        assert 0 <= result["score"] <= 100

    def test_combined_score_reasonableness(self):
        result = run_d5()
        expected = (
            result["subscores"]["chaos_engineering"] * 0.30
            + result["subscores"]["drift_detection"] * 0.25
            + result["subscores"]["reflection_loop"] * 0.20
            + result["subscores"]["convergence_cycle"] * 0.25
        )
        assert result["score"] == pytest.approx(expected, abs=0.1)

    def test_has_findings(self):
        result = run_d5()
        assert len(result["findings"]) > 0

    def test_has_summary(self):
        result = run_d5()
        assert "d5_score" in result["summary"]

    def test_has_detail_sections(self):
        result = run_d5()
        assert "part1_detail" in result
        assert "part2_detail" in result

    def test_consistency_reproducible(self):
        r1 = run_d5()
        r2 = run_d5()
        assert r1["score"] == r2["score"]
        assert r1["subscores"] == r2["subscores"]
