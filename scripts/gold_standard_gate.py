#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Gold Standard CI Gate — L0 Fast-Screen threshold enforcement.

Usage:
    python scripts/gold_standard_gate.py --card mas_eval/data/sample_cards/compliant_agent_v2.json
    python scripts/gold_standard_gate.py --cards-dir mas_eval/data/sample_cards/

Exits with code 1 if any card fails the L0 Gold Standard threshold check.
Designed to be run as a CI step after pytest.
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure the project root is on sys.path so the harness is importable.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from mas_eval.harness.l0_fast_screen import run_l0_fast_screen  # noqa: E402


def load_card(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_card(card_path: Path, verbose: bool = False) -> bool:
    """Run L0 fast-screen on a single card and return True if thresholds pass."""
    card = load_card(card_path)
    result = run_l0_fast_screen(card)
    threshold_check = result.get("threshold_check", {})

    passed = threshold_check.get("overall_pass", False)
    if verbose or not passed:
        print(f"  Card: {card_path.name}")
        print(f"    L0 status: {result.get('status', '?')}")
        print(f"    Threshold overall_pass: {passed}")
        metrics = threshold_check.get("metrics", {})
        for m_name, m_info in metrics.items():
            mark = "✓" if m_info.get("passed") else "✗"
            print(
                f"    {mark} {m_name}: {m_info.get('value', '?')}  (threshold: {m_info.get('threshold', '?')})"
            )
        print()
    return passed


def main():
    parser = argparse.ArgumentParser(description="Gold Standard L0 CI Gate")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--card", help="Path to a single agent card JSON")
    group.add_argument("--cards-dir", help="Directory of agent card JSONs")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print all results"
    )
    args = parser.parse_args()

    if args.card:
        paths = [Path(args.card)]
    else:
        paths = sorted(Path(args.cards_dir).glob("*.json"))

    if not paths:
        print("No card files found.")
        sys.exit(1)

    passed_all = True
    for p in paths:
        if not check_card(p, verbose=args.verbose):
            passed_all = False

    if passed_all:
        print(
            f"✅ Gold Standard L0 gate PASSED — all {len(paths)} card(s) meet thresholds."
        )
        sys.exit(0)
    else:
        print("❌ Gold Standard L0 gate FAILED — one or more cards below threshold.")
        sys.exit(1)


if __name__ == "__main__":
    main()
