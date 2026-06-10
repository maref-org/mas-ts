# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS-001 v3.0 — Oracle Base Framework.

Defines the Oracle ABC for executable benchmark oracles that generate
golden trajectories dynamically. Integrates with D2 run_task_completion.

Usage:
    class MyOracle(Oracle):
        @property
        def name(self):
            return "my-bench"
        def list_tasks(self):
            return [OracleTask("t1", "Do X")]
        def execute(self, task, card):
            return {"events": [...]}
        def validate_environment(self):
            return True, "ready"

    OracleRegistry.register(MyOracle())
    result = run_d2_with_oracle(card, "my-bench", "t1", mock_trajectory)
"""

import logging
from abc import ABC, abstractmethod

from mas_eval.domains.d2_single_agent import run_d2

logger = logging.getLogger(__name__)

TRAJECTORY_EVENTS_KEY = "events"
"""Key used in trajectory dicts for the event list."""


class OracleTask:
    """A single task definition for an executable oracle benchmark."""

    def __init__(
        self, task_id, prompt, expected_tools=None, rubric=None, metadata=None
    ):
        self.task_id = task_id
        self.prompt = prompt
        self.expected_tools = expected_tools or []
        self.rubric = rubric or {}
        self.metadata = metadata or {}

    def __repr__(self):
        return f"OracleTask({self.task_id})"


class Oracle(ABC):
    """Abstract base for executable benchmark oracles.

    Subclasses must implement name, list_tasks, execute, and
    validate_environment. Optionally override score() for benchmark-
    specific metrics (e.g., SWE-bench resolve_rate).
    """

    @property
    @abstractmethod
    def name(self):
        """Human-readable oracle name (used as registry key)."""

    @abstractmethod
    def list_tasks(self):
        """Return list of OracleTask instances this oracle supports."""

    @abstractmethod
    def execute(self, task, agent_card):
        """Run the task and return a golden trajectory.

        Returns a dict with key "events" containing a list of event
        dicts, each with at minimum:
          action: {type, tool_id, input}
          orchestration: {routing_decision, routing_reason}

        Compatible with run_task_completion() golden_trajectory param.
        """

    @abstractmethod
    def validate_environment(self):
        """Check if the execution environment is ready.

        Returns (ok: bool, message: str).
        """

    def score(self, task, agent_trajectory, golden_trajectory=None):
        """Optional benchmark-specific scoring.

        Return a float 0-100 or None to fall back to
        run_task_completion's generic trajectory comparison.
        """
        return None


class OracleRegistry:
    """Global registry of executable oracles.

    Usage:
        OracleRegistry.register(MyOracle())
        oracle = OracleRegistry.get("my-bench")
    """

    _oracles: dict = {}

    @classmethod
    def register(cls, oracle):
        if oracle.name in cls._oracles:
            logger.warning("Oracle %r already registered, overwriting", oracle.name)
        cls._oracles[oracle.name] = oracle

    @classmethod
    def get(cls, name):
        return cls._oracles.get(name)

    @classmethod
    def list(cls):
        return list(cls._oracles.keys())

    @classmethod
    def clear(cls):
        cls._oracles.clear()


def run_d2_with_oracle(card, oracle_name, task_id=None, mock_trajectory=None):
    """Run D2 evaluation using an oracle-generated golden trajectory.

    Args:
        card: Agent card dict.
        oracle_name: Registered oracle name.
        task_id: Specific task ID (uses first task if None).
        mock_trajectory: Agent's execution trajectory for comparison.

    Returns:
        D2 result dict (same as run_d2) with oracle metadata appended.
    """
    oracle = OracleRegistry.get(oracle_name)
    if oracle is None:
        raise ValueError(
            f"Oracle {oracle_name!r} not registered. Available: {OracleRegistry.list()}"
        )

    tasks = oracle.list_tasks()
    if not tasks:
        raise ValueError(f"Oracle {oracle_name!r} has no tasks")

    task = None
    if task_id:
        task = next((t for t in tasks if t.task_id == task_id), None)
        if task is None:
            raise ValueError(
                f"Task {task_id!r} not found in oracle {oracle_name!r}. "
                f"Available: {[t.task_id for t in tasks]}"
            )
    else:
        task = tasks[0]

    env_ok, env_msg = oracle.validate_environment()
    golden = oracle.execute(task, card)

    result = run_d2(card, golden, mock_trajectory)

    oracle_score = oracle.score(task, mock_trajectory, golden)
    if oracle_score is not None:
        result["subscores"]["oracle_score"] = oracle_score

    result["findings"].append(
        {
            "severity": "INFO",
            "category": "oracle",
            "detail": f"Oracle {oracle_name!r} task {task.task_id!r} — env: {env_msg}",
        }
    )

    result["summary"]["oracle_name"] = oracle_name
    result["summary"]["oracle_task"] = task.task_id
    result["summary"]["oracle_env_ok"] = env_ok

    return result
