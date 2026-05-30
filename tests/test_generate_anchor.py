import importlib.util
from pathlib import Path

import pytest

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

ga = load_module("generate_anchor", Path(__file__).parent.parent / "generate_anchor.py")


class TestBenchmarkGemm:
    def test_gemm_returns_positive_float(self):
        result = ga.benchmark_gemm()
        assert isinstance(result, float)
        assert result > 0

    def test_gemm_reasonable_range(self):
        result = ga.benchmark_gemm()
        assert 0.1 < result < 100000


class TestDetectAccelerator:
    def test_detects_something(self):
        result = ga.detect_accelerator()
        assert "type" in result
        assert "vendor" in result
        assert "details" in result

    def test_mac_detection_on_apple_hardware(self):
        result = ga.detect_accelerator()
        assert result["vendor"] in ("Apple", "Generic", "NVIDIA", "Ascend", "Hygon")


class TestDockerCPUBaseline:
    def test_baseline_values_present(self):
        assert ga.DOCKER_CPU_BASELINE["gemm_gflops"] > 0
        assert ga.DOCKER_CPU_BASELINE["llm_ttft_ms"] > 0
        assert ga.DOCKER_CPU_BASELINE["llm_tpot_ms"] > 0
