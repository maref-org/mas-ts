# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for the solver prompt builder and its fingerprint."""

from __future__ import annotations

from mas_eval.runner.prompt import SOLVE_PROMPT_TEMPLATE, build_prompt, prompt_sha256

# The literal prompt the batch script built inline before this module existed.
# Frozen evidence: build_prompt must reproduce it byte-for-byte so historical
# SWE-bench results stay comparable.
LEGACY_INLINE_PROMPT = (
    "You are solving a GitHub issue in the current repository.\n"
    "Issue:\nX\n\n"
    "Edit the repository to fix the issue. Do not modify tests. "
    "Keep the change minimal. Do not commit."
)


def test_build_prompt_matches_legacy_inline_prompt() -> None:
    assert build_prompt("X") == LEGACY_INLINE_PROMPT


def test_empty_append_is_a_noop() -> None:
    assert build_prompt("X", append="") == build_prompt("X")


def test_whitespace_only_append_is_a_noop() -> None:
    assert build_prompt("X", append="  \n ") == build_prompt("X")


def test_append_is_added_after_blank_line_and_newline_terminated() -> None:
    base = build_prompt("X")
    assert build_prompt("X", append="Do Y.") == base + "\n\nDo Y.\n"
    # The baseline body must stay untouched in the middle.
    assert build_prompt("X", append="Do Y.").startswith(base)
    assert build_prompt("X", append="Do Y.").startswith(LEGACY_INLINE_PROMPT)


def test_append_is_stripped() -> None:
    assert build_prompt("X", append="\n  Do Y.  \n") == build_prompt("X") + "\n\nDo Y.\n"


def test_prompt_sha256_is_stable_hex_and_input_sensitive() -> None:
    first = prompt_sha256(build_prompt("X"))
    second = prompt_sha256(build_prompt("X"))
    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")
    assert first == first.lower()

    assert prompt_sha256(build_prompt("X")) != prompt_sha256(build_prompt("Y"))
    assert prompt_sha256(build_prompt("X")) != prompt_sha256(
        build_prompt("X", append="Do Y.")
    )


def test_baseline_template_guardrails() -> None:
    assert "Do not modify tests" in SOLVE_PROMPT_TEMPLATE
    assert "{problem_statement}" in SOLVE_PROMPT_TEMPLATE
    assert SOLVE_PROMPT_TEMPLATE.count("{problem_statement}") == 1
    # Nothing but the documented placeholder may be substituted.
    assert SOLVE_PROMPT_TEMPLATE.format(problem_statement="X") == build_prompt("X")
