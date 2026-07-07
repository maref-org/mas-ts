# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for D2: Single-Agent Capability (MAS-TS-001 v3.0)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d2_single_agent import (
    ADVANCED_TOOLS,
    CORE_TOOLS,
    E2E_SCENARIOS,
    MODEL_QUALITY_DB,
    run_d2,
    run_e2e_scenarios,
    run_model_quality,
    run_step_efficiency,
    run_task_completion,
    run_tool_coverage,
    run_tool_selection_correctness,
    run_trajectory_quality,
)

FULL_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:test:test-01",
    "name": "Test Agent",
    "version": "1.0.0",
    "model_backend": {
        "provider": "test",
        "model": "claude-sonnet-4",
        "deployment": "cloud",
        "endpoint": "https://api.anthropic.com/v1/messages",
    },
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_read",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["r"],
        },
        {
            "skill_id": "file_edit",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["e"],
        },
        {
            "skill_id": "file_write",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["w"],
        },
        {
            "skill_id": "glob",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["g"],
        },
        {
            "skill_id": "grep",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["gr"],
        },
        {
            "skill_id": "web_search",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["s"],
        },
        {
            "skill_id": "web_fetch",
            "description": "x",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "examples": ["f"],
        },
        {
            "skill_id": "agent_tool",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["a"],
        },
        {
            "skill_id": "mcp_tool",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["m"],
        },
    ],
}

MINIMAL_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:minimal:min-01",
    "name": "Minimal Agent",
    "version": "0.1.0",
    "model_backend": {
        "provider": "unknown",
        "model": "unknown-model",
        "deployment": "local",
        "endpoint": "http://localhost:8080",
    },
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "x",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
        },
    ],
}

GOLDEN_TRAJECTORY = {
    "events": [
        {
            "action": {
                "type": "tool_call",
                "tool_id": "grep",
                "input": {"pattern": "foo"},
            },
            "orchestration": {
                "routing_decision": "auto",
                "routing_reason": "capability_match",
            },
        },
        {
            "action": {
                "type": "tool_call",
                "tool_id": "file_read",
                "input": {"path": "/x.py"},
            },
            "orchestration": {
                "routing_decision": "auto",
                "routing_reason": "capability_match",
            },
        },
        {
            "action": {
                "type": "tool_call",
                "tool_id": "file_edit",
                "input": {"path": "/x.py", "old_str": "foo", "new_str": "bar"},
            },
            "orchestration": {
                "routing_decision": "auto",
                "routing_reason": "capability_match",
            },
        },
    ]
}

MOCK_TRAJECTORY = {
    "events": [
        {
            "action": {
                "type": "tool_call",
                "tool_id": "grep",
                "input": {"pattern": "foo"},
            },
            "orchestration": {
                "routing_decision": "auto",
                "routing_reason": "capability_match",
            },
        },
        {
            "action": {
                "type": "tool_call",
                "tool_id": "file_read",
                "input": {"path": "/x.py"},
            },
            "orchestration": {
                "routing_decision": "auto",
                "routing_reason": "capability_match",
            },
        },
        {
            "action": {
                "type": "tool_call",
                "tool_id": "file_edit",
                "input": {"path": "/x.py", "old_str": "foo", "new_str": "bar"},
            },
            "orchestration": {
                "routing_decision": "auto",
                "routing_reason": "capability_match",
            },
        },
    ]
}


def test_d2_full():
    result = run_d2(FULL_CARD)
    assert result["domain"] == "D2"
    assert 0 <= result["score"] <= 100
    assert "subscores" in result
    assert set(result["subscores"].keys()) == {
        "model_quality",
        "tool_coverage",
        "task_completion",
        "e2e_scenarios",
        "step_efficiency",
        "trajectory_quality",
        "latency_pressure",
        "tool_selection_correctness",
    }


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
        expected = (
            data["reasoning"] * 0.35
            + data["coding"] * 0.30
            + data["multilingual"] * 0.20
            + data["instruction"] * 0.15
        )
        assert score == round(expected, 1), (
            f"{model_key}: expected {expected}, got {score}"
        )


def test_d2_tool_coverage_full():
    score, findings = run_tool_coverage(FULL_CARD)
    assert score > 80


def test_d2_tool_coverage_minimal():
    score, findings = run_tool_coverage(MINIMAL_CARD)
    assert score < 50


def test_d2_tool_coverage_all_core():
    caps = [
        {"skill_id": t, "input_schema": {}, "output_schema": {}} for t in CORE_TOOLS
    ]
    card = {"capabilities": caps}
    score, findings = run_tool_coverage(card)
    assert score >= 80


def test_d2_tool_coverage_all_advanced():
    caps = [
        {"skill_id": t, "input_schema": {}, "output_schema": {}} for t in ADVANCED_TOOLS
    ]
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
    mock_bad = {
        "events": [
            {
                "action": {"type": "tool_call", "tool_id": "bash", "input": {}},
                "orchestration": {},
            }
        ]
    }
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


# ═══════════════════════════════════════════════════════════════
# Gold Standard: StepEfficiency tests (v3.0-GA §4.2)
# ═══════════════════════════════════════════════════════════════


def test_step_efficiency_optimal():
    """3-5 step scenario, actual 4 steps → high score."""
    traj = {
        "events": [
            {"action": {"type": "tool_call", "tool_id": "grep", "is_retry": False}},
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "file_read",
                    "is_retry": False,
                }
            },
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "file_edit",
                    "is_retry": False,
                }
            },
            {"action": {"type": "tool_call", "tool_id": "grep", "is_retry": False}},
        ]
    }
    config = {"expected_steps": "3-5"}
    score, findings = run_step_efficiency(traj, config)
    assert score >= 70.0, f"Expected >=70, got {score}"


def test_step_efficiency_poor():
    """3-5 step scenario, 25 steps with repeated tools → low score."""
    traj = {
        "events": [
            {"action": {"type": "tool_call", "tool_id": "grep", "is_retry": True}}
            for _ in range(25)
        ]
    }
    config = {"expected_steps": "3-5"}
    score, findings = run_step_efficiency(traj, config)
    assert score < 50.0, f"Expected <50, got {score}"


def test_step_efficiency_no_trajectory():
    """No trajectory → score 0 + WARNING."""
    score, findings = run_step_efficiency(None, {"expected_steps": "3-5"})
    assert score == 0.0
    assert any(f["severity"] == "WARNING" for f in findings)


def test_step_efficiency_no_config():
    """No scenario config → score 0 + WARNING."""
    score, findings = run_step_efficiency({"events": []}, None)
    assert score == 0.0


def test_step_efficiency_revisit_penalty():
    """High revisitation → warning triggered."""
    traj = {
        "events": [
            {"action": {"type": "tool_call", "tool_id": "grep", "is_retry": False}},
            {"action": {"type": "tool_call", "tool_id": "grep", "is_retry": False}},
            {"action": {"type": "tool_call", "tool_id": "grep", "is_retry": False}},
            {"action": {"type": "tool_call", "tool_id": "grep", "is_retry": False}},
        ]
    }
    config = {"expected_steps": "1-3"}
    score, findings = run_step_efficiency(traj, config)
    categories = [f["category"] for f in findings]
    assert "step_efficiency_high_revisit" in categories, (
        f"Expected 'step_efficiency_high_revisit' in {categories}"
    )


def test_step_efficiency_single_step():
    """Single step near-optimal → score near 100."""
    traj = {
        "events": [
            {"action": {"type": "tool_call", "tool_id": "bash", "is_retry": False}},
        ]
    }
    config = {"expected_steps": "1-3"}
    score, findings = run_step_efficiency(traj, config)
    assert score >= 80.0, f"Expected >=80, got {score}"


# ═══════════════════════════════════════════════════════════════
# Gold Standard: TrajectoryQuality tests (v3.0-GA §4.3)
# ═══════════════════════════════════════════════════════════════


def test_trajectory_quality_perfect():
    """Perfect match with golden trajectory → high score."""
    golden = {"events": [{"action": {"type": "tool_call", "tool_id": "grep"}}]}
    actual = {
        "events": [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "grep",
                    "reasoning": "need to search",
                }
            }
        ]
    }
    score, findings = run_trajectory_quality(actual, golden)
    assert score >= 80.0, f"Expected >=80, got {score}"


def test_trajectory_quality_no_golden():
    """Without golden trajectory → partial score >= 40."""
    actual = {
        "events": [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "grep",
                    "reasoning": "search",
                }
            }
        ]
    }
    score, findings = run_trajectory_quality(actual, None)
    assert score >= 40.0, f"Expected >=40, got {score}"
    categories = [f["category"] for f in findings]
    assert "trajectory_quality_determinism" in categories


def test_trajectory_quality_empty():
    """No trajectory → score 0."""
    score, findings = run_trajectory_quality(None)
    assert score == 0.0


def test_trajectory_quality_divergent():
    """Completely different from golden → low score."""
    golden = {"events": [{"action": {"type": "tool_call", "tool_id": "bash"}}]}
    actual = {
        "events": [
            {"action": {"type": "tool_call", "tool_id": "web_search"}},
            {"action": {"type": "tool_call", "tool_id": "file_write"}},
        ]
    }
    score, findings = run_trajectory_quality(actual, golden)
    assert score < 70.0


def test_trajectory_quality_recovery():
    """Error followed by recovery → good recovery score."""
    actual = {
        "events": [
            {
                "action": {"type": "tool_call", "tool_id": "bash"},
                "error": "command not found",
                "recovery": "retry with correct command",
            },
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "bash",
                    "reasoning": "retry",
                },
            },
        ]
    }
    score, findings = run_trajectory_quality(actual, None)
    assert score > 0


# ═══════════════════════════════════════════════════════════════
# Gold Standard: ToolSelectionCorrectness tests (v3.0-GA §4.4)
# ═══════════════════════════════════════════════════════════════


def test_tool_selection_correctness_perfect():
    """All required tools used, no extras → high score."""
    traj = {
        "events": [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "grep",
                    "input": {"pattern": "foo"},
                }
            },
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "file_read",
                    "input": {"path": "bar"},
                }
            },
        ]
    }
    score, findings = run_tool_selection_correctness(traj, ["grep", "file_read"])
    assert score >= 80.0, f"Expected >=80, got {score}"


def test_tool_selection_correctness_poor():
    """Wrong tools used → low selection accuracy."""
    traj = {
        "events": [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "web_search",
                    "input": {"query": "x"},
                }
            }
        ]
    }
    score, findings = run_tool_selection_correctness(traj, ["grep", "file_read"])
    assert score < 65.0, f"Expected <65, got {score}"


def test_tool_selection_correctness_empty():
    """No trajectory → score 0."""
    score, findings = run_tool_selection_correctness(None)
    assert score == 0.0


def test_tool_selection_correctness_warning():
    """Selection accuracy < 0.85 → warning."""
    traj = {
        "events": [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "bash",
                    "input": {"cmd": "ls"},
                }
            }
        ]
    }
    score, findings = run_tool_selection_correctness(traj, ["grep", "file_read"])
    categories = [f["category"] for f in findings]
    assert "tool_selection_poor" in categories


# ═══════════════════════════════════════════════════════════════
# Gold Standard: D2 subscore validation
# ═══════════════════════════════════════════════════════════════


def test_d2_gold_subscores_present():
    """Gold Standard run_d2 returns all 8 subscores (incl. latency_pressure)."""
    result = run_d2(FULL_CARD)
    expected_subs = [
        "model_quality",
        "tool_coverage",
        "task_completion",
        "e2e_scenarios",
        "step_efficiency",
        "trajectory_quality",
        "latency_pressure",
        "tool_selection_correctness",
    ]
    for sub in expected_subs:
        assert sub in result["subscores"], f"Missing subscore: {sub}"


def test_d2_gold_subscores_range():
    """All 7 subscores within valid range."""
    result = run_d2(FULL_CARD)
    for subname, subscore in result["subscores"].items():
        assert 0 <= subscore <= 100, f"{subname} score {subscore} out of range"


def test_d2_gold_score_higher_with_scenario_trajs():
    """run_d2 with scenario_trajectories yields non-zero step efficiency."""
    traj = {
        "trajectory": {
            "events": [
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "grep",
                        "is_retry": False,
                    }
                },
            ]
        }
    }
    result = run_d2(FULL_CARD, scenario_trajectories=[traj])
    assert result["subscores"]["step_efficiency"] >= 0
