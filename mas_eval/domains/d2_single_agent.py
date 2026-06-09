# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""
MAS-TS-001 v3.0 — D2: Single-Agent Capability

4 subdomains:
  ModelQuality   × 0.25  — LLM quality DB lookup with weighted subscores
  ToolCoverage   × 0.20  — core=8 / advanced=7 tool taxonomy, schema completeness
  TaskCompletion × 0.30  — trajectory comparison (sequence/set/param/route/output)
  E2EScenarios   × 0.25  — 8 predefined scenarios, each scored 0-100

D2 = ModelQuality×0.25 + ToolCoverage×0.20 + TaskCompletion×0.30 + E2EScenarios×0.25
"""

import logging
from difflib import SequenceMatcher

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
ADVANCED_TOOLS = {
    "agent_tool",
    "mcp_tool",
    "lsp",
    "worktree",
    "cron",
    "bridge",
    "memory",
}

MODEL_QUALITY_DB = {
    "claude-opus-4": {
        "reasoning": 95,
        "coding": 95,
        "multilingual": 90,
        "instruction": 92,
        "tier": "premium",
    },
    "claude-sonnet-4": {
        "reasoning": 88,
        "coding": 90,
        "multilingual": 85,
        "instruction": 88,
        "tier": "premium",
    },
    "claude-haiku-3.5": {
        "reasoning": 78,
        "coding": 80,
        "multilingual": 80,
        "instruction": 82,
        "tier": "fast",
    },
    "gpt-4o": {
        "reasoning": 85,
        "coding": 88,
        "multilingual": 90,
        "instruction": 85,
        "tier": "premium",
    },
    "gpt-4-turbo": {
        "reasoning": 80,
        "coding": 82,
        "multilingual": 85,
        "instruction": 80,
        "tier": "premium",
    },
    "deepseek-chat-v3": {
        "reasoning": 85,
        "coding": 85,
        "multilingual": 78,
        "instruction": 80,
        "tier": "value",
    },
    "qwen-max": {
        "reasoning": 82,
        "coding": 78,
        "multilingual": 88,
        "instruction": 82,
        "tier": "value",
    },
}

E2E_SCENARIOS = [
    {
        "name": "Code Search & Fix",
        "required_tools": ["grep", "file_read", "file_edit"],
        "expected_agents": 1,
        "expected_steps": "3-5",
    },
    {
        "name": "New Feature Implementation",
        "required_tools": ["file_read", "file_write", "glob", "grep"],
        "expected_agents": "1-2",
        "expected_steps": "8-15",
    },
    {
        "name": "Bug Investigation",
        "required_tools": ["grep", "file_read", "bash", "web_search"],
        "expected_agents": "1-2",
        "expected_steps": "5-10",
    },
    {
        "name": "Code Review & Refactor",
        "required_tools": ["file_read", "file_edit", "glob"],
        "expected_agents": 1,
        "expected_steps": "6-12",
    },
    {
        "name": "Documentation Generation",
        "required_tools": ["file_read", "file_write", "web_search"],
        "expected_agents": 1,
        "expected_steps": "4-8",
    },
    {
        "name": "Web Research & Integration",
        "required_tools": ["web_search", "web_fetch", "file_write"],
        "expected_agents": "1-2",
        "expected_steps": "6-12",
    },
    {
        "name": "Multi-file Refactoring",
        "required_tools": ["file_read", "file_edit", "glob", "grep"],
        "expected_agents": "1-2",
        "expected_steps": "8-20",
    },
    {
        "name": "Test-Driven Development",
        "required_tools": ["file_write", "file_read", "bash"],
        "expected_agents": 1,
        "expected_steps": "8-15",
    },
]


def _find_model_key(model_name):
    if not model_name:
        return None
    for key in MODEL_QUALITY_DB:
        if key in model_name:
            return key
    return None


def run_model_quality(card):
    findings = []
    model_backend = card.get("model_backend", {})
    model_name = model_backend.get("model", "")
    model_key = _find_model_key(model_name)

    if model_key:
        mq = MODEL_QUALITY_DB[model_key]
        composite = (
            mq["reasoning"] * 0.35
            + mq["coding"] * 0.30
            + mq["multilingual"] * 0.20
            + mq["instruction"] * 0.15
        )
        findings.append(
            {
                "severity": "INFO",
                "category": "model_quality",
                "detail": f"Model {model_name} ({mq['tier']}) — reasoning={mq['reasoning']}, coding={mq['coding']}, multilingual={mq['multilingual']}, instruction={mq['instruction']}, composite={composite:.1f}",
            }
        )
        return round(composite, 1), findings
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "model_unknown",
                "detail": f"Model {model_name} not in quality DB, using default (50)",
            }
        )
        return 50.0, findings


def run_tool_coverage(card):
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}

    core_coverage = len(declared_tools & CORE_TOOLS) / len(CORE_TOOLS)
    missing_core = CORE_TOOLS - declared_tools
    if missing_core:
        findings.append(
            {
                "severity": "WARNING",
                "category": "missing_core_tools",
                "detail": f"Missing core tools: {', '.join(sorted(missing_core))}",
            }
        )

    advanced_coverage = len(declared_tools & ADVANCED_TOOLS) / len(ADVANCED_TOOLS)
    findings.append(
        {
            "severity": "INFO",
            "category": "tool_coverage",
            "detail": f"Core: {core_coverage * 100:.0f}% ({len(declared_tools & CORE_TOOLS)}/{len(CORE_TOOLS)}), Advanced: {advanced_coverage * 100:.0f}% ({len(declared_tools & ADVANCED_TOOLS)}/{len(ADVANCED_TOOLS)})",
        }
    )

    capabilities = card.get("capabilities", [])
    schema_issues = 0
    for cap in capabilities:
        if "input_schema" not in cap or cap.get("input_schema") is None:
            schema_issues += 1
        if "output_schema" not in cap or cap.get("output_schema") is None:
            schema_issues += 1
    schema_pct = max(0, (1 - schema_issues / max(len(capabilities) * 2, 1)) * 100)
    if schema_issues:
        findings.append(
            {
                "severity": "WARNING",
                "category": "schema_incomplete",
                "detail": f"{schema_issues} schema fields missing ({schema_pct:.0f}% complete)",
            }
        )

    tool_score = core_coverage * 80 + advanced_coverage * 20
    schema_adjustment = (schema_pct / 100) * 20
    final_score = min(100, tool_score * 0.8 + schema_adjustment)

    return round(final_score, 1), findings


def run_task_completion(card, golden_trajectory=None, mock_trajectory=None):
    findings = []

    if not golden_trajectory or not mock_trajectory:
        findings.append(
            {
                "severity": "WARNING",
                "category": "task_completion_skipped",
                "detail": "Golden or mock trajectory not provided — TaskCompletion score defaulted to 0",
            }
        )
        return 0.0, findings

    def extract_tool_signature(event):
        if event.get("action", {}).get("type") != "tool_call":
            return None
        action = event["action"]
        params = sorted(action.get("input", {}).keys())
        return f"{action['tool_id']}:{','.join(params)}"

    def extract_routing_decision(event):
        orch = event.get("orchestration", {})
        return orch.get("routing_reason") if orch.get("routing_decision") else None

    golden_events = (
        golden_trajectory
        if isinstance(golden_trajectory, list)
        else golden_trajectory.get("events", [])
    )
    mock_events = (
        mock_trajectory
        if isinstance(mock_trajectory, list)
        else mock_trajectory.get("events", [])
    )

    golden_sigs = [
        extract_tool_signature(e) for e in golden_events if extract_tool_signature(e)
    ]
    mock_sigs = [
        extract_tool_signature(e) for e in mock_events if extract_tool_signature(e)
    ]

    if not golden_sigs:
        findings.append(
            {
                "severity": "WARNING",
                "category": "task_completion",
                "detail": "No tool calls in golden trajectory",
            }
        )
        return 0.0, findings

    seq_sim = SequenceMatcher(None, golden_sigs, mock_sigs).ratio()
    golden_set = set(golden_sigs)
    mock_set = set(mock_sigs)
    set_sim = (
        len(golden_set & mock_set) / len(golden_set | mock_set)
        if (golden_set | mock_set)
        else 1.0
    )
    param_match = sum(1 for g, m in zip(golden_sigs, mock_sigs) if g == m) / max(
        len(golden_sigs), 1
    )

    golden_routes = [
        extract_routing_decision(e)
        for e in golden_events
        if extract_routing_decision(e)
    ]
    mock_routes = [
        extract_routing_decision(e) for e in mock_events if extract_routing_decision(e)
    ]
    route_match = 0.0
    if golden_routes and mock_routes:
        min_len = min(len(golden_routes), len(mock_routes))
        route_match = (
            sum(
                1
                for g, m in zip(golden_routes[:min_len], mock_routes[:min_len])
                if g == m
            )
            / min_len
        )

    output_correctness = 1.0 if seq_sim >= 0.85 and set_sim >= 0.90 else seq_sim

    score = (
        seq_sim * 25
        + set_sim * 25
        + param_match * 20
        + route_match * 15
        + output_correctness * 15
    )
    score = max(0, min(100, score))

    findings.append(
        {
            "severity": "INFO",
            "category": "task_completion",
            "detail": f"seq_sim={seq_sim:.3f}, set_sim={set_sim:.3f}, param_match={param_match:.3f}, route_match={route_match:.3f}, score={score:.1f}",
        }
    )
    return round(score, 1), findings


def run_e2e_scenarios(card):
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}
    completed = 0
    partial = 0
    failed = 0
    scenario_scores = []

    for scenario in E2E_SCENARIOS:
        required = set(scenario["required_tools"])
        available = required & declared_tools
        missing = required - declared_tools

        if not missing:
            completed += 1
            scenario_score = 100
            findings.append(
                {
                    "severity": "INFO",
                    "category": "e2e_scenario",
                    "detail": f"[PASS] {scenario['name']}",
                }
            )
        elif len(available) >= len(required) * 0.5:
            partial += 1
            scenario_score = 50
            findings.append(
                {
                    "severity": "WARNING",
                    "category": "e2e_scenario",
                    "detail": f"[PARTIAL] {scenario['name']} — missing {', '.join(sorted(missing))}",
                }
            )
        else:
            failed += 1
            scenario_score = 0
            findings.append(
                {
                    "severity": "HIGH",
                    "category": "e2e_scenario",
                    "detail": f"[FAIL] {scenario['name']} — missing critical {', '.join(sorted(missing))}",
                }
            )
        scenario_scores.append(scenario_score)

    total = len(E2E_SCENARIOS)
    e2e_score = sum(scenario_scores) / total if total else 0
    findings.append(
        {
            "severity": "INFO",
            "category": "e2e_summary",
            "detail": f"E2E: {completed}/{total} completed, {partial} partial, {failed} failed — score={e2e_score:.1f}",
        }
    )
    return round(e2e_score, 1), findings


def run_d2(card, golden_trajectory=None, mock_trajectory=None):
    model_score, model_findings = run_model_quality(card)
    tool_score, tool_findings = run_tool_coverage(card)
    task_score, task_findings = run_task_completion(
        card, golden_trajectory, mock_trajectory
    )
    e2e_score, e2e_findings = run_e2e_scenarios(card)

    all_findings = model_findings + tool_findings + task_findings + e2e_findings

    d2_score = (
        model_score * 0.25 + tool_score * 0.20 + task_score * 0.30 + e2e_score * 0.25
    )

    return {
        "domain": "D2",
        "name": "Single-Agent Capability",
        "score": round(d2_score, 1),
        "subscores": {
            "model_quality": model_score,
            "tool_coverage": tool_score,
            "task_completion": task_score,
            "e2e_scenarios": e2e_score,
        },
        "findings": all_findings,
        "summary": {
            "total_findings": len(all_findings),
            "model_name": card.get("model_backend", {}).get("model", "unknown"),
            "declared_tools_count": len(
                {cap["skill_id"] for cap in card.get("capabilities", [])}
            ),
        },
    }
