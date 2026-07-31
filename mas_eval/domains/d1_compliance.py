# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""
MAS-TS-001 v3.0 — D1: Static Compliance

10-check audit: schema validation, data residency, cross-border fraud,
Constitution envelope/health/heartbeat, authentication, prompt rot,
capabilities completeness, DAG acyclicity.

Scoring: Base=100, deduct per severity CRITICAL(-25)/HIGH(-15)/WARNING(-5)/INFO(0), floor=0.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

CORE_TOOLS = {
    "bash",
    "file_read",
    "file_edit",
    "file_write",
    "glob",
    "grep",
    "web_search",
    "web_fetch",
}
PROMPT_ROT_MAX_DAYS = int(os.environ.get("PROMPT_ROT_MAX_DAYS", "90"))

D1_CHECKS = [
    {"id": "1.1", "name": "agent_card_schema", "severity": "CRITICAL", "deduction": 25},
    {
        "id": "1.2",
        "name": "data_residency_consistency",
        "severity": "CRITICAL",
        "deduction": 25,
    },
    {
        "id": "1.3",
        "name": "cross_border_fraud",
        "severity": "CRITICAL",
        "deduction": 25,
    },
    {"id": "1.4", "name": "envelope_compliance", "severity": "HIGH", "deduction": 15},
    {
        "id": "1.5",
        "name": "health_state_registration",
        "severity": "HIGH",
        "deduction": 15,
    },
    {"id": "1.6", "name": "heartbeat_mechanism", "severity": "HIGH", "deduction": 15},
    {
        "id": "1.7",
        "name": "authentication_presence",
        "severity": "HIGH",
        "deduction": 15,
    },
    {
        "id": "1.8",
        "name": "prompt_rot_detection",
        "severity": "WARNING",
        "deduction": 5,
    },
    {
        "id": "1.9",
        "name": "capabilities_completeness",
        "severity": "WARNING",
        "deduction": 5,
    },
    {"id": "1.10", "name": "dag_acyclicity", "severity": "HIGH", "deduction": 15},
    {
        "id": "1.11",
        "name": "cross_border_chain",
        "severity": "CRITICAL",
        "deduction": 25,
    },
    {
        "id": "1.12",
        "name": "federation_version_compat",
        "severity": "HIGH",
        "deduction": 15,
    },
    {
        "id": "1.13",
        "name": "trace_audit_chain",
        "severity": "HIGH",
        "deduction": 15,
    },
    {
        "id": "1.14",
        "name": "capability_declaration_completeness",
        "severity": "HIGH",
        "deduction": 15,
    },
]

ENDPOINT_REGION_DB: dict[str, str] = {}
ENDPOINT_YAML = Path(__file__).parent.parent.parent / "configs" / "endpoints.yaml"
if ENDPOINT_YAML.exists():
    try:
        import yaml

        with open(ENDPOINT_YAML) as f:
            ep_config = yaml.safe_load(f)
        for region, domains in ep_config.get("regions", {}).items():
            for domain in domains:
                if isinstance(domain, str):
                    ENDPOINT_REGION_DB[domain] = region
    except Exception:
        pass

if not ENDPOINT_REGION_DB:
    ENDPOINT_REGION_DB = {
        "api.openai.com": "US",
        "api.anthropic.com": "US",
        "api.groq.com": "US",
        "api.together.xyz": "US",
        "api.openrouter.ai": "US",
        "api.gemini.google.com": "US",
        "api.mistral.ai": "EU",
        "api.siliconflow.cn": "CN",
        "dashscope.aliyuncs.com": "CN",
        "api.deepseek.com": "CN",
        "open.bigmodel.cn": "CN",
        "localhost": "LOCAL",
        "127.0.0.1": "LOCAL",
    }

OVERSEAS_PATTERNS = [
    r"api\.openai\.com",
    r"api\.anthropic\.com",
    r"api\.groq\.com",
    r"api\.together\.xyz",
    r"api\.openrouter\.ai",
    r"\.azure\.com",
    r"api\.gemini\.google\.com",
    r"api\.mistral\.ai",
]


def _resolve_endpoint_region(endpoint: str) -> str:
    if not endpoint:
        return "UNKNOWN"
    try:
        parsed = urlparse(endpoint)
        domain = parsed.netloc or endpoint.split("/")[0].split(":")[0]
        domain = domain.split(":")[0]
    except Exception:
        domain = endpoint.split("/")[0].split(":")[0]
    if domain in ENDPOINT_REGION_DB:
        return ENDPOINT_REGION_DB[domain]
    for known_domain, region in ENDPOINT_REGION_DB.items():
        if domain.endswith("." + known_domain) or domain.endswith(known_domain):
            return region
    return "UNKNOWN"


def check_schema(
    card: dict[str, Any], schema_path: str | None = None
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not schema_path:
        ver = card.get("schema_version", card.get("card_version", "1.2"))
        if ver == "2.0":
            schema_path = str(
                Path(__file__).parent.parent / "schemas" / "agent_card_v2.0.json"
            )
        else:
            schema_path = str(
                Path(__file__).parent.parent / "schemas" / "agent_card_v1.2.json"
            )
    resolved_path = Path(schema_path)
    if not resolved_path.exists():
        findings.append(
            {
                "check": "1.1",
                "severity": "HIGH",
                "detail": f"Schema file not found: {schema_path}",
            }
        )
        return findings
    try:
        import jsonschema

        with open(schema_path) as f:
            schema = json.load(f)
        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(card))
        for err in errors:
            path = ".".join(str(p) for p in err.absolute_path) or "(root)"
            findings.append(
                {
                    "check": "1.1",
                    "severity": "CRITICAL",
                    "detail": f"Schema violation at {path}: {err.message}",
                }
            )
    except ImportError:
        findings.append(
            {
                "check": "1.1",
                "severity": "WARNING",
                "detail": "jsonschema not installed, schema validation skipped",
            }
        )
    except json.JSONDecodeError as e:
        findings.append(
            {
                "check": "1.1",
                "severity": "CRITICAL",
                "detail": f"Schema file is not valid JSON: {e}",
            }
        )
    return findings


def check_data_residency(card: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    compliance = card.get("compliance", {})
    residency = compliance.get("data_residency")
    backend_loc = compliance.get("model_backend_location")
    if not residency:
        findings.append(
            {
                "check": "1.2",
                "severity": "CRITICAL",
                "detail": "Missing data_residency field",
            }
        )
    if not backend_loc:
        findings.append(
            {
                "check": "1.2",
                "severity": "CRITICAL",
                "detail": "Missing model_backend_location field",
            }
        )
    if residency and backend_loc and residency != backend_loc:
        findings.append(
            {
                "check": "1.2",
                "severity": "CRITICAL",
                "detail": f"data_residency({residency}) != model_backend_location({backend_loc})",
            }
        )
    return findings


def check_cross_border(card: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    compliance = card.get("compliance", {})
    residency = compliance.get("data_residency")
    backend_loc = compliance.get("model_backend_location")
    cross_border = compliance.get("cross_border")

    if cross_border is False and residency and backend_loc and residency != backend_loc:
        findings.append(
            {
                "check": "1.3",
                "severity": "CRITICAL",
                "detail": f"cross_border=false but data_residency={residency} != model_backend_location={backend_loc}",
            }
        )

    endpoint = card.get("model_backend", {}).get("endpoint", "")
    if endpoint and residency in ("CN", "EU", "SG"):
        for pattern in OVERSEAS_PATTERNS:
            if re.search(pattern, endpoint):
                findings.append(
                    {
                        "check": "1.3",
                        "severity": "HIGH",
                        "detail": f"Declared residency={residency} but endpoint {endpoint} matches overseas service",
                    }
                )
                break

    return findings


def check_envelope(card: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    constitution = card.get("constitution", {})
    env = constitution.get("envelope", {})
    required_fields = ["message_id", "correlation_id", "timestamp", "sender"]
    missing = [f for f in required_fields if not env.get(f)]
    if missing:
        findings.append(
            {
                "check": "1.4",
                "severity": "HIGH",
                "detail": f"Missing envelope fields: {', '.join(missing)}",
            }
        )
    else:
        findings.append(
            {
                "check": "1.4",
                "severity": "INFO",
                "detail": "All required envelope fields present (message_id, correlation_id, timestamp, sender)",
            }
        )
    if not constitution:
        findings.append(
            {
                "check": "1.4",
                "severity": "HIGH",
                "detail": "No constitution block found in Agent Card",
            }
        )
    return findings


def check_health_state(card: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    constitution = card.get("constitution", {})
    health = constitution.get("health_state")
    valid_states = ("STARTING", "HEALTHY", "DEGRADED", "DEAD")
    if not health:
        findings.append(
            {
                "check": "1.5",
                "severity": "HIGH",
                "detail": "Missing health_state in constitution",
            }
        )
    elif health not in valid_states:
        findings.append(
            {
                "check": "1.5",
                "severity": "HIGH",
                "detail": f"Invalid health_state '{health}', must be one of {valid_states}",
            }
        )
    else:
        findings.append(
            {
                "check": "1.5",
                "severity": "INFO",
                "detail": f"Health state registered: {health}",
            }
        )
    return findings


def check_heartbeat(card: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    constitution = card.get("constitution", {})
    interval = constitution.get("heartbeat_interval_seconds")
    if interval is None:
        findings.append(
            {
                "check": "1.6",
                "severity": "HIGH",
                "detail": "Missing heartbeat_interval_seconds in constitution",
            }
        )
    elif not isinstance(interval, int) or interval < 1 or interval > 300:
        findings.append(
            {
                "check": "1.6",
                "severity": "HIGH",
                "detail": f"Invalid heartbeat_interval_seconds={interval}, must be 1-300",
            }
        )
    else:
        findings.append(
            {
                "check": "1.6",
                "severity": "INFO",
                "detail": f"Heartbeat interval: {interval}s",
            }
        )

    stale_timeout = constitution.get("stale_node_timeout_seconds")
    if stale_timeout is not None:
        if stale_timeout < 10:
            findings.append(
                {
                    "check": "1.6",
                    "severity": "WARNING",
                    "detail": f"stale_node_timeout_seconds={stale_timeout} is too low (<10s)",
                }
            )
        else:
            findings.append(
                {
                    "check": "1.6",
                    "severity": "INFO",
                    "detail": f"Stale node timeout: {stale_timeout}s",
                }
            )
    return findings


def check_authentication(card: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    auth = card.get("authentication", {})
    auth_type = auth.get("type", "None")
    if auth_type == "None":
        findings.append(
            {
                "check": "1.7",
                "severity": "HIGH",
                "detail": "No authentication declared (type=None)",
            }
        )
    else:
        findings.append(
            {
                "check": "1.7",
                "severity": "INFO",
                "detail": f"Authentication type: {auth_type}",
            }
        )
    return findings


def check_prompt_rot(card: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    today = time.strftime("%Y-%m-%d")
    for cap in card.get("capabilities", []):
        brv = cap.get("business_rule_version")
        skill_id = cap.get("skill_id", "?")
        if not brv:
            findings.append(
                {
                    "check": "1.8",
                    "severity": "WARNING",
                    "detail": f"Skill '{skill_id}' missing business_rule_version",
                }
            )
            continue
        try:
            brv_date = datetime.strptime(brv, "%Y-%m-%d")
            today_date = datetime.strptime(today, "%Y-%m-%d")
            age = (today_date - brv_date).days
            if age > PROMPT_ROT_MAX_DAYS:
                findings.append(
                    {
                        "check": "1.8",
                        "severity": "WARNING",
                        "detail": f"Skill '{skill_id}' business_rule_version={brv} is {age} days old (> {PROMPT_ROT_MAX_DAYS})",
                    }
                )
        except ValueError:
            findings.append(
                {
                    "check": "1.8",
                    "severity": "WARNING",
                    "detail": f"Skill '{skill_id}' invalid business_rule_version format: {brv}",
                }
            )
    return findings


def check_capabilities_completeness(card: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}
    covered_core = declared_tools & CORE_TOOLS
    core_pct = len(covered_core) / len(CORE_TOOLS) * 100
    if core_pct < 50:
        missing = CORE_TOOLS - declared_tools
        findings.append(
            {
                "check": "1.9",
                "severity": "WARNING",
                "detail": f"Core tool coverage {core_pct:.0f}% (<50%), missing: {', '.join(sorted(missing))}",
            }
        )
    else:
        findings.append(
            {
                "check": "1.9",
                "severity": "INFO",
                "detail": f"Core tool coverage: {core_pct:.0f}% ({len(covered_core)}/{len(CORE_TOOLS)})",
            }
        )
    return findings


# v0.8.0 — D1.14: High-risk capability sub-permission declaration completeness.
# Inspired by Claude Code 2026-06-30 incident — 'bash' capability was declared
# but its ability to read timezone/env vars (used for backdoor) was not.
HIGH_RISK_CAPABILITIES = {
    "bash",
    "shell_exec",
    "os_exec",
    "exec",
    "subprocess",
    "file_read",
    "file_edit",
}

REQUIRED_SUB_PERMISSIONS: dict[str, dict[str, str]] = {
    "bash": {
        "env_read": "Whether bash can read environment variables",
        "timezone_read": "Whether bash can read timezone info",
        "network_access": "Whether bash can make network calls",
    },
    "shell_exec": {
        "env_read": "Whether shell_exec can read environment variables",
        "timezone_read": "Whether shell_exec can read timezone info",
        "network_access": "Whether shell_exec can make network calls",
    },
    "os_exec": {
        "env_read": "Whether os_exec can read environment variables",
        "timezone_read": "Whether os_exec can read timezone info",
        "network_access": "Whether os_exec can make network calls",
    },
    "exec": {
        "env_read": "Whether exec can read environment variables",
        "timezone_read": "Whether exec can read timezone info",
        "network_access": "Whether exec can make network calls",
    },
    "subprocess": {
        "env_read": "Whether subprocess can read environment variables",
        "timezone_read": "Whether subprocess can read timezone info",
        "network_access": "Whether subprocess can make network calls",
    },
    "file_read": {
        "system_files": "Whether file_read can access /etc, /proc, /sys",
        "credential_files": "Whether file_read can access ~/.ssh, ~/.aws",
    },
    "file_edit": {
        "system_files": "Whether file_edit can modify /etc, /proc, /sys",
        "credential_files": "Whether file_edit can modify ~/.ssh, ~/.aws",
    },
}


def check_capability_declaration_completeness(
    card: dict[str, Any],
) -> list[dict[str, Any]]:
    """Check D1.14: High-risk capabilities must declare sub-permissions.

    Inspired by Claude Code incident — 'bash' capability was declared but
    its ability to read timezone/env vars (used for backdoor) was not.
    Undeclared sub-permissions may hide covert behaviors.

    Findings use root_cause='declaration_inconsistency' to distinguish from
    other D1 permission violations.
    """
    findings: list[dict[str, Any]] = []
    capabilities = card.get("capabilities", [])

    for cap in capabilities:
        if not isinstance(cap, dict):
            continue
        skill_id = cap.get("skill_id", "").lower()
        if skill_id not in HIGH_RISK_CAPABILITIES:
            continue

        required = REQUIRED_SUB_PERMISSIONS.get(skill_id, {})
        if not required:
            continue

        sub_perms = cap.get("sub_permissions", {})
        if not isinstance(sub_perms, dict):
            sub_perms = {}

        missing: list[str] = []
        for perm_name, description in required.items():
            if perm_name not in sub_perms:
                missing.append(f"{skill_id}.{perm_name} ({description})")

        if missing:
            severity = "HIGH" if len(missing) >= 2 else "WARNING"
            findings.append(
                {
                    "check": "1.14",
                    "severity": severity,
                    "category": "capability_declaration_incomplete",
                    "detail": (
                        f"High-risk capability '{skill_id}' is missing sub-permission "
                        f"declarations: {'; '.join(missing)}. Undeclared sub-permissions "
                        f"may hide covert behaviors (cf. Claude Code 2026-06-30 incident "
                        f"where 'bash' was used to read timezone without declaration)."
                    ),
                    "root_cause": "declaration_inconsistency",
                }
            )

    return findings


def check_dag_acyclicity(card: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    capabilities = card.get("capabilities", [])
    skill_ids = {cap["skill_id"] for cap in capabilities}
    dependencies = card.get("dependencies", [])
    deps_set = set(dependencies)

    graph: dict[str, set[str]] = {}
    for skill_id in skill_ids:
        graph[skill_id] = set()

    for dep in deps_set:
        if dep in skill_ids:
            continue
        for skill_id in skill_ids:
            if dep in skill_id:
                graph[skill_id].add(dep)

    visited = set()
    recursion_stack = set()

    def has_cycle(node: str) -> bool:
        visited.add(node)
        recursion_stack.add(node)
        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                if has_cycle(neighbor):
                    return True
            elif neighbor in recursion_stack:
                return True
        recursion_stack.discard(node)
        return False

    cycle_found = False
    for node in graph:
        if node not in visited:
            if has_cycle(node):
                cycle_found = True
                break

    if cycle_found:
        findings.append(
            {
                "check": "1.10",
                "severity": "HIGH",
                "detail": "Cycle detected in tool dependency graph",
            }
        )
    else:
        findings.append(
            {
                "check": "1.10",
                "severity": "INFO",
                "detail": "Tool dependency graph is acyclic",
            }
        )
    return findings


def check_data_cross_border_chain(card: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    fed = card.get("federation") or {}
    policy = fed.get("cross_border_policy") or {}
    compliance = card.get("compliance") or {}

    if not policy:
        is_cross_border = compliance.get("cross_border", False)
        data_residency = compliance.get("data_residency")
        model_location = compliance.get("model_backend_location")
        severity = (
            "HIGH" if is_cross_border and data_residency != model_location else "INFO"
        )
        detail = (
            "Cross-border enabled with mixed residency but missing cross-border policy"
            if severity == "HIGH"
            else "No federation cross-border policy declared"
        )
        findings.append(
            {
                "check": "1.11",
                "severity": severity,
                "detail": detail,
            }
        )
        return findings

    card_residency = compliance.get("data_residency")
    policy_residency = policy.get("data_residency")
    if card_residency and policy_residency and card_residency != policy_residency:
        findings.append(
            {
                "check": "1.11",
                "severity": "CRITICAL",
                "detail": f"Cross-border policy residency {policy_residency} "
                f"mismatches compliance residency {card_residency}",
            }
        )

    zones = policy.get("allowed_transfer_zones") or []
    if not zones:
        findings.append(
            {
                "check": "1.11",
                "severity": "HIGH",
                "detail": "Cross-border policy has no allowed transfer zones",
            }
        )

    is_cross_border = compliance.get("cross_border", False)
    has_foreign_zone = False
    if is_cross_border and policy_residency:
        has_foreign_zone = any(z != policy_residency for z in zones)
        if not has_foreign_zone:
            findings.append(
                {
                    "check": "1.11",
                    "severity": "CRITICAL",
                    "detail": f"Cross-border enabled but allowed_transfer_zones {zones} "
                    f"only contains current residency {policy_residency}",
                }
            )

    requires_approval = policy.get("requires_approval", False)
    if is_cross_border and has_foreign_zone and not requires_approval:
        findings.append(
            {
                "check": "1.11",
                "severity": "HIGH",
                "detail": "Cross-border transfer enabled without requiring approval",
            }
        )

    if not findings:
        findings.append(
            {
                "check": "1.11",
                "severity": "INFO",
                "detail": f"Cross-border chain valid: {policy_residency} → {zones}",
            }
        )
    return findings


def check_federation_version_compat(card: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    fed = card.get("federation") or {}
    protocols = fed.get("federation_protocols") or {}

    if not protocols:
        findings.append(
            {
                "check": "1.12",
                "severity": "INFO",
                "detail": "No federation protocols declared",
            }
        )
        return findings

    KNOWN_MCP_VERSIONS = {"2025-03-26", "2024-11-05", "2024-10-01"}
    KNOWN_A2A_VERSIONS = {"1.0", "0.3"}
    MIN_MCP_VERSION = "2024-10-01"
    MIN_A2A_VERSION = "0.3"

    mcp = protocols.get("mcp") or {}
    if mcp:
        mcp_ver = mcp.get("version", "")
        mcp_enabled = mcp.get("enabled", True)
        if mcp_enabled and mcp_ver:
            if mcp_ver in KNOWN_MCP_VERSIONS:
                findings.append(
                    {
                        "check": "1.12",
                        "severity": "INFO",
                        "detail": f"MCP protocol version {mcp_ver} is compatible",
                    }
                )
            elif mcp_ver < MIN_MCP_VERSION:
                findings.append(
                    {
                        "check": "1.12",
                        "severity": "HIGH",
                        "detail": f"MCP version {mcp_ver} is outdated "
                        f"(minimum: {MIN_MCP_VERSION})",
                    }
                )
            else:
                findings.append(
                    {
                        "check": "1.12",
                        "severity": "INFO",
                        "detail": f"MCP version {mcp_ver} is newer than known versions",
                    }
                )

    a2a = protocols.get("a2a") or {}
    if a2a:
        a2a_ver = a2a.get("version", "")
        a2a_enabled = a2a.get("enabled", False)
        if a2a_enabled and a2a_ver:
            if a2a_ver in KNOWN_A2A_VERSIONS:
                findings.append(
                    {
                        "check": "1.12",
                        "severity": "INFO",
                        "detail": f"A2A protocol version {a2a_ver} is compatible",
                    }
                )
            elif a2a_ver < MIN_A2A_VERSION:
                findings.append(
                    {
                        "check": "1.12",
                        "severity": "HIGH",
                        "detail": f"A2A version {a2a_ver} is outdated "
                        f"(minimum: {MIN_A2A_VERSION})",
                    }
                )
            else:
                findings.append(
                    {
                        "check": "1.12",
                        "severity": "INFO",
                        "detail": f"A2A version {a2a_ver} is newer than known versions",
                    }
                )

    if not findings:
        findings.append(
            {
                "check": "1.12",
                "severity": "INFO",
                "detail": "Federation protocols not in use",
            }
        )

    return findings


def _audit_trace_enabled(card: dict[str, Any]) -> bool:
    audit = card.get("audit")
    required_flags = (
        "trace_id_required",
        "timestamp_required",
        "source_agent_required",
        "target_agent_required",
    )
    if isinstance(audit, dict):
        return all(audit.get(flag) is True for flag in required_flags)
    fed = card.get("federation") or {}
    fed_audit = fed.get("audit") if isinstance(fed, dict) else {}
    if isinstance(fed_audit, dict):
        return bool(fed_audit.get("trace_enabled", False))
    return False


def _missing_audit_trace_flags(card: dict[str, Any]) -> list[str]:
    audit = card.get("audit")
    required_flags = (
        "trace_id_required",
        "timestamp_required",
        "source_agent_required",
        "target_agent_required",
    )
    if not isinstance(audit, dict) or not audit:
        return []
    return [flag for flag in required_flags if audit.get(flag) is not True]


def check_trace_audit_chain(
    card: dict[str, Any], federation_cards: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    findings = []
    fed = card.get("federation") or {}
    envelope = card.get("constitution", {}).get("envelope", {}) or {}

    has_correlation = bool(envelope.get("correlation_id"))
    has_message_id = bool(envelope.get("message_id"))
    has_timestamp = bool(envelope.get("timestamp"))
    has_sender = bool(envelope.get("sender"))

    trace_fields = [has_message_id, has_correlation, has_timestamp, has_sender]

    if all(trace_fields):
        findings.append(
            {
                "check": "1.13",
                "severity": "INFO",
                "detail": (
                    "Envelope supports full trace chain "
                    "(message_id, correlation_id, timestamp, sender)"
                ),
            }
        )
    else:
        field_names = [
            "message_id",
            "correlation_id",
            "timestamp",
            "sender",
        ]
        missing = [fn for fn, present in zip(field_names, trace_fields) if not present]
        findings.append(
            {
                "check": "1.13",
                "severity": "WARNING",
                "detail": f"Envelope missing trace fields: {', '.join(missing)}",
            }
        )

    missing_audit_flags = _missing_audit_trace_flags(card)
    if missing_audit_flags:
        findings.append(
            {
                "check": "1.13",
                "severity": "HIGH",
                "detail": f"Missing audit trace flags: {', '.join(missing_audit_flags)}",
            }
        )

    trace_enabled = _audit_trace_enabled(card)

    if trace_enabled:
        audit_config = fed.get("audit") if isinstance(fed, dict) else {}
        trace_version = (
            audit_config.get("trace_version", "")
            if isinstance(audit_config, dict)
            else ""
        )
        findings.append(
            {
                "check": "1.13",
                "severity": "INFO",
                "detail": f"Trace_id audit enabled (version={trace_version or 'N/A'})",
            }
        )

    agent_name = card.get("name", card.get("agent_id", "primary"))

    if federation_cards:
        all_cards = [card] + list(federation_cards)
        trace_states = []
        for c in all_cards:
            c_trace = _audit_trace_enabled(c)
            c_name = c.get("name", c.get("agent_id", "unknown"))
            trace_states.append((c_name, c_trace))

        enabled_count = sum(1 for _, t in trace_states if t)
        total = len(trace_states)

        if enabled_count == 0:
            findings.append(
                {
                    "check": "1.13",
                    "severity": "HIGH",
                    "detail": (
                        f"No trace_id support among {total} agents — "
                        f"audit chain integrity cannot be verified"
                    ),
                }
            )
        elif enabled_count < total:
            missing_names = [n for n, t in trace_states if not t]
            findings.append(
                {
                    "check": "1.13",
                    "severity": "WARNING",
                    "detail": (
                        f"Partial trace support: {enabled_count}/{total} agents "
                        f"enable trace_id — gaps: {', '.join(missing_names)}"
                    ),
                }
            )
        else:
            findings.append(
                {
                    "check": "1.13",
                    "severity": "INFO",
                    "detail": (
                        f"All {total} agents support trace_id audit chain — "
                        f"full chain integrity across federation"
                    ),
                }
            )

    if not any(trace_fields) and not trace_enabled and not federation_cards:
        findings.append(
            {
                "check": "1.13",
                "severity": "INFO",
                "detail": f"Agent '{agent_name}' has no trace_id audit chain configured",
            }
        )

    return findings


def run_d1(
    card: dict[str, Any],
    schema_path: str | None = None,
    federation_cards: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings = []
    findings.extend(check_schema(card, schema_path))
    findings.extend(check_data_residency(card))
    findings.extend(check_cross_border(card))
    findings.extend(check_envelope(card))
    findings.extend(check_health_state(card))
    findings.extend(check_heartbeat(card))
    findings.extend(check_authentication(card))
    findings.extend(check_prompt_rot(card))
    findings.extend(check_capabilities_completeness(card))
    findings.extend(check_dag_acyclicity(card))
    findings.extend(check_data_cross_border_chain(card))
    findings.extend(check_federation_version_compat(card))
    findings.extend(check_trace_audit_chain(card, federation_cards))
    findings.extend(check_capability_declaration_completeness(card))

    # Gold Standard v3.0-GA §10 — augment findings with v2 attribution fields.
    from mas_eval.scoring.findings import upgrade_findings_to_v2

    findings = upgrade_findings_to_v2(
        findings,
        default_layer="safety",
        default_root_cause="permission_violation",
        default_reproducibility="deterministic",
        default_mitigation="manual_intervention",
    )

    score = 100.0
    for f in findings:
        severity_deductions = {"CRITICAL": 25, "HIGH": 15, "WARNING": 5, "INFO": 0}
        deduction = severity_deductions.get(f["severity"], 0)
        score -= deduction

    score = max(0, min(100, score))

    summary = {
        "total_findings": len(findings),
        "critical": len([f for f in findings if f["severity"] == "CRITICAL"]),
        "high": len([f for f in findings if f["severity"] == "HIGH"]),
        "warning": len([f for f in findings if f["severity"] == "WARNING"]),
        "info": len([f for f in findings if f["severity"] == "INFO"]),
    }

    conformance_verdict = "COMPLIANT"
    if summary["critical"] > 0:
        conformance_verdict = "NON-COMPLIANT (blocked)"
    elif summary["high"] > 0:
        conformance_verdict = "NON-COMPLIANT (review required)"
    elif summary["warning"] > 0:
        conformance_verdict = "COMPLIANT-WITH-NOTES"

    return {
        "domain": "D1",
        "name": "Static Compliance",
        "score": round(score, 1),
        "findings": findings,
        "summary": summary,
        "conformance_verdict": conformance_verdict,
    }
