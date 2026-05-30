"""Tests for D3: Multi-Agent Collaboration (MAS-TS-001 v3.0)"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d3_multi_agent import (
    run_d3,
    _score_spawn,
    _score_protocol,
    _score_orchestration,
    _score_isolation,
    _score_conflict,
    _score_persistence,
    D3_MAS_TASKS,
    SPAWN_REQUIRED_TOOLS,
    TRANSPORT_TYPES,
)

FULL_MAS_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:mas:full-01",
    "name": "Full MAS Agent",
    "version": "2.0.0",
    "model_backend": {"provider": "anthropic", "model": "claude-sonnet-4", "deployment": "cloud", "endpoint": "https://api.anthropic.com/v1/messages"},
    "compliance": {"data_residency": "US", "data_classification": "confidential", "cross_border": True, "model_backend_location": "US", "audit_trail_required": True},
    "constitution": {
        "envelope": {"message_id": "msg-001", "correlation_id": "corr-001", "timestamp": "2026-05-29T00:00:00Z", "sender": "urn:agent:test:mas:full-01"},
        "health_state": "HEALTHY",
        "heartbeat_interval_seconds": 30,
        "stale_node_timeout_seconds": 60,
        "message_format": {
            "version": "1.0",
            "supported_transports": ["stdio", "sse", "http", "grpc"],
            "max_payload_bytes": 1048576,
        },
    },
    "capabilities": [
        {"skill_id": "agent_tool", "description": "Spawn sub-agents", "input_schema": {}, "output_schema": {}, "examples": ["spawn"], "rate_limit": "30/min", "business_rule_version": "2026-05-01"},
        {"skill_id": "mcp_tool", "description": "MCP protocol", "input_schema": {}, "output_schema": {}, "examples": ["mcp"], "rate_limit": "30/min", "business_rule_version": "2026-05-01"},
        {"skill_id": "worktree", "description": "Isolated sessions", "input_schema": {}, "output_schema": {}, "examples": ["wt"]},
        {"skill_id": "memory", "description": "State persistence", "input_schema": {}, "output_schema": {}, "examples": ["mem"]},
        {"skill_id": "task_management", "description": "Task lifecycle", "input_schema": {}, "output_schema": {}, "examples": ["task"]},
        {"skill_id": "todo_write", "description": "Todo lists", "input_schema": {}, "output_schema": {}, "examples": ["todo"]},
        {"skill_id": "cron", "description": "Scheduling", "input_schema": {}, "output_schema": {}, "examples": ["cron"]},
        {"skill_id": "bash", "description": "Shell", "input_schema": {}, "output_schema": {}, "examples": ["bash"]},
        {"skill_id": "file_read", "description": "Read", "input_schema": {}, "output_schema": {}, "examples": ["read"]},
        {"skill_id": "file_edit", "description": "Edit", "input_schema": {}, "output_schema": {}, "examples": ["edit"]},
        {"skill_id": "file_write", "description": "Write", "input_schema": {}, "output_schema": {}, "examples": ["write"]},
    ],
    "endpoints": {
        "a2a": "https://agent.example.com/a2a",
        "mcp": "https://agent.example.com/mcp/sse",
    },
    "authentication": {"type": "OAuth2", "scopes": ["agent:spawn", "agent:communicate"]},
    "orchestration_hints": {
        "preferred_role": "supervisor",
        "parallel_safe": True,
        "stateful": True,
    },
}

MINIMAL_MAS_CARD = {
    "card_version": "1.1",
    "agent_id": "urn:agent:test:mas:minimal-01",
    "name": "Minimal MAS Agent",
    "version": "0.1.0",
    "model_backend": {"provider": "test", "model": "test-model", "deployment": "local", "endpoint": "http://localhost:8080"},
    "capabilities": [
        {"skill_id": "bash", "description": "Shell", "input_schema": {}, "output_schema": {}, "examples": ["bash"]},
        {"skill_id": "file_read", "description": "Read", "input_schema": {}, "output_schema": {}, "examples": ["read"]},
    ],
    "authentication": {"type": "None"},
    "orchestration_hints": {
        "preferred_role": "worker",
        "parallel_safe": False,
        "stateful": False,
    },
}

GOLDEN_MAS_TRAJECTORY = {
    "events": [
        {"action": {"type": "tool_call", "tool_id": "agent_tool", "input": {"task": "search"}, "output": {"status": "assigned", "task_id": "sub-001"}}, "orchestration": {"routing_decision": "auto", "routing_reason": "capability_match"}},
        {"action": {"type": "tool_call", "tool_id": "agent_tool", "input": {"task": "implement"}, "output": {"status": "assigned", "task_id": "sub-002"}}, "orchestration": {"routing_decision": "auto", "routing_reason": "capability_match"}},
        {"action": {"type": "tool_call", "tool_id": "file_write", "input": {"path": "/tmp/test.py"}, "output": {"status": "created"}}, "orchestration": {"routing_decision": "auto", "routing_reason": "capability_match"}},
    ]
}


class TestD3:
    def test_d3_full(self):
        result = run_d3(FULL_MAS_CARD, tasks={})
        assert result["domain"] == "D3"
        assert 0 <= result["score"] <= 100
        assert set(result["subscores"].keys()) == {"spawn", "protocol", "orchestration", "isolation", "conflict", "persistence"}

    def test_d3_minimal(self):
        result = run_d3(MINIMAL_MAS_CARD)
        assert result["domain"] == "D3"
        assert result["score"] < 50

    def test_d3_full_higher_than_minimal(self):
        full = run_d3(FULL_MAS_CARD, tasks={})
        minimal = run_d3(MINIMAL_MAS_CARD)
        assert full["score"] > minimal["score"]

    def test_d3_subscores_range(self):
        result = run_d3(FULL_MAS_CARD, tasks={})
        for subname, subscore in result["subscores"].items():
            assert 0 <= subscore <= 100, f"{subname} score {subscore} out of range"

    def test_d3_all_dimensions_have_findings(self):
        result = run_d3(FULL_MAS_CARD, tasks={})
        finding_categories = {f["category"] for f in result["findings"]}
        assert any("spawn" in c for c in finding_categories)
        assert any("protocol" in c for c in finding_categories)
        assert any("orchestration" in c or "parallel" in c for c in finding_categories)
        assert any("isolation" in c for c in finding_categories)
        assert any("conflict" in c for c in finding_categories)
        assert any("persistence" in c for c in finding_categories)


class TestSpawn:
    def test_spawn_with_agent_tool(self):
        score, findings = _score_spawn(FULL_MAS_CARD)
        assert score >= 40

    def test_spawn_without_agent_tool(self):
        score, findings = _score_spawn(MINIMAL_MAS_CARD)
        assert score < 40

    def test_spawn_with_golden_trajectory(self):
        score, findings = _score_spawn(FULL_MAS_CARD, GOLDEN_MAS_TRAJECTORY)
        assert score > 40

    def test_spawn_rate_limit_high(self):
        card_with_high_rate = {
            "capabilities": [{"skill_id": "agent_tool", "rate_limit": "60/min"}],
        }
        score, findings = _score_spawn(card_with_high_rate)
        assert score >= 60

    def test_spawn_rate_limit_low(self):
        card_with_low_rate = {
            "capabilities": [{"skill_id": "agent_tool", "rate_limit": "1/min"}],
        }
        score, findings = _score_spawn(card_with_low_rate)
        assert score < 60


class TestProtocol:
    def test_protocol_full(self):
        score, findings = _score_protocol(FULL_MAS_CARD)
        assert score >= 60

    def test_protocol_minimal(self):
        score, findings = _score_protocol(MINIMAL_MAS_CARD)
        assert score == 0

    def test_protocol_a2a_mcp(self):
        card = {
            "endpoints": {"a2a": "https://example.com/a2a", "mcp": "https://example.com/mcp"},
            "constitution": {"envelope": {"message_id": "1", "correlation_id": "2", "timestamp": "3", "sender": "4"}},
        }
        score, findings = _score_protocol(card)
        assert score > 0

    def test_protocol_no_endpoints(self):
        card = {"endpoints": {}, "constitution": {}}
        score, findings = _score_protocol(card)
        assert score == 0

    def test_protocol_transport_types(self):
        assert "stdio" in TRANSPORT_TYPES
        assert len(TRANSPORT_TYPES) == 6

    def test_protocol_transport_scoring(self):
        card = {
            "constitution": {
                "message_format": {
                    "version": "1.0",
                    "supported_transports": ["stdio", "sse", "websocket", "http", "grpc", "ipc"],
                    "max_payload_bytes": 1048576,
                }
            }
        }
        score, findings = _score_protocol(card)
        assert score > 0


class TestOrchestration:
    def test_orchestration_supervisor(self):
        score, findings = _score_orchestration(FULL_MAS_CARD, tasks={})
        assert score >= 40

    def test_orchestration_worker(self):
        score, findings = _score_orchestration(MINIMAL_MAS_CARD)
        assert score < 40

    def test_orchestration_with_tasks(self):
        score, findings = _score_orchestration(FULL_MAS_CARD, tasks={"some": "tasks"})
        assert score > 0

    def test_orchestration_parallel_safe(self):
        card = {"capabilities": [], "orchestration_hints": {"preferred_role": "supervisor", "parallel_safe": True, "stateful": True}}
        score, findings = _score_orchestration(card, tasks={})
        assert score >= 40

    def test_orchestration_not_parallel_safe(self):
        card = {"capabilities": [], "orchestration_hints": {"preferred_role": "worker", "parallel_safe": False}}
        score, findings = _score_orchestration(card, tasks={})
        assert score < 40

    def test_d3_task_definitions(self):
        dims = {t["dimension"] for t in D3_MAS_TASKS}
        assert "spawn" in dims
        assert "protocol" in dims
        assert "orchestration" in dims
        assert "isolation" in dims
        assert "conflict" in dims
        assert "persistence" in dims


class TestIsolation:
    def test_isolation_with_worktree(self):
        score, findings = _score_isolation(FULL_MAS_CARD)
        assert score >= 40

    def test_isolation_without_worktree(self):
        score, findings = _score_isolation(MINIMAL_MAS_CARD)
        assert score < 40

    def test_isolation_parallel_safe_plus_memory(self):
        card = {"capabilities": [{"skill_id": "worktree"}, {"skill_id": "memory"}], "orchestration_hints": {"parallel_safe": True}}
        score, findings = _score_isolation(card)
        assert score >= 70

    def test_isolation_tool_required(self):
        from mas_eval.domains.d3_multi_agent import ISOLATION_TOOLS
        assert "worktree" in ISOLATION_TOOLS


class TestConflict:
    def test_conflict_both_tools(self):
        score, findings = _score_conflict(FULL_MAS_CARD)
        assert score >= 40

    def test_conflict_no_tools(self):
        score, findings = _score_conflict(MINIMAL_MAS_CARD)
        assert score < 30

    def test_conflict_agent_only(self):
        card = {"capabilities": [{"skill_id": "agent_tool"}], "orchestration_hints": {}}
        score, findings = _score_conflict(card)
        assert 20 <= score < 40

    def test_conflict_supervisor_bonus(self):
        card = {"capabilities": [{"skill_id": "agent_tool"}, {"skill_id": "mcp_tool"}], "orchestration_hints": {"preferred_role": "supervisor"}}
        score, findings = _score_conflict(card)
        assert score >= 70

    def test_conflict_shared_tools(self):
        card = {
            "capabilities": [
                {"skill_id": "agent_tool"}, {"skill_id": "mcp_tool"},
                {"skill_id": "file_edit"}, {"skill_id": "file_write"}, {"skill_id": "bash"},
            ],
            "orchestration_hints": {"preferred_role": "supervisor"},
        }
        score, findings = _score_conflict(card)
        assert score >= 70


class TestPersistence:
    def test_persistence_full(self):
        score, findings = _score_persistence(FULL_MAS_CARD)
        assert score >= 60

    def test_persistence_minimal(self):
        score, findings = _score_persistence(MINIMAL_MAS_CARD)
        assert score < 30

    def test_persistence_memory_only(self):
        card = {"capabilities": [{"skill_id": "memory"}], "orchestration_hints": {"stateful": True}}
        score, findings = _score_persistence(card)
        assert score >= 40

    def test_persistence_stateful(self):
        card = {"capabilities": [], "orchestration_hints": {"stateful": True}}
        score, findings = _score_persistence(card)
        assert score > 0

    def test_persistence_stateless(self):
        card = {"capabilities": [], "orchestration_hints": {"stateful": False}}
        score, findings = _score_persistence(card)
        assert score == 0

    def test_persistence_cron_bonus(self):
        card = {"capabilities": [{"skill_id": "memory"}, {"skill_id": "cron"}], "orchestration_hints": {"stateful": True}}
        score, findings = _score_persistence(card)
        assert score >= 60
