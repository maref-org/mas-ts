#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Compliance Sidecar v2 — Runtime HTTP Request Interceptor with Content Audit

Extends v1 (domain-level cross-border check) with request body content audit:

  1. JSON body parser — extracts messages[] array
  2. System prompt audit — reuses d4_steganography_audit logic
  3. Unicode character-level detection — apostrophe variants, homoglyphs
  4. Date format consistency — detects 2026/07/06 vs 2026-07-06 in body
  5. HMAC audit chain — all decisions logged with tamper-evident chain

Audit levels:
  - off:     no audit (passthrough)
  - domain:  v1 behavior (cross-border domain block only)
  - content: v2 default (domain + content CRITICAL block)
  - strict:  v2 strict  (domain + any content finding blocks)

Usage:
  Set HTTP_PROXY=http://localhost:8080 before starting your Agent.
  python compliance_sidecar_v2.py --card agent_card.json --port 8080 \
      --audit-level content

Inspired by Claude Code 2026-06-30 incident — backdoor was invisible at
network layer (no separate telemetry), only detectable via request body
content audit.
"""

import argparse
import asyncio
import copy
import hashlib
import hmac
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import argcomplete

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from mas_eval import __version__ as VERSION
from mas_eval.domains.d4_injection_detection import (
    DIRECT_INJECTION_VECTORS,
    INDIRECT_INJECTION_VECTORS,
    JAILBREAK_VECTORS,
)
from mas_eval.domains.d4_steganography_audit import (
    SUSPICIOUS_PROMPT_PATTERNS,
    _count_unicode_variants,
    _detect_homoglyph_mixing,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("sidecar-v2")

# === Domain → Region mapping (inherited from v1) ===
DOMAIN_REGION_MAP = {
    "api.openai.com": "US",
    "api.anthropic.com": "US",
    "api.groq.com": "US",
    "api.together.xyz": "US",
    "api.openrouter.ai": "US",
    "api.gemini.google.com": "US",
    "api.mistral.ai": "EU",
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

# === Content audit configuration ===
MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB
AUDIT_LEVELS = {"off", "domain", "content", "strict"}

# Direct Unicode chars for pattern construction (cf. Phase 1 fixes:
# raw strings with \u escapes are unreliable across re versions).
_APOS_VARIANTS = "'’ʼʹ"  # U+0027, U+2019, U+02BC, U+02B9
_NON_ASCII_APOS = "ʼʹ’′՚ߴ＇"  # U+02BC, U+02B9, U+2019, U+2032, U+055A, U+07F4, U+FF07


class HMACAuditChain:
    """Tamper-evident audit chain for sidecar decisions.

    Each entry is linked to the previous entry's hash, forming a chain
    that cannot be modified without detection. Uses HMAC-SHA256.
    """

    def __init__(self, secret: Optional[str] = None) -> None:
        if secret is None:
            secret = os.environ.get("MAS_EVAL_HMAC_SECRET")
        if not secret:
            raise ValueError(
                "HMAC secret must be provided via argument or MAS_EVAL_HMAC_SECRET "
                "environment variable. In production, use a cryptographically secure "
                "random secret."
            )
        self.secret = secret.encode("utf-8")
        self.chain: list[dict[str, Any]] = []
        self.previous_hash = "GENESIS"

    def add_entry(self, decision: dict[str, Any]) -> str:
        """Add a decision to the audit chain. Returns entry hash.

        Note: decision is deep-copied so later mutations by the caller
        (e.g., adding audit_hash to the decision dict) do not invalidate
        the chain entry.
        """
        entry: dict[str, Any] = {
            "timestamp": time.time(),
            "previous_hash": self.previous_hash,
            "decision": copy.deepcopy(decision),
        }
        entry_json = json.dumps(entry, sort_keys=True, default=str)
        entry_hash = hmac.new(
            self.secret, entry_json.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        entry["hash"] = entry_hash
        self.chain.append(entry)
        self.previous_hash = entry_hash
        return entry_hash

    def verify_chain(self) -> bool:
        """Verify the integrity of the audit chain.

        Returns True if all entries are properly linked and hashes match.
        """
        prev = "GENESIS"
        for entry in self.chain:
            if entry["previous_hash"] != prev:
                return False
            entry_copy = {k: v for k, v in entry.items() if k != "hash"}
            entry_json = json.dumps(entry_copy, sort_keys=True, default=str)
            expected_hash = hmac.new(
                self.secret, entry_json.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            if entry["hash"] != expected_hash:
                return False
            prev = entry["hash"]
        return True

    def export(self) -> list[dict[str, Any]]:
        """Export chain for persistence."""
        return self.chain


class InjectionScanner:
    """Scan request body text for Prompt-Injection patterns at runtime (v0.8.2).

    Reuses the static vector library from d4_injection_detection (Phase 1) but
    applies an INDEPENDENT severity model tuned for live traffic: a pattern hit
    in an actual request body is direct evidence of an injection attempt, so
    direct/jailbreak vectors are CRITICAL (block in content mode) and indirect
    vectors are HIGH (block only in strict mode). Findings carry
    root_cause="prompt_injection" so they flow through upgrade_findings_to_v2
    with correct attribution.

    FP risk: patterns like "ignore previous instructions" may legitimately
    appear in user-edited prompts. Mitigated by reserving content-mode blocks
    for CRITICAL only; a future allowlist escape hatch is reserved.
    """

    _VECTOR_GROUPS = (
        (DIRECT_INJECTION_VECTORS, "CRITICAL", "runtime_injection_direct"),
        (JAILBREAK_VECTORS, "CRITICAL", "runtime_injection_jailbreak"),
        (INDIRECT_INJECTION_VECTORS, "HIGH", "runtime_injection_indirect"),
    )

    def __init__(self) -> None:
        self._compiled: list[tuple[Any, str, str, str]] = []
        for vectors, severity, cat in self._VECTOR_GROUPS:
            for v in vectors:
                pattern = v.get("pattern", "")
                if not pattern:
                    continue
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                except re.error:
                    continue
                self._compiled.append((compiled, severity, cat, v.get("id", "")))

    def scan(self, text: str) -> list[dict[str, Any]]:
        """Return injection findings for any vector pattern hit in ``text``."""
        results: list[dict[str, Any]] = []
        if not text:
            return results
        seen: set[tuple[str, str]] = set()
        for compiled, severity, category, vid in self._compiled:
            match = compiled.search(text)
            if match is None:
                continue
            key = (category, match.group(0))
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "severity": severity,
                    "category": category,
                    "detail": (
                        f"Runtime injection pattern matched in request body: "
                        f"{vid} {match.group(0)!r}"
                    ),
                    "root_cause": "prompt_injection",
                }
            )
        return results


class ContentAuditor:
    """Audit HTTP request body for steganographic backdoor markers.

    Reuses detection logic from d4_steganography_audit to scan request
    body content (messages[].content, system field, prompt field) for:
      - Unicode apostrophe variant characters
      - "Today's date is YYYY/MM/DD" steganography pattern
      - Non-ASCII apostrophe in "Today's" context
      - Suspicious prompt patterns (timezone, base_url, etc.)
      - Homoglyph mixing (ASCII + Cyrillic)
    """

    def __init__(self, audit_level: str = "content") -> None:
        if audit_level not in AUDIT_LEVELS:
            raise ValueError(f"Invalid audit_level: {audit_level}")
        self.audit_level = audit_level
        self.injection_scanner = InjectionScanner()

    def audit_body(self, body: bytes, url: str) -> dict[str, Any]:
        """Audit request body. Returns {allowed, findings, score}.

        - off/domain: no content audit, always allowed
        - content: blocks on CRITICAL findings
        - strict: blocks on ANY finding
        """
        if self.audit_level in ("off", "domain"):
            return {"allowed": True, "findings": [], "score": 100.0}

        findings: list[dict[str, Any]] = []
        score = 100.0

        # Parse JSON body
        try:
            body_str = body.decode("utf-8", errors="replace")
            body_json = json.loads(body_str)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Not JSON — skip content audit
            return {"allowed": True, "findings": [], "score": 100.0}
        except Exception:
            # body_json might be a non-dict JSON value (list, str, etc.)
            return {"allowed": True, "findings": [], "score": 100.0}

        if not isinstance(body_json, dict):
            return {"allowed": True, "findings": [], "score": 100.0}

        # Extract all text from body (messages[].content, system field, etc.)
        text_content = self._extract_text(body_json)
        if not text_content:
            return {"allowed": True, "findings": [], "score": 100.0}

        # Check 1: Unicode variant characters (multiple variants = strong signal)
        variant_counts = _count_unicode_variants(text_content)
        if len(variant_counts) >= 2:
            score -= 40
            variants_str = ", ".join(
                f"U+{ord(c):04X} (×{n})" for c, n in variant_counts.items()
            )
            findings.append(
                {
                    "severity": "CRITICAL",
                    "category": "body_unicode_multi_variant",
                    "detail": (
                        f"Multiple Unicode apostrophe variants in request body: "
                        f"{variants_str} — potential steganographic marker"
                    ),
                }
            )

        # Check 2: Non-ASCII apostrophe in "Today" context
        # Matches "Todayʼs date", "Todayʹs date", "Today’s date", etc.
        # (Claude Code backdoor 'hit type' encoding pattern)
        today_non_ascii = re.compile(
            "Today[" + _NON_ASCII_APOS + "]s?\\s*date",
            re.IGNORECASE,
        )
        if today_non_ascii.search(text_content):
            score -= 35
            findings.append(
                {
                    "severity": "CRITICAL",
                    "category": "body_today_apostrophe_variant",
                    "detail": (
                        "Request body contains 'Today' + non-ASCII apostrophe — "
                        "exact match for Claude Code 2026-06-30 backdoor pattern"
                    ),
                }
            )

        # Check 3: Slash-format date in "Today's date is" context
        # (Claude Code backdoor steganography: 2026/06/30 vs ISO 2026-06-30)
        today_slash = re.compile(
            "Today[" + _APOS_VARIANTS + "]?s?\\s*date\\s+is\\s+\\d{4}/\\d{2}/\\d{2}",
            re.IGNORECASE,
        )
        if today_slash.search(text_content):
            score -= 40
            findings.append(
                {
                    "severity": "CRITICAL",
                    "category": "body_today_slash_date",
                    "detail": (
                        "Request body contains 'Today's date is YYYY/MM/DD' — "
                        "exact match for Claude Code backdoor steganography"
                    ),
                }
            )

        # Check 4: Suspicious prompt patterns (timezone, base_url)
        suspicious_hits: list[str] = []
        for pattern in SUSPICIOUS_PROMPT_PATTERNS:
            if pattern.search(text_content):
                suspicious_hits.append(pattern.pattern)
        if len(suspicious_hits) >= 2:
            score -= 30
            findings.append(
                {
                    "severity": "CRITICAL",
                    "category": "body_suspicious_patterns",
                    "detail": (
                        f"Multiple suspicious patterns in body: {suspicious_hits} — "
                        f"potential covert detection logic"
                    ),
                }
            )
        elif len(suspicious_hits) == 1:
            score -= 15
            findings.append(
                {
                    "severity": "HIGH",
                    "category": "body_suspicious_pattern",
                    "detail": (f"Suspicious pattern in body: {suspicious_hits[0]}"),
                }
            )

        # Check 5: Homoglyph mixing (ASCII + Cyrillic)
        homoglyphs = _detect_homoglyph_mixing(text_content)
        if homoglyphs:
            score -= 30
            findings.append(
                {
                    "severity": "CRITICAL",
                    "category": "body_homoglyph_mixing",
                    "detail": (
                        f"Mixed ASCII and variant homoglyphs in body: {homoglyphs}"
                    ),
                }
            )

        # Check 6: Prompt-injection patterns (runtime detection, v0.8.2).
        # Direct/jailbreak hits in a live request body are CRITICAL (block in
        # content mode); indirect hits are HIGH (block only in strict mode).
        injection_findings = self.injection_scanner.scan(text_content)
        for f in injection_findings:
            if f["severity"] == "CRITICAL":
                score -= 25
            else:  # HIGH
                score -= 10
        findings.extend(injection_findings)

        # Determine allowed based on audit level
        if self.audit_level == "strict":
            allowed = len(findings) == 0
        else:  # content mode
            allowed = not any(f["severity"] == "CRITICAL" for f in findings)

        score = max(0, min(100, score))
        return {"allowed": allowed, "findings": findings, "score": score}

    def _extract_text(self, body_json: dict) -> str:
        """Extract all text content from JSON body.

        Supports:
          - OpenAI/Anthropic format: messages[].content (str or multi-part)
          - Anthropic format: system field (str or list of {text})
          - Legacy format: prompt field
        """
        texts: list[str] = []

        # messages[].content
        messages = body_json.get("messages", [])
        if isinstance(messages, list):
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content", "")
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            text = part.get("text", "")
                            if isinstance(text, str):
                                texts.append(text)

        # system field (Anthropic format)
        system = body_json.get("system", "")
        if isinstance(system, str):
            texts.append(system)
        elif isinstance(system, list):
            for part in system:
                if isinstance(part, dict):
                    text = part.get("text", "")
                    if isinstance(text, str):
                        texts.append(text)

        # prompt field (legacy format)
        prompt = body_json.get("prompt", "")
        if isinstance(prompt, str):
            texts.append(prompt)

        return "\n".join(texts)


class ComplianceSidecarV2:
    """Sidecar v2 with domain-level + content-level audit.

    Combines v1 cross-border domain check with v2 request body content
    audit. All decisions are recorded in a tamper-evident HMAC audit chain.
    """

    def __init__(
        self,
        agent_card_path: str,
        audit_level: str = "content",
        audit_secret: Optional[str] = None,
    ) -> None:
        try:
            with open(agent_card_path, "r", encoding="utf-8") as f:
                card = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to parse agent card JSON: %s", e)
            sys.exit(1)

        self.residency = card.get("compliance", {}).get("data_residency", "UNKNOWN")
        self.allowed_regions = RESIDENCY_ALLOWED.get(
            self.residency, [self.residency, "LOCAL"]
        )
        self.agent_name = card.get("name", "unknown-agent")
        self.audit_level = audit_level
        self.auditor = ContentAuditor(audit_level=audit_level)
        self.audit_chain = HMACAuditChain(secret=audit_secret)

    def _resolve_region(self, domain: str) -> str:
        """Resolve domain to region using local rule base."""
        if domain in DOMAIN_REGION_MAP:
            return DOMAIN_REGION_MAP[domain]
        for known_domain, region in DOMAIN_REGION_MAP.items():
            if domain.endswith(known_domain):
                return region
        return "UNKNOWN"

    def check_url(self, url: str) -> tuple[bool, str, str]:
        """Check URL at domain level. Returns (allowed, reason, region)."""
        parsed = urlparse(url)
        domain = parsed.netloc
        if not domain:
            domain = url.split("/")[0].split(":")[0]

        region = self._resolve_region(domain)

        if region == "UNKNOWN":
            return (
                True,
                f"UNKNOWN domain {domain} allowed (add to rule base)",
                region,
            )

        if region not in self.allowed_regions:
            return (
                False,
                f"BLOCKED: Agent '{self.agent_name}' tried to access {domain} "
                f"(region={region}), but declared residency={self.residency} "
                f"only allows {self.allowed_regions}",
                region,
            )

        return (
            True,
            f"ALLOWED: {domain} (region={region}) matches residency={self.residency}",
            region,
        )

    def check_request(self, url: str, body: bytes) -> dict[str, Any]:
        """Full request check: domain + content. Returns decision dict.

        The decision is recorded in the HMAC audit chain and includes
        the entry hash for traceability.
        """
        # Step 1: Domain-level check
        domain_allowed, domain_reason, region = self.check_url(url)

        # Step 2: Content-level audit (only if domain allowed and level requires)
        content_result: dict = {"allowed": True, "findings": [], "score": 100.0}
        if domain_allowed and self.audit_level in ("content", "strict"):
            content_result = self.auditor.audit_body(body, url)

        # Step 3: Aggregate decision
        allowed = domain_allowed and content_result["allowed"]
        all_findings: list[dict] = []
        if not domain_allowed:
            all_findings.append(
                {
                    "severity": "CRITICAL",
                    "category": "cross_border_violation",
                    "detail": domain_reason,
                }
            )
        all_findings.extend(content_result["findings"])

        decision = {
            "timestamp": time.time(),
            "agent": self.agent_name,
            "url": url,
            "region": region,
            "domain_allowed": domain_allowed,
            "content_score": content_result["score"],
            "allowed": allowed,
            "findings": all_findings,
            "audit_level": self.audit_level,
        }

        # Record in HMAC audit chain
        entry_hash = self.audit_chain.add_entry(decision)
        decision["audit_hash"] = entry_hash

        return decision

    async def alert(self, message: str) -> None:
        """Send alert. Override to integrate with Slack/DingTalk/WeChat."""
        logger.warning("COMPLIANCE ALERT: %s", message)


async def handle_request_v2(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    sidecar: "ComplianceSidecarV2",
) -> None:
    """Handle a single HTTP request with content audit."""
    try:
        data = await reader.read(MAX_BODY_SIZE)
        if not data:
            return

        # Parse request line and headers
        request_text = data.decode("utf-8", errors="replace")
        lines = request_text.split("\r\n")
        request_line = lines[0] if lines else ""
        parts = request_line.split()

        if len(parts) < 2:
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            await writer.drain()
            return

        method = parts[0]
        target = parts[1]

        # Extract URL
        if target.startswith("http://") or target.startswith("https://"):
            url = target
        else:
            # CONNECT proxy or relative path
            host_header = ""
            for line in lines[1:]:
                if line.lower().startswith("host:"):
                    host_header = line.split(":", 1)[1].strip()
                    break
            if host_header:
                url = f"http://{host_header}{target}"
            else:
                url = f"http://{target}"

        # Extract body (after \r\n\r\n)
        body = b""
        if "\r\n\r\n" in request_text:
            body_str = request_text.split("\r\n\r\n", 1)[1]
            body = body_str.encode("utf-8")

        # Run full check
        decision = sidecar.check_request(url, body)

        if not decision["allowed"]:
            reasons = "; ".join(f["category"] for f in decision["findings"])
            await sidecar.alert(
                f"BLOCKED {method} {url} — reasons: {reasons} "
                f"(audit_hash={decision['audit_hash'][:16]})"
            )
            response_body = json.dumps(
                {
                    "error": "blocked_by_compliance_sidecar",
                    "reasons": decision["findings"],
                    "audit_hash": decision["audit_hash"],
                },
                indent=2,
            )
            response = (
                f"HTTP/1.1 403 Forbidden\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                f"\r\n"
                f"{response_body}"
            )
            writer.write(response.encode("utf-8"))
        else:
            logger.info(
                "ALLOWED %s %s (content_score=%.1f, hash=%s)",
                method,
                url,
                decision["content_score"],
                decision["audit_hash"][:16],
            )
            # In production, forward the request here
            writer.write(b"HTTP/1.1 200 OK\r\n\r\n")

        await writer.drain()
    except Exception as e:
        logger.error("Request handling error: %s", e)
    finally:
        writer.close()


async def run_server_v2(
    host: str = "127.0.0.1",
    port: int = 8080,
    agent_card: str = "agent_card.json",
    audit_level: str = "content",
    audit_secret: Optional[str] = None,
) -> None:
    """Run the sidecar v2 HTTP proxy server."""
    sidecar = ComplianceSidecarV2(
        agent_card_path=agent_card,
        audit_level=audit_level,
        audit_secret=audit_secret,
    )
    logger.info("=== Compliance Sidecar v2 ===")
    logger.info("Loaded agent: %s", sidecar.agent_name)
    logger.info("Declared residency: %s", sidecar.residency)
    logger.info("Allowed regions: %s", sidecar.allowed_regions)
    logger.info("Audit level: %s", sidecar.audit_level)
    logger.info("Listening on %s:%s", host, port)
    logger.info("Set HTTP_PROXY=http://%s:%s in your Agent environment", host, port)

    server = await asyncio.start_server(
        lambda r, w: handle_request_v2(r, w, sidecar), host, port
    )
    async with server:
        await server.serve_forever()


def main() -> None:
    """CLI entry point for sidecar v2."""
    parser = argparse.ArgumentParser(
        description="Compliance Sidecar v2 — HTTP Proxy with Content Audit"
    )
    parser.add_argument(
        "--version", action="version", version=f"mas-eval-harness {VERSION}"
    )
    parser.add_argument(
        "--card", default="agent_card.json", help="Agent Card JSON path"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    parser.add_argument(
        "--audit-level",
        choices=sorted(AUDIT_LEVELS),
        default="content",
        help="Audit level: off (passthrough), domain (v1), content (v2 default), strict (v2)",
    )
    parser.add_argument(
        "--audit-secret",
        default=None,
        help="HMAC secret for audit chain. If not provided, reads from "
        "MAS_EVAL_HMAC_SECRET environment variable. Required for "
        "tamper-evident audit chain.",
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    try:
        asyncio.run(
            run_server_v2(
                args.host,
                args.port,
                args.card,
                args.audit_level,
                args.audit_secret,
            )
        )
    except KeyboardInterrupt:
        logger.info("Sidecar v2 shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    main()
