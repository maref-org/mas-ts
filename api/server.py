# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""FastAPI server for MAS-TS Evaluation API."""

import datetime
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from mas_eval.harness.l0_fast_screen import run_l0_fast_screen
from mas_eval.harness.l1_standard import run_l1_standard
from mas_eval.harness.l2_deep import run_l2_deep
from mas_eval.harness.l3_comprehensive import run_l3_comprehensive
from mas_eval.harness.l4_evolution import run_l4_evolution

from .metrics import (
    EVALUATION_COUNT,
    PrometheusMiddleware,
    metrics_response,
    update_hitl_gauge,
)
from .schemas import EvaluationRequest, EvaluationResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for the FastAPI app."""
    logger.info("MAS-TS Evaluation API v1.0 starting...")
    yield
    logger.info("MAS-TS Evaluation API v1.0 shutting down...")


app = FastAPI(
    title="MAS-TS Evaluation API",
    description="RESTful API for agent evaluation using MAS-TS harness",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Prometheus middleware added after CORS so it wraps outermost (records all requests)
app.add_middleware(PrometheusMiddleware)

# Optional Basic Auth for /metrics endpoint (R5 OPS — defense in depth).
# Enabled only when METRICS_BASIC_AUTH env var is set (format: "user:pass").
# In dev mode (env var unset) the endpoint is open for local inspection.
_security = HTTPBasic(auto_error=False)


def _optional_metrics_auth(
    credentials: HTTPBasicCredentials = Depends(_security),
) -> None:
    """Optional Basic Auth guard for /metrics.

    Set ``METRICS_BASIC_AUTH=user:pass`` in the environment to enable.
    Absent env var ⇒ auth disabled (dev-friendly). Mismatched creds ⇒ 401.
    """
    expected = os.environ.get("METRICS_BASIC_AUTH")
    if not expected:
        return  # Auth disabled in dev
    if not credentials or f"{credentials.username}:{credentials.password}" != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Metrics endpoint requires authentication",
            headers={"WWW-Authenticate": "Basic"},
        )


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint for health check."""
    return {
        "service": "MAS-TS Evaluation API",
        "version": "1.0.0",
        "status": "healthy",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/metrics", tags=["Observability"])
async def metrics(_: None = Depends(_optional_metrics_auth)):
    """Prometheus metrics endpoint (R5 OPS).

    Exposes RED metrics (request count/latency), evaluation count, and
    HITL task gauge. Scraped by Prometheus in production deployments.
    Production deployments should set ``METRICS_BASIC_AUTH=user:pass`` env
    var to enable Basic Auth (see operations-readiness.md Runbook §8).
    """
    update_hitl_gauge(_hitl_states)
    return metrics_response()


@app.post("/evaluate", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_agent(request: EvaluationRequest):
    """Evaluate an agent at specified level.

    Args:
        request: Evaluation request containing agent card and parameters.

    Returns:
        Evaluation response with results.

    Raises:
        HTTPException: If evaluation fails or level is invalid.
    """
    card = request.agent_card.model_dump()
    level = request.level.upper()

    try:
        if level == "L0":
            result = run_l0_fast_screen(card, request.tasks)
        elif level == "L1":
            result = run_l1_standard(card, request.golden_trajectory)
        elif level == "L2":
            result = run_l2_deep(card)
        elif level == "L3":
            result = run_l3_comprehensive(card)
        elif level == "L4":
            result = run_l4_evolution(card)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_level",
                    "message": f"Invalid evaluation level: {level}. Must be L0-L4.",
                },
            )

        return _convert_to_response(result)
    except HTTPException:
        raise
    except Exception as e:
        # Record evaluation failure so failure rate is observable via metrics
        EVALUATION_COUNT.labels(level=level, verdict="FAILED").inc()
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {str(e)}",
        )


@app.post("/evaluate/l0", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_l0(request: EvaluationRequest):
    """Evaluate an agent at L0 Fast-Screen level.

    Args:
        request: Evaluation request containing agent card.

    Returns:
        L0 evaluation response.
    """
    try:
        card = request.agent_card.model_dump()
        result = run_l0_fast_screen(card, request.tasks)
        return _convert_to_response(result)
    except Exception as e:
        EVALUATION_COUNT.labels(level="L0", verdict="FAILED").inc()
        logger.error(f"L0 evaluation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"L0 evaluation failed: {str(e)}",
        )


@app.post("/evaluate/l1", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_l1(request: EvaluationRequest):
    """Evaluate an agent at L1 Standard level.

    Args:
        request: Evaluation request containing agent card.

    Returns:
        L1 evaluation response.
    """
    try:
        card = request.agent_card.model_dump()
        result = run_l1_standard(card, request.golden_trajectory)
        return _convert_to_response(result)
    except Exception as e:
        EVALUATION_COUNT.labels(level="L1", verdict="FAILED").inc()
        logger.error(f"L1 evaluation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"L1 evaluation failed: {str(e)}",
        )


@app.post("/evaluate/l2", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_l2(request: EvaluationRequest):
    """Evaluate an agent at L2 Deep level.

    Args:
        request: Evaluation request containing agent card.

    Returns:
        L2 evaluation response.
    """
    try:
        card = request.agent_card.model_dump()
        result = run_l2_deep(card)
        return _convert_to_response(result)
    except Exception as e:
        EVALUATION_COUNT.labels(level="L2", verdict="FAILED").inc()
        logger.error(f"L2 evaluation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"L2 evaluation failed: {str(e)}",
        )


@app.post("/evaluate/l3", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_l3(request: EvaluationRequest):
    """Evaluate an agent at L3 Comprehensive level.

    Args:
        request: Evaluation request containing agent card.

    Returns:
        L3 evaluation response.
    """
    try:
        card = request.agent_card.model_dump()
        result = run_l3_comprehensive(card)
        return _convert_to_response(result)
    except Exception as e:
        EVALUATION_COUNT.labels(level="L3", verdict="FAILED").inc()
        logger.error(f"L3 evaluation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"L3 evaluation failed: {str(e)}",
        )


@app.post("/evaluate/l4", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_l4(request: EvaluationRequest):
    """Evaluate an agent at L4 Evolution level.

    Args:
        request: Evaluation request containing agent card.

    Returns:
        L4 evaluation response.
    """
    try:
        card = request.agent_card.model_dump()
        result = run_l4_evolution(card)
        return _convert_to_response(result)
    except Exception as e:
        EVALUATION_COUNT.labels(level="L4", verdict="FAILED").inc()
        logger.error(f"L4 evaluation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"L4 evaluation failed: {str(e)}",
        )


# ── HITL (Human-in-the-Loop) interrupt endpoints (R3 P0 — Handbook §5.1.3) ──

# In-memory HITL state store (per-process; production should use Redis)
_hitl_states: Dict[str, dict] = {}


def _hitl_timestamp() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@app.post("/hitl/{task_id}/cancel", tags=["HITL"])
async def hitl_cancel(task_id: str):
    """Cancel a task awaiting HITL approval.

    Args:
        task_id: The task identifier awaiting human approval.

    Returns:
        Updated HITL state with action=cancel.

    Raises:
        HTTPException: 404 if task_id not found.
    """
    if task_id not in _hitl_states:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "task_not_found",
                "message": f"HITL task {task_id} not found",
            },
        )
    previous = _hitl_states[task_id].get("state", "unknown")
    ts = _hitl_timestamp()
    _hitl_states[task_id]["state"] = "cancelled"
    _hitl_states[task_id]["action"] = "cancel"
    _hitl_states[task_id]["updated_at"] = ts
    return {
        "task_id": task_id,
        "action": "cancel",
        "previous_state": previous,
        "new_state": "cancelled",
        "timestamp": ts,
    }


@app.post("/hitl/{task_id}/confirm", tags=["HITL"])
async def hitl_confirm(task_id: str):
    """Confirm a task awaiting HITL approval.

    Args:
        task_id: The task identifier awaiting human approval.

    Returns:
        Updated HITL state with action=confirm.

    Raises:
        HTTPException: 404 if task_id not found.
    """
    if task_id not in _hitl_states:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "task_not_found",
                "message": f"HITL task {task_id} not found",
            },
        )
    previous = _hitl_states[task_id].get("state", "unknown")
    ts = _hitl_timestamp()
    _hitl_states[task_id]["state"] = "confirmed"
    _hitl_states[task_id]["action"] = "confirm"
    _hitl_states[task_id]["updated_at"] = ts
    return {
        "task_id": task_id,
        "action": "confirm",
        "previous_state": previous,
        "new_state": "confirmed",
        "timestamp": ts,
    }


@app.post("/hitl/{task_id}/pause", tags=["HITL"])
async def hitl_pause(task_id: str):
    """Pause a task awaiting HITL approval.

    Args:
        task_id: The task identifier awaiting human approval.

    Returns:
        Updated HITL state with action=pause.

    Raises:
        HTTPException: 404 if task_id not found.
    """
    if task_id not in _hitl_states:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "task_not_found",
                "message": f"HITL task {task_id} not found",
            },
        )
    previous = _hitl_states[task_id].get("state", "unknown")
    ts = _hitl_timestamp()
    _hitl_states[task_id]["state"] = "paused"
    _hitl_states[task_id]["action"] = "pause"
    _hitl_states[task_id]["updated_at"] = ts
    return {
        "task_id": task_id,
        "action": "pause",
        "previous_state": previous,
        "new_state": "paused",
        "timestamp": ts,
    }


def _convert_to_response(result: Dict) -> EvaluationResponse:
    """Convert internal result dict to API response.

    Args:
        result: Internal evaluation result dict.

    Returns:
        EvaluationResponse model.
    """
    EVALUATION_COUNT.labels(
        level=str(result.get("level", "UNKNOWN")),
        verdict=str(result.get("verdict", "UNKNOWN")),
    ).inc()
    response_data = {
        "level": result.get("level", "UNKNOWN"),
        "name": result.get("name", "Evaluation"),
        "status": result.get("status", "UNKNOWN"),
        "score": result.get("score"),
        "grade": result.get("grade"),
        "verdict": result.get("verdict"),
        "elapsed_seconds": result.get("elapsed_seconds", 0),
        "stages": result.get("stages"),
        "domain_scores": result.get("domain_scores"),
        "findings": result.get("findings"),
        "summary": result.get("summary"),
    }
    return EvaluationResponse(**response_data)
