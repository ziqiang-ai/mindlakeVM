# MindLakeVM MCP Server 使用指南

MindLakeVM MCP Server 将认知编译平台的核心能力（编译、执行、Skills 管理）暴露为标准 MCP 协议，任何 MCP 客户端都可以接入。

---

## 快速启动

### 前置条件

1. Python 3.11+，已安装 `uv`
2. 配置 `.env` 文件（参考 `.env.example`）

```bash
# 安装依赖
cd mindlakevm/runtime
uv pip install -r requirements.txt
```

### 配置 `.env`

```bash
# Option A: OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Option B: OpenRouter + Claude（推荐，支持 tool_use）
OPENROUTER_API_KEY=sk-or-...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=anthropic/claude-sonnet-4-20250514

SKILLS_DIR=./skills
```

### 启动 Server

```bash
# HTTP 模式（默认端口 9100）
python mcp_server.py

# 指定端口
python mcp_server.py --port 8080

# stdio 模式（适合 Claude Desktop 本地集成）
python mcp_server.py --stdio
```

启动成功后输出：
```
Starting MindLakeVM MCP Server on http://localhost:9100/mcp
INFO:     Uvicorn running on http://0.0.0.0:9100 (Press CTRL+C to quit)
```

---

## 接入方式

### Windsurf

Windsurf 支持 HTTP 和 stdio 两种方式。

**方式一：HTTP（推荐，需先启动 server）**

打开 Windsurf 设置 → 搜索 `MCP` → 编辑 `~/.codeium/windsurf/mcp_config.json`：

```json
{
  "mcpServers": {
    "mindlake-vm": {
      "serverUrl": "http://localhost:9100/mcp"
    }
  }
}
```

先启动 server：
```bash
cd mindlakevm/runtime
python mcp_server.py --port 9100
```

**方式二：stdio（Windsurf 自动管理进程）**

```json
{
  "mcpServers": {
    "mindlake-vm": {
      "command": "/path/to/mindlakevm/runtime/.venv/bin/python",
      "args": [
        "/path/to/mindlakevm/runtime/mcp_server.py",
        "--stdio"
      ],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-...",
        "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
        "OPENAI_MODEL": "anthropic/claude-sonnet-4-20250514",
        "SKILLS_DIR": "/path/to/mindlakevm/runtime/skills"
      }
    }
  }
}
```

配置保存后，在 Windsurf Cascade 面板中刷新 MCP，即可在对话中调用 `mindlake_compile`、`mindlake_run` 等工具。

---

### Cursor

Cursor 通过项目级或全局配置接入 MCP。

**方式一：项目级配置（推荐）**

在项目根目录创建 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "mindlake-vm": {
      "command": "/path/to/mindlakevm/runtime/.venv/bin/python",
      "args": [
        "/path/to/mindlakevm/runtime/mcp_server.py",
        "--stdio"
      ],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-...",
        "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
        "OPENAI_MODEL": "anthropic/claude-sonnet-4-20250514",
        "SKILLS_DIR": "/path/to/mindlakevm/runtime/skills"
      }
    }
  }
}
```

**方式二：全局配置**

编辑 `~/.cursor/mcp.json`（格式相同）。

配置后重启 Cursor，在 Agent 模式（`Cmd+I`）中即可使用 MindLakeVM 工具。

> **注意**：Cursor 目前仅在 **Agent 模式**下支持 MCP，普通 Chat 模式不可用。

---

### Claude Code

```bash
claude mcp add --transport http mindlake-vm http://localhost:9100/mcp
```

验证：
```bash
claude mcp list
```

### Claude Desktop

在 `claude_desktop_config.json` 中添加（stdio 模式）：

```json
{
  "mcpServers": {
    "mindlake-vm": {
      "command": "python",
      "args": [
        "/path/to/mindlakevm/runtime/mcp_server.py",
        "--stdio"
      ],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-...",
        "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
        "OPENAI_MODEL": "anthropic/claude-sonnet-4-20250514"
      }
    }
  }
}
```

macOS 配置文件位置：`~/Library/Application Support/Claude/claude_desktop_config.json`

### 挂载到 FastAPI

```python
# main.py
from mcp_server import get_mcp_app

app.mount("/mcp", get_mcp_app())
```

---

## MCP Tools

### `mindlake_compile` — 编译文档为 Skill

将企业文档（SOP、政策、RFC 等）编译为含 RNET 四核 IR 的可执行 Skill。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_description` | string | ✅ | 任务描述，如"编译 Sev1 事故响应 SOP" |
| `document_content` | string | ❌ | 文档正文（不提供则仅凭任务描述生成） |
| `strategy` | string | ❌ | 编译策略：`minimal` / `default`（默认）/ `detailed` |

**返回示例：**

```json
{
  "status": "compiled",
  "skill_id": "ops-sev1-abc123",
  "kernel_id": "kernel-xyz",
  "domain": "运维",
  "object_type": "SOP",
  "hard_constraints": ["禁止跳过 P0 告警处理", "必须通知 oncall"],
  "steps": ["告警确认", "影响评估", "应急响应", "事后复盘"],
  "step_count": 4
}
```

---

### `mindlake_list_skills` — 列出已编译 Skills

**参数：** 无

**返回示例：**

```json
[
  {
    "skill_id": "ops-sev1-abc123",
    "skill_name": "Sev1 事故响应",
    "domain": "运维",
    "object_type": "SOP",
    "compiled_at": "2026-02-27T12:00:00Z",
    "hard_constraints_count": 2,
    "step_count": 4
  }
]
```

---

### `mindlake_run` — 执行 Skill

执行已编译的 Skill，经过 guardrail 检查 → Agent 循环 → 验证三个阶段。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `skill_id` | string | ✅ | Skill ID（通过 `mindlake_list_skills` 获取） |
| `user_input` | string | ✅ | 用户的问题或请求 |

**返回示例（正常执行）：**

```json
{
  "output_text": "根据 Sev1 响应 SOP，建议采取以下步骤...",
  "blocked": false,
  "trace": [
    {"step_id": "step-1", "status": "completed", "notes": "告警确认完成"},
    {"step_id": "step-2", "status": "completed", "notes": "影响评估完成"}
  ],
  "evidence": [
    {"source_path": "./sop.md", "excerpt": "P0 告警必须在 5 分钟内响应"}
  ],
  "validation": {"passed": true, "score": 0.92}
}
```

**返回示例（触发 guardrail）：**

```json
{
  "output_text": "该请求触发了合规限制，无法执行。",
  "blocked": true,
  "violations": [
    {"constraint": "禁止跳过 P0 告警处理", "reason": "用户请求跳过告警确认步骤"}
  ]
}
```

---

### `mindlake_skill_tool_definition` — 获取 Skill 的 Claude Tool Definition

返回可直接注册到其他 Agent 的 Tool 定义包。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `skill_id` | string | ✅ | Skill ID |

---

## MCP Resources

Resources 暴露 Skill 的内部状态，可通过 MCP 客户端直接读取。

| URI | 说明 |
|-----|------|
| `skill://{skill_id}/ir` | Skill 的完整 RNET 四核 IR（JSON） |
| `skill://{skill_id}/summary` | Skill 摘要（领域、约束、步骤列表） |
| `skill://{skill_id}/tool` | Skill 的 Claude Tool Definition |

---

## MCP Prompts

| Prompt | 参数 | 说明 |
|--------|------|------|
| `skill_system_prompt` | `skill_id` | 将 Skill 渲染为 Claude system prompt，可直接用于挂载 |
| `compile_guide` | `document_type`（默认 SOP） | 编译指南，告诉 Claude 如何使用 MindLakeVM |

---

## 执行模式说明

`mindlake_run` 根据环境变量自动选择执行器：

| 条件 | 执行器 | 说明 |
|------|--------|------|
| `OPENAI_BASE_URL` 包含 `openrouter` | Agent Runner | 多轮 tool_use 循环，逐步 trace |
| `ENABLE_TOOL_USE=1` | Agent Runner | 强制启用 Agent 模式 |
| 其他 | Simple Runner | 单次 LLM 调用，适合快速测试 |

Agent Runner 特性：
- 按 T.path 逐步执行，每步记录 trace
- 支持 `tool_required` 字段的外部工具调用
- 通过 `cite_reference` tool 显式引用证据
- 通过 `report_decision` tool 记录决策点

---

## 验证 Server 是否正常

```bash
# 1. 握手测试（获取 session ID）
curl -s -X POST http://localhost:9100/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}'

# 2. 列出工具（需替换 SESSION_ID）
curl -s -X POST http://localhost:9100/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

正常响应包含 4 个工具：`mindlake_compile`、`mindlake_list_skills`、`mindlake_run`、`mindlake_skill_tool_definition`。
