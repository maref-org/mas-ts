# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for D3 Agent-to-Agent Security Interaction (v0.8.1).

Covers OWASP Agentic Top 10 #4/#5/#9 A2A attack surface evaluation:
defense detection, attack surface identification, risk-based scoring,
and D3 integration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.domains.d3_security_interaction import (
    A2A_DEFENSE_PROBES,
    SECURITY_INTERACTION_WEIGHTS,
    detect_a2a_defenses,
    run_d3_security_interaction,
)


class TestA2ADefenseDetection:
    def test_no_defenses_in_bare_card(self):
        assert detect_a2a_defenses({"name": "x"}) == set()

    def test_detects_response_sanitizer(self):
        card = {"safety": {"response_sanitizer": True}}
        assert "response_sanitizer" in detect_a2a_defenses(card)

    def test_detects_delegation_audit(self):
        card = {"governance": {"delegation_audit": "enabled"}}
        assert "delegation_audit" in detect_a2a_defenses(card)

    def test_detects_protocol_hardening(self):
        card = {"safety": {"message_signing": True}}
        assert "protocol_hardening" in detect_a2a_defenses(card)

    def test_detects_tool_scope_isolation(self):
        card = {"guardrails": {"tool_scope": "strict"}}
        assert "tool_scope_isolation" in detect_a2a_defenses(card)

    def test_all_probes_have_fields(self):
        for defense, probes in A2A_DEFENSE_PROBES.items():
            assert len(probes) > 0

    def test_weights_sum_to_one(self):
        assert abs(sum(SECURITY_INTERACTION_WEIGHTS.values()) - 1.0) < 1e-9


class TestAttackSurface:
    def test_single_agent_no_surface(self):
        result = run_d3_security_interaction({"name": "solo"})
        assert result["summary"]["has_a2a_surface"] is False
        assert result["score"] == 70.0  # neutral

    def test_a2a_endpoint_detected(self):
        card = {"endpoints": {"a2a": "https://a2a.test"}}
        result = run_d3_security_interaction(card)
        assert "a2a" in result["summary"]["a2a_surface"]

    def test_mcp_endpoint_detected(self):
        card = {"endpoints": {"mcp": "https://mcp.test"}}
        result = run_d3_security_interaction(card)
        assert "mcp" in result["summary"]["a2a_surface"]

    def test_federation_role_detected(self):
        card = {"federation": {"role": "secondary"}}
        result = run_d3_security_interaction(card)
        assert "federation" in result["summary"]["a2a_surface"]


class TestScoring:
    def test_empty_card_returns_zero_with_critical(self):
        result = run_d3_security_interaction({})
        assert result["score"] == 0.0
        assert result["findings"][0]["severity"] == "CRITICAL"
        assert result["domain"] == "D3"

    def test_single_agent_neutral_score(self):
        result = run_d3_security_interaction({"name": "solo"})
        assert result["score"] == 70.0
        # All four dimensions should be neutral
        for v in result["subscores"].values():
            assert v == 70.0

    def test_a2a_without_defense_triggers_critical(self):
        card = {"endpoints": {"a2a": "https://a2a.test", "mcp": "https://mcp.test"}}
        result = run_d3_security_interaction(card)
        assert result["score"] < 70.0
        cats = {f["category"] for f in result["findings"]}
        assert "cross_agent_injection_undefended" in cats

    def test_federation_with_weak_auth_triggers_critical(self):
        card = {
            "federation": {"role": "secondary"},
            "authentication": {"type": "None"},
        }
        result = run_d3_security_interaction(card)
        cats = {f["category"] for f in result["findings"]}
        assert "delegation_spoof_undefended" in cats

    def test_strong_auth_with_delegation_audit_raises_score(self):
        defended = run_d3_security_interaction({
            "federation": {"role": "secondary"},
            "authentication": {"type": "OAuth2"},
            "governance": {"delegation_audit": True},
        })
        undefended = run_d3_security_interaction({
            "federation": {"role": "secondary"},
            "authentication": {"type": "None"},
        })
        assert defended["score"] > undefended["score"]

    def test_response_sanitizer_raises_score(self):
        defended = run_d3_security_interaction({
            "endpoints": {"a2a": "https://a2a.test"},
            "safety": {"response_sanitizer": True},
        })
        undefended = run_d3_security_interaction({
            "endpoints": {"a2a": "https://a2a.test"},
        })
        assert defended["score"] > undefended["score"]

    def test_all_subscores_in_range(self):
        card = {
            "endpoints": {"a2a": "https://a2a.test", "mcp": "https://mcp.test"},
            "federation": {"role": "primary"},
            "authentication": {"type": "OAuth2"},
            "capabilities": [{"skill_id": f"cap_{i}"} for i in range(5)],
        }
        result = run_d3_security_interaction(card)
        for name, val in result["subscores"].items():
            assert 0 <= val <= 100, f"{name}={val} out of range"

    def test_findings_have_layer_and_root_cause(self):
        result = run_d3_security_interaction({
            "endpoints": {"a2a": "https://a2a.test"},
        })
        for f in result["findings"]:
            assert "layer" in f
            assert "root_cause" in f

    def test_summary_fields_present(self):
        result = run_d3_security_interaction({"name": "x"})
        s = result["summary"]
        assert "a2a_surface" in s
        assert "has_a2a_surface" in s
        assert "declared_a2a_defenses" in s


class TestD3Integration:
    def test_run_d3_includes_security_interaction(self):
        card = {
            "name": "fed-agent",
            "endpoints": {"a2a": "https://a2a.test", "mcp": "https://mcp.test"},
            "capabilities": [{"skill_id": "agent_tool"}, {"skill_id": "mcp_tool"}],
            "authentication": {"type": "OAuth2"},
            "orchestration_hints": {"preferred_role": "worker", "parallel_safe": True},
        }
        result = run_d3(card)
        assert "security_interaction" in result["subscores"]
        assert "security_interaction_detail" in result["subscores"]
        assert isinstance(result["subscores"]["security_interaction_detail"], dict)
        assert 0 <= result["subscores"]["security_interaction"] <= 100

    def test_run_d3_findings_include_a2a_security(self):
        card = {
            "endpoints": {"a2a": "https://a2a.test"},
            "capabilities": [{"skill_id": "agent_tool"}],
        }
        result = run_d3(card)
        a2a_cats = {f["category"] for f in result["findings"]} & {
            "cross_agent_injection_undefended",
            "protocol_hardening_missing",
        }
        assert len(a2a_cats) > 0
