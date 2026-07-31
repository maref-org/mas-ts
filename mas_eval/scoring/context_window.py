from typing import Any

TRUNCATION_STRATEGIES = {
    "drop_oldest": "remove oldest messages first",
    "summarize": "replace old messages with summary token",
    "drop_lowest_score": "remove messages with lowest relevance score",
}
DEFAULT_MAX_TOKENS = 128_000
DEFAULT_STRATEGY = "drop_oldest"


def check_context_window(
    card: dict[str, Any] | None = None,
    total_tokens: int = 0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    config = (card or {}).get("context_window") or {}
    strategy = config.get("strategy", DEFAULT_STRATEGY)
    declared_max = int(config.get("max_tokens", 0) or max_tokens)

    effective_max = min(declared_max, max_tokens)
    utilization = total_tokens / effective_max if effective_max > 0 else 0.0

    findings: list[dict[str, Any]] = []
    if strategy not in TRUNCATION_STRATEGIES:
        findings.append({
            "severity": "HIGH",
            "category": "context_window_invalid_strategy",
            "detail": f"Unknown truncation strategy '{strategy}'. Valid: {list(TRUNCATION_STRATEGIES.keys())}",
        })

    if utilization > 0.95:
        findings.append({
            "severity": "WARNING",
            "category": "context_window_near_limit",
            "detail": (
                f"Context window at {utilization*100:.0f}% capacity "
                f"({total_tokens}/{effective_max} tokens)"
            ),
        })

    if utilization >= 1.0:
        findings.append({
            "severity": "CRITICAL",
            "category": "context_window_exceeded",
            "detail": f"Context window exceeded: {total_tokens} > {effective_max} tokens",
        })

    subscore = max(0.0, min(100.0, (1.0 - utilization) * 100.0))
    if strategy not in TRUNCATION_STRATEGIES:
        subscore *= 0.5

    return {
        "score": round(subscore, 1),
        "truncation_required": utilization >= 1.0,
        "findings": findings,
        "metrics": {
            "total_tokens": total_tokens,
            "max_tokens": effective_max,
            "utilization": round(utilization, 4),
            "strategy": strategy,
            "strategy_valid": strategy in TRUNCATION_STRATEGIES,
        },
    }
