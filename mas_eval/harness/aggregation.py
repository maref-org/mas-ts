import time
from typing import Any

from mas_eval.scoring.absolute import (
    compute_gold_overall,
    compute_overall,
    determine_gold_verdict,
    determine_verdict,
    score_domain,
    score_to_grade,
)


def _subscore(result: dict[str, Any], key: str) -> float | None:
    """Read a subscore from a domain result, returning None if absent."""
    subs = result.get("subscores") or {}
    val = subs.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _pct_to_ratio(value: float | None) -> float | None:
    return None if value is None else value / 100.0


def _extract_d1_metrics(
    domain_results: dict[str, dict[str, Any]], metrics: dict[str, Any]
) -> None:
    d1 = domain_results.get("d1") or {}
    if d1.get("score") is not None:
        metrics["d1_compliance"] = float(d1["score"])


def _extract_d2_metrics(
    domain_results: dict[str, dict[str, Any]], metrics: dict[str, Any]
) -> None:
    d2 = domain_results.get("d2") or {}
    for key, sub_key in [
        ("d2_task_completion", "task_completion"),
        ("d2_tool_coverage", "tool_coverage"),
    ]:
        if (v := _subscore(d2, sub_key)) is not None:
            metrics[key] = v
    for key, sub_key in [
        ("d2_step_efficiency", "step_efficiency"),
        ("d2_trajectory_quality", "trajectory_quality"),
        ("d2_tool_select_accuracy", "tool_selection_correctness"),
    ]:
        if (v := _subscore(d2, sub_key)) is not None:
            metrics[key] = _pct_to_ratio(v)


def _extract_d3_metrics(
    domain_results: dict[str, dict[str, Any]], metrics: dict[str, Any]
) -> None:
    d3 = domain_results.get("d3") or {}
    if (v := _subscore(d3, "spawn")) is not None:
        metrics["d3_spawn_rate"] = v
    if (v := _subscore(d3, "conflict")) is not None:
        metrics["d3_conflict_resolution"] = v
    for key, sub_key in [
        ("d3_coordination_efficiency", "coordination_efficiency"),
        ("d3_plan_adherence", "plan_quality"),
    ]:
        if (v := _subscore(d3, sub_key)) is not None:
            metrics[key] = _pct_to_ratio(v)


def _extract_d4_metrics(
    domain_results: dict[str, dict[str, Any]], metrics: dict[str, Any]
) -> None:
    d4 = domain_results.get("d4") or {}
    if (v := _subscore(d4, "action_safety")) is not None:
        metrics["d4_action_safety"] = _pct_to_ratio(v)
    gov_detail = (d4.get("subscores") or {}).get("governance_detail") or {}
    if (v := _subscore({"subscores": gov_detail}, "state_machine")) is not None:
        metrics["d4_state_coverage"] = v / 10.0
    dl = d4.get("data_leakage") or {}
    dl_crit = (dl.get("summary") or {}).get("critical_count")
    if dl_crit is not None:
        metrics["d4_data_leakage"] = int(dl_crit)
    sec = d4.get("security") or {}
    sec_crit = sum(
        1 for f in (sec.get("findings") or []) if f.get("severity") == "CRITICAL"
    )
    metrics["d4_pentest"] = int(sec_crit)
    rt = d4.get("runtime_security") or {}
    if rt:
        rt_summary = rt.get("summary") or {}
        rt_crit = int(rt_summary.get("runtime_consistency_critical_count", 0)) + int(
            rt_summary.get("runtime_injection_critical_count", 0)
        )
        metrics["d4_runtime_consistency_critical"] = rt_crit


def _extract_d5_metrics(
    domain_results: dict[str, dict[str, Any]], metrics: dict[str, Any]
) -> None:
    d5 = domain_results.get("d5") or {}
    if (v := _subscore(d5, "consistency_index")) is not None:
        metrics["d5_consistency_index"] = _pct_to_ratio(v)
    if (v := _subscore(d5, "reflection_loop")) is not None:
        metrics["d5_reflection"] = _pct_to_ratio(v)
    if (v := _subscore(d5, "chaos_engineering")) is not None:
        metrics["d5_self_heal_rate"] = v
    drift_fnr = (d5.get("summary") or {}).get("drift_fnr")
    if isinstance(drift_fnr, str) and drift_fnr.endswith("%"):
        try:
            metrics["d5_drift_fnr"] = float(drift_fnr.rstrip("%"))
        except ValueError:
            pass


def _extract_cross_cutting_metrics(
    metrics: dict[str, Any],
    consistency_index: float | None = None,
    cost_efficiency: float | None = None,
    overall_score: float | None = None,
) -> None:
    if consistency_index is not None:
        metrics["d5_consistency_index"] = float(consistency_index)
    if cost_efficiency is not None:
        metrics["cost_efficiency"] = float(cost_efficiency)
    if overall_score is not None:
        metrics["overall_score"] = float(overall_score)


def extract_gold_metrics(
    domain_results: dict[str, dict[str, Any]],
    consistency_index: float | None = None,
    cost_efficiency: float | None = None,
    overall_score: float | None = None,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    _extract_d1_metrics(domain_results, metrics)
    _extract_d2_metrics(domain_results, metrics)
    _extract_d3_metrics(domain_results, metrics)
    _extract_d4_metrics(domain_results, metrics)
    _extract_d5_metrics(domain_results, metrics)
    _extract_cross_cutting_metrics(metrics, consistency_index, cost_efficiency, overall_score)
    return metrics


def aggregate_level(
    level: str,
    name: str,
    start_time: float,
    domain_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    domain_scores = {
        key: score_domain(result["score"]) for key, result in domain_results.items()
    }
    all_findings: list[dict[str, Any]] = []
    for result in domain_results.values():
        all_findings.extend(result.get("findings", []))
    overall = compute_overall(**domain_scores)
    return {
        "level": level,
        "name": name,
        "elapsed_seconds": round(time.time() - start_time, 1),
        "score": overall,
        "grade": score_to_grade(overall),
        "verdict": determine_verdict(overall, findings=all_findings),
        "domain_scores": domain_scores,
        "domains": {f"{key}_detail": result for key, result in domain_results.items()},
        "findings": all_findings,
    }


def compute_gold_report(
    domain_results: dict[str, dict[str, Any]],
    consistency_index: float | None = None,
    cost_efficiency: float | None = None,
) -> dict[str, Any]:
    """Gold Standard aggregation with cross-cutting adjustments.

    Uses Gold domain weights (D1=0.08, D2=0.22, D3=0.20, D4=0.25, D5=0.25)
    with Consistency Index and Cost Efficiency penalties.

    Args:
        domain_results: Dict mapping domain keys to their result dicts.
        consistency_index: Optional Consistency Index (0.0-1.0).
        cost_efficiency: Optional Cost Efficiency score (0.0-1.0).

    Returns:
        Dict with gold_verdict, overall, grade, domain_scores, findings.
    """
    domain_scores = {
        key: score_domain(result["score"]) for key, result in domain_results.items()
    }
    all_findings: list[dict[str, Any]] = []
    for result in domain_results.values():
        all_findings.extend(result.get("findings", []))
    overall = compute_gold_overall(
        **domain_scores,
        consistency_index=consistency_index,
        cost_efficiency=cost_efficiency,
    )
    return {
        "gold_verdict": determine_gold_verdict(
            overall, all_findings, consistency_index
        ),
        "overall": overall,
        "grade": score_to_grade(overall),
        "domain_scores": domain_scores,
        "consistency_index": consistency_index,
        "cost_efficiency": cost_efficiency,
        "findings": all_findings,
    }
