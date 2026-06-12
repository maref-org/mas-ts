"""MAS-TS v4.0 Federation Scan — Run on migrated v2.0 cards."""

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

V2_DIR = Path(__file__).resolve().parent / "v2_cards"
CARDS: Dict[str, Path] = {
    "claude_code": V2_DIR / "agent_card_claude_code_v2.json",
    "codex": V2_DIR / "agent_card_codex_v2.json",
    "cursor": V2_DIR / "agent_card_cursor_v2.json",
    "opencode": V2_DIR / "agent_card_opencode_v2.json",
    "trae_cn": V2_DIR / "agent_card_traecn_v2.json",
}


def load_cards() -> Dict[str, Any]:
    loaded: Dict[str, Any] = {}
    for name, path in CARDS.items():
        with open(path) as f:
            loaded[name] = json.load(f)
    return loaded


def p(s: str) -> None:
    print(s)


cards: Dict[str, Any] = load_cards()
results: Dict[str, Any] = {}
report: Dict[str, Any] = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "cards": "v2.0 (migrated)",
    "results": results,
}

p("=" * 70)
p("  D1 — Static Compliance (v4.0 on v2.0 cards)")
p("=" * 70)
for name, card in cards.items():
    r = run_d1(card)
    agent_results: Dict[str, Any] = {}
    results[name] = agent_results
    agent_results["d1"] = {
        "score": r["score"],
        "verdict": r["conformance_verdict"],
        "summary": r["summary"],
    }
    chain = check_data_cross_border_chain(card)
    compat = check_federation_version_compat(card)
    agent_results["d1"]["cross_border_chain"] = chain
    agent_results["d1"]["fed_version_compat"] = compat
    s = r["summary"]
    p(
        f"  {name:15s}  score={r['score']:5.1f}  verdict={r['conformance_verdict']:35s}  "
        f"C={s['critical']} H={s['high']} W={s['warning']}"
    )

p("")
p("=" * 70)
p("  D3 — Multi-Agent + Federation (v4.0)")
p("=" * 70)
for name, card in cards.items():
    d3 = run_d3(card)
    fed_s, fed_f = check_federation_compatibility(card)
    rol_s, rol_f = check_role_conflicts(card)
    per_s, per_f = check_permission_propagation(card)
    agent_results = results[name]
    agent_results["d3"] = {
        "score": d3["score"],
        "subscores": d3.get("subscores", {}),
        "federation_compat": {"score": fed_s, "findings": fed_f},
        "role_conflicts": {"score": rol_s, "findings": rol_f},
        "permission_propagation": {"score": per_s, "findings": per_f},
    }
    p(
        f"  {name:15s}  score={d3['score']:5.1f}  "
        f"fed={fed_f[-1]['severity'] if fed_f else 'NONE':10s}  "
        f"role={rol_f[-1]['severity'] if rol_f else 'NONE':10s}  "
        f"perm={per_f[-1]['severity'] if per_f else 'NONE':10s}"
    )

p("")
p("=" * 70)
p("  D4 — Governance & Trust (v4.0)")
p("=" * 70)
for name, card in cards.items():
    d4 = run_d4(card)
    tr_s, tr_f = check_trust_score(card)
    mcp_s, mcp_f = check_mcp_supply_chain(card)
    agent_results = results[name]
    agent_results["d4"] = {
        "score": d4["score"],
        "verdict": d4.get("verdict", ""),
        "trust_score": {"score": tr_s, "findings": tr_f},
        "mcp_supply_chain": {"score": mcp_s, "findings": mcp_f},
    }
    p(
        f"  {name:15s}  d4={d4['score']:5.1f}  trust={tr_s:6.2f}  mcp_findings={len(mcp_f)}"
    )

p("")
p("=" * 70)
p("  D4 Federation — Cross-Agent (v4.0)")
p("=" * 70)
cards_list: List[Dict[str, Any]] = list(cards.values())
fed = run_d4_federation(cards_list)
div_s, div_f = check_vendor_diversity(cards_list)
report["federation"] = {
    "d4_federation": fed,
    "vendor_diversity": {"score": div_s, "findings": div_f},
}
p(f"  Federation score:    {fed.get('score', 'N/A')}")
p(f"  Findings:            {len(fed.get('findings', []))}")
p(f"  Vendor diversity:    {div_s:.1f}/100")
p(f"  Diversity findings:  {len(div_f)}")

p("")
p("=" * 70)
p("  Cross-Border Chain Audit (D1.11)")
p("=" * 70)
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
        "residency": pol.get("data_residency", "?"),
        "transfers": pol.get("allowed_transfer_zones", []),
        "approval": pol.get("requires_approval", False),
    }
    r = regions[name]
    z = ",".join(r["transfers"])
    p(
        f"  {name:15s}  region={r['residency']:10s}  transfers=[{z}]  "
        f"approval={'Y' if r['approval'] else 'N'}  "
        + ("" if r["residency"] in r["transfers"] else "MISSING SELF IN TRANSFERS")
    )
report["cross_border_regions"] = regions

p("")
p("=" * 70)
p("  v3.0 vs v4.0 COMPARISON")
p("=" * 70)
d1_v3: Dict[str, float] = {
    "claude_code": 100,
    "codex": 100,
    "cursor": 100,
    "opencode": 100,
    "trae_cn": 100,
}
d1_v4: Dict[str, float] = {k: v["d1"]["score"] for k, v in results.items()}
p(f"  {'Agent':15s}  D1(v3.0)  D1(v4.0)  D3(v4.0)  D4(v4.0)")
p(f"  {'-' * 56}")
for name in d1_v3:
    d3s: float = results[name]["d3"]["score"]
    d4s: float = results[name]["d4"]["score"]
    p(
        f"  {name:15s}  {d1_v3[name]:6.1f}   {d1_v4[name]:6.1f}   {d3s:6.1f}   {d4s:6.1f}"
    )
p(f"  {'-' * 56}")
avg_v3: float = sum(d1_v3.values()) / len(d1_v3)
avg_v4: float = sum(d1_v4.values()) / len(d1_v4)
avg_d3: float = sum(results[n]["d3"]["score"] for n in d1_v3) / len(d1_v3)
avg_d4: float = sum(results[n]["d4"]["score"] for n in d1_v3) / len(d1_v3)
p(f"  {'AVERAGE':15s}  {avg_v3:6.1f}   {avg_v4:6.1f}   {avg_d3:6.1f}   {avg_d4:6.1f}")

p("")
p(f"  Federation D4 score: {fed.get('score', 'N/A')} (out of 100)")
p(f"  Vendor diversity:    {div_s:.1f}/100")
p(f"  Total cross-agent findings: {len(fed.get('findings', []))}")

# Write report
out: Path = Path(__file__).resolve().parent / "v4_federation_scan_v2_results.json"
with open(out, "w") as f:
    json.dump(report, f, indent=2, default=str)
p(f"\nReport: {out}")
