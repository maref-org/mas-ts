# SPDX-FileCopyrightText: 2026 frankiehot-tech
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
