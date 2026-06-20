# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for Loop Engineering — ConvergenceLoop, Adaptive Escalation, Verifier."""

from mas_eval.harness.loop_engine import ConvergenceLoop

SAMPLE_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:loop-001",
    "name": "LoopTest",
    "version": "1.0.0",
    "compliance": {"data_residency": "US", "data_classification": "internal"},
    "constitution": {
        "health_state": "HEALTHY",
        "heartbeat_interval_seconds": 30,
    },
    "model_backend": {"provider": "test", "model": "claude-sonnet-4"},
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "run commands",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
            "business_rule_version": "2026-05-01",
        }
    ],
    "authentication": {"type": "OAuth2", "scopes": ["read", "write"]},
}


class TestConvergenceLoop:
    def test_init_defaults(self):
        loop = ConvergenceLoop()
        assert loop.max_iterations == 5
        assert loop.convergence_delta == 0.5
        assert loop.regression_threshold == -20.0
        assert loop.history == []

    def test_init_custom(self):
        loop = ConvergenceLoop(
            max_iterations=10, convergence_delta=0.2, regression_threshold=-10.0
        )
        assert loop.max_iterations == 10
        assert loop.convergence_delta == 0.2
        assert loop.regression_threshold == -10.0

    def test_run_returns_summary(self):
        def stub_runner(card, **kw):
            return {"score": 75.0, "findings": [], "domain_scores": {"d1": 80.0}}

        loop = ConvergenceLoop(max_iterations=3, convergence_delta=5.0)
        result = loop.run(SAMPLE_CARD, stub_runner)
        assert "final_score" in result
        assert "iterations" in result
        assert "converged" in result
        assert "score_trajectory" in result
        assert "findings" in result
        assert result["iterations"] >= 1

    def test_run_converges_early(self):
        """Score stabilizes → stops before max_iterations."""
        called = [0]

        def converging_runner(card, **kw):
            called[0] += 1
            return {"score": 80.0, "findings": [], "domain_scores": {"d1": 80.0}}

        loop = ConvergenceLoop(max_iterations=10, convergence_delta=1.0)
        result = loop.run(SAMPLE_CARD, converging_runner)
        assert result["converged"] is True
        assert result["iterations"] < 10
        assert called[0] >= 2

    def test_run_stops_at_max(self):
        """Never converges → stops at max_iterations."""
        scores = iter([70.0, 72.0, 74.0, 76.0, 78.0, 80.0])

        def climbing_runner(card, **kw):
            return {
                "score": next(scores),
                "findings": [],
                "domain_scores": {},
            }

        loop = ConvergenceLoop(max_iterations=3, convergence_delta=0.1)
        result = loop.run(SAMPLE_CARD, climbing_runner)
        assert result["converged"] is False
        assert result["iterations"] == 3
        assert result["stop_reason"] == "max_iterations"

    def test_run_detects_regression(self):
        """Score drops by > threshold → diverged, stops early."""
        scores = iter([80.0, 75.0, 50.0])

        def regressing_runner(card, **kw):
            return {
                "score": next(scores),
                "findings": [
                    {
                        "severity": "HIGH",
                        "category": "regression",
                        "detail": "score dropped",
                    }
                ],
                "domain_scores": {},
            }

        loop = ConvergenceLoop(max_iterations=5, regression_threshold=-10.0)
        result = loop.run(SAMPLE_CARD, regressing_runner)
        assert result["converged"] is False
        assert result["stop_reason"] == "regression"
        assert result["iterations"] == 3

    def test_stops_on_resource_exhaustion(self):
        from mas_eval.harness.resource_governor import ResourceGovernor, TokenBudget

        budget = TokenBudget(max_calls=1)
        governor = ResourceGovernor(budget=budget)
        called = [0]

        def runner(card, **kw):
            called[0] += 1
            return {"score": 80.0, "findings": [], "domain_scores": {}}

        loop = ConvergenceLoop(max_iterations=10, resource_governor=governor)
        result = loop.run(SAMPLE_CARD, runner)
        assert result["stop_reason"] == "resource_exhausted"
        assert called[0] == 1

    def test_stops_on_circuit_open_after_repeated_runner_failures(self):
        from mas_eval.harness.resource_governor import ResourceGovernor

        governor = ResourceGovernor()
        called = [0]

        def runner(card, **kw):
            called[0] += 1
            raise RuntimeError("boom")

        loop = ConvergenceLoop(max_iterations=10, resource_governor=governor)
        result = loop.run(SAMPLE_CARD, runner)
        assert result["stop_reason"] == "circuit_open"
        assert result["iterations"] == 0
        assert called[0] == 3

    def test_wraps_l3_runner(self):
        from mas_eval.harness.l3_comprehensive import run_l3_comprehensive

        loop = ConvergenceLoop(max_iterations=5, convergence_delta=50.0)
        result = loop.run(SAMPLE_CARD, run_l3_comprehensive)
        assert result["iterations"] >= 3
        assert 0 <= result["final_score"] <= 100
        assert result["stop_reason"] == "converged"
