from api.error_codes import ERR_MAP, HITL_STATE_TRANSITIONS, build_error_response


def test_all_errors_have_http_status():
    for code, entry in ERR_MAP.items():
        assert "http_status" in entry, f"{code} missing http_status"
        assert "message" in entry, f"{code} missing message"


def test_build_error_response_uses_code():
    resp = build_error_response("invalid_level")
    assert resp["error"] == "invalid_level"
    assert resp["message"] == "Invalid evaluation level. Must be L0-L4."


def test_build_error_response_with_detail():
    resp = build_error_response("invalid_level", "L5 is not valid")
    assert resp["detail"] == "L5 is not valid"


def test_build_error_response_fallback():
    resp = build_error_response("unknown_code")
    assert resp["error"] == "unknown_code"
    assert resp["message"] == "Internal server error."


def test_hitl_state_transitions_pending():
    transitions = HITL_STATE_TRANSITIONS["pending"]
    assert "confirmed" in transitions
    assert "cancelled" in transitions
    assert "paused" in transitions


def test_hitl_state_transitions_cancelled():
    assert HITL_STATE_TRANSITIONS["cancelled"] == []


def test_hitl_state_paused_valid_transitions():
    transitions = HITL_STATE_TRANSITIONS["paused"]
    assert "confirmed" in transitions
    assert "cancelled" in transitions


def test_all_hitl_states_defined():
    expected = {"pending", "confirmed", "cancelled", "paused"}
    assert set(HITL_STATE_TRANSITIONS.keys()) == expected


def test_http_status_mapping():
    assert ERR_MAP["invalid_level"]["http_status"] == 400
    assert ERR_MAP["task_not_found"]["http_status"] == 404
    assert ERR_MAP["rate_limit_exceeded"]["http_status"] == 429
    assert ERR_MAP["evaluation_failed"]["http_status"] == 500
    assert ERR_MAP["card_validation_failed"]["http_status"] == 422
