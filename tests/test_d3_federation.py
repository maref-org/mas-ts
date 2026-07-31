"""Tests for D3 Federation Evaluation (MAS-TS-001 v4.0)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d3_multi_agent import (
    _is_federation_card,
    _pair_a2a_compat,
    _pair_auth_compat,
    _pair_cross_border_compat,
    _pair_mcp_compat,
    _pair_role_compat,
    _pair_schema_compat,
    _pair_trust_compat,
    check_federation_compatibility,
    check_federation_compatibility_matrix,
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

    def test_primary_worker_conflict_with_arbitration_policy(self):
        card = dict(BASE_CARD)
        card["federation"] = {"role": "primary", "arbitration_policy": "human_review"}
        card["orchestration_hints"] = {"preferred_role": "worker"}
        score, findings = check_role_conflicts(card)
        assert any("arbitration" in f["detail"] for f in findings)
        assert score > 0

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
        # v0.8.1: federation capability is recognized (federation subscores
        # become non-zero), but total D3 score may now be LOWER than non-fed
        # because security_interaction correctly flags the larger A2A attack
        # surface (federation role + weak auth "None" + no delegation_audit)
        # as elevated risk. The test now asserts federation recognition rather
        # than total-score dominance.
        assert fed_result["subscores"]["federation_compat"] > 0
        assert (
            fed_result["subscores"]["federation_compat"]
            > base_result["subscores"]["federation_compat"]
        )

    def test_federation_summary_field(self):
        card = dict(BASE_CARD)
        card["federation"] = {"role": "primary"}
        result = run_d3(card)
        assert result["summary"]["federation_role"] == "primary"

    def test_federation_summary_none(self):
        result = run_d3(BASE_CARD)
        assert result["summary"]["federation_role"] == "none"


class TestPairCompatFunctions:
    def test_mcp_compat_both_enabled_known(self):
        a = {
            "federation_protocols": {"mcp": {"version": "2025-03-26", "enabled": True}}
        }
        b = {
            "federation_protocols": {"mcp": {"version": "2024-11-05", "enabled": True}}
        }
        assert _pair_mcp_compat(a, b) == 20

    def test_mcp_compat_one_disabled(self):
        a = {
            "federation_protocols": {"mcp": {"version": "2025-03-26", "enabled": True}}
        }
        b = {
            "federation_protocols": {"mcp": {"version": "2024-10-01", "enabled": False}}
        }
        assert _pair_mcp_compat(a, b) == 0

    def test_a2a_compat_both_enabled(self):
        a = {"federation_protocols": {"a2a": {"version": "1.0", "enabled": True}}}
        b = {"federation_protocols": {"a2a": {"version": "0.3", "enabled": True}}}
        assert _pair_a2a_compat(a, b) == 20

    def test_a2a_compat_one_disabled(self):
        a = {"federation_protocols": {"a2a": {"version": "1.0", "enabled": True}}}
        b = {"federation_protocols": {"a2a": {"version": "0.3", "enabled": False}}}
        assert _pair_a2a_compat(a, b) == 0

    def test_schema_compat_same(self):
        a = {"card_version": "1.2"}
        b = {"card_version": "1.2"}
        assert _pair_schema_compat(a, b) == 15

    def test_schema_compat_different(self):
        a = {"card_version": "1.2"}
        b = {"card_version": "2.0"}
        assert _pair_schema_compat(a, b) == 5

    def test_auth_compat_both_secure(self):
        a = {"authentication": {"type": "mTLS"}}
        b = {"authentication": {"type": "OAuth2"}}
        assert _pair_auth_compat(a, b) == 15

    def test_auth_compat_same_insecure(self):
        a = {"authentication": {"type": "APIKey"}}
        b = {"authentication": {"type": "APIKey"}}
        assert _pair_auth_compat(a, b) == 10

    def test_cross_border_compat_overlap(self):
        a = {
            "federation": {
                "cross_border_policy": {"allowed_transfer_zones": ["US", "EU"]}
            }
        }
        b = {
            "federation": {
                "cross_border_policy": {"allowed_transfer_zones": ["EU", "CN"]}
            }
        }
        assert _pair_cross_border_compat(a, b) == 10

    def test_cross_border_compat_no_overlap(self):
        a = {"federation": {"cross_border_policy": {"allowed_transfer_zones": ["US"]}}}
        b = {"federation": {"cross_border_policy": {"allowed_transfer_zones": ["CN"]}}}
        assert _pair_cross_border_compat(a, b) == 0

    def test_trust_compat_close(self):
        a = {"federation": {"trust_score": 0.85}}
        b = {"federation": {"trust_score": 0.80}}
        assert _pair_trust_compat(a, b) == 10

    def test_trust_compat_far(self):
        a = {"federation": {"trust_score": 0.90}}
        b = {"federation": {"trust_score": 0.30}}
        assert _pair_trust_compat(a, b) == 0

    def test_trust_compat_object_scores(self):
        a = {"federation": {"trust_score": {"value": 0.85, "evaluated_by": "eval-a"}}}
        b = {"federation": {"trust_score": {"value": 0.80, "evaluated_by": "eval-b"}}}
        assert _pair_trust_compat(a, b) == 10

    def test_role_compat_no_conflict(self):
        a = {"federation": {"role": "primary"}}
        b = {"federation": {"role": "secondary"}}
        assert _pair_role_compat(a, b) == 10

    def test_role_compat_primary_primary_conflict(self):
        a = {"federation": {"role": "primary"}}
        b = {"federation": {"role": "primary"}}
        assert _pair_role_compat(a, b) == 0


class TestFederationFixtures:
    def test_v2_multi_vendor_role_conflicts_have_arbitration(self):
        cards_dir = (
            Path(__file__).parent.parent
            / "mas_eval"
            / "data"
            / "multi_vendor_test"
            / "v2_cards"
        )
        for path in cards_dir.glob("agent_card_*_v2.json"):
            import json

            card = json.loads(path.read_text())
            score, findings = check_role_conflicts(card)
            details = " ".join(f["detail"] for f in findings)
            assert score > 0, f"{path.name}: {details}"


class TestFederationCompatibilityMatrix:
    def test_less_than_two_cards(self):
        score, matrix, findings = check_federation_compatibility_matrix([BASE_CARD])
        assert score == 100.0
        assert matrix == []

    def test_empty_cards(self):
        score, matrix, findings = check_federation_compatibility_matrix([])
        assert score == 100.0

    def test_two_identical_cards(self):
        cards = [BASE_CARD, BASE_CARD]
        score, matrix, findings = check_federation_compatibility_matrix(cards)
        assert 0 <= score <= 100
        assert len(matrix) == 2

    def test_matrix_shape(self):
        cards = [BASE_CARD, BASE_CARD, BASE_CARD]
        score, matrix, findings = check_federation_compatibility_matrix(cards)
        assert len(matrix) == 3
        assert len(matrix[0]) == 3

    def test_diagonal_is_100(self):
        cards = [BASE_CARD, BASE_CARD]
        score, matrix, findings = check_federation_compatibility_matrix(cards)
        assert matrix[0][0] == 100.0
        assert matrix[1][1] == 100.0

    def test_symmetric_matrix(self):
        cards = [BASE_CARD, BASE_CARD]
        score, matrix, findings = check_federation_compatibility_matrix(cards)
        assert matrix[0][1] == matrix[1][0]

    def test_findings_present(self):
        cards = [BASE_CARD, BASE_CARD]
        score, matrix, findings = check_federation_compatibility_matrix(cards)
        assert len(findings) > 0

    def test_findings_have_correct_structure(self):
        cards = [BASE_CARD, BASE_CARD]
        score, matrix, findings = check_federation_compatibility_matrix(cards)
        for f in findings:
            assert "severity" in f
            assert "category" in f
            assert "detail" in f

    def test_summary_finding_present(self):
        cards = [BASE_CARD, BASE_CARD]
        score, matrix, findings = check_federation_compatibility_matrix(cards)
        summaries = [f for f in findings if f["category"] == "fed_matrix_summary"]
        assert len(summaries) >= 1

    def test_matrix_returned(self):
        cards = [BASE_CARD, BASE_CARD]
        score, matrix, findings = check_federation_compatibility_matrix(cards)
        assert isinstance(matrix, list)

    def test_run_d3_with_federation_cards(self):
        fed_card = dict(BASE_CARD)
        fed_card["federation"] = {
            "federation_protocols": {
                "mcp": {"version": "2025-03-26", "enabled": True},
                "a2a": {"version": "1.0", "enabled": True},
            },
            "role": "secondary",
            "allowed_mcp_servers": ["fs-mcp"],
        }
        result = run_d3(fed_card, federation_cards=[BASE_CARD])
        assert "federation_matrix" in result["subscores"]
        assert result["subscores"]["federation_matrix"] >= 0
