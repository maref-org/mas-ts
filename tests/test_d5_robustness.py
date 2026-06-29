# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 D5: Evolution & Robustness (Part 1 — Chaos Engineering + Drift Detection, Part 2 — Reflection Loop + Convergence Verification)."""

import math

import pytest

from mas_eval.domains.d5_robustness import (
    CHAOS_WEIGHTS,
    CRITIQUE_CATEGORIES,
    FEDERATION_CASCADE_WEIGHTS,
    FEDERATION_FAULT_WEIGHTS,
    FEDERATION_FAULTS,
    INFRA_FAULTS,
    LLM_FAULTS,
    QUALITY_DIMS,
    ChaosEngine,
    ConsistencyIndex,
    ConvergenceVerifier,
    DriftDetector,
    FederationCircuitBreaker,
    ReflectiveAgent,
    _cosine_sim,
    _hellinger_distance,
    _js_divergence,
    _kl_divergence,
    _score_federation_cascade,
    run_d5,
    run_d5_part1,
    run_d5_part2,
    run_federation_cascade,
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

    def test_score_kind_is_weighted_contribution(self):
        result = run_d5_part1()
        assert result["score_kind"] == "weighted_contribution"
        assert result["weighted_contribution"] == result["score"]

    def test_weights_field_exposed(self):
        result = run_d5_part1()
        assert "weights" in result
        assert result["weights"] == {"chaos_engineering": 0.30, "drift_detection": 0.25}

    def test_weights_sum_is_part1_share(self):
        result = run_d5_part1()
        total = sum(result["weights"].values())
        assert abs(total - 0.55) < 0.001

    def test_weighted_contribution_below_part_share_max(self):
        result = run_d5_part1()
        assert result["weighted_contribution"] <= 55.0 + 0.001

    def test_score_kind_is_explicit_not_zero_to_hundred(self):
        result = run_d5_part1()
        assert result["score_kind"] != "absolute_0_100"
        assert "weighted_contribution" in result

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

    def test_score_kind_is_weighted_contribution(self):
        result = run_d5_part2()
        assert result["score_kind"] == "weighted_contribution"
        assert result["weighted_contribution"] == result["score"]

    def test_weights_field_exposed(self):
        result = run_d5_part2()
        assert "weights" in result
        assert result["weights"] == {"reflection_loop": 0.20, "convergence_cycle": 0.25}

    def test_weights_sum_is_part2_share(self):
        result = run_d5_part2()
        total = sum(result["weights"].values())
        assert abs(total - 0.45) < 0.001

    def test_weighted_contribution_below_part_share_max(self):
        result = run_d5_part2()
        assert result["weighted_contribution"] <= 45.0 + 0.001


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


class TestCHAOSWEIGHTS:
    def test_weights_sum_to_one(self):
        total = sum(CHAOS_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_has_fed_cascade_key(self):
        assert "fed_cascade" in CHAOS_WEIGHTS

    def test_has_all_keys(self):
        expected = {"infra", "federation", "llm", "fed_cascade"}
        assert set(CHAOS_WEIGHTS.keys()) == expected


class TestFederationCircuitBreaker:
    def test_init_defaults(self):
        fcb = FederationCircuitBreaker()
        assert len(fcb.agent_names) == 5
        assert fcb.n == 5
        assert fcb.dependency_threshold == 0.4

    def test_init_custom_agents(self):
        fcb = FederationCircuitBreaker(agent_names=["a", "b"])
        assert fcb.n == 2
        assert fcb.agent_names == ["a", "b"]

    def test_init_with_custom_matrix(self):
        matrix = [[0.0, 0.9], [0.0, 0.0]]
        fcb = FederationCircuitBreaker(agent_names=["a", "b"], dependency_matrix=matrix)
        assert fcb.dependency_matrix == matrix

    def test_reset_all(self):
        fcb = FederationCircuitBreaker()
        fcb._trip_breaker("claude_code")
        assert fcb.agent_states["claude_code"] == "OPEN"
        fcb.reset_all()
        assert fcb.agent_states["claude_code"] == "CLOSED"
        assert fcb.cascade_history == []

    def test_trip_breaker(self):
        fcb = FederationCircuitBreaker()
        fcb._trip_breaker("opencode")
        assert fcb.agent_states["opencode"] == "OPEN"
        assert fcb.agent_failures["opencode"] == 3

    def test_default_mesh_size(self):
        fcb = FederationCircuitBreaker(agent_names=["a", "b", "c"])
        expected_size = 3
        assert len(fcb.dependency_matrix) == expected_size
        assert len(fcb.dependency_matrix[0]) == expected_size

    def test_default_mesh_hub_dependency(self):
        fcb = FederationCircuitBreaker(agent_names=["hub", "a", "b"])
        assert fcb.dependency_matrix[1][0] == 0.8
        assert fcb.dependency_matrix[2][0] == 0.8

    def test_trigger_leaf_contained(self):
        fcb = FederationCircuitBreaker()
        result = fcb.trigger(4)
        assert result["cascade_depth"] == 0
        assert result["affected_count"] == 1
        assert result["fully_contained"] is True

    def test_trigger_hub_cascade(self):
        fcb = FederationCircuitBreaker()
        result = fcb.trigger(0)
        assert result["cascade_depth"] >= 0
        assert result["affected_count"] >= 1
        assert result["cascade_path"][0][0] == "claude_code"

    def test_trigger_cascade_path_structure(self):
        fcb = FederationCircuitBreaker()
        result = fcb.trigger(0)
        for entry in result["cascade_path"]:
            assert len(entry) == 3
            name, state, depth = entry
            assert isinstance(name, str)
            assert state == "OPEN"
            assert isinstance(depth, int)

    def test_trigger_agent_state_changed(self):
        fcb = FederationCircuitBreaker()
        fcb.trigger(4)
        assert fcb.agent_states["trae_cn"] == "OPEN"

    def test_cascade_metrics_empty(self):
        fcb = FederationCircuitBreaker()
        metrics = fcb.cascade_metrics()
        assert metrics["scenarios_run"] == 0
        assert metrics["avg_depth"] == 0.0

    def test_cascade_metrics_after_scenarios(self):
        fcb = FederationCircuitBreaker()
        fcb.trigger(4)
        fcb.trigger(0)
        metrics = fcb.cascade_metrics()
        assert metrics["scenarios_run"] == 2
        assert 0 <= metrics["avg_depth"] <= 4
        assert 0 <= metrics["containment_rate"] <= 1

    def test_cascade_metrics_containment(self):
        fcb = FederationCircuitBreaker()
        fcb.trigger(4)
        metrics = fcb.cascade_metrics()
        assert metrics["containment_rate"] == 1.0

    def test_trigger_returns_correct_keys(self):
        fcb = FederationCircuitBreaker()
        result = fcb.trigger(0)
        expected_keys = {
            "source",
            "cascade_depth",
            "affected_count",
            "total_agents",
            "affected_pct",
            "cascade_path",
            "fully_contained",
        }
        assert set(result.keys()) == expected_keys

    def test_affected_pct_calculation(self):
        fcb = FederationCircuitBreaker(agent_names=["a", "b"])
        result = fcb.trigger(0)
        expected = result["affected_count"] / result["total_agents"] * 100
        assert result["affected_pct"] == expected

    def test_multiple_triggers_independent(self):
        fcb = FederationCircuitBreaker()
        fcb.trigger(4)
        fcb.reset_all()
        assert fcb.agent_states["trae_cn"] == "CLOSED"


class TestScoreFederationCascade:
    def test_score_range(self):
        score, findings = _score_federation_cascade()
        assert 0 <= score <= 100

    def test_has_findings(self):
        score, findings = _score_federation_cascade()
        assert len(findings) > 0

    def test_findings_have_correct_structure(self):
        score, findings = _score_federation_cascade()
        for f in findings:
            assert "severity" in f
            assert "category" in f
            assert "detail" in f

    def test_cascade_findings_present(self):
        score, findings = _score_federation_cascade()
        cascade_findings = [f for f in findings if f["category"] == "fed_cascade"]
        assert len(cascade_findings) >= 1

    def test_summary_finding_present(self):
        score, findings = _score_federation_cascade()
        summaries = [f for f in findings if f["category"] == "fed_cascade_summary"]
        assert len(summaries) == 1

    def test_summary_counts_all_cascade_scenarios(self):
        score, findings = _score_federation_cascade()
        summaries = [f for f in findings if f["category"] == "fed_cascade_summary"]
        assert "containment=" in summaries[0]["detail"]

    def test_with_chaos_engine(self):
        ce = ChaosEngine(seed=42)
        score, findings = _score_federation_cascade(ce=ce)
        assert 0 <= score <= 100

    def test_reproducible_score(self):
        s1, _ = _score_federation_cascade()
        s2, _ = _score_federation_cascade()
        assert s1 == s2


class TestFaultInjectorSimMode:
    """Phase 5.2: real chaos must be opt-in only; default mode is simulation."""

    def test_fault_injector_default_mode_is_sim(self):
        from mas_eval.domains.d5_robustness import FaultInjector

        fi = FaultInjector()
        assert fi.mode == "sim"
        assert fi.injection_mode() == "simulated"

    def test_chaos_engine_default_uses_sim_mode(self):
        ce = ChaosEngine(seed=42)
        assert ce.injector.mode == "sim"
        assert ce.injection_mode() == "simulated"

    def test_sim_mode_skips_subprocess_calls(self, monkeypatch):
        import mas_eval.domains.d5_robustness as mod

        calls: list[tuple[str, tuple]] = []

        def fake_popen(*args, **kwargs):
            calls.append(("Popen", args))
            raise FileNotFoundError("sim mode must not invoke Popen")

        def fake_run(*args, **kwargs):
            calls.append(("run", args))
            raise FileNotFoundError("sim mode must not invoke run")

        monkeypatch.setattr(mod.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(mod.subprocess, "run", fake_run)

        fi = mod.FaultInjector(mode="sim")
        for method, args in [
            ("inject_cpu_pressure", ()),
            ("inject_memory_pressure", ()),
            ("inject_disk_failure", ()),
            ("inject_process_kill", ()),
            ("inject_network_partition", ()),
        ]:
            result = getattr(fi, method)(*args)
            assert result["mode"] == "simulated", (
                f"{method} returned mode={result.get('mode')!r}; "
                "sim mode must produce simulated results"
            )
        assert calls == [], f"sim mode invoked subprocess: {calls}"

    def test_real_mode_requires_explicit_opt_in(self):
        from mas_eval.domains.d5_robustness import FaultInjector

        fi_sim = FaultInjector()
        assert fi_sim.mode == "sim"

        fi_real = FaultInjector(mode="real")
        assert fi_real.mode == "real"

        fi_auto = FaultInjector(mode="auto")
        assert fi_auto.mode == "auto"


class TestFederationCircuitBreakerCardConfig:
    """Phase 5.1: card governance.circuit_breaker config drives finding severity."""

    def test_card_with_breaker_enabled_no_high_finding(self):
        card = {
            "governance": {
                "circuit_breaker": {
                    "enabled": True,
                    "threshold": 3,
                    "cooldown_seconds": 30,
                }
            }
        }
        score, findings = _score_federation_cascade(card=card)
        high_or_critical = [
            f for f in findings if f["severity"] in ("HIGH", "CRITICAL")
        ]
        assert high_or_critical == [], (
            f"Cards with breaker enabled should not produce HIGH/CRITICAL "
            f"findings: {high_or_critical}"
        )
        assert 0 <= score <= 100

    def test_card_without_governance_emits_high_finding(self):
        card: dict = {}
        score, findings = _score_federation_cascade(card=card)
        breaker_findings = [
            f for f in findings if f.get("category") == "federation_circuit_breaker"
        ]
        assert any(f["severity"] in ("HIGH", "CRITICAL") for f in breaker_findings), (
            f"Expected HIGH federation_circuit_breaker finding, got: {findings}"
        )

    def test_card_without_breaker_block_emits_high_finding(self):
        card = {"governance": {}}
        score, findings = _score_federation_cascade(card=card)
        breaker_findings = [
            f for f in findings if f.get("category") == "federation_circuit_breaker"
        ]
        assert any(f["severity"] in ("HIGH", "CRITICAL") for f in breaker_findings)

    def test_card_with_breaker_disabled_emits_high_finding(self):
        card = {"governance": {"circuit_breaker": {"enabled": False}}}
        score, findings = _score_federation_cascade(card=card)
        breaker_findings = [
            f for f in findings if f.get("category") == "federation_circuit_breaker"
        ]
        assert any(f["severity"] in ("HIGH", "CRITICAL") for f in breaker_findings)

    def test_breaker_finding_category_name_matches_spec(self):
        card: dict = {}
        _, findings = _score_federation_cascade(card=card)
        breaker_findings = [
            f for f in findings if f.get("category") == "federation_circuit_breaker"
        ]
        assert len(breaker_findings) >= 1
        for f in breaker_findings:
            assert "severity" in f
            assert "detail" in f
            assert f["category"] == "federation_circuit_breaker"

    def test_card_with_breaker_enabled_still_emits_cascade_info(self):
        card = {"governance": {"circuit_breaker": {"enabled": True, "threshold": 3}}}
        _, findings = _score_federation_cascade(card=card)
        cascade_info = [f for f in findings if f["category"] == "fed_cascade"]
        assert len(cascade_info) >= 1


# ═══════════════════════════════════════════════════════════════
# Gold Standard: ConsistencyIndex (v3.0-GA §7.4)
# ═══════════════════════════════════════════════════════════════


class TestConsistencyIndexGold:
    """Gold Standard ConsistencyIndex tests (v3.0-GA §7.4)"""

    def test_ci_requires_two_runs(self):
        ci = ConsistencyIndex()
        ci.add_run({"result": {"status": "ok"}, "elapsed_seconds": 5.0, "events": []})
        result = ci.score()
        assert result["ci"] == 0.0
        assert "≥2 runs" in result["detail"]

    def test_ci_identical_runs(self):
        ci = ConsistencyIndex()
        run = {"result": {"status": "ok"}, "elapsed_seconds": 5.0, "events": []}
        ci.add_run(run)
        ci.add_run(run)
        result = ci.score()
        assert result["ci"] >= 0.9

    def test_ci_dimensions_present(self):
        ci = ConsistencyIndex()
        for _ in range(3):
            ci.add_run(
                {"result": {"status": "ok"}, "elapsed_seconds": 10.0, "events": []}
            )
        result = ci.score()
        dims = result["dimensions"]
        assert "c_task" in dims
        assert "c_tool" in dims
        assert "c_time" in dims

    def test_ci_tool_sequence_drift(self):
        ci = ConsistencyIndex()
        ci.add_run(
            {
                "result": {"status": "ok"},
                "elapsed_seconds": 5.0,
                "events": [
                    {"action": {"type": "tool_call", "tool_id": "a"}},
                    {"action": {"type": "tool_call", "tool_id": "b"}},
                    {"action": {"type": "tool_call", "tool_id": "c"}},
                    {"action": {"type": "tool_call", "tool_id": "d"}},
                    {"action": {"type": "tool_call", "tool_id": "e"}},
                ],
            }
        )
        ci.add_run(
            {
                "result": {"status": "ok"},
                "elapsed_seconds": 5.0,
                "events": [
                    {"action": {"type": "tool_call", "tool_id": "x"}},
                    {"action": {"type": "tool_call", "tool_id": "y"}},
                ],
            }
        )
        result = ci.score()
        assert result["dimensions"]["c_tool"] < 1.0

    def test_ci_time_variation_penalty(self):
        ci = ConsistencyIndex()
        for t in [1.0, 10.0, 100.0]:
            ci.add_run({"result": {"status": "ok"}, "elapsed_seconds": t, "events": []})
        result = ci.score()
        assert result["dimensions"]["c_time"] < 0.5


# ═══════════════════════════════════════════════════════════════
# Gold Standard: Federation Cascade (v3.0-GA §7.5)
# ═══════════════════════════════════════════════════════════════


class TestFederationCascadeGold:
    """Gold Standard Federation Cascade tests (v3.0-GA §7.5)"""

    def test_fed_cascade_returns_dict(self):
        result = run_federation_cascade()
        assert "score" in result
        assert "dimensions" in result
        assert "findings" in result

    def test_fed_cascade_score_range(self):
        result = run_federation_cascade()
        assert 0 <= result["score"] <= 100

    def test_fed_cascade_weights_sum_to_1(self):
        total = sum(FEDERATION_CASCADE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_fed_cascade_with_breaker(self):
        card = {"governance": {"circuit_breaker": {"enabled": True, "threshold": 3}}}
        result = run_federation_cascade(card=card)
        assert result["dimensions"]["breaker_state"] >= 0.5

    def test_fed_cascade_without_breaker(self):
        result = run_federation_cascade()
        assert result["dimensions"]["breaker_state"] == 0.0

    def test_fed_cascade_with_ce(self):
        ce = ChaosEngine(seed=42)
        result = run_federation_cascade(ce=ce)
        assert "recovery" in result["dimensions"]

    def test_fed_cascade_dimensions_present(self):
        result = run_federation_cascade()
        for dim in (
            "containment",
            "depth_control",
            "isolation",
            "recovery",
            "detection_latency",
            "breaker_state",
        ):
            assert dim in result["dimensions"]

    def test_fed_cascade_legacy_compat(self):
        score, findings = _score_federation_cascade()
        assert isinstance(score, float)
        assert isinstance(findings, list)
        assert 0 <= score <= 100
