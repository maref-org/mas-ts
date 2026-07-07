# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for D4: Security (MAS-TS-001 v3.0)

Covers: Penetration Testing, Red-Blue Exercise, Trust Chain, SAST Scanning
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d4_governance_security import (
    ACTION_SAFETY_WEIGHTS,
    AUTH_TYPE_SCORES,
    HITL_WEIGHTS,
    SECURITY_WEIGHTS,
    _score_penetration_testing,
    _score_red_blue,
    _score_sast_scanning,
    _score_trust_chain,
    run_action_safety,
    run_d4,
    run_d4_security,
    run_hitl_gate,
)

SECURE_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:secure:sec-01",
    "name": "Secure Agent",
    "version": "2.0.0",
    "model_backend": {
        "provider": "anthropic",
        "model": "claude-sonnet-4",
        "deployment": "cloud",
        "endpoint": "https://api.anthropic.com/v1/messages",
    },
    "compliance": {
        "data_residency": "US",
        "data_classification": "confidential",
        "cross_border": True,
        "model_backend_location": "US",
        "audit_trail_required": True,
    },
    "constitution": {
        "envelope": {
            "message_id": "m1",
            "correlation_id": "c1",
            "timestamp": "2026-01-01T00:00:00Z",
            "sender": "urn:agent:test:secure:sec-01",
        },
        "health_state": "HEALTHY",
        "heartbeat_interval_seconds": 15,
        "message_format": {
            "supported_transports": ["http", "grpc"],
            "max_payload_bytes": 1048576,
        },
    },
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "shell",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_edit",
            "description": "edit",
            "input_schema": {},
            "output_schema": {},
            "examples": ["e"],
        },
        {
            "skill_id": "file_write",
            "description": "write",
            "input_schema": {},
            "output_schema": {},
            "examples": ["w"],
        },
        {
            "skill_id": "web_fetch",
            "description": "fetch",
            "input_schema": {},
            "output_schema": {},
            "examples": ["f"],
        },
        {
            "skill_id": "agent_tool",
            "description": "agent",
            "input_schema": {},
            "output_schema": {},
            "examples": ["a"],
        },
    ],
    "endpoints": {
        "a2a": "https://agent.example.com/a2a",
        "mcp": "https://agent.example.com/mcp",
    },
    "authentication": {
        "type": "OAuth2",
        "scopes": ["agent:spawn", "agent:communicate", "code:read"],
    },
    "dependencies": ["anthropic-api", "git", "nodejs", "typescript"],
    "orchestration_hints": {
        "preferred_role": "supervisor",
        "parallel_safe": True,
        "stateful": True,
    },
}

WEAK_CARD = {
    "card_version": "1.1",
    "agent_id": "urn:agent:test:weak:weak-01",
    "name": "Weak Agent",
    "version": "0.1.0",
    "model_backend": {
        "provider": "test",
        "model": "test",
        "deployment": "local",
        "endpoint": "http://localhost:8080",
    },
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "shell",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
        }
    ],
    "authentication": {"type": "None"},
    "orchestration_hints": {},
}


class TestPenetrationTesting:
    def test_secure_card_high_score(self):
        score, findings = _score_penetration_testing(SECURE_CARD)
        assert score >= 60

    def test_weak_card_low_score(self):
        score, findings = _score_penetration_testing(WEAK_CARD)
        assert score < 40

    def test_auth_type_scoring(self):
        assert (
            AUTH_TYPE_SCORES["mTLS"]
            > AUTH_TYPE_SCORES["OAuth2"]
            > AUTH_TYPE_SCORES["APIKey"]
            > AUTH_TYPE_SCORES["None"]
        )

    def test_no_auth_is_critical(self):
        score, findings = _score_penetration_testing(WEAK_CARD)
        assert any(f["severity"] == "CRITICAL" for f in findings)

    def test_scopes_declared(self):
        score, findings = _score_penetration_testing(SECURE_CARD)
        assert any("scopes" in f["category"] for f in findings)

    def test_risky_tools_detected(self):
        score, findings = _score_penetration_testing(SECURE_CARD)
        assert any("risky_tools" in f["category"] for f in findings)

    def test_injection_protection(self):
        score, findings = _score_penetration_testing(SECURE_CARD)
        assert any("injection" in f["category"] for f in findings)


class TestRedBlue:
    def test_secure_card_high_score(self):
        score, findings = _score_red_blue(SECURE_CARD)
        assert score >= 50

    def test_weak_card_low_score(self):
        score, findings = _score_red_blue(WEAK_CARD)
        assert score < 40

    def test_audit_trail_required(self):
        score, findings = _score_red_blue(SECURE_CARD)
        assert any("rb_audit" in f["category"] for f in findings)

    def test_no_audit_is_high(self):
        score, findings = _score_red_blue(WEAK_CARD)
        assert any(f["severity"] == "HIGH" for f in findings)

    def test_defense_depth_counted(self):
        score, findings = _score_red_blue(SECURE_CARD)
        assert any("defense" in f["category"] for f in findings)

    def test_attack_surface_tracked(self):
        score, findings = _score_red_blue(SECURE_CARD)
        assert any("attack_surface" in f["category"] for f in findings)


class TestTrustChain:
    def test_secure_card_high_score(self):
        score, findings = _score_trust_chain(SECURE_CARD)
        assert score >= 50

    def test_weak_card_low_score(self):
        score, findings = _score_trust_chain(WEAK_CARD)
        assert score < 20

    def test_no_auth_critical(self):
        score, findings = _score_trust_chain(WEAK_CARD)
        assert any(f["severity"] == "CRITICAL" for f in findings)

    def test_mtls_highest_score(self):
        card = {
            "authentication": {"type": "mTLS", "scopes": ["test"]},
            "endpoints": {"a2a": "url"},
            "constitution": {
                "health_state": "HEALTHY",
                "heartbeat_interval_seconds": 10,
            },
        }
        score, findings = _score_trust_chain(card)
        assert score >= 70

    def test_heartbeat_freshness(self):
        score, findings = _score_trust_chain(SECURE_CARD)
        assert any("heartbeat" in f["category"] for f in findings)

    def test_scopes_boost(self):
        card = {
            "authentication": {"type": "OAuth2", "scopes": ["read", "write"]},
            "endpoints": {},
            "constitution": {},
        }
        score, findings = _score_trust_chain(card)
        assert score > 30


class TestSAST:
    def test_secure_card_high_score(self):
        score, findings = _score_sast_scanning(SECURE_CARD)
        assert score >= 50

    def test_weak_card_low_score(self):
        score, findings = _score_sast_scanning(WEAK_CARD)
        assert score < 30

    def test_no_auth_is_high(self):
        score, findings = _score_sast_scanning(WEAK_CARD)
        assert any(f["severity"] == "HIGH" for f in findings)

    def test_dependencies_scanned(self):
        score, findings = _score_sast_scanning(SECURE_CARD)
        assert any("sast_deps" in f["category"] for f in findings)

    def test_versioning_tracked(self):
        score, findings = _score_sast_scanning(SECURE_CARD)
        assert any("versioning" in f["category"] for f in findings)

    def test_business_rules_boost_score(self):
        many_rules = {
            "capabilities": [
                {"skill_id": f"t{i}", "business_rule_version": "2026-05-01"}
                for i in range(10)
            ],
            "authentication": {"type": "APIKey"},
            "compliance": {"audit_trail_required": True, "data_residency": "US"},
            "constitution": {
                "envelope": {"message_id": "1", "timestamp": "2026-01-01"}
            },
        }
        score, findings = _score_sast_scanning(many_rules)
        assert score >= 40


class TestD4SecurityIntegration:
    def test_security_scoring(self):
        result = run_d4_security(SECURE_CARD)
        assert result["domain"] == "D4"
        assert result["component"] == "security"
        assert 0 <= result["score"] <= 100

    def test_security_subscore_keys(self):
        result = run_d4_security(SECURE_CARD)
        expected = {
            "penetration_testing",
            "red_blue_exercise",
            "trust_chain",
            "sast_scanning",
        }
        assert set(result["subscores"].keys()) == expected

    def test_subscore_ranges(self):
        result = run_d4_security(SECURE_CARD)
        for subname, subscore in result["subscores"].items():
            assert 0 <= subscore <= 100, f"{subname} score {subscore} out of range"

    def test_weights_sum_to_one(self):
        total = sum(SECURITY_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_secure_higher_than_weak(self):
        secure = run_d4_security(SECURE_CARD)
        weak = run_d4_security(WEAK_CARD)
        assert secure["score"] > weak["score"]


class TestD4Full:
    def test_d4_full_integration(self):
        result = run_d4(SECURE_CARD)
        assert result["domain"] == "D4"
        assert 0 <= result["score"] <= 100
        assert "governance" in result
        assert "security" in result

    def test_d4_full_subscore_structure(self):
        result = run_d4(SECURE_CARD)
        assert "governance_detail" in result["subscores"]
        assert "security_detail" in result["subscores"]

    def test_d4_secure_higher_than_weak(self):
        secure = run_d4(SECURE_CARD)
        weak = run_d4(WEAK_CARD)
        assert secure["score"] > weak["score"]

    def test_d4_findings_present(self):
        result = run_d4(SECURE_CARD)
        assert result["summary"]["total_findings"] > 0

    def test_d4_score_composition(self):
        result = run_d4(SECURE_CARD)
        expected = (
            result["governance"]["score"] * 0.35
            + result["security"]["score"] * 0.11
            + result["subscores"].get("action_safety", 0) * 0.07
            + result["subscores"].get("data_leakage", 0) * 0.07
            + result["subscores"].get("hitl_gate", 0) * 0.05
            + result["subscores"].get("trust", 0) * 0.15
            + result["subscores"].get("vendor_diversity", 0) * 0.05
            + result["subscores"].get("mcp_supply_chain", 0) * 0.10
            + result["subscores"].get("gossip_trust", 0) * 0.05
        )
        assert abs(result["score"] - expected) < 0.1


# ═══════════════════════════════════════════════════════════════
# Gold Standard: Action Safety (v3.0-GA §4.5)
# ═══════════════════════════════════════════════════════════════


class TestHitlGate:
    """HITL gate tests (R3 P0 — Handbook §5.1.3)"""

    def test_hitl_enabled_required_high_score(self):
        """Fully configured HITL gate with required mode should score high."""
        card = {
            "compliance": {"audit_trail_required": True},
            "capabilities": [{"skill_id": "read_file"}],
            "hitl": {
                "enabled": True,
                "destructive_action_gate": "required",
                "timeout_seconds": 300,
                "escalation_policy": "block",
            },
        }
        score, findings = run_hitl_gate(card)
        assert score >= 80
        assert not any(f["severity"] == "CRITICAL" for f in findings)
        assert not any(f["severity"] == "HIGH" for f in findings)

    def test_hitl_disabled_warning(self):
        """Disabled HITL gate should produce a WARNING."""
        card = {
            "capabilities": [{"skill_id": "read_file"}],
            "hitl": {"enabled": False},
        }
        score, findings = run_hitl_gate(card)
        assert any(
            f["severity"] == "WARNING" and "disabled" in f["category"] for f in findings
        )

    def test_hitl_destructive_unguarded_critical(self):
        """Destructive actions without HITL should produce CRITICAL."""
        card = {
            "compliance": {"audit_trail_required": True},
            "capabilities": [{"skill_id": "delete"}],
            "hitl": {"enabled": False, "destructive_action_gate": "disabled"},
        }
        score, findings = run_hitl_gate(card)
        assert any(
            f["severity"] == "CRITICAL" and "unguarded" in f["category"]
            for f in findings
        )

    def test_hitl_audit_missing_high(self):
        """Destructive actions without audit_trail_required should produce HIGH."""
        card = {
            "compliance": {"audit_trail_required": False},
            "capabilities": [{"skill_id": "delete"}],
            "hitl": {
                "enabled": True,
                "destructive_action_gate": "required",
                "timeout_seconds": 300,
                "escalation_policy": "block",
            },
        }
        score, findings = run_hitl_gate(card)
        assert any(
            f["severity"] == "HIGH" and "audit_missing" in f["category"]
            for f in findings
        )

    def test_hitl_timeout_invalid_high(self):
        """HITL enabled but timeout < 30 should produce HIGH."""
        card = {
            "capabilities": [{"skill_id": "read_file"}],
            "hitl": {
                "enabled": True,
                "destructive_action_gate": "required",
                "timeout_seconds": 15,
                "escalation_policy": "block",
            },
        }
        score, findings = run_hitl_gate(card)
        assert any(
            f["severity"] == "HIGH" and "timeout_invalid" in f["category"]
            for f in findings
        )

    def test_hitl_weights_sum_to_1(self):
        """HITL_WEIGHTS must sum to 1.0."""
        total = sum(HITL_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_hitl_no_config_moderate(self):
        """Card without hitl field should produce moderate score and WARNING."""
        card = {
            "capabilities": [{"skill_id": "read_file"}],
        }
        score, findings = run_hitl_gate(card)
        assert 20 <= score <= 60
        assert any(
            f["severity"] == "WARNING" and "disabled" in f["category"] for f in findings
        )

    def test_hitl_gate_mode_optional_partial(self):
        """enabled=true with optional gate mode should get partial credit.

        With a destructive action present, 'optional' mode (vs 'required')
        yields audit_linkage=0.5 instead of 1.0, producing a partial score.
        """
        card = {
            "compliance": {"audit_trail_required": True},
            "capabilities": [{"skill_id": "read_file"}, {"skill_id": "delete"}],
            "hitl": {
                "enabled": True,
                "destructive_action_gate": "optional",
                "timeout_seconds": 300,
                "escalation_policy": "block",
            },
        }
        score, findings = run_hitl_gate(card)
        assert 60 <= score <= 90

    def test_hitl_destructive_with_audit_full(self):
        """Destructive + audit + enabled + required should score high."""
        card = {
            "compliance": {"audit_trail_required": True},
            "capabilities": [{"skill_id": "delete_file"}],
            "hitl": {
                "enabled": True,
                "destructive_action_gate": "required",
                "timeout_seconds": 600,
                "escalation_policy": "block",
            },
        }
        score, findings = run_hitl_gate(card)
        assert score >= 80
        assert not any(f["severity"] == "CRITICAL" for f in findings)

    def test_hitl_finding_category(self):
        """HITL finding should have hitl_gate category."""
        card = {"capabilities": [{"skill_id": "read_file"}]}
        score, findings = run_hitl_gate(card)
        assert any(f["category"] == "hitl_gate" for f in findings)

    def test_hitl_pre_config_without_enabled(self):
        """gate_mode set but not enabled should get partial pre-config credit."""
        card = {
            "capabilities": [{"skill_id": "read_file"}],
            "hitl": {
                "enabled": False,
                "destructive_action_gate": "required",
                "timeout_seconds": 300,
                "escalation_policy": "block",
            },
        }
        score, findings = run_hitl_gate(card)
        assert score > 0
        assert any(
            f["severity"] == "WARNING" and "disabled" in f["category"] for f in findings
        )

    def test_hitl_integrated_in_run_d4(self):
        """run_d4 should include hitl_gate in subscores."""
        card = {
            "card_version": "2.0",
            "agent_id": "urn:agent:test:hitl:hitl-01",
            "name": "HITL Test Agent",
            "version": "1.0.0",
            "compliance": {
                "data_residency": "LOCAL",
                "data_classification": "internal",
                "cross_border": False,
                "model_backend_location": "LOCAL",
                "audit_trail_required": True,
            },
            "constitution": {
                "envelope": {
                    "message_id": "msg-1",
                    "correlation_id": "corr-1",
                    "timestamp": "2026-07-03T00:00:00Z",
                    "sender": "agent:test",
                },
                "health_state": "HEALTHY",
                "heartbeat_interval_seconds": 30,
            },
            "model_backend": {
                "provider": "openai",
                "model": "gpt-4",
                "deployment": "cloud",
                "endpoint": "https://api.openai.com",
            },
            "capabilities": [
                {
                    "skill_id": "read_file",
                    "description": "read",
                    "input_schema": {},
                    "output_schema": {},
                    "examples": ["ex"],
                }
            ],
            "authentication": {"type": "APIKey"},
            "hitl": {
                "enabled": True,
                "destructive_action_gate": "required",
                "timeout_seconds": 300,
                "escalation_policy": "block",
            },
        }
        result = run_d4(card)
        assert "hitl_gate" in result["subscores"]
        assert result["subscores"]["hitl_gate"] >= 0


class TestActionSafetyGold:
    """Gold Standard action safety tests (v3.0-GA §4.5)"""

    def test_safe_card_high_score(self):
        card = {
            "authentication": {"type": "OAuth2", "scopes": ["read", "write"]},
            "capabilities": [{"skill_id": "read_file"}],
        }
        score, findings = run_action_safety(card)
        assert score >= 70

    def test_destructive_action_critical(self):
        card = {
            "authentication": {"type": "OAuth2", "scopes": ["read"]},
            "capabilities": [{"skill_id": "delete"}],
        }
        score, findings = run_action_safety(card)
        assert any(
            f["severity"] == "CRITICAL" and "destructive" in f["category"]
            for f in findings
        )

    def test_wildcard_scope_high(self):
        card = {
            "authentication": {"type": "OAuth2", "scopes": ["admin:*"]},
            "capabilities": [{"skill_id": "read"}],
        }
        score, findings = run_action_safety(card)
        assert any(
            f["severity"] == "HIGH" and "wildcard" in f["category"] for f in findings
        )

    def test_dangerous_tools_warning(self):
        card = {
            "authentication": {"type": "OAuth2", "scopes": ["read"]},
            "capabilities": [{"skill_id": "shell_exec"}],
        }
        score, findings = run_action_safety(card)
        assert any(
            f["severity"] == "WARNING" and "dangerous_tools" in f["category"]
            for f in findings
        )

    def test_action_log_audit_gap(self):
        card = {
            "authentication": {"type": "OAuth2", "scopes": ["read"]},
            "capabilities": [{"skill_id": "delete"}],
            "audit": {"enabled": True},
        }
        action_log = [
            {"action": "delete", "logged": False},
        ]
        score, findings = run_action_safety(card, action_log=action_log)
        assert any(
            f["severity"] == "HIGH" and "audit_gap" in f["category"] for f in findings
        )

    def test_action_log_all_logged(self):
        card = {
            "authentication": {"type": "OAuth2", "scopes": ["read", "write"]},
            "capabilities": [{"skill_id": "delete"}],
        }
        action_log = [
            {"action": "delete", "logged": True},
        ]
        score, findings = run_action_safety(card, action_log=action_log)
        assert not any("audit_gap" in f["category"] for f in findings)

    def test_weights_sum_to_1(self):
        total = sum(ACTION_SAFETY_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_no_auth_defaults_moderate(self):
        card = {}
        score, findings = run_action_safety(card)
        assert 50 <= score <= 70

    def test_action_safety_finding_category(self):
        card = {
            "authentication": {"type": "OAuth2", "scopes": ["read"]},
            "capabilities": [{"skill_id": "read_file"}],
        }
        score, findings = run_action_safety(card)
        assert any(f["category"] == "action_safety" for f in findings)
        assert 0 <= score <= 100
