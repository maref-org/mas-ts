# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for FederationCascadeTester (Gold Standard §7.5 extended, v0.11.0)."""

from mas_eval.domains.d5_robustness import (
    FederationCascadeTester,
    run_d5,
    run_federation_cascade_tester,
)


def test_run_returns_gold_shape():
    """Canonical run returns score/dimensions/findings keys."""
    result = run_federation_cascade_tester()
    assert result["domain"] == "D5"
    assert result["component"] == "federation_cascade_tester"
    assert set(result) >= {"score", "dimensions", "findings"}
    assert set(result["dimensions"]) == {
        "single_agent_isolation",
        "cascade_depth_control",
        "circuit_breaker_propagation",
        "recovery_propagation",
        "split_brain_detection",
    }
    assert 0.0 <= result["score"] <= 100.0


def test_single_agent_isolation_ratio_in_range():
    """Isolation dimension is a valid ratio in [0, 1]."""
    tester = FederationCascadeTester(num_agents=4, seed=42)
    tester.inject_fault(0)
    tester.propagate()
    iso = tester._score_single_agent_isolation()
    assert 0.0 <= iso <= 1.0


def test_single_agent_isolation_perfect_with_no_peers_failed():
    """With only agent 0 failed and no propagation, peers stay isolated."""
    tester = FederationCascadeTester(num_agents=4, seed=7)
    tester.inject_fault(0)
    # Force no cascade by patching propagation probability to zero.
    tester._cascade_probability = lambda hop: 0.0  # type: ignore[method-assign]
    tester.propagate()
    assert tester._score_single_agent_isolation() == 1.0


def test_cascade_depth_sla_dimension():
    """Depth control dimension reports hops and stays within [0, 1]."""
    tester = FederationCascadeTester(num_agents=5, seed=42)
    tester.inject_fault(0)
    tester.propagate()
    score, depth = tester._score_cascade_depth()
    assert isinstance(depth, int)
    assert 0.0 <= score <= 1.0


def test_circuit_breaker_propagation_returns_ratio_and_latency():
    """Breaker propagation scoring returns (ratio, max_latency)."""
    tester = FederationCascadeTester(num_agents=4, seed=42)
    tester.inject_fault(0)
    tester.propagate()
    ratio, max_latency = tester._score_circuit_breaker_propagation()
    assert 0.0 <= ratio <= 1.0
    assert max_latency >= 0.0


def test_recovery_propagation_latency_within_sla():
    """Recovery re-sync latency is recorded and scored as a valid ratio."""
    tester = FederationCascadeTester(num_agents=4, seed=42)
    tester.inject_fault(0)
    tester.propagate()
    tester.simulate_recovery()
    ratio, max_latency = tester._score_recovery_propagation()
    assert 0.0 <= ratio <= 1.0
    assert max_latency >= 0.0


def test_split_brain_detected_under_partition():
    """Default scenario with ≥2 healthy agents detects split-brain."""
    tester = FederationCascadeTester(num_agents=4, seed=42)
    tester.inject_fault(0)
    tester.propagate()
    assert tester.detect_split_brain() is True
    assert tester._score_split_brain_detection() == 1.0


def test_split_brain_undetected_single_agent():
    """A single-agent federation cannot detect split-brain."""
    tester = FederationCascadeTester(num_agents=2, seed=42)
    tester.inject_fault(0)
    tester.propagate()
    assert tester.detect_split_brain() is False
    assert tester._score_split_brain_detection() == 0.0


def test_deterministic_across_runs():
    """Same seed yields identical dimension scores (Gold §7.5 reproducibility)."""
    r1 = FederationCascadeTester(num_agents=4, seed=42).run()
    r2 = FederationCascadeTester(num_agents=4, seed=42).run()
    assert r1["dimensions"] == r2["dimensions"]
    assert r1["score"] == r2["score"]


def test_invalid_agent_index_raises():
    """inject_fault rejects out-of-range indices."""
    tester = FederationCascadeTester(num_agents=4, seed=42)
    import pytest

    with pytest.raises(ValueError):
        tester.inject_fault(9)


def test_run_d5_includes_cascade_tester():
    """run_d5 surfaces the FederationCascadeTester result without altering D5 score shape."""
    result = run_d5()
    assert "federation_cascade_tester" in result
    assert "federation_cascade_tester_score" in result["summary"]
    assert 0.0 <= result["summary"]["federation_cascade_tester_score"] <= 100.0
    assert any(
        f.get("category") == "fed_cascade_tester" for f in result["findings"]
    )


def test_custom_num_agents_two():
    """A 2-agent federation runs the scenario without error."""
    tester = FederationCascadeTester(num_agents=2, seed=42)
    result = tester.run()
    assert result["score"] >= 0.0
    assert result["dimensions"]["single_agent_isolation"] == 1.0
