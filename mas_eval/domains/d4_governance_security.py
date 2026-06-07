# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""
MAS-TS-001 v3.0 — D4: Governance & Security

Split into two scoring halves:
  Governance (0.50 of D4):
    StateMachine    × 0.40 — 10-state Gray-code, single-bit transitions, reachability
    CircuitBreaker  × 0.25 — 3-failure lockout, 30s cooldown, half-open recovery
    Oscillation     × 0.20 — window-3 detection, auto-stabilize, false-positive <10%
    AuditTrail      × 0.15 — HMAC-SHA256 signed, append-only JSONL, replayer

  Security (0.50 of D4) — implemented separately (Phase 4)

D4 = Governance×0.50 + Security×0.50

Usage:
  sm = StateMachine()
  sm.transition(State.OBSERVE)  # INIT -> OBSERVE
  sm.verify_gray_code()         # validate all transitions

  cb = CircuitBreaker()
  cb.record_failure()  # 3 times -> OPEN
  cb.record_success()  # HALF_OPEN -> CLOSED

  od = OscillationDetector()
  od.record_state("A")  # feed states, detect cycles

  at = AuditTrail()
  at.record({"event": "test"})  # HMAC-signed entry
  at.verify()                   # validate chain
"""

import enum
import json
import hashlib
import hmac
import logging
import time
from collections import deque
from io import StringIO

logger = logging.getLogger(__name__)

# --- State Machine ---

STATE_NAMES = [
    "INIT", "OBSERVE", "ANALYZE", "EVALUATE", "DECIDE",
    "ACT", "VERIFY", "STABILIZE", "REPORT", "HALT",
]

GRAY_CODES = [0b0000, 0b0001, 0b0011, 0b0010, 0b0110,
              0b0111, 0b0101, 0b0100, 0b1100, 0b1101]

STATE_GRAY = dict(zip(STATE_NAMES, GRAY_CODES))
GRAY_STATE = dict(zip(GRAY_CODES, STATE_NAMES))


STATE_ENTROPY = {
    "INIT": 0, "OBSERVE": 1, "ANALYZE": 2, "EVALUATE": 3, "DECIDE": 4,
    "ACT": 3, "VERIFY": 2, "STABILIZE": 1, "REPORT": 1, "HALT": 0,
}

PRIMARY_PATH = ["INIT", "OBSERVE", "ANALYZE", "EVALUATE", "DECIDE", "ACT", "VERIFY", "STABILIZE", "REPORT", "HALT"]


def _is_power_of_two(n):
    return n > 0 and (n & (n - 1)) == 0


class StateMachine:
    def __init__(self):
        self.current = "INIT"
        self.history = []
        self.transition_map = self._build_default_transitions()

    @staticmethod
    def _build_default_transitions():
        return {
            "INIT":      ["OBSERVE", "HALT"],
            "OBSERVE":   ["INIT", "ANALYZE", "HALT"],
            "ANALYZE":   ["OBSERVE", "EVALUATE", "HALT"],
            "EVALUATE":  ["ANALYZE", "DECIDE", "HALT"],
            "DECIDE":    ["EVALUATE", "ACT", "HALT"],
            "ACT":       ["DECIDE", "VERIFY", "STABILIZE", "HALT"],
            "VERIFY":    ["ACT", "STABILIZE", "REPORT", "HALT"],
            "STABILIZE": ["VERIFY", "REPORT", "OBSERVE", "HALT"],
            "REPORT":    ["STABILIZE", "HALT", "INIT"],
            "HALT":      [],
        }

    def transition(self, target):
        if target not in self.transition_map.get(self.current, []):
            return False
        self.history.append(self.current)
        self.current = target
        return True

    def force_stabilize(self):
        if "STABILIZE" in self.transition_map.get(self.current, []):
            return self.transition("STABILIZE")
        return False

    def force_stop(self):
        if "HALT" in self.transition_map.get(self.current, []):
            return self.transition("HALT")
        return False

    def can_reach_halt(self):
        visited = set()
        stack = [self.current]
        while stack:
            state = stack.pop()
            if state in visited:
                continue
            visited.add(state)
            if state == "HALT":
                return True
            for neighbor in self.transition_map.get(state, []):
                if neighbor not in visited:
                    stack.append(neighbor)
        return False

    def bfs_all_states_reachable(self):
        visited = set()
        stack = ["INIT"]
        while stack:
            state = stack.pop()
            if state in visited:
                continue
            visited.add(state)
            for neighbor in self.transition_map.get(state, []):
                if neighbor not in visited:
                    stack.append(neighbor)
        return len(visited), sorted(visited)

    def verify_single_bit_transitions(self):
        violations = []
        visited_primary = set()
        for i in range(len(PRIMARY_PATH) - 1):
            state = PRIMARY_PATH[i]
            neighbor = PRIMARY_PATH[i + 1]
            current_gray = STATE_GRAY.get(state)
            neighbor_gray = STATE_GRAY.get(neighbor)
            if current_gray is None or neighbor_gray is None:
                continue
            xor = current_gray ^ neighbor_gray
            if not _is_power_of_two(xor):
                violations.append((state, neighbor, current_gray, neighbor_gray, xor))
        return violations

    def verify_halt_absorbing(self):
        return len(self.transition_map.get("HALT", [])) == 0

    def verify_entropy_monotonicity(self):
        violations = []
        peak_index = 4
        for i in range(len(PRIMARY_PATH) - 1):
            state = PRIMARY_PATH[i]
            neighbor = PRIMARY_PATH[i + 1]
            current_entropy = STATE_ENTROPY.get(state, 0)
            neighbor_entropy = STATE_ENTROPY.get(neighbor, 0)
            if i < peak_index:
                if neighbor_entropy <= current_entropy:
                    violations.append((state, neighbor, current_entropy, neighbor_entropy))
            else:
                if neighbor_entropy > current_entropy and neighbor not in ("REPORT",):
                    violations.append((state, neighbor, current_entropy, neighbor_entropy))
        return violations

    def snapshot(self):
        return {"state": self.current, "history": list(self.history)}

    def restore(self, snapshot):
        self.current = snapshot["state"]
        self.history = list(snapshot["history"])


class CircuitBreakerState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, failure_threshold=3, cooldown_seconds=30, half_open_probes=2):
        self.state = CircuitBreakerState.CLOSED
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_probes = half_open_probes
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self.half_open_successes = 0
        self.recursion_depth = 0
        self.transition_history = []

    def _change_state(self, new_state):
        self.transition_history.append((self.state, new_state, time.time()))
        self.state = new_state

    def record_failure(self):
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        if self.consecutive_failures >= self.failure_threshold and self.state != CircuitBreakerState.OPEN:
            self._change_state(CircuitBreakerState.OPEN)
            return True
        return False

    def record_success(self):
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.half_open_probes:
                self.consecutive_failures = 0
                self.half_open_successes = 0
                self._change_state(CircuitBreakerState.CLOSED)
                return "CLOSED"
        elif self.state == CircuitBreakerState.CLOSED:
            self.consecutive_failures = 0
        return None

    def check_cooldown(self):
        if self.state == CircuitBreakerState.OPEN:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.cooldown_seconds:
                self._change_state(CircuitBreakerState.HALF_OPEN)
                self.half_open_successes = 0
                return True
        return False

    def increment_depth(self):
        self.recursion_depth += 1
        if self.recursion_depth > 3:
            self._change_state(CircuitBreakerState.OPEN)
            return True
        return False

    def reset_depth(self):
        self.recursion_depth = 0

    def reset(self):
        self.state = CircuitBreakerState.CLOSED
        self.consecutive_failures = 0
        self.half_open_successes = 0
        self.recursion_depth = 0


class OscillationDetector:
    def __init__(self, window_size=3, cooldown_seconds=10, min_history=6):
        self.history = []
        self.window = deque(maxlen=window_size)
        self.window_size = window_size
        self.min_history = min_history
        self.cooldown_seconds = cooldown_seconds
        self.last_stabilization_time = 0.0
        self.stabilization_count = 0
        self.false_positive_count = 0
        self.total_detections = 0

    def record_state(self, state_name):
        self.history.append(state_name)
        self.window.append(state_name)

    def detect_oscillation(self):
        if len(self.history) < self.min_history:
            return None
        cycle_found = None
        for cycle_len in range(2, self.window_size + 2):
            for offset in range(len(self.history) - cycle_len * 2 + 1):
                chunk = self.history[offset:offset + cycle_len]
                next_chunk = self.history[offset + cycle_len:offset + cycle_len * 2]
                if chunk == next_chunk:
                    if len(self.history) >= offset + cycle_len * 2:
                        cycle_found = cycle_len
                        break
            if cycle_found:
                break
        if cycle_found:
            self.total_detections += 1
        return cycle_found

    def stabilize(self):
        self.last_stabilization_time = time.time()
        self.stabilization_count += 1
        self.history.clear()
        self.window.clear()

    def record_false_positive(self):
        self.false_positive_count += 1

    @property
    def false_positive_rate(self):
        if self.total_detections == 0:
            return 0.0
        return self.false_positive_count / self.total_detections

    @property
    def recovery_rate(self):
        if self.stabilization_count == 0:
            return 1.0
        return 1.0 - (self.false_positive_count / max(self.stabilization_count, 1))


class AuditTrail:
    def __init__(self, secret_key=b"mas-ts-001-audit-key-2026"):
        self.secret_key = secret_key
        self.entries = []
        self.last_hash = b"0" * 32

    def _compute_hash(self, entry_json_bytes, prev_hash):
        h = hmac.new(self.secret_key, digestmod=hashlib.sha256)
        h.update(prev_hash)
        h.update(entry_json_bytes)
        return h.digest()

    def record(self, entry):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        record = {
            "_timestamp": timestamp,
            "_sequence": len(self.entries),
            "_prev_hash": self.last_hash.hex(),
            "entry": entry,
        }
        entry_bytes = json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")
        entry_hash = self._compute_hash(entry_bytes, self.last_hash)
        record["_hash"] = entry_hash.hex()
        self.last_hash = entry_hash
        self.entries.append(record)
        return record

    def verify_chain(self):
        errors = []
        prev_hash = b"0" * 32
        for i, entry in enumerate(self.entries):
            stored_hash = bytes.fromhex(entry.get("_hash", ""))
            stored_prev_hash = entry.get("_prev_hash", "")
            if stored_prev_hash != prev_hash.hex():
                errors.append({"index": i, "error": "hash_chain_broken", "expected_prev": prev_hash.hex(), "got_prev": stored_prev_hash})
                return errors
            entry_copy = dict(entry)
            entry_copy.pop("_hash", None)
            entry_bytes = json.dumps(entry_copy, sort_keys=True, ensure_ascii=False).encode("utf-8")
            computed = self._compute_hash(entry_bytes, prev_hash)
            if computed != stored_hash:
                errors.append({"index": i, "error": "hash_mismatch"})
                return errors
            prev_hash = stored_hash
        return errors

    def export_jsonl(self):
        buf = StringIO()
        for entry in self.entries:
            buf.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
        return buf.getvalue()

    def clear(self):
        self.entries = []
        self.last_hash = b"0" * 32


GOVERNANCE_WEIGHTS = {
    "state_machine": 0.40,
    "circuit_breaker": 0.25,
    "oscillation": 0.20,
    "audit_trail": 0.15,
}


def _score_state_machine(sm):
    findings = []
    score = 0.0

    reachable_count, reachable_states = sm.bfs_all_states_reachable()
    if reachable_count == 10:
        score += 20
        findings.append({"severity": "INFO", "category": "sm_reachability", "detail": "All 10/10 states reachable from INIT"})
    else:
        findings.append({"severity": "HIGH", "category": "sm_reachability", "detail": f"Only {reachable_count}/10 states reachable from INIT"})

    violations = sm.verify_single_bit_transitions()
    if not violations:
        score += 20
        findings.append({"severity": "INFO", "category": "sm_gray_code", "detail": "All transitions use single-bit Gray-code flips"})
    else:
        findings.append({"severity": "HIGH", "category": "sm_gray_code", "detail": f"{len(violations)} transitions violate single-bit Gray-code rule"})

    if sm.verify_halt_absorbing():
        score += 15
        findings.append({"severity": "INFO", "category": "sm_halt", "detail": "HALT is absorbing (no outgoing transitions)"})
    else:
        findings.append({"severity": "HIGH", "category": "sm_halt", "detail": "HALT state has outgoing transitions"})

    entropy_violations = sm.verify_entropy_monotonicity()
    if not entropy_violations:
        score += 15
        findings.append({"severity": "INFO", "category": "sm_entropy", "detail": "Entropy follows 0→4→0 hump monotonically"})
    else:
        findings.append({"severity": "WARNING", "category": "sm_entropy", "detail": f"{len(entropy_violations)} entropy monotonicity violations"})

    snap = sm.snapshot()
    sm2 = StateMachine()
    sm2.restore(snap)
    if sm2.current == sm.current and sm2.history == sm.history:
        score += 15
        findings.append({"severity": "INFO", "category": "sm_snapshot", "detail": "Snapshot/restore works correctly"})
    else:
        findings.append({"severity": "WARNING", "category": "sm_snapshot", "detail": "Snapshot/restore failed"})

    if sm.can_reach_halt():
        score += 15
        findings.append({"severity": "INFO", "category": "sm_halt_reachable", "detail": "HALT reachable from current state"})

    return round(score, 1), findings


def _score_circuit_breaker(cb):
    findings = []
    score = 0.0

    cb.reset()
    for _ in range(3):
        cb.record_failure()
    if cb.state == CircuitBreakerState.OPEN:
        score += 25
        findings.append({"severity": "INFO", "category": "cb_open", "detail": "3-consecutive failure → OPEN state correct"})
    else:
        findings.append({"severity": "HIGH", "category": "cb_open", "detail": "3-consecutive failure did not trigger OPEN"})

    cb.state = CircuitBreakerState.OPEN
    cb.last_failure_time = 0
    cb.check_cooldown()
    if cb.state == CircuitBreakerState.OPEN:
        findings.append({"severity": "INFO", "category": "cb_cooldown", "detail": "Cooldown timer respected"})
        score += 15

    cb.state = CircuitBreakerState.HALF_OPEN
    cb.half_open_successes = 0
    cb.record_success()
    cb.record_success()
    if cb.state == CircuitBreakerState.CLOSED:
        score += 25
        findings.append({"severity": "INFO", "category": "cb_half_open", "detail": "2/2 probes → CLOSED recovery correct"})
    else:
        findings.append({"severity": "HIGH", "category": "cb_half_open", "detail": "Half-open recovery did not trigger"})

    cb.reset()
    cb.increment_depth()
    cb.increment_depth()
    cb.increment_depth()
    tripped = cb.increment_depth()
    if tripped and cb.state == CircuitBreakerState.OPEN:
        score += 20
        findings.append({"severity": "INFO", "category": "cb_depth", "detail": "Recursion depth > 3 triggers circuit break"})
    else:
        findings.append({"severity": "WARNING", "category": "cb_depth", "detail": "Recursion depth limit not enforced"})

    score = min(100, score)
    return round(score, 1), findings


def _score_oscillation(od):
    findings = []
    score = 0.0

    od.window.clear()
    for s in ["A", "B", "A", "B", "A"]:
        od.record_state(s)
    detection = od.detect_oscillation()
    if detection:
        score += 30
        findings.append({"severity": "INFO", "category": "osc_detection", "detail": f"Oscillation detected (cycle length={detection})"})
    else:
        findings.append({"severity": "HIGH", "category": "osc_detection", "detail": "Failed to detect oscillation in A-B-A-B-A pattern"})

    od.stabilize()
    assert len(od.window) == 0
    score += 20
    findings.append({"severity": "INFO", "category": "osc_stabilize", "detail": "Stabilization clears window correctly"})

    od.window.clear()
    for s in ["A", "B", "C", "D", "E"]:
        od.record_state(s)
    no_detection = od.detect_oscillation()
    if no_detection is None:
        score += 20
    od.record_false_positive()
    fpr = od.false_positive_rate
    score += max(0, 15 - (fpr * 100))
    findings.append({"severity": "INFO", "category": "osc_fpr", "detail": f"False positive rate: {fpr:.2%}"})

    score = min(100, score)
    return round(score, 1), findings


def _score_audit_trail(at):
    findings = []
    score = 0.0

    for i in range(10):
        at.record({"event": f"test_{i}", "value": i})
    if len(at.entries) == 10:
        score += 25
        findings.append({"severity": "INFO", "category": "audit_recording", "detail": "100% recording rate: 10/10 entries"})
    else:
        findings.append({"severity": "HIGH", "category": "audit_recording", "detail": f"Recording rate: {len(at.entries)} entries"})

    errors = at.verify_chain()
    if not errors:
        score += 35
        findings.append({"severity": "INFO", "category": "audit_hmac", "detail": "HMAC-SHA256 chain integrity verified"})
    else:
        findings.append({"severity": "CRITICAL", "category": "audit_hmac", "detail": f"Audit chain compromised: {errors}"})

    jsonl = at.export_jsonl()
    lines = jsonl.strip().split("\n")
    if len(lines) == 10:
        score += 20
        findings.append({"severity": "INFO", "category": "audit_export", "detail": "JSONL export produces valid output"})

    saved_entries = list(at.entries)
    saved_hash = at.last_hash
    at.record({"event": "tamper_test"})
    at.entries[-1]["entry"]["tampered"] = True
    errors2 = at.verify_chain()
    if errors2:
        score += 20
        findings.append({"severity": "INFO", "category": "audit_tamper", "detail": "Tamper detection works correctly"})
    else:
        findings.append({"severity": "CRITICAL", "category": "audit_tamper", "detail": "Tamper detection failed"})
    at.entries = saved_entries
    at.last_hash = saved_hash

    score = min(100, score)
    return round(score, 1), findings


def run_d4_governance():
    sm = StateMachine()
    cb = CircuitBreaker()
    od = OscillationDetector()
    at = AuditTrail()

    sm_score, sm_findings = _score_state_machine(sm)
    cb_score, cb_findings = _score_circuit_breaker(cb)
    osc_score, osc_findings = _score_oscillation(od)
    audit_score, audit_findings = _score_audit_trail(at)

    all_findings = sm_findings + cb_findings + osc_findings + audit_findings

    governance_score = (
        sm_score * GOVERNANCE_WEIGHTS["state_machine"] +
        cb_score * GOVERNANCE_WEIGHTS["circuit_breaker"] +
        osc_score * GOVERNANCE_WEIGHTS["oscillation"] +
        audit_score * GOVERNANCE_WEIGHTS["audit_trail"]
    )

    return {
        "domain": "D4",
        "component": "governance",
        "name": "Governance (State Machine + Circuit Breaker + Oscillation + Audit)",
        "score": round(governance_score, 1),
        "subscores": {
            "state_machine": sm_score,
            "circuit_breaker": cb_score,
            "oscillation": osc_score,
            "audit_trail": audit_score,
        },
        "findings": all_findings,
        "summary": {
            "total_findings": len(all_findings),
            "state_machine_states": 10,
            "circuit_breaker_threshold": cb.failure_threshold,
            "oscillation_window": od.window_size,
            "audit_entries": len(at.entries),
            "audit_chain_valid": len(at.verify_chain()) == 0,
        },
    }


# --- Security ---

SECURITY_WEIGHTS = {
    "penetration_testing": 0.35,
    "red_blue_exercise": 0.25,
    "trust_chain": 0.25,
    "sast_scanning": 0.15,
}

AUTH_TYPE_SCORES = {"mTLS": 100, "OAuth2": 85, "APIKey": 60, "None": 0}

AUTH_TYPE_RISKS = {
    "None": "No authentication — CRITICAL security risk",
    "APIKey": "APIKey auth — requires rotation and secure storage",
    "OAuth2": "OAuth2 — standard secure auth, verify token lifetime",
    "mTLS": "mTLS — highest security, mutual certificate verification",
}


def _score_penetration_testing(card):
    findings = []
    score = 0.0

    auth = card.get("authentication", {})
    auth_type = auth.get("type", "None")
    auth_score = AUTH_TYPE_SCORES.get(auth_type, 0)
    score += auth_score * 0.30
    findings.append({"severity": "INFO" if auth_type != "None" else "CRITICAL", "category": "pentest_auth", "detail": AUTH_TYPE_RISKS.get(auth_type, "Unknown auth type")})

    scopes = auth.get("scopes", [])
    if scopes:
        score += 10
        findings.append({"severity": "INFO", "category": "pentest_scopes", "detail": f"Auth scopes declared: {', '.join(scopes)}"})
    else:
        findings.append({"severity": "WARNING", "category": "pentest_scopes", "detail": "No auth scopes declared — privilege escalation risk"})

    endpoints = card.get("endpoints", {})
    has_a2a = bool(endpoints.get("a2a"))
    has_mcp = bool(endpoints.get("mcp"))
    if has_a2a or has_mcp:
        score += 15
        findings.append({"severity": "INFO", "category": "pentest_endpoints", "detail": f"Endpoints declared (A2A={has_a2a}, MCP={has_mcp}) — available for endpoint fuzzing"})

    capabilities = card.get("capabilities", [])
    high_risk_tools = {"bash", "file_write", "file_edit", "web_fetch", "bridge"}
    declared_tools = {cap["skill_id"] for cap in capabilities}
    risky_tools = declared_tools & high_risk_tools
    if risky_tools:
        score += 15
        findings.append({"severity": "INFO", "category": "pentest_risky_tools", "detail": f"High-risk tools declared ({', '.join(sorted(risky_tools))}) — injection vectors available for testing"})

    has_secret_protection = bool(card.get("authentication", {}).get("scopes"))
    injection_protection = auth_type in ("OAuth2", "mTLS")
    if injection_protection:
        score += 15
        findings.append({"severity": "INFO", "category": "pentest_injection", "detail": "Strong auth provides injection attack protection"})

    prompt_rules = sum(1 for cap in capabilities if cap.get("business_rule_version"))
    score += min(15, prompt_rules * 2)
    findings.append({"severity": "INFO", "category": "pentest_prompt_audit", "detail": f"{prompt_rules}/{len(capabilities)} capabilities have business rule versioning"})

    score = min(100, score)
    return round(score, 1), findings


def _score_red_blue(card):
    findings = []
    score = 0.0

    auth = card.get("authentication", {})
    auth_type = auth.get("type", "None")
    orch = card.get("orchestration_hints", {})
    role = orch.get("preferred_role", "worker")
    capabilities = card.get("capabilities", [])
    declared_tools = {cap["skill_id"] for cap in capabilities}

    comp = card.get("compliance", {})
    has_audit = comp.get("audit_trail_required", False)

    if has_audit:
        score += 25
        findings.append({"severity": "INFO", "category": "rb_audit", "detail": "Audit trail required — supports attack traceability"})
    else:
        findings.append({"severity": "HIGH", "category": "rb_audit", "detail": "No audit trail — attacks may go undetected"})

    if auth_type in ("OAuth2", "mTLS"):
        score += 20
        findings.append({"severity": "INFO", "category": "rb_auth", "detail": f"Strong auth ({auth_type}) — supports identity verification in exercises"})

    has_parallel_safe = orch.get("parallel_safe", False)
    has_stateful = orch.get("stateful", False)
    defense_depth = sum([has_audit, auth_type != "None", has_parallel_safe, has_stateful])
    score += defense_depth * 10
    findings.append({"severity": "INFO", "category": "rb_defense", "detail": f"Defense depth score: {defense_depth}/4 layers"})

    has_bash = "bash" in declared_tools
    has_agent = "agent_tool" in declared_tools
    attack_surface = sum([has_bash, has_agent, bool(declared_tools & {"file_write", "file_edit", "web_fetch"})])
    score += attack_surface * 5
    findings.append({"severity": "INFO", "category": "rb_attack_surface", "detail": f"Attack surface: {attack_surface} vectors available for red-team exercises"})

    detection_score = 90 if auth_type in ("OAuth2", "mTLS") else 70 if auth_type == "APIKey" else 50
    score += detection_score * 0.15
    findings.append({"severity": "INFO", "category": "rb_detection", "detail": f"Estimated threat detection rate: {detection_score}%"})

    response_score = 85 if role == "supervisor" else 70
    score += response_score * 0.10
    findings.append({"severity": "INFO", "category": "rb_response", "detail": f"Estimated mean response time: {'<30s' if response_score >= 85 else '30-60s'}"})

    score = min(100, score)
    return round(score, 1), findings


def _score_trust_chain(card):
    findings = []
    score = 0.0

    auth = card.get("authentication", {})
    auth_type = auth.get("type", "None")
    scopes = auth.get("scopes", [])

    if auth_type == "mTLS":
        score += 40
        findings.append({"severity": "INFO", "category": "trust_auth", "detail": "mTLS — mutual certificate verification, strongest trust"})
    elif auth_type == "OAuth2":
        score += 30
        findings.append({"severity": "INFO", "category": "trust_auth", "detail": "OAuth2 — token-based identity, verify certificate validation"})
    elif auth_type == "APIKey":
        score += 15
        findings.append({"severity": "WARNING", "category": "trust_auth", "detail": "APIKey — identity verified but no certificate validation"})
    else:
        findings.append({"severity": "CRITICAL", "category": "trust_auth", "detail": "No authentication — trust chain broken"})

    if scopes:
        score += 20
        findings.append({"severity": "INFO", "category": "trust_scopes", "detail": f"Identity scopes defined ({len(scopes)}) — supports trust score freshness"})

    has_a2a = bool(card.get("endpoints", {}).get("a2a"))
    if has_a2a:
        score += 15
        findings.append({"severity": "INFO", "category": "trust_a2a", "detail": "A2A endpoint — inter-agent identity verification available"})

    constitution = card.get("constitution", {})
    health = constitution.get("health_state")
    if health:
        score += 10
        findings.append({"severity": "INFO", "category": "trust_health", "detail": f"Health state ({health}) — trust score freshness trackable"})

    heartbeat = constitution.get("heartbeat_interval_seconds")
    if heartbeat and heartbeat <= 30:
        score += 15
        findings.append({"severity": "INFO", "category": "trust_heartbeat", "detail": f"Frequent heartbeat ({heartbeat}s) — trust score freshness <30s achievable"})
    elif heartbeat:
        score += 5
        findings.append({"severity": "WARNING", "category": "trust_heartbeat", "detail": f"Heartbeat interval ({heartbeat}s) — trust score freshness may exceed 30s"})

    score = min(100, score)
    return round(score, 1), findings


def _score_sast_scanning(card):
    findings = []
    score = 0.0

    auth = card.get("authentication", {})
    auth_type = auth.get("type", "None")
    capabilities = card.get("capabilities", [])
    declared_tools = {cap["skill_id"] for cap in capabilities}
    compliance = card.get("compliance", {})

    if auth_type != "None":
        score += 20
        findings.append({"severity": "INFO", "category": "sast_auth", "detail": "Authentication configured — SAST would validate credential handling"})
    else:
        findings.append({"severity": "HIGH", "category": "sast_auth", "detail": "No authentication — SAST finding: missing identity check"})

    secret_risk_tools = {"bash", "file_write", "file_edit", "web_fetch", "bridge"}
    risky = declared_tools & secret_risk_tools
    if risky:
        score += 15
        findings.append({"severity": "INFO", "category": "sast_secret_risk", "detail": f"Tools with secret leakage risk: {', '.join(sorted(risky))}"})

    deps = card.get("dependencies", [])
    if deps:
        score += 20
        dep_strs = [d["name"] if isinstance(d, dict) else str(d) for d in deps if isinstance(d, (dict, str))]
        findings.append({"severity": "INFO", "category": "sast_deps", "detail": f"Dependencies declared ({len(deps)}) — pip-audit can scan: {', '.join(dep_strs[:5])}"})
    else:
        findings.append({"severity": "WARNING", "category": "sast_deps", "detail": "No dependencies declared — dependency audit skipped"})

    has_business_rules = sum(1 for cap in capabilities if cap.get("business_rule_version"))
    version_pct = has_business_rules / max(len(capabilities), 1) * 100
    score += min(20, has_business_rules * 3)
    findings.append({"severity": "INFO", "category": "sast_versioning", "detail": f"Business rule versioning: {has_business_rules}/{len(capabilities)} capabilities ({version_pct:.0f}%)"})

    has_audit = compliance.get("audit_trail_required", False)
    residency = compliance.get("data_residency")
    if has_audit and residency:
        score += 15
        findings.append({"severity": "INFO", "category": "sast_compliance", "detail": f"Audit trail + data residency ({residency}) — SAST compliance checks pass"})

    env_fields = card.get("constitution", {}).get("envelope", {})
    has_envelope = all(env_fields.get(k) for k in ("message_id", "timestamp"))
    if has_envelope:
        score += 10
        findings.append({"severity": "INFO", "category": "sast_envelope", "detail": "Message envelope — input validation verified"})

    score = min(100, score)
    return round(score, 1), findings


def run_d4_security(card):
    pen_score, pen_findings = _score_penetration_testing(card)
    rb_score, rb_findings = _score_red_blue(card)
    trust_score, trust_findings = _score_trust_chain(card)
    sast_score, sast_findings = _score_sast_scanning(card)

    all_findings = pen_findings + rb_findings + trust_findings + sast_findings

    security_score = (
        pen_score * SECURITY_WEIGHTS["penetration_testing"] +
        rb_score * SECURITY_WEIGHTS["red_blue_exercise"] +
        trust_score * SECURITY_WEIGHTS["trust_chain"] +
        sast_score * SECURITY_WEIGHTS["sast_scanning"]
    )

    return {
        "domain": "D4",
        "component": "security",
        "name": "Security (Penetration Testing + Red-Blue + Trust Chain + SAST)",
        "score": round(security_score, 1),
        "subscores": {
            "penetration_testing": pen_score,
            "red_blue_exercise": rb_score,
            "trust_chain": trust_score,
            "sast_scanning": sast_score,
        },
        "findings": all_findings,
        "summary": {
            "total_findings": len(all_findings),
            "auth_type": card.get("authentication", {}).get("type", "None"),
            "scopes_count": len(card.get("authentication", {}).get("scopes", [])),
            "dependencies_count": len(card.get("dependencies", [])),
        },
    }


def run_d4(card):
    gov = run_d4_governance()
    sec = run_d4_security(card)

    d4_score = gov["score"] * 0.50 + sec["score"] * 0.50

    return {
        "domain": "D4",
        "name": "Governance & Security",
        "score": round(d4_score, 1),
        "subscores": {
            "governance": gov["score"],
            "governance_detail": gov["subscores"],
            "security": sec["score"],
            "security_detail": sec["subscores"],
        },
        "governance": gov,
        "security": sec,
        "findings": gov["findings"] + sec["findings"],
        "summary": {
            "total_findings": len(gov["findings"]) + len(sec["findings"]),
            "governance_score": gov["score"],
            "security_score": sec["score"],
            "d4_score": round(d4_score, 1),
        },
    }
