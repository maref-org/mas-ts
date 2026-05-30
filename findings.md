# Findings & Decisions: MAS-TS-001 v3.0 工程实施方案

## 项目分析总结

### 当前状态 (v0.1.0 / MAS-TS-001 v2.1)

- **7 个独立脚本 + `mas_eval/` 包**
- **5 层评估模型** (Layer 1-5): Static Audit, Inference Metrics, Action Metrics, E2E Metrics, MAS Dimension
- **14 个测试文件** (~122 tests, ~60% 覆盖率)
- **CI**: GitHub Actions (Fast-Screen 流水线)
- **评分**: L1×0.15 + L2×0.20 + L3×0.25 + L4×0.25 + L5×0.15

### v3.0 目标架构

- **5 域 × 5 级矩阵** (D1-D5, L0-L4)
- **新域**: D4 (Governance & Security), D5 (Evolution & Robustness)
- **新机制**: Pairwise Elo Ranking, L0 Fast-Screen CI Gate, 10-state 状态机, Chaos Engineering
- **评分**: D1×0.10 + D2×0.25 + D3×0.25 + D4×0.20 + D5×0.20

### v2.1 → v3.0 差异分析

| 模块 | v2.1 实现 | v3.0 需求 | 变更类型 |
|------|-----------|-----------|----------|
| D1 (Static Compliance) | 7 项检查 (schema, residency, cross-border, prompt rot) | 10 项检查 + Constitution 检查 (envelope, health, heartbeat) | 扩展 |
| D2 (Single-Agent) | Layer 2+3+4 分散实现 | 4 个子域: ModelQuality×0.25 + ToolCoverage×0.20 + TaskCompletion×0.30 + E2E×0.25 | **重构** |
| D3 (Multi-Agent) | Layer 5 (6 维度, 工具覆盖分析) | 7 维度: Spawn×0.20 + Protocol×0.20 + Orchestration×0.25 + Isolation×0.15 + Conflict×0.10 + Persistence×0.10 | **重构+扩展** |
| D4 (Governance & Security) | **不存在** | 10-state 状态机 + Circuit Breaker + Oscillation Detection + Audit HMAC + Pen-test + Red-Blue + Trust Chain + SAST | **新建** |
| D5 (Evolution & Robustness) | **不存在** | Chaos Engineering + Drift Detection (KL/JS/Hellinger) + Reflection Loop + C1/C2/C3 Convergence | **新建** |
| 评分模型 | 5 层加权 (L1-L5) | 5 域加权 + Pairwise Elo | **重构** |
| 执行级别 | Fast-Screen + Full-Run | L0-L4 五级 (时间约束) | **重构** |
| Agent Card Schema | v1.1 | v1.1 (需扩展) | 扩展 |
| Mock LLM | 12 个预定义工具响应 | 需扩展至完整 D2 测试 | 扩展 |
| Golden Trajectories | 10 个 | 需扩展至 E2E 场景全覆盖 | 扩展 |

### 关键技术决策

| 决策 | 说明 |
|------|------|
| 保留 v2.1 代码作为基础，增量迁移到 v3.0 | v2.1 已成熟，采用适配器模式逐步迁移，避免重写 |
| 新建 D4/D5 模块为独立脚本 | 遵循现有架构风格 (独立脚本 + 测试文件) |
| L0 Fast-Screen 重写 | 集成 D1 + D2(Mock) + D3(basic)，5分钟 CI 门禁 |
| Agent Card Schema 升级到 v1.2 | 增加 constitution/health/heartbeat 字段 |
| 评分引擎重写 | 从 5 层加权切换到 5 域加权，保留向下兼容 |
| 包结构重组 | `mas_eval/` 下新建 `domains/` 子包 |
| 版本号升级到 v0.2.0 | 在 pyproject.toml 和 `__init__.py` 中同步 |

### 依赖分析

| 新依赖 | 用途 | 级别 |
|--------|------|------|
| `scipy>=1.11.0` | KL/JS/Hellinger 散度计算 | L3+ |
| `hmac` (stdlib) | Audit HMAC-SHA256 | L2+ |
| `hashlib` (stdlib) | 签名 | L2+ |
| `stress-ng` (系统工具) | CPU/内存压力注入 | L3+ |
| `hypothesis>=6.0` | 属性基测试/形式验证 | L3+ |
| `tla-utils` (可选) | TLA+ 模型检查集成 | L4 |

### 文件结构决策

```
mas-ts/
├── mas_eval/
│   ├── __init__.py              # STANDARD_VERSION="MAS-TS-001-v3.0"
│   ├── schemas/
│   │   ├── agent_card_v1.1.json # 保留向后兼容
│   │   └── agent_card_v1.2.json # 新增 v3.0 字段
│   ├── domains/                  # 新增：域评估模块
│   │   ├── __init__.py
│   │   ├── d1_compliance.py     # Static Compliance
│   │   ├── d2_single_agent.py   # Single-Agent Capability
│   │   ├── d3_multi_agent.py    # Multi-Agent Collaboration
│   │   ├── d4_governance.py     # Governance & Security
│   │   └── d5_robustness.py     # Evolution & Robustness
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── absolute.py          # 绝对评分 (0-100)
│   │   └── elo.py               # Pairwise Elo Ranking
│   ├── harness/
│   │   ├── __init__.py
│   │   ├── l0_fast_screen.py    # L0 CI 门禁
│   │   ├── l1_standard.py       # L1 标准运行
│   │   ├── l2_deep.py           # L2 深度运行
│   │   ├── l3_comprehensive.py  # L3 综合运行
│   │   └── l4_evolution.py      # L4 演化运行
│   ├── data/                    # 数据文件 (保持不变)
│   └── reports/                 # 报告输出 (保持不变)
├── tests/
│   ├── test_d1_compliance.py
│   ├── test_d2_single_agent.py
│   ├── test_d3_multi_agent.py
│   ├── test_d4_governance.py
│   ├── test_d5_robustness.py
│   ├── test_elo.py
│   ├── test_l0_fast_screen.py
│   └── ... (保留现有测试)
├── compliance_scan.py           # 保留 (适配到 D1)
├── mas_full_run.py              # 保留 (标记为 deprecated)
├── mas_fast_screen.py           # 保留 (标记为 deprecated)
└── ... (其余保留)
```

### 实施阶段划分

- **Phase 1**: D1 扩展 + D2 重构 + Agent Card Schema v1.2
- **Phase 2**: D3 重构 (Protocol Conformance, Spawn SLA, Session Isolation)
- **Phase 3**: D4 新建 (Governance: 状态机, Circuit Breaker, Oscillation, Audit)
- **Phase 4**: D4 安全 (Pen-test, Red-Blue, Trust Chain, SAST)
- **Phase 5**: D5 新建 (Chaos Engineering, Drift Detection, Reflection Loop)
- **Phase 6**: D5 Convergence Cycles + Elo Ranking
- **Phase 7**: L0-L4 执行引擎 + 评分模型 + CI/CD + 测试
