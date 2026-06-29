# MAS-TS-001 GA 晋升修复计划

> **目标**: 从 Beta → GA，消除所有 P0/P1 阻塞项
> **审计依据**: `产品级发布全量验收标准与评审流程手册.md` v0.1 (MAS-TS)
> **编制日期**: redacted

---

## 当前成熟度评估: Beta

| 维度 | 得分 | 可例外数 | 实际例外数 |
|------|------|---------|-----------|
| 工程质量 (ENGR) | 22/25 | 2 | 1 (mypy) |
| 安全合规 (SEC) | 18/20 | 0 | 1 (pip-audit 不阻断) |
| 运维就绪 (OPS) | 13/15 | 1 | 1 (无 SLO) |
| **GA 条件** | 零例外 | — | ❌ 需修复 |

---

## Task 1: 修复 mypy strict 错误 (P1→PASS)

**问题**: `mypy mas_eval/ --strict` 报 610 errors
**分类**:
- 419 `no-untyped-def` — 函数缺少返回类型注解
- 191 `no-untyped-call` — 调用无类型注解的函数

**策略**: 逐步收紧，不阻塞 CI

### Step 1: 在 pyproject.toml 增加 mypy 覆盖规则

```toml
[tool.mypy]
strict = true
ignore_missing_imports = true
exclude = ['scripts/']

[[tool.mypy.overrides]]
module = [
    'mas_eval.harness.*',
    'mas_eval.oracle.web_arena',
    'mas_eval.scoring.multi_model',
]
# 允许临时宽松，不影响核心 domains
disallow_untyped_defs = false
```

### Step 2: 修复核心 domains（D1-D5）类型注解

按模块分批次修复:

| 批次 | 模块 | 文件 | 预计 error 数 | 优先级 |
|------|------|------|-------------|--------|
| 1 | D1 Compliance | `d1_compliance.py` | ~30 | P0 |
| 2 | D2 Single Agent | `d2_single_agent.py` | ~15 | P0 |
| 3 | D3 Multi-Agent | `d3_multi_agent.py` | ~40 | P0 |
| 4 | D4 Governance | `d4_governance_security.py` | ~80 | P0 |
| 5 | D5 Robustness | `d5_robustness.py` | ~60 | P0 |
| 6 | Scoring | `scoring/*.py` | ~20 | P1 |
| 7 | Harness | `harness/*.py` | ~40 | P1 |
| 8 | Oracle | `oracle/*.py` | ~50 | P1 |
| 9 | Utils/Other | `utils.py`, `__init__.py` | ~10 | P2 |

**修复模板**:

```python
# 修复前
def run_d1(card, schemas_dir=None):

# 修复后
def run_d1(card: dict, schemas_dir: str | None = None) -> dict:
```

**验证**:
```bash
mypy mas_eval/ --strict --ignore-missing-imports --no-incremental | wc -l
# 预期: 逐批递减至 0
```

### Step 3: 更新 CI type-check.yml

在 `--ignore-missing-imports` 基础上追加 `--strict`:

```yaml
- name: mypy type check
  run: mypy mas_eval/ --strict --ignore-missing-imports --no-incremental
```

---

## Task 2: 定义 SLO/SLI (P1→PASS)

**问题**: 未定义服务水平目标和指标

### Step 1: 定义 L0-L4 执行 SLO

| Level | 名称 | P50 延迟目标 | P99 延迟目标 | 错误率目标 | 吞吐量 |
|-------|------|-------------|-------------|-----------|--------|
| L0 | Fast-Screen | ≤ 5 min | ≤ 10 min | ≤ 1% | 单卡 |
| L1 | Standard | ≤ 30 min | ≤ 45 min | ≤ 0.5% | 单卡 |
| L2 | Deep | ≤ 2 h | ≤ 3 h | ≤ 0.5% | 单卡 |
| L3 | Comprehensive | ≤ 8 h | ≤ 12 h | ≤ 0.5% | 单卡 |
| L4 | Evolution | ≤ 72 h | ≤ 96 h | ≤ 1% | 单卡 |

### Step 2: 写入文档

在 `docs/api-contracts.md` 追加 SLO/SLI 定义章节。

### Step 3: CI 中添加性能基线门禁

```bash
# 基准测试
pytest tests/ --benchmark-only --benchmark-json=benchmark.json
# 对比上次基线
python scripts/check_slo.py --benchmark benchmark.json --slo docs/slo.yaml
```

---

## Task 3: 修复运维就绪文档 (P0→PASS)

**问题**: On-call、升级路径、Runbook 均未配置

### Step 1: 创建运维就绪文档

`docs/operations-readiness.md`:

```markdown
# MAS-TS-001 运维就绪手册

## 发布通知流程
- 发布前: 在 #releases 频道通知
- 发布后: 监控 30 分钟
- 升级路径: 用户 → 开发团队 → 维护者

## Runbook
| 故障场景 | 检测方式 | 处理步骤 | 预计恢复时间 |
|---------|---------|---------|-------------|
| 测试全部失败 | CI 告警 | git bisect + revert | 30 min |
| 依赖漏洞 | pip-audit | 更新依赖版本 | 1 h |
| Python 版本不兼容 | CI 错误 | 更新 pyproject.toml 范围 | 30 min |

## 应急联系人
- 主要: @maintainer
- 备用: @backup
```

### Step 2: 添加紧急恢复脚本

```bash
scripts/emergency-rollback.sh
#!/bin/bash
# 紧急回滚到上一版本
git revert HEAD --no-edit
git push origin phase1-clean
```

---

## Task 4: 创建 docs/release-gate.md (P1→PASS)

**问题**: 手册引用的 `docs/release-gate.md` 不存在

### Step 1: 创建轻量门禁文件

`docs/release-gate.md` — 10 项标准化门禁检查清单:

```markdown
# MAS-TS-001 Release Gate Checklist

## Gate 0 — 需求冻结
- [ ] 功能验收标准已明确

## Gate 1 — 代码质量
- [x] ruff: 0 error（scripts/ 内 E402 除外）
- [ ] mypy strict: 0 error
- [ ] 覆盖率 ≥ 85%

## Gate 2 — 测试通过
- [x] pytest: 100% passed
- [x] 集成测试通过

## Gate 3 — 预发验收
- [x] bandit: 0 issues
- [ ] pip-audit: 0 Critical/High
- [ ] SLO 已定义

## Gate 4 — 生产发布
- [x] CI 全流程通过
- [ ] 运维文档就绪
```

### Step 2: 链接到 CI 状态

在 README 中增加 Gate 状态徽章。

---

## Task 5: CI/CD 加固 (P1→PASS)

### 5.1 pip-audit 阻断

修改 `.github/workflows/security-scan.yml`:

```yaml
# 修改前: || true（不阻断）
- run: pip-audit --requirement requirements.txt || true

# 修改后: 阻断 Critical/High
- run: pip-audit --requirement requirements.txt --strict
```

### 5.2 添加 SBOM 生成

在 `security-scan.yml` 中新增 step:

```yaml
- name: Generate SBOM
  run: pip install cyclonedx-bom && cyclonedx-py -o sbom.xml
- uses: actions/upload-artifact@v4
  with:
    name: sbom
    path: sbom.xml
```

### 5.3 更新 test.yml 中 mypy 校验

```yaml
# 新增 step 在 lint 之后
- name: Type check
  run: mypy mas_eval/ --strict --ignore-missing-imports --no-incremental
```

---

## Task 6: 更新过时文档 (P2→PASS)

### 6.1 README

| 需要更新 | 当前内容 | 应更新为 |
|---------|---------|---------|
| 测试数 | "806 tests" | "1139 tests (37 files)" |
| 覆盖率 | 未提及 | "94.16% coverage" |
| 快速安装 | `pip install -r requirements.txt` | `pip install -e ".[ml,dev]"` |
| CI 徽章 | 无 | 添加 GitHub Actions badge |

### 6.2 findings.md

当前内容过时 (592 tests → 1139)，应全面更新或移除。

---

## Task 7: 最终验证 (P0)

### Step 1: 全量回归

```bash
pytest tests/ -v --tb=short --cov=mas_eval --cov-report=term-missing
# 预期: 1139 passed, coverage ≥ 94%
```

### Step 2: 类型检查

```bash
mypy mas_eval/ --strict --ignore-missing-imports --no-incremental
# 预期: 0 errors
```

### Step 3: 安全扫描

```bash
bandit -r mas_eval/ -c pyproject.toml
# 预期: 0 issues
```

### Step 4: Lint

```bash
ruff check mas_eval/ --statistics
# 预期: 0 errors
```

---

## 任务汇总

| # | 任务 | 优先级 | 前序依赖 | 预计工时 | 需 Code Agent |
|---|------|--------|---------|---------|--------------|
| 1 | 修复 mypy strict 错误 | P0 | — | 4-6 h | ✅ 可批量 |
| 2 | 定义 SLO/SLI | P1 | — | 30 min | ❌ 人工决策 |
| 3 | 创建运维就绪文档 | P0 | — | 30 min | ✅ |
| 4 | 创建 docs/release-gate.md | P1 | — | 15 min | ✅ |
| 5 | CI/CD 加固 | P1 | Task1 | 30 min | ✅ |
| 6 | 更新过时文档 | P2 | — | 15 min | ✅ |
| 7 | 最终验证 | P0 | All | 10 min | ✅ |

## GA 晋升检查清单

- [ ] mypy strict: 0 errors
- [ ] SLO/SLI 已定义并文档化
- [ ] docs/operations-readiness.md 已创建
- [ ] docs/release-gate.md 已创建
- [ ] pip-audit 阻断 Critical/High
- [ ] SBOM 生成已集成到 CI
- [ ] README 已更新（测试数/覆盖率/CI徽章）
- [ ] 最终全量验证通过
