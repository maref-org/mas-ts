# Security Policy

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues via GitHub Issues with the `security` label.
Include as much detail as possible: affected component, steps to reproduce,
potential impact, and suggested fix if available.

You will receive a response within 48 hours. We will keep you updated on
the remediation progress and credit you in the security advisory (unless
you request anonymity).

## Supported Versions

| Version | Supported          |
|---------|-------------------|
| 0.1.x   | ✅ Active support |

## Security Architecture

MAS-TS-001 Evaluation Harness is a **static CLI evaluation tool** that does
not run as a service or handle user data. Security focus areas:

- **Supply Chain**: All dependencies pinned in `requirements.lock` + `uv.lock`
- **SAST**: Bandit scans every PR (0 Critical/High threshold)
- **SCA**: pip-audit blocks any Critical/High CVE in CI
- **Secret Detection**: TruffleHog scans every commit
- **SBOM**: CycloneDX SBOM generated on every push to `main`
- **Code Review**: All PRs require passing CI with ruff + mypy + coverage gates

## Security Best Practices

When using MAS-TS-001:

1. Pin dependencies (`pip install -e ".[ml,dev]"` uses locked `requirements.lock`)
2. Run `bandit -r mas_eval/` before opening PRs
3. Keep dependencies updated (`pip list --outdated`)
4. Verify SBOM for supply chain audit (`cyclonedx-py -o sbom.xml`)
