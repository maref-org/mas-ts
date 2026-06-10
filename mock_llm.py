#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""
Mock LLM - Rule-Based LLM Simulator for Fast-Screen Mode
Usage:
  python mock_llm.py --task "query order status" --policy mock_policy.yaml
  python mock_llm.py --task-file tasks.json --policy mock_policy.yaml --output mock_outputs/

Replaces real LLM calls with rule-based responses for known tool calls.
Tests orchestration logic only, NOT intelligence.
"""

import argparse
import json
import logging
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import argcomplete
import yaml

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from mas_eval import __version__ as VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


MOCK_RESPONSES = {
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
    "web_search": {
        "tool_id": "web_search",
        "action_type": "tool_call",
        "input_keys": ["query"],
        "output": {
            "results": [
                {
                    "title": "Mock Search Result",
                    "url": "https://example.com",
                    "snippet": "Mock snippet for query",
                }
            ]
        },
    },
    "pdf_parser": {
        "tool_id": "pdf_parser",
        "action_type": "tool_call",
        "input_keys": ["file_path"],
        "output": {"text": "[MOCK] Parsed PDF content placeholder", "pages": 5},
    },
}

DETERMINISTIC_PATTERNS = [
    r"query_order|get_status|read_file|calculate|get_profile",
]

SEMI_DETERMINISTIC_PATTERNS = [
    r"route_to|select_tool|classify|choose",
]

NON_DETERMINISTIC_PATTERNS = [
    r"generate|creative|summarize|reason|write|compose|draft",
]


def classify_task(task_description):
    for pattern in DETERMINISTIC_PATTERNS:
        if re.search(pattern, task_description, re.IGNORECASE):
            return "deterministic"
    for pattern in SEMI_DETERMINISTIC_PATTERNS:
        if re.search(pattern, task_description, re.IGNORECASE):
            return "semi_deterministic"
    for pattern in NON_DETERMINISTIC_PATTERNS:
        if re.search(pattern, task_description, re.IGNORECASE):
            return "non_deterministic"
    return "deterministic"


def find_matching_tool(task_description):
    for tool_id, tool_def in MOCK_RESPONSES.items():
        if re.search(re.escape(tool_id), task_description, re.IGNORECASE):
            return tool_id, tool_def
    for pattern in DETERMINISTIC_PATTERNS + SEMI_DETERMINISTIC_PATTERNS:
        match = re.search(pattern, task_description, re.IGNORECASE)
        if match:
            tool_name = match.group(0).split("|")[0]
            if tool_name in MOCK_RESPONSES:
                return tool_name, MOCK_RESPONSES[tool_name]
    return None, None


def generate_mock_trajectory(task_description, agent_card=None, policy=None):
    task_type = classify_task(task_description)
    tool_id, tool_def = find_matching_tool(task_description)

    trace_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    events = []

    events.append(
        {
            "trace_id": trace_id,
            "standard_version": "MAS-TS-001-v3.0",
            "run_mode": "fast-screen",
            "timestamp": now,
            "event_type": "task_start",
            "sequence": 1,
            "task": {
                "task_id": f"mock-task-{trace_id[:8]}",
                "description": task_description,
                "complexity": "simple" if task_type == "deterministic" else "medium",
                "mock_classification": task_type,
            },
            "agent": {
                "agent_id": agent_card.get(
                    "agent_id", "urn:agent:mock:default:mock-agent"
                )
                if agent_card
                else "urn:agent:mock:default:mock-agent",
                "role": "worker",
                "card_version": "1.1",
                "data_residency": agent_card.get("compliance", {}).get(
                    "data_residency", "LOCAL"
                )
                if agent_card
                else "LOCAL",
                "model_backend": "mock-llm",
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

    if tool_def and task_type != "non_deterministic":
        mock_input = {}
        for key in tool_def.get("input_keys", []):
            mock_input[key] = f"mock_{key}_value"

        events.append(
            {
                "trace_id": trace_id,
                "standard_version": "MAS-TS-001-v3.0",
                "run_mode": "fast-screen",
                "timestamp": now,
                "event_type": "agent_action",
                "sequence": 2,
                "task": events[0]["task"],
                "agent": events[0]["agent"],
                "action": {
                    "type": "tool_call",
                    "tool_id": tool_id,
                    "input": mock_input,
                    "output": tool_def["output"],
                    "latency_ms": 10,
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

        events.append(
            {
                "trace_id": trace_id,
                "standard_version": "MAS-TS-001-v3.0",
                "run_mode": "fast-screen",
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
    elif task_type == "non_deterministic":
        events.append(
            {
                "trace_id": trace_id,
                "standard_version": "MAS-TS-001-v3.0",
                "run_mode": "fast-screen",
                "timestamp": now,
                "event_type": "agent_action",
                "sequence": 2,
                "task": events[0]["task"],
                "agent": events[0]["agent"],
                "action": {
                    "type": "need_clarification",
                    "reason": "Non-deterministic task requires real LLM, skipped in Fast-Screen mode",
                },
                "state_delta": {},
                "orchestration": {
                    "routing_decision": "fallback",
                    "routing_reason": "non_deterministic_task",
                },
                "error": None,
                "recovery": None,
            }
        )
    else:
        events.append(
            {
                "trace_id": trace_id,
                "standard_version": "MAS-TS-001-v3.0",
                "run_mode": "fast-screen",
                "timestamp": now,
                "event_type": "agent_action",
                "sequence": 2,
                "task": events[0]["task"],
                "agent": events[0]["agent"],
                "action": {
                    "type": "need_clarification",
                    "reason": f"Unknown task pattern, no matching mock rule for: {task_description}",
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
        "run_mode": "fast-screen",
        "task_description": task_description,
        "task_type": task_type,
        "matched_tool": tool_id,
        "cost_usd": 0.0,
        "events": events,
    }


def process_task_file(task_file, policy_path=None, output_dir=None):
    try:
        with open(task_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in task file %s: %s", task_file, e)
        sys.exit(1)

    policy = None
    if policy_path and Path(policy_path).exists():
        with open(policy_path, "r", encoding="utf-8") as f:
            policy = yaml.safe_load(f)

    results = []
    task_list = tasks if isinstance(tasks, list) else tasks.get("tasks", [tasks])

    for task_desc in task_list:
        if isinstance(task_desc, dict):
            task_desc = task_desc.get(
                "description", task_desc.get("task", str(task_desc))
            )
        result = generate_mock_trajectory(task_desc, policy=policy)
        results.append(result)

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        for result in results:
            task_id = result["trace_id"][:8]
            out_file = out_path / f"mock_{task_id}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

    return results


def main():
    parser = argparse.ArgumentParser(description="MAS-TS-001 Mock LLM Simulator")
    parser.add_argument(
        "--version", action="version", version=f"mas-eval-harness {VERSION}"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--task", help="Single task description")
    group.add_argument("--task-file", help="JSON file with task descriptions")
    parser.add_argument(
        "--policy", default="mock_policy.yaml", help="Mock policy YAML path"
    )
    parser.add_argument("--output", help="Save output to JSON file")
    parser.add_argument(
        "--output-dir", help="Save individual mock trajectories to directory"
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if args.task:
        result = generate_mock_trajectory(args.task)
        output = result
    else:
        results = process_task_file(args.task_file, args.policy, args.output_dir)
        output = {
            "standard": "MAS-TS-001",
            "version": "v3.0",
            "mode": "fast-screen",
            "total_tasks": len(results),
            "mocked_tasks": len([r for r in results if r["matched_tool"]]),
            "skipped_tasks": len([r for r in results if not r["matched_tool"]]),
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
