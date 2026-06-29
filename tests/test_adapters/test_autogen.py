# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for AutoGen adapter."""

import pytest

from adapters.autogen import AutoGenAdapter, AutoGenEvaluator


class MockAutoGenAgent:
    """Mock AutoGen agent for testing."""

    def __init__(self):
        self.name = "test-agent"
        self.description = "Test AutoGen agent"
        self.tools = []


def test_autogen_adapter_init():
    """Test AutoGen adapter initialization."""
    agent = MockAutoGenAgent()
    adapter = AutoGenAdapter(agent)
    assert adapter.agent == agent
    assert adapter.config == {}


def test_autogen_adapter_with_config():
    """Test AutoGen adapter with configuration."""
    agent = MockAutoGenAgent()
    config = {
        "name": "custom-agent",
        "provider": "openai",
        "model": "gpt-4",
    }
    adapter = AutoGenAdapter(agent, config)
    assert adapter.agent == agent
    assert adapter.config == config


def test_autogen_adapter_to_agent_card():
    """Test conversion to Agent Card."""
    agent = MockAutoGenAgent()
    adapter = AutoGenAdapter(agent)
    card = adapter.to_agent_card()

    assert card["card_version"] == "2.0"
    assert card["schema_version"] == "2.0"
    assert card["name"] == "test-agent"
    assert card["description"] == "Test AutoGen agent"
    assert "agent_id" in card
    assert "compliance" in card
    assert "constitution" in card
    assert "model_backend" in card
    assert "capabilities" in card
    assert "authentication" in card
    assert "federation" in card
    assert "governance" in card
    assert "audit" in card


def test_autogen_adapter_agent_id_format():
    """Test agent ID follows URN format."""
    agent = MockAutoGenAgent()
    adapter = AutoGenAdapter(agent)
    card = adapter.to_agent_card()

    assert card["agent_id"].startswith("urn:agent:autogen:")


def test_autogen_evaluator_init():
    """Test AutoGen evaluator initialization."""
    agent = MockAutoGenAgent()
    evaluator = AutoGenEvaluator(agent)
    assert evaluator.adapter.agent == agent
    assert "agent_id" in evaluator.card


def test_autogen_evaluator_get_agent_card():
    """Test getting agent card from evaluator."""
    agent = MockAutoGenAgent()
    evaluator = AutoGenEvaluator(agent)
    card = evaluator.get_agent_card()

    assert card["card_version"] == "2.0"
    assert card["name"] == "test-agent"


def test_autogen_evaluator_evaluate_l0():
    """Test L0 evaluation."""
    agent = MockAutoGenAgent()
    evaluator = AutoGenEvaluator(agent)
    result = evaluator.evaluate_l0()

    assert result["level"] == "L0"
    assert result["name"] == "Fast-Screen"
    assert "status" in result
    assert "stages" in result
    assert "elapsed_seconds" in result


def test_autogen_evaluator_evaluate_l1():
    """Test L1 evaluation."""
    agent = MockAutoGenAgent()
    evaluator = AutoGenEvaluator(agent)
    result = evaluator.evaluate_l1()

    assert result["level"] == "L1"
    assert "score" in result
    assert "grade" in result
    assert "verdict" in result
    assert "domain_scores" in result


def test_autogen_evaluator_evaluate_invalid_level():
    """Test evaluation with invalid level."""
    agent = MockAutoGenAgent()
    evaluator = AutoGenEvaluator(agent)

    with pytest.raises(ValueError, match="Unsupported evaluation level"):
        evaluator.evaluate(level="L5")


def test_autogen_adapter_with_custom_config():
    """Test adapter with custom configuration."""
    agent = MockAutoGenAgent()
    config = {
        "data_residency": "CN",
        "provider": "anthropic",
        "model": "claude-3-opus",
        "circuit_breaker_enabled": False,
    }
    adapter = AutoGenAdapter(agent, config)
    card = adapter.to_agent_card()

    assert card["compliance"]["data_residency"] == "CN"
    assert card["model_backend"]["provider"] == "anthropic"
    assert card["model_backend"]["model"] == "claude-3-opus"
    assert card["governance"]["circuit_breaker"]["enabled"] is False
