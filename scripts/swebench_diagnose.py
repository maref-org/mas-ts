#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Attribute SWE-bench Lite failures to a concrete cause.

For each instance this reruns the official image on a *saved* model patch
(``--patch-dir/<instance>.patch``, produced by ``swebench_batch.py
--artifacts``), reruns the FAIL_TO_PASS tests with short tracebacks, and
compares the files the model touched against the reference patch.

It answers two questions only:

* which FAIL_TO_PASS test still fails, and with which assertion;
* did the model edit the same files as the reference fix.

It does not score, and it does not change the evidence mode.

Usage:
    python scripts/swebench_diagnose.py \
      --dataset /path/to/lite-astropy.json \
      --patch-dir /path/to/patches \
      --instances astropy__astropy-14182,astropy__astropy-14365 \
      --output /path/to/diagnosis.json
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
    parser = argparse.ArgumentParser(description="Attribute SWE-bench Lite failures")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--instances", required=True, help="Comma-separated ids")
    parser.add_argument(
        "--patch-dir",
        required=True,
        help="Directory holding <instance_id>.patch files",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--gold-control",
        action="store_true",
        help="Also run each instance with the reference patch (harness sanity check)",
    )
    args = parser.parse_args(argv)

    os.environ["SWE_BENCH_LITE_PATH"] = args.dataset

    from mas_eval.oracle.swe_bench import SWEBenchOracle

    patch_dir = Path(args.patch_dir)
    oracle = SWEBenchOracle()
    instances = [x.strip() for x in args.instances.split(",") if x.strip()]

    results = []
    for instance_id in instances:
        patch_file = patch_dir / f"{instance_id}.patch"
        if not patch_file.exists():
            print(f"{instance_id}: patch not found, skipped", file=sys.stderr)
            results.append(
                {"instance_id": instance_id, "error": "patch_missing"}
            )
            continue

        model_patch = patch_file.read_text(encoding="utf-8")
        print(f"{instance_id}: diagnosing ...", flush=True)
        diagnosis = oracle.diagnose_instance(instance_id, model_patch)
        results.append(diagnosis)
        print(
            f"{instance_id}: passed={diagnosis['passed']} failed={diagnosis['failed']}"
            f" failing={[f['test'] for f in diagnosis['failing']]}"
            f" only_gold={diagnosis['patch_diff']['only_gold']}",
            flush=True,
        )

        if args.gold_control:
            task = next(
                (t for t in oracle._load_tasks() if t["task_id"] == instance_id),
                None,
            )
            gold_patch = (task or {}).get("gold_patch", "")
            control = oracle.diagnose_instance(instance_id, gold_patch)
            diagnosis["gold_control"] = {
                "passed": control["passed"],
                "failed": control["failed"],
                "total": control["total"],
                "failing": [f["test"] for f in control["failing"]],
                "error": control["error"],
            }
            print(
                f"{instance_id}: gold control passed={control['passed']}"
                f" failed={control['failed']}",
                flush=True,
            )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"written: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
