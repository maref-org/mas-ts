#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""
Compliance Sidecar - Runtime HTTP Request Interceptor
Usage: Set HTTP_PROXY=http://localhost:8080 before starting your Agent.

Intercepts all outbound HTTP requests and blocks cross-border requests
based on the Agent Card's declared data_residency.
"""
import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import argcomplete

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from mas_eval import __version__ as VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Domain -> Region mapping (local rule-based, no external API calls)
DOMAIN_REGION_MAP = {
    # US / Overseas
    "api.openai.com": "US",
    "api.anthropic.com": "US",
    "api.groq.com": "US",
    "api.together.xyz": "US",
    "api.openrouter.ai": "US",
    "api.gemini.google.com": "US",
    "api.mistral.ai": "EU",
    # CN / Domestic
    "dashscope.aliyuncs.com": "CN",
    "qianwen.aliyun.com": "CN",
    "api.baichuan-ai.com": "CN",
    "open.bigmodel.cn": "CN",
    "api.deepseek.com": "CN",
    "localhost": "LOCAL",
    "127.0.0.1": "LOCAL",
}

RESIDENCY_ALLOWED = {
    "CN": ["CN", "LOCAL"],
    "EU": ["EU", "LOCAL"],
    "SG": ["SG", "LOCAL"],
    "US": ["US", "LOCAL"],
    "LOCAL": ["LOCAL"],
}


class ComplianceSidecar:
    def __init__(self, agent_card_path):
        try:
            with open(agent_card_path, "r", encoding="utf-8") as f:
                card = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse agent card JSON: %s", e)
            sys.exit(1)
        self.residency = card.get("compliance", {}).get("data_residency", "UNKNOWN")
        self.allowed_regions = RESIDENCY_ALLOWED.get(self.residency, [self.residency, "LOCAL"])
        self.agent_name = card.get("name", "unknown-agent")

    def _resolve_region(self, domain):
        """Resolve domain to region using local rule base."""
        # Exact match
        if domain in DOMAIN_REGION_MAP:
            return DOMAIN_REGION_MAP[domain]
        # Suffix match
        for known_domain, region in DOMAIN_REGION_MAP.items():
            if domain.endswith(known_domain):
                return region
        return "UNKNOWN"

    def check_url(self, url):
        """Check if URL is allowed. Returns (allowed, reason)."""
        parsed = urlparse(url)
        domain = parsed.netloc
        if not domain:
            # Handle cases like localhost without scheme
            domain = url.split("/")[0].split(":")[0]

        region = self._resolve_region(domain)

        if region == "UNKNOWN":
            # Allow unknown domains but log warning
            return True, f"UNKNOWN domain {domain} allowed (please add to rule base)"

        if region not in self.allowed_regions:
            return (
                False,
                f"BLOCKED: Agent '{self.agent_name}' tried to access {domain} "
                f"(region={region}), but declared residency={self.residency} "
                f"only allows {self.allowed_regions}"
            )

        return True, f"ALLOWED: {domain} (region={region}) matches residency={self.residency}"

    async def alert(self, message):
        """Send alert. Override this to integrate with Slack/DingTalk/WeChat."""
        logger.warning("COMPLIANCE ALERT: %s", message)


# Simple HTTP proxy implementation for demonstration
async def handle_request(reader, writer, sidecar):
    """Handle a single HTTP CONNECT or plain HTTP request."""
    try:
        data = await reader.read(4096)
        if not data:
            return

        request_line = data.decode("utf-8", errors="replace").split("\r\n")[0]
        parts = request_line.split()

        if len(parts) >= 2:
            method = parts[0]
            target = parts[1]

            # For CONNECT proxy, target is hostname:port
            # For plain HTTP, target is a full URL
            if target.startswith("http://") or target.startswith("https://"):
                url = target
            else:
                url = f"http://{target}"

            allowed, reason = sidecar.check_url(url)

            if not allowed:
                await sidecar.alert(reason)
                writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                await writer.drain()
            else:
                # In production, forward the request here
                # For demo, return 200 OK
                writer.write(b"HTTP/1.1 200 OK\r\n\r\n")
                await writer.drain()
        else:
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            await writer.drain()
    except Exception as e:
        logger.error("Request handling error: %s", e)
    finally:
        writer.close()


async def run_server(host="127.0.0.1", port=8080, agent_card="agent_card.json"):
    sidecar = ComplianceSidecar(agent_card)
    logger.info("Loaded agent: %s", sidecar.agent_name)
    logger.info("Declared residency: %s", sidecar.residency)
    logger.info("Allowed regions: %s", sidecar.allowed_regions)
    logger.info("Listening on %s:%s", host, port)
    logger.info("Set HTTP_PROXY=http://%s:%s in your Agent environment", host, port)

    server = await asyncio.start_server(
        lambda r, w: handle_request(r, w, sidecar),
        host, port
    )
    async with server:
        await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Compliance Sidecar HTTP Proxy")
    parser.add_argument("--version", action="version", version=f"mas-eval-harness {VERSION}")
    parser.add_argument("--card", default="agent_card.json", help="Agent Card JSON path")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    try:
        asyncio.run(run_server(args.host, args.port, args.card))
    except KeyboardInterrupt:
        logger.info("Sidecar shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    main()
