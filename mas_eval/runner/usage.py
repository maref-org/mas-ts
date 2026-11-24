# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Cost and token accounting for local CLI agents.

``claude -p --output-format json`` reports its own cost, but the number it
reports is not always meaningful. When the API is unreachable the CLI still
exits with ``subtype: "success"`` while emitting ``is_error: true``,
``duration_api_ms: 0``, an all-zero ``usage`` block, ``total_cost_usd: 0`` and a
``result`` string starting with ``API Error: ...``.

A reported ``total_cost_usd`` of ``0`` therefore must never be read as "free".

Two questions must be kept apart, because they have different answers for the
same run:

1. **Is the cost measurable?** — did the run actually consume model work we can
   price? That is only about evidence of usage::

       duration_api_ms > 0 and usage.output_tokens > 0

2. **What was the outcome?** — did the run succeed, hit a cap, or fail? This is
   what ``is_error`` / ``subtype`` describe.

``is_error`` must **not** be used as a measurability criterion. A run truncated
by ``--max-turns`` reports ``subtype: "error_max_turns"`` with ``is_error: true``
and yet really burned tokens (observed: ``duration_api_ms=98779``,
``output_tokens=13471``, reported cost ``1.031376``). Treating such a run as
"no cost" would understate real spend — the exact failure this module exists to
prevent. So ``cost_measurable`` ignores ``is_error``; ``outcome`` carries it.

When the cost is not measurable it is unknown (``None``), not zero, and the
caller is told why through ``untrusted_reason``.
"""

from __future__ import annotations

import json
import os
from typing import Any

__all__ = ["parse_claude_usage", "usage_is_trusted"]

_RESULT_HEAD_CHARS = 120

_TOKENS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def _as_int(value: Any) -> int:
    """Coerce a JSON scalar to int, defaulting to 0."""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except (TypeError, ValueError):
            return 0
    return 0


def _as_float(value: Any) -> float | None:
    """Coerce a JSON scalar to float, or None when absent/unusable."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (TypeError, ValueError):
            return None
    return None


def _load_payload(log: str) -> dict[str, Any] | None:
    """Find the CLI's JSON payload in ``log``.

    Tries the whole string first, then each line backwards (the CLI normally
    prints one single-line JSON object last), and gives up with None.
    """
    stripped = log.strip()
    if stripped:
        try:
            payload = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            payload = None
        if isinstance(payload, dict):
            return payload

    for line in reversed(log.splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _models(payload: dict[str, Any]) -> list[str]:
    """Model names actually used, falling back to the requested model."""
    model_usage = payload.get("modelUsage")
    if isinstance(model_usage, dict):
        names = [str(key) for key in model_usage]
        if names:
            return names
    fallback = os.environ.get("ANTHROPIC_MODEL", "").strip()
    return [fallback] if fallback else []


def _untrusted_reason(duration_api_ms: int, output_tokens: int) -> str:
    """Why the cost cannot be measured ("" when it can)."""
    if duration_api_ms <= 0:
        return "no_api_time"
    if output_tokens <= 0:
        return "no_output_tokens"
    return ""


def _subtype(payload: dict[str, Any]) -> str:
    """The raw CLI ``subtype`` string ("" when absent)."""
    raw = payload.get("subtype")
    return "" if raw is None else str(raw)


def _outcome(is_error: bool, subtype: str, cost_measurable: bool) -> str:
    """Classify the run's result state (orthogonal to cost measurability).

    Priority: success first, then the two caps the CLI names in ``subtype``,
    then an error that left no usage evidence at all (an API failure), then
    any other error.
    """
    if not is_error:
        return "ok"
    if "max_turns" in subtype:
        return "max_turns"
    if "max_budget" in subtype:
        return "max_budget"
    if not cost_measurable:
        return "api_error"
    return "error"


def parse_claude_usage(log: str) -> dict[str, Any] | None:
    """Parse a ``claude -p --output-format json`` log into a usage record.

    Returns None when no JSON payload can be found. The returned dict always
    has the same keys.

    ``total_cost_usd`` is fail-closed on *measurability* only: it is a float
    when ``duration_api_ms > 0`` and ``output_tokens > 0``, and None otherwise
    (an unmeasurable run has an *unknown* cost, not a free one). ``is_error``
    deliberately does not take part — a capped run still spent tokens. The
    value the CLI reported is always preserved in ``total_cost_usd_reported``
    for diagnosis, and ``outcome`` records what actually happened.
    """
    payload = _load_payload(log)
    if payload is None:
        return None

    raw_usage = payload.get("usage")
    usage = raw_usage if isinstance(raw_usage, dict) else {}

    is_error = bool(payload.get("is_error") or False)
    subtype = _subtype(payload)
    duration_api_ms = _as_int(payload.get("duration_api_ms"))
    output_tokens = _as_int(usage.get("output_tokens"))
    reason = _untrusted_reason(duration_api_ms, output_tokens)
    cost_measurable = reason == ""

    result = payload.get("result")
    result_text = "" if result is None else str(result)

    reported_cost = _as_float(payload.get("total_cost_usd"))

    parsed: dict[str, Any] = {
        "model": _models(payload),
        # Fail-closed: an unmeasurable run has an unknown cost, never 0.
        "total_cost_usd": reported_cost if cost_measurable else None,
        "total_cost_usd_reported": reported_cost,
        "is_error": is_error,
        "subtype": subtype,
        "outcome": _outcome(is_error, subtype, cost_measurable),
        "cost_measurable": cost_measurable,
        "result_head": result_text[:_RESULT_HEAD_CHARS],
        "duration_api_ms": duration_api_ms,
        "duration_ms": _as_int(payload.get("duration_ms")),
        "num_turns": _as_int(payload.get("num_turns")),
        # Kept for old callers; it now means "cost measurable", not "ok".
        "trusted": cost_measurable,
        "untrusted_reason": reason,
    }
    for name in _TOKENS:
        parsed[name] = _as_int(usage.get(name))
    return parsed


def usage_is_trusted(usage: dict[str, Any] | None) -> bool:
    """Whether a usage record may be used as cost evidence.

    Reads ``cost_measurable`` when present. Hand-written dicts predating that
    key fall back to the same token-based derivation, so an ``is_error`` flag
    is never mistaken for "no cost".
    """
    if not usage:
        return False
    if "cost_measurable" in usage:
        return bool(usage["cost_measurable"])
    if "trusted" in usage:
        return bool(usage["trusted"])
    return (
        _as_int(usage.get("duration_api_ms")) > 0
        and _as_int(usage.get("output_tokens")) > 0
    )

