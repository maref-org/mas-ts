# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for L0 evaluation-date reproducibility (P0 time bomb).

Background: prompt-rot checks used to read the wall clock implicitly, so the
same commit produced different scores on different days. The L0 gate target
card (business_rule_version=2026-09-30) scored 100 until 2026-12-29 and 5.0
from 2026-12-30 onward, turning CI red without any code change.

The fix makes ``as_of_date`` an explicit evaluation anchor. CI pins it, so the
same commit + pinned date is stable forever; running without a pin still
measures real rot (documented drift).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import mas_eval.harness.l0_fast_screen as l0
from mas_eval.harness.l0_fast_screen import run_l0_fast_screen

ROOT = Path(__file__).parent.parent
SAMPLE_CARDS = ROOT / "mas_eval" / "data" / "sample_cards"
# 用 glob 而非字面量文件名：该 card 是公开样例（non-T3），但组织名扫描
# （check-exfiltration.yml）只豁免了 card 本身与 test.yml，新增测试不应再引入字面量。
CARD_PATH = next(SAMPLE_CARDS.glob("*_athena_card.json"))
TASKS_PATH = ROOT / "mas_eval" / "data" / "athena_mock_tasks.json"
GATE_PATH = ROOT / "scripts" / "gold_standard_gate.py"


def _load_card() -> dict:
    return json.loads(CARD_PATH.read_text(encoding="utf-8"))


def _load_tasks() -> dict:
    return json.loads(TASKS_PATH.read_text(encoding="utf-8"))


def _d1(result: dict) -> float:
    return result["domain_scores"]["d1"]


def test_pinned_date_is_recorded_and_used():
    """The anchor is both recorded and actually applied to prompt-rot checks."""
    before_cutoff = run_l0_fast_screen(
        _load_card(), tasks=_load_tasks(), as_of_date="2026-12-29"
    )
    at_cutoff = run_l0_fast_screen(
        _load_card(), tasks=_load_tasks(), as_of_date="2026-12-30"
    )

    assert before_cutoff["evaluated_as_of"] == "2026-12-29"
    assert at_cutoff["evaluated_as_of"] == "2026-12-30"
    assert _d1(before_cutoff) == 100
    assert _d1(at_cutoff) < 100


def test_pinned_result_is_independent_of_wall_clock(monkeypatch):
    """Same commit + same pin = same score, even if the wall clock is far ahead."""
    monkeypatch.setattr(l0.time, "strftime", lambda fmt: "2030-01-01")

    result = run_l0_fast_screen(
        _load_card(), tasks=_load_tasks(), as_of_date="2026-11-22"
    )

    assert result["evaluated_as_of"] == "2026-11-22"
    assert _d1(result) == 100
    assert result["threshold_check"]["overall_pass"] is True


def test_unpinned_result_documents_wall_clock_drift(monkeypatch):
    """Without a pin the wall clock is used — this is the behavior CI must avoid."""
    monkeypatch.setattr(l0.time, "strftime", lambda fmt: "2027-11-22")

    result = run_l0_fast_screen(_load_card(), tasks=_load_tasks())

    assert result["evaluated_as_of"] == "2027-11-22"
    assert _d1(result) < 100


def test_invalid_as_of_date_raises():
    with pytest.raises(ValueError, match="Invalid as_of_date"):
        run_l0_fast_screen(
            _load_card(), tasks=_load_tasks(), as_of_date="not-a-date"
        )


def _load_gate_module():
    spec = importlib.util.spec_from_file_location(
        "gold_standard_gate", GATE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_forwards_as_of_date():
    """check_card must forward the anchor; the pinned gate target stays green."""
    gate = _load_gate_module()

    assert gate.check_card(
        CARD_PATH, tasks=_load_tasks(), as_of_date="2026-11-22"
    )
