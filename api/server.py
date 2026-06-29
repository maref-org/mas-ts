# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""FastAPI server for MAS-TS Evaluation API."""

import logging
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from mas_eval.harness.l0_fast_screen import run_l0_fast_screen
from mas_eval.harness.l1_standard import run_l1_standard
from mas_eval.harness.l2_deep import run_l2_deep
from mas_eval.harness.l3_comprehensive import run_l3_comprehensive
from mas_eval.harness.l4_evolution import run_l4_evolution

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
        logger.error(f"L4 evaluation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"L4 evaluation failed: {str(e)}",
        )


def _convert_to_response(result: Dict) -> EvaluationResponse:
    """Convert internal result dict to API response.

    Args:
        result: Internal evaluation result dict.

    Returns:
        EvaluationResponse model.
    """
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
