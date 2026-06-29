# MAS-TS-001 运维就绪手册

**版本**: v0.1 | **项目**: MAS-TS-001 Evaluation Harness (Python CLI)

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

## 应急联系人

- **主要维护者**: @frankie (GitHub)
- **备用联系人**: MAREF 治理团队 (issues)
- **上报路径**: GitHub Issues → 仓库 Discussion → MAREF governance

## 事故响应流程

1. **发现**: CI 失败 / Issue 报告
2. **分类**: 确定影响范围（单测试 / 模块 / 全仓库）
3. **响应**: 根据 Runbook 执行修复
4. **恢复**: 确认 CI 绿色通过
5. **复盘**: 更新相关文档/Runbook
