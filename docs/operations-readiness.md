# MAS-TS-001 运维就绪手册

**版本**: v0.2 | **项目**: MAS-TS-001 Evaluation Harness (Python CLI)

> v0.2 追加 2 场景（HITL 中断 API 故障 / 回归基线偏差超阈），覆盖 R3 P0 与 R8 P0 落地后的运维需求。

## 发布通知流程

- 发布准备: 确认 CI 全流程通过（8 个 workflow）
- 发布窗口: 任意时间（CLI 工具，无在线服务依赖）
- 发布后监控: 30 分钟内关注 GitHub Actions 状态
- 升级路径: 用户 → 仓库维护者 → MAREF 治理团队

## 故障 Runbook

| 故障场景 | 检测方式 | 处理步骤 | 预计恢复 |
|---------|---------|---------|---------|
| 测试全部失败 | CI 告警 (GitHub Actions) | 1. 定位失败测试 `pytest tests/ -v --tb=long` 2. 检查是否依赖/环境变更 3. git bisect 定位回归提交 4. git revert 或修复 | 30 min |
| 依赖漏洞 (Critical/High) | pip-audit CI 阻断 | 1. 识别漏洞包 `pip-audit --requirement requirements.txt` 2. 更新到安全版本 3. 重新锁定 `pip freeze > requirements.lock` | 1 h |
| Python 版本不兼容 | CI 矩阵失败 | 1. 检查 pyproject.toml `requires-python` 2. 更新兼容版本范围 3. 测试目标版本 | 30 min |
| ruff/mypy 违反 | CI lint 失败 | 1. 运行 `ruff check . --fix` 2. 修复类型注解 3. 本地验证通过后推送 | 15 min |
| 覆盖率下降 | CI coverage 失败 | 1. 运行 `pytest --cov=mas_eval --cov-report=term-missing` 2. 补充缺失测试 3. 确认 ≥85% | 1 h |
| HITL 中断 API 故障 | FastAPI /hitl 端点无响应 | 1. 检查 uvicorn 进程 `ps aux \| grep uvicorn` 2. 查看 server log 3. 重启服务 `uvicorn api.server:app --reload` 4. 验证 `_hitl_states` 内存清空（已知限制：单进程内存，重启后丢失） | 15 min |
| 回归基线偏差超阈 | pytest test_regression.py 失败 | 1. 检查 `mas_eval/data/baselines/v0.6.0_baseline.json` 是否被误改 2. 运行 `git diff` 对比基线 3. 若评分模型变更导致合理偏差：维护者评审后更新基线 4. 若非预期偏差：`git bisect` 定位回归提交 | 1 h |
| /metrics 端点故障 | Prometheus 抓取失败 | 1. `curl localhost:8000/metrics` 验证响应 2. 检查 uvicorn 进程 3. 验证 prometheus-client 依赖 4. 见下方场景 8 详情 | 15 min |

### 场景 8：/metrics 端点故障

**症状**: Prometheus 抓取 /metrics 失败（HTTP 5xx 或连接超时）

**诊断步骤**:
1. `curl -s http://localhost:8000/metrics | head` — 验证端点是否响应
2. `curl -s http://localhost:8000/health` — 验证服务是否存活
3. 检查服务日志：`journalctl -u mas-eval -n 100` 或 `docker logs mas-eval`
4. 验证 prometheus-client 依赖：`pip show prometheus-client`

**修复步骤**:
1. 若服务未启动：`uvicorn api.server:app --host 0.0.0.0 --port 8000`
2. 若 prometheus-client 缺失：`pip install prometheus-client>=0.20`
3. 若端口被占用：`lsof -i :8000` + 调整端口
4. 若响应缓慢（>5s）：检查 HITL 状态字典大小，清理过期任务

**升级路径**: 若 30 分钟内无法恢复，通知 SRE 团队，临时禁用 Prometheus 抓取（避免告警风暴）

## 应急联系人

- **主要维护者**: @frankie (GitHub)
- **备用联系人**: MAREF 治理团队 (issues)
- **上报路径**: GitHub Issues → 仓库 Discussion → MAREF governance

## 事故响应流程

1. **发现**: CI 失败 / Issue 报告
2. **分类**: 确定影响范围（单测试 / 模块 / 全仓库）
3. **响应**: 根据 Runbook 执行修复
4. **恢复**: 确认 CI 绿色通过
5. **复盘**: 按「事故复盘模板」归档至 `docs/incidents/INCIDENT-<YYYYMMDD>-<slug>.md`，更新 Runbook

## 事故复盘模板

每次 P0/P1 事故恢复后，须在 `docs/incidents/INCIDENT-<YYYYMMDD>-<slug>.md` 归档（目录首次事故时创建）：

### Timeline（时间线）
- T0 触发时间 / 发现方式（CI/Issue/用户报告）
- T1 分类完成时间 + 影响范围判定
- T2 修复方案确定时间
- T3 恢复（CI 绿）时间
- T4 复盘归档时间

### Impact（影响）
- 受影响用户/下游评估数量
- 评估结果可信度影响（是否产生误判 Grade）
- 持续时长

### RCA（根因分析，5-Why）
1. Why 发生？→ …
2. Why 未能检测？→ …
3. Why CI 未拦截？→ …
4. Why Runbook 未覆盖？→ …
5. Why 流程未预防？→ …

### Action Items
| 编号 | 措施 | 负责人 | 截止 | 状态 |
|------|------|--------|------|------|
| A1 | 新增测试用例 | @frankie | T+7 | OPEN |

### Lessons Learned
- 检测侧改进点
- 响应侧改进点
- 预防侧改进点

---

## 评分卡 N/A 声明（v0.7.0）

以下评分卡条目对本项目声明 N/A（不适用），附理由：

| 条目 | 扣分 | 理由 |
|------|------|------|
| F-04 依赖可用性 | -2 | MAS-TS 为 CLI 评估工具，运行时无外部依赖服务（数据库/消息队列/微服务均不适用）。pyproject.toml 依赖均为 Python 库，由 pip-audit + CycloneDX SBOM 覆盖供应链安全。 |
| F-06 i18n 国际化 | -1 | CLI 工具无图形界面、无多语言 UI 需求。输出语言由评估对象 Agent Card 决定，工具本身不向终端用户展示需本地化的 UI 文案。 |
| F-07 a11y 可访问性 | -1 | CLI 工具无图形界面，WCAG 2.1 不适用。终端输出遵循 ANSI 标准色（rich 库），可由终端模拟器辅助技术读取。 |
| On-call 轮值 | -1 | 单人维护的开源 CLI 工具，无生产服务部署、无 SLO 在线保障需求。故障响应通过 GitHub Issues 异步处理，已在「应急联系人」章节定义上报路径。 |
