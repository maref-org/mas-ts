#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""
Mock Drift Guard - Calibration Script (v2.0)
Usage:
  python mock_calibrate.py --golden golden_v2.3.json --mock-output mock_latest.json
  python mock_calibrate.py --golden-dir ./golden_trajectories --mock-dir ./mock_outputs --block
  python mock_calibrate.py --golden golden.json --mock-output mock.json --output report.json

Compares Mock LLM output against Golden Trajectory (real LLM recorded behavior).
Blocks release if drift exceeds thresholds.
"""

import argparse
import json
import logging
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

import argcomplete

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from mas_eval import __version__ as VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_trajectory(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in trajectory file %s: %s", path, e)
        sys.exit(1)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "events" in data:
        return data["events"]
    if isinstance(data, dict) and "trajectory" in data:
        return data["trajectory"]
    return [data]


def extract_tool_signature(event):
    if event.get("action", {}).get("type") != "tool_call":
        return None
    action = event["action"]
    params = sorted(action.get("input", {}).keys())
    return f"{action['tool_id']}:{','.join(params)}"


def extract_routing_decision(event):
    orch = event.get("orchestration", {})
    if orch.get("routing_decision"):
        return orch.get("routing_reason", "unknown")
    return None


def compare_trajectories(golden, mock, thresholds=None):
    thresholds = thresholds or {}
    threshold_seq = thresholds.get("sequence_similarity", 0.85)
    threshold_set = thresholds.get("set_similarity", 0.90)
    threshold_param = thresholds.get("param_match_rate", 0.80)

    golden_sigs = [
        extract_tool_signature(e) for e in golden if extract_tool_signature(e)
    ]
    mock_sigs = [extract_tool_signature(e) for e in mock if extract_tool_signature(e)]

    seq_sim = SequenceMatcher(None, golden_sigs, mock_sigs).ratio()

    golden_set = set(golden_sigs)
    mock_set = set(mock_sigs)
    set_sim = (
        len(golden_set & mock_set) / len(golden_set | mock_set)
        if (golden_set | mock_set)
        else 1.0
    )

    param_match = sum(1 for g, m in zip(golden_sigs, mock_sigs) if g == m) / max(
        len(golden_sigs), 1
    )

    golden_routes = [
        extract_routing_decision(e) for e in golden if extract_routing_decision(e)
    ]
    mock_routes = [
        extract_routing_decision(e) for e in mock if extract_routing_decision(e)
    ]
    route_match = 0
    if golden_routes and mock_routes:
        min_len = min(len(golden_routes), len(mock_routes))
        route_match = (
            sum(
                1
                for g, m in zip(golden_routes[:min_len], mock_routes[:min_len])
                if g == m
            )
            / min_len
        )

    drift_detected = (
        seq_sim < threshold_seq
        or set_sim < threshold_set
        or param_match < threshold_param
    )

    return {
        "sequence_similarity": round(seq_sim, 3),
        "set_similarity": round(set_sim, 3),
        "param_match_rate": round(param_match, 3),
        "route_match_rate": round(route_match, 3) if golden_routes else None,
        "golden_steps": len(golden_sigs),
        "mock_steps": len(mock_sigs),
        "step_delta": len(mock_sigs) - len(golden_sigs),
        "drift_detected": drift_detected,
        "thresholds": {
            "sequence_similarity": threshold_seq,
            "set_similarity": threshold_set,
            "param_match_rate": threshold_param,
        },
    }


def calibrate_pair(golden_path, mock_path, thresholds=None):
    golden = load_trajectory(golden_path)
    mock = load_trajectory(mock_path)
    result = compare_trajectories(golden, mock, thresholds)
    result["golden_file"] = str(golden_path)
    result["mock_file"] = str(mock_path)
    return result


def calibrate_directory(golden_dir, mock_dir, thresholds=None, skip_missing=False):
    results = []
    golden_path = Path(golden_dir)
    mock_path = Path(mock_dir)

    golden_files = {f.name: f for f in sorted(golden_path.glob("*.json"))}
    mock_files = {f.name: f for f in sorted(mock_path.glob("*.json"))}

    all_names = sorted(set(golden_files.keys()) | set(mock_files.keys()))

    for name in all_names:
        if name not in golden_files:
            if skip_missing:
                continue
            results.append(
                {
                    "task": name,
                    "status": "MISSING_GOLDEN",
                    "drift_detected": True,
                    "error": "No golden trajectory found",
                }
            )
            continue
        if name not in mock_files:
            if skip_missing:
                continue
            results.append(
                {
                    "task": name,
                    "status": "MISSING_MOCK",
                    "drift_detected": True,
                    "error": "No mock output found",
                }
            )
            continue

        try:
            result = calibrate_pair(
                str(golden_files[name]), str(mock_files[name]), thresholds
            )
            result["task"] = name
            result["status"] = "DRIFT" if result["drift_detected"] else "OK"
            results.append(result)
        except Exception as e:
            results.append(
                {
                    "task": name,
                    "status": "ERROR",
                    "drift_detected": True,
                    "error": str(e),
                }
            )

    return results


def main():
    parser = argparse.ArgumentParser(description="MAS-TS-001 Mock Drift Guard v2.0")
    parser.add_argument(
        "--version", action="version", version=f"mas-eval-harness {VERSION}"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--golden", help="Single Golden Trajectory JSON path")
    group.add_argument("--golden-dir", help="Directory of Golden Trajectory JSONs")
    parser.add_argument("--mock-output", help="Single Mock output trajectory JSON path")
    parser.add_argument("--mock-dir", help="Directory of Mock output trajectory JSONs")
    parser.add_argument(
        "--threshold-seq",
        type=float,
        default=0.85,
        help="Sequence similarity threshold",
    )
    parser.add_argument(
        "--threshold-set", type=float, default=0.90, help="Set similarity threshold"
    )
    parser.add_argument(
        "--threshold-param", type=float, default=0.80, help="Parameter match threshold"
    )
    parser.add_argument(
        "--block", action="store_true", help="Exit with error on drift detected"
    )
    parser.add_argument("--output", help="Save report to JSON file")
    parser.add_argument(
        "--skip-missing",
        action="store_true",
        help="Skip missing golden/mock pairs instead of marking as drift",
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    thresholds = {
        "sequence_similarity": args.threshold_seq,
        "set_similarity": args.threshold_set,
        "param_match_rate": args.threshold_param,
    }

    scanned_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if args.golden:
        if not args.mock_output:
            parser.error("--mock-output is required when using --golden")
        result = calibrate_pair(args.golden, args.mock_output, thresholds)
        report = {
            "standard": "MAS-TS-001",
            "version": "v3.0",
            "scanned_at": scanned_at,
            "mode": "single",
            "results": [result],
            "overall_passed": not result["drift_detected"],
        }
    elif args.golden_dir:
        if not args.mock_dir:
            parser.error("--mock-dir is required when using --golden-dir")
        results = calibrate_directory(
            args.golden_dir, args.mock_dir, thresholds, skip_missing=args.skip_missing
        )
        report = {
            "standard": "MAS-TS-001",
            "version": "v3.0",
            "scanned_at": scanned_at,
            "mode": "batch",
            "results": results,
            "overall_passed": not any(r.get("drift_detected", True) for r in results),
        }
    else:
        parser.error("Must specify --golden or --golden-dir")
        return

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info("Report saved to %s", args.output)

    if not report["overall_passed"] and args.block:
        logger.error(
            "Mock Drift exceeded thresholds! Update mock rules or adjust thresholds."
        )
        sys.exit(1)
    elif not report["overall_passed"]:
        logger.warning("Mock drift detected. Review and update mock rules.")
        sys.exit(0)
    else:
        logger.info("Mock matches Golden Trajectory. Release approved.")
        sys.exit(0)


if __name__ == "__main__":
    main()
