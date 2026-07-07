"""Observability configuration for MAS-TS Evaluation API.

Centralized logging, metrics, and tracing configuration.
"""

import json
import logging
import logging.config
import os
import time
from typing import Any, Dict

from prometheus_client import Counter, Gauge, Histogram

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.environ.get("LOG_FORMAT", "json")

DOMAIN_EVALUATION_TIME = Histogram(
    "mas_eval_domain_duration_seconds",
    "Domain evaluation duration",
    ["domain"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0),
)

DOMAIN_SCORE = Histogram(
    "mas_eval_domain_score",
    "Domain evaluation score distribution",
    ["domain"],
    buckets=(0, 20, 40, 60, 80, 90, 95, 100),
)

MEMORY_USAGE = Gauge(
    "mas_eval_memory_usage_bytes",
    "Process memory usage",
)

ACTIVE_EVALUATIONS = Gauge(
    "mas_eval_active_evaluations",
    "Number of active evaluations",
    ["level"],
)

FINDINGS_COUNTER = Counter(
    "mas_eval_findings_total",
    "Total findings by severity",
    ["severity"],
)

CACHE_HIT_RATE = Counter(
    "mas_eval_cache_operations",
    "Cache operations",
    ["operation"],
)


def configure_logging() -> None:
    """Configure structured logging for the application."""
    log_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)d %(message)s",
            },
            "text": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": LOG_FORMAT,
                "level": LOG_LEVEL,
            },
        },
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": LOG_LEVEL,
                "propagate": True,
            },
            "mas_eval": {
                "handlers": ["console"],
                "level": LOG_LEVEL,
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": LOG_LEVEL,
                "propagate": False,
            },
        },
    }
    logging.config.dictConfig(log_config)


def log_evaluation_start(level: str, agent_id: str) -> Dict[str, Any]:
    """Log evaluation start with structured metadata."""
    logger = logging.getLogger("mas_eval.observability")
    logger.info(
        json.dumps(
            {
                "event": "evaluation_start",
                "level": level,
                "agent_id": agent_id,
                "timestamp": time.time(),
            }
        )
    )
    ACTIVE_EVALUATIONS.labels(level=level).inc()
    return {"level": level, "agent_id": agent_id}


def log_evaluation_end(
    level: str, agent_id: str, score: float, verdict: str, elapsed: float
) -> None:
    """Log evaluation end with structured metadata."""
    logger = logging.getLogger("mas_eval.observability")
    logger.info(
        json.dumps(
            {
                "event": "evaluation_end",
                "level": level,
                "agent_id": agent_id,
                "score": score,
                "verdict": verdict,
                "elapsed_seconds": elapsed,
                "timestamp": time.time(),
            }
        )
    )
    ACTIVE_EVALUATIONS.labels(level=level).dec()


def record_domain_metrics(domain: str, score: float, duration_seconds: float) -> None:
    """Record domain-specific metrics."""
    DOMAIN_EVALUATION_TIME.labels(domain=domain).observe(duration_seconds)
    DOMAIN_SCORE.labels(domain=domain).observe(score)


def record_findings(findings: list[Dict[str, Any]]) -> None:
    """Record findings count by severity."""
    for finding in findings:
        severity = finding.get("severity", "INFO")
        FINDINGS_COUNTER.labels(severity=severity).inc()
