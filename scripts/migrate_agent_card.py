#!/usr/bin/env python3
"""
MAS-TS-001 v3.0 → v4.0 Agent Card Migration Tool

Migrates v1.2 cards to v2.0 Federation format.

Usage:
    # Single card (in-place or to output)
    python scripts/migrate_agent_card.py --input card.json --output card_v2.json

    # Batch directory
    python scripts/migrate_agent_card.py --dir data/sample_cards/ --suffix _v2

    # Dry run
    python scripts/migrate_agent_card.py --dir data/multi_vendor_test/ --dry-run
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_vendor_id(agent_id):
    if agent_id.startswith("urn:agent:") and agent_id.count(":") >= 3:
        parts = agent_id.split(":")
        vendor_candidates = {
            "anthropic",
            "openai",
            "anysphere",
            "bytedance",
            "deepseek",
            "github",
        }
        for i, p in enumerate(parts):
            if p in vendor_candidates:
                return p
        # Fallback: use the first non-generic segment after "urn:agent:"
        for i, p in enumerate(parts):
            if i >= 2 and p not in ("agent", "agent") and "-" not in p:
                return p
        return parts[2]
    return "unknown"


def infer_agent_type(card):
    name = (card.get("name") or "").lower()
    desc = (card.get("description") or "").lower()
    if any(kw in name or kw in desc for kw in ("ide", "editor", "cursor", "trae")):
        return "ide"
    if any(kw in name or kw in desc for kw in ("daemon", "service", "server")):
        return "daemon"
    if any(kw in name or kw in desc for kw in ("api", "endpoint", "gateway")):
        return "api"
    return "cli"


def migrate_governance(old_gov):
    if old_gov is None:
        return None
    new_gov = {}
    if "state_machine_version" in old_gov:
        new_gov["state_machine_version"] = old_gov["state_machine_version"]
    cb = {}
    if "circuit_breaker_enabled" in old_gov:
        cb["enabled"] = old_gov["circuit_breaker_enabled"]
    if "circuit_breaker_threshold" in old_gov:
        cb["threshold"] = old_gov["circuit_breaker_threshold"]
    if "cooldown_seconds" in old_gov:
        cb["cooldown_seconds"] = old_gov["cooldown_seconds"]
    if "circuit_breaker" in old_gov and isinstance(old_gov["circuit_breaker"], dict):
        cb.update(old_gov["circuit_breaker"])
    if cb:
        new_gov["circuit_breaker"] = cb
    od = {}
    if "oscillation_detection_enabled" in old_gov:
        od["enabled"] = old_gov["oscillation_detection_enabled"]
    if "oscillation_detection" in old_gov and isinstance(
        old_gov["oscillation_detection"], dict
    ):
        od.update(old_gov["oscillation_detection"])
    if od:
        new_gov["oscillation_detection"] = od
    if "cost_model" in old_gov:
        new_gov["cost_model"] = old_gov["cost_model"]
    return new_gov if new_gov else None


def migrate_cross_border_policy(compliance):
    if not compliance:
        return None
    return {
        "data_residency": compliance.get("data_residency", "US"),
        "allowed_transfer_zones": [compliance.get("data_residency", "US")],
        "requires_approval": compliance.get("cross_border", False),
    }


def migrate_constitution(constitution, agent_id):
    if constitution is None:
        return {
            "envelope": {
                "message_id": f"{agent_id}-env-001",
                "correlation_id": f"{agent_id}-correlation-001",
                "timestamp": "2026-06-11T00:00:00Z",
                "sender": agent_id,
            },
            "health_state": "HEALTHY",
            "heartbeat_interval_seconds": 30,
            "stale_node_timeout_seconds": 60,
        }
    result = dict(constitution)
    env = dict(constitution.get("envelope", {}))
    old_env_keys = {"version", "jurisdiction", "protocol"}
    if old_env_keys & set(env.keys()):
        new_env = {
            "message_id": f"{agent_id}-env-001",
            "correlation_id": f"{agent_id}-correlation-001",
            "timestamp": "2026-06-11T00:00:00Z",
            "sender": agent_id,
        }
        env = new_env
    result["envelope"] = env
    if "health_state" in result and isinstance(result["health_state"], str):
        result["health_state"] = result["health_state"].upper()
        if result["health_state"] not in ("STARTING", "HEALTHY", "DEGRADED", "DEAD"):
            result["health_state"] = "HEALTHY"
    return result


def migrate_card(card):
    result = dict(card)

    if result.get("schema_version") == "2.0" and result.get("card_version") == "2.0":
        logger.debug("Already v2.0: %s", result.get("agent_id", "unknown"))
        return result

    result["card_version"] = "2.0"
    result["schema_version"] = "2.0"

    agent_id = result.get("agent_id", "urn:agent:unknown:migrated:v1")

    if "vendor_id" not in result:
        result["vendor_id"] = extract_vendor_id(agent_id)

    if "agent_type" not in result:
        result["agent_type"] = infer_agent_type(card)

    result["constitution"] = migrate_constitution(result.get("constitution"), agent_id)

    if "governance" in result and result["governance"] is not None:
        result["governance"] = migrate_governance(result["governance"])

    existing_fed = result.get("federation", {}) or {}
    fed = dict(existing_fed)
    if "role" not in fed:
        fed["role"] = "secondary"
    if "trust_score" not in fed:
        fed["trust_score"] = 0.5
    if "allowed_mcp_servers" not in fed:
        fed["allowed_mcp_servers"] = []
    if "cross_border_policy" not in fed:
        fed["cross_border_policy"] = migrate_cross_border_policy(
            result.get("compliance")
        )
    if "federation_protocols" not in fed:
        fed["federation_protocols"] = {
            "a2a": {"version": "0.3", "enabled": False},
            "mcp": {"version": "2025-03-26", "enabled": True},
        }
    result["federation"] = fed

    return result


def process_file(input_path, output_path=None, dry_run=False):
    input_path = Path(input_path)
    if not input_path.exists():
        logger.error("File not found: %s", input_path)
        return False
    try:
        card = json.loads(input_path.read_text())
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in %s: %s", input_path, e)
        return False

    migrated = migrate_card(card)
    size_diff = len(json.dumps(migrated, indent=2)) - len(json.dumps(card, indent=2))

    if dry_run:
        logger.info(
            "[DRY RUN] %s → v2.0 (vendor=%s, type=%s, +%d bytes)",
            input_path.name,
            migrated.get("vendor_id"),
            migrated.get("agent_type"),
            size_diff,
        )
        return True

    if output_path:
        output_path = Path(output_path)
    else:
        output_path = input_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(migrated, indent=2, ensure_ascii=False) + "\n")
    logger.info(
        "Migrated %s → %s (%d bytes)", input_path.name, output_path.name, size_diff
    )
    return True


def process_directory(input_dir, output_dir=None, suffix="_v2", dry_run=False):
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        logger.error("Directory not found: %s", input_dir)
        return False

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        logger.warning("No JSON files found in %s", input_dir)
        return False

    success = 0
    for fpath in json_files:
        if output_dir:
            out_path = Path(output_dir) / f"{fpath.stem}{suffix}.json"
        elif suffix:
            out_path = fpath.with_stem(f"{fpath.stem}{suffix}")
        else:
            out_path = fpath
        if process_file(fpath, out_path if not dry_run else None, dry_run=dry_run):
            success += 1

    logger.info("Processed %d/%d files in %s", success, len(json_files), input_dir)
    return success == len(json_files)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Agent Card v1.2 → v2.0 Federation format"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", "-i", help="Single input JSON file")
    group.add_argument("--dir", "-d", help="Directory of JSON files to migrate")
    parser.add_argument(
        "--output", "-o", help="Output file (with --input) or directory (with --dir)"
    )
    parser.add_argument(
        "--suffix", default="_v2", help="Suffix for migrated files (default: _v2)"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Show what would be migrated"
    )
    parser.add_argument("--in-place", action="store_true", help="Overwrite input files")
    args = parser.parse_args()

    if args.dry_run:
        logger.setLevel(logging.INFO)

    if args.input:
        out_path = args.output or (args.input if args.in_place else None)
        process_file(args.input, out_path, dry_run=args.dry_run)
    elif args.dir:
        out_dir = args.output if args.output and not args.in_place else None
        process_directory(
            args.dir,
            output_dir=out_dir,
            suffix="" if args.in_place else args.suffix,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
