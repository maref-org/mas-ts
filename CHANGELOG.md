# Changelog

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
