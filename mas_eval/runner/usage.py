# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Cost and token accounting for local CLI agents.

``claude -p --output-format json`` reports its own cost, but the number it
reports is not always meaningful. When the API is unreachable the CLI still
exits with ``subtype: "success"`` while emitting ``is_error: true``,
``duration_api_ms: 0``, an all-zero ``usage`` block, ``total_cost_usd: 0`` and a
``result`` string starting with ``API Error: ...``.

A reported ``total_cost_usd`` of ``0`` therefore must never be read as "free".
A usage record is only trusted when **all three** hold::

    is_error is False and duration_api_ms > 0 and usage.output_tokens > 0

Otherwise the cost is unknown (``None``), not zero, and the caller is told why
through ``untrusted_reason``.
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


def _untrusted_reason(is_error: bool, duration_api_ms: int, output_tokens: int) -> str:
    if is_error:
        return "api_error"
    if duration_api_ms <= 0:
        return "no_api_time"
    if output_tokens <= 0:
        return "no_output_tokens"
    return ""


def parse_claude_usage(log: str) -> dict[str, Any] | None:
    """Parse a ``claude -p --output-format json`` log into a usage record.

    Returns None when no JSON payload can be found. The returned dict always
    has the same keys.

    ``total_cost_usd`` is fail-closed: it is a float only when the record is
    trusted, and None otherwise (an unverifiable run has an *unknown* cost, not
    a free one). The value the CLI reported is always preserved in
    ``total_cost_usd_reported`` for diagnosis.
    """
    payload = _load_payload(log)
    if payload is None:
        return None

    raw_usage = payload.get("usage")
    usage = raw_usage if isinstance(raw_usage, dict) else {}

    is_error = bool(payload.get("is_error") or False)
    duration_api_ms = _as_int(payload.get("duration_api_ms"))
    output_tokens = _as_int(usage.get("output_tokens"))
    reason = _untrusted_reason(is_error, duration_api_ms, output_tokens)

    result = payload.get("result")
    result_text = "" if result is None else str(result)

    trusted = reason == ""
    reported_cost = _as_float(payload.get("total_cost_usd"))

    parsed: dict[str, Any] = {
        "model": _models(payload),
        # Fail-closed: an untrusted run has an unknown cost, never 0.
        "total_cost_usd": reported_cost if trusted else None,
        "total_cost_usd_reported": reported_cost,
        "is_error": is_error,
        "result_head": result_text[:_RESULT_HEAD_CHARS],
        "duration_api_ms": duration_api_ms,
        "duration_ms": _as_int(payload.get("duration_ms")),
        "num_turns": _as_int(payload.get("num_turns")),
        "trusted": trusted,
        "untrusted_reason": reason,
    }
    for name in _TOKENS:
        parsed[name] = _as_int(usage.get(name))
    return parsed


def usage_is_trusted(usage: dict[str, Any] | None) -> bool:
    """Whether a usage record may be used as cost evidence."""
    if not usage:
        return False
    if "trusted" in usage:
        return bool(usage["trusted"])
    return (
        not bool(usage.get("is_error", False))
        and _as_int(usage.get("duration_api_ms")) > 0
        and _as_int(usage.get("output_tokens")) > 0
    )
