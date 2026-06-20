# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for VerifierRegistry — pluggable verifier + cross-validation."""

import pytest

from mas_eval.scoring.verifier import MockVerifier, Verifier, VerifierRegistry


class TestVerifier:
    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Verifier("abstract")

    def test_mock_verifier(self):
        v = MockVerifier(name="test-judge", score=85.0)
        result = v.evaluate("task_1", ["response"])
        assert result["verifier"] == "test-judge"
        assert result["score"] == 85.0
        assert result["task_id"] == "task_1"

    def test_eval_count(self):
        v = MockVerifier(name="counter")
        v.evaluate("t1", ["r1"])
        v.evaluate("t2", ["r2"])
        assert v.eval_count == 2

    def test_verifier_records_accuracy(self):
        v = MockVerifier(name="v1")
        v.record_accuracy(0.85)
        assert v.accuracy == 0.85


class TestVerifierRegistry:
    def test_register_verifier(self):
        registry = VerifierRegistry()
        v = MockVerifier(name="test-judge", score=85.0)
        registry.register(v)
        assert "test-judge" in registry.list_verifiers()

    def test_unregister(self):
        registry = VerifierRegistry()
        v = MockVerifier(name="v1")
        registry.register(v)
        registry.unregister("v1")
        assert "v1" not in registry.list_verifiers()

    def test_get_verifier(self):
        registry = VerifierRegistry()
        v = MockVerifier(name="v1")
        registry.register(v)
        assert registry.get("v1") is v
        assert registry.get("nonexistent") is None

    def test_evaluate_all(self):
        registry = VerifierRegistry()
        registry.register(MockVerifier(name="v1", score=85.0))
        registry.register(MockVerifier(name="v2", score=90.0))
        results = registry.evaluate_all("task_1", ["response_a"])
        assert len(results) == 2
        assert all("score" in r for r in results)
        assert all("verifier" in r for r in results)

    def test_consensus_score(self):
        registry = VerifierRegistry()
        registry.register(MockVerifier(name="v1", score=85.0))
        registry.register(MockVerifier(name="v2", score=90.0))
        result = registry.consensus_evaluate("task_1", ["response_a"])
        assert "consensus_score" in result
        assert "individual_scores" in result
        assert "agreement" in result
        assert result["consensus_score"] == 87.5
        assert result["agreement"] == 1.0

    def test_consensus_low_agreement(self):
        registry = VerifierRegistry()
        registry.register(MockVerifier(name="v1", score=50.0))
        registry.register(MockVerifier(name="v2", score=90.0))
        result = registry.consensus_evaluate("task_1", ["response"])
        assert result["consensus_score"] == 70.0
        assert result["agreement"] < 1.0
        assert result["verifier_count"] == 2

    def test_consensus_empty_registry(self):
        registry = VerifierRegistry()
        result = registry.consensus_evaluate("task_1", ["response"])
        assert result["consensus_score"] == 0.0
        assert result["verifier_count"] == 0

    def test_run_d5_with_verifier_registry(self):
        from mas_eval.domains.d5_robustness import run_d5

        registry = VerifierRegistry()
        v1 = MockVerifier(name="v1", score=88.0)
        v2 = MockVerifier(name="v2", score=92.0)
        registry.register(v1)
        registry.register(v2)

        result_with_reg = run_d5(verifier_registry=registry)

        assert result_with_reg["domain"] == "D5"
        assert 0 <= result_with_reg["score"] <= 100
        assert v1.eval_count > 0
        assert v2.eval_count > 0

    def test_convergence_verifier_uses_registry_for_c1_and_c2_all_tasks(self):
        from mas_eval.domains.d5_robustness import ConvergenceVerifier

        registry = VerifierRegistry()
        v1 = MockVerifier(name="v1", score=88.0)
        v2 = MockVerifier(name="v2", score=92.0)
        registry.register(v1)
        registry.register(v2)

        cv = ConvergenceVerifier()
        cv.set_verifier_registry(registry)
        for task_id in ("math", "code"):
            cv.add_response(task_id, "answer one")
            cv.add_response(task_id, "answer two")
            cv.add_response(task_id, "answer three")

        c1 = cv.score_c1_consistency()
        c2 = cv.score_c2_self_consistency()

        assert 0 <= c1 <= 1
        assert 0 <= c2 <= 1
        assert v1.eval_count == 4
        assert v2.eval_count == 4
