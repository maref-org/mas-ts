# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Offline tests for the test-feedback loop primitives.

No agent, no repo, no build: only the logic that decides what the agent sees,
whether a rep was tampered with, and how a rep's cost is reported.
"""

from __future__ import annotations

from mas_eval.runner.testfed import (
    build_feedback_prompt,
    detect_test_tampering,
    summarize_rounds,
)

PROBLEM = "ascii.qdp Table format assumes QDP commands are upper case"


def _usage(cost: float | None, measurable: bool = True, outcome: str = "ok") -> dict:
    """A usage record shaped like parse_claude_usage's output."""
    return {
        "total_cost_usd": cost if measurable else None,
        "cost_measurable": measurable,
        "outcome": outcome,
        "duration_api_ms": 1000 if measurable else 0,
        "output_tokens": 100 if measurable else 0,
    }


class TestBuildFeedbackPrompt:
    def test_keeps_baseline_prompt_and_appends_feedback(self):
        prompt = build_feedback_prompt(PROBLEM, "FAILED test_qdp.py::test_roundtrip")

        # The frozen baseline is still there verbatim, followed by the output.
        assert PROBLEM in prompt
        assert "Do not modify tests." in prompt
        assert "FAILED test_qdp.py::test_roundtrip" in prompt
        assert "不要修改测试文件" in prompt
        assert prompt.index(PROBLEM) < prompt.index("FAILED test_qdp.py")

    def test_truncates_to_the_tail(self):
        output = "HEAD-" + ("x" * 100) + "-TAIL-MARKER"

        prompt = build_feedback_prompt(PROBLEM, output, max_chars=20)

        assert "-TAIL-MARKER" in prompt
        assert "HEAD-" not in prompt

    def test_truncation_boundary_is_exact(self):
        prompt = build_feedback_prompt(PROBLEM, "0123456789", max_chars=4)

        assert "6789" in prompt
        assert "56789" not in prompt

    def test_empty_output_still_asks_for_a_retry(self):
        prompt = build_feedback_prompt(PROBLEM, "", max_chars=2000)

        assert PROBLEM in prompt
        assert "没有拿到可用的测试输出" in prompt
        assert "不要修改测试文件" in prompt

    def test_zero_char_budget_omits_output_without_losing_instruction(self):
        prompt = build_feedback_prompt(PROBLEM, "CRASH-DETAIL", max_chars=0)

        assert "CRASH-DETAIL" not in prompt
        assert "不要修改测试文件" in prompt


class TestDetectTestTampering:
    def test_detects_edit_under_test_prefix(self):
        changed = ["astropy/io/ascii/qdp.py", "astropy/io/ascii/tests/test_qdp.py"]

        assert detect_test_tampering(changed, test_prefix="astropy/io/ascii/tests/") is True

    def test_non_test_edits_are_clean(self):
        changed = ["astropy/io/ascii/qdp.py", "astropy/io/ascii/core.py"]

        assert detect_test_tampering(changed) is False

    def test_empty_change_list_is_clean(self):
        assert detect_test_tampering([]) is False

    def test_custom_prefix_and_whitespace(self):
        changed = ["  tests/test_demo.py  "]

        assert detect_test_tampering(changed, test_prefix="tests/") is True
        assert detect_test_tampering(changed) is False

    def test_similarly_named_directory_is_not_a_hit(self):
        # A prefix match must be a directory boundary, not a string prefix.
        assert detect_test_tampering(["astropy/io/ascii/tests_extra/x.py"]) is False

    def test_empty_prefix_returns_false_no_judgement(self):
        """Empty/whitespace prefix means 'cannot judge' -> returns False."""
        changed = ["tests/test_something.py", "src/main.py"]
        assert detect_test_tampering(changed, test_prefix="") is False
        assert detect_test_tampering(changed, test_prefix="   ") is False
        # With explicit prefix it still works
        assert detect_test_tampering(changed, test_prefix="tests/") is True


class TestSummarizeRounds:
    def test_sums_measurable_round_costs(self):
        rounds = [
            {"round": 1, "usage": _usage(0.5)},
            {"round": 2, "usage": _usage(0.25)},
        ]

        summary = summarize_rounds(rounds)

        assert summary["cost_measurable"] is True
        assert summary["total_cost_usd"] == 0.75
        assert summary["rounds_used"] == 2
        assert summary["outcome"] == "ok"

    def test_unmeasurable_round_makes_whole_rep_none(self):
        rounds = [
            {"round": 1, "usage": _usage(0.5)},
            {"round": 2, "usage": _usage(0.0, measurable=False)},
        ]

        summary = summarize_rounds(rounds)

        assert summary["cost_measurable"] is False
        assert summary["total_cost_usd"] is None  # unknown, not 0.5

    def test_missing_usage_is_unmeasurable(self):
        summary = summarize_rounds([{"round": 1, "usage": None}])

        assert summary["cost_measurable"] is False
        assert summary["total_cost_usd"] is None

    def test_measured_cost_but_null_value_is_unmeasurable(self):
        # Defensive: a record claiming measurability without a price is not a 0.
        summary = summarize_rounds([{"round": 1, "usage": _usage(None)}])

        assert summary["cost_measurable"] is False
        assert summary["total_cost_usd"] is None

    def test_no_rounds_is_not_free(self):
        summary = summarize_rounds([])

        assert summary["cost_measurable"] is False
        assert summary["total_cost_usd"] is None
        assert summary["rounds_used"] == 0
        assert summary["outcome"] == "unknown"

    def test_abort_cap_outranks_a_later_ok_round(self):
        rounds = [
            {"round": 1, "usage": _usage(0.4, outcome="max_budget")},
            {"round": 2, "usage": _usage(0.1)},
        ]

        assert summarize_rounds(rounds)["outcome"] == "max_budget"

    def test_last_round_outcome_wins_without_a_cap(self):
        rounds = [
            {"round": 1, "usage": _usage(0.1, outcome="api_error")},
            {"round": 2, "usage": _usage(0.1)},
        ]

        assert summarize_rounds(rounds)["outcome"] == "ok"
