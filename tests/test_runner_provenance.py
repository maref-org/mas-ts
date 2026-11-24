# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Runner provenance tests (fully offline, no model calls).

The regression these guard against: two batches whose budget cap and timeout
differed, compared as if they were the same experiment because neither gate was
written into the result rows.
"""

from __future__ import annotations

import pytest

from mas_eval.runner.provenance import parse_max_budget_usd, runner_metadata


def test_space_separated_budget_is_parsed() -> None:
    assert parse_max_budget_usd("claude -p --max-budget-usd 1.00 json") == 1.0


def test_equals_separated_budget_is_parsed() -> None:
    assert parse_max_budget_usd("claude -p --max-budget-usd=1.5 json") == 1.5


def test_missing_flag_is_none() -> None:
    assert parse_max_budget_usd("claude -p --output-format json") is None


def test_non_numeric_value_is_none_without_raising() -> None:
    # A malformed value must degrade to "unknown", never blow up a batch run.
    assert parse_max_budget_usd("claude -p --max-budget-usd abc") is None


def test_trailing_flag_without_value_is_none() -> None:
    assert parse_max_budget_usd("claude -p --max-budget-usd") is None


def test_runner_metadata_key_set_is_exact() -> None:
    meta = runner_metadata("claude -p --max-budget-usd 1.00", 600, "default")
    assert set(meta) == {
        "agent_cmd",
        "timeout_s",
        "max_budget_usd",
        "prompt_label",
    }


def test_runner_metadata_passes_label_through() -> None:
    meta = runner_metadata("claude -p", 900, "append:budget-hint")
    assert meta["prompt_label"] == "append:budget-hint"


@pytest.mark.parametrize(
    ("cmd", "expected"),
    [
        ("claude -p --max-budget-usd 0.25", 0.25),
        ("claude --max-budget-usd=2", 2.0),
    ],
)
def test_budget_is_float(cmd: str, expected: float) -> None:
    assert parse_max_budget_usd(cmd) == expected
