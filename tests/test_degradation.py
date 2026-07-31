from mas_eval.scoring.degradation import (
    DEFAULT_FALLBACK_CONFIG,
    DegradationMode,
    build_degradation_assessment,
    determine_degradation_mode,
)


def test_normal_mode_no_failures():
    mode = determine_degradation_mode(failures=0)
    assert mode == DegradationMode.NORMAL


def test_degraded_after_3_failures():
    mode = determine_degradation_mode(failures=3)
    assert mode == DegradationMode.DEGRADED


def test_fallback_when_available_after_5_failures():
    mode = determine_degradation_mode(failures=5, fallback_available=True)
    assert mode == DegradationMode.FALLBACK


def test_degraded_when_no_fallback():
    mode = determine_degradation_mode(failures=5, fallback_available=False)
    assert mode == DegradationMode.DEGRADED


def test_blocked_with_critical_findings():
    mode = determine_degradation_mode(critical_findings=1)
    assert mode == DegradationMode.BLOCKED


def test_blocked_at_10_failures():
    mode = determine_degradation_mode(failures=10)
    assert mode == DegradationMode.BLOCKED


def test_build_assessment_normal():
    result = build_degradation_assessment("database", failures=0)
    assert result["mode"] == "normal"
    assert result["action_required"] is False
    assert len(result["findings"]) == 0


def test_build_assessment_blocked():
    result = build_degradation_assessment("llm", critical_findings=1)
    assert result["mode"] == "blocked"
    assert result["action_required"] is True
    assert any("blocked" in f["category"] for f in result["findings"])


def test_build_assessment_fallback():
    result = build_degradation_assessment(
        "cache", failures=5, fallback_available=True
    )
    assert result["mode"] == "fallback"
    assert any("fallback" in f["category"] for f in result["findings"])


def test_default_config_present():
    assert "timeout_seconds" in DEFAULT_FALLBACK_CONFIG
    assert "retry_count" in DEFAULT_FALLBACK_CONFIG
    assert DEFAULT_FALLBACK_CONFIG["retry_backoff_base"] == 2.0


def test_degradation_level_normal():
    result = build_degradation_assessment("test", failures=0)
    assert result["degradation_level"] == 0.0


def test_degradation_level_blocked():
    result = build_degradation_assessment("test", failures=10)
    assert result["degradation_level"] >= 0.5


def test_all_modes_enum():
    assert len(DegradationMode) == 5
    assert DegradationMode.NORMAL.value == "normal"
    assert DegradationMode.BLOCKED.value == "blocked"
