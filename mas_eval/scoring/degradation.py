import enum
from typing import Any


class DegradationMode(enum.Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    FALLBACK = "fallback"
    BLOCKED = "blocked"
    MANUAL = "manual_override"


_DEGRADATION_ORDER = [
    DegradationMode.NORMAL,
    DegradationMode.DEGRADED,
    DegradationMode.FALLBACK,
    DegradationMode.MANUAL,
    DegradationMode.BLOCKED,
]

DEFAULT_FALLBACK_CONFIG: dict[str, Any] = {
    "timeout_seconds": 30,
    "cache_ttl_seconds": 300,
    "retry_count": 3,
    "retry_backoff_base": 2.0,
    "circuit_breaker_threshold": 3,
    "circuit_breaker_cooldown": 30,
}


def determine_degradation_mode(
    failures: int = 0,
    critical_findings: int = 0,
    dependency_healthy: bool = True,
    fallback_available: bool = False,
) -> DegradationMode:
    if critical_findings > 0 or failures >= 10:
        return DegradationMode.BLOCKED
    if failures >= 5 or not dependency_healthy:
        return DegradationMode.FALLBACK if fallback_available else DegradationMode.DEGRADED
    if failures >= 3:
        return DegradationMode.DEGRADED
    return DegradationMode.NORMAL


def build_degradation_assessment(
    component: str,
    failures: int = 0,
    critical_findings: int = 0,
    dependency_healthy: bool = True,
    fallback_available: bool = False,
    mode: DegradationMode | None = None,
) -> dict[str, Any]:
    if mode is None:
        mode = determine_degradation_mode(
            failures, critical_findings, dependency_healthy, fallback_available
        )

    level = _DEGRADATION_ORDER.index(mode) if mode in _DEGRADATION_ORDER else 0
    max_level = len(_DEGRADATION_ORDER) - 1

    findings: list[dict[str, Any]] = []
    if mode == DegradationMode.BLOCKED:
        findings.append({
            "severity": "CRITICAL",
            "category": f"degradation_{component}_blocked",
            "detail": f"{component} is blocked — cannot proceed without manual intervention",
        })
    elif mode == DegradationMode.FALLBACK:
        findings.append({
            "severity": "HIGH",
            "category": f"degradation_{component}_fallback",
            "detail": f"{component} running with fallback — results may have reduced quality",
        })
    elif mode == DegradationMode.DEGRADED:
        findings.append({
            "severity": "WARNING",
            "category": f"degradation_{component}_degraded",
            "detail": f"{component} degraded — some features may be unavailable",
        })

    return {
        "component": component,
        "mode": mode.value,
        "degradation_level": round(level / max_level, 2) if max_level > 0 else 0.0,
        "action_required": mode in (DegradationMode.BLOCKED, DegradationMode.MANUAL),
        "findings": findings,
        "config": dict(DEFAULT_FALLBACK_CONFIG),
    }
