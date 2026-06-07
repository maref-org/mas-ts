#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""
Hardware Anchor Coefficient Generator
Usage: python generate_anchor.py --output report.json --runs 5

Runs standardized benchmarks (GEMM + LLM inference) and generates
a normalization coefficient relative to the official Docker-CPU baseline.
"""
import time
import json
import argparse
import subprocess
import sys
import os
import logging
from pathlib import Path

import numpy as np
import argcomplete
import tenacity
import requests

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from mas_eval import __version__ as VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Official Docker-CPU Baseline (Intel Xeon Platinum)
DOCKER_CPU_BASELINE = {
    "gemm_gflops": 12.5,
    "llm_ttft_ms": 8500.0,
    "llm_tpot_ms": 45.0,
    "source": "MAS-TS-001 Docker-CPU-Baseline v2026Q1"
}


def benchmark_gemm():
    """Run GEMM (General Matrix Multiply) benchmark."""
    sizes = [512, 1024, 2048]
    gflops_list = []

    for N in sizes:
        A = np.random.rand(N, N).astype(np.float32)
        B = np.random.rand(N, N).astype(np.float32)
        _ = A @ B  # Warmup

        times = []
        for _ in range(3):
            start = time.perf_counter()
            C = A @ B
            end = time.perf_counter()
            times.append(end - start)

        avg_time = np.mean(times)
        gflops = (2 * N ** 3) / (avg_time * 1e9)
        gflops_list.append(gflops)

    return float(np.mean(gflops_list))


def _llm_request(endpoint: str, headers: dict, payload: dict) -> dict:
    """Make LLM API request with automatic retry on transient errors."""
    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(
            (requests.exceptions.RequestException, tenacity.TryAgain)
        ),
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _request():
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        return resp.json()

    return _request()


def benchmark_llm():
    """Run LLM inference benchmark using reference model (Qwen2.5-7B)."""
    try:
        import requests
    except ImportError:
        logger.error("'requests' library not found. Install: pip install requests")
        sys.exit(1)

    ENDPOINT = os.getenv("ANCHOR_LLM_ENDPOINT", "http://localhost:8000/v1/chat/completions")
    MODEL = os.getenv("ANCHOR_LLM_MODEL", "qwen2.5-7b-instruct")

    test_prompt = (
        'Please summarize the following news in one sentence: '
        '"Scientists have discovered a new superconducting material that achieves zero-resistance transmission at room temperature, '
        'a breakthrough that could revolutionize energy transmission and quantum computing."'
    )

    headers = {"Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": test_prompt}],
        "max_tokens": 64,
        "temperature": 0.0
    }

    ttft_list = []
    tpot_list = []

    for _ in range(5):
        start = time.perf_counter()
        try:
            data = _llm_request(ENDPOINT, headers, payload)

            usage = data.get("usage", {})
            completion_tokens = usage.get("completion_tokens", 64)
            total_time = time.perf_counter() - start

            # Approximate TTFT as 30% of total time
            ttft = total_time * 0.3
            tpot = (total_time - ttft) / max(completion_tokens, 1)

            ttft_list.append(ttft * 1000)
            tpot_list.append(tpot * 1000)
        except Exception as e:
            logger.error("LLM benchmark failed: %s", e)
            logger.warning("Ensure Qwen2.5-7B is deployed locally (e.g., via Ollama: ollama run qwen2.5:7b)")
            sys.exit(1)

    return {
        "ttft_ms": float(np.median(ttft_list)),
        "tpot_ms": float(np.median(tpot_list))
    }


def detect_accelerator():
    """Auto-detect accelerator type."""
    info = {"type": "CPU", "vendor": "Generic", "details": ""}

    try:
        result = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info["type"] = "GPU"
            info["vendor"] = "NVIDIA"
            info["details"] = result.stdout.strip().split("\n")[0]
            return info
    except Exception:
        pass

    try:
        result = subprocess.run(["npu-smi", "info"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info["type"] = "NPU"
            info["vendor"] = "Ascend"
            info["details"] = "Ascend NPU detected"
            return info
    except Exception:
        pass

    try:
        result = subprocess.run(["rocm-smi"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and "Hygon" in result.stdout:
            info["type"] = "DCU"
            info["vendor"] = "Hygon"
            info["details"] = "Hygon DCU detected"
            return info
    except Exception:
        pass

    try:
        result = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=5)
        if "Apple" in result.stdout:
            info["type"] = "SoC"
            info["vendor"] = "Apple"
            info["details"] = result.stdout.strip()
            return info
    except Exception:
        pass

    return info


def print_accelerator_guide(vendor):
    guides = {
        "Ascend": """
[Ascend 910B Setup Guide]
1. Install CANN Toolkit: https://www.hiascend.com/software/cann/community
2. Use MindSpore or PyTorch NPU backend
3. Deploy vLLM-Ascend: https://github.com/vllm-project/vllm-ascend
4. Set env: export ANCHOR_LLM_ENDPOINT=http://localhost:8000/v1/chat/completions
""",
        "Hygon": """
[Hygon DCU Setup Guide]
1. Install DTK (DCU Toolkit): https://www.dtk-zn.com/
2. Use PyTorch ROCm backend (Hygon ROCm-compatible)
3. Deploy vLLM-ROCm: https://github.com/vllm-project/vllm/tree/main/examples/rocm
4. Set env: export ANCHOR_LLM_ENDPOINT=http://localhost:8000/v1/chat/completions
"""
    }
    if vendor in guides:
        print(guides[vendor])


def main():
    parser = argparse.ArgumentParser(description="MAS-TS-001 Hardware Anchor Coefficient Generator")
    parser.add_argument("--version", action="version", version=f"mas-eval-harness {VERSION}")
    parser.add_argument("--output", default="anchor_report.json", help="Output report path")
    parser.add_argument("--runs", type=int, default=5, help="LLM inference repeat count")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM test (CPU-only environment)")
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("MAS-TS-001 Hardware Anchor Coefficient Generator")
    logger.info("=" * 60)

    accel = detect_accelerator()
    logger.info("Detected Hardware: %s %s", accel['vendor'], accel['type'])
    logger.info("Details: %s", accel['details'])

    if accel["vendor"] in ["Ascend", "Hygon"]:
        print_accelerator_guide(accel["vendor"])

    logger.info("[1/3] Running GEMM matrix multiplication benchmark...")
    gemm_gflops = benchmark_gemm()
    logger.info("  Local GFLOPS: %.2f", gemm_gflops)
    logger.info("  Baseline GFLOPS: %.2f", DOCKER_CPU_BASELINE['gemm_gflops'])
    gemm_coeff = gemm_gflops / DOCKER_CPU_BASELINE["gemm_gflops"]
    logger.info("  GEMM Coefficient: %.2fx", gemm_coeff)

    llm_result = {"ttft_ms": None, "tpot_ms": None, "llm_coeff": None}

    if not args.skip_llm:
        logger.info("[2/3] Running LLM inference benchmark (Qwen2.5-7B)...")
        logger.info("  Ensure local deployment is available (e.g., Ollama: ollama run qwen2.5:7b)")
        llm_result = benchmark_llm()
        logger.info("  Local TTFT: %.1fms", llm_result['ttft_ms'])
        logger.info("  Baseline TTFT: %.1fms", DOCKER_CPU_BASELINE['llm_ttft_ms'])
        logger.info("  Local TPOT: %.1fms", llm_result['tpot_ms'])
        logger.info("  Baseline TPOT: %.1fms", DOCKER_CPU_BASELINE['llm_tpot_ms'])

        ttft_ratio = DOCKER_CPU_BASELINE["llm_ttft_ms"] / llm_result["ttft_ms"]
        tpot_ratio = DOCKER_CPU_BASELINE["llm_tpot_ms"] / llm_result["tpot_ms"]
        llm_coeff = (ttft_ratio * tpot_ratio) ** 0.5
        llm_result["llm_coeff"] = round(llm_coeff, 2)
        logger.info("  LLM Composite Coefficient: %.2fx", llm_coeff)
    else:
        logger.info("[2/3] Skipping LLM benchmark (--skip-llm)")

    logger.info("[3/3] Calculating composite normalization coefficient...")
    if llm_result.get("llm_coeff"):
        final_coeff = gemm_coeff * 0.4 + llm_result["llm_coeff"] * 0.6
    else:
        final_coeff = gemm_coeff

    logger.info("  Composite Coefficient: %.2fx", final_coeff)

    report = {
        "standard": "MAS-TS-001",
        "version": "v2.1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware": accel,
        "baseline": DOCKER_CPU_BASELINE,
        "results": {
            "gemm_gflops": round(gemm_gflops, 2),
            "gemm_coefficient": round(gemm_coeff, 2),
            "llm_ttft_ms": llm_result["ttft_ms"],
            "llm_tpot_ms": llm_result["tpot_ms"],
            "llm_coefficient": llm_result.get("llm_coeff"),
            "final_normalization_coefficient": round(final_coeff, 2)
        },
        "usage": {
            "latency_conversion": f"Measured Latency x {round(final_coeff, 2)} = Baseline-equivalent Latency",
            "example": f"If local Latency=10s, baseline-equivalent=10x{round(final_coeff, 2)}={round(10*final_coeff, 1)}s"
        },
        "submission_guide": {
            "to_community": "github.com/maa-swg/hardware-coefficients",
            "required_evidence": ["report.json", "3 repeated run logs"],
            "review_time": "7 business days"
        }
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("DONE: Report saved: %s", args.output)
    logger.info("SUBMIT: Submit this report for community review to join the official table")
    logger.info("CONVERT: When reporting latency, multiply by %.2fx to convert to baseline", round(final_coeff, 2))


if __name__ == "__main__":
    main()
