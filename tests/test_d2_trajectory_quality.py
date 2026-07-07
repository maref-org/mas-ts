# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for Trajectory Quality D2 Gold Standard metric."""

from mas_eval.domains.d2_trajectory_quality import (
    check_trajectory_quality_thresholds,
    run_trajectory_quality,
)


class TestTrajectoryQuality:
    def test_empty_trajectory(self):
        result = run_trajectory_quality(None)
        assert result["trajectory_quality"] == 0.0
        assert result["optimality"] == 0.0
        assert result["coherence"] == 0.0

    def test_optimality_with_expert(self):
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
                {"action": {"tool_id": "report", "type": "tool_call"}},
            ]
        }
        expert_trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
                {"action": {"tool_id": "report", "type": "tool_call"}},
            ]
        }

        result = run_trajectory_quality(trajectory, expert_trajectory)
        # Perfect match should give high optimality
        assert result["optimality"] > 0.8

    def test_optimality_without_expert(self):
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
                {"action": {"tool_id": "report", "type": "tool_call"}},
            ]
        }

        result = run_trajectory_quality(trajectory)
        # Without expert, should get placeholder score
        assert result["optimality"] == 0.5

    def test_coherence_diverse(self):
        # Diverse but coherent trajectory
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
                {"action": {"tool_id": "report", "type": "tool_call"}},
            ]
        }

        result = run_trajectory_quality(trajectory)
        # 3 unique tools out of 3 steps = diversity ratio 1.0
        # Should get moderate coherence (0.7 per heuristic)
        assert 0.6 <= result["coherence"] <= 0.8

    def test_coherence_repetitive(self):
        # Repetitive trajectory
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "search", "type": "tool_call"}},
            ]
        }

        result = run_trajectory_quality(trajectory)
        # 1 unique tool out of 3 steps = diversity ratio 0.33
        # Should get low coherence (0.3 per heuristic)
        assert result["coherence"] <= 0.4

    def test_determinism_insufficient_runs(self):
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
            ]
        }

        # Less than 5 runs
        multiple_runs = [trajectory] * 3

        result = run_trajectory_quality(trajectory, multiple_runs=multiple_runs)
        # Should get placeholder when insufficient runs
        assert result["determinism"] == 0.5

    def test_determinism_consistent_runs(self):
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
            ]
        }

        # 5 identical runs
        multiple_runs = [trajectory] * 5

        result = run_trajectory_quality(trajectory, multiple_runs=multiple_runs)
        # Identical runs should give high determinism
        assert result["determinism"] > 0.9

    def test_recovery_no_data(self):
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
            ]
        }

        result = run_trajectory_quality(trajectory)
        # Should get placeholder when no recovery data
        assert result["recovery"] == 0.5

    def test_recovery_perfect(self):
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
            ]
        }

        recovery_data = {
            "total_errors": 0,
            "recovered_errors": 0,
        }

        result = run_trajectory_quality(trajectory, recovery_data=recovery_data)
        # No errors means perfect recovery
        assert result["recovery"] == 1.0

    def test_recovery_good(self):
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
            ]
        }

        recovery_data = {
            "total_errors": 10,
            "recovered_errors": 9,  # 90% recovery
        }

        result = run_trajectory_quality(trajectory, recovery_data=recovery_data)
        # 90% recovery should give high score
        assert result["recovery"] == 1.0

    def test_transparency_no_reasoning(self):
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"type": "think"}},  # No tool_id
            ]
        }

        result = run_trajectory_quality(trajectory)
        # No reasoning, but has tool_id for first step
        assert 0.3 <= result["transparency"] <= 0.6

    def test_transparency_with_reasoning(self):
        trajectory = {
            "events": [
                {
                    "action": {
                        "tool_id": "search",
                        "type": "tool_call",
                        "reasoning": "Need to find information",
                        "parameters": {"query": "test"},
                    }
                },
                {
                    "action": {
                        "type": "think",
                        "explanation": "Analyzing results",
                    },
                    "context": "Previous step results",
                },
            ]
        }

        result = run_trajectory_quality(trajectory)
        # With reasoning, explanation, parameters, context
        assert result["transparency"] > 0.7

    def test_thresholds_l2_pass(self):
        # L2 thresholds: trajectory_quality ≥0.55, determinism ≥0.55
        result = check_trajectory_quality_thresholds(
            trajectory_quality=0.6, determinism=0.6, level="L2"
        )
        assert result["level"] == "L2"
        assert result["trajectory_quality"]["passed"] is True
        assert result["determinism"]["passed"] is True
        assert result["overall_pass"] is True

    def test_thresholds_l3_fail(self):
        # L3 thresholds: trajectory_quality ≥0.65, determinism ≥0.65
        result = check_trajectory_quality_thresholds(
            trajectory_quality=0.7,
            determinism=0.6,  # Below 0.65
            level="L3",
        )
        assert result["level"] == "L3"
        assert result["trajectory_quality"]["passed"] is True
        assert result["determinism"]["passed"] is False
        assert result["overall_pass"] is False

    def test_thresholds_l4_strict(self):
        # L4 thresholds: trajectory_quality ≥0.75, determinism ≥0.75
        result = check_trajectory_quality_thresholds(
            trajectory_quality=0.8, determinism=0.8, level="L4"
        )
        assert result["level"] == "L4"
        assert result["trajectory_quality"]["passed"] is True
        assert result["determinism"]["passed"] is True
        assert result["overall_pass"] is True

    def test_overall_trajectory_quality(self):
        trajectory = {
            "events": [
                {
                    "action": {
                        "tool_id": "search",
                        "type": "tool_call",
                        "reasoning": "Need information",
                    }
                },
                {
                    "action": {
                        "tool_id": "analyze",
                        "type": "tool_call",
                        "explanation": "Processing results",
                    }
                },
            ]
        }

        expert_trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
            ]
        }

        result = run_trajectory_quality(trajectory, expert_trajectory)

        # Should have all 5 dimensions
        assert "optimality" in result
        assert "coherence" in result
        assert "determinism" in result
        assert "recovery" in result
        assert "transparency" in result
        assert "trajectory_quality" in result

        # Overall should be weighted average
        weights = {
            "optimality": 0.25,
            "coherence": 0.20,
            "determinism": 0.20,
            "recovery": 0.20,
            "transparency": 0.15,
        }
        expected = (
            result["optimality"] * weights["optimality"]
            + result["coherence"] * weights["coherence"]
            + result["determinism"] * weights["determinism"]
            + result["recovery"] * weights["recovery"]
            + result["transparency"] * weights["transparency"]
        )

        from pytest import approx

        assert result["trajectory_quality"] == approx(expected, abs=0.01)
