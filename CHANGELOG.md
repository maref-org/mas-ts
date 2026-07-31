# Changelog

## [0.9.0] - 2026-07-31
### Added — GA 运维加固 (API 生产就绪 + 评分基础设施 + 发布门禁扩展)

Closes Gate 3.6/3.7/3.8 运维门禁项。Phase 4 完成 API 生产加固（速率限制、安全头、链路追踪、错误码标准化），Phase 5 新增评分基础设施（上下文窗口管理、降级框架、SLO 错误预算），所有新增模块均接入发布门禁检查。

#### Phase 4 — API 生产就绪 (4 项中间件)
- `api/error_codes.py` (~52 行) — 8 种标准化错误码映射（invalid_level / evaluation_failed / internal_error / hitl_not_found / hitl_timeout / hitl_rejected / rate_limited / validation_error），含 `build_error_response` 工厂函数；7 个端点全部使用统一错误响应格式
- `api/ratelimit.py` (~67 行) — Token bucket 速率限制中间件，支持 `RATE_LIMIT_RATE`/`RATE_LIMIT_BURST` 环境变量配置（默认 100/s burst 50）；429 响应含 `Retry-After` 头
- `api/security_headers.py` (~28 行) — 5 项安全响应头：`X-Content-Type-Options: nosniff` / `X-Frame-Options: DENY` / `X-XSS-Protection: 0` / `Permissions-Policy` / `Referrer-Policy`；`Content-Security-Policy` 在开发模式宽松
- `api/tracing.py` (~41 行) — `X-Trace-ID` 请求/响应贯通中间件（缺失时自动生成 UUIDv4）；结构化日志绑定 trace_id，支持跨请求追踪

#### Phase 5 — 评分基础设施增强
- `mas_eval/scoring/context_window.py` (~64 行) — 3 种截断策略（drop_oldest / summarize / drop_lowest_score），`DEFAULT_MAX_TOKENS=128K`，`check_context_utilization` 返回 token 利用率百分比
- `mas_eval/scoring/degradation.py` (~89 行) — 5 级降级状态机枚举（NORMAL→DEGRADED→FALLBACK→BLOCKED→MANUAL_OVERRIDE），含 `should_degrade`（基于失败率阶梯 1%/5%/25%/50%）和 `should_recover`（连续成功阈值）
- `mas_eval/scoring/slo.py` (~142 行) — Prometheus `Gauge` 错误预算暴露，`check_slo` 评估 5 级 SLO（L0-L4），`get_level_slo_summary` 返回剩余预算百分比+燃烧率；`reset_slo_state` 重置计数器

#### API 集成
- `api/server.py` — CORS 环境变量化（`CORS_ORIGINS` env var, 默认空）；中间件顺序链 Tracing→Security→RateLimit→CORS→Prometheus；新增 `/slo-status` 端点暴露 5 级 SLO 状态
- `api/metrics.py` — Prometheus RED 指标中间件（请求数/延迟） + HITL gauge 更新

#### 模块同步提交
- `mas_eval/domains/d3_security_interaction.py`, `d4_injection_detection.py`, `d4_runtime_consistency.py` — v0.8.1 安全域模块（首批正式纳入版本控制）
- `mas_eval/harness/sidecar_bridge.py` — v0.8.2 运行时安全桥接
- `mas_eval/scoring/standards_mapping.py` — v0.8.3 外部标准映射引擎

#### 发布门禁扩展
- `scripts/release_gate_check.py` — 新增 3 项自动门禁: G3.6 (SLO 错误预算检查), G3.7 (安全头 5 项断言), G3.8 (追踪中间件导入断言)
- `docs/release-gate.md` — v0.3→v0.4 追加 G3.6/G3.7/G3.8 文档；Gate 4 更新（8 CI workflow + 运维文档）
- `tests/test_release_gate_check.py` — 新增 G3.6/G3.7/G3.8 对应的 gate count 断言

### Changed
- `pyproject.toml`: version 0.8.3 → 0.9.0

### Design Decisions
1. 中间件顺序 Tracing→Security→RateLimit→CORS→Prometheus — 追踪在最外层捕获所有请求；安全头在响应序列化前注入；速率限制在 CORS 之前拒绝；Prometheus 在末端采集已完成请求
2. Token bucket 而非 leaky bucket — 支持短突发（burst=50），适配 CI/CD 批量评估场景
3. CSP 开发模式宽松 — 生产部署通过环境变量锁定
4. SLO 使用 Prometheus Gauge 而非 Counter — 便于 /metrics 快照，无需 Rate 计算
5. 降级状态机独立于 D4 评分 — 作为跨维度运维工具，不影响 D1-D5 评分兼容性
6. 上下文截断默认 drop_oldest — 最可预测的行为，适合评估管线的确定性要求

### Verified
- **2042 tests passing** (was 1991 in v0.8.3; +51 new: 13 error_codes + 8 ratelimit + 4 security_headers + 6 tracing + 6 context_window + 6 degradation + 6 SLO + 2 release_gate_check), 82 test files, 0 skipped
- **Coverage**: 91.50% (gate: 85%)
- **mypy strict**: no issues on all modified + new modules
- **ruff**: all checks passed
- **bandit**: 0 issues
- **Release gate**: 11 PASS / 0 FAIL / 4 MANUAL (新增 G3.6/G3.7/G3.8 全部 PASS)
- **Prometheus client**: wired as optional dependency (requirements.txt + pyproject.toml)
- **Regression**: 30 passed (zero drift)
- **Known pre-existing**: 3 SWE-bench tests skipped (require Docker daemon — `tests/test_swe_bench.py` integration/edge tests)

### References
- L0 source report: `AI安全威胁全景与MAS-TS治理补强报告.md` §6.4 (Phase 4/5 design)
- Release gate spec: `docs/release-gate.md` v0.4
- Operations readiness: `docs/operations-readiness.md`

## [0.8.3] - 2026-07-09
### Added — Standards Mapping Engine + Meta-Evaluation Wrap-up (L0 report §6.3 / gap D residual)

Closes 缺口 D 残余 (evaluator self-robustness) and adds cross-framework compliance attribution. Phase 3.1 maps every Finding to OWASP Agentic Top 10 / MITRE ATLAS / NIST SP 800-53 Rev 5; Phase 3.2 quantifies the framework's own resistance to prompt-mutation attacks and adds reproducibility-variance scoring.

#### Phase 3.1 — External Standards Mapping Engine
- `mas_eval/scoring/standards_mapping.py` (~338 lines) — three reference dicts: `OWASP_AGENTIC_TOP_10` (A01-Agent Hijacking ~ A10-Compliance & Governance), `MITRE_ATLAS_TECHNIQUES` (5 entries: AML.T0051/T0043/T0048/T0040/T0050), `NIST_RMF_CONTROLS` (16 SP 800-53 Rev 5 controls)
- Three prefix-mapping tables (32/19/28 entries) cluster ~90 finding categories by prefix (e.g. `direct_injection_*`, `sm_*`, `runtime_steganography_*`); first-match returns, unmatched falls back to per-framework defaults (A10 / AML.T0051 / SI-10)
- `map_findings_to_standards(findings)` aggregator returns `{frameworks, mappings, coverage, unmapped_categories, summary}`; a category is "mapped" only when at least one framework hits a concrete prefix (not fallback)
- Integrated into `mas_eval/reporting/gold_report.py` as optional top-level key `standards_mapping` (None when findings empty — byte-for-byte backward compatible)

#### Phase 3.2 — Meta-Evaluation Wrap-up (gap D residual)
- `mas_eval/scoring/meta_evaluator.py` — `auto_red_team` gains probe 4 `adversarial_prompt_mutation`: 14 canonical attacks (DI-001~007 + JB-001~007) × 5 deterministic mutation operators (case_flip / leet_speak / whitespace_inflation / cyrillic_homoglyph / hyphenation) = 70 mutations. Probe 4 is a FRAMEWORK SELF-ASSESSMENT (tests the regex vector library's resistance to obfuscated prompts), NOT an agent-card check — it never enters `detected_behaviors` and does NOT affect `anti_cheat_score`
- `probe_count` changed from `3 if sidecar_log else 2` to `4 if sidecar_log else 3` (probe 4 always runs); `summary.probes_clean` and `summary.framework_robustness_score` added
- New `MetaEvaluator.score_reproducibility_variance(runs, metric)` method — coefficient-of-variation based 0-100 score (lower variance = higher score); complements existing `score_reproducibility` (0-1 float), does not replace it
- Lazy regex cache `_INJECTION_REGEX_CACHE` avoids circular import; mutation operators are pure deterministic functions (no randomness → reproducible tests)

#### Baseline Sync
- `mas_eval/data/baselines/backdoor_detection_baseline.json` — `baseline_version` → `v0.8.3-standards-metaeval`; three cards `expected_probe_count` 2→3 (probe 4 always runs; baseline tests have no sidecar_log); comments annotated with v0.8.3 note

### Design Decisions
1. Prefix-match mapping at the REPORT layer (D1) — Finding dataclass untouched, avoids touching 70 test files
2. Probe 4 = framework self-assessment (D3/D5) — does not detect agent cards, never enters `detected`, never affects `anti_cheat_score`
3. Probe 4 always runs (D4) — `probe_count` 3→4 (with sidecar) / 2→3 (without); baseline `expected_probe_count` synced 2→3
4. Canonical attacks = 14 (D8) — DI-001~007 + JB-001~007; DI-001/JB-003 texts corrected so unmutated forms are caught by the regex library (escape_rate purely reflects mutation resistance)
5. `standards_mapping` is an optional top-level key (D7) — None when findings empty, full backward compatibility
6. `score_reproducibility_variance` returns a 0-100 dict (D6) — complements (does not replace) existing 0-1 float `score_reproducibility`

### Verified
- 1991 tests passing (was 1961 in v0.8.2; +30 new: 16 standards_mapping + 8 reproducibility_variance + 3 gold_report integration + 3 probe4 baseline), 72 test files, 0 skipped
- mypy strict: no issues on new + modified modules
- ruff: all checks passed
- Backdoor regression baseline: 24 passed (21 original + 3 new probe-4 tests) — zero drift on original 21 (probe 4 does not affect `anti_cheat_score`; `expected_probe_count` assertions synced 2→3)
- `auto_red_team` existing callers unaffected: 3 hardcoded `probe_count` assertions in `tests/test_auto_red_team.py` updated (3→4 with sidecar, 2→3 without)

### Gap D Quantified Finding
- Probe 4 measured escape rate **77.14%** (54/70 mutations evaded the regex vector library), score 22.9 / verdict "poor" — the framework's regex detectors are weak against leet_speak / cyrillic_homoglyph / whitespace_inflation / hyphenation obfuscation. Recorded as a future hardening direction (e.g. normalization layer before regex matching), NOT addressed in Phase 3.

### References
- L0 source report: `AI安全威胁全景与MAS-TS治理补强报告.md` §6.3 (Phase 3 design)
- Plan: `.trae/documents/phase3-standards-mapping-and-meta-eval.md`
- Finalization plan: `.trae/documents/phase3-finalization-docs.md`

## [0.8.2] - 2026-07-09
### Added — Sidecar Runtime Security Bridge (L0 report §6.2 / gap C')

Closes the runtime-assessment gap: D1-D5 previously evaluated only the static Agent Card declaration. Phase 2 wires Compliance Sidecar v2 runtime audit data into the L2/L3 evaluation flow and activates the `d4_runtime_consistency_critical` Gold metric (L3/L4 threshold = 0, defined since v0.8.0 but never populated until now).

#### Sidecar Bridge
- `mas_eval/harness/sidecar_bridge.py` — flattens HMAC audit-chain exports into the `runtime_log` event list; fuses runtime consistency (undeclared network / cross-border / steganography) × 0.6 + runtime injection × 0.4 into a single `runtime_security` result
- `ingest_audit_chain` transparently handles both chain-shaped exports (entries wrapping `decision`) and flat decision lists
- `verify_chain_integrity` — operator utility (HMAC-SHA256 re-verification); NOT called by the evaluation path so secrets never enter the harness
- `run_runtime_injection_detection` — aggregates `runtime_injection_*` findings signed into the chain (bodies are never stored in the chain for privacy/size)

#### Runtime Prompt-Injection Detection
- `compliance_sidecar_v2.py` — new `InjectionScanner` class reuses the Phase 1 static vector library (direct/jailbreak/indirect) with an INDEPENDENT runtime severity model: direct/jailbreak hits in a live request body are CRITICAL (block in content mode), indirect hits are HIGH
- `ContentAuditor.audit_body` Check 6: applies CRITICAL -25 / HIGH -10 score penalties and extends findings before the allowed/block decision

#### D4 Runtime Integration
- `mas_eval/domains/d4_governance_security.py`: `run_d4` accepts an optional `runtime_log` tail parameter. When supplied, D4 applies an ADDITIVE penalty `min(30, crit*8 + high*3)` (capped to prevent a single runtime signal from zeroing D4) and surfaces a top-level `runtime_security` sub-result + subscores (runtime_security / runtime_consistency / runtime_injection) + summary counts. `runtime_log=None` leaves behavior byte-for-byte unchanged (all 28 existing call sites unaffected).
- `mas_eval/harness/aggregation.py`: `extract_gold_metrics` populates `d4_runtime_consistency_critical` only when `runtime_security` is present (graceful skip otherwise — `check_level_thresholds` already tolerates missing metrics)
- `mas_eval/harness/l2_deep.py` (`run_l2_deep` + `run_l2_with_oracle`) and `mas_eval/harness/l3_comprehensive.py` (`run_l3_comprehensive`): thread `runtime_log` through to `run_d4`

### Design Decisions
1. Additive penalty (not blend) — avoids a clean runtime log inflating a weak static card's score
2. Chain-internal pre-computed findings aggregation — bodies are absent from the HMAC chain
3. `verify_chain_integrity` is an operator tool — secrets never enter the evaluation path
4. InjectionScanner severity is independent of the static scorer — direct/jailbreak=CRITICAL, indirect=HIGH
5. Mirrors the `data_leakage` pattern — top-level `runtime_security` key appears only when `runtime_log` is supplied

### Verified
- 1961 tests passing (was 1930 in v0.8.1; +31 new: 18 sidecar_bridge + 7 InjectionScanner/integration + 3 run_d4 runtime_log + 3 gold_metrics), 0 skipped
- mypy strict: no issues on new + modified modules
- ruff: all checks passed
- Backdoor regression baseline: 21 passed — zero drift (baseline tests do not call `run_d4`)
- `test_d4_score_composition` (hardcoded weighted-sum assertion) passes unchanged — `runtime_log=None` applies zero penalty

### References
- L0 source report: `AI安全威胁全景与MAS-TS治理补强报告.md` §4.3 (gap C') / §6.2 (Phase 2 design)
- Plan: `.trae/documents/phase2-runtime-security-continuation.md`

## [0.8.1] - 2026-07-09
### Added — Agentic Security Surface Coverage (OWASP Agentic Top 10 #4 / #5 / #9)

Closes the two largest structural gaps identified in the L0 governance report (AI安全威胁全景与MAS-TS治理补强报告): Prompt-Injection detection and Agent-to-Agent attack-surface testing. Both new domains operate on the existing static Agent-Card evaluation paradigm (no runtime log required), preserving L0/L1 fast-screen parity.

#### D4 — Prompt Injection Detection
- `mas_eval/domains/d4_injection_detection.py` — 4-dimension injection-resistance scoring (direct_injection / indirect_injection / jailbreak_resistance / false_positive_control)
- Defense-declaration audit: scans card for `input_filter`, `prompt_guard`, `tool_output_sanitizer`, `jailbreak_canary`, etc.; rewards declared defenses (DEFENSE_DECLARED_BONUS=30) and penalizes undefended high-risk tools (UNDEFENDED_HIGH_RISK_PENALTY=40, BASE_RESISTANCE=60)
- Vector library: 20 patterns across direct (7), indirect (6), jailbreak (7) categories
- Integrated as 5th sub-score of D4 security (SECURITY_WEIGHTS `injection_detection=0.15`; penetration_testing 0.35→0.30, red_blue 0.25→0.21, trust_chain 0.25→0.21, sast 0.15→0.13)
- 24 tests in `tests/test_d4_injection_detection.py`

#### D3 — Agent-to-Agent Security Interaction
- `mas_eval/domains/d3_security_interaction.py` — 4-dimension A2A attack-surface scoring (cross_agent_injection / delegation_spoof / tool_visibility_exploit / coordination_attack)
- A2A defense probes: response_sanitizer, delegation_audit, tool_scope_isolation, protocol_hardening, identity_verification
- Detects OWASP Agentic #5 (privilege escalation via delegation) and #9 (delegation identity spoofing); flags federation cards that combine a federation role with weak auth + missing delegation_audit
- Integrated as a D3 sub-dimension (orchestration 0.20→0.15, security_interaction 0.05); single-agent cards with no A2A surface receive a neutral 70 + INFO findings
- 22 tests in `tests/test_d3_security_interaction.py`

#### Findings Schema
- `mas_eval/scoring/findings.py` — ROOT_CAUSES expanded 17 → 21 (prompt_injection, undeclared_defense, a2a_security_gap, over_strict_defense) for OWASP Agentic attribution

### Changed
- `mas_eval/domains/d4_governance_security.py`: SECURITY_WEIGHTS rebalanced for the new injection_detection sub-score; `run_d4_security` exposes `injection_detection` subscore plus `injection_detection_score` / `injection_critical_count` in summary
- `mas_eval/domains/d3_multi_agent.py`: `run_d3` integrates security_interaction (0.05 weight); subscores expose `security_interaction` + `security_interaction_detail`
- `pyproject.toml`: version 0.8.0 → 0.8.1
- `tests/test_d3_federation.py`: `test_federation_card_score_higher_than_non_fed` semantics updated — now asserts federation *recognition* (federation_compat > 0 and > base) rather than total-score dominance, since the new security_interaction dimension correctly down-scores federation cards with weak auth + no delegation audit

### Verified
- 1930 tests passing (was 1902 in v0.8.0; +28 new), 0 skipped
- mypy strict: no issues on new + modified modules
- Backdoor regression baseline: 21 passed — tracked subscores (steganography_audit / data_leakage / D1 / D1.14) unchanged; injection_detection and security_interaction are additive and score-neutral on those dimensions
- Federation card correctly scored: A2A surface flagged when federation role + weak auth + missing delegation_audit co-occur

### References
- L0 source report: `AI安全威胁全景与MAS-TS治理补强报告.md` (Athena 知识库)
- Cross-validation corrected 3 report claims: §3.3 omitted `d4_runtime_consistency.py`; §4.1 "Phase 4 待实现" stale (auto_red_team 已实现); §4.4 "score_anti_cheat 硬编码 0.5" stale (已动态化)
- Adjusted plan: 缺口 C' 收窄 (函数已存在，缺采集管道)；缺口 D' 降级 P2 (Anti-Cheat 主体已实现)

## [0.8.0] - 2026-07-06
### Added — Backdoor Detection Enhancement (MAS-TS-BACKDOOR-ENHANCEMENT-001)

Triggered by Claude Code steganography backdoor incident (2026-06-30 Reddit exposure / 2026-07-03 Alibaba ban). Upgrades MAS-TS from "declarative static evaluation" to "declarative + runtime verification" dual-layer detection.

#### Phase 1: Steganography Detection
- `mas_eval/domains/d4_steganography_audit.py` — 4-dimension steganography audit (unicode_steganography / date_format_audit / prompt_content_audit / format_consistency)
- Integrated as 5th sub-score of D4 data_leakage (weight 0.15)
- Detects Claude Code backdoor patterns: Unicode apostrophe variants (U+0027/U+02BC/U+02B9), date format switching (2026-06-30 → 2026/06/30), suspicious prompt patterns (ANTHROPIC_BASE_URL, Asia/Shanghai)
- 27 tests in `tests/test_d4_steganography_audit.py`

#### Phase 2: Sidecar v2 Content Audit
- `compliance_sidecar_v2.py` — HTTP proxy with 4-level audit (off/domain/content/strict)
- HMAC-SHA256 tamper-evident audit chain
- ContentAuditor parses JSON request body, scans for steganography markers
- Detects Claude Code backdoor at runtime: "Todayʼs date is 2026/07/06" + ANTHROPIC_BASE_URL → score=0, blocked
- 18 tests in `tests/test_compliance_sidecar_v2.py`

#### Phase 3: Declaration Gap Enhancement
- D1.14 `check_capability_declaration_completeness` — high-risk capabilities (bash/shell_exec/file_read/file_edit) must declare sub_permissions (env_read/timezone_read/network_access/system_files/credential_files)
- `mas_eval/domains/d4_runtime_consistency.py` — runtime behavior vs Agent Card declaration comparison (3 detection dimensions: undeclared_network_access / cross_border_violation / steganography_findings)
- YARA rule set: 14 rules across 4 files (`security/yara_rules/`) covering Claude Code backdoor, Unicode steganography, date format, domain blacklists
- `mas_eval/scoring/gold_thresholds.py` — L3/L4 added `d4_runtime_consistency_critical: 0`
- `mas_eval/scoring/findings.py` — ROOT_CAUSES expanded from 11 to 17 (steganography_backdoor, declaration_inconsistency, declaration_runtime_mismatch, runtime_violation, undeclared_steganography, binary_pattern_match)
- Schema v1.2 and v2.0 updated: capabilities.sub_permissions + constitution.system_prompt(_samples) + message_format.date_format/timestamp_format
- 27 tests (12 runtime_consistency + 15 D1.14)

#### Phase 4: Strategic Upgrade
- `auto_red_team` function in `mas_eval/scoring/meta_evaluator.py` — automated red-team probes replacing manual red_team_results input (3 probes: static_steganography / static_data_leakage / runtime_inconsistency)
- `docs/proposals/agent_card_mandatory_disclosure_v1.0.md` — industry standard proposal requiring closed-source agents to provide sub_permissions, system_prompt_samples, ISO 8601 date_format, endpoints declaration
- `mas_eval/data/baselines/backdoor_detection_baseline.json` — regression baseline with measured scores for 3 test cards
- `mas_eval/data/backdoor_test/` — 3 test cards (claude_code_compromised / claude_code_clean / unicode_steganography)
- 31 tests (10 auto_red_team + 21 baseline regression)

### Changed
- `pyproject.toml`: version 0.5.0 → 0.8.0
- `tests/test_d1_compliance.py` SAMPLE_CARD: added sub_permissions to bash/file_read/file_edit (now required by D1.14)
- `tests/test_integration.py` and `tests/test_harness.py` SAMPLE_CARD: same sub_permissions addition
- `mas_eval/schemas/agent_card_v1.2.json` and `v2.0.json`: added sub_permissions, system_prompt, system_prompt_samples, date_format, timestamp_format fields

### Verified
- 1902 tests passing (was 1799 in v0.7.0)
- Coverage 88.60% (gate: 85%)
- Claude Code v2.0 card detection: D1 score=30 (NON-COMPLIANT), 3 D1.14 HIGH findings, steg audit detects 5 CRITICAL, auto_red_team score<60
- Clean card passes D1.14 with 0 findings

### References
- Implementation plan: `BACKDOOR_DETECTION_ENHANCEMENT_PLAN_v1.0.md`
- Standard proposal: `docs/proposals/agent_card_mandatory_disclosure_v1.0.md`
- Regression baseline: `mas_eval/data/baselines/backdoor_detection_baseline.json`

## [0.5.0] - 2026-06-22
### Added
- LangChain Adapter SDK (`adapters/langchain/`)
- AutoGen Adapter SDK (`adapters/autogen/`)
- Evaluation HTTP API v1.0 (`api/`) with FastAPI
- L0 Fast Screen parallel execution optimization (<30s target)
- Test coverage for adapters and API

### Changed
- L0 Fast Screen: parallel execution of constitution_check, mock_tasks, agent_spawn stages
- absolute.py docstring: updated to reflect findings opt-in behavior
- pyproject.toml: added fastapi, pydantic, uvicorn dependencies
- pyproject.toml: updated version to 0.5.0
- CI test.yml: extended lint/typecheck/coverage to include tests/

### Fixed
- Chinese filename moved from root to docs/
- DeprecationWarning visibility: changed from ignore to default

## [0.1.0] - 2026-05-14
### Added
- Initial release: MAS-TS-001 Evaluation Harness
- Fast-Screen mode (5-minute zero-cost evaluation)
- Full-Run mode (5-layer deep evaluation)
- Mock LLM engine with rule-based simulation
- Static compliance scanning (Agent Card v1.1 schema + cross-border detection)
- Runtime compliance sidecar (HTTP proxy interceptor)
- Hardware anchor coefficient generation
- Mock drift calibration against golden trajectories

### Fixed
- generate_anchor.py syntax error (nested quotes)
- compliance_sidecar.py missing import argparse
- resolve_endpoint_region port number handling

### Changed
- All scripts: print() replaced with structured logging (logging module)

### Added
- 52 unit tests for core logic modules (compliance_scan, mock_llm, mock_calibrate, compliance_sidecar)
- Git repository initialization
- .gitignore for Python project standards
