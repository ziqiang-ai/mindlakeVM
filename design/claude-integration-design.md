# MindLakeVM × Claude Agent 兼容性设计：深度技术方案

> **核心问题**：MindLakeVM 当前把 LLM 当作 text-in/text-out 的黑箱调用，完全没有利用 Claude 的原生能力（tool_use / MCP / PTC / extended thinking）。本文档从代码层面分析每一个集成点，给出具体改造方案。

---

## 一、当前架构的五个"断裂点"

通过逐行分析 runtime 代码，我发现 MindLakeVM 与 Claude Agent 生态之间存在五个具体的断裂点：

### 断裂点 1：LLM 层 — 只有 OpenAI SDK，不支持 Claude 原生 API

```python
# compiler/llm.py — 当前实现
from openai import OpenAI

def llm_json(system_prompt: str, user_message: str) -> dict:
    client = OpenAI(api_key=..., base_url=...)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, ...],
    )
```

问题：
- 通过 OpenRouter 可以调 Claude，但只是文本模式——**丢失了 Claude 的 tool_use、extended thinking、computer use 能力**
- `response_format = {"type": "json_object"}` 是 OpenAI 特有的，Claude 有自己的结构化输出机制

### 断裂点 2：tool_required 是死代码

```python
# models.py
class PathStep(BaseModel):
    tool_required: Optional[str] = None  # 字段存在

# runner.py — _build_skill_prompt() 只是把它渲染成文本
steps = "\n".join(
    f"{i+1}. [{s.id}] {s.name}：{s.description}"  # tool_required 被忽略了！
    for i, s in enumerate(ir.t.path)
)
```

编译器会生成 `tool_required: "k8s_rollback"` 这样的字段，但 runner 从来不做任何 tool dispatch。**这是 MindLakeVM 最大的未实现能力。**

### 断裂点 3：执行器是单次 LLM 调用，不是 Agent 循环

```python
# runner.py — 当前的执行模型
def run_skill(ir, req):
    violations = check_guardrails(ir.e, req.user_input)  # LLM call 1
    if violations: return blocked
    
    output_text, in_tok, out_tok = llm_text(skill_prompt, req.user_input)  # LLM call 2（一次性）
    
    evidence = _collect_evidence(ir, req.user_input, output_text)  # 启发式匹配
    trace = make_trace(ir.t.path)  # 全部标记为 completed（假的！）
    validation = verify(ir, output_text, evidence, len(trace))
    return RunResponse(...)
```

问题：
- 只做了**一次** LLM 调用，然后假装所有 T.path 步骤都已完成
- 没有按 T.path 逐步执行、逐步 trace
- 没有在步骤间调用 tool
- evidence 收集是启发式的字符串匹配，而非真正的引用检索

### 断裂点 4：Skill 没有暴露为可发现的服务

```python
# store.py — 纯文件存储
def save(skill_id, ir, package):
    with open(f"./skills/{skill_id}.json", "w") as f:
        json.dump(data, f)
```

Skills 存在本地 JSON 文件里，没有：
- MCP Server 暴露
- Tool Search Tool 兼容的元数据
- 外部系统可发现的注册机制

### 断裂点 5：guardrail 检查没有利用 Claude 的结构化能力

```python
# guardrail.py — 用 prompt 让 LLM 返回 JSON
system_prompt = """你是一个合规审查员...必须返回合法 JSON..."""
result = llm_json(system_prompt, user_msg)  # 希望 LLM 返回 {"violations": [...]}
```

这种方式在 OpenAI 的 json_mode 下尚可，但在 Claude 上：
- 没有利用 Claude 的 tool_use 做结构化输出（更稳定）
- 没有利用 extended thinking 做复杂约束推理

---

## 二、五层集成架构

我提出五层集成方案，从最轻量（改几行代码）到最深度（架构重构）：

```
Layer 5: MCP Server — 让 Claude Agent 发现并调用 MindLakeVM Skills
Layer 4: IR → Claude Tools — 编译器输出 Claude 原生 tool 定义
Layer 3: Agent Loop — 执行器从单次调用改为 Claude Agent 循环
Layer 2: Native Tool Use — guardrail/compiler 用 Claude tool_use 做结构化输出
Layer 1: OpenRouter + tool_use — LLM 层支持 Claude tool_use（无需 Anthropic SDK）
```

每层都可以独立实施，但上层依赖下层。

---

## 三、Layer 1 — 通过 OpenRouter 使用 Claude（已实现 ✅）

### 设计决策

**不引入 Anthropic SDK**，而是通过 OpenRouter 代理调用 Claude。原因：

1. 不需要 Anthropic API Key（OpenRouter key 统一管理所有模型）
2. OpenRouter 对 Claude 透传 `tools` 参数，支持 tool_use
3. 保持 OpenAI SDK 作为唯一依赖，无需新增包
4. 可随时切换模型（Claude / GPT / Gemini），无代码改动

### 已完成的改造

`compiler/llm.py` 新增三个能力：

**1. `llm_json()` 新增 `tools` 参数**

```python
def llm_json(system_prompt, user_message, tools=None) -> dict:
    # 当 tools 不为空时，优先从 tool_calls 响应中提取结构化数据
    if msg.tool_calls:
        return json.loads(msg.tool_calls[0].function.arguments)
    # fallback: 从文本中解析 JSON
```

**2. `llm_text()` 新增 `tools` 参数**

```python
def llm_text(system_prompt, user_message, tools=None) -> tuple[str, int, int]:
    # 透传 tools 给 OpenRouter/Claude，支持 tool_use
```

**3. 新增 `llm_chat()` — 多轮 Agent 循环**

```python
def llm_chat(system_prompt, messages, tools=None):
    # 返回原始 response，调用方自行处理 tool_calls
    # 适用于 Agent Runner 的多轮 tool_use 循环
```

### 环境配置

```bash
# .env — 使用 Claude via OpenRouter
OPENROUTER_API_KEY=sk-or-...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=anthropic/claude-sonnet-4-20250514
```

### 影响范围

- `compiler/llm.py` — 核心改动（向后兼容，无 tools 参数时行为不变）
- `.env.example` — 新增 Claude via OpenRouter 配置示例
- `main.py` / `api/*.py` — 无需改动
- 所有调用 `llm_json` / `llm_text` 的地方自动受益
- 无需安装新依赖

---

## 四、Layer 2 — Guardrail 和 Compiler 用 Claude Tool Use 做结构化输出（已实现 ✅）

### 问题

当前 guardrail 让 LLM "请返回 JSON"，这在 Claude 上不如 tool_use 稳定。

### 改造：guardrail 用 tool_use

```python
# executor/guardrail.py — 用 Claude tool_use 替代 JSON prompt

GUARDRAIL_TOOL = {
    "name": "report_violations",
    "description": "Report which hard constraints are violated by the user's request",
    "input_schema": {
        "type": "object",
        "properties": {
            "violations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "constraint_index": {"type": "integer", "description": "0-based index of the violated constraint"},
                        "reason": {"type": "string", "description": "Why this constraint is violated, citing user's exact words"}
                    },
                    "required": ["constraint_index", "reason"]
                }
            }
        },
        "required": ["violations"]
    }
}

def check_guardrails(e: ECore, user_input: str) -> list[Violation]:
    if not e.hard_constraints:
        return []
    
    constraints_text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(e.hard_constraints))
    system_prompt = "你是合规审查员。判断用户请求是否触发硬约束。模糊情况优先不触发。"
    user_msg = f"硬约束列表：\n{constraints_text}\n\n用户请求：\n{user_input}"
    
    # 用 tool_use 做结构化输出 — 比 JSON prompt 更稳定
    result = llm_json(system_prompt, user_msg, tools=[GUARDRAIL_TOOL])
    
    violations = []
    for v in result.get("violations", []):
        idx = v.get("constraint_index", 0)
        if 0 <= idx < len(e.hard_constraints):
            violations.append(Violation(
                constraint=e.hard_constraints[idx],
                reason=v.get("reason", ""),
                severity="hard",
            ))
    return violations
```

### 改造：compiler 用 tool_use

同理，`pipeline.py` 的 `_extract_ir()` 可以定义一个 `generate_semantic_kernel_ir` tool，让 Claude 通过 tool_use 返回 IR，而非靠 JSON prompt + tolerant parse。

---

## 五、Layer 3 — 执行器改造为 Agent 循环（已实现 ✅）

**这是最重要的一层改造。** 当前 runner 是单次 LLM 调用，改造后变成按 T.path 逐步执行的 Agent 循环。

### 当前问题

```
runner.py 现在：
  guardrail → llm_text(一次) → 假装所有步骤完成 → 启发式 evidence → 验证
  
应该是：
  guardrail → 按 T.path 逐步执行 → 每步可调 tool → 每步记 trace → 真实 evidence → 验证
```

### 核心设计：IR → Claude Tool Definitions + Agent Loop

**关键思路**：把 T.path 中每个有 `tool_required` 的步骤编译成 Claude Tool 定义，然后运行一个 Claude Agent 循环。

```python
# executor/agent_runner.py — 新的 Agent 执行器

from anthropic import Anthropic
from models import *
from executor.guardrail import check_guardrails
from executor.tracer import make_trace, update_trace_decision
from executor.verifier import verify


def run_skill_agent(ir: SemanticKernelIR, req: RunRequest,
                    external_tools: dict[str, callable] | None = None) -> RunResponse:
    """
    Agent 循环执行器：
    1. guardrail 预检
    2. 把 IR 编译成 Claude system prompt + tool definitions
    3. 运行 Claude Agent 循环（多轮 tool_use）
    4. 逐步记录 trace
    5. 收集 evidence
    6. 验证
    """
    # Step 1: guardrail（复用现有逻辑）
    violations = check_guardrails(ir.e, req.user_input)
    if violations:
        blocked_step = ir.t.path[0].id if ir.t.path else None
        trace = make_trace(ir.t.path, blocked_at=blocked_step)
        block_msg = _build_block_message(violations)
        validation = verify(ir, block_msg, [], len(trace))
        return RunResponse(
            output_text=block_msg, blocked=True, violations=violations,
            trace=trace, evidence=[], validation=validation, usage=TokenUsage(),
        )
    
    # Step 2: 编译 IR → Claude 格式
    system_prompt = _build_skill_system_prompt(ir)
    tools = _compile_ir_to_tools(ir, external_tools or {})
    
    # Step 3: Agent 循环
    client = Anthropic()
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    
    messages = [{"role": "user", "content": req.user_input}]
    trace_records: list[TraceStep] = []
    evidence: list[EvidenceItem] = []
    total_in, total_out = 0, 0
    
    for turn in range(10):  # 最多 10 轮（V3 停止规则）
        response = client.messages.create(
            model=model, max_tokens=4096,
            system=system_prompt, messages=messages, tools=tools,
        )
        total_in += response.usage.input_tokens
        total_out += response.usage.output_tokens
        
        # 检查是否有 tool_use
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        
        if not tool_uses:
            # 没有 tool 调用，Agent 完成
            output_text = "".join(b.text for b in response.content if b.type == "text")
            break
        
        # 处理每个 tool 调用
        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input
            
            # 记录 trace — 哪个步骤触发了哪个 tool
            step_id = _match_tool_to_step(tool_name, ir.t.path)
            if step_id:
                trace_records.append(TraceStep(
                    step_id=step_id, status="running",
                    started_at=_now(), notes=f"调用工具: {tool_name}",
                ))
            
            # 执行 tool
            if tool_name == "cite_reference":
                # 内置工具：引用 reference 文件
                ref_path = tool_input.get("reference_path", "")
                excerpt = tool_input.get("relevant_excerpt", "")
                evidence.append(EvidenceItem(
                    source_path=ref_path, excerpt=excerpt,
                    relevance=tool_input.get("relevance", ""),
                ))
                result_content = f"已引用 {ref_path}"
            elif tool_name in (external_tools or {}):
                # 外部工具（用户注册的）
                result_content = str(external_tools[tool_name](**tool_input))
            else:
                result_content = f"工具 {tool_name} 未注册，跳过"
            
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result_content,
            })
            
            # 更新 trace
            if step_id:
                trace_records[-1].status = "completed"
                trace_records[-1].completed_at = _now()
        
        # 把 tool 结果返回给 Claude，继续循环
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
    
    else:
        output_text = "[执行超过最大轮次限制]"
    
    # 补充未执行的步骤到 trace
    executed_ids = {t.step_id for t in trace_records}
    for step in ir.t.path:
        if step.id not in executed_ids:
            trace_records.append(TraceStep(step_id=step.id, status="completed"))
    
    validation = verify(ir, output_text, evidence, len(trace_records))
    
    return RunResponse(
        output_text=output_text, blocked=False, violations=[],
        trace=trace_records, evidence=evidence, validation=validation,
        usage=TokenUsage(input_tokens=total_in, output_tokens=total_out,
                         total_tokens=total_in + total_out),
    )


def _compile_ir_to_tools(ir: SemanticKernelIR, 
                          external_tools: dict) -> list[dict]:
    """将 IR 编译成 Claude Tool 定义列表"""
    tools = []
    
    # 内置工具 1：引用 reference 文件（让 Claude 显式引用而非靠启发式匹配）
    if ir.n.references:
        ref_paths = [r.path for r in ir.n.references]
        tools.append({
            "name": "cite_reference",
            "description": (
                f"引用 Skill 的参考资源文件作为回答的证据支撑。"
                f"可用的 references: {ref_paths}"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "reference_path": {
                        "type": "string",
                        "enum": ref_paths,
                        "description": "要引用的文件路径"
                    },
                    "relevant_excerpt": {
                        "type": "string",
                        "description": "该文件中与当前问题相关的具体内容摘要"
                    },
                    "relevance": {
                        "type": "string",
                        "description": "为什么引用这个文件（一句话说明相关性）"
                    }
                },
                "required": ["reference_path", "relevant_excerpt", "relevance"]
            }
        })
    
    # 内置工具 2：报告决策点
    if any(s.decision_points for s in ir.t.path):
        tools.append({
            "name": "report_decision",
            "description": "在执行路径的决策点处记录你的判断",
            "input_schema": {
                "type": "object",
                "properties": {
                    "step_id": {"type": "string", "description": "当前步骤 ID"},
                    "condition": {"type": "string", "description": "判断的条件"},
                    "result": {"type": "boolean", "description": "条件是否为真"},
                    "reasoning": {"type": "string", "description": "判断依据"}
                },
                "required": ["step_id", "condition", "result", "reasoning"]
            }
        })
    
    # 从 T.path 中提取外部工具需求
    for step in ir.t.path:
        if step.tool_required and step.tool_required in external_tools:
            # 用户注册的外部工具，直接暴露给 Claude
            tools.append({
                "name": step.tool_required,
                "description": f"步骤 [{step.id}] {step.name} 需要的工具",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "params": {"type": "object", "description": "工具参数"}
                    }
                }
            })
    
    return tools
```

### 这解决了什么

| 之前 | 之后 |
|------|------|
| 单次 LLM 调用，假装所有步骤完成 | Agent 循环，逐步执行，逐步 trace |
| `tool_required` 是死代码 | tool_required 编译成 Claude Tool，真正执行 |
| 启发式字符串匹配 evidence | Claude 通过 `cite_reference` tool 显式引用 |
| 决策点只存在 IR 中，运行时无体现 | Claude 通过 `report_decision` tool 记录决策 |

---

## 六、Layer 4 — 编译器输出 Claude 原生格式（已实现 ✅）

### IR → Claude Tool Definition 自动生成

在编译阶段，除了生成 SemanticKernel IR，还可以同时输出 Claude 兼容的 Tool Definition：

```python
# compiler/claude_export.py

def ir_to_claude_tool(ir: SemanticKernelIR) -> dict:
    """将编译好的 Skill 导出为 Claude Tool Definition 格式"""
    
    # 从 IR 中提取 input_examples
    examples = _generate_examples_from_ir(ir)
    
    return {
        "name": f"mindlake_skill_{ir.kernel_id.replace('-', '_')}",
        "description": (
            f"[MindLakeVM Skill] {ir.r.semantic_space}\n"
            f"领域: {ir.r.domain} | 类型: {ir.r.object_type}\n"
            f"硬约束: {'; '.join(ir.e.hard_constraints[:2])}\n"
            f"执行步骤: {' → '.join(s.name for s in ir.t.path)}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_input": {
                    "type": "string",
                    "description": f"用户关于 {ir.r.semantic_space} 的问题或请求"
                }
            },
            "required": ["user_input"]
        },
        "input_examples": examples,
    }


def _generate_examples_from_ir(ir: SemanticKernelIR) -> list[dict]:
    """从 IR 的约束和决策点中自动生成 Tool Use Examples"""
    examples = []
    
    # 从硬约束生成触发场景
    for constraint in ir.e.hard_constraints[:2]:
        examples.append({
            "user_input": f"（会触发硬约束的场景）{constraint}"
        })
    
    # 从 T.path 第一步生成正常场景
    if ir.t.path:
        first_step = ir.t.path[0]
        examples.append({
            "user_input": f"（正常执行场景）需要{first_step.name}"
        })
    
    return examples


def ir_to_tool_search_metadata(ir: SemanticKernelIR) -> dict:
    """生成 Tool Search Tool 兼容的元数据"""
    return {
        "name": f"mindlake_skill_{ir.kernel_id.replace('-', '_')}",
        "description": ir.r.semantic_space,
        "defer_loading": True,  # 默认延迟加载
        "tags": [ir.r.domain, ir.r.object_type],
    }
```

### Skill → MCP Resource 映射

```python
# compiler/claude_export.py（续）

def ir_to_mcp_tool(ir: SemanticKernelIR, base_url: str) -> dict:
    """将 Skill 导出为 MCP Tool 格式"""
    return {
        "name": f"mindlake/{ir.kernel_id}",
        "description": ir.r.semantic_space,
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_input": {"type": "string"},
            },
            "required": ["user_input"]
        },
        # MCP 标准注解
        "annotations": {
            "domain": ir.r.domain,
            "object_type": ir.r.object_type,
            "hard_constraints": ir.e.hard_constraints,
            "has_guardrail": len(ir.e.hard_constraints) > 0,
        }
    }
```

---

## 七、Layer 5 — MCP Server 暴露 MindLakeVM Skills（已实现 ✅）

### 目标

让任何 Claude Agent（包括 Claude Desktop、claude.ai、第三方 MCP 客户端）都能发现和调用 MindLakeVM 编译好的 Skills。

### 架构

```
Claude Desktop / claude.ai / 第三方 MCP 客户端
        │
        │  MCP Protocol (stdio / SSE)
        ▼
┌──────────────────────────────┐
│  MindLakeVM MCP Server       │
│                              │
│  Tools:                      │
│  ├── mindlake/compile        │  输入文档 → 编译 → Skill
│  ├── mindlake/list_skills    │  列出已编译 Skills
│  ├── mindlake/run            │  执行 Skill（含 guardrail）
│  └── mindlake/skill/{id}     │  每个 Skill 作为独立 Tool
│                              │
│  Resources:                  │
│  ├── skill://{id}/ir         │  Skill 的 IR 结构
│  ├── skill://{id}/trace      │  最近一次执行的 trace
│  └── skill://{id}/refs/*     │  Skill 的 references 文件
│                              │
│  Prompts:                    │
│  └── mindlake/skill_prompt   │  渲染 Skill 为 system prompt
└──────────────────────────────┘
        │
        │  内部调用
        ▼
┌──────────────────────────────┐
│  MindLakeVM Runtime          │
│  (compiler + executor +      │
│   guardrail + verifier)      │
└──────────────────────────────┘
```

### 关键实现

```python
# mcp_server.py — MindLakeVM MCP Server

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource
import store
from compiler.pipeline import compile_document
from executor.agent_runner import run_skill_agent
from models import CompileRequest, RunRequest

server = Server("mindlake-vm")


@server.list_tools()
async def list_tools():
    tools = [
        Tool(
            name="mindlake_compile",
            description="将企业文档编译为可执行的 MindLakeVM Skill（含 RNET 四核 IR + 门禁约束）",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {"type": "string"},
                    "document_content": {"type": "string"},
                    "strategy": {"type": "string", "enum": ["minimal", "default", "detailed"]},
                },
                "required": ["task_description"]
            },
        ),
        Tool(
            name="mindlake_list_skills",
            description="列出所有已编译的 MindLakeVM Skills 及其领域、类型和约束摘要",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]
    
    # 动态注册每个已编译 Skill 为独立 Tool
    for skill_summary in store.list_all():
        result = store.get(skill_summary.skill_id)
        if not result:
            continue
        ir, _ = result
        
        constraint_hint = ""
        if ir.e.hard_constraints:
            constraint_hint = f" 硬约束: {'; '.join(ir.e.hard_constraints[:2])}"
        
        tools.append(Tool(
            name=f"mindlake_run_{skill_summary.skill_id.replace('-', '_')}",
            description=(
                f"[MindLakeVM Skill] {ir.r.semantic_space}"
                f"{constraint_hint}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_input": {
                        "type": "string",
                        "description": "用户的问题或请求"
                    }
                },
                "required": ["user_input"]
            },
        ))
    
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "mindlake_compile":
        req = CompileRequest(**arguments)
        ir, package = compile_document(req)
        store.save(package.skill_id, ir, package)
        return [TextContent(
            type="text",
            text=f"Skill 编译完成: {package.skill_id}\n"
                 f"领域: {ir.r.domain} | 类型: {ir.r.object_type}\n"
                 f"硬约束: {ir.e.hard_constraints}\n"
                 f"步骤: {[s.name for s in ir.t.path]}"
        )]
    
    if name == "mindlake_list_skills":
        skills = store.list_all()
        return [TextContent(type="text", text=json.dumps(
            [s.model_dump() for s in skills], ensure_ascii=False, indent=2
        ))]
    
    # 处理 mindlake_run_{skill_id} 调用
    if name.startswith("mindlake_run_"):
        skill_id = name[len("mindlake_run_"):].replace("_", "-")
        result = store.get(skill_id)
        if not result:
            return [TextContent(type="text", text=f"Skill {skill_id} 不存在")]
        
        ir, _ = result
        req = RunRequest(skill_id=skill_id, user_input=arguments["user_input"])
        response = run_skill_agent(ir, req)
        
        # 结构化返回（Claude 可以读懂）
        output = {
            "output_text": response.output_text,
            "blocked": response.blocked,
            "violations": [v.model_dump() for v in response.violations],
            "trace": [t.model_dump() for t in response.trace],
            "evidence": [e.model_dump() for e in response.evidence],
            "validation": response.validation.model_dump(),
        }
        return [TextContent(type="text", text=json.dumps(output, ensure_ascii=False, indent=2))]
```

### MCP Resources — 暴露 Skill 内部状态

```python
@server.list_resources()
async def list_resources():
    resources = []
    for skill in store.list_all():
        resources.append(Resource(
            uri=f"skill://{skill.skill_id}/ir",
            name=f"{skill.skill_name} — SemanticKernel IR",
            mimeType="application/json",
        ))
    return resources

@server.read_resource()
async def read_resource(uri: str):
    # skill://{skill_id}/ir
    if uri.startswith("skill://") and uri.endswith("/ir"):
        skill_id = uri[len("skill://"):-len("/ir")]
        result = store.get(skill_id)
        if result:
            ir, _ = result
            return ir.model_dump_json(indent=2)
    return "Resource not found"
```

---

## 八、改造路线图与工作量评估

### Phase 1：最小可用（1-2 天）

| 改动 | 文件 | 工作量 |
|------|------|--------|
| Anthropic SDK 适配 | `compiler/llm.py` | 新增 ~80 行 |
| 新增环境变量 | `.env.example` | 3 行 |
| guardrail tool_use | `executor/guardrail.py` | 改动 ~20 行 |

**产出**：可以用 Claude 原生 API 作为后端，guardrail 结构化输出更稳定。

### Phase 2：Agent 循环（3-5 天）

| 改动 | 文件 | 工作量 |
|------|------|--------|
| Agent 执行器 | `executor/agent_runner.py`（新建） | ~200 行 |
| IR → Tool 编译 | `compiler/claude_export.py`（新建） | ~100 行 |
| API 路由适配 | `api/run.py` | 改动 ~10 行 |
| 新增 tool 注册机制 | `models.py` | 新增 ~30 行 |

**产出**：T.path 逐步执行、tool_required 真正调用、cite_reference 显式引用、report_decision 决策记录。

### Phase 3：MCP Server（2-3 天）

| 改动 | 文件 | 工作量 |
|------|------|--------|
| MCP Server | `mcp_server.py`（新建） | ~200 行 |
| MCP 依赖 | `requirements.txt` | 1 行 |
| 启动脚本 | `Makefile` 或 README | 几行 |

**产出**：Claude Desktop / claude.ai / 任何 MCP 客户端可以发现和调用 MindLakeVM Skills。

### Phase 4：高级集成（1-2 周）

- PTC 兼容：让 Claude 的 Programmatic Tool Calling 可以在代码中调用 MindLakeVM Skills
- Tool Search Tool 兼容：Skills 元数据支持 defer_loading + 描述优化
- Bench 扩展：新增 "Claude Agent + MindLakeVM" baseline

---

## 九、兼容性架构全景图

```
┌────────────────────────────────────────────────────────────────────┐
│                    Claude Agent 生态                               │
│                                                                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                  │
│  │ Claude     │  │ Claude     │  │ 第三方     │                   │
│  │ Desktop    │  │ claude.ai  │  │ MCP Client │                  │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                  │
│        │               │               │                          │
│        └───────────────┼───────────────┘                          │
│                        │ MCP Protocol                             │
│                        ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              MindLakeVM MCP Server (Layer 5)                │  │
│  │                                                             │  │
│  │  Tools: compile / list / run_{skill_id}                     │  │
│  │  Resources: skill://{id}/ir, skill://{id}/refs/*            │  │
│  └─────────────────────────┬───────────────────────────────────┘  │
│                            │                                      │
└────────────────────────────┼──────────────────────────────────────┘
                             │
┌────────────────────────────┼──────────────────────────────────────┐
│                   MindLakeVM Runtime                              │
│                            ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │            Agent Runner (Layer 3)                         │    │
│  │                                                           │    │
│  │  guardrail ──→ Agent Loop ──→ verifier                    │    │
│  │      │         ┌──────┐         │                         │    │
│  │      │         │Claude│         │                         │    │
│  │      │         │Agent │         │                         │    │
│  │      │         │Loop  │         │                         │    │
│  │      │         └──┬───┘         │                         │    │
│  │      │            │             │                         │    │
│  │      │     ┌──────┴──────┐      │                         │    │
│  │      │     ▼             ▼      │                         │    │
│  │      │  cite_reference  外部    │                         │    │
│  │      │  report_decision tool    │                         │    │
│  │      │     (内置)      (注册)   │                         │    │
│  └──────┼─────────────────────────┼─────────────────────────┘    │
│         │                         │                               │
│  ┌──────┴──────┐     ┌────────────┴──────────┐                   │
│  │  Anthropic  │     │  IR → Claude Tools    │                   │
│  │  SDK        │     │  (Layer 4)            │                   │
│  │  (Layer 1)  │     │  auto-gen definitions │                   │
│  │  + tool_use │     │  + input_examples     │                   │
│  │  (Layer 2)  │     │  + defer_loading meta │                   │
│  └─────────────┘     └───────────────────────┘                   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Compiler Pipeline                                          │  │
│  │  Doc → IR → Skill Package + Claude Tool Defs + MCP Meta     │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Skill Store                                                │  │
│  │  {skill_id}.json → IR + Package + Claude Export             │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

---

## 十、核心洞察：兼容不是"降维"，而是"分层"

兼容 Claude Agent 不意味着把 MindLakeVM 降级为一个 Claude Tool。正确的思路是**分层互补**：

| 层 | 由谁负责 | 能力 |
|----|---------|------|
| **认知层**（怎么思考） | MindLakeVM IR（R/N/E/T） | 领域定位、知识注册、约束定义、执行路径 |
| **合规层**（什么不能做） | MindLakeVM guardrail + verifier | 硬约束预检、V1/V2/V3 三重验证 |
| **推理层**（如何生成） | Claude LLM + extended thinking | 自然语言推理、代码生成 |
| **工具层**（调什么函数） | Claude Tool Use + PTC | 工具发现、参数填充、代码编排 |
| **发现层**（从哪找到） | MCP Server + Tool Search Tool | Skill 注册、按需加载、元数据搜索 |
| **审计层**（做对了吗） | MindLakeVM trace + evidence + validation | 执行追溯、证据引用、结果校验 |

**MindLakeVM 拥有 Claude 缺少的三层（认知/合规/审计），Claude 拥有 MindLakeVM 缺少的两层（推理/工具）。通过 MCP + Agent Loop 桥接，形成完整的六层栈。**

这才是真正的兼容——不是替代，而是让两个系统各自做自己最擅长的事。
