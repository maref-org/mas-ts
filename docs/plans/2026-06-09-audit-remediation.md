# MAS-TS-001 Audit Remediation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Fix all P0/P1 audit findings: dependency declaration, ruff errors, CI pipeline, leak cleanup

**Architecture:** Fix pyproject.toml first (blocks everything), then code quality, then CI. Each step independently testable.

**Tech Stack:** Python 3.11+, setuptools, ruff, mypy, jsonschema, scipy

**Audit reference:** `产品级发布全量验收标准与评审流程手册.md` + `AGENTS.md` §治理合规检查清单

---

### Task 1: Fix pyproject.toml — add dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add `[project.dependencies]` and `[project.optional-dependencies]`**

Replace entire file with:

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "mas-eval-harness"
version = "0.1.0"
description = "MAS-TS-001 Fast-Screen Evaluation Harness"
requires-python = ">=3.11"
license = {text = "Apache-2.0"}
dependencies = [
    "argcomplete>=3.0",
    "jsonschema>=4.20",
    "numpy>=1.24",
    "pyyaml>=6.0",
    "requests>=2.31",
    "rich>=13.0",
    "tenacity>=8.0",
]
optional-dependencies = {
    "ml" = ["scipy>=1.10"],
    "dev" = [
        "pytest>=8.0",
        "pytest-cov>=5.0",
        "ruff>=0.15",
        "mypy>=1.0",
        "types-requests",
    ],
}

[tool.mas-eval]
fast_screen_timeout_minutes = 5
report_dir = "reports"
trace_dir = "/var/log/mas-eval/traces"
```

**Step 2: Remove `.coverage` from git tracking**

Run: `git rm --cached .coverage`

**Step 3: Add `.coverage` to `.gitignore` (verify it's already there)**

Run: `grep -q '^.coverage$' .gitignore || echo ".coverage" >> .gitignore`

**Step 4: Install deps and verify**

Run: `pip install -e ".[ml,dev]"`

**Step 5: Run tests to confirm install works**

Run: `pytest tests/ -q --tb=line`
Expected: 3 failed (2 jsonschema-related + 1 scipy-related — scipy now present should fix the remaining)

**Step 6: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "fix: add project.dependencies to pyproject.toml
```

---

### Task 2: Fix ruff errors — mas_eval/ package

**Files:**
- Auto-fix was already applied (9 errors fixed)
- Manual verify: `mas_eval/domains/d2_single_agent.py` (Path unused)
- Manual verify: `mas_eval/domains/d3_multi_agent.py` (Path unused, spawn_count, f-string)
- Manual verify: `mas_eval/domains/d4_governance_security.py` (enum unused, visited_primary, has_secret_protection)
- Manual verify: `mas_eval/harness/l0_fast_screen.py` (json unused)
- Manual verify: `mas_eval/utils.py` (Sequence unused)

**Step 1: Auto-fix was already applied in previous session. Verify state.**

Run: `ruff check mas_eval/ --statistics`
Expected: No errors

**Step 2: Commit**

```bash
git add mas_eval/domains/d2_single_agent.py mas_eval/domains/d3_multi_agent.py mas_eval/domains/d4_governance_security.py mas_eval/harness/l0_fast_screen.py mas_eval/utils.py
git commit -m "fix: remove unused imports and variables (ruff)"
```

---

### Task 3: Fix manual ruff errors — root scripts

**Files:**
- Modify: `mas_full_run.py` — rename `l` → `layer` in comprehensions (E741)
- Modify: `generate_anchor.py` — move `import requests` to top level (move try/except import to top or use importlib)
- Modify: `scripts/audit_deep_eval.py` — not in CI scope, leave E402 for now
- Note: `compliance_sidecar.py` F841 (`method`) needs manual check

**Step 1: Fix `mas_full_run.py` ambiguous `l`**

Replace lines 810-823:

```python
def compute_overall_score(layers):
    weights = {1: 0.15, 2: 0.20, 3: 0.25, 4: 0.25, 5: 0.15}
    total = sum(layer["score"] * weights[layer["layer"]] for layer in layers)
    return round(total, 1)
```

Also fix lines in `generate_report`:

```python
    critical_count = sum(
        len([f for f in layer["findings"] if f["severity"] == "CRITICAL"])
        for layer in layers
    )
    high_count = sum(
        len([f for f in layer["findings"] if f["severity"] == "HIGH"])
        for layer in layers
    )
    warning_count = sum(
        len([f for f in layer["findings"] if f["severity"] == "WARNING"])
        for layer in layers
    )
    info_count = sum(
        len([f for f in layer["findings"] if f["severity"] == "INFO"])
        for layer in layers
    )
```

**Step 2: Run to verify**

Run: `ruff check mas_full_run.py --statistics`
Expected: No errors

**Step 3: Fix remaining root script errors**

- `compliance_sidecar.py`: remove `method = parts[0]` (or use it), remove unused `import re`
- `generate_anchor.py`: keep `try: import requests` pattern (it's intentional availability check)
- `mas_fast_screen.py`: remove unused `import os`, fix `f"..."` → `"..."`
- `mas_full_run.py`: remove unused `import subprocess`, `import os`
- `mock_llm.py`: remove unused `import time`

Run: `ruff check *.py --fix`

**Step 4: Verify**

Run: `ruff check *.py --statistics`
Expected: Only E402 in `scripts/` remains (acceptable)

**Step 5: Commit**

```bash
git add mas_full_run.py compliance_sidecar.py mas_fast_screen.py mock_llm.py
git commit -m "fix: remaining ruff lint errors in root scripts"
```

---

### Task 4: Add test CI workflow

**Files:**
- Create: `.github/workflows/test.yml`

**Step 1: Create CI test workflow**

```yaml
name: Test Suite
on:
  push:
    branches: [main, develop, phase*]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -e ".[ml,dev]"

      - name: Lint with ruff
        run: ruff check mas_eval/ --statistics

      - name: Type check with mypy
        run: mypy mas_eval/ --ignore-missing-imports || true

      - name: Test with pytest
        run: pytest tests/ -v --tb=short --cov=mas_eval --cov-report=term-missing

      - name: Check coverage
        run: |
          coverage=$(python3 -c "import json; d=json.load(open('coverage.json')); print(d['totals']['percent_covered'])")
          if (( $(echo "$coverage < 70" | bc -l) )); then
            echo "Coverage $coverage% below threshold 70%"
            exit 1
          fi
```

**Step 2: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: add test suite workflow with pytest, ruff, mypy"
```

---

### Task 5: Enable pre-commit hooks

**Files:**
- Modify: `.pre-commit-config.yaml` (adjust mypy rev to v1.15+ for Python 3.14 compat if needed)

**Step 1: Install pre-commit in venv**

Run: `pip install pre-commit`

**Step 2: Install hooks**

Run: `pre-commit install`

**Step 3: Run hooks on all files**

Run: `pre-commit run --all-files`

**Step 4: Fix any hook failures (iterate)**

- If mypy fails: add `--ignore-missing-imports` or type annotations
- If check-added-large-files fails: verify no >1MB files

**Step 5: Verify git commit works with hooks**

Run: `git add -A && git commit -m "chore: enable pre-commit hooks"` then abort.

---

### Task 6: Final verification

**Step 1: Complete test suite**

```bash
pytest tests/ -v --tb=short --cov=mas_eval --cov-report=term-missing
```

Expected output:
- All tests PASS
- Coverage ≥ 90% on mas_eval/
- 0 ruff errors
- 0 pre-commit hook failures

**Step 2: Verify git status is clean**

```bash
git status
git diff --stat
```

Expected: Only intended changes, no untracked leak files.

---

## Summary

| Task | Priority | Impact | Est. Time |
|------|----------|--------|-----------|
| 1. pyproject.toml deps | P0 | Unblocks all installs | 5 min |
| 2. mas_eval/ ruff fixes | P1 | 9 errors → 0 | 2 min (auto) |
| 3. Root script ruff fixes | P1 | 12 errors → 0 | 5 min |
| 4. CI test workflow | P1 | Quality gate | 10 min |
| 5. Pre-commit hooks | P2 | Developer ergonomics | 5 min |
| 6. Final verification | P0 | Validate everything | 3 min |
