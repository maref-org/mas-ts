# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""API request/response schemas for MASAS-TS Evaluation API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentCard(BaseModel):
    """Agent Card schema for API requests."""

    card_version: str = Field(..., description="Card format version")
    schema_version: Optional[str] = Field(None, description="Schema version identifier")
    agent_id: str = Field(..., description="URN-format agent identifier")
    name: str = Field(..., description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    version: str = Field(..., description="Semantic versioning")
    compliance: Dict[str, Any] = Field(..., description="Compliance configuration")
    constitution: Dict[str, Any] = Field(
        ..., description="Constitution compliance fields"
    )
    model_backend: Dict[str, Any] = Field(
        ..., description="Model backend configuration"
    )
    capabilities: List[Dict[str, Any]] = Field(..., description="Agent capabilities")
    authentication: Dict[str, Any] = Field(
        ..., description="Authentication configuration"
    )
    federation: Optional[Dict[str, Any]] = Field(
        None, description="Federation configuration"
    )
    governance: Optional[Dict[str, Any]] = Field(
        None, description="Governance configuration"
    )
    audit: Optional[Dict[str, Any]] = Field(None, description="Audit configuration")


class EvaluationRequest(BaseModel):
    """Evaluation request schema."""

    agent_card: AgentCard = Field(..., description="Agent card to evaluate")
    level: str = Field(default="L0", description="Evaluation level (L0-L4)")
    tasks: Optional[List[Dict[str, Any]]] = Field(
        None, description="Tasks for mock evaluation"
    )
    golden_trajectory: Optional[List[Dict[str, Any]]] = Field(
        None, description="Golden trajectory for comparison"
    )
    config: Optional[Dict[str, Any]] = Field(
        None, description="Additional evaluation configuration"
    )


class StageResult(BaseModel):
    """Stage evaluation result."""

    stage: str = Field(..., description="Stage name")
    status: str = Field(..., description="Stage status (PASS/WARNING/FAIL)")
    score: Optional[float] = Field(None, description="Stage score")
    duration_ms: Optional[int] = Field(
        None, description="Stage duration in milliseconds"
    )
    details: Optional[str] = Field(None, description="Stage details")


class EvaluationResponse(BaseModel):
    """Evaluation response schema."""

    level: str = Field(..., description="Evaluation level")
    name: str = Field(..., description="Evaluation name")
    status: str = Field(..., description="Overall status (PASS/WARNING/FAIL)")
    score: Optional[float] = Field(None, description="Overall score")
    grade: Optional[str] = Field(None, description="Letter grade")
    verdict: Optional[str] = Field(
        None, description="Verdict (APPROVED/CONDITIONAL/BLOCKED)"
    )
    elapsed_seconds: float = Field(..., description="Total elapsed time in seconds")
    stages: Optional[List[StageResult]] = Field(None, description="Stage results")
    domain_scores: Optional[Dict[str, float]] = Field(None, description="Domain scores")
    findings: Optional[List[Dict[str, Any]]] = Field(
        None, description="Evaluation findings"
    )
    summary: Optional[Dict[str, str]] = Field(
        None, description="Summary of stage statuses"
    )


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
