# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""
MAS-TS-001 v3.0-GA — D2: Single-Agent Capability (Gold Standard)

7 subdomains:
  ModelQuality             × 0.20 — LLM quality DB lookup with weighted subscores
  ToolCoverage             × 0.15 — core=8 / advanced=7 tool taxonomy, schema completeness
  TaskCompletion           × 0.25 — trajectory comparison (sequence/set/param/route/output)
  E2EScenarios             × 0.20 — 8 predefined scenarios, each scored 0-100
  StepEfficiency           × 0.10 — expected_steps / actual_steps, redundancy, revisitation
  TrajectoryQuality        × 0.10 — semantic quality: optimality, coherence, determinism, recovery, transparency
  ToolSelectionCorrectness × 0.00 — selection accuracy, argument correctness (bonus domain)

D2 = ModelQuality×0.20 + ToolCoverage×0.15 + TaskCompletion×0.25
     + E2EScenarios×0.20 + StepEfficiency×0.10 + TrajectoryQuality×0.10
     + ToolSelectionCorrectness×0.00 (bonus — adds up to +5 to overall if ≥70)
"""

import logging
from difflib import SequenceMatcher
from typing import Any

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

MODEL_QUALITY_DB: dict[str, dict[str, Any]] = {
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

E2E_SCENARIOS: list[dict[str, Any]] = [
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


def _find_model_key(model_name: str) -> str | None:
    if not model_name:
        return None
    for key in MODEL_QUALITY_DB:
        if key in model_name:
            return key
    return None


def run_model_quality(card: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
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


def run_tool_coverage(
    card: dict[str, Any], core_tools: set[str] | None = None
) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    core_tools = core_tools or CORE_TOOLS
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}

    core_coverage = len(declared_tools & core_tools) / len(core_tools)
    missing_core = core_tools - declared_tools
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
            "detail": f"Core: {core_coverage * 100:.0f}% ({len(declared_tools & core_tools)}/{len(core_tools)}), Advanced: {advanced_coverage * 100:.0f}% ({len(declared_tools & ADVANCED_TOOLS)}/{len(ADVANCED_TOOLS)})",
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


def run_task_completion(
    card: dict[str, Any],
    golden_trajectory: list[Any] | dict[str, Any] | None = None,
    mock_trajectory: list[Any] | dict[str, Any] | None = None,
) -> tuple[float, list[dict[str, Any]]]:
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

    def extract_tool_signature(event: dict[str, Any]) -> str | None:
        if event.get("action", {}).get("type") != "tool_call":
            return None
        action = event["action"]
        params = sorted(action.get("input", {}).keys())
        return f"{action['tool_id']}:{','.join(params)}"

    def extract_routing_decision(event: dict[str, Any]) -> str | None:
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


def run_e2e_scenarios(card: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
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


# ═══════════════════════════════════════════════════════════════
# Gold Standard: Step Efficiency (v3.0-GA §4.2)
# ═══════════════════════════════════════════════════════════════


def run_step_efficiency(
    trajectory: list[Any] | dict[str, Any] | None = None,
    scenario_config: dict[str, Any] | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    """Evaluate step efficiency of a task execution trajectory.

    Gold Standard §4.2 — three sub-metrics:
      - Optimality Ratio:  expected_min_steps / actual_steps
      - Redundancy Ratio:  1 - unnecessary_steps / total_steps
      - Revisit Ratio:     revisited_tools / unique_tools

    Args:
        trajectory: List of events or dict with 'events' key.
        scenario_config: Dict with 'expected_steps' (str range like "3-5").

    Returns:
        Score 0.0-100.0, findings list.
    """
    findings = []
    if not trajectory or not scenario_config:
        findings.append(
            {
                "severity": "WARNING",
                "category": "step_efficiency_skipped",
                "detail": "Trajectory or scenario config not provided",
            }
        )
        return 0.0, findings

    expected_range = str(scenario_config.get("expected_steps", "1-999"))
    try:
        parts = expected_range.split("-")
        expected_min = int(parts[0])
        expected_max = int(parts[-1])
    except (ValueError, IndexError):
        expected_min, expected_max = 1, 999

    events = (
        trajectory if isinstance(trajectory, list) else trajectory.get("events", [])
    )
    actual_steps = len(events)
    tool_calls = [e for e in events if e.get("action", {}).get("type") == "tool_call"]
    tool_ids = [t.get("action", {}).get("tool_id", "") for t in tool_calls]
    unique_tools = set(tool_ids)

    optimal_target = max(expected_min, 1)
    optimality = optimal_target / max(actual_steps, 1) if actual_steps > 0 else 0.0
    optimality = min(1.0, optimality)

    unnecessary = sum(
        1 for i in range(1, len(tool_ids)) if tool_ids[i] == tool_ids[i - 1]
    )
    redundancy = 1.0 - (unnecessary / max(len(tool_ids), 1))

    revisited = len(tool_ids) - len(unique_tools)
    revisit = 1.0 - (revisited / max(len(tool_ids), 1))

    score = optimality * 40 + redundancy * 30 + revisit * 30
    score = max(0, min(100, score))

    findings.append(
        {
            "severity": "INFO",
            "category": "step_efficiency",
            "detail": (
                f"expected={expected_min}-{expected_max}, actual={actual_steps}, "
                f"optimality={optimality:.3f}, redundancy={redundancy:.3f}, "
                f"revisit={revisit:.3f}, score={score:.1f}"
            ),
        }
    )

    if optimality < 0.4:
        findings.append(
            {
                "severity": "WARNING",
                "category": "step_efficiency_poor",
                "detail": f"Optimality {optimality:.2f} < 0.4 — excessive steps",
            }
        )
    if revisit < 0.65:
        findings.append(
            {
                "severity": "WARNING",
                "category": "step_efficiency_high_revisit",
                "detail": f"Revisit {revisit:.2f} — possible retry loop",
            }
        )

    return round(score, 1), findings


# ═══════════════════════════════════════════════════════════════
# Gold Standard: Trajectory Quality (v3.0-GA §4.3)
# ═══════════════════════════════════════════════════════════════


def run_trajectory_quality(
    trajectory: list[Any] | dict[str, Any] | None = None,
    golden_trajectory: list[Any] | dict[str, Any] | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    """Evaluate semantic quality of execution trajectory.

    Gold Standard §4.3 — five dimensions:
      - Optimality:    edit distance vs expert trajectory (0.25)
      - Coherence:     adjacent tool call diversity (0.20)
      - Determinism:   N-run tool sequence consistency (0.20)
      - Recovery:      error-to-recovery rate (0.20)
      - Transparency:  reasoning present per step (0.15)

    Args:
        trajectory: Execution trajectory events.
        golden_trajectory: Optional golden/reference trajectory.

    Returns:
        Score 0.0-100.0, findings list.
    """
    findings = []
    if not trajectory:
        findings.append(
            {
                "severity": "WARNING",
                "category": "trajectory_quality_skipped",
                "detail": "No trajectory provided — TrajectoryQuality defaulted to 0",
            }
        )
        return 0.0, findings

    events = (
        trajectory if isinstance(trajectory, list) else trajectory.get("events", [])
    )
    dim_scores: dict[str, float] = {}

    golden_events: list[dict[str, Any]] = []
    if golden_trajectory:
        golden_events = (
            golden_trajectory
            if isinstance(golden_trajectory, list)
            else golden_trajectory.get("events", [])
        )

    if golden_events:
        golden_seq = [e.get("action", {}).get("tool_id", "") for e in golden_events]
        actual_seq = [
            e.get("action", {}).get("tool_id", "")
            for e in events
            if e.get("action", {}).get("type") == "tool_call"
        ]
        edit_dist = sum(1 for a, b in zip(golden_seq, actual_seq) if a != b) + abs(
            len(golden_seq) - len(actual_seq)
        )
        max_dist = max(len(golden_seq), len(actual_seq), 1)
        dim_scores["optimality"] = max(0, 1.0 - edit_dist / max_dist)
    else:
        dim_scores["optimality"] = 0.5

    tool_ids = [
        e.get("action", {}).get("tool_id", "")
        for e in events
        if e.get("action", {}).get("type") == "tool_call"
    ]
    if len(tool_ids) >= 2:
        switches = sum(
            1 for i in range(len(tool_ids) - 1) if tool_ids[i] != tool_ids[i + 1]
        )
        dim_scores["coherence"] = switches / max(len(tool_ids) - 1, 1)
    else:
        dim_scores["coherence"] = 1.0

    dim_scores["determinism"] = 0.5  # stub — needs multi-run data

    errors = [e for e in events if e.get("error") is not None]
    recoveries = [e for e in events if e.get("recovery") is not None]
    if errors:
        dim_scores["recovery"] = len(recoveries) / max(len(errors), 1)
    else:
        dim_scores["recovery"] = 1.0

    reasoning_steps = sum(
        1 for e in events if e.get("action", {}).get("reasoning") is not None
    )
    dim_scores["transparency"] = reasoning_steps / max(len(events), 1)

    weights = {
        "optimality": 0.25,
        "coherence": 0.20,
        "determinism": 0.20,
        "recovery": 0.20,
        "transparency": 0.15,
    }
    score = sum(dim_scores[d] * weights[d] for d in weights) * 100
    score = max(0, min(100, round(score, 1)))

    dim_details = ", ".join(f"{k}={v:.3f}" for k, v in sorted(dim_scores.items()))
    findings.append(
        {
            "severity": "INFO",
            "category": "trajectory_quality",
            "detail": f"TrajectoryQuality score={score:.1f} — {dim_details}",
        }
    )

    if golden_trajectory is None:
        findings.append(
            {
                "severity": "WARNING",
                "category": "trajectory_quality_determinism",
                "detail": "Determinism requires N>=5 runs — score is partial",
            }
        )

    return score, findings


# ═══════════════════════════════════════════════════════════════
# Gold Standard: Tool Selection Correctness (v3.0-GA §4.4)
# ═══════════════════════════════════════════════════════════════


def run_tool_selection_correctness(
    trajectory: list[Any] | dict[str, Any] | None = None,
    task_requirements: list[str] | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    """Evaluate whether the agent selected the correct tools for the task.

    Gold Standard §4.4:
      - Selection Accuracy:  correct_tool_choices / total_tool_choices
      - Argument Correctness: semantically_valid_params / total_params
      - Redundant Call Rate:  duplicate_tool_calls / unique_tool_calls

    Args:
        trajectory: Execution trajectory with tool calls.
        task_requirements: List of expected tool IDs for the task.

    Returns:
        Score 0.0-100.0, findings list.
    """
    findings: list[dict[str, Any]] = []
    if not trajectory:
        return 0.0, findings

    events: list[dict[str, Any]] = (
        trajectory if isinstance(trajectory, list) else trajectory.get("events", [])
    )
    tool_calls = [e for e in events if e.get("action", {}).get("type") == "tool_call"]

    if not tool_calls:
        return 0.0, findings

    tool_ids = [t.get("action", {}).get("tool_id", "") for t in tool_calls]
    unique_tools = set(tool_ids)

    if task_requirements:
        required_set = set(task_requirements)
        correct = len(unique_tools & required_set)
        total = len(unique_tools | required_set)
        selection_acc = correct / max(total, 1)
    else:
        selection_acc = 0.5

    total_params = 0
    valid_params = 0
    for tc in tool_calls:
        inp = tc.get("action", {}).get("input", {})
        if inp:
            total_params += 1
            if any(v is not None and v != "" for v in inp.values()):
                valid_params += 1
    arg_correctness = valid_params / max(total_params, 1) if total_params > 0 else 1.0

    duplicates = len(tool_ids) - len(unique_tools)
    redundant_rate = duplicates / max(len(tool_ids), 1)

    score = selection_acc * 40 + arg_correctness * 35 + (1 - redundant_rate) * 25
    score = max(0, min(100, round(score, 1)))

    findings.append(
        {
            "severity": "INFO",
            "category": "tool_selection_correctness",
            "detail": (
                f"selection_acc={selection_acc:.3f}, "
                f"arg_correctness={arg_correctness:.3f}, "
                f"redundant_rate={redundant_rate:.3f}, "
                f"score={score:.1f}"
            ),
        }
    )

    if selection_acc < 0.85 and task_requirements:
        findings.append(
            {
                "severity": "WARNING",
                "category": "tool_selection_poor",
                "detail": f"Selection accuracy {selection_acc:.2f} < 0.85",
            }
        )

    return score, findings


def run_d2(
    card: dict[str, Any],
    golden_trajectory: list[Any] | dict[str, Any] | None = None,
    mock_trajectory: list[Any] | dict[str, Any] | None = None,
    core_tools: set[str] | None = None,
    scenario_trajectories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    model_score, model_findings = run_model_quality(card)
    tool_score, tool_findings = run_tool_coverage(card, core_tools)
    task_score, task_findings = run_task_completion(
        card, golden_trajectory, mock_trajectory
    )
    e2e_score, e2e_findings = run_e2e_scenarios(card)

    step_score: float = 0.0
    step_findings: list[dict[str, Any]] = []
    traj_score: float = 0.0
    traj_findings: list[dict[str, Any]] = []
    tool_sel_score: float = 0.0
    tool_sel_findings: list[dict[str, Any]] = []

    if scenario_trajectories:
        step_scores = []
        for i, traj in enumerate(scenario_trajectories):
            config = E2E_SCENARIOS[i] if i < len(E2E_SCENARIOS) else None
            s, f = run_step_efficiency(traj.get("trajectory"), config)
            step_scores.append(s)
            step_findings.extend(f)
        step_score = sum(step_scores) / max(len(step_scores), 1) if step_scores else 0.0
        traj_score, traj_findings = run_trajectory_quality(
            scenario_trajectories[0].get("trajectory")
            if scenario_trajectories
            else None,
            golden_trajectory,
        )
        tool_sel_score, tool_sel_findings = (
            run_tool_selection_correctness(
                scenario_trajectories[0].get("trajectory"),
                E2E_SCENARIOS[0].get("required_tools"),
            )
            if scenario_trajectories
            else (0.0, [])
        )

    all_findings = (
        model_findings
        + tool_findings
        + task_findings
        + e2e_findings
        + step_findings
        + traj_findings
        + tool_sel_findings
    )

    d2_score = (
        model_score * 0.20
        + tool_score * 0.15
        + task_score * 0.25
        + e2e_score * 0.20
        + step_score * 0.10
        + traj_score * 0.10
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
            "step_efficiency": step_score,
            "trajectory_quality": traj_score,
            "tool_selection_correctness": tool_sel_score,
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
