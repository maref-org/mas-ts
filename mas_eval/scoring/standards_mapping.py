# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS-001 v0.8.3 — External Standards Mapping Engine.

Phase 3 (L0 报告 §6.3): 为每个 Finding 产出跨框架标识，将 MAS-TS 内部
category 映射到三大外部安全标准，便于合规审计与跨评估器对标：

  - OWASP Agentic Top 10 (2026 draft) — Agent 安全风险 Top 10
  - MITRE ATLAS — Adversarial Threat Landscape for AI Systems
  - NIST SP 800-53 Rev 5 — RMF 安全控制族

设计决策 (D1): 采用前缀匹配而非逐条枚举 ~90 个 category。MAS-TS 的
category 命名高度聚类（如 ``direct_injection_*``、``sm_*``、``audit_*``），
前缀匹配覆盖率高且易维护。未命中具体前缀的 category 回退到默认标识并记入
``unmapped_categories``，便于后续补全。

不修改 Finding dataclass (D2) — 映射在报告层 (``gold_report.py``) 完成，
避免触及 70 个测试文件中的 Finding 构造点。

Usage:
    from mas_eval.scoring.standards_mapping import map_findings_to_standards
    report = map_findings_to_standards(findings)
    # report["summary"]["owasp_top_hit"] == "A04"
"""

from collections import Counter
from typing import Any

# ═══════════════════════════════════════════════════════════════════════
# 1. 参考字典（人类可读的标准标识 → 名称）
# ═══════════════════════════════════════════════════════════════════════

OWASP_AGENTIC_TOP_10: dict[str, str] = {
    "A01": "Agent Hijacking",
    "A02": "Tool Misuse",
    "A03": "Insecure Authentication / Privilege Escalation",
    "A04": "Prompt Injection",
    "A05": "Insecure Tool & Agent-to-Agent Communication",
    "A06": "Excessive Agency / Over-Permissioned",
    "A07": "Sensitive Information Disclosure / Data Leakage",
    "A08": "Data Poisoning / Training Data Integrity",
    "A09": "Supply Chain & Dependency",
    "A10": "Compliance & Governance Violation",
}

MITRE_ATLAS_TECHNIQUES: dict[str, str] = {
    "AML.T0040": "ML Data Inference",
    "AML.T0043": "Defense Evasion",
    "AML.T0048": "Supply Chain Compromise",
    "AML.T0050": "Execute ML Model",
    "AML.T0051": "LLM Prompt Injection",
}

NIST_RMF_CONTROLS: dict[str, str] = {
    "AC-3": "Access Enforcement",
    "AC-4": "Information Flow Enforcement",
    "AC-6": "Least Privilege",
    "AU-6": "Audit Record Review and Analysis",
    "AU-10": "Non-Repudiation",
    "CA-8": "Penetration Testing",
    "CP-9": "System Backup",
    "IA-2": "Identification and Authentication",
    "PT-7": "Data Residency / Privacy",
    "RA-5": "Vulnerability Monitoring and Scanning",
    "SC-8": "Transmission Integrity",
    "SI-3": "Malicious Code Protection",
    "SI-7": "Software, Firmware, and Information Integrity",
    "SI-10": "Information Input Validation",
    "SR-3": "Supply Chain Risk Management",
    "SR-5": "Acquisition Strategies and Methods",
}

# ═══════════════════════════════════════════════════════════════════════
# 2. 前缀映射表（按顺序匹配，首命中返回）
#    每张表为 list[tuple[prefix, [standard_ids]]]；category.startswith(prefix)
#    命中即返回对应 IDs。未命中任何前缀 → 使用 _DEFAULT_* fallback。
# ═══════════════════════════════════════════════════════════════════════

OWASP_AGENTIC_MAP: list[tuple[str, list[str]]] = [
    # 注入类 → A04 (Prompt Injection)
    ("direct_injection_", ["A04"]),
    ("indirect_injection_", ["A04"]),
    ("jailbreak_", ["A04"]),
    ("runtime_injection_", ["A04"]),
    ("false_positive_risk_", ["A04"]),
    ("prompt_steg", ["A04"]),
    # A2A / 工具通信类 → A05
    ("cross_agent_injection_", ["A05"]),
    ("delegation_spoof_", ["A05"]),
    ("coordination_attack_", ["A05"]),
    ("protocol_hardening_", ["A05"]),
    # 工具误用 → A02
    ("tool_scope_", ["A02"]),
    ("tool_visibility_", ["A02"]),
    # 数据泄漏 → A07
    ("covert_collection_", ["A07"]),
    ("hidden_channels_", ["A07"]),
    # 过度授权 / 未声明网络访问 → A06
    ("undeclared_network_access", ["A06"]),
    ("runtime_cross_border_", ["A06"]),
    ("cross_border_violation", ["A06"]),
    # 隐写 / 数据投毒 → A08
    ("unicode_", ["A08"]),
    ("steganography_", ["A08"]),
    ("runtime_steganography_", ["A08"]),
    # 供应链 → A09
    ("trust_", ["A09"]),
    ("gossip_", ["A09"]),
    ("vendor_diversity", ["A09"]),
    ("mcp_supply_chain", ["A09"]),
    # 鉴权 / 提权 → A03
    ("pentest_", ["A03"]),
    # 治理 / 合规 → A10
    ("sm_", ["A10"]),
    ("cb_", ["A10"]),
    ("osc_", ["A10"]),
    ("audit_", ["A10"]),
    ("rb_", ["A10"]),
    ("capability_declaration_incomplete", ["A10"]),
    ("empty_agent_card", ["A10"]),
]

MITRE_ATLAS_MAP: list[tuple[str, list[str]]] = [
    # 注入类 → AML.T0051
    ("direct_injection_", ["AML.T0051"]),
    ("indirect_injection_", ["AML.T0051"]),
    ("jailbreak_", ["AML.T0051"]),
    ("runtime_injection_", ["AML.T0051"]),
    ("false_positive_risk_", ["AML.T0051"]),
    # 隐写 / 防御规避 → AML.T0043
    ("unicode_", ["AML.T0043"]),
    ("steganography_", ["AML.T0043"]),
    ("runtime_steganography_", ["AML.T0043"]),
    # 供应链 → AML.T0048
    ("vendor_diversity", ["AML.T0048"]),
    ("mcp_supply_chain", ["AML.T0048"]),
    ("trust_", ["AML.T0048"]),
    ("gossip_", ["AML.T0048"]),
    # 数据推理 / 隐蔽收集 → AML.T0040
    ("covert_collection_", ["AML.T0040"]),
    ("hidden_channels_", ["AML.T0040"]),
    # 工具执行 → AML.T0050
    ("tool_scope_", ["AML.T0050"]),
    ("tool_visibility_", ["AML.T0050"]),
    # A2A / 治理 → AML.T0051 (cross-agent injection 复用 prompt injection 技术)
    ("cross_agent_injection_", ["AML.T0051"]),
    ("delegation_spoof_", ["AML.T0051"]),
    ("coordination_attack_", ["AML.T0051"]),
]

NIST_RMF_MAP: list[tuple[str, list[str]]] = [
    # 注入类 → SI-10 (输入校验) + SI-3 (恶意代码)
    ("direct_injection_", ["SI-10", "SI-3"]),
    ("indirect_injection_", ["SI-10", "SI-3"]),
    ("jailbreak_", ["SI-10", "SI-3"]),
    ("runtime_injection_", ["SI-10", "SI-3"]),
    ("false_positive_risk_", ["SI-10"]),
    # 数据泄漏 → SC-8 (传输完整性) + AC-4 (信息流)
    ("covert_collection_", ["SC-8", "AC-4"]),
    ("hidden_channels_", ["SC-8", "AC-4"]),
    # 隐写 → SI-7 (软件/固件完整性)
    ("unicode_", ["SI-7"]),
    ("steganography_", ["SI-7"]),
    ("runtime_steganography_", ["SI-7"]),
    # 治理 / 审计 → AU-6 + AU-10
    ("sm_", ["AU-6", "AU-10"]),
    ("cb_", ["AU-6", "AU-10"]),
    ("osc_", ["AU-6"]),
    ("audit_", ["AU-6", "AU-10"]),
    ("rb_", ["AU-6", "CP-9"]),
    # 供应链 → SR-3 + SR-5
    ("trust_", ["SR-3"]),
    ("gossip_", ["SR-3", "IA-2"]),
    ("vendor_diversity", ["SR-3", "SR-5"]),
    ("mcp_supply_chain", ["SR-3", "SR-5"]),
    # 工具范围 / 最小权限 → AC-3 + AC-6
    ("tool_scope_", ["AC-3", "AC-6"]),
    ("tool_visibility_", ["AC-3", "AC-6"]),
    ("cross_agent_injection_", ["AC-3", "IA-2"]),
    ("delegation_spoof_", ["AC-3", "IA-2"]),
    ("coordination_attack_", ["AC-3", "AC-4"]),
    ("protocol_hardening_", ["SC-8"]),
    # 跨境 / 数据驻留 → AC-4 + PT-7
    ("undeclared_network_access", ["AC-3", "AC-4"]),
    ("runtime_cross_border_", ["AC-4", "PT-7"]),
    ("cross_border_violation", ["AC-4", "PT-7"]),
    # 渗透测试 → CA-8 + RA-5
    ("pentest_", ["CA-8", "RA-5"]),
    # 声明合规 → AU-6
    ("capability_declaration_incomplete", ["AU-6"]),
    ("empty_agent_card", ["AU-6"]),
]

# Fallback 标识（未命中任何具体前缀时使用）
_DEFAULT_OWASP = ["A10"]
_DEFAULT_ATLAS = ["AML.T0051"]
_DEFAULT_NIST = ["SI-10"]


# ═══════════════════════════════════════════════════════════════════════
# 3. 核心函数
# ═══════════════════════════════════════════════════════════════════════


def _match_prefix(
    category: str,
    table: list[tuple[str, list[str]]],
    fallback: list[str],
) -> tuple[list[str], bool]:
    """Return (standard_ids, matched) for a category against a prefix table.

    ``matched`` is True when a specific prefix hit occurred, False when the
    fallback was used (so callers can track unmapped categories).
    """
    for prefix, ids in table:
        if category.startswith(prefix):
            return list(ids), True
    return list(fallback), False


def map_category_to_standards(category: str) -> dict[str, list[str]]:
    """Map a single MAS-TS finding category to three external frameworks.

    Args:
        category: MAS-TS finding ``category`` string (e.g.
            ``"direct_injection_critical"``).

    Returns:
        Dict with keys ``"owasp"`` / ``"mitre_atlas"`` / ``"nist_rmf"``, each
        mapping to a list of standard identifiers. Unknown categories fall
        back to a sensible default per framework.
    """
    owasp, _ = _match_prefix(category, OWASP_AGENTIC_MAP, _DEFAULT_OWASP)
    atlas, _ = _match_prefix(category, MITRE_ATLAS_MAP, _DEFAULT_ATLAS)
    nist, _ = _match_prefix(category, NIST_RMF_MAP, _DEFAULT_NIST)
    return {"owasp": owasp, "mitre_atlas": atlas, "nist_rmf": nist}


def map_findings_to_standards(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate cross-framework mappings for a list of findings.

    For each finding the ``category`` is mapped to OWASP Agentic / MITRE ATLAS
    / NIST RMF identifiers via prefix matching. The result aggregates per-
    framework coverage counts, tracks categories that fell through to the
    default fallback, and reports the most-hit identifier per framework.

    Args:
        findings: List of finding dicts. Each must carry a ``category`` field
            (missing → treated as ``"general"``). ``severity`` is echoed into
            the per-finding mapping for triage.

    Returns:
        Dict with keys:
          - ``frameworks``: per-framework metadata + control name tables
          - ``mappings``: one entry per finding (severity/category + ids +
            ``mapped`` flag)
          - ``coverage``: per-framework {identifier: count}
          - ``unmapped_categories``: sorted unique categories that hit fallback
          - ``summary``: total/mapped counts + top-hit identifier per framework
    """
    mappings: list[dict[str, Any]] = []
    coverage_owasp: Counter[str] = Counter()
    coverage_atlas: Counter[str] = Counter()
    coverage_nist: Counter[str] = Counter()
    unmapped: set[str] = set()
    mapped_count = 0

    for f in findings:
        raw = f.get("category")
        category = str(raw) if raw else "general"
        severity = str(f.get("severity", "INFO"))
        owasp, owasp_hit = _match_prefix(category, OWASP_AGENTIC_MAP, _DEFAULT_OWASP)
        atlas, atlas_hit = _match_prefix(category, MITRE_ATLAS_MAP, _DEFAULT_ATLAS)
        nist, nist_hit = _match_prefix(category, NIST_RMF_MAP, _DEFAULT_NIST)

        # A finding is "mapped" if at least one framework hit a specific prefix
        # (not the fallback). A finding is "unmapped" only if every framework
        # fell through to its default — those categories get tracked for
        # future rule expansion.
        mapped = owasp_hit or atlas_hit or nist_hit
        if mapped:
            mapped_count += 1
        else:
            unmapped.add(category)

        for cid in owasp:
            coverage_owasp[cid] += 1
        for cid in atlas:
            coverage_atlas[cid] += 1
        for cid in nist:
            coverage_nist[cid] += 1

        mappings.append(
            {
                "severity": severity,
                "category": category,
                "owasp": owasp,
                "mitre_atlas": atlas,
                "nist_rmf": nist,
                "mapped": mapped,
            }
        )

    def _top(counter: Counter[str]) -> str | None:
        if not counter:
            return None
        return counter.most_common(1)[0][0]

    return {
        "frameworks": {
            "owasp_agentic": {
                "name": "OWASP Agentic Top 10 (2026 draft)",
                "controls": OWASP_AGENTIC_TOP_10,
            },
            "mitre_atlas": {
                "name": "MITRE ATLAS",
                "controls": MITRE_ATLAS_TECHNIQUES,
            },
            "nist_rmf": {
                "name": "NIST SP 800-53 Rev 5",
                "controls": NIST_RMF_CONTROLS,
            },
        },
        "mappings": mappings,
        "coverage": {
            "owasp_agentic": dict(coverage_owasp),
            "mitre_atlas": dict(coverage_atlas),
            "nist_rmf": dict(coverage_nist),
        },
        "unmapped_categories": sorted(unmapped),
        "summary": {
            "total_findings": len(findings),
            "mapped_findings": mapped_count,
            "owasp_top_hit": _top(coverage_owasp),
            "mitre_top_hit": _top(coverage_atlas),
            "nist_top_hit": _top(coverage_nist),
        },
    }
