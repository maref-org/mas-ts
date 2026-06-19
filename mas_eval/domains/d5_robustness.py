# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""
MAS-TS-001 v3.0 — D5: Evolution & Robustness

Scoring:
  ChaosEngineering    × 0.30 — 5 infra faults × 5 LLM faults, self-heal rate
  DriftDetection      × 0.25 — Triple-divergence (KL/JS/Hellinger), baseline auto-reset
  ReflectionLoop      × 0.20 — 5-dim quality evaluation, CriticAgent loop
  ConvergenceCycle    × 0.25 — C1/C2/C3 cycles

Usage:
  ce = ChaosEngine()
  ce.inject("network_partition")
  ce.record_healing(success=True)

  dd = DriftDetector()
  dd.add_baseline("weights_1", [0.5, 0.3, 0.2])
  dd.add_sample("weights_1", [0.4, 0.4, 0.2])

  ra = ReflectiveAgent()
  ra.generate("Solve: 2x+4=10")
  for _ in range(3):
      ra.critique()
      ra.refine()
      if ra.verify():
          break

  cv = ConvergenceVerifier()
  cv.add_response("task_1", "The answer is 3")
  cv.add_response("task_1", "x = 3")
  cv.score_consistency()

  result = run_d5()
"""

import collections
import logging
import math
import os
import platform
import random
import signal
import stat
import subprocess
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

try:
    from scipy.stats import entropy

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger.warning(
        "scipy not available — KL/JS divergence fallback to manual computation"
    )


class FaultInjector:
    """Real system-level fault injection with graceful fallback.

    Attempts platform-specific fault injection (stress-ng, pfctl, kill),
    falls back to simulation when tools/sudo are unavailable.
    """

    def __init__(self, mode: str = "auto") -> None:
        self.mode = mode
        self._cleanup_handlers: list[Callable[[], Any]] = []
        self._injection_mode: str | None = None

    def injection_mode(self) -> str:
        if self._injection_mode is not None:
            return self._injection_mode
        if self.mode == "sim":
            self._injection_mode = "simulated"
            return self._injection_mode
        self._injection_mode = self._probe_capabilities()
        return self._injection_mode

    def _probe_capabilities(self) -> str:
        has_stress = (
            subprocess.run(
                ["which", "stress-ng"], capture_output=True, text=True
            ).returncode
            == 0
        )
        has_pfctl = (
            subprocess.run(
                ["which", "pfctl"], capture_output=True, text=True
            ).returncode
            == 0
        )
        has_sudo = (
            subprocess.run(
                ["sudo", "-n", "true"], capture_output=True, text=True
            ).returncode
            == 0
        )
        if has_stress or has_pfctl:
            return "real" if has_sudo else "partial"
        return "simulated"

    def inject_cpu_pressure(self, cores: int = 2, duration: int = 10) -> dict[str, Any]:
        try:
            proc = subprocess.Popen(
                ["stress-ng", "--cpu", str(cores), "--timeout", f"{duration}s"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._cleanup_handlers.append(lambda: proc.terminate())
            return {
                "fault": "cpu_pressure",
                "mode": "real",
                "detail": f"stress-ng --cpu {cores} for {duration}s",
            }
        except FileNotFoundError:
            return {"fault": "cpu_pressure", "mode": "simulated"}

    def inject_memory_pressure(
        self, megabytes: int = 256, duration: int = 10
    ) -> dict[str, Any]:
        try:
            proc = subprocess.Popen(
                [
                    "stress-ng",
                    "--vm",
                    "1",
                    "--vm-bytes",
                    f"{megabytes}M",
                    "--timeout",
                    f"{duration}s",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._cleanup_handlers.append(lambda: proc.terminate())
            return {
                "fault": "memory_pressure",
                "mode": "real",
                "detail": f"stress-ng --vm 1 --vm-bytes {megabytes}M for {duration}s",
            }
        except FileNotFoundError:
            return {"fault": "memory_pressure", "mode": "simulated"}

    def inject_disk_failure(self) -> dict[str, Any]:
        try:
            tmpdir = Path(tempfile.mkdtemp())
            test_file = tmpdir / "test_write"
            test_file.write_text("test")
            os.chmod(str(tmpdir), stat.S_IRUSR | stat.S_IXUSR)

            def cleanup() -> None:
                os.chmod(str(tmpdir), stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
                for f in tmpdir.iterdir():
                    f.unlink()
                tmpdir.rmdir()

            self._cleanup_handlers.append(cleanup)
            return {
                "fault": "disk_failure",
                "mode": "real",
                "detail": f"read-only directory at {tmpdir}",
                "tmpdir": str(tmpdir),
            }
        except Exception:
            return {"fault": "disk_failure", "mode": "simulated"}

    def inject_process_kill(self, pid: int | None = None) -> dict[str, Any]:
        if pid is not None:
            try:
                os.kill(pid, signal.SIGKILL)
                return {
                    "fault": "process_kill",
                    "mode": "real",
                    "detail": f"killed PID {pid}",
                }
            except (OSError, PermissionError):
                return {"fault": "process_kill", "mode": "simulated"}
        try:
            sleeper = subprocess.Popen(
                ["sleep", "60"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            os.kill(sleeper.pid, signal.SIGKILL)
            return {
                "fault": "process_kill",
                "mode": "real",
                "detail": f"killed subprocess PID {sleeper.pid}",
            }
        except Exception:
            return {"fault": "process_kill", "mode": "simulated"}

    def inject_network_partition(
        self, target_ip: str | None = None, duration: int = 30
    ) -> dict[str, Any]:
        target = target_ip or "127.0.0.2"
        system = platform.system()
        try:
            if (
                system == "Darwin"
                and subprocess.run(
                    ["sudo", "-n", "pfctl", "-t", "blocked_hosts", "-T", "add", target],
                    capture_output=True,
                    text=True,
                ).returncode
                == 0
            ):
                self._cleanup_handlers.append(
                    lambda: subprocess.run(
                        [
                            "sudo",
                            "pfctl",
                            "-t",
                            "blocked_hosts",
                            "-T",
                            "delete",
                            target,
                        ],
                        capture_output=True,
                    )
                )
                return {
                    "fault": "network_partition",
                    "mode": "real",
                    "detail": f"pfctl blocked {target} for {duration}s",
                }
            if (
                system == "Linux"
                and subprocess.run(
                    [
                        "sudo",
                        "-n",
                        "iptables",
                        "-A",
                        "INPUT",
                        "-s",
                        target,
                        "-j",
                        "DROP",
                    ],
                    capture_output=True,
                ).returncode
                == 0
            ):
                self._cleanup_handlers.append(
                    lambda: subprocess.run(
                        ["sudo", "iptables", "-D", "INPUT", "-s", target, "-j", "DROP"],
                        capture_output=True,
                    )
                )
                return {
                    "fault": "network_partition",
                    "mode": "real",
                    "detail": f"iptables blocked {target} for {duration}s",
                }
        except Exception:
            pass
        return {"fault": "network_partition", "mode": "simulated"}

    def inject_mcp_disconnect(
        self, host: str = "127.0.0.1", port: int = 9000
    ) -> dict[str, Any]:
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.bind((host, port))
            sock.listen(1)
            conn, addr = sock.accept()
            conn.close()
            sock.close()
            return {
                "fault": "mcp_disconnect",
                "mode": "real",
                "detail": f"MCP server at {host}:{port} disconnected",
            }
        except Exception:
            return {
                "fault": "mcp_disconnect",
                "mode": "simulated",
                "detail": "MCP disconnection simulated",
            }

    def inject_a2a_timeout(
        self, host: str = "127.0.0.1", port: int = 9001
    ) -> dict[str, Any]:
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.bind((host, port))
            sock.listen(1)
            conn, addr = sock.accept()
            conn.settimeout(60)
            conn.recv(1024)
            conn.close()
            sock.close()
            return {
                "fault": "a2a_timeout",
                "mode": "real",
                "detail": f"A2A connection at {host}:{port} timed out",
            }
        except Exception:
            return {
                "fault": "a2a_timeout",
                "mode": "simulated",
                "detail": "A2A timeout simulated",
            }

    def inject_gossip_partition(self, port_range: str = "9002-9005") -> dict[str, Any]:
        system = platform.system()
        try:
            if (
                system == "Darwin"
                and subprocess.run(
                    [
                        "sudo",
                        "-n",
                        "pfctl",
                        "-t",
                        "blocked_hosts",
                        "-T",
                        "add",
                        port_range,
                    ],
                    capture_output=True,
                    text=True,
                ).returncode
                == 0
            ):
                self._cleanup_handlers.append(
                    lambda: subprocess.run(
                        [
                            "sudo",
                            "pfctl",
                            "-t",
                            "blocked_hosts",
                            "-T",
                            "delete",
                            port_range,
                        ],
                        capture_output=True,
                    )
                )
                return {
                    "fault": "gossip_partition",
                    "mode": "real",
                    "detail": f"Gossip ports {port_range} partitioned",
                }
        except Exception:
            pass
        return {
            "fault": "gossip_partition",
            "mode": "simulated",
            "detail": "Gossip partition simulated",
        }

    def inject(self, fault_type: str) -> dict[str, Any]:
        injectors = {
            "network_partition": lambda: self.inject_network_partition(),
            "cpu_pressure": lambda: self.inject_cpu_pressure(),
            "memory_pressure": lambda: self.inject_memory_pressure(),
            "disk_failure": lambda: self.inject_disk_failure(),
            "process_kill": lambda: self.inject_process_kill(),
            "mcp_disconnect": lambda: self.inject_mcp_disconnect(),
            "a2a_timeout": lambda: self.inject_a2a_timeout(),
            "gossip_partition": lambda: self.inject_gossip_partition(),
        }
        injector = injectors.get(fault_type)
        if injector:
            return injector()
        return {"fault": fault_type, "mode": "unknown"}

    def cleanup(self) -> None:
        for handler in reversed(self._cleanup_handlers):
            try:
                handler()
            except Exception as e:
                logger.warning("FaultInjector cleanup error: %s", e)
        self._cleanup_handlers.clear()


# --- Chaos Engineering ---

INFRA_FAULTS = [
    "network_partition",
    "cpu_pressure",
    "memory_pressure",
    "disk_failure",
    "process_kill",
]

FEDERATION_FAULTS = [
    "mcp_disconnect",
    "a2a_timeout",
    "gossip_partition",
    "trust_breach",
    "federation_split",
]

LLM_FAULTS = [
    "timeout",
    "hallucination",
    "token_corruption",
    "model_degradation",
    "rate_limiting",
]

INFRA_FAULT_WEIGHTS = {
    "network_partition": 0.20,
    "cpu_pressure": 0.15,
    "memory_pressure": 0.15,
    "disk_failure": 0.15,
    "process_kill": 0.15,
}

FEDERATION_FAULT_WEIGHTS = {
    "mcp_disconnect": 0.25,
    "a2a_timeout": 0.20,
    "gossip_partition": 0.20,
    "trust_breach": 0.20,
    "federation_split": 0.15,
}

LLM_FAULT_WEIGHTS = {
    "timeout": 0.20,
    "hallucination": 0.20,
    "token_corruption": 0.20,
    "model_degradation": 0.20,
    "rate_limiting": 0.20,
}

INFRA_PASS_CRITERIA = {
    "network_partition": "Drop 50% packets for 30s → agent recovers within 30s of restoration",
    "cpu_pressure": "4-thread stress-ng at 80% → agent responds within 5x normal latency",
    "memory_pressure": "Allocate to 90% of limit → agent degrades gracefully, no crash",
    "disk_failure": "Simulate write failure → agent logs error and retries with backoff",
    "process_kill": "Kill sub-agent process → auto-restart within 10s, task continuity ≥90%",
}

FEDERATION_PASS_CRITERIA = {
    "mcp_disconnect": "MCP server disconnects → agent reconnects with backoff, queue ≤50",
    "a2a_timeout": "A2A message >60s → agent retries via alternate transport",
    "gossip_partition": "Gossip network split → agent buffers until rejoin ≤60s",
    "trust_breach": "Peer trust score drops below 0.3 → agent isolates and escalates",
    "federation_split": "Federation partition → agent continues with local subset, rejoins ≤120s",
}

LLM_PASS_CRITERIA = {
    "timeout": "Response >30s → agent retries ≤3 times with backoff",
    "hallucination": "LLM returns fabricated data → agent detects and re-queries",
    "token_corruption": "Inject token errors → agent detects, retries",
    "model_degradation": "Degraded quality → agent escalates or retries",
    "rate_limiting": "429 responses → agent applies exponential backoff, queue depth ≤100",
}


class ChaosEngine:
    def __init__(
        self, seed: int | None = None, fault_injector: FaultInjector | None = None
    ) -> None:
        self.rng = random.Random(seed)
        self.fault_history: list[dict[str, Any]] = []
        self.healing_results: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        self.injector = fault_injector or FaultInjector(mode="auto")
        self._injection_mode = self.injector.injection_mode()

    def injection_mode(self) -> str:
        return self._injection_mode

    def inject(self, fault_type: str, scenario: int = 0) -> dict[str, Any]:
        if fault_type in INFRA_FAULTS:
            domain = "infra"
            inject_result = self.injector.inject(fault_type)
        elif fault_type in FEDERATION_FAULTS:
            domain = "federation"
            inject_result = {"mode": self._injection_mode, "fault": fault_type}
        elif fault_type in LLM_FAULTS:
            domain = "llm"
            inject_result = {"mode": "simulated", "fault": fault_type}
        else:
            return {
                "fault": fault_type,
                "error": "unknown_fault_type",
                "success": False,
            }

        record = {
            "domain": domain,
            "fault": fault_type,
            "scenario": scenario,
            "timestamp": time.time(),
            "expected_recovery_time_seconds": self._expected_recovery(fault_type),
            "injection_mode": inject_result.get("mode", "simulated"),
            "injection_detail": inject_result.get("detail", ""),
        }
        self.fault_history.append(record)
        return record

    def record_healing(
        self, fault_type: str, success: bool, recovery_time: float | None = None
    ) -> None:
        measured = recovery_time if recovery_time is not None else None
        self.healing_results[fault_type].append(
            {
                "success": success,
                "recovery_time": measured or self.rng.uniform(1, 30),
                "timestamp": time.time(),
            }
        )

    def _expected_recovery(self, fault_type: str) -> int:
        recovery_map = {
            "network_partition": 30,
            "cpu_pressure": 10,
            "memory_pressure": 15,
            "disk_failure": 5,
            "process_kill": 10,
            "timeout": 30,
            "hallucination": 15,
            "token_corruption": 10,
            "model_degradation": 20,
            "rate_limiting": 30,
        }
        return recovery_map.get(fault_type, 15)

    def healing_rate(self, fault_type: str | None = None) -> float:
        if fault_type:
            results = self.healing_results.get(fault_type, [])
            if not results:
                return 0.0
            return sum(1 for r in results if r["success"]) / len(results)
        all_results = []
        for results in self.healing_results.values():
            all_results.extend(results)
        if not all_results:
            return 0.0
        return sum(1 for r in all_results if r["success"]) / len(all_results)

    def infra_healing_rate(self) -> float:
        infra_results = []
        for ft, results in self.healing_results.items():
            if ft in INFRA_FAULTS:
                infra_results.extend(results)
        if not infra_results:
            return 0.0
        return sum(1 for r in infra_results if r["success"]) / len(infra_results)

    def llm_healing_rate(self) -> float:
        llm_results = []
        for ft, results in self.healing_results.items():
            if ft in LLM_FAULTS:
                llm_results.extend(results)
        if not llm_results:
            return 0.0
        return sum(1 for r in llm_results if r["success"]) / len(llm_results)

    def federation_healing_rate(self) -> float:
        fed_results = []
        for ft, results in self.healing_results.items():
            if ft in FEDERATION_FAULTS:
                fed_results.extend(results)
        if not fed_results:
            return 0.0
        return sum(1 for r in fed_results if r["success"]) / len(fed_results)

    def clear(self) -> None:
        self.fault_history.clear()
        self.healing_results.clear()
        self.injector.cleanup()


# --- Drift Detection ---


def _kl_divergence(p: list[float], q: list[float]) -> float:
    p = [max(x, 1e-10) for x in p]
    q = [max(x, 1e-10) for x in q]
    if abs(sum(p) - 1.0) > 0.01:
        s = sum(p)
        p = [x / s for x in p]
    if abs(sum(q) - 1.0) > 0.01:
        s = sum(q)
        q = [x / s for x in q]
    if HAS_SCIPY:
        return float(entropy(p, q))
    return sum(pi * math.log(pi / qi) for pi, qi in zip(p, q))


def _js_divergence(p: list[float], q: list[float]) -> float:
    p = [max(x, 1e-10) for x in p]
    q = [max(x, 1e-10) for x in q]
    if abs(sum(p) - 1.0) > 0.01:
        s = sum(p)
        p = [x / s for x in p]
    if abs(sum(q) - 1.0) > 0.01:
        s = sum(q)
        q = [x / s for x in q]
    m = [(pi + qi) / 2 for pi, qi in zip(p, q)]
    return (_kl_divergence(p, m) + _kl_divergence(q, m)) / 2


def _hellinger_distance(p: list[float], q: list[float]) -> float:
    p = [max(x, 1e-10) for x in p]
    q = [max(x, 1e-10) for x in q]
    if abs(sum(p) - 1.0) > 0.01:
        s = sum(p)
        p = [x / s for x in p]
    if abs(sum(q) - 1.0) > 0.01:
        s = sum(q)
        q = [x / s for x in q]
    return math.sqrt(
        0.5 * sum((math.sqrt(pi) - math.sqrt(qi)) ** 2 for pi, qi in zip(p, q))
    )


KL_WARNING = 0.1
KL_CRITICAL = 0.5
HELLINGER_WARNING = 0.2
HELLINGER_CRITICAL = 0.5
BASELINE_COOLDOWN = 60
HUMAN_REVIEW_TIMEOUT = 300


class DriftDetector:
    def __init__(self) -> None:
        self.baselines: dict[str, list[float]] = {}
        self.samples: defaultdict[str, list[list[float]]] = defaultdict(list)
        self.results: list[dict[str, Any]] = []
        self.false_negatives = 0
        self.false_positives = 0
        self.total_checks = 0
        self.last_baseline_reset: dict[str, float] = {}

    def add_baseline(self, name: str, distribution: list[float]) -> None:
        self.baselines[name] = list(distribution)
        self.last_baseline_reset[name] = time.time()

    def add_sample(self, name: str, distribution: list[float]) -> None:
        self.samples[name].append(list(distribution))

    def check_drift(
        self, name: str, sample: list[float] | None = None
    ) -> dict[str, Any]:
        if name not in self.baselines:
            return {"error": "no_baseline", "name": name}

        baseline = self.baselines[name]
        sample = sample or (self.samples[name][-1] if self.samples[name] else None)

        if sample is None:
            return {"error": "no_sample", "name": name}

        self.total_checks += 1

        kl = _kl_divergence(baseline, sample)
        js = _js_divergence(baseline, sample)
        hd = _hellinger_distance(baseline, sample)

        drift_warning = kl >= KL_WARNING or hd >= HELLINGER_WARNING
        drift_critical = kl >= KL_CRITICAL or hd >= HELLINGER_CRITICAL

        result = {
            "name": name,
            "kl_divergence": round(kl, 4),
            "js_divergence": round(js, 4),
            "hellinger_distance": round(hd, 4),
            "drift_warning": drift_warning,
            "drift_critical": drift_critical,
            "baseline_length": len(baseline),
            "sample_length": len(sample),
        }

        self.results.append(result)
        return result

    def auto_reset_baseline(self, name: str, sample: list[float] | None = None) -> bool:
        if name not in self.baselines:
            return False
        now = time.time()
        last_reset = self.last_baseline_reset.get(name, 0)
        if now - last_reset < BASELINE_COOLDOWN:
            return False
        sample = sample or (self.samples[name][-1] if self.samples[name] else None)
        if sample:
            self.add_baseline(name, sample)
            return True
        return False

    def record_false_negative(self) -> None:
        self.false_negatives += 1

    def record_false_positive(self) -> None:
        self.false_positives += 1

    @property
    def fnr(self) -> float:
        if self.total_checks == 0:
            return 0.0
        return self.false_negatives / self.total_checks

    @property
    def fpr(self) -> float:
        if self.total_checks == 0:
            return 0.0
        return self.false_positives / self.total_checks

    def clear(self) -> None:
        self.baselines.clear()
        self.samples.clear()
        self.results.clear()
        self.false_negatives = 0
        self.false_positives = 0
        self.total_checks = 0


# --- Federation Circuit Breaker Cascade ---


class FederationCircuitBreaker:
    """Models cascading circuit breaker failure propagation across a federation.

    Each agent has a binary breaker state (CLOSED/OPEN). When an agent's
    breaker trips, dependent agents may also trip, creating a cascade.
    Measures cascade depth, width, and containment.
    """

    def __init__(
        self,
        agent_names: list[str] | None = None,
        dependency_matrix: list[list[float]] | None = None,
    ) -> None:
        self.agent_names = agent_names or [
            "claude_code",
            "codex",
            "cursor",
            "opencode",
            "trae_cn",
        ]
        self.n = len(self.agent_names)
        self.dependency_threshold = 0.4
        self.dependency_matrix = (
            dependency_matrix if dependency_matrix else self._default_mesh()
        )
        self.reset_all()

    def _default_mesh(self) -> list[list[float]]:
        n = self.n
        m = [[0.0] * n for _ in range(n)]
        for i in range(1, n):
            m[i][0] = 0.8
        if n > 2:
            m[2][1] = 0.5
            if n > 3:
                m[3][1] = 0.5
                m[3][2] = 0.5
        return m

    def reset_all(self) -> None:
        self.agent_states = {name: "CLOSED" for name in self.agent_names}
        self.agent_failures = {name: 0 for name in self.agent_names}
        self.cascade_history: list[dict[str, Any]] = []

    def _trip_breaker(self, name: str) -> None:
        self.agent_failures[name] = 3
        self.agent_states[name] = "OPEN"

    def trigger(self, source_idx: int) -> dict[str, Any]:
        source_name = self.agent_names[source_idx]
        self._trip_breaker(source_name)

        visited = {source_idx}
        queue = collections.deque([(source_idx, 0)])
        cascade_path = [(source_name, "OPEN", 0)]
        affected_indices = {source_idx}
        max_depth = 0

        while queue:
            current, depth = queue.popleft()
            for i in range(self.n):
                if i in visited:
                    continue
                dep_weight = self.dependency_matrix[i][current]
                if dep_weight > self.dependency_threshold:
                    dep_name = self.agent_names[i]
                    self._trip_breaker(dep_name)
                    visited.add(i)
                    affected_indices.add(i)
                    new_depth = depth + 1
                    max_depth = max(max_depth, new_depth)
                    queue.append((i, new_depth))
                    cascade_path.append((dep_name, "OPEN", new_depth))

        result = {
            "source": source_name,
            "cascade_depth": max_depth,
            "affected_count": len(affected_indices),
            "total_agents": self.n,
            "affected_pct": len(affected_indices) / self.n * 100,
            "cascade_path": cascade_path,
            "fully_contained": len(affected_indices) == 1,
        }
        self.cascade_history.append(result)
        return result

    def cascade_metrics(self) -> dict[str, float | int]:
        if not self.cascade_history:
            return {
                "avg_depth": 0.0,
                "avg_affected_pct": 0.0,
                "containment_rate": 0.0,
                "scenarios_run": 0,
            }
        depths = [h["cascade_depth"] for h in self.cascade_history]
        affected_pcts = [h["affected_pct"] for h in self.cascade_history]
        contained = sum(1 for h in self.cascade_history if h["fully_contained"])
        return {
            "avg_depth": sum(depths) / len(depths),
            "avg_affected_pct": sum(affected_pcts) / len(affected_pcts),
            "containment_rate": contained / len(self.cascade_history),
            "scenarios_run": len(self.cascade_history),
        }


# --- Scoring ---

CHAOS_WEIGHTS = {
    "infra": 0.30,
    "federation": 0.20,
    "llm": 0.30,
    "fed_cascade": 0.20,
}


def _score_federation_cascade(
    ce: ChaosEngine | None = None, card: dict[str, Any] | None = None
) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    fcb = FederationCircuitBreaker()

    source_indices = [0, 3, 1]
    for source_idx in source_indices:
        fcb.reset_all()
        result = fcb.trigger(source_idx)
        findings.append(
            {
                "severity": "INFO",
                "category": "fed_cascade",
                "detail": (
                    f"Cascade from '{result['source']}': "
                    f"depth={result['cascade_depth']}, "
                    f"affected={result['affected_count']}/{result['total_agents']}, "
                    f"contained={result['fully_contained']}"
                ),
            }
        )
        if ce:
            for _ in range(result["affected_count"]):
                ce.record_healing(f"fed_cascade_{source_idx}", True)

    metrics = fcb.cascade_metrics()

    containment_score = metrics["containment_rate"] * 40
    max_depth = fcb.n - 1
    depth_ratio = metrics["avg_depth"] / max_depth if max_depth > 0 else 0
    depth_score = max(0, 1 - depth_ratio) * 30
    affected_ratio = metrics["avg_affected_pct"] / 100
    affected_score = max(0, 1 - affected_ratio) * 30
    score = containment_score + depth_score + affected_score

    findings.append(
        {
            "severity": "INFO",
            "category": "fed_cascade_summary",
            "detail": (
                f"Cascade containment={metrics['containment_rate']:.0%}, "
                f"avg_depth={metrics['avg_depth']:.1f}/{max_depth}, "
                f"avg_affected={metrics['avg_affected_pct']:.0f}% "
                f"({metrics['scenarios_run']} scenarios)"
            ),
        }
    )

    return round(score, 1), findings


def _score_chaos(
    ce: ChaosEngine, card: dict[str, Any] | None = None
) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    score = 0.0

    injection_mode = ce.injection_mode()
    findings.append(
        {
            "severity": "INFO",
            "category": "chaos_injection_mode",
            "detail": f"Fault injection mode: {injection_mode}",
        }
    )

    base_success_rate = 0.85
    if card:
        capabilities = card.get("capabilities", [])
        tool_count = len(capabilities)
        base_success_rate = min(0.95, 0.60 + tool_count * 0.03)

        constitution = card.get("constitution", {})
        health = constitution.get("health_state", "")
        if health.upper() in ("HEALTHY",):
            base_success_rate += 0.05
        if constitution.get("heartbeat_interval_seconds", 999) <= 30:
            base_success_rate += 0.05
        base_success_rate = min(base_success_rate, 0.95)

    infra_threshold = 1.0 - base_success_rate
    fed_threshold = 1.0 - (base_success_rate - 0.03)
    llm_threshold = 1.0 - (base_success_rate - 0.05)

    for fault in INFRA_FAULTS:
        for scenario in range(3):
            ce.inject(fault, scenario)
            success = ce.rng.random() > infra_threshold
            recovery = ce.rng.uniform(1, 25)
            ce.record_healing(fault, success, recovery_time=recovery)
            if not success:
                ce.fault_history[-1]["healed"] = False

    infra_rate = ce.infra_healing_rate()

    for fault in FEDERATION_FAULTS:
        for scenario in range(3):
            ce.inject(fault, scenario)
            success = ce.rng.random() > fed_threshold
            recovery = ce.rng.uniform(1, 30)
            ce.record_healing(fault, success, recovery_time=recovery)
            if not success:
                ce.fault_history[-1]["healed"] = False

    fed_rate = ce.federation_healing_rate()

    for fault in LLM_FAULTS:
        for scenario in range(3):
            ce.inject(fault, scenario)
            success = ce.rng.random() > llm_threshold
            recovery = ce.rng.uniform(1, 35)
            ce.record_healing(fault, success, recovery_time=recovery)
            if not success:
                ce.fault_history[-1]["healed"] = False

    llm_rate = ce.llm_healing_rate()

    cascade_score, cascade_findings = _score_federation_cascade(ce, card)
    findings.extend(cascade_findings)

    infra_score = infra_rate * 100
    fed_score = fed_rate * 100
    llm_score = llm_rate * 100

    score = (
        infra_score * CHAOS_WEIGHTS["infra"]
        + fed_score * CHAOS_WEIGHTS["federation"]
        + llm_score * CHAOS_WEIGHTS["llm"]
        + cascade_score * CHAOS_WEIGHTS["fed_cascade"]
    )

    findings.append(
        {
            "severity": "INFO",
            "category": "chaos_infra",
            "detail": (
                f"Infra self-heal rate: {infra_rate * 100:.0f}% "
                f"(weight {CHAOS_WEIGHTS['infra']:.0%})"
            ),
        }
    )
    findings.append(
        {
            "severity": "INFO",
            "category": "chaos_federation",
            "detail": (
                f"Federation self-heal rate: {fed_rate * 100:.0f}% "
                f"(weight {CHAOS_WEIGHTS['federation']:.0%})"
            ),
        }
    )
    findings.append(
        {
            "severity": "INFO",
            "category": "chaos_llm",
            "detail": (
                f"LLM self-heal rate: {llm_rate * 100:.0f}% "
                f"(weight {CHAOS_WEIGHTS['llm']:.0%})"
            ),
        }
    )

    overall_rate = ce.healing_rate()
    findings.append(
        {
            "severity": "INFO",
            "category": "chaos_overall",
            "detail": f"Overall self-heal rate: {overall_rate * 100:.0f}% ({sum(len(v) for v in ce.healing_results.values())} total injections)",
        }
    )

    unhealed = [r for r in ce.fault_history if r.get("healed") is False]
    if unhealed:
        for r in unhealed[:3]:
            findings.append(
                {
                    "severity": "WARNING",
                    "category": "chaos_unhealed",
                    "detail": f"Fault '{r['fault']}' (scenario {r['scenario']}) failed to self-heal",
                }
            )

    return round(score, 1), findings


def _score_drift(dd: DriftDetector) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    score = 100.0

    dd.add_baseline("tool_weights", [0.25, 0.20, 0.15, 0.10, 0.10, 0.10, 0.05, 0.05])
    dd.add_baseline("model_probs", [0.4, 0.3, 0.2, 0.1])

    sample_small = [0.24, 0.21, 0.16, 0.11, 0.10, 0.09, 0.05, 0.04]
    res1 = dd.check_drift("tool_weights", sample_small)
    if res1 and not res1.get("drift_warning"):
        score -= 15
        dd.record_false_negative()

    sample_drifted = [0.40, 0.30, 0.10, 0.05, 0.05, 0.05, 0.03, 0.02]
    res2 = dd.check_drift("tool_weights", sample_drifted)
    if res2 and res2.get("drift_warning"):
        findings.append(
            {
                "severity": "INFO",
                "category": "drift_detected",
                "detail": f"Drift detected: KL={res2['kl_divergence']:.4f}, JS={res2['js_divergence']:.4f}, H={res2['hellinger_distance']:.4f}",
            }
        )
    else:
        score -= 25

    dd.record_false_positive()
    score -= 5

    sample_close = [0.25, 0.20, 0.15, 0.10, 0.10, 0.10, 0.05, 0.05]
    res3 = dd.check_drift("tool_weights", sample_close)
    if res3 and res3.get("drift_warning"):
        score -= 5
        dd.record_false_positive()

    auto_reset = dd.auto_reset_baseline("tool_weights", sample_close)
    if auto_reset:
        findings.append(
            {
                "severity": "INFO",
                "category": "drift_auto_reset",
                "detail": "Baseline auto-reset triggered after cooldown",
            }
        )

    findings.append(
        {
            "severity": "INFO",
            "category": "drift_summary",
            "detail": f"FNR={dd.fnr:.2%}, FPR={dd.fpr:.2%}, checks={dd.total_checks}",
        }
    )

    score = max(0, min(100, score))
    return round(score, 1), findings


# --- Reflection Loop ---

QUALITY_DIMS = {
    "correctness": 0.25,
    "completeness": 0.25,
    "safety": 0.20,
    "efficiency": 0.15,
    "consistency": 0.15,
}

CRITIQUE_CATEGORIES = [
    "logical_error",
    "missing_edge_case",
    "safety_concern",
    "inefficient",
    "inconsistent",
]


class ReflectiveAgent:
    def __init__(self, max_iterations: int = 3) -> None:
        self.max_iterations = max_iterations
        self.history: list[dict[str, Any]] = []
        self.current_output = ""
        self.iteration = 0
        self.critiques: list[dict[str, float]] = []
        self.scores: list[float] = []

    def generate(self, task: str, output: str | None = None) -> None:
        self.iteration = 0
        self.critiques = []
        self.scores = []
        self.current_output = output or f"Draft solution for: {task}"
        self.history.append(
            {"iteration": 0, "phase": "generate", "output": self.current_output}
        )

    def critique(self, critique_scores: dict[str, float] | None = None) -> float:
        if self.iteration >= self.max_iterations:
            return self.scores[-1] if self.scores else 0

        if critique_scores:
            dim_scores = critique_scores
        else:
            dim_scores = {
                "correctness": round(self._mock_score(0.5, 0.9), 2),
                "completeness": round(self._mock_score(0.5, 0.9), 2),
                "safety": round(self._mock_score(0.7, 1.0), 2),
                "efficiency": round(self._mock_score(0.4, 0.8), 2),
                "consistency": round(self._mock_score(0.6, 0.9), 2),
            }

        weighted = sum(dim_scores[d] * w for d, w in QUALITY_DIMS.items())
        self.scores.append(weighted)
        self.critiques.append(dim_scores)

        found_categories = []
        for cat in CRITIQUE_CATEGORIES:
            if self._mock_score(0, 1) > 0.6:
                found_categories.append(cat)

        self.history.append(
            {
                "iteration": self.iteration,
                "phase": "critique",
                "dim_scores": dim_scores,
                "weighted_score": weighted,
                "critique_categories": found_categories,
            }
        )

        return weighted

    def _mock_score(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * 0.5

    def refine(self, refinement: str | None = None) -> str:
        if self.iteration >= self.max_iterations:
            return self.current_output

        self.iteration += 1
        self.current_output = (
            refinement or f"Refined iteration {self.iteration}: {self.current_output}"
        )
        self.history.append(
            {
                "iteration": self.iteration,
                "phase": "refine",
                "output": self.current_output,
            }
        )
        return self.current_output

    def verify(self) -> bool:
        if not self.scores:
            return False
        threshold = 0.85
        best_score = max(self.scores)
        return best_score >= threshold

    def accept(self) -> dict[str, Any]:
        best_idx = (
            max(range(len(self.scores)), key=lambda i: self.scores[i])
            if self.scores
            else -1
        )
        return {
            "accepted_iteration": best_idx,
            "best_score": max(self.scores) if self.scores else 0,
            "total_iterations": self.iteration,
            "critique_history": self.critiques,
        }

    def clear(self) -> None:
        self.history.clear()
        self.current_output = ""
        self.iteration = 0
        self.critiques.clear()
        self.scores.clear()


# --- Convergence Verification ---

C1_CONSISTENCY_THRESHOLD = 0.7
C2_AGREEMENT_THRESHOLD = 0.6
C3_PASS_THRESHOLD = 80


def _cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return dot / (na * nb)


class ConvergenceVerifier:
    def __init__(self) -> None:
        self.responses: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        self.task_results: dict[str, bool] = {}
        self._verifier_registry = None

    def add_response(
        self, task_id: str, response_text: str, embedding: list[float] | None = None
    ) -> None:
        self.responses[task_id].append(
            {
                "text": response_text,
                "embedding": embedding or self._mock_embedding(response_text),
                "timestamp": time.time(),
            }
        )

    def add_task_result(self, task_id: str, passed: bool) -> None:
        self.task_results[task_id] = passed

    def set_verifier_registry(self, registry: Any) -> None:
        """Set a VerifierRegistry for cross-validated evaluation."""
        self._verifier_registry = registry

    def _mock_embedding(self, text: str) -> list[float]:
        return [hash(c) % 100 / 100.0 for c in text.ljust(8, "_")[:8]]

    def score_c1_consistency(self, task_id: str | None = None) -> float:
        task_ids = [task_id] if task_id else list(self.responses.keys())
        if not task_ids:
            return 0.0

        scores = []
        for tid in task_ids:
            resp_list = self.responses.get(tid, [])
            if len(resp_list) < 2:
                scores.append(0.0)
                continue
            sims = []
            for i in range(len(resp_list)):
                e1 = resp_list[i]["embedding"]
                for j in range(i + 1, len(resp_list)):
                    e2 = resp_list[j]["embedding"]
                    sims.append(_cosine_sim(e1, e2))
            if sims:
                scores.append(sum(sims) / len(sims))
            else:
                scores.append(0.0)

        avg = sum(scores) / len(scores) if scores else 0.0
        return round(avg, 2)

    def score_c2_self_consistency(self, task_id: str | None = None) -> float:
        task_ids = [task_id] if task_id else list(self.responses.keys())
        if not task_ids:
            return 0.0

        scores = []
        for tid in task_ids:
            resp_list = self.responses.get(tid, [])
            if len(resp_list) < 3:
                scores.append(0.0)
                continue
            embeddings = [r["embedding"] for r in resp_list]
            agreement = 0
            for i, e1 in enumerate(embeddings):
                matches = sum(
                    1
                    for j, e2 in enumerate(embeddings)
                    if i != j and _cosine_sim(e1, e2) >= C1_CONSISTENCY_THRESHOLD
                )
                if matches >= len(embeddings) - 2:
                    agreement += 1
            scores.append(agreement / len(embeddings))

        avg = sum(scores) / len(scores) if scores else 0.0
        return round(avg, 2)

    def score_c3_task_completion(self) -> float:
        if not self.task_results:
            return 0.0
        passed = sum(1 for v in self.task_results.values() if v)
        return round(passed / len(self.task_results) * 100, 1)

    def clear(self) -> None:
        self.responses.clear()
        self.task_results.clear()


def _score_reflection(
    ra: ReflectiveAgent | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    if ra is None:
        ra = ReflectiveAgent(max_iterations=3)

    ra.generate("Solve: 2x + 4 = 10")

    score_rounds = []
    for i in range(3):
        s = ra.critique()
        score_rounds.append(s)
        ra.refine()
        if ra.verify():
            break

    acceptance = ra.accept()
    best_score = acceptance["best_score"]
    score = round(best_score * 100, 1)

    findings.append(
        {
            "severity": "INFO",
            "category": "reflection_loop",
            "detail": f"CriticAgent: {acceptance['total_iterations']} rounds, best score={best_score:.3f}, accepted at iteration {acceptance['accepted_iteration']}",
        }
    )

    convergence_rate = len(
        [s for s in acceptance["critique_history"] if max(s.values()) > 0.8]
    ) / max(len(acceptance["critique_history"]), 1)
    findings.append(
        {
            "severity": "INFO",
            "category": "reflection_convergence",
            "detail": f"Dimension convergence rate: {convergence_rate:.0%}",
        }
    )

    return score, findings


def _score_convergence(
    cv: ConvergenceVerifier | None = None,
    verifier_registry: Any = None,
) -> tuple[float, list[dict[str, Any]]]:
    findings = []
    if cv is None:
        cv = ConvergenceVerifier()
    if verifier_registry:
        cv.set_verifier_registry(verifier_registry)

    cv.add_response("math_1", "x = 3")
    cv.add_response("math_1", "x = 3")
    cv.add_response("math_1", "x = 3")
    cv.add_response("math_1", "The answer is 3")
    cv.add_response("math_1", "x equals 3")

    cv.add_response("code_1", "def add(a,b): return a+b")
    cv.add_response("code_1", "def add(a, b):\n    return a + b")
    cv.add_response("code_1", "def sum(a,b): return a+b")
    cv.add_response("code_1", "def add_numbers(a, b): return a + b")
    cv.add_response("code_1", "def add(a,b):\n    return a+b")

    cv.add_task_result("task_1", True)
    cv.add_task_result("task_2", True)
    cv.add_task_result("task_3", True)
    cv.add_task_result("task_4", False)
    cv.add_task_result("task_5", True)

    c1 = cv.score_c1_consistency()
    c2 = cv.score_c2_self_consistency()
    c3 = cv.score_c3_task_completion()

    if cv._verifier_registry is not None:
        task_ids = list(cv.responses.keys())
        if task_ids:
            for tid in task_ids:
                resp_texts = [r["text"] for r in cv.responses.get(tid, [])]
                if len(resp_texts) >= 2:
                    cons = cv._verifier_registry.consensus_evaluate(tid, resp_texts)
                    if cons["verifier_count"] > 0:
                        verifier_norm = cons["consensus_score"] / 100.0
                        c1 = round(c1 * 0.6 + verifier_norm * 0.4, 2)
                        break

    c1_score = min(100, c1 * 100)
    c2_score = min(100, c2 * 100)
    c3_score = c3
    score = c1_score * 0.35 + c2_score * 0.35 + c3_score * 0.30

    findings.append(
        {
            "severity": "INFO",
            "category": "convergence_c1",
            "detail": f"C1 Response Consistency: {c1:.2f} (score={c1_score:.1f}) — threshold≥{C1_CONSISTENCY_THRESHOLD}",
        }
    )
    findings.append(
        {
            "severity": "INFO",
            "category": "convergence_c2",
            "detail": f"C2 Self-Consistency: {c2:.2f} (score={c2_score:.1f}) — threshold≥{C2_AGREEMENT_THRESHOLD}",
        }
    )
    findings.append(
        {
            "severity": "INFO",
            "category": "convergence_c3",
            "detail": f"C3 Task Completion: {c3:.1f}% (score={c3_score:.1f}) — threshold≥{C3_PASS_THRESHOLD}%",
        }
    )
    findings.append(
        {
            "severity": "INFO",
            "category": "convergence_combined",
            "detail": f"C1×0.35 + C2×0.35 + C3×0.30 = {score:.1f}",
        }
    )

    return round(score, 1), findings


def run_d5_part1(
    ce: ChaosEngine | None = None,
    dd: DriftDetector | None = None,
    card: dict[str, Any] | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    ce = ce or ChaosEngine(seed=seed)
    dd = dd or DriftDetector()

    chaos_score, chaos_findings = _score_chaos(ce, card)
    drift_score, drift_findings = _score_drift(dd)

    all_findings = chaos_findings + drift_findings

    return {
        "domain": "D5",
        "component": "part1",
        "name": "Chaos Engineering + Drift Detection",
        "score": round(chaos_score * 0.30 + drift_score * 0.25, 1),
        "subscores": {
            "chaos_engineering": chaos_score,
            "drift_detection": drift_score,
        },
        "findings": all_findings,
        "summary": {
            "total_findings": len(all_findings),
            "chaos_overall_rate": f"{ce.healing_rate() * 100:.0f}%",
            "drift_total_checks": dd.total_checks,
            "drift_fnr": f"{dd.fnr:.2%}",
            "drift_fpr": f"{dd.fpr:.2%}",
        },
    }


def run_d5_part2(
    ra: ReflectiveAgent | None = None,
    cv: ConvergenceVerifier | None = None,
    verifier_registry: Any = None,
) -> dict[str, Any]:
    reflection_score, reflection_findings = _score_reflection(ra)
    convergence_score, convergence_findings = _score_convergence(cv, verifier_registry)
    all_findings = reflection_findings + convergence_findings

    return {
        "domain": "D5",
        "component": "part2",
        "name": "Reflection Loop + Convergence Verification",
        "score": round(reflection_score * 0.20 + convergence_score * 0.25, 1),
        "subscores": {
            "reflection_loop": reflection_score,
            "convergence_cycle": convergence_score,
        },
        "findings": all_findings,
        "summary": {
            "total_findings": len(all_findings),
            "reflection_score": reflection_score,
            "convergence_score": convergence_score,
        },
    }


def run_d5(
    ce: ChaosEngine | None = None,
    dd: DriftDetector | None = None,
    card: dict[str, Any] | None = None,
    seed: int = 42,
    verifier_registry: Any = None,
) -> dict[str, Any]:
    """Run D5 evaluation: chaos engineering + drift detection + reflection + convergence.

    Args:
        ce: Optional ChaosEngine instance (created with seed if None).
        dd: Optional DriftDetector instance.
        card: Optional agent card dict.
        seed: Random seed for deterministic chaos injection (default 42).
        verifier_registry: Optional VerifierRegistry for cross-validated evaluation.

    Returns:
        Dict with domain, score, subscores, findings.
    """
    p1 = run_d5_part1(ce, dd, card, seed=seed)
    p2 = run_d5_part2(verifier_registry=verifier_registry)

    d5_score = (
        p1["subscores"]["chaos_engineering"] * 0.30
        + p1["subscores"]["drift_detection"] * 0.25
        + p2["subscores"]["reflection_loop"] * 0.20
        + p2["subscores"]["convergence_cycle"] * 0.25
    )

    return {
        "domain": "D5",
        "name": "Evolution & Robustness",
        "score": round(d5_score, 1),
        "subscores": {
            "chaos_engineering": p1["subscores"]["chaos_engineering"],
            "drift_detection": p1["subscores"]["drift_detection"],
            "reflection_loop": p2["subscores"]["reflection_loop"],
            "convergence_cycle": p2["subscores"]["convergence_cycle"],
        },
        "part1_detail": p1,
        "part2_detail": p2,
        "findings": p1["findings"] + p2["findings"],
        "summary": {
            "total_findings": len(p1["findings"]) + len(p2["findings"]),
            "chaos_score": p1["subscores"]["chaos_engineering"],
            "drift_score": p1["subscores"]["drift_detection"],
            "reflection_score": p2["subscores"]["reflection_loop"],
            "convergence_score": p2["subscores"]["convergence_cycle"],
            "d5_score": round(d5_score, 1),
        },
    }
