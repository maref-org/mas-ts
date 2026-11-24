# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Record which runner configuration produced each result row.

Why this exists: an experiment once compared two batches that had silently
drifted apart. Early runs used ``--max-budget-usd 1.00`` with ``timeout 600``;
later arms used ``1.50`` with ``900``. The same instances went from 0/7 to 2/5
resolved, and no field in the result JSONL recorded either gate — so the batches
looked comparable when they were not, and the difference was briefly credited to
another variable. Provenance is cheap; a silent drift invalidates every
cross-batch comparison.

``max_budget_usd`` is parsed out of the agent command so the cap is visible even
when it hides inside a long argv list. ``None`` means "no budget flag in the
command", which is different from "budget of zero".
"""

from __future__ import annotations

import re

__all__ = ["parse_max_budget_usd", "runner_metadata"]

# ``--max-budget-usd 1.00`` and ``--max-budget-usd=1.00`` must both match; the
# value stops at the first whitespace so a trailing argument is not swallowed.
_BUDGET_RE = re.compile(r"--max-budget-usd(?:=|\s+)(\S+)")


def parse_max_budget_usd(agent_cmd: str) -> float | None:
    """Return the ``--max-budget-usd`` value in ``agent_cmd``, or ``None``.

    ``None`` covers three cases that must not be confused with a real number:
    the flag is absent, the flag is present but valueless (end of command), and
    the value is not parseable as a float.
    """
    match = _BUDGET_RE.search(agent_cmd)
    if match is None:
        return None
    raw = match.group(1).rstrip(",;")
    try:
        return float(raw)
    except ValueError:
        return None


def runner_metadata(agent_cmd: str, timeout_s: int, label: str) -> dict[str, object]:
    """Describe the runner configuration behind a result row.

    Returned keys are fixed so downstream consumers can rely on them.
    """
    return {
        "agent_cmd": agent_cmd,
        "timeout_s": timeout_s,
        "max_budget_usd": parse_max_budget_usd(agent_cmd),
        "prompt_label": label,
    }
