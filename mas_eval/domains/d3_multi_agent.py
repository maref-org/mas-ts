# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
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
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)

TRANSPORT_TYPES = {"stdio", "sse", "websocket", "http", "grpc", "ipc"}

SPAWN_REQUIRED_TOOLS = {"agent_tool"}
PROTOCOL_REQUIRED_TOOLS = {"mcp_tool"}
ORCHESTRATION_TOOLS = {"agent_tool", "todo_write", "task_management"}
ISOLATION_TOOLS = {"worktree"}
CONFLICT_TOOLS = {"agent_tool", "mcp_tool"}
PERSISTENCE_TOOLS = {"memory", "task_management"}

D3_MAS_TASKS = [
    {
        "id": "mas-spawn-001",
        "description": "Spawn a sub-agent for parallel code search",
        "dimension": "spawn",
        "required_tools": ["agent_tool"],
    },
    {
        "id": "mas-spawn-002",
        "description": "Spawn 3 sub-agents for parallel task execution",
        "dimension": "spawn",
        "required_tools": ["agent_tool"],
    },
    {
        "id": "mas-proto-001",
        "description": "Send JSON-RPC 2.0 message via MCP to remote agent",
        "dimension": "protocol",
        "required_tools": ["mcp_tool"],
    },
    {
        "id": "mas-orch-001",
        "description": "Decompose task into DAG, assign sub-tasks to agents",
        "dimension": "orchestration",
        "required_tools": ["agent_tool", "todo_write"],
    },
    {
        "id": "mas-orch-002",
        "description": "Coordinate two agents working on interdependent tasks",
        "dimension": "orchestration",
        "required_tools": ["agent_tool", "task_management"],
    },
    {
        "id": "mas-isol-001",
        "description": "Create isolated worktree for each sub-agent session",
        "dimension": "isolation",
        "required_tools": ["worktree"],
    },
    {
        "id": "mas-conf-001",
        "description": "Resolve write conflict on shared file between two agents",
        "dimension": "conflict",
        "required_tools": ["agent_tool", "file_edit"],
    },
    {
        "id": "mas-pers-001",
        "description": "Save agent state to memory, crash, restore state",
        "dimension": "persistence",
        "required_tools": ["memory"],
    },
    {
        "id": "mas-pers-002",
        "description": "Detect and break out of chat storm loop between agents",
        "dimension": "persistence",
        "required_tools": ["agent_tool", "task_management"],
    },
]


def _score_spawn(
    card: dict[str, Any], golden_trajectory: list[Any] | dict[str, Any] | None = None
) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}
    score = 0.0

    has_agent_tool = "agent_tool" in declared_tools
    if has_agent_tool:
        score += 40
        findings.append(
            {
                "severity": "INFO",
                "category": "spawn_capability",
                "detail": "agent_tool declared — supports sub-agent spawning",
            }
        )
    else:
        findings.append(
            {
                "severity": "HIGH",
                "category": "spawn_capability",
                "detail": "Missing agent_tool — no sub-agent spawn capability",
            }
        )

    for cap in card.get("capabilities", []):
        if cap["skill_id"] == "agent_tool":
            rl = cap.get("rate_limit", "")
            if rl:
                match = re.search(r"(\d+)", rl)
                if match:
                    rate = int(match.group(1))
                    spawn_score = min(30, rate * 3)
                    score += spawn_score
                    findings.append(
                        {
                            "severity": "INFO",
                            "category": "spawn_rate_limit",
                            "detail": f"agent_tool rate limit: {rl} (spawn score: +{spawn_score})",
                        }
                    )
            break

    if golden_trajectory:
        events = (
            golden_trajectory
            if isinstance(golden_trajectory, list)
            else golden_trajectory.get("events", [])
        )
        agent_tool_calls = [
            e for e in events if e.get("action", {}).get("tool_id") == "agent_tool"
        ]
        spawn_success = [
            e
            for e in agent_tool_calls
            if e.get("action", {}).get("output", {}).get("status")
            in ("success", "assigned")
        ]
        if agent_tool_calls:
            success_rate = len(spawn_success) / len(agent_tool_calls)
            score += min(30, success_rate * 30)
            findings.append(
                {
                    "severity": "INFO",
                    "category": "spawn_success_rate",
                    "detail": f"Spawn success rate from trajectory: {success_rate * 100:.0f}%",
                }
            )

    score = min(100, score)
    return round(score, 1), findings


def _score_protocol(card: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    score = 0.0

    endpoints = card.get("endpoints", {})
    has_a2a = bool(endpoints.get("a2a"))
    has_mcp = bool(endpoints.get("mcp"))

    if has_a2a:
        score += 20
        findings.append(
            {
                "severity": "INFO",
                "category": "protocol_a2a",
                "detail": f"A2A endpoint declared: {endpoints['a2a']}",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "protocol_a2a",
                "detail": "No A2A endpoint declared — limited inter-agent communication",
            }
        )

    if has_mcp:
        score += 20
        findings.append(
            {
                "severity": "INFO",
                "category": "protocol_mcp",
                "detail": f"MCP endpoint declared: {endpoints['mcp']}",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "protocol_mcp",
                "detail": "No MCP endpoint declared",
            }
        )

    constitution = card.get("constitution", {})
    env = constitution.get("envelope", {})
    if (
        env.get("message_id")
        and env.get("correlation_id")
        and env.get("timestamp")
        and env.get("sender")
    ):
        score += 20
        findings.append(
            {
                "severity": "INFO",
                "category": "protocol_envelope",
                "detail": "JSON-RPC 2.0 envelope fields present",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "protocol_envelope",
                "detail": "Incomplete message envelope",
            }
        )

    msg_format = constitution.get("message_format", {})
    transports = msg_format.get("supported_transports", [])
    if transports:
        transport_set = set(transports) & TRANSPORT_TYPES
        transport_score = min(20, len(transport_set) * 3)
        score += transport_score
        findings.append(
            {
                "severity": "INFO",
                "category": "protocol_transports",
                "detail": f"Supported transports ({len(transport_set)}): {', '.join(sorted(transport_set))}",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "protocol_transports",
                "detail": "No supported transports declared",
            }
        )

    if msg_format.get("max_payload_bytes"):
        score += 5
    if msg_format.get("version"):
        score += 5

    score = min(100, score)
    return round(score, 1), findings


def _score_orchestration(
    card: dict[str, Any], tasks: list[dict[str, Any]] | None = None
) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}
    score = 0.0

    orch = card.get("orchestration_hints", {})
    role = orch.get("preferred_role", "worker")

    if role == "supervisor":
        score += 20
        findings.append(
            {
                "severity": "INFO",
                "category": "orchestration_role",
                "detail": "Supervisor role — suitable for multi-agent coordination",
            }
        )
    elif role == "planner":
        score += 15
        findings.append(
            {
                "severity": "INFO",
                "category": "orchestration_role",
                "detail": "Planner role — can decompose tasks",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "orchestration_role",
                "detail": "Worker role — limited coordination capability",
            }
        )

    available_orch = declared_tools & ORCHESTRATION_TOOLS
    orch_coverage = len(available_orch) / len(ORCHESTRATION_TOOLS)
    score += orch_coverage * 25
    missing_orch = ORCHESTRATION_TOOLS - declared_tools
    if missing_orch:
        findings.append(
            {
                "severity": "WARNING",
                "category": "orchestration_tools",
                "detail": f"Missing orchestration tools: {', '.join(sorted(missing_orch))}",
            }
        )
    else:
        findings.append(
            {
                "severity": "INFO",
                "category": "orchestration_tools",
                "detail": "All orchestration tools present",
            }
        )

    if orch.get("parallel_safe"):
        score += 15
        findings.append(
            {
                "severity": "INFO",
                "category": "parallel_safety",
                "detail": "Agent is parallel-safe",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "parallel_safety",
                "detail": "Agent is NOT parallel-safe",
            }
        )

    if orch.get("stateful"):
        score += 10
        findings.append(
            {
                "severity": "INFO",
                "category": "statefulness",
                "detail": "Agent is stateful — supports long-running coordination",
            }
        )

    if tasks:
        task_coverage = 0
        total_mas_tasks = len(D3_MAS_TASKS)
        for task in D3_MAS_TASKS:
            required = set(task["required_tools"])
            if required & declared_tools:
                task_coverage += 1
        task_pct = task_coverage / total_mas_tasks if total_mas_tasks else 0
        score += task_pct * 20
        findings.append(
            {
                "severity": "INFO",
                "category": "orchestration_task_coverage",
                "detail": f"MAS task coverage: {task_coverage}/{total_mas_tasks}",
            }
        )

    score = min(100, score)
    return round(score, 1), findings


def _score_isolation(card: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}
    score = 0.0

    has_worktree = "worktree" in declared_tools
    if has_worktree:
        score += 40
        findings.append(
            {
                "severity": "INFO",
                "category": "isolation_worktree",
                "detail": "worktree tool declared — supports session isolation",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "isolation_worktree",
                "detail": "No worktree tool — session isolation may be limited",
            }
        )

    orch = card.get("orchestration_hints", {})
    if orch.get("parallel_safe"):
        score += 30
        findings.append(
            {
                "severity": "INFO",
                "category": "isolation_parallel_safe",
                "detail": "Agent declared parallel-safe — isolation supported",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "isolation_parallel_safe",
                "detail": "Agent not parallel-safe — concurrent session risk",
            }
        )

    has_memory = "memory" in declared_tools
    has_task_mgmt = "task_management" in declared_tools
    if has_memory or has_task_mgmt:
        score += 30
        findings.append(
            {
                "severity": "INFO",
                "category": "isolation_state",
                "detail": "State isolation via memory/task_management",
            }
        )

    score = min(100, score)
    return round(score, 1), findings


def _score_conflict(card: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
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
        findings.append(
            {
                "severity": "INFO",
                "category": "conflict_resolution",
                "detail": "Agent_tool + MCP tool — supports consensus and conflict resolution",
            }
        )
    elif conflict_tools == 1:
        score += 20
        findings.append(
            {
                "severity": "WARNING",
                "category": "conflict_resolution",
                "detail": "Limited conflict resolution (only one coordination tool)",
            }
        )
    else:
        findings.append(
            {
                "severity": "HIGH",
                "category": "conflict_resolution",
                "detail": "No conflict resolution tools declared",
            }
        )

    overlapping = declared_tools & {
        "file_edit",
        "file_write",
        "bash",
        "web_search",
        "web_fetch",
    }
    overlap_count = len(overlapping)
    if overlap_count >= 3:
        score += 30
        findings.append(
            {
                "severity": "INFO",
                "category": "conflict_overlap",
                "detail": f"Shared tool access on {overlap_count} tools — conflict possible but resolvable",
            }
        )
    elif overlap_count > 0:
        score += 15
        findings.append(
            {
                "severity": "WARNING",
                "category": "conflict_overlap",
                "detail": f"Shared tool access on {overlap_count} tools",
            }
        )

    orch = card.get("orchestration_hints", {})
    if orch.get("preferred_role") == "supervisor":
        score += 30
        findings.append(
            {
                "severity": "INFO",
                "category": "conflict_supervisor",
                "detail": "Supervisor role supports conflict arbitration",
            }
        )

    score = min(100, score)
    return round(score, 1), findings


def _score_persistence(card: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}
    score = 0.0

    has_memory = "memory" in declared_tools
    has_task_mgmt = "task_management" in declared_tools
    has_cron = "cron" in declared_tools

    if has_memory:
        score += 30
        findings.append(
            {
                "severity": "INFO",
                "category": "persistence_memory",
                "detail": "Memory tool — supports state persistence across sessions",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "persistence_memory",
                "detail": "No memory tool — state may not persist across sessions",
            }
        )

    if has_task_mgmt:
        score += 25
        findings.append(
            {
                "severity": "INFO",
                "category": "persistence_task",
                "detail": "Task management — persistent task lifecycle",
            }
        )

    if has_cron:
        score += 15
        findings.append(
            {
                "severity": "INFO",
                "category": "persistence_scheduling",
                "detail": "Cron tool — persistent scheduled execution",
            }
        )

    stateful = card.get("orchestration_hints", {}).get("stateful", False)
    if stateful:
        score += 15
        findings.append(
            {
                "severity": "INFO",
                "category": "persistence_stateful",
                "detail": "Agent declared stateful — maintains context",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "persistence_stateful",
                "detail": "Agent declared stateless — may lose context",
            }
        )

    chat_storm_tools = declared_tools & {"task_management", "agent_tool"}
    has_chat_storm = len(chat_storm_tools) >= 1
    if has_chat_storm:
        score += 15
        findings.append(
            {
                "severity": "INFO",
                "category": "persistence_chat_storm",
                "detail": "Chat storm detection capability present",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "persistence_chat_storm",
                "detail": "No chat storm detection capability",
            }
        )

    score = min(100, score)
    return round(score, 1), findings


def _is_federation_card(card: dict[str, Any]) -> bool:
    return card.get("federation") is not None


def check_federation_compatibility(
    card: dict[str, Any],
) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    fed = card.get("federation") or {}
    protocols = fed.get("federation_protocols") or {}

    if not protocols:
        findings.append(
            {
                "severity": "INFO",
                "category": "federation_compat",
                "detail": "No federation protocols declared — compatibility not assessed",
            }
        )
        return 0, findings

    score = 0.0
    any_enabled = False

    mcp = protocols.get("mcp") or {}
    a2a = protocols.get("a2a") or {}

    if mcp.get("enabled") and mcp.get("version", ""):
        any_enabled = True
        mcp_ver = mcp["version"]
        if mcp_ver >= "2024-10-01":
            score += 5
            findings.append(
                {
                    "severity": "INFO",
                    "category": "federation_compat",
                    "detail": f"MCP v{mcp_ver} compatible with federation topology",
                }
            )
        else:
            findings.append(
                {
                    "severity": "WARNING",
                    "category": "federation_compat",
                    "detail": f"MCP v{mcp_ver} outdated — federation topology risk",
                }
            )

    if a2a.get("enabled") and a2a.get("version", ""):
        any_enabled = True
        a2a_ver = a2a["version"]
        if a2a_ver >= "0.3":
            score += 5
            findings.append(
                {
                    "severity": "INFO",
                    "category": "federation_compat",
                    "detail": f"A2A v{a2a_ver} compatible with federation topology",
                }
            )
        else:
            findings.append(
                {
                    "severity": "WARNING",
                    "category": "federation_compat",
                    "detail": f"A2A v{a2a_ver} outdated — federation topology risk",
                }
            )

    if any_enabled and not findings:
        findings.append(
            {
                "severity": "INFO",
                "category": "federation_compat",
                "detail": "Federation protocol topology is compatible",
            }
        )

    if not any_enabled:
        findings.append(
            {
                "severity": "INFO",
                "category": "federation_compat",
                "detail": "No federation protocols enabled — compatibility not assessed",
            }
        )

    return round(score, 1), findings


MCP_VERSIONS = {"2025-03-26", "2024-11-05", "2024-10-01"}
A2A_VERSIONS = {"1.0", "0.3"}


def _pair_mcp_compat(a_fed: dict[str, Any], b_fed: dict[str, Any]) -> int:
    a_mcp = (a_fed.get("federation_protocols") or {}).get("mcp") or {}
    b_mcp = (b_fed.get("federation_protocols") or {}).get("mcp") or {}
    a_ver = a_mcp.get("version", "")
    b_ver = b_mcp.get("version", "")
    a_enabled = a_mcp.get("enabled", False)
    b_enabled = b_mcp.get("enabled", False)
    if not a_enabled or not b_enabled:
        return 0
    if a_ver in MCP_VERSIONS and b_ver in MCP_VERSIONS:
        return 20
    if a_ver == b_ver:
        return 20
    return 10


def _pair_a2a_compat(a_fed: dict[str, Any], b_fed: dict[str, Any]) -> int:
    a_a2a = (a_fed.get("federation_protocols") or {}).get("a2a") or {}
    b_a2a = (b_fed.get("federation_protocols") or {}).get("a2a") or {}
    a_ver = a_a2a.get("version", "")
    b_ver = b_a2a.get("version", "")
    a_enabled = a_a2a.get("enabled", False)
    b_enabled = b_a2a.get("enabled", False)
    if not a_enabled or not b_enabled:
        return 0
    if a_ver in A2A_VERSIONS and b_ver in A2A_VERSIONS:
        return 20
    if a_ver == b_ver:
        return 20
    return 10


def _pair_schema_compat(a_card: dict[str, Any], b_card: dict[str, Any]) -> int:
    a_ver = a_card.get("schema_version", a_card.get("card_version", "1.2"))
    b_ver = b_card.get("schema_version", b_card.get("card_version", "1.2"))
    return 15 if a_ver == b_ver else 5


def _pair_auth_compat(a_card: dict[str, Any], b_card: dict[str, Any]) -> int:
    a_auth = a_card.get("authentication", {}).get("type", "None")
    b_auth = b_card.get("authentication", {}).get("type", "None")
    secure = {"mTLS", "OAuth2"}
    if a_auth in secure and b_auth in secure:
        return 15
    if a_auth == b_auth:
        return 10
    return 5


def _pair_cross_border_compat(a_card: dict[str, Any], b_card: dict[str, Any]) -> int:
    a_fed = a_card.get("federation") or {}
    b_fed = b_card.get("federation") or {}
    a_policy = a_fed.get("cross_border_policy") or {}
    b_policy = b_fed.get("cross_border_policy") or {}
    a_zones = set(a_policy.get("allowed_transfer_zones") or [])
    b_zones = set(b_policy.get("allowed_transfer_zones") or [])
    if not a_zones or not b_zones:
        return 5
    overlap = a_zones & b_zones
    if overlap:
        return 10
    return 0


def _trust_score_value(value: Any) -> float:
    if isinstance(value, dict):
        raw = value.get("value", 0.5)
    else:
        raw = value
    if isinstance(raw, int | float):
        return float(raw)
    return 0.5


def _pair_trust_compat(a_card: dict[str, Any], b_card: dict[str, Any]) -> int:
    a_trust = _trust_score_value(
        (a_card.get("federation") or {}).get("trust_score", 0.5)
    )
    b_trust = _trust_score_value(
        (b_card.get("federation") or {}).get("trust_score", 0.5)
    )
    delta = abs(a_trust - b_trust)
    if delta <= 0.1:
        return 10
    if delta <= 0.3:
        return 5
    return 0


def _pair_role_compat(a_card: dict[str, Any], b_card: dict[str, Any]) -> int:
    a_role = (a_card.get("federation") or {}).get("role", "")
    b_role = (b_card.get("federation") or {}).get("role", "")
    if not a_role or not b_role:
        return 5
    conflict_pairs = {("primary", "primary"), ("secondary", "")}
    pair = (a_role, b_role)
    if pair in conflict_pairs or (pair[1], pair[0]) in conflict_pairs:
        return 0
    return 10


COMPAT_DIMS = [
    ("mcp_version", _pair_mcp_compat, 20),
    ("a2a_version", _pair_a2a_compat, 20),
    ("schema_version", _pair_schema_compat, 15),
    ("auth_type", _pair_auth_compat, 15),
    ("cross_border", _pair_cross_border_compat, 10),
    ("trust_delta", _pair_trust_compat, 10),
    ("role", _pair_role_compat, 10),
]


def check_federation_compatibility_matrix(
    cards: list[dict[str, Any]],
) -> tuple[float, list[Any], list[dict[str, Any]]]:
    findings = []
    n = len(cards)
    if n < 2:
        return (
            100.0,
            [],
            [
                {
                    "severity": "INFO",
                    "category": "fed_matrix",
                    "detail": "Less than 2 agents — compatibility matrix not built",
                }
            ],
        )

    matrix = [[0.0] * n for _ in range(n)]
    pair_scores = []
    incompatible_pairs = []

    for i in range(n):
        matrix[i][i] = 100.0
        for j in range(i + 1, n):
            a_card, b_card = cards[i], cards[j]
            a_name = a_card.get("name", a_card.get("agent_id", f"agent_{i}"))
            b_name = b_card.get("name", b_card.get("agent_id", f"agent_{j}"))

            pair_score = 0
            dim_scores = {}
            for dim_name, dim_fn, dim_max in COMPAT_DIMS:
                ds = dim_fn(a_card, b_card)
                dim_scores[dim_name] = ds
                pair_score += ds

            matrix[i][j] = pair_score
            matrix[j][i] = pair_score
            pair_scores.append(pair_score)

            status = (
                "compatible"
                if pair_score >= 80
                else "partial"
                if pair_score >= 50
                else "incompatible"
            )
            if status == "incompatible":
                incompatible_pairs.append((a_name, b_name, pair_score, dim_scores))

            findings.append(
                {
                    "severity": "INFO",
                    "category": "fed_matrix",
                    "detail": (
                        f"{a_name} ↔ {b_name}: score={pair_score}/100 "
                        f"({status}, {n} dims)"
                    ),
                }
            )

    agg_score = sum(pair_scores) / len(pair_scores) if pair_scores else 100.0
    penalty = len(incompatible_pairs) * 10
    agg_score = max(0, agg_score - penalty)

    findings.append(
        {
            "severity": "WARNING" if incompatible_pairs else "INFO",
            "category": "fed_matrix_summary",
            "detail": (
                f"Compatibility matrix: {n} agents, "
                f"avg_pair={sum(pair_scores) / len(pair_scores):.1f}/100, "
                f"incompatible={len(incompatible_pairs)} pairs"
            ),
        }
    )

    return round(agg_score, 1), matrix, findings


def check_role_conflicts(card: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    fed = card.get("federation") or {}
    role = fed.get("role")
    hints = card.get("orchestration_hints") or {}
    preferred_role = hints.get("preferred_role")

    if not role:
        findings.append(
            {
                "severity": "INFO",
                "category": "federation_role",
                "detail": "No federation role declared — role conflict not assessed",
            }
        )
        return 0, findings

    score = 0.0
    ROLE_COMPAT = {
        "primary": ("supervisor", "planner"),
        "secondary": ("worker", "validator"),
        "observer": (),
    }

    compatible_roles = ROLE_COMPAT.get(role, ())
    if preferred_role and compatible_roles:
        if preferred_role in compatible_roles:
            score += 5
            findings.append(
                {
                    "severity": "INFO",
                    "category": "federation_role",
                    "detail": f"Federation role '{role}' matches orchestration role '{preferred_role}'",
                }
            )
        else:
            arbitration_policy = fed.get("arbitration_policy")
            if arbitration_policy:
                score += 3
                findings.append(
                    {
                        "severity": "INFO",
                        "category": "federation_role",
                        "detail": f"Federation role '{role}' conflicts with orchestration role '{preferred_role}' but arbitration policy '{arbitration_policy}' is declared",
                    }
                )
            else:
                findings.append(
                    {
                        "severity": "WARNING",
                        "category": "federation_role",
                        "detail": f"Federation role '{role}' conflicts with "
                        f"orchestration role '{preferred_role}'",
                    }
                )

    return round(score, 1), findings


def check_permission_propagation(
    card: dict[str, Any],
) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    fed = card.get("federation") or {}
    allowed_servers = fed.get("allowed_mcp_servers") or []
    declared_tools = {cap["skill_id"] for cap in card.get("capabilities", [])}

    if not allowed_servers:
        findings.append(
            {
                "severity": "INFO",
                "category": "federation_permissions",
                "detail": "No MCP server whitelist — permission not assessed",
            }
        )
        return 0, findings

    score = 0.0
    has_mcp_tool = "mcp_tool" in declared_tools
    has_bridge = "bridge" in declared_tools

    if has_mcp_tool:
        score += 3
        findings.append(
            {
                "severity": "INFO",
                "category": "federation_permissions",
                "detail": f"MCP tool declared with {len(allowed_servers)} allowed server(s)",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "federation_permissions",
                "detail": "MCP whitelist declared but no mcp_tool capability",
            }
        )

    if len(allowed_servers) <= 5:
        score += 2
        findings.append(
            {
                "severity": "INFO",
                "category": "federation_permissions",
                "detail": f"Principle of least privilege: {len(allowed_servers)} MCP server(s)",
            }
        )
    else:
        findings.append(
            {
                "severity": "WARNING",
                "category": "federation_permissions",
                "detail": f"Broad MCP access: {len(allowed_servers)} servers — review need",
            }
        )

    if has_bridge:
        findings.append(
            {
                "severity": "WARNING",
                "category": "federation_permissions",
                "detail": "Bridge tool + MCP whitelist — permission propagation risk",
            }
        )

    return round(score, 1), findings


# ═══════════════════════════════════════════════════════════════
# Gold Standard: Coordination Efficiency (v3.0-GA §5.2)
# ═══════════════════════════════════════════════════════════════


def run_coordination_efficiency(
    trajectory: list[dict[str, Any]] | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    """Evaluate multi-agent coordination efficiency.

    Gold Standard §5.2 — measures:
      - Message efficiency:     actual_messages / optimal_messages
      - Communication overhead:  comm_time / total_time
      - Coordination complexity: coord_turns / task_steps
      - Noise ratio:             irrelevant_msgs / total_msgs
      - Serialization loss:      waiting_msgs / total_msgs
    """
    findings: list[dict[str, Any]] = []
    if not trajectory:
        return 50.0, findings  # neutral for single-agent

    events: list[dict[str, Any]] = (
        trajectory if isinstance(trajectory, list) else trajectory.get("events", [])
    )
    messages = [
        e
        for e in events
        if e.get("message_type") in ("request", "response", "broadcast", "irrelevant")
    ]
    tool_calls = [e for e in events if e.get("action", {}).get("type") == "tool_call"]

    if not messages:
        return 50.0, findings

    actual_msg_count = len(messages)
    optimal_msg_count = max(len(tool_calls) * 2, 1)
    msg_efficiency = min(1.0, optimal_msg_count / max(actual_msg_count, 1))

    total_latency = sum(m.get("latency_ms", 0) for m in messages)
    task_latency = sum(
        e.get("latency_ms", 0)
        for e in events
        if e.get("action", {}).get("type") == "tool_call"
    )
    total_time = total_latency + task_latency
    comm_overhead = 1.0 - (total_latency / max(total_time, 1))

    coord_messages = sum(1 for m in messages if m.get("is_coordination", False))
    coord_complexity = coord_messages / max(len(tool_calls), 1)
    coord_efficiency = min(1.0, 1.0 / max(coord_complexity, 0.1))

    irrelevant = sum(1 for m in messages if m.get("message_type") == "irrelevant")
    noise_ratio = 1.0 - (irrelevant / max(actual_msg_count, 1))

    waiting_msgs = sum(1 for m in messages if m.get("is_waiting_response", False))
    serial_loss = 1.0 - (waiting_msgs / max(actual_msg_count, 1))

    dim_weights = {
        "msg_efficiency": 0.30,
        "comm_overhead": 0.25,
        "coord_complexity": 0.20,
        "noise_ratio": 0.15,
        "serialization_loss": 0.10,
    }
    dim_scores = {
        "msg_efficiency": msg_efficiency,
        "comm_overhead": comm_overhead,
        "coord_complexity": coord_efficiency,
        "noise_ratio": noise_ratio,
        "serialization_loss": serial_loss,
    }
    score = sum(dim_scores[k] * dim_weights[k] for k in dim_weights) * 100
    score = round(max(0, min(100, score)), 1)

    findings.append(
        {
            "severity": "INFO",
            "category": "coordination_efficiency",
            "detail": (
                f"msgs={actual_msg_count}, overhead={1 - comm_overhead:.2f}, "
                f"noise={1 - noise_ratio:.2f}, score={score:.1f}"
            ),
        }
    )

    if 1 - comm_overhead > 0.5:
        findings.append(
            {
                "severity": "HIGH",
                "category": "coordination_overhead_excessive",
                "detail": f"Comm overhead {(1 - comm_overhead) * 100:.0f}% > 50%",
            }
        )
    if 1 - noise_ratio > 0.2:
        findings.append(
            {
                "severity": "WARNING",
                "category": "coordination_noise_high",
                "detail": f"Irrelevant message ratio {(1 - noise_ratio) * 100:.0f}% > 20%",
            }
        )

    return score, findings


# ═══════════════════════════════════════════════════════════════
# Gold Standard: Plan Quality (v3.0-GA §5.3)
# ═══════════════════════════════════════════════════════════════


def run_plan_quality(
    planned_trajectory: list[dict[str, Any]] | None = None,
    actual_trajectory: list[dict[str, Any]] | None = None,
    runs: list[dict[str, Any]] | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    """Evaluate plan quality of a multi-agent orchestration.

    Gold Standard §5.3 — dimensions:
      - Completeness: plan covers all required actions (40%)
      - Adherence:    actual vs planned tool sequence match (35%)
      - Stability:    plan consistency across multiple runs (25%)

    Returns:
        Score 0.0-100.0, findings list.
    """
    findings: list[dict[str, Any]] = []
    if not planned_trajectory:
        return 50.0, findings  # neutral

    planned_events: list[dict[str, Any]] = (
        planned_trajectory
        if isinstance(planned_trajectory, list)
        else planned_trajectory.get("events", [])
    )
    actual_events: list[dict[str, Any]] = (
        actual_trajectory
        if isinstance(actual_trajectory, list)
        else (actual_trajectory or {}).get("events", [])  # type: ignore[call-overload]
    )

    planned_tools = [
        e.get("action", {}).get("tool_id", "")
        for e in planned_events
        if e.get("action", {}).get("type") == "tool_call"
    ]
    actual_tools = [
        e.get("action", {}).get("tool_id", "")
        for e in actual_events
        if e.get("action", {}).get("type") == "tool_call"
    ]

    adherence = (
        SequenceMatcher(None, planned_tools, actual_tools).ratio()
        if planned_tools
        else 0.0
    )

    if planned_tools:
        executed = sum(1 for p in planned_tools if p in actual_tools)
        completeness = executed / len(planned_tools)
    else:
        completeness = 0.5

    if runs and len(runs) >= 2:
        plans = [
            [
                e.get("action", {}).get("tool_id", "")
                for e in (r if isinstance(r, list) else r.get("events", []))
                if e.get("action", {}).get("type") == "tool_call"
            ]
            for r in runs
        ]
        similarities = []
        for i in range(len(plans)):
            for j in range(i + 1, len(plans)):
                sim = SequenceMatcher(None, plans[i], plans[j]).ratio()
                similarities.append(sim)
        stability = (
            sum(similarities) / max(len(similarities), 1) if similarities else 0.0
        )
    else:
        stability = 0.5

    score = completeness * 40 + adherence * 35 + stability * 25
    score = round(max(0, min(100, score)), 1)

    findings.append(
        {
            "severity": "INFO",
            "category": "plan_quality",
            "detail": (
                f"completeness={completeness:.3f}, "
                f"adherence={adherence:.3f}, "
                f"stability={stability:.3f}, "
                f"score={score:.1f}"
            ),
        }
    )

    if adherence < 0.6:
        findings.append(
            {
                "severity": "WARNING",
                "category": "plan_adherence_poor",
                "detail": (
                    f"Plan adherence {adherence:.2f} < 0.6 — "
                    "execution diverged from plan"
                ),
            }
        )

    return score, findings


def run_d3(
    card: dict[str, Any],
    tasks: list[dict[str, Any]] | None = None,
    golden_trajectory: list[Any] | dict[str, Any] | None = None,
    federation_cards: list[dict[str, Any]] | None = None,
    inter_agent_trajectory: list[dict[str, Any]] | None = None,
    planned_trajectory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    spawn_score, spawn_findings = _score_spawn(card, golden_trajectory)
    protocol_score, protocol_findings = _score_protocol(card)
    orchestration_score, orchestration_findings = _score_orchestration(card, tasks)
    isolation_score, isolation_findings = _score_isolation(card)
    conflict_score, conflict_findings = _score_conflict(card)
    persistence_score, persistence_findings = _score_persistence(card)
    coord_score, coord_findings = run_coordination_efficiency(inter_agent_trajectory)
    plan_score, plan_findings = run_plan_quality(
        planned_trajectory, inter_agent_trajectory
    )

    # v0.8.1 NEW — A2A security interaction (OWASP Agentic #4/#5/#9)
    from mas_eval.domains.d3_security_interaction import run_d3_security_interaction

    sec_result = run_d3_security_interaction(card)
    sec_score = sec_result["score"]
    sec_findings = sec_result.get("findings", [])

    all_findings = (
        spawn_findings
        + protocol_findings
        + orchestration_findings
        + isolation_findings
        + conflict_findings
        + persistence_findings
        + coord_findings
        + plan_findings
        + sec_findings
    )

    d3_score = (
        spawn_score * 0.15
        + protocol_score * 0.15
        + orchestration_score * 0.15  # v0.8.0: 0.20 → v0.8.1: 0.15 (rebalanced for security_interaction)
        + isolation_score * 0.15
        + conflict_score * 0.10
        + persistence_score * 0.10
        + coord_score * 0.10
        + plan_score * 0.05
        + sec_score * 0.05  # v0.8.1 NEW — A2A security interaction
    )

    fed_compat_score = 0.0
    role_score = 0.0
    perm_score = 0.0
    matrix_score = None
    if _is_federation_card(card):
        fed_compat_score, fed_findings = check_federation_compatibility(card)
        role_score, role_findings = check_role_conflicts(card)
        perm_score, perm_findings = check_permission_propagation(card)
        all_findings.extend(fed_findings + role_findings + perm_findings)
        d3_score += fed_compat_score * 0.05 + role_score * 0.05 + perm_score * 0.05

    all_cards = [card]
    if federation_cards:
        all_cards.extend(federation_cards)
    if len(all_cards) >= 2:
        matrix_score, matrix_raw, matrix_findings = (
            check_federation_compatibility_matrix(all_cards)
        )
        all_findings.extend(matrix_findings)

    d3_score = min(100, d3_score)

    # Gold Standard v3.0-GA §10 — augment findings with v2 attribution fields.
    from mas_eval.scoring.findings import upgrade_findings_to_v2

    all_findings = upgrade_findings_to_v2(
        all_findings,
        default_layer="coordination",
        default_root_cause="coordination_failure",
        default_reproducibility="stochastic",
        default_mitigation="auto_recovery",
    )

    subscores = {
        "spawn": spawn_score,
        "protocol": protocol_score,
        "orchestration": orchestration_score,
        "isolation": isolation_score,
        "conflict": conflict_score,
        "persistence": persistence_score,
        "coordination_efficiency": coord_score,
        "plan_quality": plan_score,
        "security_interaction": sec_score,  # v0.8.1 NEW
        "security_interaction_detail": sec_result.get("subscores", {}),  # v0.8.1 NEW
        "federation_compat": fed_compat_score,
        "federation_role": role_score,
        "federation_permissions": perm_score,
    }
    if matrix_score is not None:
        subscores["federation_matrix"] = matrix_score

    return {
        "domain": "D3",
        "name": "Multi-Agent Collaboration",
        "score": round(d3_score, 1),
        "subscores": subscores,
        "findings": all_findings,
        "summary": {
            "total_findings": len(all_findings),
            "preferred_role": card.get("orchestration_hints", {}).get(
                "preferred_role", "unknown"
            ),
            "parallel_safe": card.get("orchestration_hints", {}).get(
                "parallel_safe", False
            ),
            "stateful": card.get("orchestration_hints", {}).get("stateful", False),
            "has_a2a": bool(card.get("endpoints", {}).get("a2a")),
            "has_mcp": bool(card.get("endpoints", {}).get("mcp")),
            "federation_role": (card.get("federation") or {}).get("role", "none"),
        },
    }
