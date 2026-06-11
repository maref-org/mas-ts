"""Tests for D3 Federation Evaluation (MAS-TS-001 v4.0)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d3_multi_agent import (
    _is_federation_card,
    check_federation_compatibility,
    check_permission_propagation,
    check_role_conflicts,
    run_d3,
)

BASE_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:test:test-01",
    "name": "Test Agent",
    "version": "1.0.0",
    "compliance": {
        "data_residency": "US",
        "data_classification": "public",
        "cross_border": False,
        "model_backend_location": "US",
        "audit_trail_required": False,
    },
    "constitution": {
        "envelope": {
            "message_id": "m1",
            "correlation_id": "c1",
            "timestamp": "2026-06-11T00:00:00Z",
            "sender": "urn:agent:test:test:test-01",
        },
        "health_state": "HEALTHY",
        "heartbeat_interval_seconds": 30,
    },
    "model_backend": {
        "provider": "test",
        "model": "test",
        "deployment": "cloud",
        "endpoint": "https://test.com/v1",
    },
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "run",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
        },
        {
            "skill_id": "agent_tool",
            "description": "spawn",
            "input_schema": {},
            "output_schema": {},
            "examples": ["spawn"],
        },
        {
            "skill_id": "mcp_tool",
            "description": "mcp",
            "input_schema": {},
            "output_schema": {},
            "examples": ["mcp"],
        },
        {
            "skill_id": "memory",
            "description": "mem",
            "input_schema": {},
            "output_schema": {},
            "examples": ["mem"],
        },
        {
            "skill_id": "worktree",
            "description": "wt",
            "input_schema": {},
            "output_schema": {},
            "examples": ["wt"],
        },
        {
            "skill_id": "todo_write",
            "description": "todo",
            "input_schema": {},
            "output_schema": {},
            "examples": ["todo"],
        },
        {
            "skill_id": "task_management",
            "description": "task",
            "input_schema": {},
            "output_schema": {},
            "examples": ["task"],
        },
    ],
    "authentication": {"type": "None"},
    "endpoints": {"a2a": "https://a2a.test", "mcp": "https://mcp.test"},
    "orchestration_hints": {
        "preferred_role": "supervisor",
        "parallel_safe": True,
        "stateful": True,
    },
}


class TestFederationCardDetection:
    def test_non_federation_card(self):
        assert _is_federation_card(BASE_CARD) is False

    def test_federation_card(self):
        card = dict(BASE_CARD)
        card["federation"] = {}
        assert _is_federation_card(card) is True

    def test_federation_card_with_data(self):
        card = dict(BASE_CARD)
        card["federation"] = {"role": "primary", "trust_score": 0.8}
        assert _is_federation_card(card) is True


class TestCheckFederationCompatibility:
    def test_no_protocols(self):
        card = dict(BASE_CARD)
        card["federation"] = {}
        score, findings = check_federation_compatibility(card)
        assert any(
            "Not assessed" in f["detail"] or "not assessed" in f["detail"]
            for f in findings
        )
        assert score == 0

    def test_valid_mcp(self):
        card = dict(BASE_CARD)
        card["federation"] = {
            "federation_protocols": {
                "mcp": {"version": "2025-03-26", "enabled": True},
            },
        }
        score, findings = check_federation_compatibility(card)
        assert any("compatible" in f["detail"] for f in findings)
        assert score >= 5

    def test_outdated_mcp(self):
        card = dict(BASE_CARD)
        card["federation"] = {
            "federation_protocols": {
                "mcp": {"version": "2024-09-01", "enabled": True},
            },
        }
        score, findings = check_federation_compatibility(card)
        assert any("outdated" in f["detail"] for f in findings)
        assert score == 0

    def test_valid_a2a(self):
        card = dict(BASE_CARD)
        card["federation"] = {
            "federation_protocols": {
                "a2a": {"version": "1.0", "enabled": True},
            },
        }
        score, findings = check_federation_compatibility(card)
        assert any("compatible" in f["detail"] for f in findings)
        assert score >= 5

    def test_both_protocols(self):
        card = dict(BASE_CARD)
        card["federation"] = {
            "federation_protocols": {
                "a2a": {"version": "1.0", "enabled": True},
                "mcp": {"version": "2025-03-26", "enabled": True},
            },
        }
        score, findings = check_federation_compatibility(card)
        compat = [f for f in findings if "compatible" in f["detail"]]
        assert len(compat) >= 2

    def test_disabled_protocol(self):
        card = dict(BASE_CARD)
        card["federation"] = {
            "federation_protocols": {
                "mcp": {"version": "2024-09-01", "enabled": False},
            },
        }
        score, findings = check_federation_compatibility(card)
        assert score == 0
        assert any("not assessed" in f["detail"] for f in findings)

    def test_no_protocols_declared(self):
        card = dict(BASE_CARD)
        card["federation"] = {
            "federation_protocols": {},
        }
        score, findings = check_federation_compatibility(card)
        assert score == 0
        assert any("No federation protocols" in f["detail"] for f in findings)


class TestCheckRoleConflicts:
    def test_no_role_declared(self):
        card = dict(BASE_CARD)
        card["federation"] = {}
        score, findings = check_role_conflicts(card)
        assert any("not assessed" in f["detail"] for f in findings)
        assert score == 0

    def test_primary_supervisor_match(self):
        card = dict(BASE_CARD)
        card["federation"] = {"role": "primary"}
        card["orchestration_hints"] = {"preferred_role": "supervisor"}
        score, findings = check_role_conflicts(card)
        assert any("matches" in f["detail"] for f in findings)
        assert score >= 5

    def test_secondary_worker_match(self):
        card = dict(BASE_CARD)
        card["federation"] = {"role": "secondary"}
        card["orchestration_hints"] = {"preferred_role": "worker"}
        score, findings = check_role_conflicts(card)
        assert any("matches" in f["detail"] for f in findings)
        assert score >= 5

    def test_primary_worker_conflict(self):
        card = dict(BASE_CARD)
        card["federation"] = {"role": "primary"}
        card["orchestration_hints"] = {"preferred_role": "worker"}
        score, findings = check_role_conflicts(card)
        assert any("conflicts" in f["detail"] for f in findings)
        assert score == 0

    def test_observer_no_compat_roles(self):
        card = dict(BASE_CARD)
        card["federation"] = {"role": "observer"}
        card["orchestration_hints"] = {"preferred_role": "supervisor"}
        score, findings = check_role_conflicts(card)
        assert score == 0


class TestCheckPermissionPropagation:
    def test_no_whitelist(self):
        card = dict(BASE_CARD)
        card["federation"] = {}
        score, findings = check_permission_propagation(card)
        assert any("not assessed" in f["detail"] for f in findings)
        assert score == 0

    def test_reasonable_whitelist(self):
        card = dict(BASE_CARD)
        card["federation"] = {
            "allowed_mcp_servers": ["fs-mcp", "search-mcp", "db-mcp"],
        }
        score, findings = check_permission_propagation(card)
        assert any("least privilege" in f["detail"] for f in findings)
        assert score >= 2

    def test_broad_whitelist(self):
        card = dict(BASE_CARD)
        card["federation"] = {
            "allowed_mcp_servers": [f"s{i}" for i in range(10)],
        }
        score, findings = check_permission_propagation(card)
        assert any("Broad" in f["detail"] for f in findings)
        warning = [f for f in findings if f["severity"] == "WARNING"]
        assert len(warning) >= 1

    def test_no_mcp_tool_with_whitelist(self):
        card = dict(BASE_CARD)
        card["capabilities"] = [
            c for c in BASE_CARD["capabilities"] if c["skill_id"] != "mcp_tool"
        ]
        card["federation"] = {
            "allowed_mcp_servers": ["fs-mcp"],
        }
        score, findings = check_permission_propagation(card)
        assert any("no mcp_tool" in f["detail"] for f in findings)

    def test_bridge_permission_risk(self):
        card = dict(BASE_CARD)
        card["capabilities"].append(
            {
                "skill_id": "bridge",
                "description": "bridge",
                "input_schema": {},
                "output_schema": {},
                "examples": ["bridge"],
            }
        )
        card["federation"] = {
            "allowed_mcp_servers": ["fs-mcp"],
        }
        score, findings = check_permission_propagation(card)
        assert any("Bridge" in f["detail"] for f in findings)


class TestRunD3Federation:
    def test_non_federation_skips_fed_checks(self):
        result = run_d3(BASE_CARD)
        fed_scores = {k: v for k, v in result["subscores"].items() if "federation" in k}
        assert all(v == 0 for v in fed_scores.values())

    def test_federation_card_includes_fed_scores(self):
        card = dict(BASE_CARD)
        card["federation"] = {
            "role": "primary",
            "allowed_mcp_servers": ["fs-mcp", "search-mcp"],
            "federation_protocols": {
                "a2a": {"version": "1.0", "enabled": True},
                "mcp": {"version": "2025-03-26", "enabled": True},
            },
        }
        result = run_d3(card)
        assert result["subscores"]["federation_compat"] >= 5
        assert result["subscores"]["federation_role"] >= 5
        assert result["subscores"]["federation_permissions"] >= 2

    def test_federation_card_score_higher_than_non_fed(self):
        fed_card = dict(BASE_CARD)
        fed_card["federation"] = {
            "role": "secondary",
            "allowed_mcp_servers": ["fs-mcp"],
            "federation_protocols": {
                "mcp": {"version": "2025-03-26", "enabled": True},
            },
        }
        fed_result = run_d3(fed_card)
        base_result = run_d3(BASE_CARD)
        assert fed_result["score"] >= base_result["score"]

    def test_federation_summary_field(self):
        card = dict(BASE_CARD)
        card["federation"] = {"role": "primary"}
        result = run_d3(card)
        assert result["summary"]["federation_role"] == "primary"

    def test_federation_summary_none(self):
        result = run_d3(BASE_CARD)
        assert result["summary"]["federation_role"] == "none"
