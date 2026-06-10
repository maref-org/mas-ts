#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""
Compliance Auto-Guard - Static Agent Card Scanner (v2.0)
Usage:
  python compliance_scan.py --card agent_card.json --block
  python compliance_scan.py --dir ./agent_cards --block
  python compliance_scan.py --card agent_card.json --schema mas_eval/schemas/agent_card_v1.1.json

Scans Agent Card(s) for compliance violations:
- JSON Schema compliance (Agent Card v1.1)
- Missing data_residency / model_backend_location
- Cross-border mismatch (declared CN but endpoint is OpenAI)
- Fraudulent cross_border=false with mismatched locations
- Prompt rot detection (business_rule_version staleness)
- Batch directory scanning
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import argcomplete
from rich.console import Console
from rich.panel import Panel

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from mas_eval import __version__ as VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

console = Console()

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

SCHEMA_DIR = Path(__file__).parent / "mas_eval" / "schemas"
DEFAULT_SCHEMA = SCHEMA_DIR / "agent_card_v1.1.json"

ENDPOINT_REGION_DB = {}

ENDPOINT_YAML = Path(__file__).parent / "configs" / "endpoints.yaml"
if HAS_YAML and ENDPOINT_YAML.exists():
    try:
        with open(ENDPOINT_YAML, "r", encoding="utf-8") as f:
            ep_config = yaml.safe_load(f)
        for region, domains in ep_config.get("regions", {}).items():
            for domain in domains:
                ENDPOINT_REGION_DB[domain] = region
        logger.info(
            "Loaded %d endpoint regions from %s", len(ENDPOINT_REGION_DB), ENDPOINT_YAML
        )
    except Exception as e:
        logger.warning("Failed to load endpoint YAML, using defaults: %s", e)

if not ENDPOINT_REGION_DB:
    ENDPOINT_REGION_DB = {
        "api.openai.com": "US",
        "api.anthropic.com": "US",
        "api.groq.com": "US",
        "api.together.xyz": "US",
        "api.openrouter.ai": "US",
        "api.gemini.google.com": "US",
        "api.mistral.ai": "EU",
        "api.siliconflow.cn": "CN",
        "dashscope.aliyuncs.com": "CN",
        "qianwen.aliyun.com": "CN",
        "api.baichuan-ai.com": "CN",
        "open.bigmodel.cn": "CN",
        "api.deepseek.com": "CN",
        "api.minimax.chat": "CN",
        "api.moonshot.cn": "CN",
        "api.stepfun.com": "CN",
        "api.lingyiwanwu.com": "CN",
        "api.01.ai": "CN",
        "api.zhipuai.vip": "CN",
        "localhost": "LOCAL",
        "127.0.0.1": "LOCAL",
        "0.0.0.0": "LOCAL",
    }

OVERSEAS_PATTERNS = [
    r"api\.openai\.com",
    r"api\.anthropic\.com",
    r"api\.groq\.com",
    r"api\.together\.xyz",
    r"api\.openrouter\.ai",
    r"\.azure\.com",
    r"\.aws\.amazon\.com",
    r"api\.gemini\.google\.com",
    r"api\.mistral\.ai",
]

PROMPT_ROT_MAX_DAYS = 90


def resolve_endpoint_region(endpoint):
    if not endpoint:
        return "UNKNOWN"
    from urllib.parse import urlparse

    try:
        parsed = urlparse(endpoint)
        domain = parsed.netloc or endpoint.split("/")[0].split(":")[0]
        domain = domain.split(":")[0]
    except Exception:
        domain = endpoint.split("/")[0].split(":")[0]

    if domain in ENDPOINT_REGION_DB:
        return ENDPOINT_REGION_DB[domain]
    for known_domain, region in ENDPOINT_REGION_DB.items():
        if domain.endswith("." + known_domain) or domain.endswith(known_domain):
            return region
    return "UNKNOWN"


def check_endpoint_location(endpoint, declared_residency):
    if not endpoint:
        return False, "CRITICAL", "Endpoint is empty, cannot verify"

    if declared_residency in ["CN", "EU", "SG"]:
        for pattern in OVERSEAS_PATTERNS:
            if re.search(pattern, endpoint):
                return (
                    False,
                    "HIGH",
                    f"Declared residency={declared_residency}, but endpoint {endpoint} matches overseas model",
                )

    if declared_residency == "LOCAL":
        if not re.search(r"localhost|127\.0\.0\.1|0\.0\.0\.0", endpoint):
            return (
                False,
                "MEDIUM",
                f"Declared residency=LOCAL, but endpoint {endpoint} is not local",
            )

    actual_region = resolve_endpoint_region(endpoint)
    if actual_region != "UNKNOWN" and declared_residency not in [
        actual_region,
        "LOCAL",
    ]:
        if declared_residency != actual_region:
            return (
                False,
                "HIGH",
                f"Declared residency={declared_residency}, but endpoint resolves to region={actual_region}",
            )

    return True, "LOW", "Endpoint matches declared residency"


def check_prompt_rot(card):
    issues = []
    today = time.strftime("%Y-%m-%d")
    for cap in card.get("capabilities", []):
        brv = cap.get("business_rule_version")
        if not brv:
            issues.append(
                {
                    "level": "WARNING",
                    "msg": f"Skill '{cap.get('skill_id', '?')}' missing business_rule_version, prompt rot undetectable",
                }
            )
            continue
        try:
            from datetime import datetime

            brv_date = datetime.strptime(brv, "%Y-%m-%d")
            today_date = datetime.strptime(today, "%Y-%m-%d")
            age_days = (today_date - brv_date).days
            if age_days > PROMPT_ROT_MAX_DAYS:
                issues.append(
                    {
                        "level": "WARNING",
                        "msg": f"Skill '{cap.get('skill_id', '?')}' business_rule_version={brv} is {age_days} days old (>{PROMPT_ROT_MAX_DAYS}), prompt rot risk",
                    }
                )
        except ValueError:
            issues.append(
                {
                    "level": "WARNING",
                    "msg": f"Skill '{cap.get('skill_id', '?')}' business_rule_version='{brv}' is not YYYY-MM-DD format",
                }
            )
    return issues


def validate_schema(card, schema_path):
    if not HAS_JSONSCHEMA:
        return [
            {
                "level": "WARNING",
                "msg": "jsonschema library not installed, schema validation skipped",
            }
        ]
    if not schema_path or not os.path.exists(schema_path):
        return [{"level": "WARNING", "msg": f"Schema file not found: {schema_path}"}]

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except json.JSONDecodeError as e:
        return [{"level": "CRITICAL", "msg": f"Schema file is not valid JSON: {e}"}]

    issues = []
    validator = jsonschema.Draft7Validator(schema)
    for error in sorted(validator.iter_errors(card), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        issues.append(
            {"level": "CRITICAL", "msg": f"Schema violation at {path}: {error.message}"}
        )
    return issues


def scan_agent_card(card_path, schema_path=None):
    try:
        with open(card_path, "r", encoding="utf-8") as f:
            card = json.load(f)
    except json.JSONDecodeError as e:
        return [{"level": "CRITICAL", "msg": f"Agent Card file is not valid JSON: {e}"}]

    issues = []

    if schema_path:
        issues.extend(validate_schema(card, schema_path))

    residency = card.get("compliance", {}).get("data_residency")
    if not residency:
        issues.append({"level": "CRITICAL", "msg": "Missing data_residency field"})

    backend_loc = card.get("compliance", {}).get("model_backend_location")
    if not backend_loc:
        issues.append(
            {"level": "CRITICAL", "msg": "Missing model_backend_location field"}
        )

    if residency and backend_loc and residency != backend_loc:
        issues.append(
            {
                "level": "HIGH",
                "msg": f"data_residency({residency}) != model_backend_location({backend_loc}), cross-border risk",
            }
        )

    endpoint = card.get("model_backend", {}).get("endpoint", "")
    if residency:
        compliant, risk, reason = check_endpoint_location(endpoint, residency)
        if not compliant:
            issues.append({"level": risk, "msg": reason})

    cross_border = card.get("compliance", {}).get("cross_border")
    if cross_border is False and residency and backend_loc and residency != backend_loc:
        issues.append(
            {
                "level": "CRITICAL",
                "msg": "cross_border=false but residency != backend_location, fraudulent declaration",
            }
        )

    if not card.get("capabilities"):
        issues.append({"level": "CRITICAL", "msg": "No capabilities declared"})

    issues.extend(check_prompt_rot(card))

    return issues


def scan_directory(dir_path, schema_path=None):
    results = []
    dir_p = Path(dir_path)
    for card_file in sorted(dir_p.glob("*.json")):
        try:
            issues = scan_agent_card(str(card_file), schema_path)
            results.append(
                {
                    "card": str(card_file),
                    "issues": issues,
                    "passed": len(
                        [i for i in issues if i["level"] in ["CRITICAL", "HIGH"]]
                    )
                    == 0,
                }
            )
        except Exception as e:
            results.append(
                {
                    "card": str(card_file),
                    "issues": [{"level": "CRITICAL", "msg": f"Failed to parse: {e}"}],
                    "passed": False,
                }
            )
    return results


def main():
    parser = argparse.ArgumentParser(
        description="MAS-TS-001 Compliance Auto-Guard Scanner v2.0"
    )
    parser.add_argument(
        "--version", action="version", version=f"mas-eval-harness {VERSION}"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--card", help="Single Agent Card JSON path")
    group.add_argument("--dir", help="Directory of Agent Card JSONs to batch scan")
    parser.add_argument(
        "--schema", default=str(DEFAULT_SCHEMA), help="Agent Card JSON Schema path"
    )
    parser.add_argument(
        "--block", action="store_true", help="Exit with error on HIGH/CRITICAL issues"
    )
    parser.add_argument(
        "--no-schema", action="store_true", help="Skip JSON Schema validation"
    )
    parser.add_argument("--output", help="Save report to JSON file")
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    schema_path = None if args.no_schema else args.schema
    scanned_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if args.card:
        issues = scan_agent_card(args.card, schema_path)
        passed = len([i for i in issues if i["level"] in ["CRITICAL", "HIGH"]]) == 0
        report = {
            "standard": "MAS-TS-001",
            "version": "v3.0",
            "scanned_at": scanned_at,
            "mode": "single",
            "results": [{"card": args.card, "issues": issues, "passed": passed}],
            "overall_passed": passed,
        }
    else:
        results = scan_directory(args.dir, schema_path)
        report = {
            "standard": "MAS-TS-001",
            "version": "v3.0",
            "scanned_at": scanned_at,
            "mode": "batch",
            "results": results,
            "overall_passed": all(r["passed"] for r in results),
        }

    color = "green" if report["overall_passed"] else "red"
    console.print(
        Panel.fit(
            f"[bold {color}]Overall: {'✅ PASS' if report['overall_passed'] else '❌ FAIL'}[/]",
            border_style=color,
        )
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info("Report saved to %s", args.output)

    if not report["overall_passed"] and args.block:
        logger.error("Compliance check FAILED. Build/release blocked.")
        sys.exit(1)
    elif not report["overall_passed"]:
        logger.warning("Compliance issues found. Please fix.")
        sys.exit(0)
    else:
        logger.info("Compliance check passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
