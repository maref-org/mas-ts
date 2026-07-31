# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for Meta-Evaluator (Gold Standard §11)."""

from mas_eval.scoring.meta_evaluator import MetaEvaluator


class TestMetaEvaluator:
    def test_empty_no_runs(self):
        me = MetaEvaluator()
        result = me.overall_meta_score()
        assert "meta_score" in result
        assert "confidence" in result

    def test_reproducibility_needs_3_runs(self):
        me = MetaEvaluator()
        for i in range(2):
            me.record_run({"model": "x"}, {"overall": 80.0})
        assert me.score_reproducibility() == 0.0

    def test_reproducibility_identical(self):
        me = MetaEvaluator()
        for _ in range(3):
            me.record_run({"model": "x"}, {"overall": 85.0})
        assert me.score_reproducibility() >= 0.9

    def test_reproducibility_divergent(self):
        me = MetaEvaluator()
        for score in [70, 90, 50]:
            me.record_run({"model": "x"}, {"overall": float(score)})
        assert me.score_reproducibility() < 0.8

    def test_discriminability_perfect(self):
        me = MetaEvaluator()
        score = me.score_discriminability({"overall": 30}, {"overall": 90})
        assert score == 1.0

    def test_discriminability_poor(self):
        me = MetaEvaluator()
        score = me.score_discriminability({"overall": 75}, {"overall": 80})
        assert score < 0.5

    def test_confidence_high(self):
        me = MetaEvaluator()
        for _ in range(3):
            me.record_run({"model": "x"}, {"overall": 85.0})
        result = me.overall_meta_score(
            weak_result={"overall": 30}, strong_result={"overall": 90}
        )
        assert result["confidence"] == "high"
        assert result["meta_score"] >= 0.7

    def test_confidence_low(self):
        me = MetaEvaluator()
        result = me.overall_meta_score()
        assert "low" in result["confidence"]  # Should contain "low"
        assert (
            "低置信度" in result["confidence"]
        )  # Should contain low confidence marker
        assert result["low_confidence"] is True

    def test_robustness_perfect(self):
        me = MetaEvaluator()
        base_result = {"overall": 85.0}
        perturbed_result = {"overall": 86.0}  # Only 1 point difference
        score = me.score_robustness(base_result, perturbed_result)
        assert score == 1.0  # diff ≤ 2 → perfect score

    def test_robustness_poor(self):
        me = MetaEvaluator()
        base_result = {"overall": 85.0}
        perturbed_result = {"overall": 100.0}  # 15 point difference
        score = me.score_robustness(base_result, perturbed_result)
        assert score == 0.0  # diff > 10 → zero score

    def test_robustness_gradual(self):
        me = MetaEvaluator()
        base_result = {"overall": 85.0}
        perturbed_result = {"overall": 90.0}  # 5 point difference
        score = me.score_robustness(base_result, perturbed_result)
        # diff = 5, should be between 0.5 and 1.0
        assert 0.5 < score < 1.0

    def test_efficiency_perfect(self):
        me = MetaEvaluator()
        # eval_time = 100ms, task_time = 1000ms → overhead = 10% ≤ 20%
        score = me.score_efficiency(100, 1000)
        assert score == 1.0

    def test_efficiency_poor(self):
        me = MetaEvaluator()
        # eval_time = 2000ms, task_time = 1000ms → overhead = 200% > 100%
        score = me.score_efficiency(2000, 1000)
        assert score == 0.0

    def test_efficiency_gradual(self):
        me = MetaEvaluator()
        # eval_time = 500ms, task_time = 1000ms → overhead = 50%
        # Should be between 0.5 and 1.0 (linear decay from 20% to 100%)
        score = me.score_efficiency(500, 1000)
        assert 0.5 < score < 1.0

    def test_efficiency_zero_task_time(self):
        me = MetaEvaluator()
        score = me.score_efficiency(100, 0)
        assert score == 0.0

    def test_dynamic_robustness_in_overall(self):
        me = MetaEvaluator()
        base_result = {"overall": 85.0}
        perturbed_result = {"overall": 86.0}

        result = me.overall_meta_score(robustness_data=(base_result, perturbed_result))
        assert "robustness" in result["dimensions"]
        # With perfect robustness, score should be 1.0
        assert result["dimensions"]["robustness"] == 1.0

    def test_dynamic_efficiency_in_overall(self):
        me = MetaEvaluator()
        # Add some runs for reproducibility
        for _ in range(3):
            me.record_run({"model": "x"}, {"overall": 85.0})

        result = me.overall_meta_score(
            weak_result={"overall": 30},
            strong_result={"overall": 90},
            efficiency_data=(100, 1000),  # 10% overhead
        )
        assert "efficiency" in result["dimensions"]
        # With 10% overhead, efficiency should be 1.0
        assert result["dimensions"]["efficiency"] == 1.0

    def test_low_confidence_marker(self):
        me = MetaEvaluator()
        # No runs, low reproducibility, should get low confidence
        result = me.overall_meta_score()
        assert "低置信度" in result["confidence"]
        assert result["low_confidence"] is True

    def test_anti_cheat_placeholder(self):
        me = MetaEvaluator()
        score = me.score_anti_cheat()
        assert score == 0.5  # Placeholder without red-team data

    def test_anti_cheat_dynamic_no_data(self):
        me = MetaEvaluator()
        # No red_team_results → placeholder 0.5
        result = me.overall_meta_score()
        assert result["dimensions"]["anti_cheat"] == 0.5

    def test_anti_cheat_good(self):
        me = MetaEvaluator()
        red_team_results = [
            {
                "attack_type": "prompt_injection",
                "detected": True,
                "gamification_score": 0.1,
            },
            {
                "attack_type": "metric_gaming",
                "detected": True,
                "gamification_score": 0.2,
            },
            {
                "attack_type": "boundary_case",
                "detected": False,
                "gamification_score": 0.3,
            },
        ]
        score = me.score_anti_cheat(red_team_results)
        # detection_rate = 2/3 = 0.667, avg_gamification = 0.2
        # score = 0.667*0.6 + 0.8*0.4 = 0.4 + 0.32 = 0.72
        assert score == 0.72

    def test_anti_cheat_poor(self):
        me = MetaEvaluator()
        red_team_results = [
            {
                "attack_type": "prompt_injection",
                "detected": False,
                "gamification_score": 0.9,
            },
            {
                "attack_type": "metric_gaming",
                "detected": False,
                "gamification_score": 0.8,
            },
        ]
        score = me.score_anti_cheat(red_team_results)
        # detection_rate = 0, avg_gamification = 0.85
        # score = 0*0.6 + 0.15*0.4 = 0.06
        assert score == 0.06


class TestReproducibilityVariance:
    """Tests for MetaEvaluator.score_reproducibility_variance (Phase 3 §6.3)."""

    def test_reproducibility_variance_insufficient(self):
        me = MetaEvaluator()
        # < 2 runs → insufficient data
        me.record_run({"model": "x"}, {"overall": 85.0})
        r = me.score_reproducibility_variance()
        assert r["score"] == 0.0
        assert r["verdict"] == "insufficient_data"
        assert r["n_runs"] == 1

    def test_reproducibility_variance_empty(self):
        me = MetaEvaluator()
        r = me.score_reproducibility_variance()
        assert r["score"] == 0.0
        assert r["verdict"] == "insufficient_data"
        assert r["n_runs"] == 0

    def test_reproducibility_variance_identical(self):
        me = MetaEvaluator()
        for _ in range(3):
            me.record_run({"model": "x"}, {"overall": 85.0})
        r = me.score_reproducibility_variance()
        assert r["score"] == 100.0
        assert r["cv"] == 0.0
        assert r["verdict"] == "excellent"
        assert r["n_runs"] == 3

    def test_reproducibility_variance_divergent(self):
        me = MetaEvaluator()
        for s in [70.0, 90.0, 50.0]:
            me.record_run({"model": "x"}, {"overall": s})
        r = me.score_reproducibility_variance()
        assert r["score"] < 80.0  # divergent → not excellent
        assert r["cv"] > 0.0
        assert r["n_runs"] == 3

    def test_reproducibility_variance_uses_self_runs(self):
        # When runs=None, uses self.eval_runs
        me = MetaEvaluator()
        for s in [80.0, 80.0]:
            me.record_run({"model": "x"}, {"overall": s})
        r = me.score_reproducibility_variance()
        assert r["n_runs"] == 2
        assert r["score"] == 100.0

    def test_reproducibility_variance_explicit_runs(self):
        # Explicit runs arg overrides self.eval_runs
        me = MetaEvaluator()
        me.record_run({"model": "x"}, {"overall": 50.0})
        runs = [{"overall": 90.0}, {"overall": 90.0}, {"overall": 90.0}]
        r = me.score_reproducibility_variance(runs=runs)
        assert r["n_runs"] == 3
        assert r["score"] == 100.0
        assert r["values"] == [90.0, 90.0, 90.0]

    def test_reproducibility_variance_custom_metric(self):
        me = MetaEvaluator()
        for s in [85.0, 85.0, 85.0]:
            me.record_run({"model": "x"}, {"overall": s, "d4": 70.0})
        r = me.score_reproducibility_variance(metric="d4")
        assert r["metric"] == "d4"
        assert r["score"] == 100.0
        assert r["values"] == [70.0, 70.0, 70.0]

    def test_reproducibility_variance_verdict_labels(self):
        me = MetaEvaluator()
        # identical → excellent
        for _ in range(2):
            me.record_run({"model": "x"}, {"overall": 80.0})
        assert me.score_reproducibility_variance()["verdict"] == "excellent"
        # highly divergent → poor
        me2 = MetaEvaluator()
        me2.record_run({"model": "x"}, {"overall": 10.0})
        me2.record_run({"model": "x"}, {"overall": 90.0})
        assert me2.score_reproducibility_variance()["verdict"] == "poor"


class TestCanonicalAttackRegexCoupling:
    """Verify each canonical attack text matches at least one regex pattern.

    Phase 3 (review finding #2): _CANONICAL_ATTACKS texts are implicitly
    coupled to DIRECT_INJECTION_VECTORS / JAILBREAK_VECTORS regex patterns.
    If a regex changes, the corresponding canonical text may silently stop
    matching, inflating probe 4's escape_rate. This test provides the
    automated sync check missing from the module-level design.
    """

    def test_each_canonical_attack_matches_at_least_one_regex(self):
        from mas_eval.scoring.meta_evaluator import (
            _CANONICAL_ATTACKS,
            _get_injection_regexes,
        )

        regexes = _get_injection_regexes()
        unmatchable: list[str] = []

        for attack_id, text in _CANONICAL_ATTACKS.items():
            if not any(p.search(text) for p in regexes):
                unmatchable.append(attack_id)

        assert not unmatchable, (
            f"Canonical attack texts not matched by any regex: {unmatchable}. "
            "Update _CANONICAL_ATTACKS or the regex patterns in "
            "d4_injection_detection.py to restore coupling."
        )

    def test_probe4_sample_escapes_covers_distinct_attack_types(self):
        """Verify stratified sampling produces diverse attack types."""
        from mas_eval.scoring.meta_evaluator import _run_probe4_adversarial_mutation

        result = _run_probe4_adversarial_mutation()
        sample = result["sample_escapes"]
        if len(sample) <= 1:
            return  # Not enough escapes to test diversity
        attack_ids = {e["attack_id"] for e in sample}
        # At least 2 distinct attack types if sample has ≥2 entries
        assert len(attack_ids) >= min(2, len(sample)), (
            f"Stratified sample should cover distinct attack types, "
            f"got {attack_ids} from {len(sample)} samples"
        )
