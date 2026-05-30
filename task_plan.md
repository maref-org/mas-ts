# Task Plan: MAS-TS-001 v3.0 迭代工程实施方案

## Goal

将 MAS-TS-001 Evaluation Harness 从 v2.1 (5层架构) 增量迁移到 v3.0 (5域×5级架构)，实现 D4 Governance & Security、D5 Evolution & Robustness、Pairwise Elo Ranking 和 L0-L4 执行级别系统。

## Current Phase

Phase 1

## Phases

### Phase 1: 基础架构重构 — D1 扩展 + D2 重构 + Schema v1.2

**目标**: 建立 v3.0 包结构，实现 D1 的 10 项检查和 D2 的 4 子域评分

- [ ] 1.1 创建目录结构: `mas_eval/domains/`, `mas_eval/scoring/`, `mas_eval/harness/`
- [ ] 1.2 创建 Agent Card Schema v1.2 (`mas_eval/schemas/agent_card_v1.2.json`): 增加 constitution 字段 (envelope, health_state, heartbeat), message_format, governance 字段
- [ ] 1.3 实现 D1 (Static Compliance): `mas_eval/domains/d1_compliance.py`
  - 10 项检查 (D1.1-D1.10)
  - 保留 v2.1 的 schema/residency/cross-border 逻辑
  - 新增 Constitution 检查 (envelope 字段, health 4-state, heartbeat)
  - 新增 DAG acyclicity 检查
  - 分数: Base=100, 梯度扣分
- [ ] 1.4 重构 D2 (Single-Agent): `mas_eval/domains/d2_single_agent.py`
  - ModelQuality×0.25: 从 `mas_full_run.py` 提取 MODEL_QUALITY_DB, 增加 weighted subscores
  - ToolCoverage×0.20: core=8/advanced=7 工具分类, schema completeness
  - TaskCompletion×0.30: 从 `mock_calibrate.py` 集成, 5 个子指标
  - E2EScenarios×0.25: 8 场景评分
- [ ] 1.5 更新 `mas_eval/__init__.py`: `STANDARD_VERSION = "MAS-TS-001-v3.0"`
- [ ] 1.6 更新 `pyproject.toml`: version = "0.2.0"
- [ ] 1.7 编写测试: `tests/test_d1_compliance.py`, `tests/test_d2_single_agent.py`
- [ ] 1.8 运行现有测试确保 v2.1 功能不受影响
- **Status:** pending
- **Effort:** ~400 行代码, ~200 行测试

### Phase 2: D3 Multi-Agent Collaboration 重构

**目标**: 将 Layer 5 重构为完整 D3 域 (6 维度+Chat Storm)

- [ ] 2.1 实现 `mas_eval/domains/d3_multi_agent.py`
  - Spawn×0.20: 成功率 ≥95%, 延迟 P99 <2s, 上下文隔离
  - Protocol×0.20: JSON-RPC 2.0 信封, 6 种传输 (stdio/SSE/WS/HTTP/gRPC/IPC), 重试/退避
  - Orchestration×0.25: TaskDAG, Saga 事务, 角色匹配, 并行安全, 动态扩缩
  - Isolation×0.15: 状态隔离 + 资源隔离证明
  - Conflict×0.10: 共识率 ≥0.5, Jaccard 相似度 ≥0.65
  - Persistence×0.10: 快照/恢复, 状态转换正确性, Chat Storm 检测
- [ ] 2.2 更新 `claude_code_tasks.json`: 增加多 agent 测试用例
- [ ] 2.3 添加多 agent 场景 golden trajectories
- [ ] 2.4 编写测试: `tests/test_d3_multi_agent.py`
- **Status:** pending
- **Effort:** ~500 行代码, ~200 行测试

### Phase 3: D4 Governance (治理子系统) 新建

**目标**: 实现 10-state Gray-code 状态机, Circuit Breaker, Oscillation Detection, Audit Trail

- [ ] 3.1 实现 `mas_eval/domains/d4_governance_security.py` — Governance 部分 (0.50 of D4)
  - 10-state 状态机 (INIT→OBSERVE→...→HALT) 带 Gray-code 编码
  - 状态可达性 BFS 验证 (10/10 states)
  - 单 bit 翻转验证 (XOR = power of 2)
  - HALT 吸收状态验证
  - 熵单调性验证 (0→4→0 hump)
  - 快照/恢复测试
- [ ] 3.2 Circuit Breaker 实现
  - 3 连续失败 → OPEN
  - 30s 冷却 → HALF_OPEN
  - 2/2 探测成功 → CLOSED
  - 递归深度 >3 → 触发
  - 滑动窗口宽度 3 振荡检测
- [ ] 3.3 Oscillation Detection
  - 窗口-3 模式匹配
  - 自动稳定 → 冷却 → 验证 → 调整
  - 假阳性率 <10% (200 次运行)
- [ ] 3.4 Audit Trail
  - HMAC-SHA256 签名
  - Append-only JSONL
  - 审计日志重放验证
- [ ] 3.5 编写测试: `tests/test_d4_governance.py`
  - 状态机测试 (Gray-code, 可达性, 单 bit)
  - Circuit Breaker 测试 (OPEN/CLOSED/HALF_OPEN)
  - Oscillation 检测测试
  - Audit HMAC 链验证
- **Status:** pending
- **Effort:** ~600 行代码, ~300 行测试

### Phase 4: D4 Security (安全子系统) 新建

**目标**: 实现渗透测试、红蓝对抗、信任链、SAST 扫描

- [ ] 4.1 Penetration Testing (0.35 of Security)
  - 注入攻击测试 (prompt injection, tool injection)
  - 权限提升测试
  - MCP endpoint fuzzing
  - 密钥泄漏检测
- [ ] 4.2 Red-Blue Exercise (0.25 of Security)
  - 200 轮 × 5 阶段攻防
  - 威胁检测率 ≥90%
  - 平均响应时间 <30s
- [ ] 4.3 Trust Chain (0.25 of Security)
  - 身份验证 (OAuth2/APIKey/mTLS)
  - 信任分数新鲜度 <30s
  - 证书验证 100% 通过
- [ ] 4.4 SAST Scanning (0.15 of Security)
  - Bandit SAST 集成
  - pip-audit 依赖审计
  - TruffleHog 密钥扫描
- [ ] 4.5 完成 `d4_governance_security.py` Security 部分
- [ ] 4.6 编写测试: `tests/test_d4_security.py`
- **Status:** pending
- **Effort:** ~400 行代码, ~200 行测试

### Phase 5: D5 Evolution & Robustness Part 1 新建

**目标**: 实现 Chaos Engineering 和 Drift Detection

- [ ] 5.1 Chaos Engineering (0.30 of D5)
  - 5 种基础设施故障: Network partition, CPU pressure, Memory pressure, Disk failure, Process kill
  - 5 种 LLM 故障: Timeout, Hallucination, Token corruption, Model degradation, Rate limiting
  - 每个故障注入 → 自我修复率测量
- [ ] 5.2 Drift Detection (0.25 of D5)
  - Triple-divergence pipeline: KL divergence, JS divergence, Hellinger distance
  - 基线自动重置 (冷却 60s)
  - 假阴性/假阳性跟踪
- [ ] 5.3 实现 `mas_eval/domains/d5_robustness.py` (部分)
- [ ] 5.4 编写测试: `tests/test_d5_chaos.py`, `tests/test_d5_drift.py`
- **Status:** pending
- **Effort:** ~500 行代码, ~250 行测试

### Phase 6: D5 Evolution & Robustness Part 2 + Elo Ranking

**目标**: 实现 Reflection Loop, C1/C2/C3 Convergence Cycles, Pairwise Elo Ranking

- [ ] 6.1 Reflection Loop (0.20 of D5)
  - 5 维度评估: Correctness(0.35), Completeness(0.25), Conciseness(0.20), Safety(0.10), Actionability(0.10)
  - CriticAgent + RefinerAgent, 最多 3 次迭代
  - 阈值 ≥0.85, 最小改善 ≥0.05/轮
  - 安全门: safety < 0.5 → 阻断
- [ ] 6.2 Convergence Cycles (0.25 of D5)
  - C1 Baseline: 50 轮, FNR<0.15, FPR<0.10
  - C2 Optimization: 100 轮, 策略梯度优化
  - C3 Verification: 50 轮, FNR σ<0.05, FPR σ<0.03, oscillation=0
  - 3 周期通过比例评分
- [ ] 6.3 完成 `mas_eval/domains/d5_robustness.py`
- [ ] 6.4 Pairwise Elo Ranking (`mas_eval/scoring/elo.py`)
  - 初始 Elo=1200, K=32
  - 最少 50 场配对比赛
  - 95% 置信区间
  - 排行榜输出
- [ ] 6.5 编写测试: `tests/test_d5_reflection.py`, `tests/test_d5_convergence.py`, `tests/test_elo.py`
- **Status:** pending
- **Effort:** ~600 行代码, ~300 行测试

### Phase 7: L0-L4 执行引擎 + 评分模型 + CI/CD

**目标**: 实现 5 级执行引擎，统一评分模型，升级 CI/CD

- [ ] 7.1 L0 Fast-Screen CI Gate (`mas_eval/harness/l0_fast_screen.py`)
  - Stage 0: Agent Card 验证 (D1.1-D1.3)
  - Stage 1: Constitution 检查 (D1.4-D1.6)
  - Stage 2: Mock LLM 任务分发 (D2.4 子集, 10 任务)
  - Stage 3: Agent Spawn (D3.2 子集, 5 次)
  - Stage 4: 交通灯报告 (PASS/FAIL/WARNING)
  - 5 分钟完成, $0 token 成本
- [ ] 7.2 L1 Standard (`mas_eval/harness/l1_standard.py`): D1-D3 完整, ~30 分钟
- [ ] 7.3 L2 Deep (`mas_eval/harness/l2_deep.py`): D1-D4, 真实 LLM 子集, ~2 小时
- [ ] 7.4 L3 Comprehensive (`mas_eval/harness/l3_comprehensive.py`): D1-D5, ~8 小时
- [ ] 7.5 L4 Evolution (`mas_eval/harness/l4_evolution.py`): D5 C1-C3 全周期, 多天
- [ ] 7.6 评分模型 (`mas_eval/scoring/absolute.py`)
  - 各域 0-100, 严重度 CRITICAL(-25)/HIGH(-15)/WARNING(-5)/INFO(0)
  - 等级: A≥90, B≥80, C≥70, D≥60, F<60
  - Overall = D1×0.10 + D2×0.25 + D3×0.25 + D4×0.20 + D5×0.20
  - Verdict: APPROVED(≥70, 无 CRITICAL) / CONDITIONAL(≥50) / BLOCKED(<50)
- [ ] 7.7 更新 `generate_report()`: 增加域评分、Elo 排行、L0-L4 报告模板
- [ ] 7.8 更新 `.github/workflows/mas-eval.yml`
  - L0 Fast-Screen 作为 commit gate
  - L1 作为 daily CI
  - 多 Python 版本矩阵 (3.11, 3.12)
  - 覆盖率阈值 ≥70%
- [ ] 7.9 重写 `mas_fast_screen.py` → 包装 L0 引擎
  - `mas_full_run.py` → 包装 L2/L3 引擎
  - 保留 CLI 兼容性
- [ ] 7.10 更新 README, CHANGELOG
- [ ] 7.11 全面 pytest 验证, 确保所有现有测试通过
- **Status:** pending
- **Effort:** ~800 行代码, ~400 行测试

### Phase 8: 集成测试 + 文档 + 发布

**目标**: 完整验证 v3.0 实现, 补充文档, 准备发布

- [ ] 8.1 端到端集成测试: Agent Card → L0 → L2 → L3 流水线
- [ ] 8.2 性能基线测试 (L0 <5min, L1 <30min)
- [ ] 8.3 更新 CONTRIBUTING.md, AGENTS.md
- [ ] 8.4 更新 CHANGELOG.md (v0.2.0)
- [ ] 8.5 更新 SECURITY.md (D4 安全内容)
- [ ] 8.6 代码审查 + 清理
- **Status:** pending
- **Effort:** ~200 行代码, ~200 行测试

## Key Questions

1. Agent Card Schema v1.2 的 constitution 字段具体结构如何设计以保持向后兼容？
2. 是否保留 `mas_fast_screen.py` 和 `mas_full_run.py` 作为 CLI 入口 (包装新模式) 还是废弃？
3. 真实 LLM 集成测试的 API key 管理策略？
4. Chaos Engineering 的故障注入是否需要 Docker 容器化支持？
5. L4 Evolution Cycle 是否需要持久化存储来跨 session 保持状态？

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| 保留 v2.1 脚本作为 CLI 包装器 | 保持向后兼容性，用户无需修改现有调用 |
| Agent Card Schema v1.2 增加而非替换 v1.1 | 向后兼容，现有 Agent Card 无需修改 |
| `mas_eval/domains/` 包封装各域逻辑 | 模块化设计，每个域独立可测试 |
| D4 分为 Governance + Security 两部分 | 分别对应不同测试级别 (L1 仅 Governance, L3 完整安全) |
| L0 Fast-Screen 完全重写 | v3.0 L0 比 v2.1 Fast-Screen 更严格 (增加 constitution 和 spawn 检查) |
| 使用 scipy 计算 KL/JS/Hellinger | scipy.stats.entropy 直接支持，避免手动实现 |
| Mock LLM 保留但增加 v3.0 任务集 | 零成本 CI 门禁的核心依赖，需扩展任务库 |
| Elo 评分作为可选附加分 | 底线评分保持绝对分数, Elo 用于横向比较 |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| -- | -- | -- |

## Notes

- 总预估: ~4000 行新代码 + ~2000 行测试
- 开发顺序: 域实现 (D1→D2→D3→D4→D5) → 执行引擎 (L0→L4) → 评分 → CI/CD → 文档
- 每次 Phase 完成后须运行 `pytest tests/ -v` 确保回归测试通过
