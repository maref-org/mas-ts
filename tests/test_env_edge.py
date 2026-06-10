# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Extended environment detection tests covering edge case paths."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.oracle.env import check_docker, check_playwright, check_stress_ng


class TestCheckDockerEdgeCases:
    def test_docker_not_in_path(self, monkeypatch):
        monkeypatch.setattr("mas_eval.oracle.env.shutil.which", lambda _: None)
        ok, msg = check_docker()
        assert ok is False
        assert "not found" in msg

    def test_docker_oserror(self, monkeypatch):
        monkeypatch.setattr(
            "mas_eval.oracle.env.shutil.which", lambda _: "/usr/bin/docker"
        )

        def _raise_oserror(*args, **kwargs):
            raise OSError("connection refused")

        monkeypatch.setattr("mas_eval.oracle.env.subprocess.run", _raise_oserror)
        ok, msg = check_docker()
        assert ok is False
        assert "error" in msg

    def test_docker_timeout(self, monkeypatch):
        monkeypatch.setattr(
            "mas_eval.oracle.env.shutil.which", lambda _: "/usr/bin/docker"
        )

        def _raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="docker ps", timeout=10)

        monkeypatch.setattr("mas_eval.oracle.env.subprocess.run", _raise_timeout)
        ok, msg = check_docker()
        assert ok is False
        assert "timed out" in msg

    def test_docker_file_not_found(self, monkeypatch):
        monkeypatch.setattr(
            "mas_eval.oracle.env.shutil.which", lambda _: "/usr/bin/docker"
        )

        def _raise_fnf(*args, **kwargs):
            raise FileNotFoundError("docker not found")

        monkeypatch.setattr("mas_eval.oracle.env.subprocess.run", _raise_fnf)
        ok, msg = check_docker()
        assert ok is False
        assert "not found" in msg


class TestCheckPlaywrightEdgeCases:
    def test_playwright_not_installed(self, monkeypatch):
        def _raise_import(*args, **kwargs):
            raise ImportError("no module named playwright")

        monkeypatch.setattr("builtins.__import__", _raise_import)
        ok, msg = check_playwright()
        assert ok is False
        assert "not installed" in msg

    def test_playwright_installed_returns_true(self):
        ok, msg = check_playwright()
        assert ok is True
        assert "installed" in msg


class TestCheckStressNgEdgeCases:
    def test_stress_ng_not_in_path(self, monkeypatch):
        monkeypatch.setattr("mas_eval.oracle.env.shutil.which", lambda _: None)
        ok, msg = check_stress_ng()
        assert ok is False
        assert "not found" in msg

    def test_stress_ng_run_error(self, monkeypatch):
        monkeypatch.setattr(
            "mas_eval.oracle.env.shutil.which", lambda _: "/usr/bin/stress-ng"
        )

        def _run_error(*args, **kwargs):
            result = subprocess.CompletedProcess(
                args=["stress-ng"], returncode=1, stderr="error message", stdout=""
            )
            return result

        monkeypatch.setattr("mas_eval.oracle.env.subprocess.run", _run_error)
        ok, msg = check_stress_ng()
        assert ok is False
        assert "error" in msg

    def test_stress_ng_timeout(self, monkeypatch):
        monkeypatch.setattr(
            "mas_eval.oracle.env.shutil.which", lambda _: "/usr/bin/stress-ng"
        )

        def _raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="stress-ng", timeout=5)

        monkeypatch.setattr("mas_eval.oracle.env.subprocess.run", _raise_timeout)
        ok, msg = check_stress_ng()
        assert ok is False
        assert "timed out" in msg or "failed" in msg

    def test_stress_ng_oserror(self, monkeypatch):
        monkeypatch.setattr(
            "mas_eval.oracle.env.shutil.which", lambda _: "/usr/bin/stress-ng"
        )

        def _raise_os(*args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr("mas_eval.oracle.env.subprocess.run", _raise_os)
        ok, msg = check_stress_ng()
        assert ok is False
        assert "failed" in msg

    def test_stress_ng_file_not_found(self, monkeypatch):
        monkeypatch.setattr(
            "mas_eval.oracle.env.shutil.which", lambda _: "/usr/bin/stress-ng"
        )

        def _raise_fnf(*args, **kwargs):
            raise FileNotFoundError("stress-ng disappeared")

        monkeypatch.setattr("mas_eval.oracle.env.subprocess.run", _raise_fnf)
        ok, msg = check_stress_ng()
        assert ok is False
        assert "failed" in msg
