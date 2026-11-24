# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Solver prompt construction and prompt fingerprinting for agent runs.

The baseline template is frozen: it is the text every historical SWE-bench
result was produced with, so editing it silently breaks comparability. New
instructions go through ``build_prompt(..., append=...)`` instead.
"""

from __future__ import annotations

import hashlib

__all__ = ["SOLVE_PROMPT_TEMPLATE", "build_prompt", "prompt_sha256"]

# Frozen baseline. Do not edit: historical runs used exactly this text.
SOLVE_PROMPT_TEMPLATE = (
    "You are solving a GitHub issue in the current repository.\n"
    "Issue:\n{problem_statement}\n\n"
    "Edit the repository to fix the issue. Do not modify tests. "
    "Keep the change minimal. Do not commit."
)


def build_prompt(problem_statement: str, append: str = "") -> str:
    """Return the solver prompt, optionally followed by an extra instruction.

    With an empty (or whitespace-only) ``append`` the result is byte-identical
    to the historical inline prompt. A non-empty ``append`` is appended after a
    blank line and terminated with a newline so it cannot glue onto whatever
    the agent prints next.
    """
    prompt = SOLVE_PROMPT_TEMPLATE.format(problem_statement=problem_statement)
    extra = append.strip()
    if not extra:
        return prompt
    return f"{prompt}\n\n{extra}\n"


def prompt_sha256(prompt: str) -> str:
    """Return the lowercase hex SHA-256 fingerprint of ``prompt``."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
