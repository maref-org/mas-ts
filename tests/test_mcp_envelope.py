# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 MCP core envelope & governance validation."""

from mas_eval.mcp import (
    check_mcp_compliance,
    validate_mcp_envelope,
)


def _valid_message() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "api_version": "2024-10-01",
    }


def test_valid_same_boundary_envelope():
    result = validate_mcp_envelope(_valid_message(), cross_boundary=False)
    assert result["valid"] is True
    assert result["missing"] == []


def test_missing_jsonrpc_field():
    msg = _valid_message()
    del msg["jsonrpc"]
    result = validate_mcp_envelope(msg)
    assert result["valid"] is False
    assert "jsonrpc" in result["missing"]


def test_missing_api_version_article_15():
    msg = _valid_message()
    del msg["api_version"]
    result = validate_mcp_envelope(msg)
    assert result["valid"] is False
    assert "api_version" in result["missing"]
    assert any(f["category"] == "mcp_api_version_missing" for f in result["findings"])


def test_cross_boundary_requires_trace_fields_article_15a():
    msg = _valid_message()
    result = validate_mcp_envelope(msg, cross_boundary=True)
    assert result["valid"] is False
    for field in ("trace_id", "timestamp", "source_agent"):
        assert field in result["missing"]


def test_cross_boundary_requires_fail_mode_article_7():
    msg = _valid_message()
    msg.update({"trace_id": "t1", "timestamp": "2026-01-01T00:00:00Z", "source_agent": "a"})
    result = validate_mcp_envelope(msg, cross_boundary=True)
    assert result["valid"] is False
    assert "FAIL_MODE" in result["missing"]
    assert any(f["severity"] == "CRITICAL" for f in result["findings"])


def test_valid_cross_boundary_envelope():
    msg = _valid_message()
    msg.update(
        {
            "trace_id": "t1",
            "timestamp": "2026-01-01T00:00:00Z",
            "source_agent": "agent_a",
            "FAIL_MODE": "degraded",
        }
    )
    result = validate_mcp_envelope(msg, cross_boundary=True)
    assert result["valid"] is True


def test_invalid_fail_mode_value():
    msg = _valid_message()
    msg.update(
        {
            "trace_id": "t1",
            "timestamp": "2026-01-01T00:00:00Z",
            "source_agent": "agent_a",
            "FAIL_MODE": "explode",
        }
    )
    result = validate_mcp_envelope(msg, cross_boundary=True)
    assert any(f["category"] == "mcp_fail_mode_invalid" for f in result["findings"])


def test_non_dict_message():
    result = validate_mcp_envelope("not-a-dict")
    assert result["valid"] is False


def test_check_mcp_compliance_disabled():
    result = check_mcp_compliance({"endpoints": {}})
    assert result["component"] == "mcp_compliance"
    assert result["score"] >= 0.0


def test_check_mcp_compliance_enabled_ok():
    card = {"federation_protocols": {"mcp": {"enabled": True, "version": "2024-10-01"}}}
    result = check_mcp_compliance(card)
    assert result["subscores"]["mcp_declared"] == 1.0


def test_check_mcp_compliance_enabled_missing_version():
    card = {"federation_protocols": {"mcp": {"enabled": True}}}
    result = check_mcp_compliance(card)
    assert result["subscores"]["mcp_declared"] == 0.0
    assert any(f["category"] == "mcp_version_missing" for f in result["findings"])
