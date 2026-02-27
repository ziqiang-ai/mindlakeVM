# MindLakeVM 开发者指南

本文档面向需要**扩展或定制** MindLakeVM 的开发者，涵盖项目结构、核心模型、添加新 Skill、注册外部工具、自定义执行器等主题。

---

## 项目结构

```
mindlakevm/runtime/
├── main.py                  # FastAPI 应用入口，挂载所有路由 + MCP Server
├── mcp_server.py            # MCP Server（独立运行或挂载到 FastAPI）
├── models.py                # 所有 Pydantic 数据模型（IR、请求/响应）
├── store.py                 # Skill 持久化（读写 skills/ 目录）
│
├── compiler/
│   ├── llm.py               # LLM 调用封装（llm_json / llm_text / llm_chat）
│   ├── pipeline.py          # Doc2Skill 编译管线（7 阶段）
│   └── tool_export.py       # IR → Claude Tool Definition 导出
│
├── executor/
│   ├── runner.py            # Simple Runner（单次 LLM 调用，快速模式）
│   ├── agent_runner.py      # Agent Runner（多轮 tool_use 循环）
│   ├── guardrail.py         # E 核硬约束检查器
│   ├── tracer.py            # Trace 记录工具
│   └── verifier.py          # 输出验证器
│
├── api/
│   ├── compile.py           # POST /compile
│   ├── run.py               # POST /run
│   ├── skills.py            # GET /skills, GET /skills/{id}
│   └── bench.py             # POST /bench
│
├── skills/                  # 已编译 Skill 的 JSON 存储目录
├── .env                     # 环境变量（不提交 git）
└── requirements.txt
```

---

## 核心数据模型

所有模型定义在 `models.py`，基于 Pydantic。

### SemanticKernelIR — RNET 四核中间表示

```python
class SemanticKernelIR(BaseModel):
    kernel_id: str              # 唯一 ID，kebab-case，如 ops-sev1-v1
    version: str                # IR 版本，当前 "0.3"
    r: RCore                    # R 核：表示层
    n: NCore                    # N 核：标注层
    e: ECore                    # E 核：熵控层
    t: TCore                    # T 核：变换层
```

**R 核（表示）**：领域归类

```python
class RCore(BaseModel):
    domain: str                 # 命名空间，如 "ops.incident"
    object_type: str            # 文档类型：sop/policy/rfc/checklist/faq/postmortem/spec/other
    semantic_space: str         # 一句话描述：面向哪类用户、处理哪类问题
```

**N 核（标注）**：输出约束

```python
class NCore(BaseModel):
    structure: str              # 结构类型：step_by_step/decision_tree/checklist/matrix/faq/mixed
    constraints: list[str]      # 输出必须包含的信息字段
    references: list[ReferenceEntry]  # 关联的参考文件
```

**E 核（熵控）**：合规约束

```python
class ECore(BaseModel):
    format: str                 # 输出格式：markdown/json/structured_text
    target_entropy: str         # 这个 Skill 要消除哪类不确定性
    hard_constraints: list[str] # 硬约束（触发即拦截的红线）
    soft_constraints: list[str] # 软约束（建议遵守）
    meta_ignorance: list[str]   # 文档未涵盖的盲点
```

**T 核（变换）**：执行路径

```python
class PathStep(BaseModel):
    id: str                     # 步骤 ID，kebab-case
    name: str                   # 步骤名称
    description: str            # 步骤说明
    decision_points: list[DecisionPoint]  # 决策点列表
    tool_required: Optional[str]          # 该步骤需要的外部工具名
    requires_evidence: bool     # 是否需要引用证据

class TCore(BaseModel):
    path: list[PathStep]        # 执行路径（有序步骤列表）
    cot_steps: list[str]        # 引导 LLM 推理的思维链
```

---

## 编译管线

`compiler/pipeline.py` 的 `compile_document()` 实现 7 阶段编译：

```
Ingest → Classify → Extract → Synthesize → Package → (Validate) → (Test)
```

1. **Ingest**：标准化输入（处理空文档等边界情况）
2. **Classify**：关键词匹配识别文档类型（sop/policy/rfc 等）
3. **Extract + Synthesize**：调用 LLM，通过 `generate_semantic_kernel_ir` tool_use 生成 IR
4. **Package**：构建 `SkillPackage` 元数据（skill_id、文件列表等）

### 编译策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| `minimal` | 只填必填字段，约束和步骤尽量简洁 | 快速原型、简单文档 |
| `default` | 标准详细度，包含主要约束和步骤 | 日常使用（推荐） |
| `detailed` | 尽量穷举所有约束、决策点、盲点 | 复杂 SOP、高风险政策 |

### 添加新的文档类型分类

在 `pipeline.py` 的 `_TYPE_KEYWORDS` 字典中添加关键词：

```python
_TYPE_KEYWORDS = {
    "sop":        ["sop", "应急", "响应", ...],
    "policy":     ["政策", "policy", ...],
    # 新增类型
    "runbook":    ["runbook", "操作手册", "运维手册"],
}
```

同时在 `models.py` 的 `RCore.object_type` 和 `COMPILE_IR_TOOL` 的 `enum` 中同步添加。

---

## 执行器

### 两种执行器的选择

`mcp_server.py` 和 `api/run.py` 根据环境变量自动选择：

```python
# 触发 Agent Runner 的条件
use_agent = "openrouter" in OPENAI_BASE_URL or ENABLE_TOOL_USE == "1"
```

| 执行器 | 文件 | 特点 |
|--------|------|------|
| Simple Runner | `executor/runner.py` | 单次 LLM 调用，速度快，trace 为模拟值 |
| Agent Runner | `executor/agent_runner.py` | 多轮 tool_use 循环，真实 trace，支持外部工具 |

### Agent Runner 内置工具

Agent Runner 自动为每个 Skill 提供三个内置工具：

| 工具名 | 触发时机 | 作用 |
|--------|---------|------|
| `cite_reference` | 涉及具体规定时 | 显式引用 N 核中的 reference 文件，生成 evidence |
| `report_decision` | 遇到 T 核决策点时 | 记录判断结果和依据到 trace |
| `step_complete` | 完成每个步骤后 | 标记步骤状态，更新 trace |

### 注册外部工具

当 T 核的 `PathStep.tool_required` 不为空，且该工具名在 `external_tools` 中注册时，Agent 会真实调用该工具。

**注册方式**（调用 `run_skill_agent` 时传入）：

```python
from executor.agent_runner import run_skill_agent
from models import RunRequest

# 定义工具的 Claude Tool 描述
external_tools = {
    "k8s_get_pod_status": {
        "type": "function",
        "function": {
            "name": "k8s_get_pod_status",
            "description": "查询 Kubernetes Pod 状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "pod_name": {"type": "string"},
                },
                "required": ["namespace", "pod_name"]
            }
        }
    }
}

# 定义工具的执行函数
external_handlers = {
    "k8s_get_pod_status": lambda namespace, pod_name: (
        f"Pod {pod_name} in {namespace}: Running (2/2 containers ready)"
    )
}

response = run_skill_agent(
    ir=ir,
    req=RunRequest(skill_id="my-skill", user_input="查询 default 命名空间下的 nginx pod"),
    external_tools=external_tools,
    external_handlers=external_handlers,
)
```

**在 SOP 文档中声明工具需求**：编译时在文档中描述工具，LLM 会自动将其写入 `PathStep.tool_required`：

```markdown
## 步骤三：查询当前 Pod 状态

使用 k8s_get_pod_status 工具查询受影响 Pod 的当前状态，
确认是否处于 CrashLoopBackOff 或 OOMKilled 状态。
```

---

## Guardrail 定制

`executor/guardrail.py` 的 `check_guardrails()` 检查 E 核硬约束。

硬约束在**编译时**从文档中提取，运行时不可修改（体现"编译即合规"的设计）。

### 通过编译 API 设置硬约束

编译时在文档中明确描述红线，LLM 会提取到 `e.hard_constraints`：

```markdown
## 操作限制（禁止事项）

- **严禁**在高峰期（09:00-21:00）执行扩缩容操作，除非有 CTO 书面授权
- **禁止**跳过影响范围评估步骤直接执行回滚
- **必须**在执行任何 DB 变更前获得 DBA 审批
```

### 强制重新编译以更新约束

```python
from compiler.pipeline import compile_document
from models import CompileRequest

req = CompileRequest(
    task_description="更新 Sev1 响应 SOP",
    document_content="<新版文档内容>",
    strategy="detailed",
    force_recompile=True,  # 忽略缓存，强制重新编译
)
ir, package = compile_document(req)
```

---

## 直接操作 Store

`store.py` 提供 Skill 的持久化接口，存储在 `skills/` 目录的 JSON 文件中。

```python
import store
from models import SemanticKernelIR, SkillPackage

# 保存
store.save(skill_id, ir, package)

# 读取
result = store.get(skill_id)  # 返回 (ir, package) 或 None
if result:
    ir, package = result

# 列出所有
summaries = store.list_all()  # 返回 list[SkillSummary]

# 删除
store.delete(skill_id)
```

---

## 添加新的 MCP Tool

在 `mcp_server.py` 中添加新的 `@mcp.tool()` 装饰器函数：

```python
@mcp.tool()
def mindlake_export_ir(skill_id: str, format: str = "json") -> str:
    """将 Skill 的 IR 导出为指定格式。
    
    参数：
    - skill_id: Skill ID
    - format: 导出格式 json | yaml
    """
    result = store.get(skill_id)
    if not result:
        return json.dumps({"error": f"Skill '{skill_id}' 不存在"})
    ir, _ = result
    if format == "yaml":
        import yaml
        return yaml.dump(ir.model_dump(), allow_unicode=True)
    return ir.model_dump_json(indent=2)
```

FastMCP 自动从函数签名和 docstring 中提取参数描述，无需手动写 schema。

---

## 添加新的 REST API 路由

在 `api/` 目录中新建文件，然后在 `main.py` 中注册：

```python
# api/export.py
from fastapi import APIRouter
from models import ErrorResponse
import store, json

router = APIRouter()

@router.get("/skills/{skill_id}/export")
def export_skill(skill_id: str):
    result = store.get(skill_id)
    if not result:
        return ErrorResponse(error="not_found", message=f"Skill {skill_id} 不存在")
    ir, package = result
    return {"ir": ir.model_dump(), "package": package.model_dump()}
```

```python
# main.py — 注册路由
from api.export import router as export_router
app.include_router(export_router, prefix="/api/v1", tags=["export"])
```

---

## 本地开发流程

```bash
# 1. 进入 runtime 目录
cd mindlakevm/runtime

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 安装依赖
uv pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 5. 启动开发服务器（热重载）
uvicorn main:app --reload --port 8000

# 6. 同时启动 MCP Server（另一个终端）
python mcp_server.py --port 9100
```

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 只运行 MCP 集成测试
python -m pytest tests/test_claude_integration.py -v
```

### 快速编译测试（不需要启动服务器）

```python
# 直接在 Python 中测试编译管线
import sys
sys.path.insert(0, ".")

from compiler.pipeline import compile_document
from models import CompileRequest

req = CompileRequest(
    task_description="编译数据库变更审批 SOP",
    document_content="""
    ## 数据库变更流程
    1. 提交变更申请单
    2. DBA 审核（必须）
    3. 在测试环境验证
    4. 执行生产变更（禁止在业务高峰期执行）
    5. 验证变更结果
    """,
    strategy="default",
)

ir, package = compile_document(req)
print(f"Skill ID: {package.skill_id}")
print(f"硬约束: {ir.e.hard_constraints}")
print(f"执行步骤: {[s.name for s in ir.t.path]}")
```

---

## 环境变量参考

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 与 `OPENROUTER_API_KEY` 二选一 | OpenAI API Key |
| `OPENROUTER_API_KEY` | 与 `OPENAI_API_KEY` 二选一 | OpenRouter API Key |
| `OPENAI_BASE_URL` | 否 | 自定义 API Base URL，设为 `https://openrouter.ai/api/v1` 时自动启用 tool_use |
| `OPENAI_MODEL` | 否 | 模型名称，默认 `gpt-4o` |
| `ENABLE_TOOL_USE` | 否 | 设为 `1` 强制启用 tool_use 模式（无论使用哪个后端） |
| `SKILLS_DIR` | 否 | Skill 存储目录，默认 `./skills` |
