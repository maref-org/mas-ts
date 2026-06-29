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
        assert result["confidence"] == "low"
