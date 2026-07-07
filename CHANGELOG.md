# Changelog

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
