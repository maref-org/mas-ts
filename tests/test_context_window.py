from mas_eval.scoring.context_window import TRUNCATION_STRATEGIES, check_context_window


def test_context_window_normal():
    result = check_context_window(total_tokens=5000, max_tokens=128000)
    assert result["score"] > 95
    assert result["truncation_required"] is False
    assert len(result["findings"]) == 0


def test_context_window_near_limit():
    result = check_context_window(total_tokens=125000, max_tokens=128000)
    assert result["score"] < 10
    assert result["truncation_required"] is False
    assert any(f["category"] == "context_window_near_limit" for f in result["findings"])


def test_context_window_exceeded():
    result = check_context_window(total_tokens=200000, max_tokens=128000)
    assert result["score"] == 0.0
    assert result["truncation_required"] is True
    assert any(f["category"] == "context_window_exceeded" for f in result["findings"])


def test_context_window_invalid_strategy():
    result = check_context_window(
        card={"context_window": {"strategy": "unknown_strategy"}},
        total_tokens=1000,
        max_tokens=128000,
    )
    assert any(f["category"] == "context_window_invalid_strategy" for f in result["findings"])
    assert result["metrics"]["strategy_valid"] is False


def test_context_window_custom_max():
    result = check_context_window(
        card={"context_window": {"max_tokens": 64000}},
        total_tokens=32000,
        max_tokens=128000,
    )
    assert result["metrics"]["max_tokens"] == 64000
    assert result["metrics"]["utilization"] == 0.5


def test_truncation_strategies_defined():
    assert "drop_oldest" in TRUNCATION_STRATEGIES
    assert "summarize" in TRUNCATION_STRATEGIES
    assert "drop_lowest_score" in TRUNCATION_STRATEGIES


def test_context_window_empty_card():
    result = check_context_window(card={}, total_tokens=64000, max_tokens=128000)
    assert result["metrics"]["utilization"] == 0.5


def test_context_window_full_utilization():
    result = check_context_window(total_tokens=128000, max_tokens=128000)
    assert result["score"] == 0.0
    assert result["truncation_required"] is True
