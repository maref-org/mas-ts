#!/usr/bin/env python3
"""
MAS-TS-001 Full-Run Evaluation Pipeline (Layer 1-5)
Usage:
  python mas_full_run.py --card mas_eval/data/sample_cards/claude_code.json
  python mas_full_run.py --card claude_code.json --tasks mas_eval/data/claude_code_tasks.json --output reports/full_eval.json
  python mas_full_run.py --card claude_code.json --source-dir "/path/to/agent/source" --output reports/full_eval.json

Implements the complete 5-layer evaluation per MAS-TS-001 v2.1:
  Layer 1: Static Audit (compliance scan, schema, cross-border, prompt rot)
  Layer 2: Inference Metrics (model quality, latency, token, context window)
  Layer 3: Action Metrics (tool coverage, schema correctness, action sequences)
  Layer 4: E2E Metrics (task coverage, capability completeness, dependency analysis)
  Layer 5: MAS Dimension (agent spawn, session isolation, coordination, state, scheduling)
"""
import json
import sys
import argparse
import time
import subprocess
import os
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

import argcomplete

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from mas_eval import __version__ as VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
logger = logging.getLogger(__name__)

SCHEMA_DIR = Path(__file__).parent / "mas_eval" / "schemas"
DEFAULT_SCHEMA = SCHEMA_DIR / "agent_card_v1.1.json"

MODEL_QUALITY_DB = {
    "claude-sonnet-4": {"tier": "premium", "reasoning": 0.92, "coding": 0.95, "multilingual": 0.90},
    "claude-opus-4": {"tier": "premium", "reasoning": 0.96, "coding": 0.93, "multilingual": 0.92},
    "claude-haiku-3.5": {"tier": "fast", "reasoning": 0.82, "coding": 0.85, "multilingual": 0.80},
    "gpt-4o": {"tier": "premium", "reasoning": 0.90, "coding": 0.91, "multilingual": 0.88},
    "gpt-4-turbo": {"tier": "premium", "reasoning": 0.88, "coding": 0.89, "multilingual": 0.86},
    "deepseek-chat-v3": {"tier": "value", "reasoning": 0.85, "coding": 0.90, "multilingual": 0.82},
    "qwen-max": {"tier": "value", "reasoning": 0.83, "coding": 0.84, "multilingual": 0.88},
}

DEPLOYMENT_LATENCY = {
    "local": {"p50_ms": 50, "p99_ms": 200, "cold_start_ms": 500},
    "cloud": {"p50_ms": 300, "p99_ms": 2000, "cold_start_ms": 3000},
    "hybrid": {"p50_ms": 150, "p99_ms": 1000, "cold_start_ms": 1500},
}

CONTEXT_WINDOWS = {
    "claude-sonnet-4": 200000,
    "claude-opus-4": 200000,
    "claude-haiku-3.5": 200000,
    "gpt-4o": 128000,
    "gpt-4-turbo": 128000,
    "deepseek-chat-v3": 64000,
    "qwen-max": 32000,
}

TOOL_COMPLEXITY_WEIGHTS = {
    "bash": 0.8,
    "file_read": 0.3,
    "file_edit": 0.6,
    "file_write": 0.5,
    "glob": 0.2,
    "grep": 0.2,
    "web_search": 0.4,
    "web_fetch": 0.5,
    "agent_tool": 0.9,
    "mcp_tool": 0.7,
    "todo_write": 0.2,
    "plan_mode": 0.4,
    "task_management": 0.3,
    "worktree": 0.8,
    "notebook_edit": 0.4,
    "lsp": 0.5,
    "cron": 0.6,
    "memory": 0.5,
    "bridge": 0.9,
    "skill_invoke": 0.4,
}

MAS_DIMENSIONS = {
    "agent_spawn": {
        "description": "Ability to spawn and manage sub-agents",
        "required_tools": ["agent_tool"],
        "weight": 0.25
    },
    "session_isolation": {
        "description": "Support for isolated execution sessions (worktree, sandbox)",
        "required_tools": ["worktree"],
        "weight": 0.15
    },
    "coordination": {
        "description": "Coordinator mode for multi-agent task delegation",
        "required_tools": ["agent_tool", "todo_write"],
        "weight": 0.20
    },
    "state_persistence": {
        "description": "Persistent state across sessions (memory, tasks)",
        "required_tools": ["memory", "task_management"],
        "weight": 0.15
    },
    "scheduling": {
        "description": "Cron-based recurring task scheduling",
        "required_tools": ["cron"],
        "weight": 0.10
    },
    "remote_control": {
        "description": "Remote bridge control for multi-session management",
        "required_tools": ["bridge"],
        "weight": 0.15
    },
}


def load_card(card_path):
    try:
        with open(card_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in card file %s: %s", card_path, e)
        sys.exit(1)


def load_tasks(tasks_path):
    if not tasks_path or not Path(tasks_path).exists():
        return None
    try:
        with open(tasks_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in tasks file %s: %s", tasks_path, e)
        return None


def run_layer1_static_audit(card, schema_path=None):
    findings = []
    score = 100.0

    try:
        import jsonschema
        if schema_path and Path(schema_path).exists():
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema = json.load(f)
            except json.JSONDecodeError as e:
                findings.append({"severity": "CRITICAL", "category": "schema_validation", "detail": f"Schema file is not valid JSON: {e}"})
                score -= 10
            validator = jsonschema.Draft7Validator(schema)
            errors = list(validator.iter_errors(card))
            for err in errors:
                path = ".".join(str(p) for p in err.absolute_path) or "(root)"
                findings.append({
                    "severity": "CRITICAL",
                    "category": "schema_violation",
                    "detail": f"Schema violation at {path}: {err.message}"
                })
                score -= 10
    except ImportError:
        findings.append({
            "severity": "WARNING",
            "category": "schema_validation",
            "detail": "jsonschema not installed, schema validation skipped"
        })

    compliance = card.get("compliance", {})
    residency = compliance.get("data_residency")
    backend_loc = compliance.get("model_backend_location")
    cross_border = compliance.get("cross_border")

    if not residency:
        findings.append({"severity": "CRITICAL", "category": "data_residency", "detail": "Missing data_residency"})
        score -= 15
    if not backend_loc:
        findings.append({"severity": "CRITICAL", "category": "model_backend_location", "detail": "Missing model_backend_location"})
        score -= 15

    if residency and backend_loc and residency != backend_loc:
        if not cross_border:
            findings.append({
                "severity": "CRITICAL",
                "category": "cross_border_fraud",
                "detail": f"cross_border=false but data_residency={residency} != model_backend_location={backend_loc}"
            })
            score -= 25
        else:
            findings.append({
                "severity": "HIGH",
                "category": "cross_border_risk",
                "detail": f"Cross-border data flow: residency={residency}, backend={backend_loc}"
            })
            score -= 10

    endpoint = card.get("model_backend", {}).get("endpoint", "")
    if endpoint and residency:
        try:
            parsed = urlparse(endpoint)
            domain = parsed.netloc or endpoint.split("/")[0].split(":")[0]
            overseas = ["api.openai.com", "api.anthropic.com", "api.groq.com", "api.gemini.google.com"]
            if residency in ["CN", "EU", "SG"]:
                for od in overseas:
                    if domain.endswith(od) or domain == od:
                        findings.append({
                            "severity": "HIGH",
                            "category": "endpoint_mismatch",
                            "detail": f"Declared residency={residency}, but endpoint uses {domain} (US-based)"
                        })
                        score -= 15
                        break
        except Exception:
            pass

    capabilities = card.get("capabilities", [])
    if not capabilities:
        findings.append({"severity": "CRITICAL", "category": "no_capabilities", "detail": "No capabilities declared"})
        score -= 20

    today = time.strftime("%Y-%m-%d")
    for cap in capabilities:
        brv = cap.get("business_rule_version")
        if not brv:
            findings.append({
                "severity": "WARNING",
                "category": "prompt_rot",
                "detail": f"Skill '{cap.get('skill_id', '?')}' missing business_rule_version"
            })
            score -= 2
        else:
            try:
                brv_date = datetime.strptime(brv, "%Y-%m-%d")
                today_date = datetime.strptime(today, "%Y-%m-%d")
                age = (today_date - brv_date).days
                if age > 90:
                    findings.append({
                        "severity": "WARNING",
                        "category": "prompt_rot",
                        "detail": f"Skill '{cap.get('skill_id', '?')}' business_rule_version is {age} days old"
                    })
                    score -= 3
            except ValueError:
                findings.append({
                    "severity": "WARNING",
                    "category": "prompt_rot",
                    "detail": f"Skill '{cap.get('skill_id', '?')}' invalid business_rule_version format"
                })
                score -= 2

    score = max(0, min(100, score))
    return {
        "layer": 1,
        "name": "Static Audit",
        "score": round(score, 1),
        "grade": score_to_grade(score),
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "critical": len([f for f in findings if f["severity"] == "CRITICAL"]),
            "high": len([f for f in findings if f["severity"] == "HIGH"]),
            "warning": len([f for f in findings if f["severity"] == "WARNING"]),
            "capabilities_count": len(capabilities),
            "data_residency": residency,
            "cross_border": cross_border,
            "model_backend_location": backend_loc
        }
    }


def run_layer2_inference_metrics(card):
    findings = []
    score = 100.0

    model_backend = card.get("model_backend", {})
    model_name = model_backend.get("model", "")
    deployment = model_backend.get("deployment", "cloud")
    provider = model_backend.get("provider", "")

    model_key = None
    for key in MODEL_QUALITY_DB:
        if key in model_name:
            model_key = key
            break

    if model_key:
        mq = MODEL_QUALITY_DB[model_key]
        reasoning_score = mq["reasoning"] * 100
        coding_score = mq["coding"] * 100
        multilingual_score = mq["multilingual"] * 100
        tier = mq["tier"]

        findings.append({
            "severity": "INFO",
            "category": "model_quality",
            "detail": f"Model {model_name} (tier: {tier}) - reasoning: {reasoning_score:.0f}, coding: {coding_score:.0f}, multilingual: {multilingual_score:.0f}"
        })
    else:
        reasoning_score = 70
        coding_score = 70
        multilingual_score = 65
        tier = "unknown"
        findings.append({
            "severity": "WARNING",
            "category": "model_unknown",
            "detail": f"Model {model_name} not in quality DB, using default estimates"
        })
        score -= 10

    latency_info = DEPLOYMENT_LATENCY.get(deployment, DEPLOYMENT_LATENCY["cloud"])
    findings.append({
        "severity": "INFO",
        "category": "latency",
        "detail": f"Deployment: {deployment}, P50: {latency_info['p50_ms']}ms, P99: {latency_info['p99_ms']}ms, cold_start: {latency_info['cold_start_ms']}ms"
    })

    if deployment == "cloud":
        score -= 5
        findings.append({
            "severity": "WARNING",
            "category": "cloud_latency",
            "detail": "Cloud deployment adds network latency. Consider edge deployment for latency-sensitive tasks."
        })

    context_window = 0
    for key, window in CONTEXT_WINDOWS.items():
        if key in model_name:
            context_window = window
            break
    if not context_window:
        context_window = 32000

    findings.append({
        "severity": "INFO",
        "category": "context_window",
        "detail": f"Context window: {context_window:,} tokens"
    })

    if context_window < 64000:
        score -= 10
        findings.append({
            "severity": "HIGH",
            "category": "small_context",
            "detail": f"Context window {context_window:,} is below recommended 64K for coding agents"
        })

    capabilities = card.get("capabilities", [])
    total_rate_limits = 0
    for cap in capabilities:
        rl = cap.get("rate_limit", "")
        if rl:
            try:
                num = int(re.search(r'(\d+)', rl).group(1))
                total_rate_limits += num
            except (AttributeError, ValueError):
                pass

    avg_rate = total_rate_limits / max(len(capabilities), 1)
    if avg_rate < 15:
        score -= 5
        findings.append({
            "severity": "WARNING",
            "category": "low_rate_limit",
            "detail": f"Average rate limit {avg_rate:.0f}/min may be insufficient for complex multi-tool workflows"
        })

    inference_score = (reasoning_score * 0.4 + coding_score * 0.35 + multilingual_score * 0.25)
    score = score * 0.6 + inference_score * 0.4
    score = max(0, min(100, score))

    return {
        "layer": 2,
        "name": "Inference Metrics",
        "score": round(score, 1),
        "grade": score_to_grade(score),
        "findings": findings,
        "summary": {
            "model": model_name,
            "provider": provider,
            "tier": tier,
            "deployment": deployment,
            "reasoning_score": round(reasoning_score, 1),
            "coding_score": round(coding_score, 1),
            "multilingual_score": round(multilingual_score, 1),
            "context_window_tokens": context_window,
            "latency_p50_ms": latency_info["p50_ms"],
            "latency_p99_ms": latency_info["p99_ms"],
            "avg_rate_limit_per_min": round(avg_rate, 1)
        }
    }


def run_layer3_action_metrics(card, tasks=None):
    findings = []
    score = 100.0

    capabilities = card.get("capabilities", [])
    declared_tools = {cap["skill_id"] for cap in capabilities}

    expected_coding_tools = {
        "bash", "file_read", "file_edit", "file_write", "glob", "grep",
        "web_search", "web_fetch"
    }

    coverage = len(declared_tools & expected_coding_tools) / len(expected_coding_tools)
    missing_core = expected_coding_tools - declared_tools

    if missing_core:
        findings.append({
            "severity": "HIGH",
            "category": "missing_core_tools",
            "detail": f"Missing core coding tools: {', '.join(sorted(missing_core))}"
        })
        score -= len(missing_core) * 8

    advanced_tools = {"agent_tool", "mcp_tool", "lsp", "worktree", "cron", "bridge", "memory"}
    advanced_coverage = len(declared_tools & advanced_tools) / len(advanced_tools)
    findings.append({
        "severity": "INFO",
        "category": "tool_coverage",
        "detail": f"Core tool coverage: {coverage*100:.0f}%, Advanced tool coverage: {advanced_coverage*100:.0f}%, Total declared: {len(declared_tools)}"
    })

    schema_issues = 0
    for cap in capabilities:
        if not cap.get("input_schema"):
            findings.append({
                "severity": "WARNING",
                "category": "missing_input_schema",
                "detail": f"Skill '{cap['skill_id']}' missing input_schema"
            })
            schema_issues += 1
        if not cap.get("output_schema"):
            findings.append({
                "severity": "WARNING",
                "category": "missing_output_schema",
                "detail": f"Skill '{cap['skill_id']}' missing output_schema"
            })
            schema_issues += 1
    score -= schema_issues * 3

    total_complexity = 0
    for cap in capabilities:
        sid = cap["skill_id"]
        weight = TOOL_COMPLEXITY_WEIGHTS.get(sid, 0.3)
        total_complexity += weight

    max_possible_complexity = sum(TOOL_COMPLEXITY_WEIGHTS.values())
    complexity_ratio = total_complexity / max_possible_complexity
    findings.append({
        "severity": "INFO",
        "category": "capability_complexity",
        "detail": f"Capability complexity ratio: {complexity_ratio*100:.1f}% ({total_complexity:.1f}/{max_possible_complexity:.1f})"
    })

    if tasks:
        task_categories = tasks.get("task_categories", {})
        total_tasks = 0
        covered_tasks = 0
        uncovered_tasks = []

        for cat_name, task_list in task_categories.items():
            for task in task_list:
                total_tasks += 1
                expected = task.get("expected_tools", [])
                if all(t in declared_tools for t in expected):
                    covered_tasks += 1
                else:
                    missing = [t for t in expected if t not in declared_tools]
                    uncovered_tasks.append({
                        "task_id": task.get("id", "?"),
                        "missing_tools": missing
                    })

        task_coverage = covered_tasks / max(total_tasks, 1)
        findings.append({
            "severity": "INFO",
            "category": "task_coverage",
            "detail": f"Task coverage: {task_coverage*100:.0f}% ({covered_tasks}/{total_tasks})"
        })

        if uncovered_tasks:
            for ut in uncovered_tasks[:5]:
                findings.append({
                    "severity": "WARNING",
                    "category": "uncovered_task",
                    "detail": f"Task {ut['task_id']} needs tools not in card: {', '.join(ut['missing_tools'])}"
                })
            score -= len(uncovered_tasks) * 3
    else:
        task_coverage = coverage

    action_score = coverage * 40 + advanced_coverage * 30 + task_coverage * 30
    score = min(score, action_score)
    score = max(0, min(100, score))

    return {
        "layer": 3,
        "name": "Action Metrics",
        "score": round(score, 1),
        "grade": score_to_grade(score),
        "findings": findings,
        "summary": {
            "declared_tools_count": len(declared_tools),
            "core_tool_coverage": f"{coverage*100:.0f}%",
            "advanced_tool_coverage": f"{advanced_coverage*100:.0f}%",
            "capability_complexity_ratio": f"{complexity_ratio*100:.1f}%",
            "schema_completeness": f"{(1 - schema_issues/(len(capabilities)*2))*100:.0f}%" if capabilities else "0%",
            "task_coverage": f"{task_coverage*100:.0f}%" if tasks else "N/A"
        }
    }


def run_layer4_e2e_metrics(card, tasks=None):
    findings = []
    score = 100.0

    capabilities = card.get("capabilities", [])
    declared_tools = {cap["skill_id"] for cap in capabilities}

    e2e_scenarios = [
        {
            "name": "Code Search & Fix",
            "required_tools": ["grep", "file_read", "file_edit"],
            "description": "Search codebase, read files, apply fixes"
        },
        {
            "name": "New Feature Implementation",
            "required_tools": ["file_write", "file_edit", "bash", "glob"],
            "description": "Create new files, modify existing ones, run tests"
        },
        {
            "name": "Bug Investigation",
            "required_tools": ["bash", "grep", "file_read"],
            "description": "Run failing tests, search for errors, read relevant code"
        },
        {
            "name": "Code Review & Refactor",
            "required_tools": ["file_read", "file_edit", "grep"],
            "description": "Read code, identify patterns, apply refactoring"
        },
        {
            "name": "Documentation Generation",
            "required_tools": ["glob", "file_read", "file_write"],
            "description": "Scan project structure, read code, write docs"
        },
        {
            "name": "Web Research & Integration",
            "required_tools": ["web_search", "web_fetch", "file_edit"],
            "description": "Search web, fetch docs, integrate findings"
        },
        {
            "name": "Multi-file Refactoring",
            "required_tools": ["glob", "grep", "file_read", "file_edit"],
            "description": "Find all affected files, read context, apply changes"
        },
        {
            "name": "Test-Driven Development",
            "required_tools": ["file_write", "bash", "file_edit"],
            "description": "Write tests, run them, fix failures"
        },
    ]

    completed_scenarios = 0
    partial_scenarios = 0
    failed_scenarios = 0

    for scenario in e2e_scenarios:
        required = set(scenario["required_tools"])
        available = required & declared_tools
        missing = required - declared_tools

        if not missing:
            completed_scenarios += 1
            findings.append({
                "severity": "INFO",
                "category": "e2e_scenario",
                "detail": f"[PASS] {scenario['name']}: All tools available ({', '.join(sorted(required))})"
            })
        elif len(available) >= len(required) * 0.5:
            partial_scenarios += 1
            findings.append({
                "severity": "WARNING",
                "category": "e2e_scenario",
                "detail": f"[PARTIAL] {scenario['name']}: Missing {', '.join(sorted(missing))}"
            })
        else:
            failed_scenarios += 1
            findings.append({
                "severity": "HIGH",
                "category": "e2e_scenario",
                "detail": f"[FAIL] {scenario['name']}: Missing critical tools {', '.join(sorted(missing))}"
            })

    total = len(e2e_scenarios)
    e2e_rate = (completed_scenarios + partial_scenarios * 0.5) / total

    score = e2e_rate * 100
    score -= failed_scenarios * 10
    score = max(0, min(100, score))

    dependencies = card.get("dependencies", [])
    if dependencies:
        findings.append({
            "severity": "INFO",
            "category": "dependencies",
            "detail": f"Agent declares {len(dependencies)} dependencies: {', '.join(dependencies)}"
        })
    else:
        findings.append({
            "severity": "WARNING",
            "category": "no_dependencies",
            "detail": "No dependencies declared - runtime failures may be undetected"
        })
        score -= 5

    auth = card.get("authentication", {})
    auth_type = auth.get("type", "None")
    if auth_type == "None":
        findings.append({
            "severity": "HIGH",
            "category": "no_auth",
            "detail": "No authentication declared - security risk"
        })
        score -= 15
    elif auth_type in ["OAuth2", "mTLS"]:
        findings.append({
            "severity": "INFO",
            "category": "auth",
            "detail": f"Secure authentication: {auth_type}"
        })
    elif auth_type == "APIKey":
        findings.append({
            "severity": "WARNING",
            "category": "auth",
            "detail": "APIKey auth - ensure key rotation and secure storage"
        })

    return {
        "layer": 4,
        "name": "E2E Metrics",
        "score": round(score, 1),
        "grade": score_to_grade(score),
        "findings": findings,
        "summary": {
            "e2e_scenarios_total": total,
            "e2e_completed": completed_scenarios,
            "e2e_partial": partial_scenarios,
            "e2e_failed": failed_scenarios,
            "e2e_completion_rate": f"{e2e_rate*100:.0f}%",
            "dependencies_count": len(dependencies),
            "auth_type": auth_type
        }
    }


def run_layer5_mas_dimension(card, tasks=None):
    findings = []
    dimension_scores = {}

    capabilities = card.get("capabilities", [])
    declared_tools = {cap["skill_id"] for cap in capabilities}

    for dim_name, dim_spec in MAS_DIMENSIONS.items():
        required = set(dim_spec["required_tools"])
        available = required & declared_tools
        coverage = len(available) / len(required) if required else 1.0
        weight = dim_spec["weight"]

        dim_score = coverage * 100

        if coverage == 1.0:
            findings.append({
                "severity": "INFO",
                "category": f"mas_{dim_name}",
                "detail": f"[PASS] {dim_spec['description']} - All required tools present: {', '.join(sorted(required))}"
            })
        elif coverage > 0:
            missing = required - declared_tools
            findings.append({
                "severity": "WARNING",
                "category": f"mas_{dim_name}",
                "detail": f"[PARTIAL] {dim_spec['description']} - Missing: {', '.join(sorted(missing))}"
            })
            dim_score -= 20
        else:
            findings.append({
                "severity": "HIGH",
                "category": f"mas_{dim_name}",
                "detail": f"[FAIL] {dim_spec['description']} - No required tools available"
            })
            dim_score = 0

        dimension_scores[dim_name] = round(dim_score, 1)

    orch_hints = card.get("orchestration_hints", {})
    preferred_role = orch_hints.get("preferred_role", "worker")
    parallel_safe = orch_hints.get("parallel_safe", False)
    stateful = orch_hints.get("stateful", False)

    if preferred_role == "supervisor":
        findings.append({
            "severity": "INFO",
            "category": "orchestration_role",
            "detail": "Agent declares supervisor role - suitable for multi-agent coordination"
        })
    elif preferred_role == "worker":
        findings.append({
            "severity": "WARNING",
            "category": "orchestration_role",
            "detail": "Agent declares worker role - limited coordination capability"
        })

    if parallel_safe:
        findings.append({
            "severity": "INFO",
            "category": "parallel_safety",
            "detail": "Agent is parallel-safe - can run alongside other agents"
        })
    else:
        findings.append({
            "severity": "WARNING",
            "category": "parallel_safety",
            "detail": "Agent is NOT parallel-safe - may conflict with concurrent agents"
        })

    if stateful:
        findings.append({
            "severity": "INFO",
            "category": "statefulness",
            "detail": "Agent is stateful - maintains context across interactions"
        })
    else:
        findings.append({
            "severity": "WARNING",
            "category": "statefulness",
            "detail": "Agent is stateless - may lose context between interactions"
        })

    weighted_score = sum(
        dimension_scores[dim] * MAS_DIMENSIONS[dim]["weight"]
        for dim in MAS_DIMENSIONS
    )

    if preferred_role == "supervisor":
        weighted_score = min(100, weighted_score * 1.05)
    if not parallel_safe:
        weighted_score *= 0.9
    if not stateful:
        weighted_score *= 0.95

    weighted_score = max(0, min(100, weighted_score))

    return {
        "layer": 5,
        "name": "MAS Dimension",
        "score": round(weighted_score, 1),
        "grade": score_to_grade(weighted_score),
        "findings": findings,
        "summary": {
            "dimension_scores": dimension_scores,
            "preferred_role": preferred_role,
            "parallel_safe": parallel_safe,
            "stateful": stateful,
            "mas_readiness": "READY" if weighted_score >= 70 else "PARTIAL" if weighted_score >= 40 else "NOT_READY"
        }
    }


def score_to_grade(score):
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def grade_to_emoji(grade):
    return {"A": "🟢", "B": "🟢", "C": "🟡", "D": "🟠", "F": "🔴"}.get(grade, "⚪")


def compute_overall_score(layers):
    weights = {1: 0.15, 2: 0.20, 3: 0.25, 4: 0.25, 5: 0.15}
    total = sum(l["score"] * weights[l["layer"]] for l in layers)
    return round(total, 1)


def generate_report(card, layers, tasks=None, source_dir=None):
    overall = compute_overall_score(layers)
    overall_grade = score_to_grade(overall)

    critical_count = sum(len([f for f in l["findings"] if f["severity"] == "CRITICAL"]) for l in layers)
    high_count = sum(len([f for f in l["findings"] if f["severity"] == "HIGH"]) for l in layers)
    warning_count = sum(len([f for f in l["findings"] if f["severity"] == "WARNING"]) for l in layers)
    info_count = sum(len([f for f in l["findings"] if f["severity"] == "INFO"]) for l in layers)

    report = {
        "standard": "MAS-TS-001",
        "version": "v2.1",
        "mode": "full-run",
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "target_agent": {
            "agent_id": card.get("agent_id", "unknown"),
            "name": card.get("name", "unknown"),
            "version": card.get("version", "unknown"),
            "source_dir": str(source_dir) if source_dir else None
        },
        "overall": {
            "score": overall,
            "grade": overall_grade,
            "emoji": grade_to_emoji(overall_grade),
            "verdict": "APPROVED" if overall >= 70 and critical_count == 0 else
                       "CONDITIONAL" if overall >= 50 else "BLOCKED"
        },
        "layers": layers,
        "findings_summary": {
            "critical": critical_count,
            "high": high_count,
            "warning": warning_count,
            "info": info_count,
            "total": critical_count + high_count + warning_count + info_count
        },
        "recommendations": generate_recommendations(layers, card)
    }

    return report


def generate_recommendations(layers, card):
    recs = []

    for layer in layers:
        for finding in layer["findings"]:
            if finding["severity"] == "CRITICAL":
                recs.append({
                    "priority": "P0",
                    "layer": layer["layer"],
                    "category": finding["category"],
                    "recommendation": f"FIX IMMEDIATELY: {finding['detail']}"
                })
            elif finding["severity"] == "HIGH":
                recs.append({
                    "priority": "P1",
                    "layer": layer["layer"],
                    "category": finding["category"],
                    "recommendation": f"Address before production: {finding['detail']}"
                })

    compliance = card.get("compliance", {})
    if compliance.get("cross_border"):
        recs.append({
            "priority": "P1",
            "layer": 1,
            "category": "cross_border",
            "recommendation": "Implement data residency proxy or deploy regional model backend for CN deployment"
        })

    orch = card.get("orchestration_hints", {})
    if not orch.get("parallel_safe"):
        recs.append({
            "priority": "P2",
            "layer": 5,
            "category": "parallel_safety",
            "recommendation": "Add concurrency controls and state isolation to enable parallel agent execution"
        })

    return recs


def print_report(report):
    print("\n" + "=" * 70)
    print("  MAS-TS-001 Full Evaluation Report")
    print("=" * 70)
    print(f"  Standard:    {report['standard']} {report['version']}")
    print(f"  Mode:        {report['mode']}")
    print(f"  Agent:       {report['target_agent']['name']} ({report['target_agent']['agent_id']})")
    print(f"  Version:     {report['target_agent']['version']}")
    print(f"  Evaluated:   {report['evaluated_at']}")
    print("-" * 70)

    overall = report["overall"]
    print(f"\n  Overall Score:  {overall['score']}/100  {overall['emoji']} Grade {overall['grade']}")
    print(f"  Verdict:        {overall['verdict']}")

    print("\n  Layer Scores:")
    print("  " + "-" * 50)
    for layer in report["layers"]:
        emoji = grade_to_emoji(layer["grade"])
        print(f"  {emoji} Layer {layer['layer']}: {layer['name']:<25} {layer['score']:>5.1f}/100  Grade {layer['grade']}")

    print("\n  Findings Summary:")
    print("  " + "-" * 50)
    fs = report["findings_summary"]
    print(f"  CRITICAL: {fs['critical']}  |  HIGH: {fs['high']}  |  WARNING: {fs['warning']}  |  INFO: {fs['info']}")

    if report["recommendations"]:
        print("\n  Top Recommendations:")
        print("  " + "-" * 50)
        for rec in report["recommendations"][:8]:
            print(f"  [{rec['priority']}] L{rec['layer']} {rec['category']}: {rec['recommendation'][:80]}")

    print("\n" + "=" * 70)

    if overall["verdict"] == "BLOCKED":
        print("  BLOCKED: Agent does not meet minimum requirements for deployment.")
    elif overall["verdict"] == "CONDITIONAL":
        print("  CONDITIONAL: Agent passes with conditions. Address P0/P1 items.")
    else:
        print("  APPROVED: Agent meets MAS-TS-001 requirements.")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="MAS-TS-001 Full-Run Evaluation Pipeline (Layer 1-5)")
    parser.add_argument("--version", action="version", version=f"mas-eval-harness {VERSION}")
    parser.add_argument("--card", required=True, help="Agent Card JSON path")
    parser.add_argument("--tasks", help="Task definitions JSON path")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Agent Card JSON Schema path")
    parser.add_argument("--source-dir", help="Agent source code directory for deeper analysis")
    parser.add_argument("--output", help="Save report to JSON file")
    parser.add_argument("--block", action="store_true", help="Exit with error code if verdict is BLOCKED")
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    card = load_card(args.card)
    tasks = load_tasks(args.tasks)

    logger.info("Full-Run Evaluation starting for: %s", card.get('name', 'unknown'))
    logger.info("Agent ID: %s", card.get('agent_id', 'unknown'))

    layers = []

    logger.info("[Layer 1/5] Running Static Audit...")
    t0 = time.perf_counter()
    layer1 = run_layer1_static_audit(card, args.schema)
    layer1["duration_ms"] = int((time.perf_counter() - t0) * 1000)
    layers.append(layer1)
    logger.info("  -> Score: %s Grade: %s (%sms)", layer1['score'], layer1['grade'], layer1['duration_ms'])

    logger.info("[Layer 2/5] Running Inference Metrics...")
    t0 = time.perf_counter()
    layer2 = run_layer2_inference_metrics(card)
    layer2["duration_ms"] = int((time.perf_counter() - t0) * 1000)
    layers.append(layer2)
    logger.info("  -> Score: %s Grade: %s (%sms)", layer2['score'], layer2['grade'], layer2['duration_ms'])

    logger.info("[Layer 3/5] Running Action Metrics...")
    t0 = time.perf_counter()
    layer3 = run_layer3_action_metrics(card, tasks)
    layer3["duration_ms"] = int((time.perf_counter() - t0) * 1000)
    layers.append(layer3)
    logger.info("  -> Score: %s Grade: %s (%sms)", layer3['score'], layer3['grade'], layer3['duration_ms'])

    logger.info("[Layer 4/5] Running E2E Metrics...")
    t0 = time.perf_counter()
    layer4 = run_layer4_e2e_metrics(card, tasks)
    layer4["duration_ms"] = int((time.perf_counter() - t0) * 1000)
    layers.append(layer4)
    logger.info("  -> Score: %s Grade: %s (%sms)", layer4['score'], layer4['grade'], layer4['duration_ms'])

    logger.info("[Layer 5/5] Running MAS Dimension...")
    t0 = time.perf_counter()
    layer5 = run_layer5_mas_dimension(card, tasks)
    layer5["duration_ms"] = int((time.perf_counter() - t0) * 1000)
    layers.append(layer5)
    logger.info("  -> Score: %s Grade: %s (%sms)", layer5['score'], layer5['grade'], layer5['duration_ms'])

    report = generate_report(card, layers, tasks, args.source_dir)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info("Report saved to %s", args.output)

    print_report(report)

    if report["overall"]["verdict"] == "BLOCKED" and args.block:
        sys.exit(1)


if __name__ == "__main__":
    main()
