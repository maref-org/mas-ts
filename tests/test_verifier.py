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
        registry.register(MockVerifier(name="v1", score=88.0))
        registry.register(MockVerifier(name="v2", score=92.0))

        result = run_d5(verifier_registry=registry)
        assert result["domain"] == "D5"
        assert 0 <= result["score"] <= 100
        assert "chaos_engineering" in result["subscores"]
        assert "reflection_loop" in result["subscores"]
