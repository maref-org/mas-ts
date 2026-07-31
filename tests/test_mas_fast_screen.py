# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from tests.test_utils import load_module

mfs = load_module(
    "mas_fast_screen", Path(__file__).parent.parent / "mas_fast_screen.py"
)


class TestDetermineOverallStatus:
    def test_all_pass(self) -> None:
        stages = [{"status": "PASS"}, {"status": "PASS"}]
        assert mfs.determine_overall_status(stages) == "PASS"

    def test_fail_dominates(self) -> None:
        stages = [{"status": "PASS"}, {"status": "FAIL"}, {"status": "PASS"}]
        assert mfs.determine_overall_status(stages) == "FAIL"

    def test_timeout_dominates(self) -> None:
        stages = [{"status": "PASS"}, {"status": "TIMEOUT"}]
        assert mfs.determine_overall_status(stages) == "FAIL"

    def test_error_dominates(self) -> None:
        stages = [{"status": "PASS"}, {"status": "ERROR"}]
        assert mfs.determine_overall_status(stages) == "FAIL"


class TestGenerateTrafficLight:
    def test_pass_green(self) -> None:
        assert "🟢" in mfs.generate_traffic_light("PASS")

    def test_fail_red(self) -> None:
        assert "🔴" in mfs.generate_traffic_light("FAIL")

    def test_warning_yellow(self) -> None:
        assert "🟡" in mfs.generate_traffic_light("TIMEOUT")
        assert "🟡" in mfs.generate_traffic_light("ERROR")
        assert "🟡" in mfs.generate_traffic_light("UNKNOWN")
