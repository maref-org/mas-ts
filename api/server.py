# SPDX-FileCopyrightText: 2026 maref-org
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
from mas_eval.scoring.slo import check_slo, get_level_slo_summary

from .error_codes import ERR_MAP, build_error_response
from .metrics import (
    EVALUATION_COUNT,
    PrometheusMiddleware,
    metrics_response,
    update_hitl_gauge,
)
from .ratelimit import RateLimitMiddleware
from .schemas import EvaluationRequest, EvaluationResponse
from .security_headers import SecurityHeadersMiddleware
from .tracing import TRACE_ID_HEADER, TracingMiddleware

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

# Middleware order (outermost first): Tracing → Security → RateLimit → CORS → Prometheus
app.add_middleware(TracingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    rate=float(os.environ.get("RATE_LIMIT_RATE", "100.0")),
    burst=int(os.environ.get("RATE_LIMIT_BURST", "50")),
)
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.split(",") if CORS_ORIGINS else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", TRACE_ID_HEADER],
)
app.add_middleware(PrometheusMiddleware)

# Optional Basic Auth for /metrics endpoint (R5 OPS — defense in depth).
# Enabled only when METRICS_BASIC_AUTH env var is set (format: "user:pass").
# In dev mode (env var unset) the endpoint is open for local inspection.
_security = HTTPBasic(auto_error=False)


def _error(code: str, detail: str | None = None) -> HTTPException:
    entry = ERR_MAP.get(code, ERR_MAP["internal_error"])
    status_code = int(entry["http_status"])
    return HTTPException(
        status_code=status_code,
        detail=build_error_response(code, detail),
    )


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


@app.get("/slo-status", tags=["Observability"])
async def slo_status():
    """SLO error budget status across all levels.
    Returns current violation counts, budget remaining, and burn rates.
    """
    levels = {}
    for level in ["L0", "L1", "L2", "L3", "L4"]:
        levels[level] = get_level_slo_summary(level)
    return {"service": "MAS-TS Evaluation API", "levels": levels}


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
            raise _error("invalid_level", f"Invalid evaluation level: {level}. Must be L0-L4.")

        return _convert_to_response(result)
    except HTTPException:
        raise
    except Exception as e:
        EVALUATION_COUNT.labels(level=level, verdict="FAILED").inc()
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        raise _error("evaluation_failed", str(e))


def _evaluate_common(level: str, request: EvaluationRequest) -> dict:
    card = request.agent_card.model_dump()
    level_upper = level.upper()
    try:
        if level_upper == "L0":
            result = run_l0_fast_screen(card, request.tasks)
        elif level_upper == "L1":
            result = run_l1_standard(card, request.golden_trajectory)
        elif level_upper == "L2":
            result = run_l2_deep(card)
        elif level_upper == "L3":
            result = run_l3_comprehensive(card)
        elif level_upper == "L4":
            result = run_l4_evolution(card)
        else:
            raise _error("invalid_level", f"Invalid evaluation level: {level}. Must be L0-L4.")
        return result
    except HTTPException:
        raise
    except Exception as e:
        EVALUATION_COUNT.labels(level=level_upper, verdict="FAILED").inc()
        logger.error(f"{level_upper} evaluation failed: {e}", exc_info=True)
        raise _error("evaluation_failed", str(e))


@app.post("/evaluate/l0", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_l0(request: EvaluationRequest):
    result = _evaluate_common("L0", request)
    return _convert_to_response(result)


@app.post("/evaluate/l1", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_l1(request: EvaluationRequest):
    result = _evaluate_common("L1", request)
    return _convert_to_response(result)


@app.post("/evaluate/l2", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_l2(request: EvaluationRequest):
    result = _evaluate_common("L2", request)
    return _convert_to_response(result)


@app.post("/evaluate/l3", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_l3(request: EvaluationRequest):
    result = _evaluate_common("L3", request)
    return _convert_to_response(result)


@app.post("/evaluate/l4", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_l4(request: EvaluationRequest):
    result = _evaluate_common("L4", request)
    return _convert_to_response(result)


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
        raise _error("task_not_found", f"HITL task {task_id} not found")
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
        raise _error("task_not_found", f"HITL task {task_id} not found")
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
        raise _error("task_not_found", f"HITL task {task_id} not found")
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

    level = result.get("level", "L0")
    domain_results = result.get("domains") or {}
    if domain_results:
        from mas_eval.harness.aggregation import extract_gold_metrics
        gm = extract_gold_metrics(domain_results)
        if gm:
            check_slo(gm, level=str(level))
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
