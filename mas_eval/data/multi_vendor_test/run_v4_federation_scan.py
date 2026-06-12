"""MAS-TS v4.0 Federation Scan — Run D1-D5 on 5 vendor agents + federation analysis."""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from mas_eval.domains.d1_compliance import (
    check_data_cross_border_chain,
    check_federation_version_compat,
    run_d1,
)
from mas_eval.domains.d3_multi_agent import (
    check_federation_compatibility,
    check_permission_propagation,
    check_role_conflicts,
    run_d3,
)
from mas_eval.domains.d4_governance_security import (
    check_mcp_supply_chain,
    check_trust_score,
    check_vendor_diversity,
    run_d4,
    run_d4_federation,
)

DATA_DIR = Path(__file__).resolve().parent
CARDS = {
    "claude_code": DATA_DIR / "agent_card_claude_code.json",
    "codex": DATA_DIR / "agent_card_codex.json",
    "cursor": DATA_DIR / "agent_card_cursor.json",
    "opencode": DATA_DIR / "agent_card_opencode.json",
    "trae_cn": DATA_DIR / "agent_card_traecn.json",
}


def load_cards() -> Dict[str, Any]:
    loaded: Dict[str, Any] = {}
    for name, path in CARDS.items():
        with open(path) as f:
            loaded[name] = json.load(f)
    return loaded


def print_header(s):
    print(f"\n{'=' * 70}")
    print(f"  {s}")
    print(f"{'=' * 70}")


# Load
cards: Dict[str, Any] = load_cards()
results: Dict[str, Any] = {}
report: Dict[str, Any] = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "results": results,
}

# ===== D1 — Per-Agent Compliance (includes D1.11 + D1.12) =====
print_header("D1 — Static Compliance (v4.0: 12 checks)")
for name, card in cards.items():
    result = run_d1(card)
    agent_results: Dict[str, Any] = {}
    results[name] = agent_results
    agent_results["d1"] = {
        "score": result["score"],
        "conformance_verdict": result["conformance_verdict"],
        "severity_counts": result["summary"],
    }
    chain = check_data_cross_border_chain(card)
    compat = check_federation_version_compat(card)
    agent_results["d1"]["data_cross_border_chain"] = chain
    agent_results["d1"]["federation_version_compat"] = compat
    print(
        f"  {name:15s} score={result['score']:5.1f}  verdict={result['conformance_verdict']:35s}  "
        f"C={result['summary']['critical']} H={result['summary']['high']} W={result['summary']['warning']}"
    )

# ===== D3 — Multi-Agent & Federation =====
print_header("D3 — Multi-Agent Collaboration + Federation (v4.0)")
for name, card in cards.items():
    d3 = run_d3(card)
    agent_results = results[name]
    agent_results["d3"] = {"score": d3["score"], "subscores": d3.get("subscores", {})}
    fed_score, fed_findings = check_federation_compatibility(card)
    role_score, role_findings = check_role_conflicts(card)
    perm_score, perm_findings = check_permission_propagation(card)
    agent_results["d3"]["federation_compatibility"] = {
        "score": fed_score,
        "findings": fed_findings,
    }
    agent_results["d3"]["role_conflicts"] = {
        "score": role_score,
        "findings": role_findings,
    }
    agent_results["d3"]["permission_propagation"] = {
        "score": perm_score,
        "findings": perm_findings,
    }
    fed_severity = fed_findings[-1].get("severity", "N/A") if fed_findings else "NONE"
    role_severity = (
        role_findings[-1].get("severity", "N/A") if role_findings else "NONE"
    )
    perm_severity = (
        perm_findings[-1].get("severity", "N/A") if perm_findings else "NONE"
    )
    print(
        f"  {name:15s} score={d3['score']:5.1f}  fed={fed_severity:10s}  role={role_severity:10s}  perm={perm_severity:10s}"
    )

# ===== D4 — Governance + Trust (v4.0) =====
print_header("D4 — Governance & Trust (v4.0 Federation)")
for name, card in cards.items():
    d4 = run_d4(card)
    agent_results = results[name]
    agent_results["d4"] = {"score": d4["score"], "verdict": d4.get("verdict", "")}
    trust_score, trust_findings = check_trust_score(card)
    agent_results["d4"]["trust_score"] = {
        "score": trust_score,
        "findings": trust_findings,
    }
    mcp_score, mcp_findings = check_mcp_supply_chain(card)
    agent_results["d4"]["mcp_supply_chain"] = {
        "score": mcp_score,
        "findings": mcp_findings,
    }
    print(
        f"  {name:15s} d4_score={d4['score']:5.1f}  trust={trust_score:.2f}  mcp_findings={len(mcp_findings)}"
    )

# ===== D4 Federation — Cross-Agent =====
print_header("D4 Federation — Cross-Agent (v4.0)")
cards_list: List[Dict[str, Any]] = list(cards.values())
fed_result = run_d4_federation(cards_list)
div_score, div_findings = check_vendor_diversity(cards_list)
print(f"  Federation score: {fed_result.get('score', 'N/A')}")
print(f"  Findings: {len(fed_result.get('findings', []))}")
print(f"  Vendor diversity score: {div_score:.1f}")
print(f"  Diversity findings: {len(div_findings)}")
report["federation"] = {
    "d4_federation": fed_result,
    "vendor_diversity": {"score": div_score, "findings": div_findings},
}

# ===== Cross-border audit summary =====
print_header("Cross-Border Chain Audit (D1.11)")
regions: Dict[str, Any] = {}
for name, card in cards.items():
    fed_block: Dict[str, Any] = (
        card.get("federation", {}) if isinstance(card.get("federation"), dict) else {}
    )
    pol: Dict[str, Any] = (
        fed_block.get("cross_border_policy", {})
        if isinstance(fed_block.get("cross_border_policy"), dict)
        else {}
    )
    regions[name] = {
        "data_residency": pol.get("data_residency", "UNKNOWN"),
        "allowed_transfer_zones": pol.get("allowed_transfer_zones", []),
    }
    print(
        f"  {name:15s}  region={regions[name]['data_residency']:10s}  transfers={regions[name]['allowed_transfer_zones']}"
    )
report["cross_border_regions"] = regions

# ===== Summary =====
print_header("SUMMARY")
d1_scores: Dict[str, float] = {k: v["d1"]["score"] for k, v in results.items()}
d3_scores: Dict[str, float] = {k: v["d3"]["score"] for k, v in results.items()}
d4_scores: Dict[str, float] = {k: v["d4"]["score"] for k, v in results.items()}
print(f"  D1 Compliance (avg):  {sum(d1_scores.values()) / len(d1_scores):.1f}")
print(f"  D3 Multi-Agent (avg): {sum(d3_scores.values()) / len(d3_scores):.1f}")
print(f"  D4 Governance (avg):  {sum(d4_scores.values()) / len(d4_scores):.1f}")
print(f"  Federation D4 score:  {fed_result.get('score', 'N/A')}")
print(f"  Vendor Diversity:     {div_score:.1f}/100")
print(
    f"  Total findings:       {sum(len(v['d1'].get('findings', [])) for v in results.values())}"
)

# Write report
out_path = DATA_DIR / "v4_federation_scan_results.json"
with open(out_path, "w") as f:
    json.dump(report, f, indent=2, default=str)
print(f"\nReport written to: {out_path}")
