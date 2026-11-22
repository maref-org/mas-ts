# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Evidence-mode contract tests (P0-2 option A).

The harness must never present caller-supplied artifacts as proof that an agent
performed a task. Every result carries an explicit ``evidence_mode`` so reports
and consumers can tell the difference.
"""

from __future__ import annotations

import json
from pathlib import Path

from api.schemas import EvaluationResponse
from mas_eval.evidence import (
    CURRENT_EVIDENCE_MODE,
    EVIDENCE_MODE_DECLARED,
    EVIDENCE_MODE_LIVE,
    VALID_EVIDENCE_MODES,
)
from mas_eval.harness.aggregation import aggregate_level, compute_gold_report
from mas_eval.harness.l0_fast_screen import run_l0_fast_screen

ROOT = Path(__file__).parent.parent
CARD_PATH = next((ROOT / "mas_eval" / "data" / "sample_cards").glob("*_athena_card.json"))


def _load_card() -> dict:
    return json.loads(CARD_PATH.read_text(encoding="utf-8"))


def test_evidence_mode_constants():
    assert EVIDENCE_MODE_DECLARED == "declared_input"
    assert EVIDENCE_MODE_LIVE == "live_run"
    assert VALID_EVIDENCE_MODES == {EVIDENCE_MODE_DECLARED, EVIDENCE_MODE_LIVE}
    assert CURRENT_EVIDENCE_MODE in VALID_EVIDENCE_MODES


def test_l0_result_declares_evidence_mode():
    result = run_l0_fast_screen(_load_card(), as_of_date="2026-11-22")
    assert result["evidence_mode"] == EVIDENCE_MODE_DECLARED


def test_aggregate_level_declares_evidence_mode():
    domain_results = {
        "d1": {"score": 100.0, "findings": []},
        "d2": {"score": 90.0, "findings": []},
        "d3": {"score": 90.0, "findings": []},
    }
    result = aggregate_level("L1", "Standard", 0.0, domain_results)
    assert result["evidence_mode"] == EVIDENCE_MODE_DECLARED


def test_gold_report_declares_evidence_mode():
    domain_results = {
        "d1": {"score": 100.0, "findings": []},
        "d2": {"score": 90.0, "findings": []},
        "d3": {"score": 90.0, "findings": []},
        "d4": {"score": 90.0, "findings": []},
        "d5": {"score": 90.0, "findings": []},
    }
    result = compute_gold_report(domain_results)
    assert result["evidence_mode"] == EVIDENCE_MODE_DECLARED


def test_api_schema_exposes_evidence_mode():
    model = EvaluationResponse(
        level="L0",
        name="Fast-Screen",
        status="PASS",
        elapsed_seconds=1.0,
        evidence_mode=EVIDENCE_MODE_DECLARED,
    )
    assert model.evidence_mode == EVIDENCE_MODE_DECLARED
