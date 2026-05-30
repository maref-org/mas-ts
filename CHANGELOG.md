# Changelog

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
