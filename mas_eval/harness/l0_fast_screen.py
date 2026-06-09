# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""L0 Fast-Screen CI Gate for MAS-TS-001 v3.0.

5 stages, <5 minutes, zero LLM token cost.
"""

import logging
import time

from mas_eval.domains.d1_compliance import run_d1
from mas_eval.domains.d2_single_agent import run_d2
from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.scoring.absolute import score_to_grade

logger = logging.getLogger(__name__)

L0_TIMEOUT_SECONDS = 300
L0_STAGES = [
    "card_validation",
    "constitution_check",
    "mock_tasks",
    "agent_spawn",
    "traffic_light",
]


def run_l0_fast_screen(card, tasks=None):
    start = time.time()
    stages = []

    t0 = time.time()
    card_validation = _stage_card_validation(card)
    card_validation["duration_ms"] = int((time.time() - t0) * 1000)
    stages.append(card_validation)

    if card_validation["status"] == "FAIL":
        return _l0_result(stages, start)

    t0 = time.time()
    constitution = _stage_constitution_check(card)
    constitution["duration_ms"] = int((time.time() - t0) * 1000)
    stages.append(constitution)

    t0 = time.time()
    mock_tasks = _stage_mock_tasks(card, tasks)
    mock_tasks["duration_ms"] = int((time.time() - t0) * 1000)
    stages.append(mock_tasks)

    t0 = time.time()
    agent_spawn = _stage_agent_spawn(card)
    agent_spawn["duration_ms"] = int((time.time() - t0) * 1000)
    stages.append(agent_spawn)

    t0 = time.time()
    traffic_light = _stage_traffic_light(stages)
    traffic_light["duration_ms"] = int((time.time() - t0) * 1000)
    stages.append(traffic_light)

    return _l0_result(stages, start)


def _stage_card_validation(card):
    d1 = run_d1(card)
    score = d1["score"]
    errors = [f for f in d1.get("findings", []) if f.get("severity") == "CRITICAL"]
    return {
        "stage": "card_validation",
        "status": "PASS" if score >= 60 else "FAIL",
        "score": score,
        "checks": ["d1.1", "d1.2", "d1.3"],
        "errors": len(errors),
        "details": f"D1 score={score}, errors={len(errors)}",
    }


def _stage_constitution_check(card):
    d1_full = run_d1(card)
    findings = d1_full.get("findings", [])
    missing = [f for f in findings if "missing" in f.get("detail", "").lower()]
    return {
        "stage": "constitution_check",
        "status": "PASS" if len(missing) == 0 else "WARNING",
        "score": d1_full["score"],
        "checks": ["d1.4", "d1.5", "d1.6"],
        "warnings": len(missing),
        "details": f"Constitution checks: {len(missing)} missing fields",
    }


def _stage_mock_tasks(card, tasks=None):
    d2 = run_d2(card, tasks or [])
    score = d2.get("subscores", {}).get("task_completion", 0)
    return {
        "stage": "mock_tasks",
        "status": "PASS" if score >= 70 else "WARNING",
        "score": score,
        "checks": ["d2.4"],
        "details": f"Mock task completion: {score:.1f}%",
    }


def _stage_agent_spawn(card):
    d3 = run_d3(card)
    spawn_score = d3.get("subscores", {}).get("spawn", 0)
    return {
        "stage": "agent_spawn",
        "status": "PASS" if spawn_score >= 60 else "WARNING",
        "score": spawn_score,
        "checks": ["d3.2"],
        "details": f"Spawn score: {spawn_score:.1f}",
    }


def _stage_traffic_light(stages):
    all_pass = all(s["status"] == "PASS" for s in stages)
    any_fail = any(s["status"] == "FAIL" for s in stages)
    status = "PASS" if all_pass else ("FAIL" if any_fail else "WARNING")
    overall = sum(s["score"] for s in stages if s["status"] != "FAIL") / max(
        len(stages), 1
    )
    return {
        "stage": "traffic_light",
        "status": status,
        "score": round(overall, 1),
        "checks": [],
        "details": f"Overall: {status} ({score_to_grade(overall)})",
    }


def _l0_result(stages, start_time):
    elapsed = time.time() - start_time
    return {
        "level": "L0",
        "name": "Fast-Screen",
        "elapsed_seconds": round(elapsed, 1),
        "timeout": L0_TIMEOUT_SECONDS,
        "status": stages[-1]["status"] if stages else "FAIL",
        "stages": stages,
        "summary": {s["stage"]: s["status"] for s in stages},
    }
