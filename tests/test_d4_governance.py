"""Tests for D4: Governance (MAS-TS-001 v3.0)

Covers: StateMachine, CircuitBreaker, OscillationDetector, AuditTrail
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d4_governance_security import (
    StateMachine, CircuitBreaker, CircuitBreakerState,
    OscillationDetector, AuditTrail,
    run_d4_governance,
    STATE_NAMES, GRAY_CODES, STATE_GRAY, GRAY_STATE,
    GOVERNANCE_WEIGHTS,
)


class TestStateMachine:
    def test_initial_state(self):
        sm = StateMachine()
        assert sm.current == "INIT"

    def test_valid_transition(self):
        sm = StateMachine()
        assert sm.transition("OBSERVE") is True
        assert sm.current == "OBSERVE"

    def test_invalid_transition(self):
        sm = StateMachine()
        assert sm.transition("HALT") is True
        assert sm.transition("OBSERVE") is False

    def test_full_path_to_halt(self):
        sm = StateMachine()
        path = ["OBSERVE", "ANALYZE", "EVALUATE", "DECIDE", "ACT", "VERIFY", "STABILIZE", "REPORT", "HALT"]
        for state in path:
            assert sm.transition(state), f"Failed to transition to {state}"
        assert sm.current == "HALT"

    def test_bfs_all_states_reachable(self):
        sm = StateMachine()
        count, states = sm.bfs_all_states_reachable()
        assert count == 10
        assert set(states) == set(STATE_NAMES)

    def test_halt_absorbing(self):
        sm = StateMachine()
        assert sm.verify_halt_absorbing() is True
        assert len(sm.transition_map["HALT"]) == 0

    def test_gray_code_count(self):
        assert len(STATE_NAMES) == 10
        assert len(GRAY_CODES) == 10

    def test_gray_codes_unique(self):
        assert len(set(GRAY_CODES)) == 10

    def test_gray_code_single_bit_transitions(self):
        sm = StateMachine()
        violations = sm.verify_single_bit_transitions()
        assert len(violations) == 0, f"Found {len(violations)} single-bit violations"

    def test_entropy_monotonicity(self):
        sm = StateMachine()
        violations = sm.verify_entropy_monotonicity()
        assert len(violations) == 0, f"Found {len(violations)} entropy violations"

    def test_gray_entropy_hump(self):
        from mas_eval.domains.d4_governance_security import STATE_ENTROPY, PRIMARY_PATH
        entropies = [STATE_ENTROPY[s] for s in PRIMARY_PATH]
        assert entropies[0] == 0
        mid = len(entropies) // 2
        assert max(entropies) == 4
        assert entropies[-1] == 0

    def test_snapshot_restore(self):
        sm = StateMachine()
        sm.transition("OBSERVE")
        sm.transition("ANALYZE")
        snap = sm.snapshot()
        sm2 = StateMachine()
        sm2.restore(snap)
        assert sm2.current == "ANALYZE"
        assert sm2.history == ["INIT", "OBSERVE"]

    def test_can_reach_halt(self):
        sm = StateMachine()
        assert sm.can_reach_halt() is True

    def test_force_stabilize(self):
        sm = StateMachine()
        sm.transition("OBSERVE")
        sm.transition("ANALYZE")
        sm.transition("EVALUATE")
        sm.transition("DECIDE")
        sm.transition("ACT")
        sm.transition("VERIFY")
        assert sm.force_stabilize() is True
        assert sm.current == "STABILIZE"

    def test_force_stop(self):
        sm = StateMachine()
        sm.transition("OBSERVE")
        assert sm.force_stop() is True
        assert sm.current == "HALT"

    def test_history_tracking(self):
        sm = StateMachine()
        sm.transition("OBSERVE")
        sm.transition("ANALYZE")
        assert sm.history == ["INIT", "OBSERVE"]

    def test_transition_map_completeness(self):
        sm = StateMachine()
        for state in STATE_NAMES:
            assert state in sm.transition_map, f"Missing {state} in transition map"

    def test_illegal_halt_escape(self):
        sm = StateMachine()
        sm.current = "HALT"
        for target in STATE_NAMES:
            assert sm.transition(target) is False, f"Should not be able to leave HALT to {target}"


class TestCircuitBreaker:
    def test_initial_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_three_failures_opens(self):
        cb = CircuitBreaker()
        for _ in range(2):
            cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_cooldown_transitions_to_half_open(self):
        cb = CircuitBreaker()
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        cb.last_failure_time = 0
        assert cb.check_cooldown() is True
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_half_open_two_successes_closes(self):
        cb = CircuitBreaker(cooldown_seconds=0)
        for _ in range(3):
            cb.record_failure()
        cb.check_cooldown()
        assert cb.state == CircuitBreakerState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitBreakerState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_reset(self):
        cb = CircuitBreaker()
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.consecutive_failures == 0

    def test_depth_limit_triggers_open(self):
        cb = CircuitBreaker()
        for _ in range(4):
            tripped = cb.increment_depth()
        assert tripped is True
        assert cb.state == CircuitBreakerState.OPEN

    def test_depth_below_limit(self):
        cb = CircuitBreaker()
        for _ in range(3):
            tripped = cb.increment_depth()
        assert tripped is False
        assert cb.state == CircuitBreakerState.CLOSED

    def test_depth_reset(self):
        cb = CircuitBreaker()
        cb.increment_depth()
        cb.increment_depth()
        cb.reset_depth()
        assert cb.recursion_depth == 0

    def test_transition_history(self):
        cb = CircuitBreaker()
        for _ in range(3):
            cb.record_failure()
        assert len(cb.transition_history) >= 1
        assert cb.transition_history[-1][1] == CircuitBreakerState.OPEN

    def test_success_in_closed_resets_failures(self):
        cb = CircuitBreaker()
        cb.record_failure()
        cb.record_failure()
        assert cb.consecutive_failures == 2
        cb.record_success()
        assert cb.consecutive_failures == 0

    def test_cooldown_not_elapsed(self):
        cb = CircuitBreaker(cooldown_seconds=3600)
        for _ in range(3):
            cb.record_failure()
        assert cb.check_cooldown() is False
        assert cb.state == CircuitBreakerState.OPEN


class TestOscillationDetector:
    def test_detect_cycle_ab(self):
        od = OscillationDetector(window_size=3, min_history=4)
        for s in ["A", "B", "A", "B", "A", "B"]:
            od.record_state(s)
        result = od.detect_oscillation()
        assert result is not None

    def test_no_false_positive(self):
        od = OscillationDetector(window_size=3)
        for s in ["A", "B", "C", "D", "E"]:
            od.record_state(s)
        result = od.detect_oscillation()
        assert result is None

    def test_stabilize_clears_window(self):
        od = OscillationDetector()
        for s in ["A", "B", "A"]:
            od.record_state(s)
        od.stabilize()
        assert len(od.window) == 0

    def test_false_positive_rate(self):
        od = OscillationDetector()
        assert od.false_positive_rate == 0.0
        od.total_detections = 10
        od.false_positive_count = 1
        assert od.false_positive_rate == 0.1

    def test_insufficient_data_returns_none(self):
        od = OscillationDetector(window_size=3)
        od.record_state("A")
        od.record_state("B")
        assert od.detect_oscillation() is None

    def test_recovery_rate(self):
        od = OscillationDetector()
        od.stabilization_count = 10
        od.false_positive_count = 1
        assert od.recovery_rate == 0.9

    def test_cycle_len_3(self):
        od = OscillationDetector(window_size=4)
        for s in ["A", "B", "C", "A", "B", "C"]:
            od.record_state(s)
        result = od.detect_oscillation()
        assert result is not None


class TestAuditTrail:
    def test_record_increments_entries(self):
        at = AuditTrail()
        at.record({"event": "test"})
        assert len(at.entries) == 1

    def test_chain_valid(self):
        at = AuditTrail()
        for i in range(10):
            at.record({"event": f"test_{i}"})
        errors = at.verify_chain()
        assert len(errors) == 0

    def test_tamper_detection(self):
        at = AuditTrail()
        at.record({"event": "valid"})
        at.entries[0]["entry"]["tampered"] = True
        errors = at.verify_chain()
        assert len(errors) > 0

    def test_chain_structure(self):
        at = AuditTrail()
        rec = at.record({"event": "first"})
        assert "_hash" in rec
        assert "_prev_hash" in rec
        assert "_timestamp" in rec
        assert "_sequence" in rec

    def test_prev_hash_chaining(self):
        at = AuditTrail()
        r1 = at.record({"event": "first"})
        r2 = at.record({"event": "second"})
        assert r2["_prev_hash"] == r1["_hash"]

    def test_jsonl_export(self):
        at = AuditTrail()
        for i in range(3):
            at.record({"event": f"e{i}"})
        jsonl = at.export_jsonl()
        lines = jsonl.strip().split("\n")
        assert len(lines) == 3

    def test_clear(self):
        at = AuditTrail()
        at.record({"event": "test"})
        at.clear()
        assert len(at.entries) == 0
        assert at.last_hash == b"0" * 32

    def test_chain_broken_after_modification(self):
        at = AuditTrail()
        at.record({"event": "a"})
        at.record({"event": "b"})
        at.entries[0]["entry"]["x"] = "y"
        errors = at.verify_chain()
        assert len(errors) > 0


class TestD4Governance:
    def test_governance_scoring(self):
        result = run_d4_governance()
        assert result["domain"] == "D4"
        assert result["component"] == "governance"
        assert 0 <= result["score"] <= 100
        assert set(result["subscores"].keys()) == {"state_machine", "circuit_breaker", "oscillation", "audit_trail"}

    def test_governance_subscore_ranges(self):
        result = run_d4_governance()
        for subname, subscore in result["subscores"].items():
            assert 0 <= subscore <= 100, f"{subname} score {subscore} out of range"

    def test_governance_findings_present(self):
        result = run_d4_governance()
        assert result["summary"]["total_findings"] > 0

    def test_governance_perfect_state_machine(self):
        result = run_d4_governance()
        assert result["subscores"]["state_machine"] >= 80

    def test_governance_weights_sum_to_one(self):
        total = sum(GOVERNANCE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_governance_all_state_names_defined(self):
        assert len(STATE_NAMES) == 10
        expected = ["INIT", "OBSERVE", "ANALYZE", "EVALUATE", "DECIDE",
                     "ACT", "VERIFY", "STABILIZE", "REPORT", "HALT"]
        assert STATE_NAMES == expected

    def test_governance_audit_chain_valid(self):
        result = run_d4_governance()
        assert result["summary"]["audit_chain_valid"] is True
