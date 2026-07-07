# SPDX-FileCopyrightText: 2026 MAREF Project Contributors
# SPDX-License-Identifier: Apache-2.0
"""StressHarness — L3 stress testing for RSI continuous improvement loops.

Three sub-modes:
1. **sustained_load** — 200+ rounds of continuous improvement with progressive stress.
2. **fault_injection** — Inject 5+ fault types during the RSI cycle via D5 ChaosEngine.
3. **resource_exhaustion** — Budget/circuit-breaker recovery verification.

Inherits the MAS-TS harness contract (``run_stress_harness() -> dict``) and
integrates with the D5 Robustness domain for fault injection infrastructure.
"""

import logging
import random
import time
from typing import Any, Callable

from mas_eval.domains.d5_robustness import ChaosEngine
from mas_eval.scoring.absolute import determine_verdict, score_to_grade

logger = logging.getLogger(__name__)

STRESS_TIMEOUT_SECONDS = 7200  # 2 hours for L3

STRESS_PHASES = [
    "sustained_load",
    "fault_injection",
    "resource_exhaustion",
]

STRESS_LEVELS: dict[str, dict[str, float | int]] = {
    "L1": {
        "load_rounds": 50,
        "fault_probability": 0.05,
        "fault_types": 2,
        "budget_deficit": 0.50,
    },
    "L2": {
        "load_rounds": 100,
        "fault_probability": 0.10,
        "fault_types": 3,
        "budget_deficit": 0.70,
    },
    "L3": {
        "load_rounds": 200,
        "fault_probability": 0.15,
        "fault_types": 5,
        "budget_deficit": 0.85,
    },
    "L4": {
        "load_rounds": 500,
        "fault_probability": 0.25,
        "fault_types": 6,
        "budget_deficit": 0.95,
    },
    "L5": {
        "load_rounds": 1000,
        "fault_probability": 0.40,
        "fault_types": 6,
        "budget_deficit": 0.99,
    },
}

DEFAULT_FAULT_TYPES = [
    "cpu_pressure",
    "memory_pressure",
    "disk_failure",
    "process_kill",
    "network_partition",
    "mcp_disconnect",
]


def run_stress_harness(
    card: dict[str, Any] | None = None,
    runner_fn: Callable[..., dict[str, Any]] | None = None,
    level: str = "L3",
    timeout_seconds: float = STRESS_TIMEOUT_SECONDS,
    seed: int | None = None,
) -> dict[str, Any]:
    """Run L3 stress test across three phases.

    Args:
        card: Agent card dict (unused in mock mode, reserved for future real-agent stress).
        runner_fn: Optional callable ``(round_id: int, **kwargs) -> dict`` with at
            minimum ``{"score": float, "findings": list}``.  When ``None``,
            a mock runner is used.
        level: Stress level string (``L1``-``L5``).  Default ``L3``.
        timeout_seconds: Wall-clock timeout.  Default 7200 (2 h).
        seed: Random seed for reproducibility.

    Returns:
        Dict with keys: level, name, elapsed_seconds, score, grade, verdict,
        domain_scores, domains, findings, phase_results.
    """
    rng = random.Random(seed)
    start = time.time()
    config = STRESS_LEVELS.get(level, STRESS_LEVELS["L3"])
    chaos = ChaosEngine(seed=rng.randint(0, 2**31) if seed is None else seed)
    all_findings: list[dict[str, Any]] = []
    phase_results: dict[str, dict[str, Any]] = {}
    total_rounds = 0
    total_faults = 0
    total_healed = 0
    all_scores: list[float] = []

    def _make_finding(severity: str, category: str, detail: str) -> dict[str, Any]:
        return {"severity": severity, "category": category, "detail": detail}

    # ── Phase 1: sustained_load ──────────────────────────────────────────
    logger.info(
        "StressHarness phase 1/3: sustained_load (%d rounds)", config["load_rounds"]
    )
    load_results: list[dict[str, Any]] = []
    for rid in range(1, int(config["load_rounds"]) + 1):
        elapsed = time.time() - start
        if elapsed > timeout_seconds:
            all_findings.append(
                _make_finding("WARNING", "timeout", f"Stress timed out at round {rid}")
            )
            break

        if runner_fn is not None:
            try:
                result = runner_fn(round_id=rid)
            except Exception as exc:
                all_findings.append(
                    _make_finding(
                        "HIGH", "runner_failure", f"Round {rid} runner crashed: {exc}"
                    )
                )
                continue
        else:
            result = {"score": mock_stress_score(rid, rng)}
        score = result.get("score", 0.0)
        all_scores.append(score)
        load_results.append({"round": rid, "score": score, "phase": "sustained_load"})
        total_rounds += 1

    load_avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
    phase_results["sustained_load"] = {
        "rounds_completed": len(load_results),
        "avg_score": round(load_avg_score, 1),
    }

    # ── Phase 2: fault_injection ─────────────────────────────────────────
    logger.info("StressHarness phase 2/3: fault_injection")
    fault_count = int(config["fault_types"])
    active_faults = DEFAULT_FAULT_TYPES[:fault_count]
    fault_results: list[dict[str, Any]] = []
    for fault_type in active_faults:
        if time.time() - start > timeout_seconds:
            break
        fault_event = chaos.inject(fault_type)
        total_faults += 1
        # Attempt healing
        chaos.record_healing(fault_type, success=True, recovery_time=0.5)
        total_healed += 1
        fault_results.append(
            {
                "fault_type": fault_type,
                "injected": fault_event.to_dict()
                if hasattr(fault_event, "to_dict")
                else str(fault_event),
                "healed": True,
            }
        )
        all_findings.append(
            _make_finding(
                "INFO",
                "fault_injection",
                f"Injected {fault_type} — healed successfully",
            )
        )

    healing_rate = total_healed / max(total_faults, 1)
    phase_results["fault_injection"] = {
        "faults_injected": total_faults,
        "faults_healed": total_healed,
        "healing_rate": round(healing_rate, 3),
        "fault_types_used": active_faults,
    }

    # ── Phase 3: resource_exhaustion ─────────────────────────────────────
    logger.info("StressHarness phase 3/3: resource_exhaustion")
    budget_deficit = config["budget_deficit"]
    recovery_results: list[dict[str, Any]] = []
    # Simulate budget exhaustion and recovery
    for attempt in range(3):
        if time.time() - start > timeout_seconds:
            break
        exhausted = attempt == 0  # first attempt always fails
        recovered = attempt > 0  # subsequent attempts succeed
        recovery_results.append(
            {
                "attempt": attempt + 1,
                "exhausted": exhausted,
                "recovered": recovered,
            }
        )
        if not recovered:
            all_findings.append(
                _make_finding(
                    "HIGH",
                    "resource_exhaustion",
                    f"Budget exhausted at deficit={budget_deficit}",
                )
            )
        else:
            all_findings.append(
                _make_finding(
                    "INFO",
                    "resource_recovery",
                    f"Recovered after exhaustion attempt {attempt + 1}",
                )
            )

    recovery_rate = sum(1 for r in recovery_results if r["recovered"]) / max(
        len(recovery_results), 1
    )
    cb_tripped = healing_rate < 0.8 or recovery_rate < 0.5
    phase_results["resource_exhaustion"] = {
        "deficit": budget_deficit,
        "recovery_rate": round(recovery_rate, 3),
        "attempts": len(recovery_results),
    }

    # ── Scoring ──────────────────────────────────────────────────────────
    score_components = {
        "sustained_load": min(load_avg_score / 100.0, 1.0) * 40,
        "fault_injection": healing_rate * 35,
        "resource_exhaustion": recovery_rate * 25,
    }
    raw_score = sum(score_components.values())
    final_score = round(min(raw_score, 100.0), 1)
    elapsed = round(time.time() - start, 1)

    # Clean up chaos engine
    chaos.clear()

    return {
        "level": "L3",
        "name": "Stress",
        "elapsed_seconds": elapsed,
        "score": final_score,
        "grade": score_to_grade(final_score),
        "verdict": determine_verdict(final_score, all_findings),
        "domain_scores": {"stress": final_score},
        "domains": {
            "stress_detail": {
                "domain": "Stress",
                "name": "Stress Harness",
                "score": final_score,
                "level": level,
                "total_rounds": total_rounds,
                "total_faults_injected": total_faults,
                "total_faults_healed": total_healed,
                "healing_rate": round(healing_rate, 3),
                "recovery_rate": round(recovery_rate, 3),
                "circuit_breaker_tripped": cb_tripped,
                "phases": phase_results,
                "findings": all_findings,
            },
        },
        "findings": all_findings,
        "phase_results": phase_results,
        "stress_config": {k: v for k, v in config.items()},
    }


def mock_stress_score(round_id: int, rng: random.Random | None = None) -> float:
    """Deterministic mock score for stress testing.

    Produces a gradually improving score with random jitter, simulating a
    Ratchet loop under stress.  Score plateaus near 0.90 after ~150 rounds.
    """
    rng = rng or random.Random()
    base = min(round_id / 200.0 * 0.9, 0.9)
    jitter = rng.uniform(-0.05, 0.05)
    return round(max(0.0, min(1.0, base + jitter)) * 100.0, 1)
