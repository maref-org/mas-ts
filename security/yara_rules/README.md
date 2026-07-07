# MAS-TS YARA Rules — Agent Binary/Source Steganography Scan

## Overview

YARA rule set for detecting steganographic backdoor patterns in agent
binaries and source code. Inspired by the Claude Code 2026-06-30 incident
where backdoor behaviors were hidden using Unicode steganography and date
format switching.

## Rule Categories

| Rule File | Severity | Target |
|---|---|---|
| `claude_code_backdoor.yar` | CRITICAL | Claude Code 2026-06-30 specific patterns |
| `unicode_steganography.yar` | HIGH | General Unicode variant character abuse |
| `domain_blacklists.yar` | HIGH | Hidden domain blacklists and proxy detection |
| `date_format_steganography.yar` | HIGH | Date format steganography patterns |

## Usage

### Command Line

```bash
# Scan agent binary/source against all rules
yara -r security/yara_rules/ /path/to/agent/

# Scan with specific rule file
yara -r security/yara_rules/claude_code_backdoor.yar /path/to/agent/

# Scan with verbose output
yara -r -s security/yara_rules/ /path/to/agent/
```

### Python Integration

```python
import subprocess
from pathlib import Path

def scan_agent_binary(agent_path: str) -> list[dict]:
    """Scan agent binary/source with YARA rules.

    Args:
        agent_path: Path to agent binary or source directory.

    Returns:
        List of findings, each with severity, category, detail.
    """
    rules_dir = Path(__file__).parent.parent / "security" / "yara_rules"
    result = subprocess.run(
        ["yara", "-r", str(rules_dir), agent_path],
        capture_output=True, text=True,
    )
    findings = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split(" ", 1)
            if len(parts) == 2:
                rule_name, file_path = parts
                findings.append({
                    "severity": "CRITICAL",
                    "category": f"yara_{rule_name}",
                    "detail": f"YARA rule {rule_name} matched in {file_path}",
                    "layer": "safety",
                    "root_cause": "binary_pattern_match",
                })
    return findings
```

## Rule Details

### claude_code_backdoor.yar

4 rules targeting the specific Claude Code 2026-06-30 backdoor:

1. **Claude_Code_Backdoor_DateFormat** — "Today's date is 2026/07/06" with slash separator
2. **Claude_Code_Backdoor_Apostrophe_Variant** — Non-ASCII apostrophe (U+02BC/U+02B9/U+2019) in "Today" context
3. **Claude_Code_Backdoor_Timezone_Detection** — Asia/Shanghai, Asia/Urumqi timezone references
4. **Claude_Code_Backdoor_CN_Domain_Blacklist** — 5+ Chinese company domain keywords

### unicode_steganography.yar

3 rules for general Unicode steganography:

1. **Unicode_Homoglyph_Mixing** — ASCII + Cyrillic homoglyphs in same file
2. **Unicode_Apostrophe_Variants** — 2+ different apostrophe variants
3. **Unicode_Normalization_Anomaly** — Excessive combining diacritical marks

### date_format_steganography.yar

4 rules for date format steganography:

1. **Date_Format_Slash_Variant** — YYYY/MM/DD format (Claude Code pattern)
2. **Date_Format_Mixed_Separator** — Mixed - and / in same date
3. **Date_Format_Dot_Variant** — DD.MM.YYYY European format
4. **Conditional_Date_Logic** — Conditional date format switching in code

### domain_blacklists.yar

3 rules for hidden blacklists:

1. **CN_Company_Blacklist_Pattern** — 5+ Chinese company keywords
2. **Domain_Block_Logic** — Domain blocking logic in source code
3. **Proxy_Detection_Logic** — Proxy/VPN detection (ANTHROPIC_BASE_URL, HTTP_PROXY)

## Requirements

- YARA 4.3+ (`brew install yara` or `apt install yara`)
- Optional: integrated as D4 sub-check in future MAS-TS version

## CI Integration

YARA scanning is integrated into `.github/workflows/security-scan.yml`
as an optional (non-blocking) job that scans sample agent cards and
test fixtures.

## Limitations

- YARA rules detect **patterns**, not **intent** — false positives possible
- Binary/compiled agents may require string extraction before scanning
- Encrypted/obfuscated backdoors may evade pattern matching
- Recommend combining with runtime Sidecar v2 content audit for defense-in-depth
