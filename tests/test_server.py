# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for FastAPI server endpoints (MAS-TS-001 API).

Covers: /health, /hitl/{task_id}/cancel|confirm|pause (R3 P0 — §5.1.3)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

# TestClient requires httpx; skip entire module if not installed
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from api.server import _hitl_states, app

client = TestClient(app)


class TestHealthEndpoints:
    """Basic health check endpoints."""

    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "MAS-TS Evaluation API"
        assert data["status"] == "healthy"

    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestHitlCancel:
    """Tests for POST /hitl/{task_id}/cancel endpoint."""

    def test_cancel_not_found(self):
        """Cancelling a non-existent task should return 404."""
        response = client.post("/hitl/nonexistent-task/cancel")
        assert response.status_code == 404

    def test_cancel_success(self):
        """Cancelling an existing task should succeed."""
        _hitl_states["task-cancel-1"] = {"state": "pending"}
        response = client.post("/hitl/task-cancel-1/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "cancel"
        assert data["new_state"] == "cancelled"
        assert data["previous_state"] == "pending"
        assert "timestamp" in data
        _hitl_states.clear()

    def test_cancel_returns_task_id(self):
        """Response should include the task_id."""
        _hitl_states["task-cancel-2"] = {"state": "awaiting"}
        response = client.post("/hitl/task-cancel-2/cancel")
        data = response.json()
        assert data["task_id"] == "task-cancel-2"
        _hitl_states.clear()


class TestHitlConfirm:
    """Tests for POST /hitl/{task_id}/confirm endpoint."""

    def test_confirm_not_found(self):
        """Confirming a non-existent task should return 404."""
        response = client.post("/hitl/nonexistent-task/confirm")
        assert response.status_code == 404

    def test_confirm_success(self):
        """Confirming an existing task should succeed."""
        _hitl_states["task-confirm-1"] = {"state": "pending"}
        response = client.post("/hitl/task-confirm-1/confirm")
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "confirm"
        assert data["new_state"] == "confirmed"
        _hitl_states.clear()


class TestHitlPause:
    """Tests for POST /hitl/{task_id}/pause endpoint."""

    def test_pause_not_found(self):
        """Pausing a non-existent task should return 404."""
        response = client.post("/hitl/nonexistent-task/pause")
        assert response.status_code == 404

    def test_pause_success(self):
        """Pausing an existing task should succeed."""
        _hitl_states["task-pause-1"] = {"state": "pending"}
        response = client.post("/hitl/task-pause-1/pause")
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "pause"
        assert data["new_state"] == "paused"
        _hitl_states.clear()


class TestHitlStateTransitions:
    """Tests for HITL state transition sequences."""

    def test_confirm_after_pause(self):
        """Confirming after pause should update state correctly."""
        _hitl_states["task-seq-1"] = {"state": "pending"}
        # First pause
        r1 = client.post("/hitl/task-seq-1/pause")
        assert r1.json()["new_state"] == "paused"
        assert r1.json()["previous_state"] == "pending"
        # Then confirm
        r2 = client.post("/hitl/task-seq-1/confirm")
        assert r2.json()["new_state"] == "confirmed"
        assert r2.json()["previous_state"] == "paused"
        _hitl_states.clear()

    def test_cancel_after_confirm(self):
        """Cancelling after confirm should update state correctly."""
        _hitl_states["task-seq-2"] = {"state": "pending"}
        client.post("/hitl/task-seq-2/confirm")
        r = client.post("/hitl/task-seq-2/cancel")
        assert r.json()["new_state"] == "cancelled"
        assert r.json()["previous_state"] == "confirmed"
        _hitl_states.clear()

    def test_timestamp_is_iso_format(self):
        """Timestamp should be a non-empty ISO 8601 string."""
        _hitl_states["task-ts-1"] = {"state": "pending"}
        response = client.post("/hitl/task-ts-1/cancel")
        ts = response.json()["timestamp"]
        assert isinstance(ts, str)
        assert len(ts) > 10  # at least some date-like content
        _hitl_states.clear()


class TestMetricsEndpoint:
    """Tests for GET /metrics endpoint (R5 OPS — Prometheus)."""

    def test_metrics_returns_200(self):
        """GET /metrics should return HTTP 200."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_content_type(self):
        """/metrics should return Prometheus exposition format (text/plain)."""
        response = client.get("/metrics")
        assert "text/plain" in response.headers.get("content-type", "")

    def test_metrics_exposes_request_count(self):
        """/metrics should expose mas_eval_http_requests_total Counter."""
        # Trigger a request first so the counter has at least one sample
        client.get("/health")
        response = client.get("/metrics")
        assert b"mas_eval_http_requests_total" in response.content

    def test_metrics_exposes_request_latency(self):
        """/metrics should expose mas_eval_http_request_duration_seconds Histogram."""
        client.get("/health")
        response = client.get("/metrics")
        assert b"mas_eval_http_request_duration_seconds" in response.content

    def test_metrics_exposes_evaluation_count(self):
        """/metrics should expose mas_eval_evaluations_total Counter."""
        response = client.get("/metrics")
        assert b"mas_eval_evaluations_total" in response.content

    def test_metrics_exposes_hitl_gauge(self):
        """/metrics should expose mas_eval_hitl_tasks Gauge."""
        response = client.get("/metrics")
        assert b"mas_eval_hitl_tasks" in response.content

    def test_metrics_records_request_after_call(self):
        """After a /health call, REQUEST_COUNT should include a /health sample."""
        response = client.get("/metrics")
        content = response.content.decode()
        # After prior tests, /health and /metrics entries should exist
        assert "mas_eval_http_requests_total" in content


class TestHitlGaugeUpdate:
    """Tests for HITL_STATE_GAUGE refresh on /metrics call (R5 OPS)."""

    def test_hitl_gauge_reflects_pending_state(self):
        """Gauge should reflect pending task count after /metrics call."""
        _hitl_states["task-gauge-1"] = {"state": "pending"}
        _hitl_states["task-gauge-2"] = {"state": "confirmed"}
        response = client.get("/metrics")
        content = response.content.decode()
        assert 'mas_eval_hitl_tasks{state="pending"} 1.0' in content
        assert 'mas_eval_hitl_tasks{state="confirmed"} 1.0' in content
        _hitl_states.clear()

    def test_hitl_gauge_zero_when_no_tasks(self):
        """Gauge should show 0 for all states when no HITL tasks exist."""
        _hitl_states.clear()
        response = client.get("/metrics")
        content = response.content.decode()
        assert 'mas_eval_hitl_tasks{state="pending"} 0.0' in content
        assert 'mas_eval_hitl_tasks{state="cancelled"} 0.0' in content
