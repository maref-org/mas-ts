# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS Evaluation API."""

import pytest
from fastapi.testclient import TestClient

from api import app
from api.schemas import AgentCard, EvaluationRequest


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_agent_card():
    """Create sample agent card for testing."""
    return AgentCard(
        card_version="2.0",
        schema_version="2.0",
        agent_id="urn:agent:test:sample-agent:1234567890ab",
        name="test-agent",
        description="Test agent for API",
        version="0.1.0",
        compliance={
            "data_residency": "LOCAL",
            "data_classification": "internal",
            "cross_border": False,
            "model_backend_location": "LOCAL",
            "audit_trail_required": True,
        },
        constitution={
            "envelope": {
                "message_id": "msg-123",
                "correlation_id": "corr-123",
                "timestamp": "2026-06-22T00:00:00Z",
                "sender": "urn:agent:test:sample-agent:1234567890ab",
            },
            "health_state": "HEALTHY",
            "heartbeat_interval_seconds": 60,
        },
        model_backend={
            "provider": "test",
            "model": "test-model",
            "deployment": "local",
            "endpoint": "http://localhost:8000",
        },
        capabilities=[
            {
                "skill_id": "test-skill",
                "description": "Test skill",
                "input_schema": {},
                "output_schema": {},
                "examples": [],
            }
        ],
        authentication={
            "type": "None",
            "scopes": [],
        },
        federation={
            "role": "primary",
            "trust_score": 1.0,
        },
        governance={
            "state_machine_version": "1.0",
            "circuit_breaker": {
                "enabled": True,
                "threshold": 3,
                "cooldown_seconds": 30,
            },
        },
        audit={
            "trace_id_required": True,
            "timestamp_required": True,
            "source_agent_required": True,
            "target_agent_required": True,
        },
    )


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "MAS-TS Evaluation API"
    assert data["version"] == "1.0.0"
    assert data["status"] == "healthy"


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_evaluate_l0(client, sample_agent_card):
    """Test L0 evaluation endpoint."""
    request = EvaluationRequest(agent_card=sample_agent_card, level="L0")
    response = client.post("/evaluate/l0", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "L0"
    assert data["name"] == "Fast-Screen"
    assert "status" in data
    assert "stages" in data
    assert "elapsed_seconds" in data


def test_evaluate_l1(client, sample_agent_card):
    """Test L1 evaluation endpoint."""
    request = EvaluationRequest(agent_card=sample_agent_card, level="L1")
    response = client.post("/evaluate/l1", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "L1"
    assert "status" in data
    assert "domain_scores" in data


def test_evaluate_l2(client, sample_agent_card):
    """Test L2 evaluation endpoint."""
    request = EvaluationRequest(agent_card=sample_agent_card, level="L2")
    response = client.post("/evaluate/l2", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "L2"
    assert "status" in data


def test_evaluate_l3(client, sample_agent_card):
    """Test L3 evaluation endpoint."""
    request = EvaluationRequest(agent_card=sample_agent_card, level="L3")
    response = client.post("/evaluate/l3", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "L3"
    assert "status" in data


def test_evaluate_l4(client, sample_agent_card):
    """Test L4 evaluation endpoint."""
    request = EvaluationRequest(agent_card=sample_agent_card, level="L4")
    response = client.post("/evaluate/l4", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "L4"
    assert "status" in data


def test_evaluate_with_level(client, sample_agent_card):
    """Test evaluate endpoint with level parameter."""
    request = EvaluationRequest(agent_card=sample_agent_card, level="L0")
    response = client.post("/evaluate", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "L0"


def test_evaluate_invalid_level(client, sample_agent_card):
    """Test evaluate endpoint with invalid level."""
    request = EvaluationRequest(agent_card=sample_agent_card, level="L5")
    response = client.post("/evaluate", json=request.model_dump())

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], dict)
    assert data["detail"]["error"] == "invalid_level"
    assert "Invalid evaluation level" in data["detail"]["message"]


def test_evaluate_with_tasks(client, sample_agent_card):
    """Test L0 evaluation with tasks."""
    tasks = [{"task": "test-task"}]
    request = EvaluationRequest(agent_card=sample_agent_card, level="L0", tasks=tasks)
    response = client.post("/evaluate/l0", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "L0"


def test_evaluate_with_golden_trajectory(client, sample_agent_card):
    """Test L1 evaluation with golden trajectory."""
    golden_trajectory = [{"step": "test-step"}]
    request = EvaluationRequest(
        agent_card=sample_agent_card,
        level="L1",
        golden_trajectory=golden_trajectory,
    )
    response = client.post("/evaluate/l1", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "L1"
