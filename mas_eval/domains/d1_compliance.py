# SPDX-FileCopyrightText: 2026 frankiehot-tech
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
import re
import time
from datetime import datetime
from pathlib import Path
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
PROMPT_ROT_MAX_DAYS = 90

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
]

ENDPOINT_REGION_DB = {}
ENDPOINT_YAML = Path(__file__).parent.parent.parent / "configs" / "endpoints.yaml"
if ENDPOINT_YAML.exists():
    try:
        import yaml

        with open(ENDPOINT_YAML) as f:
            ep_config = yaml.safe_load(f)
        for region, domains in ep_config.get("regions", {}).items():
            for domain in domains:
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


def _resolve_endpoint_region(endpoint):
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


def check_schema(card, schema_path=None):
    findings = []
    if not schema_path:
        return findings
    schema_path = Path(schema_path)
    if not schema_path.exists():
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


def check_data_residency(card):
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


def check_cross_border(card):
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


def check_envelope(card):
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


def check_health_state(card):
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


def check_heartbeat(card):
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


def check_authentication(card):
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


def check_prompt_rot(card):
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


def check_capabilities_completeness(card):
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


def check_dag_acyclicity(card):
    findings = []
    capabilities = card.get("capabilities", [])
    skill_ids = {cap["skill_id"] for cap in capabilities}
    dependencies = card.get("dependencies", [])
    deps_set = set(dependencies)

    graph = {}
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

    def has_cycle(node):
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


def run_d1(card, schema_path=None):
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
