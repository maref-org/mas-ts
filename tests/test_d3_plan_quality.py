# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for Plan Quality D3 Gold Standard metric."""

from mas_eval.domains.d3_plan_quality import (
    check_plan_quality_thresholds,
    run_plan_quality,
)


class TestPlanQuality:
    def test_empty_plan(self):
        result = run_plan_quality(None)
        assert result["plan_quality"] == 0.0
        assert result["completeness"] == 0.0
        assert result["adherence"] == 0.0

    def test_perfect_plan_execution(self):
        # Plan and execution match perfectly
        plan = {
            "steps": [
                {"tool_id": "search", "action": "find"},
                {"tool_id": "analyze", "action": "process"},
                {"tool_id": "report", "action": "output"},
            ]
        }
        execution = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
                {"action": {"tool_id": "report", "type": "tool_call"}},
            ]
        }

        result = run_plan_quality(plan, execution)
        # Perfect match should give high scores
        assert result["completeness"] == 1.0
        assert result["adherence"] > 0.8
        assert result["plan_quality"] > 0.7

    def test_incomplete_plan(self):
        # Plan missing some steps needed by execution
        plan = {
            "steps": [
                {"tool_id": "search", "action": "find"},
                {"tool_id": "report", "action": "output"},
            ]
        }
        execution = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {
                    "action": {"tool_id": "analyze", "type": "tool_call"}
                },  # Missing from plan
                {"action": {"tool_id": "report", "type": "tool_call"}},
            ]
        }

        result = run_plan_quality(plan, execution)
        # Completeness should be partial (2/3 tools covered)
        assert result["completeness"] < 1.0
        assert result["completeness"] >= 0.6

    def test_plan_with_extra_steps(self):
        # Execution deviates from plan
        plan = {
            "steps": [
                {"tool_id": "search", "action": "find"},
                {"tool_id": "analyze", "action": "process"},
            ]
        }
        execution = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "validate", "type": "tool_call"}},  # Not in plan
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
            ]
        }

        result = run_plan_quality(plan, execution)
        # Adherence should be affected by deviation
        assert result["adherence"] < 1.0

    def test_plan_stability_consistent(self):
        # Multiple identical plans
        plan = {
            "steps": [
                {"tool_id": "search", "action": "find"},
                {"tool_id": "analyze", "action": "process"},
            ]
        }
        multiple_plans = [
            {"steps": [{"tool_id": "search"}, {"tool_id": "analyze"}]},
            {"steps": [{"tool_id": "search"}, {"tool_id": "analyze"}]},
            {"steps": [{"tool_id": "search"}, {"tool_id": "analyze"}]},
        ]

        result = run_plan_quality(plan, multiple_plans=multiple_plans)
        # Identical plans should have perfect stability
        assert result["stability"] == 1.0

    def test_plan_stability_variable(self):
        # Plans with some variation
        plan = {
            "steps": [
                {"tool_id": "search", "action": "find"},
                {"tool_id": "analyze", "action": "process"},
            ]
        }
        multiple_plans = [
            {"steps": [{"tool_id": "search"}, {"tool_id": "analyze"}]},
            {"steps": [{"tool_id": "search"}, {"tool_id": "validate"}]},  # Different
            {"steps": [{"tool_id": "search"}, {"tool_id": "analyze"}]},
        ]

        result = run_plan_quality(plan, multiple_plans=multiple_plans)
        # Variable plans should have lower stability
        assert result["stability"] < 1.0
        assert result["stability"] > 0.3

    def test_no_execution_data(self):
        # Plan but no execution
        plan = {
            "steps": [
                {"tool_id": "search", "action": "find"},
                {"tool_id": "analyze", "action": "process"},
            ]
        }

        result = run_plan_quality(plan)
        # Without execution, completeness and adherence get placeholders
        assert result["completeness"] == 0.5
        assert result["adherence"] == 0.5
        # Stability also gets placeholder (no multiple plans)
        assert result["stability"] == 0.5

    def test_thresholds_l2_pass(self):
        # L2 thresholds: adherence ≥0.65, stability ≥0.65
        result = check_plan_quality_thresholds(adherence=0.7, stability=0.7, level="L2")
        assert result["level"] == "L2"
        assert result["adherence"]["passed"] is True
        assert result["stability"]["passed"] is True
        assert result["overall_pass"] is True

    def test_thresholds_l3_fail(self):
        # L3 thresholds: adherence ≥0.75, stability ≥0.75
        result = check_plan_quality_thresholds(
            adherence=0.7,  # Below 0.75
            stability=0.8,
            level="L3",
        )
        assert result["level"] == "L3"
        assert result["adherence"]["passed"] is False
        assert result["overall_pass"] is False

    def test_thresholds_l4_strict(self):
        # L4 thresholds: adherence ≥0.82, stability ≥0.82
        result = check_plan_quality_thresholds(
            adherence=0.85, stability=0.85, level="L4"
        )
        assert result["level"] == "L4"
        assert result["adherence"]["passed"] is True
        assert result["stability"]["passed"] is True
        assert result["overall_pass"] is True

    def test_plan_step_counts(self):
        plan = {
            "steps": [
                {"tool_id": "search", "action": "find"},
                {"tool_id": "analyze", "action": "process"},
                {"tool_id": "report", "action": "output"},
            ]
        }
        execution = {
            "events": [
                {"action": {"tool_id": "search", "type": "tool_call"}},
                {"action": {"tool_id": "analyze", "type": "tool_call"}},
            ]
        }

        result = run_plan_quality(plan, execution)
        assert result["plan_steps"] == 3
        assert result["execution_steps"] == 2
