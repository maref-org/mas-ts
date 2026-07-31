# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS Evaluation HTTP API v1.0.

RESTful API for agent evaluation using MAS-TS harness.
"""

from .schemas import (
    AgentCard,
    ErrorResponse,
    EvaluationRequest,
    EvaluationResponse,
)
from .server import app, lifespan

__all__ = [
    "app",
    "lifespan",
    "AgentCard",
    "EvaluationRequest",
    "EvaluationResponse",
    "ErrorResponse",
]
__version__ = "1.0.0"
