# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mfs = load_module(
    "mas_fast_screen", Path(__file__).parent.parent / "mas_fast_screen.py"
)


class TestDetermineOverallStatus:
    def test_all_pass(self):
        stages = [{"status": "PASS"}, {"status": "PASS"}]
        assert mfs.determine_overall_status(stages) == "PASS"

    def test_fail_dominates(self):
        stages = [{"status": "PASS"}, {"status": "FAIL"}, {"status": "PASS"}]
        assert mfs.determine_overall_status(stages) == "FAIL"

    def test_timeout_dominates(self):
        stages = [{"status": "PASS"}, {"status": "TIMEOUT"}]
        assert mfs.determine_overall_status(stages) == "FAIL"

    def test_error_dominates(self):
        stages = [{"status": "PASS"}, {"status": "ERROR"}]
        assert mfs.determine_overall_status(stages) == "FAIL"


class TestGenerateTrafficLight:
    def test_pass_green(self):
        assert "🟢" in mfs.generate_traffic_light("PASS")

    def test_fail_red(self):
        assert "🔴" in mfs.generate_traffic_light("FAIL")

    def test_warning_yellow(self):
        assert "🟡" in mfs.generate_traffic_light("TIMEOUT")
        assert "🟡" in mfs.generate_traffic_light("ERROR")
        assert "🟡" in mfs.generate_traffic_light("UNKNOWN")
