# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for Step Efficiency D2 Gold Standard metric."""

from mas_eval.domains.d2_step_efficiency import (
    check_step_efficiency_thresholds,
    run_step_efficiency,
)


class TestStepEfficiency:
    def test_empty_trajectory(self):
        result = run_step_efficiency(None)
        assert result["step_efficiency"] == 0.0
        assert result["optimality_ratio"] == 0.0

    def test_optimal_trajectory(self):
        # Perfect trajectory: 3 steps, minimal
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
                {"action": {"tool_id": "report", "type": "tool_call"}},
            ]
        }
        # Expert trajectory also has 3 steps
        expert_trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
                {"action": {"tool_id": "report", "type": "tool_call"}},
            ]
        }

        result = run_step_efficiency(trajectory, expert_trajectory)
        assert result["optimality_ratio"] == 1.0  # 3/3
        assert result["redundancy_ratio"] == 1.0  # No unnecessary steps
        assert result["revisit_ratio"] == 0.0  # No tool reuse
        assert result["step_efficiency"] > 0.9  # Should be high

    def test_redundant_trajectory(self):
        # Redundant trajectory: 5 steps, but expert only needs 3
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "search", "type": "tool_call"}},  # Redundant
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
                {"action": {"tool_id": "validate", "type": "tool_call"}},  # Unnecessary
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

        result = run_step_efficiency(trajectory, expert_trajectory)
        from pytest import approx

        assert result["optimality_ratio"] == approx(0.6)  # 3/5
        assert result["redundancy_ratio"] == approx(0.6)  # 2 unnecessary out of 5
        assert result["actual_steps"] == 5
        assert result["expected_min_steps"] == 3
        assert result["unnecessary_steps"] == 2

    def test_revisit_trajectory(self):
        # Trajectory with tool revisit
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
                {"action": {"tool_id": "search", "type": "tool_call"}},  # Revisit
                {"action": {"tool_id": "report", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},  # Revisit
            ]
        }

        result = run_step_efficiency(trajectory)
        assert result["revisit_ratio"] > 0  # Should have revisit
        assert result["unique_tools"] == 3  # search, analyze, report
        assert result["revisited_tools"] == 2  # search and analyze revisited

    def test_severe_inefficiency_warning(self):
        # Trajectory with optimality ratio < 0.4
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
            ]
            * 10  # 10 steps
        }
        expert_trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
            ]  # 1 step
        }

        result = run_step_efficiency(trajectory, expert_trajectory)
        assert result["optimality_ratio"] == 0.1  # 1/10
        assert result["optimality_score"] == 0.0  # Should be 0 due to < 0.4 threshold
        assert "严重低效" in " ".join(result["warnings"])

    def test_potential_loop_warning(self):
        # Trajectory with high revisit ratio
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "search", "type": "tool_call"}},
            ]
        }

        result = run_step_efficiency(trajectory)
        assert result["revisit_ratio"] == 1.0  # Only one tool, used 4 times
        assert "潜在死循环" in " ".join(result["warnings"])

    def test_thresholds_l2_pass(self):
        # L2 thresholds: optimality ≥0.5, revisit ≤0.25
        result = check_step_efficiency_thresholds(
            optimality_ratio=0.6, revisit_ratio=0.2, level="L2"
        )
        assert result["level"] == "L2"
        assert result["optimality"]["passed"] is True
        assert result["revisit"]["passed"] is True
        assert result["overall_pass"] is True

    def test_thresholds_l3_fail(self):
        # L3 thresholds: optimality ≥0.65, revisit ≤0.20
        result = check_step_efficiency_thresholds(
            optimality_ratio=0.6,  # Below 0.65
            revisit_ratio=0.15,
            level="L3",
        )
        assert result["level"] == "L3"
        assert result["optimality"]["passed"] is False
        assert result["overall_pass"] is False

    def test_thresholds_l4_strict(self):
        # L4 thresholds: optimality ≥0.8, revisit ≤0.15
        result = check_step_efficiency_thresholds(
            optimality_ratio=0.85, revisit_ratio=0.1, level="L4"
        )
        assert result["level"] == "L4"
        assert result["optimality"]["passed"] is True
        assert result["revisit"]["passed"] is True
        assert result["overall_pass"] is True

    def test_no_expert_trajectory(self):
        # Test without expert trajectory (should use heuristic)
        trajectory = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
                {"action": {"tool_id": "report", "type": "tool_call"}},
            ]
        }

        result = run_step_efficiency(trajectory)
        # Without expert, expected_min_steps should be heuristic (actual_steps // 2)
        assert result["expected_min_steps"] == 1  # 3 // 2 = 1
        from pytest import approx

        # Function rounds to 3 decimal places, so 1/3 ≈ 0.333
        assert result["optimality_ratio"] == approx(0.333, abs=0.001)
        assert result["unnecessary_steps"] == 0  # Can't identify without expert
