# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for D2: Single-Agent Capability (MAS-TS-001 v3.0)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d2_single_agent import (
    run_d2,
    run_model_quality,
    run_tool_coverage,
    run_task_completion,
    run_e2e_scenarios,
    MODEL_QUALITY_DB,
    CORE_TOOLS,
    ADVANCED_TOOLS,
    E2E_SCENARIOS,
)

FULL_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:test:test-01",
    "name": "Test Agent",
    "version": "1.0.0",
    "model_backend": {"provider": "test", "model": "claude-sonnet-4", "deployment": "cloud", "endpoint": "https://api.anthropic.com/v1/messages"},
    "capabilities": [
        {"skill_id": "bash", "description": "x", "input_schema": {}, "output_schema": {}, "examples": ["ls"], "business_rule_version": "2026-05-01"},
        {"skill_id": "file_read", "description": "x", "input_schema": {}, "output_schema": {}, "examples": ["r"]},
        {"skill_id": "file_edit", "description": "x", "input_schema": {}, "output_schema": {}, "examples": ["e"]},
        {"skill_id": "file_write", "description": "x", "input_schema": {}, "output_schema": {}, "examples": ["w"]},
        {"skill_id": "glob", "description": "x", "input_schema": {}, "output_schema": {}, "examples": ["g"]},
        {"skill_id": "grep", "description": "x", "input_schema": {}, "output_schema": {}, "examples": ["gr"]},
        {"skill_id": "web_search", "description": "x", "input_schema": {}, "output_schema": {}, "examples": ["s"]},
        {"skill_id": "web_fetch", "description": "x", "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "examples": ["f"]},
        {"skill_id": "agent_tool", "description": "x", "input_schema": {}, "output_schema": {}, "examples": ["a"]},
        {"skill_id": "mcp_tool", "description": "x", "input_schema": {}, "output_schema": {}, "examples": ["m"]},
    ],
}

MINIMAL_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:minimal:min-01",
    "name": "Minimal Agent",
    "version": "0.1.0",
    "model_backend": {"provider": "unknown", "model": "unknown-model", "deployment": "local", "endpoint": "http://localhost:8080"},
    "capabilities": [
        {"skill_id": "bash", "description": "x", "input_schema": {}, "output_schema": {}, "examples": ["ls"]},
    ],
}

GOLDEN_TRAJECTORY = {
    "events": [
        {"action": {"type": "tool_call", "tool_id": "grep", "input": {"pattern": "foo"}}, "orchestration": {"routing_decision": "auto", "routing_reason": "capability_match"}},
        {"action": {"type": "tool_call", "tool_id": "file_read", "input": {"path": "/x.py"}}, "orchestration": {"routing_decision": "auto", "routing_reason": "capability_match"}},
        {"action": {"type": "tool_call", "tool_id": "file_edit", "input": {"path": "/x.py", "old_str": "foo", "new_str": "bar"}}, "orchestration": {"routing_decision": "auto", "routing_reason": "capability_match"}},
    ]
}

MOCK_TRAJECTORY = {
    "events": [
        {"action": {"type": "tool_call", "tool_id": "grep", "input": {"pattern": "foo"}}, "orchestration": {"routing_decision": "auto", "routing_reason": "capability_match"}},
        {"action": {"type": "tool_call", "tool_id": "file_read", "input": {"path": "/x.py"}}, "orchestration": {"routing_decision": "auto", "routing_reason": "capability_match"}},
        {"action": {"type": "tool_call", "tool_id": "file_edit", "input": {"path": "/x.py", "old_str": "foo", "new_str": "bar"}}, "orchestration": {"routing_decision": "auto", "routing_reason": "capability_match"}},
    ]
}


def test_d2_full():
    result = run_d2(FULL_CARD)
    assert result["domain"] == "D2"
    assert 0 <= result["score"] <= 100
    assert "subscores" in result
    assert set(result["subscores"].keys()) == {"model_quality", "tool_coverage", "task_completion", "e2e_scenarios"}


def test_d2_model_quality_known():
    score, findings = run_model_quality(FULL_CARD)
    assert score == 88.0
    assert any("claude-sonnet-4" in f["detail"] for f in findings)


def test_d2_model_quality_unknown():
    score, findings = run_model_quality(MINIMAL_CARD)
    assert score == 50.0
    assert any("WARNING" in f["severity"] for f in findings)


def test_d2_model_quality_all_models():
    for model_key, data in MODEL_QUALITY_DB.items():
        card = {"model_backend": {"model": model_key}}
        score, _ = run_model_quality(card)
        expected = data["reasoning"] * 0.35 + data["coding"] * 0.30 + data["multilingual"] * 0.20 + data["instruction"] * 0.15
        assert score == round(expected, 1), f"{model_key}: expected {expected}, got {score}"


def test_d2_tool_coverage_full():
    score, findings = run_tool_coverage(FULL_CARD)
    assert score > 80


def test_d2_tool_coverage_minimal():
    score, findings = run_tool_coverage(MINIMAL_CARD)
    assert score < 50


def test_d2_tool_coverage_all_core():
    caps = [{"skill_id": t, "input_schema": {}, "output_schema": {}} for t in CORE_TOOLS]
    card = {"capabilities": caps}
    score, findings = run_tool_coverage(card)
    assert score >= 80


def test_d2_tool_coverage_all_advanced():
    caps = [{"skill_id": t, "input_schema": {}, "output_schema": {}} for t in ADVANCED_TOOLS]
    card = {"capabilities": caps}
    score, findings = run_tool_coverage(card)
    assert score > 0


def test_d2_task_completion_match():
    score, findings = run_task_completion(FULL_CARD, GOLDEN_TRAJECTORY, MOCK_TRAJECTORY)
    assert score >= 90


def test_d2_task_completion_no_data():
    score, findings = run_task_completion(FULL_CARD)
    assert score == 0.0
    assert any("not provided" in f["detail"] for f in findings)


def test_d2_task_completion_mismatch():
    mock_bad = {"events": [{"action": {"type": "tool_call", "tool_id": "bash", "input": {}}, "orchestration": {}}]}
    score, findings = run_task_completion(FULL_CARD, GOLDEN_TRAJECTORY, mock_bad)
    assert score < 50


def test_d2_e2e_full():
    score, findings = run_e2e_scenarios(FULL_CARD)
    assert score > 80


def test_d2_e2e_minimal():
    score, findings = run_e2e_scenarios(MINIMAL_CARD)
    assert score < 50


def test_d2_e2e_all_scenarios_covered():
    declared = set()
    for s in E2E_SCENARIOS:
        declared.update(s["required_tools"])
    card = {"capabilities": [{"skill_id": t} for t in declared]}
    score, _ = run_e2e_scenarios(card)
    assert score == 100.0


def test_d2_e2e_scenario_count():
    assert len(E2E_SCENARIOS) == 8


def test_d2_composite_score():
    full = run_d2(FULL_CARD)
    minimal = run_d2(MINIMAL_CARD)
    assert full["score"] > minimal["score"]


def test_d2_subscores_range():
    result = run_d2(FULL_CARD)
    for subname, subscore in result["subscores"].items():
        assert 0 <= subscore <= 100, f"{subname} score {subscore} out of range"


def test_d2_task_completion_empty_trajectories():
    score, findings = run_task_completion(FULL_CARD, {"events": []}, {"events": []})
    assert score == 0.0


def test_d2_core_tools_defined():
    assert len(CORE_TOOLS) == 8


def test_d2_advanced_tools_defined():
    assert len(ADVANCED_TOOLS) == 7
