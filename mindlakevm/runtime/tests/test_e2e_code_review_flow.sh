#!/usr/bin/env bash
set -euo pipefail

BASE="http://localhost:8000"
RUNTIME_DIR="/Users/mindlake/Documents/mindlakeVM/mindlakevm/runtime"
TMP_REPO="/tmp/mindlakevm_demo_repo"

echo "# PR 代码审查全流程演示"
echo
echo "1. 请先启动后端："
echo "   cd $RUNTIME_DIR && uv run uvicorn main:app --reload --port 8000"
echo

mkdir -p "$TMP_REPO"
cat > "$TMP_REPO/README.md" <<'EOF'
# Demo Repo

This is a placeholder repository for the PR review demo.
EOF

echo "2. 编译代码审查案例文档"
COMPILE_RESP=$(cd "$RUNTIME_DIR" && curl -s -X POST "$BASE/compile" \
  -H "Content-Type: application/json" \
  -d @../../../specs/api/examples/code_review_compile_request.json)
echo "$COMPILE_RESP" | python3 -m json.tool | sed -n '1,80p'
SKILL_ID=$(echo "$COMPILE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['artifacts']['skill_id'])")

echo
echo "3. 读取 skill 详情并提取第一个 step_id"
SKILL_RESP=$(curl -s "$BASE/skills/$SKILL_ID")
STEP_ID=$(echo "$SKILL_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['ir']['t']['path'][0]['id'])")
echo "skill_id=$SKILL_ID"
echo "step_id=$STEP_ID"

echo
echo "4. 注册 PR review 工具"
TOOL_PAYLOAD=$(python3 - <<'PY'
import json
payload = json.load(open("/Users/mindlake/Documents/mindlakeVM/specs/api/examples/code_review_tool_handle.json", encoding="utf-8"))
print(json.dumps(payload, ensure_ascii=False))
PY
)
curl -s -X POST "$BASE/tool-handles/register" \
  -H "Content-Type: application/json" \
  -d "$TOOL_PAYLOAD" | python3 -m json.tool

echo
echo "5. probe 工具"
curl -s -X POST "$BASE/tool-handles/cli_anything_pr_review/probe" | python3 -m json.tool

echo
echo "6. 绑定第一个 step 到 PR review 工具"
BIND_PAYLOAD=$(python3 - <<PY
import json
payload = json.load(open("/Users/mindlake/Documents/mindlakeVM/specs/api/examples/code_review_tool_binding.json", encoding="utf-8"))
payload["skill_id"] = "$SKILL_ID"
payload["step_id"] = "$STEP_ID"
print(json.dumps(payload, ensure_ascii=False))
PY
)
curl -s -X POST "$BASE/tool-bindings" \
  -H "Content-Type: application/json" \
  -d "$BIND_PAYLOAD" | python3 -m json.tool

echo
echo "7. simulate 模式：生成审查草稿"
SIM_PAYLOAD=$(python3 - <<PY
import json
payload = json.load(open("/Users/mindlake/Documents/mindlakeVM/specs/api/examples/code_review_run_simulate_request.json", encoding="utf-8"))
payload["skill_id"] = "$SKILL_ID"
payload["input_context"]["repo_path"] = "$TMP_REPO"
print(json.dumps(payload, ensure_ascii=False))
PY
)
curl -s -X POST "$BASE/run" \
  -H "Content-Type: application/json" \
  -d "$SIM_PAYLOAD" | python3 -m json.tool | sed -n '1,140p'

echo
echo "8. live 模式：发布审查结果"
LIVE_PAYLOAD=$(python3 - <<PY
import json
payload = json.load(open("/Users/mindlake/Documents/mindlakeVM/specs/api/examples/code_review_run_live_request.json", encoding="utf-8"))
payload["skill_id"] = "$SKILL_ID"
payload["input_context"]["repo_path"] = "$TMP_REPO"
print(json.dumps(payload, ensure_ascii=False))
PY
)
curl -s -X POST "$BASE/run" \
  -H "Content-Type: application/json" \
  -d "$LIVE_PAYLOAD" | python3 -m json.tool | sed -n '1,160p'

echo
echo "9. 说明"
echo "simulate 只生成 findings 草稿，不发布。"
echo "live 在确认和副作用权限都满足时，生成 review 结果文件并返回 artifacts。"
