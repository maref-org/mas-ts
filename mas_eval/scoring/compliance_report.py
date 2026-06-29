# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""
MAS-TS-001 v5.0 — Federation Compliance Report

Aggregates D1-D5 evaluation results across multiple agents into a
structured compliance report with federation-wide metrics, gap analysis,
and recommendations.

Usage:
    from mas_eval.scoring.compliance_report import build_report
    report = build_report(agent_results, cards)
    print(json.dumps(report, indent=2))
"""

import logging
import statistics
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DOMAIN_NAMES = {
    "D1": "Static Compliance",
    "D2": "Single-Agent Quality",
    "D3": "Multi-Agent Collaboration",
    "D4": "Governance & Security",
    "D5": "Evolution & Robustness",
}

DOMAIN_WEIGHTS = {
    "D1": 0.10,
    "D2": 0.25,
    "D3": 0.25,
    "D4": 0.20,
    "D5": 0.20,
}


def _extract_domain_scores(result):
    scores = {}
    scores["domain_score"] = result.get("score", 0)
    subscores = result.get("subscores", {})
    if isinstance(subscores, dict):
        scores["subscores"] = subscores
    return scores


def _compute_federation_health(agent_scores):
    if not agent_scores:
        return 0.0
    d_scores: dict[str, list[float]] = {d: [] for d in DOMAIN_WEIGHTS}
    for entry in agent_scores:
        for d in DOMAIN_WEIGHTS:
            val = entry.get("scores", {}).get(d)
            if val is not None:
                d_scores[d].append(val)
    weighted_sum = 0.0
    for d, weight in DOMAIN_WEIGHTS.items():
        if d_scores[d]:
            weighted_sum += statistics.mean(d_scores[d]) * weight
    return round(weighted_sum, 1)


def _analyze_gaps(agent_results, cards):
    gaps = []
    all_findings = []
    for agent_name, result in agent_results.items():
        findings = result.get("findings", [])
        for f in findings:
            all_findings.append(
                {
                    "agent": agent_name,
                    "check": f.get("check", f.get("category", "unknown")),
                    "severity": f.get("severity", "INFO"),
                    "detail": f.get("detail", ""),
                }
            )
    critical = [f for f in all_findings if f["severity"] == "CRITICAL"]
    high = [f for f in all_findings if f["severity"] == "HIGH"]
    for f in critical[:5]:
        gaps.append(
            {
                "severity": "CRITICAL",
                "description": f["detail"],
                "check": f["check"],
                "affected_agents": [f["agent"]],
            }
        )
    for f in high[:5]:
        gaps.append(
            {
                "severity": "HIGH",
                "description": f["detail"],
                "check": f["check"],
                "affected_agents": [f["agent"]],
            }
        )
    return gaps


def _card_trace_enabled(card):
    audit = card.get("audit")
    required_flags = (
        "trace_id_required",
        "timestamp_required",
        "source_agent_required",
        "target_agent_required",
    )
    if isinstance(audit, dict) and all(
        audit.get(flag) is True for flag in required_flags
    ):
        return True
    return bool((card.get("federation") or {}).get("audit", {}).get("trace_enabled"))


def _generate_recommendations(agent_results, cards):
    recs = []
    fed_count = sum(1 for c in cards if c.get("federation"))
    if fed_count < len(cards):
        recs.append(
            f"Configure federation block on {len(cards) - fed_count}/{len(cards)} agents"
        )

    fed_with_trace = sum(1 for c in cards if _card_trace_enabled(c))
    if fed_with_trace < fed_count:
        recs.append(
            f"Enable trace_id audit chain on {fed_count - fed_with_trace} agent(s)"
        )

    for agent_name, result in agent_results.items():
        d3_subscores = result.get("D3", {}).get("subscores", {})
        role = d3_subscores.get("federation_role", 0)
        if role == 0:
            recs.append(f"Resolve federation role conflict on '{agent_name}'")
            break

    return recs


def _build_agent_entry(agent_name, card, result):
    d1 = _extract_domain_scores(result.get("D1", {}))
    d2 = _extract_domain_scores(result.get("D2", {}))
    d3 = _extract_domain_scores(result.get("D3", {}))
    d4 = _extract_domain_scores(result.get("D4", {}))
    d5 = _extract_domain_scores(result.get("D5", {}))

    def _clamp(v, lo=0, hi=100):
        return max(lo, min(hi, v))

    scores = {
        "D1": _clamp(d1.get("domain_score", 0)),
        "D2": _clamp(d2.get("domain_score", 0)),
        "D3": _clamp(d3.get("domain_score", 0)),
        "D4": _clamp(d4.get("domain_score", 0)),
        "D5": _clamp(d5.get("domain_score", 0)),
    }

    verdict = "PASS"
    for f in result.get("findings", []):
        sev = f.get("severity", "")
        if sev == "CRITICAL":
            verdict = "BLOCKED"
            break
        if sev == "HIGH":
            verdict = "REVIEW"
        elif sev == "WARNING" and verdict != "REVIEW":
            verdict = "NOTES"

    fed_details = {}
    d4_subs = d4.get("subscores", {})
    for k in ("trust", "vendor_diversity", "mcp_supply_chain", "gossip_trust"):
        if k in d4_subs:
            fed_details[k] = d4_subs[k]

    d3_subs = d3.get("subscores", {})
    if "federation_matrix" in d3_subs:
        fed_details["compatibility_matrix"] = d3_subs["federation_matrix"]

    entry = {
        "name": card.get("name", agent_name),
        "agent_id": card.get("agent_id", agent_name),
        "vendor_id": card.get("vendor_id", "unknown"),
        "schema_version": card.get("schema_version", card.get("card_version", "1.2")),
        "scores": scores,
        "verdict": verdict,
        "federation_details": fed_details,
    }

    has_fed = card.get("federation")
    if has_fed:
        entry["federation_role"] = has_fed.get("role", "not set")
        entry["trust_score"] = has_fed.get("trust_score", 0)
    return entry


def build_report(agent_results, cards):
    agent_entries = []
    for i, card in enumerate(cards):
        agent_name = card.get("agent_id", card.get("name", f"agent_{i}"))
        result = agent_results.get(agent_name, {})
        entry = _build_agent_entry(agent_name, card, result)
        agent_entries.append(entry)

    federation_health = _compute_federation_health(
        [{"scores": e["scores"]} for e in agent_entries]
    )
    gaps = _analyze_gaps(
        {e["name"]: agent_results.get(e["agent_id"], {}) for e in agent_entries},
        cards,
    )
    recommendations = _generate_recommendations(
        {e["agent_id"]: agent_results.get(e["agent_id"], {}) for e in agent_entries},
        cards,
    )

    compliant = sum(1 for e in agent_entries if e["verdict"] in ("PASS", "NOTES"))
    total = len(agent_entries)

    report = {
        "report_type": "federation_compliance_report",
        "report_version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "agents": agent_entries,
        "federation": {
            "agent_count": total,
            "compliance_rate": f"{compliant}/{total}",
            "overall_health": federation_health,
            "domain_averages": {
                d: round(
                    statistics.mean([e["scores"].get(d, 0) for e in agent_entries])
                    if agent_entries
                    else 0,
                    1,
                )
                for d in DOMAIN_WEIGHTS
            },
        },
        "gaps": gaps,
        "recommendations": recommendations,
        "summary": {
            "total_agents": total,
            "agents_passing": compliant,
            "agents_blocked": sum(
                1 for e in agent_entries if e["verdict"] == "BLOCKED"
            ),
            "agents_needing_review": sum(
                1 for e in agent_entries if e["verdict"] == "REVIEW"
            ),
            "total_gaps": len(gaps),
            "total_recommendations": len(recommendations),
            "federation_health": federation_health,
        },
    }

    return report
