# MAS-TS-001 UAT 执行记录 v1.0.1

**版本**: v1.0.1 | **执行日期**: 2026-11-22 | **执行环境**: macOS / Python 3.14.3 / `.venv`
**依据**: 《产品级发布全量验收标准与评审流程手册 v0.3》Gate 3 / G3.4

> **状态：未签署。**
> 本文件是 v1.0.1 的 UAT 执行证据，不是签署记录。在业务方代表与发布经理签字前，
> 不得作为发布证据使用。签署后请另存为
> `docs/uat/MAS-TS-001_UAT_Signoff_v1.0.1.md`，并把所有 `_待填_` 替换为真实姓名。
>
> `scripts/check_version_consistency.py --require-uat` 会同时检查：
> ① 存在 `*UAT_Signoff_v1.0.1.md`；② 勾选了 Go/Conditional Go；③ 无 `_待填_` 残留。
> 仅存在文件不算通过。

---

## 1. 范围

v1.0.1 是**可信度修复版本**，不新增评估能力。UAT 聚焦两条保证：

1. **可复现**：同一 commit 的 L0 评分不再随墙钟漂移。
2. **账本一致**：版本号在所有消费者可见的位置一致，且门禁能自动发现不一致。

沿用 `MAS-TS-001_UAT_v0.7.0.md` 的用例编号体系，新增 UC-08 验证 UAT 门禁本身不是装饰。

---

## 2. 执行结果

| 用例 | 优先级 | 目标 | 实际结果 | 判定 |
|---|---|---|---|---|
| UC-01 | P0 | L0 固定锚点后结果可复现 | 同一 card 连续两次 `as_of_date=2026-11-22`，`domain_scores` 完全一致 | ✅ |
| UC-02 | P0 | 时间边界行为可解释 | `2026-12-29` → D1=100；`2026-12-30` → D1=5.0；gate 固定锚点后不受墙钟影响 | ✅ |
| UC-03 | P0 | 版本账本一致 | pyproject/CHANGELOG/AGENTS/mas_eval/api 均为 `1.0.1` | ✅ |
| UC-04 | P0 | 全量回归无退化 | `2101 passed`，覆盖率 `92.17%`（门禁 85%） | ✅ |
| UC-05 | P1 | 静态质量 | `ruff` 零错误；`mypy mas_eval/ tests/ --strict` 零错误（160 files） | ✅ |
| UC-06 | P0 | CI 黄金门禁路径 | `gold_standard_gate.py --as-of-date 2026-11-22` → PASSED，exit 0 | ✅ |
| UC-07 | P1 | 发布门禁真实性 | `release_gate_check.py`：G3.4 由 manual 改为自动校验；未签署时 FAIL | ✅（按预期失败） |
| UC-08 | P1 | UAT 门禁不可被空文件绕过 | `check_version_consistency.py --require-uat` → exit 1（当前未签署） | ✅（按预期失败） |
| UC-09 | P0 | SWE-bench 真实 Docker 验证 | 正确 patch → `100.0` + `verified_patch`；错误 patch → `0.0` + `verified_patch`；Docker 不可用 → `declared_input` | ✅ |

### 2.1 关键命令与输出

```text
$ python -m pytest tests/ -q --cov=mas_eval --cov-report=term
2101 passed, 22 warnings
Total coverage: 92.17%

$ python scripts/check_version_consistency.py
OK  pyproject.toml: 1.0.1
OK  CHANGELOG.md (top): 1.0.1
OK  AGENTS.md (header): 1.0.1
OK  mas_eval/__init__.py: 1.0.1
OK  api/__init__.py: 1.0.1
WARN UAT signoff for v1.0.1 not found in docs/uat/
Version ledger: CONSISTENT

$ python scripts/check_version_consistency.py --require-uat
ERROR: --require-uat is set but the UAT record is not signed
Version ledger: NOT CONSISTENT   (exit 1)

$ python scripts/gold_standard_gate.py \
    --card mas_eval/data/sample_cards/<l0_target_card>.json \
    --tasks mas_eval/data/athena_mock_tasks.json \
    --as-of-date 2026-11-22
✅ Gold Standard L0 gate PASSED — all 1 card(s) meet thresholds.   (exit 0)

$ python -m pytest tests/test_swe_bench_live.py -m slow -q
3 passed   # 真实 Docker：正确 patch=100 verified_patch，错误 patch=0 verified_patch

$ python - <<'PY'
import json, pathlib
from mas_eval.domains.d1_compliance import run_d1
card_path = next(pathlib.Path("mas_eval/data/sample_cards").glob("*_athena_card.json"))
card = json.loads(card_path.read_text())
for d in ["2026-12-29", "2026-12-30"]:
    print(d, run_d1(card, as_of_date=d)["score"])
PY
2026-12-29 100
2026-12-30 5.0
```

---

## 3. 未覆盖项（已登记）

| 项 | 原因 | 归属 |
|---|---|---|
| 真实 agent 执行（构念效度） | 已实现 `verified_patch`（真实 Docker 测试自报 patch），但行为仍由调用方提供 | P0-2 B（agent runner） |
| RTM 映射校验 | 44/44 条 test_cases 已失效，文件已标 STALE | P1 下一轮 |
| 外部第三方复跑 | 需独立环境/人 | 发布前补 |

---

## 4. 签署（签署后另存为 `MAS-TS-001_UAT_Signoff_v1.0.1.md`）

### 4.1 Go/No-Go 决策

- [ ] **Go** — 全部 P0 用例通过，可进入发布
- [ ] **Conditional Go** — P0 通过，附条件清单（见 4.3）
- [ ] **No-Go** — 存在 P0 失败，阻塞发布

### 4.2 签署方

| 角色 | 姓名 | 签字 | 日期 |
|---|---|---|---|
| 业务方代表 | _待填_ | _待填_ | _待填_ |
| 技术评估方 | _待填_ | _待填_ | _待填_ |
| 发布经理 | _待填_ | _待填_ | _待填_ |

### 4.3 附条件清单（Conditional Go 适用）

_待填_

---

## 5. 与上一版的差异

| 项 | v0.8.0 | v1.0.1 |
|---|---|---|
| 评分时间锚点 | 隐式墙钟 | 显式 `as_of_date`，CI 固定 |
| 版本一致性 | 无自动检查 | `check_version_consistency.py` 接入 CI |
| UAT 门禁 | 人工，硬编码 v0.8.0 路径 | 自动校验当前版本已签署 |
| RTM | 声称 100% 覆盖 | 显式标记 STALE，禁止作发布证据 |
