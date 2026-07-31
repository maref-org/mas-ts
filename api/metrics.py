# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Prometheus metrics for MAS-TS Evaluation API (R5 OPS).

Exposes RED metrics (Rate, Errors, Duration) plus evaluation and HITL gauges.
Mounted at /metrics endpoint, scraped by Prometheus in production deployments.
"""

import time
from typing import Awaitable, Callable

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "mas_eval_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "mas_eval_http_request_duration_seconds",
    "HTTP request latency (seconds)",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
EVALUATION_COUNT = Counter(
    "mas_eval_evaluations_total",
    "Total evaluations run",
    ["level", "verdict"],
)
HITL_STATE_GAUGE = Gauge(
    "mas_eval_hitl_tasks",
    "HITL tasks by state",
    ["state"],
)

# Known HITL states (keeps label cardinality bounded)
_KNOWN_HITL_STATES = ("pending", "confirmed", "cancelled", "paused", "awaiting")


class PrometheusMiddleware(BaseHTTPMiddleware):
    """ASGI middleware recording RED metrics for every request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.time()
        # Use route pattern (e.g. "/hitl/{task_id}/cancel") instead of raw
        # path to avoid label cardinality explosion from dynamic segments.
        route = request.scope.get("route")
        endpoint = getattr(route, "path", None) or request.url.path
        # Default to 500 so exceptions propagating through call_next
        # (e.g., ResponseValidationError, unhandled errors in /health or
        # /hitl routes) are still recorded. ServerErrorMiddleware (outermost)
        # will convert the re-raised exception to a 500 response afterwards.
        status_code = "500"
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
        finally:
            elapsed = time.time() - start
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status=status_code,
            ).inc()
            REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(
                elapsed
            )


def metrics_response() -> Response:
    """Build the /metrics HTTP response with Prometheus exposition format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def update_hitl_gauge(states: dict[str, dict]) -> None:
    """Refresh HITL state gauge from in-memory _hitl_states.

    Sets all known states to current counts (zero when absent) so stale
    labels do not linger after state transitions. Unknown states (e.g.,
    typos) are also exposed to avoid silent metric loss. Iterates over a
    snapshot to avoid concurrent modification under async workloads.
    """
    counts: dict[str, int] = {}
    # Snapshot iteration (list) to avoid RuntimeError if the dict is
    # modified by an async HITL endpoint between scheduling points.
    for v in list(states.values()):
        s = v.get("state", "unknown") if isinstance(v, dict) else "unknown"
        counts[s] = counts.get(s, 0) + 1
    for s in _KNOWN_HITL_STATES:
        HITL_STATE_GAUGE.labels(state=s).set(counts.get(s, 0))
    # Expose unknown states too (e.g., typos) so they are visible in metrics
    for s, cnt in counts.items():
        if s not in _KNOWN_HITL_STATES:
            HITL_STATE_GAUGE.labels(state=s).set(cnt)
