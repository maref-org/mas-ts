from mas_eval.scoring.slo import check_slo, get_level_slo_summary, reset_slo_state


def test_slo_passes_all_metrics():
    reset_slo_state()
    metrics = {"d1_compliance": 100, "d2_tool_coverage": 95, "d3_spawn_rate": 99}
    result = check_slo(metrics, level="L0")
    assert result["overall_pass"] is True
    assert result["total_checks"] == 3
    assert result["passed_checks"] == 3
    assert len(result["violations"]) == 0


def test_slo_detects_violation():
    reset_slo_state()
    metrics = {"d1_compliance": 50}
    result = check_slo(metrics, level="L0")
    assert result["overall_pass"] is False
    assert len(result["violations"]) == 1
    assert result["violations"][0]["metric"] == "d1_compliance"


def test_slo_lower_is_better():
    reset_slo_state()
    metrics = {"d3_message_efficiency": 999, "d4_pentest": 99}
    result = check_slo(metrics, level="L3")
    assert result["overall_pass"] is False
    assert len(result["violations"]) == 2


def test_slo_budget_tracks_violations():
    reset_slo_state()
    for _ in range(10):
        check_slo({"d1_compliance": 50}, level="L0")
    result = check_slo({"d1_compliance": 100}, level="L0")
    assert result["metrics"]["d1_compliance"]["violations_since_start"] == 10
    assert result["metrics"]["d1_compliance"]["budget_remaining"] < 1.0


def test_slo_budget_exhaustion():
    reset_slo_state()
    for _ in range(11):
        check_slo({"d1_compliance": 0}, level="L0")
    result = check_slo({"d1_compliance": 0}, level="L0")
    m = result["metrics"]["d1_compliance"]
    assert m["budget_exhausted"] is True or m["violations_since_start"] >= 10


def test_get_level_slo_summary():
    reset_slo_state()
    check_slo({"d1_compliance": 50}, level="L0")
    check_slo({"d1_compliance": 50}, level="L0")
    summary = get_level_slo_summary("L0")
    assert summary["total_violations"] == 2
    assert "d1_compliance" in summary["metrics"]


def test_get_level_slo_summary_empty_level():
    reset_slo_state()
    summary = get_level_slo_summary("L4")
    assert summary["total_violations"] == 0
    assert summary["total_budgets_exhausted"] == 0


def test_slo_unknown_level():
    reset_slo_state()
    result = check_slo({}, level="L99")
    assert "error" in result


def test_slo_burn_rate_no_violations():
    reset_slo_state()
    result = check_slo({"d1_compliance": 100}, level="L0", budget_window_hours=1)
    m = result["metrics"]["d1_compliance"]
    assert m["violations_since_start"] == 0
    assert m["budget_remaining"] == 1.0
