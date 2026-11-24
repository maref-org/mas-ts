# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Usage/cost parsing tests (fully offline, no model calls)."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from mas_eval.runner.local_cli import LocalCLIRunner
from mas_eval.runner.usage import parse_claude_usage, usage_is_trusted


def _payload(**overrides: Any) -> dict[str, Any]:
    """A healthy successful CLI payload, with optional field overrides."""
    payload: dict[str, Any] = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_ms": 4210,
        "duration_api_ms": 3800,
        "num_turns": 3,
        "result": "Fixed the bug in calc.py",
        "total_cost_usd": 0.0421,
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 350,
            "cache_read_input_tokens": 800,
            "cache_creation_input_tokens": 40,
        },
        "modelUsage": {"claude-sonnet-4-5": {"inputTokens": 1200}},
    }
    payload.update(overrides)
    return payload


def _dead_api_payload() -> dict[str, Any]:
    """What the CLI prints when the API is unreachable: success + zeros."""
    return _payload(
        is_error=True,
        duration_api_ms=0,
        duration_ms=12,
        num_turns=1,
        result="API Error: Connection error.",
        total_cost_usd=0,
        usage={
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        modelUsage={},
    )


def _max_turns_payload(after_tokens: int = 13471) -> dict[str, Any]:
    """A run cut off by ``--max-turns``: error state, but real spend."""
    return _payload(
        subtype="error_max_turns",
        is_error=True,
        duration_api_ms=98779,
        num_turns=40,
        result="Reached max turns before finishing",
        total_cost_usd=1.031376,
        usage={
            "input_tokens": 21000,
            "output_tokens": after_tokens,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    )


def test_successful_run_is_trusted_with_real_cost():
    usage = parse_claude_usage(json.dumps(_payload()))

    assert usage is not None
    assert usage["trusted"] is True
    assert usage["cost_measurable"] is True
    assert usage["outcome"] == "ok"
    assert usage["subtype"] == "success"
    assert usage["untrusted_reason"] == ""
    assert usage["total_cost_usd"] == 0.0421
    assert usage["total_cost_usd_reported"] == 0.0421
    assert usage["is_error"] is False
    assert usage["duration_api_ms"] == 3800
    assert usage["duration_ms"] == 4210
    assert usage["num_turns"] == 3
    assert usage["input_tokens"] == 1200
    assert usage["output_tokens"] == 350
    assert usage["cache_read_input_tokens"] == 800
    assert usage["cache_creation_input_tokens"] == 40
    assert usage["model"] == ["claude-sonnet-4-5"]
    assert usage["result_head"] == "Fixed the bug in calc.py"
    assert usage_is_trusted(usage) is True


def test_unmeasurable_run_keeps_reported_cost_but_zeroes_trusted_cost():
    """No API time and no output tokens: cost unknown, reported value kept."""
    usage = parse_claude_usage(json.dumps(_dead_api_payload()))

    assert usage is not None
    assert usage["trusted"] is False
    assert usage["cost_measurable"] is False
    assert usage["untrusted_reason"] == "no_api_time"
    assert usage["outcome"] == "api_error"
    assert usage["total_cost_usd"] is None
    assert usage["total_cost_usd_reported"] == 0
    assert usage["result_head"].startswith("API Error:")
    assert usage_is_trusted(usage) is False


def test_max_turns_truncation_is_measurable_not_ok():
    """--max-turns burns tokens: cost must be counted, outcome is "max_turns"."""
    usage = parse_claude_usage(json.dumps(_max_turns_payload()))

    assert usage is not None
    assert usage["is_error"] is True
    assert usage["subtype"] == "error_max_turns"
    assert usage["cost_measurable"] is True
    assert usage["trusted"] is True
    assert usage["untrusted_reason"] == ""
    assert usage["total_cost_usd"] == 1.031376
    assert usage["total_cost_usd_reported"] == 1.031376
    assert usage["output_tokens"] == 13471
    assert usage["outcome"] == "max_turns"
    assert usage_is_trusted(usage) is True


def test_max_budget_stop_is_measurable_with_max_budget_outcome():
    usage = parse_claude_usage(
        json.dumps(_max_turns_payload().copy() | {"subtype": "error_max_budget_usd"})
    )

    assert usage is not None
    assert usage["subtype"] == "error_max_budget_usd"
    assert usage["cost_measurable"] is True
    assert usage["total_cost_usd"] == 1.031376
    assert usage["outcome"] == "max_budget"


def test_error_without_usage_evidence_is_api_error():
    usage = parse_claude_usage(
        json.dumps(
            _payload(
                is_error=True,
                subtype="error_during_execution",
                duration_api_ms=0,
                total_cost_usd=0,
                usage={
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            )
        )
    )

    assert usage is not None
    assert usage["cost_measurable"] is False
    assert usage["outcome"] == "api_error"
    assert usage["total_cost_usd"] is None
    assert usage["total_cost_usd_reported"] == 0
    assert usage["untrusted_reason"] == "no_api_time"


def test_plain_error_with_usage_is_error_but_cost_is_counted():
    usage = parse_claude_usage(
        json.dumps(_payload(is_error=True, subtype="error_during_execution"))
    )

    assert usage is not None
    assert usage["outcome"] == "error"
    assert usage["cost_measurable"] is True
    assert usage["total_cost_usd"] == 0.0421
    assert usage["untrusted_reason"] == ""


def test_zero_api_time_is_not_trusted():
    usage = parse_claude_usage(json.dumps(_payload(duration_api_ms=0)))

    assert usage is not None
    assert usage["trusted"] is False
    assert usage["cost_measurable"] is False
    assert usage["untrusted_reason"] == "no_api_time"
    assert usage["outcome"] == "ok"
    assert usage["total_cost_usd"] is None
    assert usage["total_cost_usd_reported"] == 0.0421


def test_zero_output_tokens_is_not_trusted():
    payload = _payload(
        usage={
            "input_tokens": 10,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        total_cost_usd=0,
    )
    usage = parse_claude_usage(json.dumps(payload))

    assert usage is not None
    assert usage["trusted"] is False
    assert usage["cost_measurable"] is False
    assert usage["untrusted_reason"] == "no_output_tokens"
    assert usage["total_cost_usd"] is None
    assert usage["total_cost_usd_reported"] == 0


def test_missing_subtype_defaults_to_empty_string():
    payload = _payload()
    payload.pop("subtype")

    usage = parse_claude_usage(json.dumps(payload))

    assert usage is not None
    assert usage["subtype"] == ""
    assert usage["outcome"] == "ok"


def test_result_head_is_truncated_to_120_chars():
    usage = parse_claude_usage(json.dumps(_payload(result="x" * 500)))

    assert usage is not None
    assert len(usage["result_head"]) == 120


def test_model_list_empty_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-env-model")

    usage = parse_claude_usage(json.dumps(_payload(modelUsage={})))

    assert usage is not None
    assert usage["model"] == ["claude-env-model"]


def test_model_list_empty_and_no_env_is_empty_list(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    usage = parse_claude_usage(json.dumps(_payload(modelUsage={})))

    assert usage is not None
    assert usage["model"] == []


def test_prose_plus_single_line_json_still_parses():
    log = "\n".join(
        [
            "Reading repository ...",
            "Applying edit to calc.py",
            "Some [warning] that breaks naive brace matching {",
            json.dumps(_payload()),
        ]
    )

    usage = parse_claude_usage(log)

    assert usage is not None
    assert usage["trusted"] is True
    assert usage["total_cost_usd"] == 0.0421


def test_non_json_log_returns_none():
    assert parse_claude_usage("just a plain text log\nnothing to see") is None
    assert parse_claude_usage("") is None


def test_json_without_usage_block_defaults_to_zero_tokens():
    payload = _payload()
    payload.pop("usage")
    payload.pop("modelUsage")

    usage = parse_claude_usage(json.dumps(payload))

    assert usage is not None
    assert usage["input_tokens"] == 0
    assert usage["output_tokens"] == 0
    assert usage["model"] == [] or usage["model"] == [os.environ.get("ANTHROPIC_MODEL")]
    assert usage["untrusted_reason"] == "no_output_tokens"
    assert usage["total_cost_usd"] is None
    assert usage["total_cost_usd_reported"] == 0.0421


def test_missing_cost_is_none_not_zero():
    payload = _payload()
    payload.pop("total_cost_usd")

    usage = parse_claude_usage(json.dumps(payload))

    assert usage is not None
    assert usage["total_cost_usd"] is None
    assert usage["total_cost_usd_reported"] is None


def test_unusable_scalars_are_coerced_safely():
    payload = _payload(
        total_cost_usd="0.5",
        duration_api_ms="1200",
        duration_ms=4.0,
        num_turns=None,
        usage={
            "input_tokens": "42",
            "output_tokens": 7.9,
            "cache_read_input_tokens": "n/a",
            "cache_creation_input_tokens": True,
        },
    )

    usage = parse_claude_usage(json.dumps(payload))

    assert usage is not None
    assert usage["total_cost_usd"] == 0.5
    assert usage["duration_api_ms"] == 1200
    assert usage["duration_ms"] == 4
    assert usage["num_turns"] == 0
    assert usage["input_tokens"] == 42
    assert usage["output_tokens"] == 7
    assert usage["cache_read_input_tokens"] == 0
    assert usage["cache_creation_input_tokens"] == 0
    assert usage["trusted"] is True


def test_unusable_cost_falls_back_to_none():
    usage = parse_claude_usage(json.dumps(_payload(total_cost_usd="not-a-number")))

    assert usage is not None
    assert usage["total_cost_usd"] is None


def test_non_dict_json_payload_returns_none():
    assert parse_claude_usage('[{"is_error": false}]') is None
    assert parse_claude_usage('"a string"') is None


def test_usage_is_trusted_none_is_false():
    assert usage_is_trusted(None) is False
    assert usage_is_trusted({}) is False


def test_usage_is_trusted_prefers_cost_measurable():
    measurable = {
        "cost_measurable": True,
        "is_error": True,
        "duration_api_ms": 100,
        "output_tokens": 5,
    }
    assert usage_is_trusted(measurable) is True
    assert usage_is_trusted({**measurable, "cost_measurable": False}) is False


def test_usage_is_trusted_recomputes_for_bare_records():
    bare_ok = {"is_error": False, "duration_api_ms": 10, "output_tokens": 3}
    assert usage_is_trusted(bare_ok) is True
    assert usage_is_trusted({**bare_ok, "duration_api_ms": 0}) is False
    assert usage_is_trusted({**bare_ok, "trusted": False}) is False


def test_usage_is_trusted_legacy_dict_ignores_is_error():
    """A pre-``cost_measurable`` dict with spend is measurable, error or not."""
    legacy = {"is_error": True, "duration_api_ms": 100, "output_tokens": 5}

    assert usage_is_trusted(legacy) is True
    assert usage_is_trusted({**legacy, "duration_api_ms": 0}) is False
    assert usage_is_trusted({**legacy, "output_tokens": 0}) is False


def test_usage_is_trusted_explicit_trusted_false_overrides_tokens():
    """Explicit trusted: False means not trusted even with positive tokens."""
    assert usage_is_trusted({"trusted": False, "duration_api_ms": 5, "output_tokens": 3}) is False


def test_usage_is_trusted_explicit_trusted_true_requires_tokens():
    """trusted: True (or missing) falls back to token derivation."""
    assert usage_is_trusted({"trusted": True, "duration_api_ms": 5, "output_tokens": 3}) is True
    assert usage_is_trusted({"trusted": True, "duration_api_ms": 0, "output_tokens": 0}) is False


def test_usage_is_trusted_missing_trusted_derives_from_tokens():
    """Missing trusted key derives from tokens (same as before)."""
    assert usage_is_trusted({"duration_api_ms": 5, "output_tokens": 3}) is True
    assert usage_is_trusted({"duration_api_ms": 0, "output_tokens": 3}) is False
    assert usage_is_trusted({"duration_api_ms": 5, "output_tokens": 0}) is False


def test_unserialisable_cost_field_falls_back_to_none():
    usage = parse_claude_usage(json.dumps(_payload(total_cost_usd=[1])))

    assert usage is not None
    assert usage["total_cost_usd"] is None


def test_runner_attaches_parsed_usage(tmp_path):
    script = f"import json; print(json.dumps({_payload()!r}))"
    runner = LocalCLIRunner(
        "fake-agent",
        [sys.executable, "-c", script],
        usage_parser=parse_claude_usage,
    )

    result = runner.run("fix", tmp_path, "task-1")

    assert result.usage is not None
    assert result.usage["trusted"] is True
    assert result.usage["outcome"] == "ok"
    assert result.usage["total_cost_usd"] == 0.0421


def test_runner_without_parser_has_no_usage(tmp_path):
    runner = LocalCLIRunner("fake-agent", [sys.executable, "-c", "print('{}')"])

    result = runner.run("fix", tmp_path, "task-1")

    assert result.usage is None


def test_runner_injects_env_into_child_process(tmp_path):
    script = "import os; print('FOO=' + os.environ.get('FOO', 'MISSING'))"
    runner = LocalCLIRunner(
        "fake-agent", [sys.executable, "-c", script], env={"FOO": "bar"}
    )

    result = runner.run("fix", tmp_path, "task-1")

    assert "FOO=bar" in result.log
