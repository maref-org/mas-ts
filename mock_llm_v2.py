#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""
Mock LLM v2 - Enhanced Rule-Based LLM Simulator with Chaos Engineering

Usage:
  python mock_llm_v2.py --task "query order status" --mode normal
  python mock_llm_v2.py --task "analyze data" --mode network_partition --probability 0.3
  python mock_llm_v2.py --task-file tasks.json --mode hallucination --output mock_outputs/

Modes:
  Normal modes (10):
    - query_order, get_status, read_file, calculate, get_profile
    - route_to, select_tool, classify, search_flight, book_ticket

  Infra fault modes (5):
    - network_partition: Simulate network partition failures
    - cpu_pressure: Simulate high CPU load causing delays
    - memory_pressure: Simulate memory pressure causing crashes
    - disk_failure: Simulate disk I/O failures
    - process_kill: Simulate process termination

  LLM fault modes (5):
    - timeout: Simulate LLM timeout
    - hallucination: Simulate LLM hallucination
    - token_corruption: Simulate token corruption
    - model_degradation: Simulate model quality degradation
    - rate_limiting: Simulate API rate limiting

Total: 20 modes (10 normal + 10 fault)
"""

import argparse
import json
import logging
import random
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import argcomplete

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from mas_eval import __version__ as VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# Normal mock responses (10 modes)
NORMAL_MOCK_RESPONSES = {
    "query_order": {
        "tool_id": "query_order",
        "action_type": "tool_call",
        "input_keys": ["order_id"],
        "output": {
            "status": "shipped",
            "estimated_delivery": "2026-05-15",
            "tracking_number": "MOCK-TRACK-001",
        },
    },
    "get_status": {
        "tool_id": "get_status",
        "action_type": "tool_call",
        "input_keys": ["entity_id"],
        "output": {"status": "active", "last_updated": "2026-05-10T00:00:00Z"},
    },
    "read_file": {
        "tool_id": "read_file",
        "action_type": "tool_call",
        "input_keys": ["path"],
        "output": {"content": "[MOCK] File content placeholder", "size_bytes": 1024},
    },
    "calculate": {
        "tool_id": "calculate",
        "action_type": "tool_call",
        "input_keys": ["expression"],
        "output": {"result": 42.0, "precision": "float64"},
    },
    "get_profile": {
        "tool_id": "get_profile",
        "action_type": "tool_call",
        "input_keys": ["user_id"],
        "output": {"name": "Mock User", "email": "mock@example.com", "role": "user"},
    },
    "route_to": {
        "tool_id": "route_to",
        "action_type": "tool_call",
        "input_keys": ["department", "priority"],
        "output": {
            "routed_to": "department-{department}",
            "ticket_id": "MOCK-TICKET-001",
        },
    },
    "select_tool": {
        "tool_id": "select_tool",
        "action_type": "tool_call",
        "input_keys": ["task_type"],
        "output": {"selected_tool": "appropriate_tool_for_task", "confidence": 0.95},
    },
    "classify": {
        "tool_id": "classify",
        "action_type": "tool_call",
        "input_keys": ["text", "categories"],
        "output": {"category": "category_1", "confidence": 0.92},
    },
    "search_flight": {
        "tool_id": "search_flight",
        "action_type": "tool_call",
        "input_keys": ["origin", "dest"],
        "output": {
            "flights": [
                {
                    "flight_no": "MOCK-1001",
                    "departure": "08:00",
                    "arrival": "10:30",
                    "price": 580,
                }
            ]
        },
    },
    "book_ticket": {
        "tool_id": "book_ticket",
        "action_type": "tool_call",
        "input_keys": ["flight_no", "passenger"],
        "output": {"booking_id": "MOCK-BOOK-001", "status": "confirmed"},
    },
}

# Infra fault modes (5 modes)
INFRA_FAULT_MODES = {
    "network_partition": {
        "description": "Simulate network partition failures",
        "latency_ms": 5000,
        "error_rate": 0.3,
        "error_type": "NetworkError",
    },
    "cpu_pressure": {
        "description": "Simulate high CPU load causing delays",
        "latency_ms": 2000,
        "error_rate": 0.1,
        "error_type": "TimeoutError",
    },
    "memory_pressure": {
        "description": "Simulate memory pressure causing crashes",
        "latency_ms": 1000,
        "error_rate": 0.2,
        "error_type": "MemoryError",
    },
    "disk_failure": {
        "description": "Simulate disk I/O failures",
        "latency_ms": 3000,
        "error_rate": 0.25,
        "error_type": "IOError",
    },
    "process_kill": {
        "description": "Simulate process termination",
        "latency_ms": 100,
        "error_rate": 0.15,
        "error_type": "ProcessTerminatedError",
    },
}

# LLM fault modes (5 modes)
LLM_FAULT_MODES = {
    "timeout": {
        "description": "Simulate LLM timeout",
        "latency_ms": 30000,
        "error_rate": 1.0,
        "error_type": "TimeoutError",
    },
    "hallucination": {
        "description": "Simulate LLM hallucination",
        "latency_ms": 500,
        "error_rate": 0.4,
        "error_type": "HallucinationError",
    },
    "token_corruption": {
        "description": "Simulate token corruption",
        "latency_ms": 200,
        "error_rate": 0.3,
        "error_type": "TokenCorruptionError",
    },
    "model_degradation": {
        "description": "Simulate model quality degradation",
        "latency_ms": 1000,
        "error_rate": 0.2,
        "error_type": "ModelDegradationError",
    },
    "rate_limiting": {
        "description": "Simulate API rate limiting",
        "latency_ms": 100,
        "error_rate": 0.5,
        "error_type": "RateLimitError",
    },
}

ALL_MODES = (
    list(NORMAL_MOCK_RESPONSES.keys())
    + list(INFRA_FAULT_MODES.keys())
    + list(LLM_FAULT_MODES.keys())
)


def get_mode_config(mode: str) -> Dict[str, Any]:
    """Get configuration for a specific mode."""
    if mode in NORMAL_MOCK_RESPONSES:
        return {"type": "normal", "config": NORMAL_MOCK_RESPONSES[mode]}
    elif mode in INFRA_FAULT_MODES:
        return {"type": "infra_fault", "config": INFRA_FAULT_MODES[mode]}
    elif mode in LLM_FAULT_MODES:
        return {"type": "llm_fault", "config": LLM_FAULT_MODES[mode]}
    else:
        raise ValueError(f"Unknown mode: {mode}")


def simulate_fault(
    mode_config: Dict[str, Any], probability: float = 0.5
) -> Optional[Dict[str, Any]]:
    """Simulate a fault based on mode configuration and probability."""
    if mode_config["type"] == "normal":
        return None

    config = mode_config["config"]

    # Simulate latency
    latency_ms = config.get("latency_ms", 100)
    time.sleep(latency_ms / 1000.0)

    # Simulate error based on probability
    if random.random() < probability:
        return {
            "error_type": config.get("error_type", "UnknownError"),
            "error_message": f"Simulated {config.get('description', 'error')}",
            "latency_ms": latency_ms,
        }

    return None


def generate_hallucinated_response(task_description: str) -> Dict[str, Any]:
    """Generate a hallucinated response for a task."""
    hallucinations = [
        "I'm confident that the answer is 42, but I'm not sure why.",
        "The data shows a clear trend that doesn't actually exist.",
        "Based on my analysis, the opposite is actually true.",
        "I found information that contradicts itself but seems correct.",
        "The result is exactly what you want, even if it's not accurate.",
    ]
    return {
        "result": random.choice(hallucinations),
        "confidence": random.uniform(0.7, 0.95),
        "hallucination_detected": True,
    }


def generate_corrupted_response(original_response: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a corrupted response by modifying the original."""
    corrupted = original_response.copy()
    if "output" in corrupted:
        if isinstance(corrupted["output"], dict):
            for key in corrupted["output"]:
                if isinstance(corrupted["output"][key], str):
                    # Corrupt string data
                    corrupted["output"][key] = corrupted["output"][key][::-1]
                elif isinstance(corrupted["output"][key], (int, float)):
                    # Corrupt numeric data
                    corrupted["output"][key] *= random.uniform(0.5, 1.5)
    corrupted["corruption_detected"] = True
    return corrupted


def generate_degraded_response(original_response: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a degraded response with lower quality."""
    degraded = original_response.copy()
    if "output" in degraded and isinstance(degraded["output"], dict):
        degraded["output"]["confidence"] = random.uniform(0.5, 0.7)
        degraded["output"]["quality"] = "degraded"
    return degraded


def generate_mock_trajectory_v2(
    task_description: str,
    mode: str = "normal",
    probability: float = 0.5,
    agent_card: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Generate mock trajectory with fault simulation."""
    trace_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Get mode configuration
    try:
        mode_config = get_mode_config(mode)
    except ValueError as e:
        logger.error(str(e))
        mode = "normal"
        mode_config = get_mode_config(mode)

    # Find matching tool for normal mode
    tool_id = None
    tool_def = None
    if mode_config["type"] == "normal":
        for tool_name, tool_info in NORMAL_MOCK_RESPONSES.items():
            if re.search(re.escape(tool_name), task_description, re.IGNORECASE):
                tool_id = tool_name
                tool_def = tool_info
                break
    else:
        # For fault modes, use a default tool for simulation
        tool_id = "mock_tool"
        tool_def = {
            "tool_id": "mock_tool",
            "action_type": "tool_call",
            "input_keys": ["input"],
            "output": {"result": "mock_result"},
        }

    # Simulate fault
    fault = simulate_fault(mode_config, probability)

    events = []

    # Task start event
    events.append(
        {
            "trace_id": trace_id,
            "standard_version": "MAS-TS-001-v3.0",
            "run_mode": "mock-v2",
            "timestamp": now,
            "event_type": "task_start",
            "sequence": 1,
            "task": {
                "task_id": f"mock-task-{trace_id[:8]}",
                "description": task_description,
                "mode": mode,
                "fault_probability": probability,
            },
            "agent": {
                "agent_id": agent_card.get(
                    "agent_id", "urn:agent:mock:default:mock-agent"
                )
                if agent_card
                else "urn:agent:mock:default:mock-agent",
                "role": "worker",
                "card_version": "2.0",
            },
            "action": {"type": "task_received"},
            "state_delta": {},
            "orchestration": {
                "routing_decision": "auto",
                "routing_reason": "mock_dispatch",
            },
            "error": None,
            "recovery": None,
        }
    )

    # Agent action event
    if fault:
        # Fault occurred
        events.append(
            {
                "trace_id": trace_id,
                "standard_version": "MAS-TS-001-v3.0",
                "run_mode": "mock-v2",
                "timestamp": now,
                "event_type": "agent_action",
                "sequence": 2,
                "task": events[0]["task"],
                "agent": events[0]["agent"],
                "action": {
                    "type": "error",
                    "error_type": fault["error_type"],
                    "error_message": fault["error_message"],
                    "latency_ms": fault["latency_ms"],
                },
                "state_delta": {},
                "orchestration": {
                    "routing_decision": "error",
                    "routing_reason": f"fault_{mode}",
                },
                "error": {
                    "type": fault["error_type"],
                    "message": fault["error_message"],
                    "recoverable": fault["error_type"]
                    not in ["ProcessTerminatedError", "MemoryError"],
                },
                "recovery": None,
            }
        )
    elif tool_def:
        # Normal execution with potential mode-specific modifications
        output = tool_def["output"].copy()

        # Apply mode-specific modifications
        if mode == "hallucination":
            output = generate_hallucinated_response(task_description)
        elif mode == "token_corruption":
            output = generate_corrupted_response(tool_def)
        elif mode == "model_degradation":
            output = generate_degraded_response(tool_def)

        mock_input = {}
        for key in tool_def.get("input_keys", []):
            mock_input[key] = f"mock_{key}_value"

        events.append(
            {
                "trace_id": trace_id,
                "standard_version": "MAS-TS-001-v3.0",
                "run_mode": "mock-v2",
                "timestamp": now,
                "event_type": "agent_action",
                "sequence": 2,
                "task": events[0]["task"],
                "agent": events[0]["agent"],
                "action": {
                    "type": "tool_call",
                    "tool_id": tool_id,
                    "input": mock_input,
                    "output": output,
                    "latency_ms": mode_config["config"].get("latency_ms", 10),
                    "token_usage": {"input": 0, "output": 0},
                    "cost_usd": 0.0,
                },
                "state_delta": {
                    "memory_read": [],
                    "memory_write": {},
                    "shared_state_touch": False,
                },
                "orchestration": {
                    "routing_decision": "auto",
                    "routing_reason": f"capability_match:{tool_id}",
                    "chat_storm_detected": False,
                },
                "error": None,
                "recovery": None,
            }
        )

        # Task complete event
        events.append(
            {
                "trace_id": trace_id,
                "standard_version": "MAS-TS-001-v3.0",
                "run_mode": "mock-v2",
                "timestamp": now,
                "event_type": "task_complete",
                "sequence": 3,
                "task": events[0]["task"],
                "agent": events[0]["agent"],
                "action": {"type": "task_complete", "result": "success"},
                "state_delta": {},
                "orchestration": {
                    "routing_decision": None,
                    "routing_reason": None,
                    "chat_storm_detected": False,
                },
                "error": None,
                "recovery": None,
            }
        )
    else:
        # No matching tool
        events.append(
            {
                "trace_id": trace_id,
                "standard_version": "MAS-TS-001-v3.0",
                "run_mode": "mock-v2",
                "timestamp": now,
                "event_type": "agent_action",
                "sequence": 2,
                "task": events[0]["task"],
                "agent": events[0]["agent"],
                "action": {
                    "type": "need_clarification",
                    "reason": f"Unknown task pattern or mode: {mode}",
                },
                "state_delta": {},
                "orchestration": {
                    "routing_decision": "fallback",
                    "routing_reason": "unknown_task",
                },
                "error": None,
                "recovery": None,
            }
        )

    return {
        "trace_id": trace_id,
        "standard_version": "MAS-TS-001-v3.0",
        "run_mode": "mock-v2",
        "task_description": task_description,
        "mode": mode,
        "fault_probability": probability,
        "matched_tool": tool_id,
        "fault": fault,
        "cost_usd": 0.0,
        "events": events,
    }


def process_task_file_v2(
    task_file: str,
    mode: str = "normal",
    probability: float = 0.5,
    output_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Process task file with fault simulation."""
    try:
        with open(task_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in task file %s: %s", task_file, e)
        sys.exit(1)

    results = []
    task_list = tasks if isinstance(tasks, list) else tasks.get("tasks", [tasks])

    for task_desc in task_list:
        if isinstance(task_desc, dict):
            task_desc = task_desc.get(
                "description", task_desc.get("task", str(task_desc))
            )
        result = generate_mock_trajectory_v2(task_desc, mode, probability)
        results.append(result)

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        for result in results:
            task_id = result["trace_id"][:8]
            out_file = out_path / f"mock_v2_{task_id}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="MAS-TS-001 Mock LLM Simulator v2 with Chaos Engineering"
    )
    parser.add_argument(
        "--version", action="version", version=f"mas-eval-harness {VERSION}"
    )
    parser.add_argument(
        "--mode",
        default="query_order",
        choices=ALL_MODES,
        help="Simulation mode (normal or fault mode)",
    )
    parser.add_argument(
        "--probability", type=float, default=0.5, help="Fault probability (0.0-1.0)"
    )
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--task", help="Single task description")
    group.add_argument("--task-file", help="JSON file with task descriptions")

    parser.add_argument("--output", help="Save output to JSON file")
    parser.add_argument(
        "--output-dir", help="Save individual mock trajectories to directory"
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)

    if args.task:
        result = generate_mock_trajectory_v2(args.task, args.mode, args.probability)
        output = result
    else:
        results = process_task_file_v2(
            args.task_file, args.mode, args.probability, args.output_dir
        )
        output = {
            "standard": "MAS-TS-001",
            "version": "v3.0",
            "mode": "mock-v2",
            "simulation_mode": args.mode,
            "fault_probability": args.probability,
            "total_tasks": len(results),
            "successful_tasks": len([r for r in results if not r["fault"]]),
            "failed_tasks": len([r for r in results if r["fault"]]),
            "total_cost_usd": 0.0,
            "results": results,
        }

    print(json.dumps(output, indent=2, ensure_ascii=False))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        logger.info("Output saved to %s", args.output)


if __name__ == "__main__":
    main()
