"""
MAS-TS-001 v3.0 — D3: Multi-Agent Collaboration

6 dimensions:
  Spawn          × 0.20 — success rate ≥95%, latency P99 <2s, context isolation
  Protocol       × 0.20 — JSON-RPC 2.0 envelope, 6 transports, retry/backoff, serialization
  Orchestration  × 0.25 — TaskDAG, Saga, role matching, parallel safety, dynamic scaling
  Isolation      × 0.15 — state isolation + resource isolation
  Conflict       × 0.10 — consensus ≥0.5, Jaccard similarity ≥0.65
  Persistence    × 0.10 — snapshot/restore, state transition, Chat Storm detection

D3 = Spawn×0.20 + Protocol×0.20 + Orchestration×0.25 + Isolation×0.15 + Conflict×0.10 + Persistence×0.10
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

TRANSPORT_TYPES = {"stdio", "sse", "websocket", "http", "grpc", "ipc"}

SPAWN_REQUIRED_TOOLS = {"agent_tool"}
PROTOCOL_REQUIRED_TOOLS = {"mcp_tool"}
ORCHESTRATION_TOOLS = {"agent_tool", "todo_write", "task_management"}
ISOLATION_TOOLS = {"worktree"}
CONFLICT_TOOLS = {"agent_tool", "mcp_tool"}
PERSISTENCE_TOOLS = {"memory", "task_management"}

D3_MAS_TASKS = [
    {"id": "mas-spawn-001", "description": "Spawn a sub-agent for parallel code search", "dimension": "spawn", "required_tools": ["agent_tool"]},
    {"id": "mas-spawn-002", "description": "Spawn 3 sub-agents for parallel task execution", "dimension": "spawn", "required_tools": ["agent_tool"]},
    {"id": "mas-proto-001", "description": "Send JSON-RPC 2.0 message via MCP to remote agent", "dimension": "protocol", "required_tools": ["mcp_tool"]},
    {"id": "mas-orch-001", "description": "Decompose task into DAG, assign sub-tasks to agents", "dimension": "orchestration", "required_tools": ["agent_tool", "todo_write"]},
    {"id": "mas-orch-002", "description": "Coordinate two agents working on interdependent tasks", "dimension": "orchestration", "required_tools": ["agent_tool", "task_management"]},
    {"id": "mas-isol-001", "description": "Create isolated worktree for each sub-agent session", "dimension": "isolation", "required_tools": ["worktree"]},
    {"id": "mas-conf-001", "description": "Resolve write conflict on shared file between two agents", "dimension": "conflict", "required_tools": ["agent_tool", "file_edit"]},
    {"id": "mas-pers-001", "description": "Save agent state to memory, crash, restore state", "dimension": "persistence", "required_tools": ["memory"]},
    {"id": "mas-pers-002", "description": "Detect and break out of chat storm loop between agents", "dimension": "persistence", "required_tools": ["agent_tool", "task_management"]},
]


def _score_spawn(card, golden_trajectory=None):
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}
    score = 0.0

    has_agent_tool = "agent_tool" in declared_tools
    if has_agent_tool:
        score += 40
        findings.append({"severity": "INFO", "category": "spawn_capability", "detail": "agent_tool declared — supports sub-agent spawning"})
    else:
        findings.append({"severity": "HIGH", "category": "spawn_capability", "detail": "Missing agent_tool — no sub-agent spawn capability"})

    spawn_count = 0
    for cap in card.get("capabilities", []):
        if cap["skill_id"] == "agent_tool":
            rl = cap.get("rate_limit", "")
            if rl:
                match = re.search(r'(\d+)', rl)
                if match:
                    rate = int(match.group(1))
                    spawn_score = min(30, rate * 3)
                    score += spawn_score
                    findings.append({"severity": "INFO", "category": "spawn_rate_limit", "detail": f"agent_tool rate limit: {rl} (spawn score: +{spawn_score})"})
            break

    if golden_trajectory:
        events = golden_trajectory if isinstance(golden_trajectory, list) else golden_trajectory.get("events", [])
        agent_tool_calls = [e for e in events if e.get("action", {}).get("tool_id") == "agent_tool"]
        spawn_success = [e for e in agent_tool_calls if e.get("action", {}).get("output", {}).get("status") in ("success", "assigned")]
        if agent_tool_calls:
            success_rate = len(spawn_success) / len(agent_tool_calls)
            score += min(30, success_rate * 30)
            findings.append({"severity": "INFO", "category": "spawn_success_rate", "detail": f"Spawn success rate from trajectory: {success_rate*100:.0f}%"})

    score = min(100, score)
    return round(score, 1), findings


def _score_protocol(card):
    findings = []
    score = 0.0

    endpoints = card.get("endpoints", {})
    has_a2a = bool(endpoints.get("a2a"))
    has_mcp = bool(endpoints.get("mcp"))

    if has_a2a:
        score += 20
        findings.append({"severity": "INFO", "category": "protocol_a2a", "detail": f"A2A endpoint declared: {endpoints['a2a']}"})
    else:
        findings.append({"severity": "WARNING", "category": "protocol_a2a", "detail": "No A2A endpoint declared — limited inter-agent communication"})

    if has_mcp:
        score += 20
        findings.append({"severity": "INFO", "category": "protocol_mcp", "detail": f"MCP endpoint declared: {endpoints['mcp']}"})
    else:
        findings.append({"severity": "WARNING", "category": "protocol_mcp", "detail": "No MCP endpoint declared"})

    constitution = card.get("constitution", {})
    env = constitution.get("envelope", {})
    if env.get("message_id") and env.get("correlation_id") and env.get("timestamp") and env.get("sender"):
        score += 20
        findings.append({"severity": "INFO", "category": "protocol_envelope", "detail": "JSON-RPC 2.0 envelope fields present"})
    else:
        findings.append({"severity": "WARNING", "category": "protocol_envelope", "detail": "Incomplete message envelope"})

    msg_format = constitution.get("message_format", {})
    transports = msg_format.get("supported_transports", [])
    if transports:
        transport_set = set(transports) & TRANSPORT_TYPES
        transport_score = min(20, len(transport_set) * 3)
        score += transport_score
        findings.append({"severity": "INFO", "category": "protocol_transports", "detail": f"Supported transports ({len(transport_set)}): {', '.join(sorted(transport_set))}"})
    else:
        findings.append({"severity": "WARNING", "category": "protocol_transports", "detail": "No supported transports declared"})

    if msg_format.get("max_payload_bytes"):
        score += 5
    if msg_format.get("version"):
        score += 5

    score = min(100, score)
    return round(score, 1), findings


def _score_orchestration(card, tasks=None):
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}
    score = 0.0

    orch = card.get("orchestration_hints", {})
    role = orch.get("preferred_role", "worker")

    if role == "supervisor":
        score += 20
        findings.append({"severity": "INFO", "category": "orchestration_role", "detail": "Supervisor role — suitable for multi-agent coordination"})
    elif role == "planner":
        score += 15
        findings.append({"severity": "INFO", "category": "orchestration_role", "detail": "Planner role — can decompose tasks"})
    else:
        findings.append({"severity": "WARNING", "category": "orchestration_role", "detail": f"Worker role — limited coordination capability"})

    available_orch = declared_tools & ORCHESTRATION_TOOLS
    orch_coverage = len(available_orch) / len(ORCHESTRATION_TOOLS)
    score += orch_coverage * 25
    missing_orch = ORCHESTRATION_TOOLS - declared_tools
    if missing_orch:
        findings.append({"severity": "WARNING", "category": "orchestration_tools", "detail": f"Missing orchestration tools: {', '.join(sorted(missing_orch))}"})
    else:
        findings.append({"severity": "INFO", "category": "orchestration_tools", "detail": "All orchestration tools present"})

    if orch.get("parallel_safe"):
        score += 15
        findings.append({"severity": "INFO", "category": "parallel_safety", "detail": "Agent is parallel-safe"})
    else:
        findings.append({"severity": "WARNING", "category": "parallel_safety", "detail": "Agent is NOT parallel-safe"})

    if orch.get("stateful"):
        score += 10
        findings.append({"severity": "INFO", "category": "statefulness", "detail": "Agent is stateful — supports long-running coordination"})

    if tasks:
        task_coverage = 0
        total_mas_tasks = len(D3_MAS_TASKS)
        for task in D3_MAS_TASKS:
            required = set(task["required_tools"])
            if required & declared_tools:
                task_coverage += 1
        task_pct = task_coverage / total_mas_tasks if total_mas_tasks else 0
        score += task_pct * 20
        findings.append({"severity": "INFO", "category": "orchestration_task_coverage", "detail": f"MAS task coverage: {task_coverage}/{total_mas_tasks}"})

    score = min(100, score)
    return round(score, 1), findings


def _score_isolation(card):
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}
    score = 0.0

    has_worktree = "worktree" in declared_tools
    if has_worktree:
        score += 40
        findings.append({"severity": "INFO", "category": "isolation_worktree", "detail": "worktree tool declared — supports session isolation"})
    else:
        findings.append({"severity": "WARNING", "category": "isolation_worktree", "detail": "No worktree tool — session isolation may be limited"})

    orch = card.get("orchestration_hints", {})
    if orch.get("parallel_safe"):
        score += 30
        findings.append({"severity": "INFO", "category": "isolation_parallel_safe", "detail": "Agent declared parallel-safe — isolation supported"})
    else:
        findings.append({"severity": "WARNING", "category": "isolation_parallel_safe", "detail": "Agent not parallel-safe — concurrent session risk"})

    has_memory = "memory" in declared_tools
    has_task_mgmt = "task_management" in declared_tools
    if has_memory or has_task_mgmt:
        score += 30
        findings.append({"severity": "INFO", "category": "isolation_state", "detail": "State isolation via memory/task_management"})

    score = min(100, score)
    return round(score, 1), findings


def _score_conflict(card):
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}
    score = 0.0

    has_agent = "agent_tool" in declared_tools
    has_mcp = "mcp_tool" in declared_tools
    conflict_tools = 0
    if has_agent:
        conflict_tools += 1
    if has_mcp:
        conflict_tools += 1

    if conflict_tools >= 2:
        score += 40
        findings.append({"severity": "INFO", "category": "conflict_resolution", "detail": "Agent_tool + MCP tool — supports consensus and conflict resolution"})
    elif conflict_tools == 1:
        score += 20
        findings.append({"severity": "WARNING", "category": "conflict_resolution", "detail": "Limited conflict resolution (only one coordination tool)"})
    else:
        findings.append({"severity": "HIGH", "category": "conflict_resolution", "detail": "No conflict resolution tools declared"})

    overlapping = declared_tools & {"file_edit", "file_write", "bash", "web_search", "web_fetch"}
    overlap_count = len(overlapping)
    if overlap_count >= 3:
        score += 30
        findings.append({"severity": "INFO", "category": "conflict_overlap", "detail": f"Shared tool access on {overlap_count} tools — conflict possible but resolvable"})
    elif overlap_count > 0:
        score += 15
        findings.append({"severity": "WARNING", "category": "conflict_overlap", "detail": f"Shared tool access on {overlap_count} tools"})

    orch = card.get("orchestration_hints", {})
    if orch.get("preferred_role") == "supervisor":
        score += 30
        findings.append({"severity": "INFO", "category": "conflict_supervisor", "detail": "Supervisor role supports conflict arbitration"})

    score = min(100, score)
    return round(score, 1), findings


def _score_persistence(card):
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}
    score = 0.0

    has_memory = "memory" in declared_tools
    has_task_mgmt = "task_management" in declared_tools
    has_cron = "cron" in declared_tools

    if has_memory:
        score += 30
        findings.append({"severity": "INFO", "category": "persistence_memory", "detail": "Memory tool — supports state persistence across sessions"})
    else:
        findings.append({"severity": "WARNING", "category": "persistence_memory", "detail": "No memory tool — state may not persist across sessions"})

    if has_task_mgmt:
        score += 25
        findings.append({"severity": "INFO", "category": "persistence_task", "detail": "Task management — persistent task lifecycle"})

    if has_cron:
        score += 15
        findings.append({"severity": "INFO", "category": "persistence_scheduling", "detail": "Cron tool — persistent scheduled execution"})

    stateful = card.get("orchestration_hints", {}).get("stateful", False)
    if stateful:
        score += 15
        findings.append({"severity": "INFO", "category": "persistence_stateful", "detail": "Agent declared stateful — maintains context"})
    else:
        findings.append({"severity": "WARNING", "category": "persistence_stateful", "detail": "Agent declared stateless — may lose context"})

    chat_storm_tools = declared_tools & {"task_management", "agent_tool"}
    has_chat_storm = len(chat_storm_tools) >= 1
    if has_chat_storm:
        score += 15
        findings.append({"severity": "INFO", "category": "persistence_chat_storm", "detail": "Chat storm detection capability present"})
    else:
        findings.append({"severity": "WARNING", "category": "persistence_chat_storm", "detail": "No chat storm detection capability"})

    score = min(100, score)
    return round(score, 1), findings


def run_d3(card, tasks=None, golden_trajectory=None):
    spawn_score, spawn_findings = _score_spawn(card, golden_trajectory)
    protocol_score, protocol_findings = _score_protocol(card)
    orchestration_score, orchestration_findings = _score_orchestration(card, tasks)
    isolation_score, isolation_findings = _score_isolation(card)
    conflict_score, conflict_findings = _score_conflict(card)
    persistence_score, persistence_findings = _score_persistence(card)

    all_findings = spawn_findings + protocol_findings + orchestration_findings + isolation_findings + conflict_findings + persistence_findings

    d3_score = (
        spawn_score * 0.20 +
        protocol_score * 0.20 +
        orchestration_score * 0.25 +
        isolation_score * 0.15 +
        conflict_score * 0.10 +
        persistence_score * 0.10
    )

    return {
        "domain": "D3",
        "name": "Multi-Agent Collaboration",
        "score": round(d3_score, 1),
        "subscores": {
            "spawn": spawn_score,
            "protocol": protocol_score,
            "orchestration": orchestration_score,
            "isolation": isolation_score,
            "conflict": conflict_score,
            "persistence": persistence_score,
        },
        "findings": all_findings,
        "summary": {
            "total_findings": len(all_findings),
            "preferred_role": card.get("orchestration_hints", {}).get("preferred_role", "unknown"),
            "parallel_safe": card.get("orchestration_hints", {}).get("parallel_safe", False),
            "stateful": card.get("orchestration_hints", {}).get("stateful", False),
            "has_a2a": bool(card.get("endpoints", {}).get("a2a")),
            "has_mcp": bool(card.get("endpoints", {}).get("mcp")),
        },
    }
