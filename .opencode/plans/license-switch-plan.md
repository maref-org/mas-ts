# License Switch: CC-BY-SA 4.0 → Apache-2.0

## Execute the script below

Copy and paste the entire block into your terminal:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /Volumes/1TB-M2/public/mas-ts

echo "=== Step 1: Replace LICENSE ==="
curl -sSL https://www.apache.org/licenses/LICENSE-2.0.txt > LICENSE
echo "  Append copyright notice"
cat >> LICENSE << 'EOF'

   Copyright 2026 frankiehot-tech

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
EOF
echo "  DONE"

echo ""
echo "=== Step 2: Update pyproject.toml ==="
sed -i '' 's/license = {text = "CC-BY-SA 4.0"}/license = {text = "Apache-2.0"}/' pyproject.toml
echo "  DONE"

echo ""
echo "=== Step 3: Update README.md ==="
sed -i '' 's/\*\*License\*\*: CC-BY-SA 4.0/**License**: Apache-2.0/' README.md
echo "  DONE"

echo ""
echo "=== Step 4: Update CONTRIBUTING.md ==="
cat >> CONTRIBUTING.md << 'CONTEOF'

## License

By contributing to this project, you agree that your contributions will be licensed under the Apache License, Version 2.0.
CONTEOF
echo "  DONE"

echo ""
echo "=== Step 5: Add SPDX headers ==="
COPYRIGHT="# SPDX-FileCopyrightText: 2026 frankiehot-tech"
IDENTIFIER="# SPDX-License-Identifier: Apache-2.0"

# Format A — Shebang scripts (8 files)
for f in \
  mas_fast_screen.py \
  mas_full_run.py \
  compliance_scan.py \
  compliance_sidecar.py \
  mock_llm.py \
  mock_calibrate.py \
  generate_anchor.py \
  scripts/audit_deep_eval.py; do
  sed -i '' "1a\\
$COPYRIGHT\\
$IDENTIFIER
" "$f"
  echo "  A: $f"
done

# Format B — Docstring modules (35 files)
for f in \
  mas_eval/domains/d1_compliance.py \
  mas_eval/domains/d2_single_agent.py \
  mas_eval/domains/d3_multi_agent.py \
  mas_eval/domains/d4_governance_security.py \
  mas_eval/domains/d5_robustness.py \
  mas_eval/harness/l0_fast_screen.py \
  mas_eval/harness/l1_standard.py \
  mas_eval/harness/l2_deep.py \
  mas_eval/harness/l3_comprehensive.py \
  mas_eval/harness/l4_evolution.py \
  mas_eval/scoring/absolute.py \
  mas_eval/scoring/elo.py \
  mas_eval/utils.py \
  tests/test_d1_compliance.py \
  tests/test_d2_single_agent.py \
  tests/test_d3_multi_agent.py \
  tests/test_d4_governance.py \
  tests/test_d4_security.py \
  tests/test_d5_robustness.py \
  tests/test_absolute_scoring.py \
  tests/test_compliance_scan.py \
  tests/test_compliance_scan_extended.py \
  tests/test_compliance_sidecar.py \
  tests/test_compliance_sidecar_extended.py \
  tests/test_elo.py \
  tests/test_generate_anchor.py \
  tests/test_generate_anchor_extended.py \
  tests/test_harness.py \
  tests/test_integration.py \
  tests/test_mas_fast_screen.py \
  tests/test_mas_fast_screen_extended.py \
  tests/test_mas_full_run.py \
  tests/test_mock_calibrate.py \
  tests/test_mock_calibrate_extended.py \
  tests/test_mock_llm.py \
  tests/test_mock_llm_extended.py; do
  sed -i '' "1s/^/$COPYRIGHT\\
$IDENTIFIER\\
/" "$f"
  echo "  B: $f"
done

# Format C — __init__.py files (5 files)
for f in \
  __init__.py \
  mas_eval/__init__.py \
  mas_eval/domains/__init__.py \
  mas_eval/harness/__init__.py \
  mas_eval/scoring/__init__.py; do
  printf "%s\n%s\n" "$COPYRIGHT" "$IDENTIFIER" > "$f"
  echo "  C: $f"
done

echo ""
echo "=== Step 6: Verify ==="
TOTAL=$(find . -name "*.py" -not -path './.opencode/*' -not -path './.venv/*' -type f | wc -l)
COVERED=$(rg -l --glob "*.py" "SPDX-License-Identifier" . 2>/dev/null | wc -l)
echo "  Covered: $COVERED / $TOTAL"

if [ "$COVERED" -eq "$TOTAL" ]; then
  echo "  ✓ All files have SPDX header"
else
  echo "  ✗ Missing:"
  rg -L --glob "*.py" "SPDX-License-Identifier" . 2>/dev/null
fi

echo ""
echo "=== Step 7: Run tests ==="
python -m pytest tests/ -v --tb=short || echo "Some tests failed — inspect above"

echo ""
echo "=== DONE ==="
echo "Run 'git diff --stat' to review changes"
```

## Post-execution: commit

```bash
git add -A
git diff --cached --stat
git commit -m "license: CC-BY-SA 4.0 → Apache-2.0"
```
