# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import requests
import tenacity
import pytest

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

ga_mod = load_module("generate_anchor", Path(__file__).parent.parent / "generate_anchor.py")


def _make_http_error(status_code, text):
    resp = requests.Response()
    resp.status_code = status_code
    resp.encoding = "utf-8"
    resp._content = text.encode("utf-8")
    return requests.exceptions.HTTPError(f"{status_code} {text}", response=resp)


class TestLlmRequest:
    def test_retry_on_429_then_success(self):
        """_llm_request retries on 429 then succeeds."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = [
            _make_http_error(429, "Too Many Requests"),
            _make_http_error(429, "Too Many Requests"),
            None
        ]
        mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = ga_mod._llm_request("http://localhost:8000/v1", {}, {})

        assert mock_post.call_count == 3
        assert result["choices"][0]["message"]["content"] == "ok"

    def test_retry_on_500_then_success(self):
        """_llm_request retries on 500 then succeeds."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = [
            _make_http_error(500, "Server Error"),
            None
        ]
        mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = ga_mod._llm_request("http://localhost:8000/v1", {}, {})

        assert mock_post.call_count == 2
        assert result["choices"][0]["message"]["content"] == "ok"

    def test_gives_up_after_max_retries(self):
        """_llm_request raises RetryError after retries exhausted."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = _make_http_error(503, "Unavailable")

        with patch("requests.post", return_value=mock_response):
            with pytest.raises((tenacity.RetryError, requests.exceptions.RequestException)):
                ga_mod._llm_request("http://localhost:8000/v1", {}, {})

    def test_success_on_first_try(self):
        """_llm_request succeeds on first attempt."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"usage": {"completion_tokens": 64}}

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = ga_mod._llm_request("http://localhost:8000/v1", {}, {})

        assert mock_post.call_count == 1
        assert result["usage"]["completion_tokens"] == 64


class TestBenchmarkLlm:
    def test_benchmark_llm_success(self):
        """benchmark_llm returns ttft_ms and tpot_ms."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "usage": {"completion_tokens": 64},
            "choices": [{"message": {"content": "summary"}}]
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = ga_mod.benchmark_llm()

        assert mock_post.call_count == 5
        assert "ttft_ms" in result
        assert "tpot_ms" in result
        assert result["ttft_ms"] > 0
        assert result["tpot_ms"] > 0

    def test_benchmark_llm_fails_after_retries(self):
        """benchmark_llm sys.exits when API persistently fails."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = _make_http_error(503, "Unavailable")

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(SystemExit):
                ga_mod.benchmark_llm()

    def test_benchmark_llm_request_exception_direct(self):
        """benchmark_llm catches RequestException from _llm_request."""
        with patch.object(ga_mod, "_llm_request", side_effect=requests.exceptions.RequestException("connection error")):
            with pytest.raises(SystemExit):
                ga_mod.benchmark_llm()


class TestDetectAccelerator:
    def test_nvidia_gpu(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "GPU 0: Tesla V100"
        with patch.object(subprocess, "run", return_value=mock_proc):
            result = ga_mod.detect_accelerator()
        assert result["type"] == "GPU"
        assert result["vendor"] == "NVIDIA"

    def test_ascend_npu(self):
        def mock_subprocess(cmd, **kw):
            cmd_str = " ".join(cmd)
            mock_proc = MagicMock()
            if "nvidia-smi" in cmd_str:
                mock_proc.returncode = 1
            elif "npu-smi" in cmd_str:
                mock_proc.returncode = 0
                mock_proc.stdout = "NPU detected"
            else:
                mock_proc.returncode = 1
            return mock_proc
        with patch.object(subprocess, "run", side_effect=mock_subprocess):
            result = ga_mod.detect_accelerator()
        assert result["type"] == "NPU"
        assert result["vendor"] == "Ascend"

    def test_hygon_dcu(self):
        def mock_subprocess(cmd, **kw):
            cmd_str = " ".join(cmd)
            mock_proc = MagicMock()
            if "nvidia-smi" in cmd_str or "npu-smi" in cmd_str:
                mock_proc.returncode = 1
            elif "rocm-smi" in cmd_str:
                mock_proc.returncode = 0
                mock_proc.stdout = "Hygon DCU detected"
            else:
                mock_proc.returncode = 1
            return mock_proc
        with patch.object(subprocess, "run", side_effect=mock_subprocess):
            result = ga_mod.detect_accelerator()
        assert result["type"] == "DCU"
        assert result["vendor"] == "Hygon"

    def test_apple_soc(self):
        def mock_subprocess(cmd, **kw):
            cmd_str = " ".join(cmd)
            mock_proc = MagicMock()
            if "nvidia-smi" in cmd_str or "npu-smi" in cmd_str or "rocm-smi" in cmd_str:
                mock_proc.returncode = 1
            elif "sysctl" in cmd_str:
                mock_proc.returncode = 0
                mock_proc.stdout = "Apple M3"
            else:
                mock_proc.returncode = 1
            return mock_proc
        with patch.object(subprocess, "run", side_effect=mock_subprocess):
            result = ga_mod.detect_accelerator()
        assert result["type"] == "SoC"
        assert result["vendor"] == "Apple"

    def test_fallback_to_cpu(self):
        with patch.object(subprocess, "run", side_effect=FileNotFoundError("no such binary")):
            result = ga_mod.detect_accelerator()
        assert result["type"] == "CPU"
        assert result["vendor"] == "Generic"


class TestPrintAcceleratorGuide:
    def test_ascend_guide_prints(self, capsys):
        ga_mod.print_accelerator_guide("Ascend")
        captured = capsys.readouterr()
        assert "CANN Toolkit" in captured.out

    def test_hygon_guide_prints(self, capsys):
        ga_mod.print_accelerator_guide("Hygon")
        captured = capsys.readouterr()
        assert "DTK" in captured.out

    def test_unknown_vendor_no_output(self, capsys):
        ga_mod.print_accelerator_guide("NVIDIA")
        captured = capsys.readouterr()
        assert captured.out == ""


class TestMainFunction:
    @patch.object(ga_mod, "benchmark_gemm", return_value=50.0)
    @patch.object(ga_mod, "detect_accelerator", return_value={"type": "CPU", "vendor": "Generic", "details": ""})
    def test_main_with_skip_llm(self, mock_accel, mock_gemm):
        test_args = ["generate_anchor.py", "--output", "/tmp/anchor.json", "--skip-llm"]
        with patch.object(sys, "argv", test_args), patch("builtins.open"):
            ga_mod.main()

    @patch.object(ga_mod, "benchmark_gemm", return_value=50.0)
    @patch.object(ga_mod, "detect_accelerator", return_value={"type": "GPU", "vendor": "NVIDIA", "details": "Tesla V100"})
    def test_main_with_ascend_prints_guide(self, mock_accel, mock_gemm, capsys):
        test_args = ["generate_anchor.py", "--output", "/tmp/anchor.json", "--skip-llm"]
        with patch.object(sys, "argv", test_args), patch("builtins.open"):
            ga_mod.main()
        captured = capsys.readouterr()
        assert "Ascend" not in captured.out  # Not Ascend, so no guide

    @patch.object(ga_mod, "benchmark_gemm", return_value=50.0)
    @patch.object(ga_mod, "detect_accelerator", return_value={"type": "NPU", "vendor": "Ascend", "details": "Ascend NPU"})
    def test_main_ascend_prints_guide(self, mock_accel, mock_gemm, capsys):
        test_args = ["generate_anchor.py", "--output", "/tmp/anchor.json", "--skip-llm"]
        with patch.object(sys, "argv", test_args), patch("builtins.open"):
            ga_mod.main()
        captured = capsys.readouterr()
        assert "CANN" in captured.out

    @patch.object(ga_mod, "benchmark_gemm", return_value=50.0)
    @patch.object(ga_mod, "detect_accelerator", return_value={"type": "CPU", "vendor": "Generic", "details": ""})
    @patch.object(ga_mod, "benchmark_llm", return_value={"ttft_ms": 100.0, "tpot_ms": 10.0, "llm_coeff": 1.5})
    def test_main_with_llm(self, mock_llm, mock_accel, mock_gemm):
        test_args = ["generate_anchor.py", "--output", "/tmp/anchor.json"]
        with patch.object(sys, "argv", test_args), patch("builtins.open"):
            ga_mod.main()
