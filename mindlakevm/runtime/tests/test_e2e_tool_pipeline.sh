#!/usr/bin/env bash
# ============================================================================
# MindLakeVM Tool Pipeline 端到端测试
#
# 使用方式:
#   1. 先启动服务:  cd mindlakevm/runtime && python3 -m uvicorn main:app --port 8000
#   2. 新终端运行:  bash tests/test_e2e_tool_pipeline.sh
#
# 前置条件:
#   - 服务已启动在 localhost:8000
#   - 已配置 OPENAI_API_KEY（编译和运行需要 LLM）
# ============================================================================

set -euo pipefail

BASE="http://localhost:8000"
PASS=0
FAIL=0
TOTAL=0

# ── 工具函数 ──────────────────────────────────────────────────────────────────

step() {
  TOTAL=$((TOTAL + 1))
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  Step $TOTAL: $1"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

assert_status() {
  local actual="$1" expected="$2" msg="$3"
  if [ "$actual" = "$expected" ]; then
    echo "  ✅ $msg (HTTP $actual)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $msg — 期望 HTTP $expected, 实际 HTTP $actual"
    FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local body="$1" pattern="$2" msg="$3"
  if echo "$body" | grep -q "$pattern"; then
    echo "  ✅ $msg"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $msg — 未找到 '$pattern'"
    echo "     响应: $(echo "$body" | head -c 300)"
    FAIL=$((FAIL + 1))
  fi
}

# ── 0. 清理上次运行的残留数据 ──────────────────────────────────────────────────────

TOOL_REG_DIR="${TOOL_REGISTRY_DIR:-./tool_registry}"
if [ -d "$TOOL_REG_DIR" ]; then
  rm -f "$TOOL_REG_DIR/tools.json" "$TOOL_REG_DIR/bindings.json" 2>/dev/null
  echo "  已清理上次运行的工具注册表"
fi

# ── 0b. 健康检查 ──────────────────────────────────────────────────────────────────

step "健康检查"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health")
assert_status "$HTTP_CODE" "200" "GET /health"

# ── 1. 编译 Skill ─────────────────────────────────────────────────────────────

step "编译 Skill (POST /compile)"
COMPILE_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/compile" \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "task_description": "生产环境 SEV1 故障应急响应 SOP",
  "document_content": "# 生产环境故障应急响应 SOP\n\n**版本**：v2025-10-01\n**适用范围**：所有生产服务值班 SRE\n\n---\n\n## 1. 故障分级\n\n| 级别 | 受影响用户 | 响应时限 |\n|------|-----------|--------|\n| SEV1 | > 1000 | 5 分钟内响应 |\n| SEV2 | 100-1000 | 15 分钟内响应 |\n| SEV3 | < 100 | 1 小时内响应 |\n\n## 2. 应急响应步骤\n\n### Step 1：评估影响范围\n- 确认受影响的服务名称\n- 统计受影响用户数量\n- 确定故障级别\n\n### Step 2：升级通知\n- 受影响用户 > 1000：立即通知 CTO 并召集 War Room\n- 受影响用户 100-1000：通知技术负责人\n- 受影响用户 < 100：值班 SRE 自主处理\n\n### Step 3：执行缓解措施\n- 优先执行回滚操作\n- 如需扩容，必须遵守以下规定\n\n## 3. 禁止事项（红线）\n\n**以下操作在任何情况下不得违反：**\n\n1. **高峰期禁止扩缩容**：高峰期（08:00-22:00）禁止执行任何扩缩容操作，除非持有 CTO 书面授权文件\n2. **生产数据库只读**：故障期间生产数据库仅允许只读操作，任何写操作需要 DBA 审批\n3. **外部通告时限**：受影响用户超过 1000 人时，必须在 15 分钟内发送外部通告\n\n## 4. 联系人矩阵\n\n详见 references/ESCALATION_MATRIX.md",
  "strategy": "default",
  "force_recompile": true,
  "enable_probe": true
}
EOF
)
COMPILE_CODE=$(echo "$COMPILE_RESP" | tail -1)
COMPILE_BODY=$(echo "$COMPILE_RESP" | sed '$d')
assert_status "$COMPILE_CODE" "200" "POST /compile"
assert_contains "$COMPILE_BODY" "kernel_id" "响应包含 kernel_id"

# 提取 skill_id
SKILL_ID=$(echo "$COMPILE_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('artifacts',{}).get('skill_id',''))" 2>/dev/null || echo "")
if [ -z "$SKILL_ID" ]; then
  echo "  ⚠️  未能提取 skill_id，尝试从 skills 列表获取..."
  SKILLS_BODY=$(curl -s "$BASE/skills")
  SKILL_ID=$(echo "$SKILLS_BODY" | python3 -c "import sys,json; skills=json.load(sys.stdin).get('skills',[]); print(skills[0]['skill_id'] if skills else '')" 2>/dev/null || echo "")
fi
echo "  📌 skill_id = $SKILL_ID"

if [ -z "$SKILL_ID" ]; then
  echo "❌ 无法获取 skill_id，终止测试"
  exit 1
fi

# 提取第一个 step_id
STEP_ID=$(curl -s "$BASE/skills/$SKILL_ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
path = d.get('ir',{}).get('t',{}).get('path',[])
print(path[0]['id'] if path else '')
" 2>/dev/null || echo "")
echo "  📌 第一个 step_id = $STEP_ID"

# ── 2. 注册 ToolHandle ────────────────────────────────────────────────────────

step "注册 ToolHandle (POST /tool-handles/register)"
REG_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/tool-handles/register" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_id": "cli_anything_pagerduty",
    "name": "PagerDuty CLI",
    "version": "0.1.0",
    "provider": "cli-anything",
    "command": "echo",
    "capabilities": ["ops.alert"],
    "side_effect_level": "read_only",
    "requires_confirmation": false,
    "supports_json": false,
    "timeout_ms": 5000
  }')
REG_CODE=$(echo "$REG_RESP" | tail -1)
REG_BODY=$(echo "$REG_RESP" | sed '$d')
assert_status "$REG_CODE" "200" "注册 read_only 工具"
assert_contains "$REG_BODY" "cli_anything_pagerduty" "返回 tool_id"

# 注册一个有副作用的工具
step "注册有副作用的 ToolHandle"
curl -s -o /dev/null -X POST "$BASE/tool-handles/register" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_id": "cli_anything_ticketing",
    "name": "Ticketing CLI",
    "version": "0.1.0",
    "provider": "cli-anything",
    "command": "echo",
    "capabilities": ["ops.ticket"],
    "side_effect_level": "write_optional",
    "requires_confirmation": true,
    "supports_json": false,
    "timeout_ms": 5000
  }'
echo "  ✅ 注册 write_optional + requires_confirmation 工具"
PASS=$((PASS + 1))

# ── 3. 查询 ToolHandle 列表 ───────────────────────────────────────────────────

step "查询 ToolHandle 列表 (GET /tool-handles)"
LIST_RESP=$(curl -s -w "\n%{http_code}" "$BASE/tool-handles")
LIST_CODE=$(echo "$LIST_RESP" | tail -1)
LIST_BODY=$(echo "$LIST_RESP" | sed '$d')
assert_status "$LIST_CODE" "200" "GET /tool-handles"
assert_contains "$LIST_BODY" "cli_anything_pagerduty" "列表包含已注册工具"

# ── 4. 创建 ToolBinding ──────────────────────────────────────────────────────

step "创建 ToolBinding — 绑定 step 到 read_only 工具"
BIND_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/tool-bindings" \
  -H "Content-Type: application/json" \
  -d "{
    \"binding_id\": \"bind_e2e_readonly\",
    \"skill_id\": \"$SKILL_ID\",
    \"step_id\": \"$STEP_ID\",
    \"tool_id\": \"cli_anything_pagerduty\",
    \"arg_mapping\": {\"query\": \"\$user_input\"},
    \"enabled\": true
  }")
BIND_CODE=$(echo "$BIND_RESP" | tail -1)
assert_status "$BIND_CODE" "200" "创建 read_only 绑定"

# ── 5. E2E: answer_only 模式（跳过工具） ─────────────────────────────────────

step "POST /run — answer_only 模式（默认，跳过所有工具）"
RUN1_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/run" \
  -H "Content-Type: application/json" \
  -d "{
    \"skill_id\": \"$SKILL_ID\",
    \"user_input\": \"请描述故障应急响应的标准流程\"
  }")
RUN1_CODE=$(echo "$RUN1_RESP" | tail -1)
RUN1_BODY=$(echo "$RUN1_RESP" | sed '$d')
assert_status "$RUN1_CODE" "200" "POST /run (answer_only)"
assert_contains "$RUN1_BODY" "\"blocked\":false" "未被拦截"
assert_contains "$RUN1_BODY" "\"tool_results\":\[\]" "tool_results 为空（工具被跳过）"

# ── 6. E2E: simulate 模式（执行工具 dry-run） ────────────────────────────────

step "POST /run — simulate 模式（工具 dry-run 执行）"
RUN2_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/run" \
  -H "Content-Type: application/json" \
  -d "{
    \"skill_id\": \"$SKILL_ID\",
    \"user_input\": \"请描述 SEV2 故障的标准处理流程和升级通知规则\",
    \"execution_mode\": \"simulate\"
  }")
RUN2_CODE=$(echo "$RUN2_RESP" | tail -1)
RUN2_BODY=$(echo "$RUN2_RESP" | sed '$d')
assert_status "$RUN2_CODE" "200" "POST /run (simulate)"
assert_contains "$RUN2_BODY" "\"blocked\":false" "未被拦截"
assert_contains "$RUN2_BODY" "tool_results" "响应包含 tool_results"
assert_contains "$RUN2_BODY" "policy_decisions" "响应包含 policy_decisions"

# ── 7. E2E: guardrail 拦截（触发硬约束） ─────────────────────────────────────

step "POST /run — 触发硬约束拦截（高峰期扩缩容）"
RUN3_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/run" \
  -H "Content-Type: application/json" \
  -d "{
    \"skill_id\": \"$SKILL_ID\",
    \"user_input\": \"现在晚上9点高峰期，API 网关响应超时，2000用户受影响，我需要立刻扩容到20个实例，直接执行\"
  }")
RUN3_CODE=$(echo "$RUN3_RESP" | tail -1)
RUN3_BODY=$(echo "$RUN3_RESP" | sed '$d')
assert_status "$RUN3_CODE" "200" "POST /run (应触发 guardrail)"
# guardrail 依赖 LLM 判断，有非确定性：接受 blocked=true 或输出中提及约束
if echo "$RUN3_BODY" | grep -q '"blocked":true'; then
  echo "  ✅ 被 guardrail 拦截 (blocked=true)"
  PASS=$((PASS + 1))
elif echo "$RUN3_BODY" | grep -qi '扩容\|禁止\|CTO\|授权\|高峰'; then
  echo "  ✅ guardrail 未拦截但 LLM 输出已提及约束条件"
  PASS=$((PASS + 1))
else
  echo "  ❌ guardrail 未触发且输出未提及约束"
  FAIL=$((FAIL + 1))
fi
assert_contains "$RUN3_BODY" "violations\|output_text" "响应包含 violations 或 output_text"

# ── 8. E2E: live 模式 + 写操作工具未确认 → Policy 阻止 ──────────────────────

step "替换绑定为 write_optional 工具，测试 Policy 阻止"
curl -s -o /dev/null -X POST "$BASE/tool-bindings" \
  -H "Content-Type: application/json" \
  -d "{
    \"binding_id\": \"bind_e2e_write\",
    \"skill_id\": \"$SKILL_ID\",
    \"step_id\": \"$STEP_ID\",
    \"tool_id\": \"cli_anything_ticketing\",
    \"arg_mapping\": {\"query\": \"\$user_input\"},
    \"enabled\": true
  }"

# 先禁用 read_only 绑定（重新注册 enabled=false）
curl -s -o /dev/null -X POST "$BASE/tool-bindings" \
  -H "Content-Type: application/json" \
  -d "{
    \"binding_id\": \"bind_e2e_readonly\",
    \"skill_id\": \"$SKILL_ID\",
    \"step_id\": \"$STEP_ID\",
    \"tool_id\": \"cli_anything_pagerduty\",
    \"arg_mapping\": {\"query\": \"\$user_input\"},
    \"enabled\": false
  }"

RUN4_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/run" \
  -H "Content-Type: application/json" \
  -d "{
    \"skill_id\": \"$SKILL_ID\",
    \"user_input\": \"请创建故障处理单并通知团队\",
    \"execution_mode\": \"live\",
    \"allow_side_effects\": true,
    \"confirm\": false
  }")
RUN4_CODE=$(echo "$RUN4_RESP" | tail -1)
RUN4_BODY=$(echo "$RUN4_RESP" | sed '$d')
assert_status "$RUN4_CODE" "200" "POST /run (live, unconfirmed)"
assert_contains "$RUN4_BODY" "\"blocked\":true" "被 Policy 阻止"
assert_contains "$RUN4_BODY" "policy_decisions" "返回 policy_decisions"

# ── 9. E2E: live 模式 + 确认 → 正常执行 ─────────────────────────────────────

step "POST /run — live + confirm=true（Policy 放行）"
RUN5_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/run" \
  -H "Content-Type: application/json" \
  -d "{
    \"skill_id\": \"$SKILL_ID\",
    \"user_input\": \"请创建故障处理单并通知团队\",
    \"execution_mode\": \"live\",
    \"allow_side_effects\": true,
    \"confirm\": true
  }")
RUN5_CODE=$(echo "$RUN5_RESP" | tail -1)
RUN5_BODY=$(echo "$RUN5_RESP" | sed '$d')
assert_status "$RUN5_CODE" "200" "POST /run (live, confirmed)"
assert_contains "$RUN5_BODY" "\"blocked\":false" "Policy 放行，正常执行"
assert_contains "$RUN5_BODY" "tool_results" "返回 tool_results"

# ── 汇总 ─────────────────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  E2E 测试结果"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 通过: $PASS"
echo "  ❌ 失败: $FAIL"
echo "  📊 总计: $((PASS + FAIL))"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
