"""Tests for Agent Card v2.0 Schema (MAS-TS-001 v4.0 Federation Edition)"""

import json
import os
import sys
import tempfile
from pathlib import Path

import jsonschema.exceptions

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d1_compliance import check_schema
from scripts.migrate_agent_card import (
    extract_vendor_id,
    infer_agent_type,
    migrate_card,
    migrate_constitution,
    migrate_cross_border_policy,
    migrate_governance,
)

SCHEMA_DIR = Path(__file__).parent.parent / "mas_eval" / "schemas"
SCHEMA_V2 = json.loads((SCHEMA_DIR / "agent_card_v2.0.json").read_text())
VALIDATOR = jsonschema.Draft7Validator(SCHEMA_V2)
META_VALIDATOR = jsonschema.Draft7Validator(
    json.loads((SCHEMA_DIR / "agent_card_v1.2.json").read_text())
)

V2_CARD = {
    "card_version": "2.0",
    "schema_version": "2.0",
    "agent_id": "urn:agent:anthropic:claude-code:claude-code-1-0",
    "vendor_id": "anthropic",
    "agent_type": "cli",
    "name": "Test Agent v2",
    "description": "A test agent card for v2.0 schema validation",
    "version": "2.0.0",
    "compliance": {
        "data_residency": "US",
        "data_classification": "confidential",
        "cross_border": True,
        "model_backend_location": "US",
        "audit_trail_required": True,
    },
    "constitution": {
        "envelope": {
            "message_id": "msg-001",
            "correlation_id": "corr-001",
            "timestamp": "2026-06-11T00:00:00Z",
            "sender": "urn:agent:anthropic:claude-code:claude-code-1-0",
        },
        "health_state": "HEALTHY",
        "heartbeat_interval_seconds": 30,
        "stale_node_timeout_seconds": 60,
    },
    "model_backend": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "deployment": "cloud",
        "endpoint": "https://api.anthropic.com/v1/messages",
    },
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "Execute shell commands",
            "input_schema": {},
            "output_schema": {},
            "examples": ["example1"],
            "business_rule_version": "2026-05-01",
        }
    ],
    "authentication": {"type": "OAuth2", "scopes": ["read", "write"]},
    "federation": {
        "role": "secondary",
        "trust_score": 0.85,
        "trust_history": [
            {
                "timestamp": "2026-06-10T00:00:00Z",
                "score": 0.80,
                "source": "self",
            }
        ],
        "allowed_mcp_servers": ["fs-mcp", "search-mcp"],
        "cross_border_policy": {
            "data_residency": "US",
            "allowed_transfer_zones": ["US", "EU"],
            "requires_approval": True,
        },
        "federation_protocols": {
            "a2a": {"version": "1.0", "enabled": True},
            "mcp": {"version": "2025-03-26", "enabled": True},
        },
    },
    "governance": {
        "state_machine_version": "gray-code-v1.5",
        "circuit_breaker": {
            "enabled": True,
            "threshold": 3,
            "cooldown_seconds": 30,
        },
        "oscillation_detection": {
            "enabled": True,
            "window_size": 3,
        },
        "cost_model": {
            "max_tokens_per_hour": 1000000,
            "max_cost_per_run": 0.50,
        },
    },
    "endpoints": {
        "a2a": "https://api.anthropic.com/v1/agents",
        "mcp": "https://api.anthropic.com/v1/mcp",
    },
    "orchestration_hints": {
        "preferred_role": "worker",
        "parallel_safe": True,
        "stateful": True,
    },
    "message_format": {
        "protocol": "json-rpc-2.0",
        "transport": "stdio",
    },
}


class TestSchemaV2Structural:
    def test_schema_is_valid_json_schema(self):
        jsonschema.Draft7Validator.check_schema(SCHEMA_V2)

    def test_schema_title(self):
        assert SCHEMA_V2["title"] == "MAS-TS-001 Agent Card v2.0"

    def test_schema_type_is_object(self):
        assert SCHEMA_V2["type"] == "object"

    def test_schema_has_all_required_fields(self):
        required = set(SCHEMA_V2["required"])
        expected = {
            "card_version",
            "agent_id",
            "name",
            "version",
            "compliance",
            "constitution",
            "model_backend",
            "capabilities",
            "authentication",
        }
        assert required == expected

    def test_schema_version_const(self):
        assert SCHEMA_V2["properties"]["schema_version"]["const"] == "2.0"

    def test_card_version_no_const(self):
        props = SCHEMA_V2["properties"]["card_version"]
        assert "const" not in props
        assert props["type"] == "string"


class TestSchemaV2CoreRequired:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_full_v2_card_valid(self):
        errors = self.validate(V2_CARD)
        assert not errors, f"Expected no errors, got: {[e.message for e in errors]}"

    def test_missing_agent_id(self):
        card = {k: v for k, v in V2_CARD.items() if k != "agent_id"}
        errors = self.validate(card)
        assert any("agent_id" in str(e.message) for e in errors)

    def test_missing_name(self):
        card = {k: v for k, v in V2_CARD.items() if k != "name"}
        errors = self.validate(card)
        assert any("name" in str(e.message) for e in errors)

    def test_missing_version(self):
        card = {k: v for k, v in V2_CARD.items() if k != "version"}
        errors = self.validate(card)
        assert any("version" in str(e.message) for e in errors)

    def test_missing_compliance(self):
        card = {k: v for k, v in V2_CARD.items() if k != "compliance"}
        errors = self.validate(card)
        assert any("compliance" in str(e.message) for e in errors)

    def test_missing_constitution(self):
        card = {k: v for k, v in V2_CARD.items() if k != "constitution"}
        errors = self.validate(card)
        assert any("constitution" in str(e.message) for e in errors)

    def test_missing_model_backend(self):
        card = {k: v for k, v in V2_CARD.items() if k != "model_backend"}
        errors = self.validate(card)
        assert any("model_backend" in str(e.message) for e in errors)

    def test_missing_capabilities(self):
        card = {k: v for k, v in V2_CARD.items() if k != "capabilities"}
        errors = self.validate(card)
        assert any("capabilities" in str(e.message) for e in errors)

    def test_missing_authentication(self):
        card = {k: v for k, v in V2_CARD.items() if k != "authentication"}
        errors = self.validate(card)
        assert any("authentication" in str(e.message) for e in errors)


class TestSchemaV2AgentId:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_valid_urn_agent_id(self):
        card = dict(V2_CARD)
        card["agent_id"] = "urn:agent:test:project:agent-01"
        errors = self.validate(card)
        assert not errors

    def test_invalid_agent_id_no_urn(self):
        card = dict(V2_CARD)
        card["agent_id"] = "test-agent-001"
        errors = self.validate(card)
        assert errors

    def test_invalid_agent_id_short(self):
        card = dict(V2_CARD)
        card["agent_id"] = "short"
        errors = self.validate(card)
        assert errors


class TestSchemaV2Compliance:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_valid_residency_values(self):
        for region in ("CN", "US", "EU", "SG", "OTHER", "LOCAL"):
            card = dict(V2_CARD)
            card["compliance"] = dict(V2_CARD["compliance"])
            card["compliance"]["data_residency"] = region
            card["compliance"]["model_backend_location"] = region
            errors = self.validate(card)
            assert not errors, f"Failed for region: {region}"

    def test_invalid_residency_value(self):
        card = dict(V2_CARD)
        card["compliance"] = dict(V2_CARD["compliance"])
        card["compliance"]["data_residency"] = "MOON"
        errors = self.validate(card)
        assert errors

    def test_missing_data_classification(self):
        card = dict(V2_CARD)
        card["compliance"] = {
            k: v for k, v in V2_CARD["compliance"].items() if k != "data_classification"
        }
        errors = self.validate(card)
        assert errors

    def test_missing_cross_border(self):
        card = dict(V2_CARD)
        card["compliance"] = {
            k: v for k, v in V2_CARD["compliance"].items() if k != "cross_border"
        }
        errors = self.validate(card)
        assert errors

    def test_valid_data_classification_values(self):
        for cls in ("public", "internal", "confidential", "restricted"):
            card = dict(V2_CARD)
            card["compliance"] = dict(V2_CARD["compliance"])
            card["compliance"]["data_classification"] = cls
            errors = self.validate(card)
            assert not errors, f"Failed for classification: {cls}"


class TestSchemaV2Constitution:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_valid_health_states(self):
        for state in ("STARTING", "HEALTHY", "DEGRADED", "DEAD"):
            card = dict(V2_CARD)
            card["constitution"] = dict(V2_CARD["constitution"])
            card["constitution"]["health_state"] = state
            errors = self.validate(card)
            assert not errors, f"Failed for health_state: {state}"

    def test_invalid_health_state(self):
        card = dict(V2_CARD)
        card["constitution"] = dict(V2_CARD["constitution"])
        card["constitution"]["health_state"] = "healthy"
        errors = self.validate(card)
        assert errors

    def test_envelope_missing_sender(self):
        card = dict(V2_CARD)
        card["constitution"] = {
            "envelope": {
                k: v
                for k, v in V2_CARD["constitution"]["envelope"].items()
                if k != "sender"
            },
            "health_state": "HEALTHY",
            "heartbeat_interval_seconds": 30,
        }
        errors = self.validate(card)
        assert errors

    def test_envelope_missing_timestamp(self):
        card = dict(V2_CARD)
        card["constitution"] = {
            "envelope": {
                k: v
                for k, v in V2_CARD["constitution"]["envelope"].items()
                if k != "timestamp"
            },
            "health_state": "HEALTHY",
            "heartbeat_interval_seconds": 30,
        }
        errors = self.validate(card)
        assert errors

    def test_heartbeat_interval_minimum(self):
        card = dict(V2_CARD)
        card["constitution"] = dict(V2_CARD["constitution"])
        card["constitution"]["heartbeat_interval_seconds"] = 0
        errors = self.validate(card)
        assert errors

    def test_heartbeat_interval_maximum(self):
        card = dict(V2_CARD)
        card["constitution"] = dict(V2_CARD["constitution"])
        card["constitution"]["heartbeat_interval_seconds"] = 301
        errors = self.validate(card)
        assert errors

    def test_stale_node_timeout_default(self):
        card = dict(V2_CARD)
        card["constitution"] = dict(V2_CARD["constitution"])
        card["constitution"]["stale_node_timeout_seconds"] = 5
        errors = self.validate(card)
        assert errors


class TestSchemaV2Federation:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_valid_roles(self):
        for role in ("primary", "secondary", "observer"):
            card = dict(V2_CARD)
            card["federation"] = dict(V2_CARD["federation"])
            card["federation"]["role"] = role
            errors = self.validate(card)
            assert not errors, f"Failed for role: {role}"

    def test_invalid_role(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["role"] = "commander"
        errors = self.validate(card)
        assert errors

    def test_trust_score_range_min(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["trust_score"] = -0.1
        errors = self.validate(card)
        assert errors

    def test_trust_score_range_max(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["trust_score"] = 1.1
        errors = self.validate(card)
        assert errors

    def test_trust_score_boundary(self):
        for score in (0.0, 0.5, 1.0):
            card = dict(V2_CARD)
            card["federation"] = dict(V2_CARD["federation"])
            card["federation"]["trust_score"] = score
            errors = self.validate(card)
            assert not errors, f"Failed for score: {score}"

    def test_allowed_mcp_servers_unique(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["allowed_mcp_servers"] = ["mcp1", "mcp1"]
        errors = self.validate(card)
        assert errors

    def test_allowed_mcp_servers_empty(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["allowed_mcp_servers"] = []
        errors = self.validate(card)
        assert not errors

    def test_cross_border_policy_missing_approval(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        fed = dict(V2_CARD["federation"])
        fed["cross_border_policy"] = {
            "data_residency": "US",
            "allowed_transfer_zones": ["US"],
        }
        card["federation"] = fed
        errors = self.validate(card)
        assert errors

    def test_cross_border_policy_invalid_transfer_zone(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        fed = dict(V2_CARD["federation"])
        fed["cross_border_policy"] = {
            "data_residency": "US",
            "allowed_transfer_zones": ["MOON"],
            "requires_approval": False,
        }
        card["federation"] = fed
        errors = self.validate(card)
        assert errors

    def test_federation_protocols_empty(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["federation_protocols"] = {"a2a": {}, "mcp": {}}
        errors = self.validate(card)
        assert not errors

    def test_federation_optional(self):
        card = {k: v for k, v in V2_CARD.items() if k != "federation"}
        errors = self.validate(card)
        assert not errors

    def test_trust_history_timestamp_required(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["trust_history"] = [{"score": 0.5, "source": "self"}]
        errors = self.validate(card)
        assert errors

    def test_trust_score_object_with_evaluator_valid(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["trust_score"] = {
            "value": 0.85,
            "evaluated_by": "urn:agent:mas-ts:evaluator",
            "method": "behavioral_analysis",
        }
        errors = self.validate(card)
        assert not errors

    def test_trust_score_object_value_range(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["trust_score"] = {
            "value": 1.5,
            "evaluated_by": "urn:agent:mas-ts:evaluator",
        }
        errors = self.validate(card)
        assert errors

    def test_federation_permissions_values(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["permissions"] = {
            "read": True,
            "write": "requires_hitl",
            "delete": "requires_hitl",
            "execute": "denied",
        }
        errors = self.validate(card)
        assert not errors

    def test_federation_permissions_reject_invalid_value(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["permissions"] = {"execute": "always"}
        errors = self.validate(card)
        assert errors

    def test_federation_arbitration_policy_valid(self):
        card = dict(V2_CARD)
        card["federation"] = dict(V2_CARD["federation"])
        card["federation"]["arbitration_policy"] = "human_review"
        errors = self.validate(card)
        assert not errors

    def test_audit_trace_flags_required_when_audit_present(self):
        card = dict(V2_CARD)
        card["audit"] = {"trace_id_required": True}
        errors = self.validate(card)
        assert errors

    def test_audit_trace_flags_valid(self):
        card = dict(V2_CARD)
        card["audit"] = {
            "trace_id_required": True,
            "timestamp_required": True,
            "source_agent_required": True,
            "target_agent_required": True,
        }
        errors = self.validate(card)
        assert not errors


class TestSchemaV2Governance:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_governance_optional(self):
        card = {k: v for k, v in V2_CARD.items() if k != "governance"}
        errors = self.validate(card)
        assert not errors

    def test_circuit_breaker_nested_structure(self):
        card = dict(V2_CARD)
        card["governance"] = {
            "circuit_breaker": {
                "enabled": True,
                "threshold": 5,
                "cooldown_seconds": 60,
            },
        }
        errors = self.validate(card)
        assert not errors

    def test_circuit_breaker_threshold_minimum(self):
        card = dict(V2_CARD)
        card["governance"] = {
            "circuit_breaker": {
                "enabled": True,
                "threshold": 0,
                "cooldown_seconds": 30,
            },
        }
        errors = self.validate(card)
        assert errors

    def test_oscillation_detection_window_minimum(self):
        card = dict(V2_CARD)
        card["governance"] = {
            "oscillation_detection": {"enabled": True, "window_size": 0},
        }
        errors = self.validate(card)
        assert errors

    def test_cost_model_positive_values(self):
        card = dict(V2_CARD)
        card["governance"] = {
            "cost_model": {"max_tokens_per_hour": 500000, "max_cost_per_run": 0.25},
        }
        errors = self.validate(card)
        assert not errors

    def test_cost_model_negative_cost(self):
        card = dict(V2_CARD)
        card["governance"] = {
            "cost_model": {"max_tokens_per_hour": 1000, "max_cost_per_run": -1},
        }
        errors = self.validate(card)
        assert errors

    def test_governance_no_flat_fields(self):
        card = dict(V2_CARD)
        card["governance"] = {
            "circuit_breaker_enabled": True,
            "oscillation_detection_enabled": True,
        }
        errors = self.validate(card)
        assert errors


class TestSchemaV2MultiVendorFixtures:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_v2_multi_vendor_cards_have_federation_release_fields(self):
        cards_dir = (
            Path(__file__).parent.parent
            / "mas_eval"
            / "data"
            / "multi_vendor_test"
            / "v2_cards"
        )
        card_paths = sorted(cards_dir.glob("agent_card_*_v2.json"))
        cards = [json.loads(path.read_text()) for path in card_paths]
        passing_cards = [
            card
            for card in cards
            if card.get("federation", {}).get("allowed_mcp_servers")
            and all(
                card.get("audit", {}).get(field) is True
                for field in (
                    "trace_id_required",
                    "timestamp_required",
                    "source_agent_required",
                    "target_agent_required",
                )
            )
        ]
        assert len(passing_cards) >= 3
        assert all(not self.validate(card) for card in cards)


class TestSchemaV2BackwardCompat:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_v12_card_without_federation_passes(self):
        v12_card = {
            "card_version": "1.2",
            "agent_id": "urn:agent:anthropic:claude-code:claude-code-1-0",
            "name": "Claude Code",
            "version": "1.0.0",
            "compliance": {
                "data_residency": "US",
                "data_classification": "confidential",
                "cross_border": True,
                "model_backend_location": "US",
                "audit_trail_required": True,
            },
            "constitution": {
                "envelope": {
                    "message_id": "msg-001",
                    "correlation_id": "corr-001",
                    "timestamp": "2026-06-11T00:00:00Z",
                    "sender": "urn:agent:anthropic:claude-code:claude-code-1-0",
                },
                "health_state": "HEALTHY",
                "heartbeat_interval_seconds": 30,
            },
            "model_backend": {
                "provider": "anthropic",
                "model": "claude-sonnet-4",
                "deployment": "cloud",
                "endpoint": "https://api.anthropic.com/v1/messages",
            },
            "capabilities": [
                {
                    "skill_id": "bash",
                    "description": "run commands",
                    "input_schema": {},
                    "output_schema": {},
                    "examples": ["ls"],
                    "business_rule_version": "2026-05-01",
                }
            ],
            "authentication": {"type": "APIKey", "scopes": ["read"]},
        }
        errors = self.validate(v12_card)
        assert not errors, (
            f"v1.2 card failed v2.0 validation: {[e.message for e in errors]}"
        )

    def test_v12_card_with_flat_governance_fails(self):
        card = dict(V2_CARD)
        card["governance"] = {
            "state_machine_version": "v1",
            "circuit_breaker_enabled": True,
            "oscillation_detection_enabled": False,
        }
        errors = self.validate(card)
        assert errors


class TestSchemaV2ModelBackend:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_valid_deployment_types(self):
        for dep in ("local", "cloud", "hybrid"):
            card = dict(V2_CARD)
            card["model_backend"] = dict(V2_CARD["model_backend"])
            card["model_backend"]["deployment"] = dep
            errors = self.validate(card)
            assert not errors, f"Failed for deployment: {dep}"

    def test_invalid_deployment_type(self):
        card = dict(V2_CARD)
        card["model_backend"] = dict(V2_CARD["model_backend"])
        card["model_backend"]["deployment"] = "edge"
        errors = self.validate(card)
        assert errors


class TestSchemaV2Authentication:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_valid_auth_types(self):
        for auth_type in ("OAuth2", "APIKey", "mTLS", "None"):
            card = dict(V2_CARD)
            card["authentication"] = dict(V2_CARD["authentication"])
            card["authentication"]["type"] = auth_type
            errors = self.validate(card)
            assert not errors, f"Failed for auth type: {auth_type}"

    def test_invalid_auth_type(self):
        card = dict(V2_CARD)
        card["authentication"] = dict(V2_CARD["authentication"])
        card["authentication"]["type"] = "Basic"
        errors = self.validate(card)
        assert errors


class TestSchemaV2Capabilities:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_empty_capabilities_fails(self):
        card = dict(V2_CARD)
        card["capabilities"] = []
        errors = self.validate(card)
        assert errors

    def test_capability_missing_description(self):
        card = dict(V2_CARD)
        card["capabilities"] = [dict(V2_CARD["capabilities"][0])]
        del card["capabilities"][0]["description"]
        errors = self.validate(card)
        assert errors

    def test_capability_missing_input_schema(self):
        card = dict(V2_CARD)
        card["capabilities"] = [dict(V2_CARD["capabilities"][0])]
        del card["capabilities"][0]["input_schema"]
        errors = self.validate(card)
        assert errors

    def test_capability_empty_examples_fails(self):
        card = dict(V2_CARD)
        card["capabilities"] = [dict(V2_CARD["capabilities"][0])]
        card["capabilities"][0]["examples"] = []
        errors = self.validate(card)
        assert errors

    def test_business_rule_version_pattern_valid(self):
        card = dict(V2_CARD)
        card["capabilities"] = [dict(V2_CARD["capabilities"][0])]
        card["capabilities"][0]["business_rule_version"] = "2026-12-31"
        errors = self.validate(card)
        assert not errors

    def test_business_rule_version_pattern_invalid(self):
        card = dict(V2_CARD)
        card["capabilities"] = [dict(V2_CARD["capabilities"][0])]
        card["capabilities"][0]["business_rule_version"] = "2026/12/31"
        errors = self.validate(card)
        assert errors


class TestSchemaV2VendorType:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def test_vendor_id_optional(self):
        card = {k: v for k, v in V2_CARD.items() if k != "vendor_id"}
        errors = self.validate(card)
        assert not errors

    def test_agent_type_optional(self):
        card = {k: v for k, v in V2_CARD.items() if k != "agent_type"}
        errors = self.validate(card)
        assert not errors

    def test_agent_type_enum_all(self):
        for atype in ("cli", "ide", "api", "daemon"):
            card = dict(V2_CARD)
            card["agent_type"] = atype
            errors = self.validate(card)
            assert not errors, f"Failed for agent_type: {atype}"

    def test_agent_type_invalid(self):
        card = dict(V2_CARD)
        card["agent_type"] = "desktop"
        errors = self.validate(card)
        assert errors


class TestMigrationScript:
    def test_extract_vendor_id_anthropic(self):
        assert (
            extract_vendor_id("urn:agent:anthropic:claude-code:claude-code-1-0")
            == "anthropic"
        )

    def test_extract_vendor_id_openai(self):
        assert extract_vendor_id("urn:agent:openai:codex:codex-1-0") == "openai"

    def test_extract_vendor_id_unknown(self):
        assert extract_vendor_id("urn:agent:test:project:agent-01") == "test"

    def test_extract_vendor_id_non_urn(self):
        assert extract_vendor_id("plain-id") == "unknown"

    def test_infer_agent_type_ide(self):
        assert infer_agent_type({"name": "Cursor", "description": "AI IDE"}) == "ide"

    def test_infer_agent_type_cli(self):
        assert (
            infer_agent_type({"name": "Claude Code", "description": "CLI tool"})
            == "cli"
        )

    def test_infer_agent_type_api(self):
        assert (
            infer_agent_type({"name": "API Gateway", "description": "API endpoint"})
            == "api"
        )

    def test_infer_agent_type_daemon(self):
        assert (
            infer_agent_type({"name": "Worker", "description": "daemon service"})
            == "daemon"
        )

    def test_infer_agent_type_default(self):
        assert (
            infer_agent_type({"name": "Generic", "description": "A generic agent"})
            == "cli"
        )

    def test_migrate_card_adds_schema_version(self):
        card = {
            "agent_id": "urn:agent:test:project:agent-01",
            "name": "Test",
            "version": "1.0.0",
            "compliance": {
                "data_residency": "US",
                "data_classification": "public",
                "cross_border": False,
                "model_backend_location": "US",
                "audit_trail_required": False,
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
                }
            ],
            "authentication": {"type": "None"},
        }
        result = migrate_card(card)
        assert result["schema_version"] == "2.0"
        assert result["card_version"] == "2.0"

    def test_migrate_card_adds_federation_defaults(self):
        card = {
            "agent_id": "urn:agent:test:project:agent-01",
            "name": "Test",
            "version": "1.0.0",
            "compliance": {
                "data_residency": "US",
                "data_classification": "public",
                "cross_border": False,
                "model_backend_location": "US",
                "audit_trail_required": False,
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
                }
            ],
            "authentication": {"type": "None"},
        }
        result = migrate_card(card)
        assert "federation" in result
        assert result["federation"]["role"] == "secondary"
        assert result["federation"]["trust_score"] == 0.5
        assert result["federation"]["allowed_mcp_servers"] == []

    def test_migrate_card_skips_already_v2(self):
        card = {"schema_version": "2.0", "card_version": "2.0", "agent_id": "test"}
        result = migrate_card(card)
        assert result["card_version"] == "2.0"
        assert len(result) == 3

    def test_migrate_constitution_missing(self):
        result = migrate_constitution(None, "urn:agent:test:agent:001")
        assert result["health_state"] == "HEALTHY"
        assert result["envelope"]["sender"] == "urn:agent:test:agent:001"
        assert result["heartbeat_interval_seconds"] == 30

    def test_migrate_constitution_old_format(self):
        old = {
            "envelope": {"version": "1.0", "jurisdiction": "US-CA"},
            "health_state": "healthy",
            "heartbeat_interval_seconds": 15,
        }
        result = migrate_constitution(old, "urn:agent:test:agent:001")
        assert "message_id" in result["envelope"]
        assert "version" not in result["envelope"]
        assert result["health_state"] == "HEALTHY"

    def test_migrate_governance_flat_to_nested(self):
        old = {"circuit_breaker_enabled": True, "oscillation_detection_enabled": False}
        result = migrate_governance(old)
        assert result["circuit_breaker"]["enabled"] is True
        assert result["oscillation_detection"]["enabled"] is False

    def test_migrate_governance_none(self):
        assert migrate_governance(None) is None

    def test_migrate_cross_border_policy(self):
        compliance = {"data_residency": "CN", "cross_border": True}
        result = migrate_cross_border_policy(compliance)
        assert result["data_residency"] == "CN"
        assert result["allowed_transfer_zones"] == ["CN"]
        assert result["requires_approval"] is True

    def test_migrate_card_preserves_existing_federation(self):
        card = {
            "agent_id": "urn:agent:test:project:agent-01",
            "name": "Test",
            "version": "1.0.0",
            "compliance": {
                "data_residency": "US",
                "data_classification": "public",
                "cross_border": False,
                "model_backend_location": "US",
                "audit_trail_required": False,
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
                }
            ],
            "authentication": {"type": "None"},
            "federation": {
                "role": "primary",
                "trust_score": 0.9,
                "allowed_mcp_servers": ["custom-mcp"],
            },
        }
        result = migrate_card(card)
        assert result["federation"]["role"] == "primary"
        assert result["federation"]["trust_score"] == 0.9
        assert result["federation"]["allowed_mcp_servers"] == ["custom-mcp"]

    def test_migrated_card_passes_v2_schema(self):
        card = {
            "agent_id": "urn:agent:anthropic:claude-code:claude-code-1-0",
            "name": "Claude Code",
            "version": "1.0.0",
            "compliance": {
                "data_residency": "US",
                "data_classification": "confidential",
                "cross_border": True,
                "model_backend_location": "US",
                "audit_trail_required": True,
            },
            "model_backend": {
                "provider": "anthropic",
                "model": "claude-sonnet-4",
                "deployment": "cloud",
                "endpoint": "https://api.anthropic.com/v1/messages",
            },
            "capabilities": [
                {
                    "skill_id": "bash",
                    "description": "run",
                    "input_schema": {},
                    "output_schema": {},
                    "examples": ["ls"],
                }
            ],
            "authentication": {"type": "APIKey"},
        }
        result = migrate_card(card)
        errors = list(VALIDATOR.iter_errors(result))
        assert not errors, f"Migrated card failed v2.0: {[e.message for e in errors]}"

    def test_migrate_card_vendor_id_from_agent_id(self):
        card = {
            "agent_id": "urn:agent:bytedance:trae-cn:trae-cn-1-0",
            "name": "Trae CN",
            "version": "1.0.0",
            "compliance": {
                "data_residency": "CN",
                "data_classification": "confidential",
                "cross_border": False,
                "model_backend_location": "CN",
                "audit_trail_required": True,
            },
            "model_backend": {
                "provider": "bytedance",
                "model": "doubao",
                "deployment": "cloud",
                "endpoint": "https://api.bytedance.com/v1/chat",
            },
            "capabilities": [
                {
                    "skill_id": "code_completion",
                    "description": "code",
                    "input_schema": {},
                    "output_schema": {},
                    "examples": ["complete"],
                }
            ],
            "authentication": {"type": "APIKey"},
        }
        result = migrate_card(card)
        assert result["vendor_id"] == "bytedance"

    def test_migrate_card_constitution_added_when_missing(self):
        card = {
            "agent_id": "urn:agent:test:project:agent-01",
            "name": "Minimal",
            "version": "1.0.0",
            "compliance": {
                "data_residency": "US",
                "data_classification": "public",
                "cross_border": False,
                "model_backend_location": "US",
                "audit_trail_required": False,
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
                }
            ],
            "authentication": {"type": "None"},
        }
        result = migrate_card(card)
        assert "constitution" in result
        assert "envelope" in result["constitution"]
        assert "health_state" in result["constitution"]


class TestSchemaV2MigratedCards:
    def validate(self, card):
        return list(VALIDATOR.iter_errors(card))

    def _load_v2_card(self, relative_path):
        path = Path(__file__).parent.parent / relative_path
        return json.loads(path.read_text())

    def test_multi_vendor_claude_code(self):
        card = self._load_v2_card(
            "mas_eval/data/multi_vendor_test/agent_card_claude_code.json"
        )
        errors = self.validate(card)
        assert not errors

    def test_multi_vendor_codex(self):
        card = self._load_v2_card(
            "mas_eval/data/multi_vendor_test/agent_card_codex.json"
        )
        errors = self.validate(card)
        assert not errors

    def test_multi_vendor_cursor(self):
        card = self._load_v2_card(
            "mas_eval/data/multi_vendor_test/agent_card_cursor.json"
        )
        errors = self.validate(card)
        assert not errors

    def test_multi_vendor_opencode(self):
        card = self._load_v2_card(
            "mas_eval/data/multi_vendor_test/agent_card_opencode.json"
        )
        errors = self.validate(card)
        assert not errors

    def test_multi_vendor_traecn(self):
        card = self._load_v2_card(
            "mas_eval/data/multi_vendor_test/agent_card_traecn.json"
        )
        errors = self.validate(card)
        assert not errors

    def test_sample_card_claude_code_v2(self):
        card = self._load_v2_card("mas_eval/data/sample_cards/claude_code_v2.json")
        errors = self.validate(card)
        assert not errors

    def test_sample_card_compliant_v2(self):
        card = self._load_v2_card("mas_eval/data/sample_cards/compliant_agent_v2.json")
        errors = self.validate(card)
        assert not errors

    def test_sample_card_maref_v2(self):
        card = self._load_v2_card("mas_eval/data/sample_cards/maref_v2.json")
        errors = self.validate(card)
        assert not errors

    def test_sample_card_percv_v2(self):
        card = self._load_v2_card("mas_eval/data/sample_cards/percv_v2.json")
        errors = self.validate(card)
        assert not errors

    def test_sample_card_skillos_v2(self):
        card = self._load_v2_card("mas_eval/data/sample_cards/skillos_v2.json")
        errors = self.validate(card)
        assert not errors


class TestSchemaV2CheckSchemaIntegration:
    def test_check_schema_v2_default_path(self):
        card = dict(V2_CARD)
        v2_schema_path = SCHEMA_DIR / "agent_card_v2.0.json"
        findings = check_schema(card, str(v2_schema_path))
        critical = [f for f in findings if f["severity"] == "CRITICAL"]
        assert len(critical) == 0, f"v2 card has schema violations: {critical}"

    def test_check_schema_v2_rejects_missing_field(self):
        card = {k: v for k, v in V2_CARD.items() if k != "agent_id"}
        v2_schema_path = SCHEMA_DIR / "agent_card_v2.0.json"
        findings = check_schema(card, str(v2_schema_path))
        critical = [f for f in findings if f["severity"] == "CRITICAL"]
        assert len(critical) >= 1

    def test_check_schema_v2_migrated_card_passes(self):
        card = {
            "agent_id": "urn:agent:anthropic:claude-code:claude-code-1-0",
            "name": "Claude Code",
            "version": "1.0.0",
            "compliance": {
                "data_residency": "US",
                "data_classification": "confidential",
                "cross_border": True,
                "model_backend_location": "US",
                "audit_trail_required": True,
            },
            "model_backend": {
                "provider": "anthropic",
                "model": "claude-sonnet-4",
                "deployment": "cloud",
                "endpoint": "https://api.anthropic.com/v1/messages",
            },
            "capabilities": [
                {
                    "skill_id": "bash",
                    "description": "run",
                    "input_schema": {},
                    "output_schema": {},
                    "examples": ["ls"],
                }
            ],
            "authentication": {"type": "APIKey"},
        }
        migrated = migrate_card(card)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(migrated, f)
            schema_path = f.name
        try:
            findings = check_schema(migrated, schema_path)
            critical = [x for x in findings if x["severity"] == "CRITICAL"]
            assert len(critical) == 0
        finally:
            os.unlink(schema_path)
