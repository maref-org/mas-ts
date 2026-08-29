# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""L0 Fast-Screen CI Gate for MAS-TS-001 v3.0-GA.

6 stages, <5 minutes, zero LLM token cost.
Gold Standard: adds StepEfficiency fast-screen (v3.0-GA §9.1).
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from mas_eval.domains.d1_compliance import run_d1
from mas_eval.domains.d2_single_agent import run_d2, run_step_efficiency
from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.scoring.absolute import score_to_grade
from mas_eval.scoring.gold_thresholds import check_level_thresholds

logger = logging.getLogger(__name__)

L0_TIMEOUT_SECONDS = 300
L0_STAGES = [
    "card_validation",
    "constitution_check",
    "mock_tasks",
    "agent_spawn",
    "step_efficiency",
    "traffic_light",
]


def run_l0_fast_screen(card, tasks=None):
    """Run the L0 Fast-Screen CI gate (6 stages, <30s).

    Evaluates an agent card across 6 stages: card_validation, constitution_check,
    mock_tasks, step_efficiency, agent_spawn, and traffic_light.

    Gold Standard: StepEfficiency gate at L0 warns if optimality < 0.5.

    Args:
    card: Agent card dict.
    tasks: Optional list of task dicts for mock task stage.

    Returns:
    Dict with keys: level, name, elapsed_seconds, timeout, status, stages, summary.
    """
    start = time.time()
    stages = []

    t0 = time.time()
    card_validation = _stage_card_validation(card)
    card_validation["duration_ms"] = int((time.time() - t0) * 1000)
    stages.append(card_validation)

    if card_validation["status"] == "FAIL":
        return _l0_result(stages, start)

    golden, mock = _parse_trajectories(tasks)
    with ThreadPoolExecutor(max_workers=3) as executor:
        constitution_future = executor.submit(_stage_constitution_check, card)
        mock_tasks_future = executor.submit(_stage_mock_tasks, card, golden, mock)
        agent_spawn_future = executor.submit(_stage_agent_spawn, card, golden)

        t0 = time.time()
        constitution = constitution_future.result()
        constitution["duration_ms"] = int((time.time() - t0) * 1000)
        stages.append(constitution)

        t0 = time.time()
        mock_tasks = mock_tasks_future.result()
        mock_tasks["duration_ms"] = int((time.time() - t0) * 1000)
        stages.append(mock_tasks)

        t0 = time.time()
        agent_spawn = agent_spawn_future.result()
        agent_spawn["duration_ms"] = int((time.time() - t0) * 1000)
        stages.append(agent_spawn)

    t0 = time.time()
    step_eff = _stage_step_efficiency(mock_tasks.get("trajectory"))
    step_eff["duration_ms"] = int((time.time() - t0) * 1000)
    stages.append(step_eff)

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


def _parse_trajectories(tasks):
    """从 --tasks 数据中解析 golden/mock 轨迹。

    新格式: {"golden_trajectory": [events...], "mock_trajectory": [events...]}
    旧格式: {"tasks": [{"description": ...}]} → 无轨迹，返回 (None, None)。
    列表直接视为 golden（兼容旧调用方）。
    """
    if isinstance(tasks, dict):
        if "golden_trajectory" in tasks or "mock_trajectory" in tasks:
            return tasks.get("golden_trajectory"), tasks.get("mock_trajectory")
        return None, None
    if isinstance(tasks, list):
        return tasks, None
    return None, None


def _stage_mock_tasks(card, golden_trajectory=None, mock_trajectory=None):
    d2 = run_d2(card, golden_trajectory, mock_trajectory)
    score = d2.get("subscores", {}).get("task_completion", 0)
    traj_events = (
        golden_trajectory
        if isinstance(golden_trajectory, list)
        else (golden_trajectory or {}).get("events", [])
        if golden_trajectory
        else []
    )
    return {
        "stage": "mock_tasks",
        "status": "PASS" if score >= 70 else "WARNING",
        "score": score,
        "checks": ["d2.4"],
        "details": f"Mock task completion: {score:.1f}%",
        "trajectory": traj_events,
    }


def _stage_step_efficiency(trajectory_data):
    """Gold Standard L0 StepEfficiency gate (v3.0-GA §9.1, hardened).

    FAIL if step efficiency < 50 — L0 is a hard CI gate and must not allow
    agents with poor step efficiency to pass. Previously returned WARNING.
    """
    if not trajectory_data:
        return {
            "stage": "step_efficiency",
            "status": "SKIP",
            "score": 0,
            "checks": ["d2.5"],
            "details": "No trajectory data",
        }
    score, findings = run_step_efficiency(
        {"events": trajectory_data},
        {"expected_steps": "1-50"},
    )
    return {
        "stage": "step_efficiency",
        "status": "PASS" if score >= 50 else "FAIL",
        "score": score,
        "checks": ["d2.5"],
        "warnings": len([f for f in findings if f["severity"] == "WARNING"]),
        "details": f"StepEfficiency={score:.1f}"
        + (f" ({findings[-1]['detail']})" if findings else ""),
    }


def _stage_agent_spawn(card, golden_trajectory=None):
    d3 = run_d3(card, golden_trajectory=golden_trajectory)
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

    # 提取金标阈值检查所需的指标，并把各 stage 分数映射到 D1/D2/D3 域
    metrics = {}
    domain_scores = {}
    all_findings = []
    for stage in stages:
        if stage["stage"] == "card_validation":
            metrics["d1_compliance"] = stage["score"]
            domain_scores["d1"] = stage["score"]
        elif stage["stage"] == "step_efficiency" and stage["status"] != "SKIP":
            metrics["d2_step_efficiency"] = stage["score"] / 100.0
        elif stage["stage"] == "mock_tasks":
            metrics["d2_tool_coverage"] = stage["score"]
            domain_scores["d2"] = stage["score"]
        elif stage["stage"] == "agent_spawn":
            metrics["d3_spawn_rate"] = stage["score"]
            domain_scores["d3"] = stage["score"]
        all_findings.extend(stage.get("findings", []))

    # 执行金标阈值检查
    threshold_check = check_level_thresholds(metrics, level="L0")

    from mas_eval.scoring.absolute import (
        compute_overall,
        determine_verdict,
        score_to_grade,
    )

    overall = compute_overall(**domain_scores)

    return {
        "level": "L0",
        "name": "Fast-Screen",
        "elapsed_seconds": round(elapsed, 1),
        "timeout": L0_TIMEOUT_SECONDS,
        "status": stages[-1]["status"] if stages else "FAIL",
        "score": overall,
        "grade": score_to_grade(overall),
        "verdict": determine_verdict(overall, findings=all_findings),
        "domain_scores": domain_scores,
        "stages": stages,
        "summary": {s["stage"]: s["status"] for s in stages},
        "threshold_check": threshold_check,
        "findings": all_findings,
    }
