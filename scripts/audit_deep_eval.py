#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""
MAS-TS-001 深度审计脚本 — 运行完整评估并检查偏差
"""

import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 领域权重
DOMAIN_WEIGHTS = {
    "D1": 0.10,
    "D2": 0.25,
    "D3": 0.25,
    "D4": 0.20,
    "D5": 0.20,
}


def evaluate_card(card_path: Path) -> dict:
    """对单个Agent Card运行完整评估"""
    from mas_eval.domains.d1_compliance import run_d1
    from mas_eval.domains.d2_single_agent import run_d2
    from mas_eval.domains.d3_multi_agent import run_d3
    from mas_eval.domains.d4_governance_security import run_d4
    from mas_eval.domains.d5_robustness import run_d5

    print(f"\n{'=' * 80}")
    print(f"评估: {card_path.name}")
    print(f"{'=' * 80}")

    with open(card_path) as f:
        card = json.load(f)

    # 运行5个领域评估
    results = {}

    print("\n[D1] Static Compliance...")
    d1 = run_d1(card)
    results["D1"] = d1
    print(f"  Score: {d1['score']} ({d1.get('conformance_verdict', 'N/A')})")
    # 打印关键发现
    critical_high = [
        f for f in d1.get("findings", []) if f.get("severity") in ("CRITICAL", "HIGH")
    ]
    if critical_high:
        print(f"  Issues: {len(critical_high)}")
        for f in critical_high[:3]:
            print(f"    [{f['severity']}] {f['detail']}")

    print("\n[D2] Single-Agent Capability...")
    d2 = run_d2(card)
    results["D2"] = d2
    print(f"  Score: {d2['score']}")
    print(f"    Model: {d2['summary'].get('model_name', 'unknown')}")
    print(f"    Tools: {d2['summary'].get('declared_tools_count', 0)}")
    critical_high = [
        f for f in d2.get("findings", []) if f.get("severity") in ("CRITICAL", "HIGH")
    ]
    if critical_high:
        print(f"  Issues: {len(critical_high)}")
        for f in critical_high[:3]:
            print(f"    [{f['severity']}] {f['detail']}")

    print("\n[D3] Multi-Agent Collaboration...")
    d3 = run_d3(card)
    results["D3"] = d3
    print(f"  Score: {d3['score']}")
    print(f"    Subscores: {d3['subscores']}")
    critical_high = [
        f for f in d3.get("findings", []) if f.get("severity") in ("CRITICAL", "HIGH")
    ]
    if critical_high:
        print(f"  Issues: {len(critical_high)}")
        for f in critical_high[:3]:
            print(f"    [{f['severity']}] {f['detail']}")

    print("\n[D4] Governance & Security...")
    d4 = run_d4(card)
    results["D4"] = d4
    print(f"  Score: {d4['score']}")
    print(f"    Governance: {d4['subscores'].get('governance', 'N/A')}")
    print(f"    Security: {d4['subscores'].get('security', 'N/A')}")
    critical_high = [
        f for f in d4.get("findings", []) if f.get("severity") in ("CRITICAL", "HIGH")
    ]
    if critical_high:
        print(f"  Issues: {len(critical_high)}")
        for f in critical_high[:3]:
            print(f"    [{f['severity']}] {f['detail']}")

    print("\n[D5] Robustness...")
    # D5 needs ChaosEngine and DriftDetector, not just the card
    from mas_eval.domains.d5_robustness import ChaosEngine, DriftDetector

    ce = ChaosEngine(seed=42)
    dd = DriftDetector()
    d5 = run_d5(ce, dd, card)
    results["D5"] = d5
    print(f"  Score: {d5['score']}")
    print(f"    Subscores: {d5['subscores']}")
    critical_high = [
        f for f in d5.get("findings", []) if f.get("severity") in ("CRITICAL", "HIGH")
    ]
    if critical_high:
        print(f"  Issues: {len(critical_high)}")
        for f in critical_high[:3]:
            print(f"    [{f['severity']}] {f['detail']}")

    # 计算加权总分
    total_score = sum(
        results[domain]["score"] * DOMAIN_WEIGHTS[domain] for domain in DOMAIN_WEIGHTS
    )

    results["overall"] = {
        "score": round(total_score, 1),
        "weighted_scores": {
            domain: round(results[domain]["score"] * DOMAIN_WEIGHTS[domain], 1)
            for domain in DOMAIN_WEIGHTS
        },
    }

    print(f"\n{'=' * 80}")
    print(f"总体结果: {total_score:.1f}")
    print(f"{'=' * 80}")
    for domain in DOMAIN_WEIGHTS:
        w = DOMAIN_WEIGHTS[domain]
        s = results[domain]["score"]
        ws = s * w
        print(f"  {domain}: {s:.1f} × {w} = {ws:.1f}")
    print(f"  Total: {total_score:.1f}")

    return results


def main():
    cards_dir = PROJECT_ROOT / "mas_eval" / "data" / "sample_cards"
    target_cards = ["maref.json", "percv.json", "skillos.json"]

    all_results = {}

    for card_name in target_cards:
        card_path = cards_dir / card_name
        if card_path.exists():
            results = evaluate_card(card_path)
            all_results[card_name] = results
        else:
            print(f"⚠️  Card not found: {card_path}")

    # 打印对比表
    print(f"\n{'=' * 80}")
    print("对比表")
    print(f"{'=' * 80}")
    print(f"{'仓库':<12} {'D1':<8} {'D2':<8} {'D3':<8} {'D4':<8} {'D5':<8} {'总分':<8}")
    print("-" * 80)

    for card_name, results in all_results.items():
        name = card_name.replace(".json", "").upper()
        overall = results.get("overall", {})
        print(
            f"{name:<12} "
            f"{results['D1']['score']:<8.1f} "
            f"{results['D2']['score']:<8.1f} "
            f"{results['D3']['score']:<8.1f} "
            f"{results['D4']['score']:<8.1f} "
            f"{results['D5']['score']:<8.1f} "
            f"{overall.get('score', 0):<8.1f}"
        )

    # 保存结果
    output_path = PROJECT_ROOT / "reports" / "audit_deep_evaluation.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存至: {output_path}")


if __name__ == "__main__":
    main()
