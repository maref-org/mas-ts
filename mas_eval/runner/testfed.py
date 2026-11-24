# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Test-feedback loop primitives for agent runs.

A test-feedback run differs from a one-shot run in one way only: the agent sees
the failing test output of its previous attempt and may try again. That makes
three things measurable per rep instead of one — how many rounds were needed,
whether the agent cheated by editing the tests, and what the loop cost.

The functions here are the parts worth testing without an agent, a repo or a
build; ``scripts/swebench_testfed.py`` only orchestrates them.

Two rules are load-bearing:

* **The baseline prompt is never rewritten.** Feedback is appended through
  :func:`build_prompt`, so the frozen template stays byte-identical and a
  feedback run stays comparable to a one-shot run.
* **An unknown cost is never zero.** If any round's usage cannot be priced, the
  whole rep's cost is unknown (``None``), because summing the rounds that happen
  to be measurable would silently understate real spend.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from mas_eval.runner.prompt import build_prompt
from mas_eval.runner.usage import usage_is_trusted

__all__ = [
    "DEFAULT_TEST_PREFIX",
    "build_feedback_prompt",
    "detect_test_tampering",
    "summarize_rounds",
]

# Test directory of the instance family this loop was verified on. Callers
# normally derive the prefix from FAIL_TO_PASS instead of using this default.
# Empty string means "no default" — callers MUST pass an explicit prefix.
# When test_prefix is empty/whitespace, detect_test_tampering returns False
# (cannot judge tampering without a prefix).
DEFAULT_TEST_PREFIX = ""

_FEEDBACK_TEMPLATE = (
    "你上一次的修复没有通过测试，测试输出如下：\n"
    "{output}\n"
    "请继续在当前工作区修复。不要修改测试文件。"
)

_NO_OUTPUT_TEMPLATE = (
    "你上一次的修复没有通过测试，但没有拿到可用的测试输出。"
    "请重新检查当前工作区的改动并继续修复。不要修改测试文件。"
)

# Outcomes that mean "the run was stopped by a cap". They outrank a later "ok"
# in the aggregate: a silently capped round is the notable event of the rep.
_ABORT_OUTCOMES = ("max_turns", "max_budget")


def build_feedback_prompt(
    problem_statement: str, test_output: str, max_chars: int = 2000
) -> str:
    """Return the baseline prompt with failing test output appended.

    ``test_output`` is truncated to its last ``max_chars`` characters — pytest
    puts the actionable assertion at the end, and a full traceback would dwarf
    the issue text. ``max_chars <= 0`` (or empty output) keeps the retry
    instruction but omits the output, so a retry always tells the agent that it
    failed and that the tests are off limits.
    """
    tail = test_output[-max_chars:].strip() if max_chars > 0 and test_output else ""
    if tail:
        feedback = _FEEDBACK_TEMPLATE.format(output=tail)
    else:
        feedback = _NO_OUTPUT_TEMPLATE
    return build_prompt(problem_statement, append=feedback)


def detect_test_tampering(
    changed_files: Sequence[str], test_prefix: str = DEFAULT_TEST_PREFIX
) -> bool:
    """Whether any changed path lives under the test directory.

    ``changed_files`` is ``git diff --name-only`` output: repo-relative paths
    with no ``a/``/``b/`` prefix. Passing tests by editing them is not a fix,
    so a hit invalidates the rep before its tests are even run.

    If ``test_prefix`` is empty or whitespace, tampering detection is skipped
    (returns False). Callers should derive the prefix from FAIL_TO_PASS via
    :func:`derive_test_prefix`; an empty prefix means "cannot judge, so don't
    judge" rather than "no tests exist".
    """
    if not test_prefix or not test_prefix.strip():
        return False

    for raw in changed_files:
        path = raw.strip().lstrip("/")
        if path.startswith("./"):
            path = path[2:]
        if path.startswith(test_prefix):
            return True
    return False


def summarize_rounds(rounds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate a rep's rounds into cost, measurability, outcome and count.

    ``rounds`` are the per-round dicts written to the JSONL row; each may carry
    a ``usage`` record from :func:`~mas_eval.runner.usage.parse_claude_usage`.

    ``cost_measurable`` is True only when *every* round is priceable, and
    ``total_cost_usd`` is then their sum. Otherwise both flip to
    ``None``/``False`` rather than reporting a partial sum as the rep's cost.
    Zero rounds is likewise not "free": it is unmeasurable.

    ``outcome`` prefers an abort cap (``max_turns``/``max_budget``) over a later
    successful round, because that cap is what limits the measurement; with no
    cap it is the last round's outcome.
    """
    total_cost = 0.0
    measurable = bool(rounds)
    outcomes: list[str] = []

    for rnd in rounds:
        usage = rnd.get("usage")
        if not isinstance(usage, dict) or not usage_is_trusted(usage):
            measurable = False
            outcomes.append("unknown")
            continue

        outcome = str(usage.get("outcome") or "unknown")
        outcomes.append(outcome)
        cost = usage.get("total_cost_usd")
        if isinstance(cost, bool) or not isinstance(cost, int | float):
            measurable = False
            continue
        total_cost += float(cost)

    capped = [name for name in outcomes if name in _ABORT_OUTCOMES]
    outcome = capped[0] if capped else (outcomes[-1] if outcomes else "unknown")

    return {
        "total_cost_usd": round(total_cost, 6) if measurable else None,
        "cost_measurable": measurable,
        "outcome": outcome,
        "rounds_used": len(rounds),
    }
