# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for D1: Static Compliance (MAS-TS-001 v3.0)"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d1_compliance import (
    CORE_TOOLS,
    check_authentication,
    check_capabilities_completeness,
    check_cross_border,
    check_dag_acyclicity,
    check_data_residency,
    check_envelope,
    check_health_state,
    check_heartbeat,
    check_prompt_rot,
    check_schema,
    run_d1,
)

SAMPLE_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:test:test-01",
    "name": "Test Agent",
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
            "timestamp": "2026-05-29T00:00:00Z",
            "sender": "urn:agent:test:test:test-01",
        },
        "health_state": "HEALTHY",
        "heartbeat_interval_seconds": 30,
        "stale_node_timeout_seconds": 60,
    },
    "model_backend": {
        "provider": "test",
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
        },
        {
            "skill_id": "file_read",
            "description": "read files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["read"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_edit",
            "description": "edit files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["edit"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_write",
            "description": "write files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["write"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "glob",
            "description": "glob",
            "input_schema": {},
            "output_schema": {},
            "examples": ["glob"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "grep",
            "description": "grep",
            "input_schema": {},
            "output_schema": {},
            "examples": ["grep"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "web_search",
            "description": "search",
            "input_schema": {},
            "output_schema": {},
            "examples": ["search"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "web_fetch",
            "description": "fetch",
            "input_schema": {},
            "output_schema": {},
            "examples": ["fetch"],
            "business_rule_version": "2026-05-01",
        },
    ],
    "authentication": {"type": "APIKey", "scopes": ["test"]},
    "dependencies": ["git", "nodejs"],
}


def test_d1_full_compliant():
    result = run_d1(SAMPLE_CARD)
    assert result["domain"] == "D1"
    assert result["score"] >= 90, (
        f"Expected high score for compliant card, got {result['score']}"
    )
    assert result["conformance_verdict"] in ("COMPLIANT", "COMPLIANT-WITH-NOTES")


def test_d1_schema_missing_required():
    import os
    import tempfile

    card = dict(SAMPLE_CARD)
    del card["agent_id"]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "type": "object",
                "required": ["agent_id"],
                "properties": {"agent_id": {"type": "string"}},
                "additionalProperties": True,
            },
            f,
        )
        schema_path = f.name
    result = run_d1(card, schema_path)
    os.unlink(schema_path)
    assert any(
        f["check"] == "1.1" and f["severity"] == "CRITICAL" for f in result["findings"]
    )


def test_d1_data_residency_mismatch_critical():
    card = dict(SAMPLE_CARD)
    card["compliance"] = dict(card["compliance"])
    card["compliance"]["data_residency"] = "CN"
    card["compliance"]["model_backend_location"] = "US"
    result = run_d1(card)
    assert any(
        f["check"] == "1.2" and f["severity"] == "CRITICAL" for f in result["findings"]
    )


def test_d1_cross_border_fraud():
    card = dict(SAMPLE_CARD)
    card["compliance"] = dict(card["compliance"])
    card["compliance"]["data_residency"] = "CN"
    card["compliance"]["model_backend_location"] = "US"
    card["compliance"]["cross_border"] = False
    card["model_backend"] = dict(card["model_backend"])
    card["model_backend"]["endpoint"] = "https://api.deepseek.com/v1"
    result = run_d1(card)
    assert any(
        f["check"] == "1.3" and f["severity"] == "CRITICAL" for f in result["findings"]
    )


def test_d1_envelope_missing():
    card = dict(SAMPLE_CARD)
    card["constitution"] = {}
    result = run_d1(card)
    assert any(f["check"] == "1.4" for f in result["findings"])


def test_d1_health_state_invalid():
    card = dict(SAMPLE_CARD)
    card["constitution"] = dict(card["constitution"])
    card["constitution"]["health_state"] = "UNKNOWN"
    result = run_d1(card)
    assert any(f["check"] == "1.5" for f in result["findings"])


def test_d1_heartbeat_missing():
    card = dict(SAMPLE_CARD)
    card["constitution"] = dict(card["constitution"])
    del card["constitution"]["heartbeat_interval_seconds"]
    result = run_d1(card)
    assert any(f["check"] == "1.6" for f in result["findings"])


def test_d1_no_auth():
    card = dict(SAMPLE_CARD)
    card["authentication"] = {"type": "None"}
    result = run_d1(card)
    assert any(
        f["check"] == "1.7" and f["severity"] == "HIGH" for f in result["findings"]
    )


def test_d1_prompt_rot():
    card = dict(SAMPLE_CARD)
    card["capabilities"] = [
        {
            "skill_id": "bash",
            "description": "run",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
            "business_rule_version": "2024-01-01",
        },
    ]
    result = run_d1(card)
    assert any(f["check"] == "1.8" for f in result["findings"])


def test_d1_capabilities_below_50_pct():
    card = dict(SAMPLE_CARD)
    card["capabilities"] = [
        {
            "skill_id": "bash",
            "description": "run",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
        },
    ]
    result = run_d1(card)
    assert any(f["check"] == "1.9" for f in result["findings"])


def test_d1_dag_acyclic():
    result = run_d1(SAMPLE_CARD)
    assert any(
        f["check"] == "1.10" and f["severity"] == "INFO" for f in result["findings"]
    )


def test_d1_score_floor():
    card = {
        "card_version": "1.2",
        "agent_id": "bad",
        "name": "Bad",
        "version": "0.0.0",
        "compliance": {},
        "model_backend": {},
        "capabilities": [],
        "authentication": {"type": "None"},
    }
    result = run_d1(card)
    assert result["score"] == 0


def test_d1_check_schema():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "type": "object",
                "required": ["agent_id"],
                "properties": {"agent_id": {"type": "string"}},
            },
            f,
        )
        schema_path = f.name
    card_invalid = {"name": "no-agent-id"}
    findings = check_schema(card_invalid, schema_path)
    os.unlink(schema_path)
    assert len(findings) > 0


def test_d1_check_data_residency_missing():
    findings = check_data_residency({"compliance": {}})
    assert any("Missing data_residency" in f["detail"] for f in findings)


def test_d1_check_cross_border_false_with_mismatch():
    card = {
        "compliance": {
            "data_residency": "CN",
            "model_backend_location": "US",
            "cross_border": False,
        },
        "model_backend": {"endpoint": "https://api.deepseek.com/v1"},
    }
    findings = check_cross_border(card)
    assert any(f["severity"] == "CRITICAL" for f in findings)


def test_d1_check_envelope_missing():
    findings = check_envelope({"constitution": {}})
    assert len(findings) > 0


def test_d1_check_envelope_complete():
    card = {
        "constitution": {
            "envelope": {
                "message_id": "1",
                "correlation_id": "2",
                "timestamp": "3",
                "sender": "4",
            }
        }
    }
    findings = check_envelope(card)
    assert any(f["severity"] == "INFO" for f in findings)


def test_d1_check_health_state_valid():
    findings = check_health_state({"constitution": {"health_state": "HEALTHY"}})
    assert any(f["severity"] == "INFO" for f in findings)


def test_d1_check_health_state_invalid():
    findings = check_health_state({"constitution": {"health_state": "BAD"}})
    assert any(f["severity"] == "HIGH" for f in findings)


def test_d1_check_heartbeat_valid():
    findings = check_heartbeat(
        {
            "constitution": {
                "heartbeat_interval_seconds": 30,
                "stale_node_timeout_seconds": 60,
            }
        }
    )
    assert any(f["severity"] == "INFO" for f in findings)


def test_d1_check_heartbeat_invalid():
    findings = check_heartbeat({"constitution": {"heartbeat_interval_seconds": 999}})
    assert any(f["severity"] == "HIGH" for f in findings)


def test_d1_check_auth_none():
    findings = check_authentication({"authentication": {"type": "None"}})
    assert any(f["severity"] == "HIGH" for f in findings)


def test_d1_check_auth_valid():
    findings = check_authentication({"authentication": {"type": "OAuth2"}})
    assert any(f["severity"] == "INFO" for f in findings)


def test_d1_check_prompt_rot_missing_brv():
    findings = check_prompt_rot(
        {
            "capabilities": [
                {
                    "skill_id": "bash",
                    "description": "x",
                    "input_schema": {},
                    "output_schema": {},
                }
            ]
        }
    )
    assert any(f["severity"] == "WARNING" for f in findings)


def test_d1_check_capabilities_below_50():
    findings = check_capabilities_completeness({"capabilities": [{"skill_id": "bash"}]})
    assert len(findings) > 0


def test_d1_check_capabilities_above_50():
    caps = [{"skill_id": t} for t in list(CORE_TOOLS)[:5]]
    findings = check_capabilities_completeness({"capabilities": caps})
    assert any(f["severity"] == "INFO" for f in findings)


def test_d1_check_dag_no_cycle():
    findings = check_dag_acyclicity(SAMPLE_CARD)
    assert any(f["severity"] == "INFO" for f in findings)


def test_d1_findings_count():
    result = run_d1(SAMPLE_CARD)
    assert isinstance(result["summary"]["total_findings"], int)
    assert result["summary"]["total_findings"] == len(result["findings"])


def test_d1_conformance_blocked():
    card = {
        "card_version": "1.2",
        "agent_id": "bad",
        "name": "Bad",
        "version": "0.0.0",
        "compliance": {},
        "model_backend": {},
        "capabilities": [],
        "authentication": {"type": "None"},
    }
    result = run_d1(card)
    assert "NON-COMPLIANT" in result["conformance_verdict"]
    assert "blocked" in result["conformance_verdict"]
