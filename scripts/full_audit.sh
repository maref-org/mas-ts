#!/bin/bash
# MAS-TS-001 全量审计脚本

set -e

PERCV_CARD="/Volumes/1TB-M2/public/mas-ts/mas_eval/data/sample_cards/percv.json"
SCHEMA_V11="/Volumes/1TB-M2/public/mas-ts/mas_eval/schemas/agent_card_v1.1.json"
SCHEMA_V12="/Volumes/1TB-M2/public/mas-ts/mas_eval/schemas/agent_card_v1.2.json"

echo "=========================================="
echo "  MAS-TS-001 全量审计报告"
echo "=========================================="
echo ""

echo "=== 1. Agent Card Schema 验证 ==="
echo "1.1 验证 v1.2 Schema..."
python3 -c "
import json, jsonschema
with open('$PERCV_CARD') as f:
    card = json.load(f)
with open('$SCHEMA_V12') as f:
    schema = json.load(f)
jsonschema.validate(card, schema)
print('  ✅ v1.2 Schema 验证通过')
"

echo "1.2 检查 card_version..."
python3 -c "
import json
with open('$PERCV_CARD') as f:
    card = json.load(f)
cv = card.get('card_version')
print(f'  card_version: {cv}')
if cv == '1.2':
    print('  ✅ card_version 正确 (1.2)')
else:
    print(f'  ⚠️  card_version 为 {cv}, 预期 1.2')
"

echo ""
echo "=== 2. MAS 关键能力声明检查 ==="
python3 -c "
import json
with open('$PERCV_CARD') as f:
    card = json.load(f)

declared = {cap['skill_id'] for cap in card.get('capabilities', [])}
mas_tools = ['agent_tool', 'worktree', 'memory', 'task_management', 'cron', 'bridge', 'mcp_tool', 'todo_write']

for tool in mas_tools:
    if tool in declared:
        print(f'  ✅ {tool}')
    else:
        print(f'  ❌ {tool} - 缺失')
"

echo ""
echo "=== 3. 端点检查 ==="
python3 -c "
import json
with open('$PERCV_CARD') as f:
    card = json.load(f)

endpoints = card.get('endpoints', {})
for ep in ['api', 'a2a', 'mcp', 'dashboard']:
    if ep in endpoints:
        print(f'  ✅ {ep}: {endpoints[ep]}')
    else:
        print(f'  ❌ {ep} - 缺失')
"

echo ""
echo "=== 4. Constitution 检查 ==="
python3 -c "
import json
with open('$PERCV_CARD') as f:
    card = json.load(f)

const = card.get('constitution', {})
required = ['envelope', 'health_state', 'heartbeat_interval_seconds', 'message_format']
for field in required:
    if field in const:
        print(f'  ✅ {field}')
    else:
        print(f'  ❌ {field} - 缺失')

env = const.get('envelope', {})
env_fields = ['message_id', 'correlation_id', 'timestamp', 'sender', 'protocol']
for field in env_fields:
    if field in env:
        print(f'  ✅ envelope.{field}')
    else:
        print(f'  ❌ envelope.{field} - 缺失')
"

echo ""
echo "=== 5. 重复能力检查 ==="
python3 -c "
import json
from collections import Counter
with open('$PERCV_CARD') as f:
    card = json.load(f)

skill_ids = [cap['skill_id'] for cap in card.get('capabilities', [])]
duplicates = {k: v for k, v in Counter(skill_ids).items() if v > 1}
if duplicates:
    print(f'  ⚠️  发现重复能力声明: {duplicates}')
else:
    print('  ✅ 无重复能力声明')

print(f'  📊 能力声明总数: {len(skill_ids)}')
print(f'  📊 唯一能力数: {len(set(skill_ids))}')
"

echo ""
echo "=== 6. 评估器 Schema 选择逻辑检查 ==="
python3 -c "
import sys
sys.path.insert(0, '/Volumes/1TB-M2/public/mas-ts')
from mas_full_run import select_schema
import json

with open('$PERCV_CARD') as f:
    card = json.load(f)

schema = select_schema(card)
print(f'  自动选择的 Schema: {schema}')
if 'v1.2' in schema:
    print('  ✅ Schema 自动选择逻辑正确')
else:
    print('  ❌ Schema 自动选择逻辑有误')
"

echo ""
echo "=== 7. 运行完整 MAS-TS-001 评估 ==="
cd /Volumes/1TB-M2/public/mas-ts
python3 mas_full_run.py --card "$PERCV_CARD" --output /tmp/percv_audit_result.json 2>&1 | tail -30

echo ""
echo "=== 8. 审计总结 ==="
python3 -c "
import json
with open('/tmp/percv_audit_result.json') as f:
    report = json.load(f)

overall = report['overall']
print(f'  📊 总体得分: {overall[\"score\"]}/100')
print(f'  🎖️  等级: {overall[\"grade\"]}')
print(f'  ✅ 判定: {overall[\"verdict\"]}')
print()
print('  各层级得分:')
for layer in report['layers']:
    print(f'    L{layer[\"layer\"]}: {layer[\"name\"]:<25} {layer[\"score\"]:>5.1f}/100  Grade {layer[\"grade\"]}')
print()
fs = report['findings_summary']
print(f'  问题汇总: CRITICAL={fs[\"critical\"]}, HIGH={fs[\"high\"]}, WARNING={fs[\"warning\"]}, INFO={fs[\"info\"]}')
print()

# 审计结论
if overall['score'] >= 90 and overall['verdict'] == 'APPROVED' and fs['critical'] == 0:
    print('  🎉 审计通过! PERCV 已达到 A 级标准')
elif overall['score'] >= 80:
    print('  ✅ 审计通过! PERCV 已达到 B 级或以上标准')
else:
    print('  ⚠️  审计未完全通过, 需要进一步调优')
"

echo ""
echo "=========================================="
echo "  审计完成"
echo "=========================================="
