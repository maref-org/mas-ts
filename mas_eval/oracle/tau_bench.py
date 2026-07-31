# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS-001 v3.0 — Tau-Bench Oracle.

Executable benchmark for tool-use conversation tasks. Provides
pre-defined golden trajectories and task completion scoring.

Tasks: airline, hotel, restaurant, weather, news, product, schedule.

Usage:
    from mas_eval.oracle.tau_bench import TauBenchOracle
    OracleRegistry.register(TauBenchOracle())
    result = run_d2_with_oracle(card, "tau-bench", "tau-bench-airline-001")
"""

import json
import logging
from pathlib import Path

from mas_eval.oracle.oracle_base import Oracle, OracleTask

logger = logging.getLogger(__name__)

TASKS_FILE = Path(__file__).parent / "data" / "tau_bench_tasks.json"


class TauBenchOracle(Oracle):
    """Pre-defined golden trajectories for tool-use conversation tasks."""

    def __init__(self):
        self._tasks_cache = None

    @property
    def name(self):
        return "tau-bench"

    def list_tasks(self):
        tasks = self._load_tasks()
        return [
            OracleTask(
                task_id=t["task_id"],
                prompt=t["prompt"],
                expected_tools=t.get("expected_tools", []),
                rubric=t.get("rubric", {}),
                metadata={
                    "domain": t.get("domain", ""),
                    "expected_steps": t.get("expected_steps", 0),
                },
            )
            for t in tasks
        ]

    def execute(self, task, agent_card):
        tasks = self._load_tasks()
        match = next((t for t in tasks if t["task_id"] == task.task_id), None)
        if match is None:
            logger.warning("Task %r not found in tau-bench tasks", task.task_id)
            return {"events": []}
        return match.get("golden_trajectory", {"events": []})

    def validate_environment(self):
        if TASKS_FILE.exists():
            return True, f"tasks loaded from {TASKS_FILE.name}"
        return False, f"{TASKS_FILE.name} not found"

    def score(self, task, agent_trajectory, golden_trajectory=None):
        """Tau-Bench scoring: 60% tool coverage + 40% task completion."""
        if not agent_trajectory:
            return 0.0

        events = self._get_events(agent_trajectory)
        if not events:
            return 0.0

        called_tools = {
            e.get("action", {}).get("tool_id")
            for e in events
            if e.get("action", {}).get("type") == "tool_call"
        }

        task_complete = any(
            e.get("action", {}).get("type") == "task_complete"
            and e.get("action", {}).get("result") == "success"
            for e in events
        )

        expected = set(task.expected_tools) if task.expected_tools else set()
        if not expected:
            return 100.0 if task_complete else 0.0

        tool_ratio = len(called_tools & expected) / len(expected)
        composite = tool_ratio * 60 + (100.0 if task_complete else 0.0) * 0.40
        return round(composite, 1)

    def _load_tasks(self):
        if self._tasks_cache is not None:
            return self._tasks_cache
        if not TASKS_FILE.exists():
            logger.warning("Tasks file not found: %s", TASKS_FILE)
            self._tasks_cache = []
            return self._tasks_cache
        with open(TASKS_FILE) as f:
            self._tasks_cache = json.load(f)
        return self._tasks_cache

    @staticmethod
    def _get_events(trajectory):
        if isinstance(trajectory, list):
            return trajectory
        if isinstance(trajectory, dict):
            return trajectory.get("events", [])
        return []
