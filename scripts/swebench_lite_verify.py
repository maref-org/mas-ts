#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Verify one official SWE-bench Lite instance against a unified diff.

The dataset is never stored in this repository. Export the rows you need to a
local JSON file (list of instances) and pass it with ``--dataset``.

Usage:
    python scripts/swebench_lite_verify.py \
        --dataset /path/to/lite-astropy.json \
        --instance astropy__astropy-12907 \
        --patch /path/to/model.patch

    # self-check with the dataset's gold patch
    python scripts/swebench_lite_verify.py \
        --dataset /path/to/lite-astropy.json \
        --instance astropy__astropy-12907 --gold

Exit codes: 0 resolved, 1 not resolved / error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify one SWE-bench Lite instance")
    parser.add_argument("--dataset", required=True, help="Local JSON list of instances")
    parser.add_argument("--instance", required=True, help="instance_id to verify")
    parser.add_argument("--patch", help="Unified diff produced by the agent")
    parser.add_argument(
        "--gold",
        action="store_true",
        help="Use the dataset's reference patch (self-check)",
    )
    parser.add_argument(
        "--namespace",
        default="swebench",
        help="Docker Hub namespace for official images",
    )
    args = parser.parse_args(argv)

    if not args.gold and not args.patch:
        parser.error("provide --patch or --gold")

    dataset = Path(args.dataset)
    if not dataset.exists():
        parser.error(f"dataset not found: {dataset}")
    if args.patch and not Path(args.patch).exists():
        parser.error(f"patch not found: {args.patch}")

    os.environ["SWE_BENCH_LITE_PATH"] = str(dataset)

    from mas_eval.oracle.swe_bench import SWEBenchOracle, official_image_name

    oracle = SWEBenchOracle()
    task_data = next(
        (t for t in oracle._load_tasks() if t["task_id"] == args.instance), None
    )
    if task_data is None:
        print(f"instance not found: {args.instance}", file=sys.stderr)
        return 1

    if args.gold:
        model_patch = task_data.get("gold_patch", "")
    else:
        model_patch = Path(args.patch).read_text(encoding="utf-8")

    print(f"instance: {args.instance}")
    print(f"image:    {task_data.get('image') or official_image_name(args.instance, args.namespace)}")
    print(f"tests:    {len(task_data.get('FAIL_TO_PASS', []))} FAIL_TO_PASS + "
          f"{len(task_data.get('PASS_TO_PASS', []))} PASS_TO_PASS")

    result = oracle.verify_instance(args.instance, model_patch)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("resolved") else 1


if __name__ == "__main__":
    sys.exit(main())
