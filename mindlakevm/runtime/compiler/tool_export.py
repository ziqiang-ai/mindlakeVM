"""
Layer 4: IR → Claude Tool Definition 导出器

将编译好的 MindLakeVM Skill（SemanticKernelIR）导出为：
1. Claude Tool Definition（OpenAI function calling 格式，兼容 OpenRouter）
2. Tool Use Examples（从 IR 的约束和决策点中自动生成）
3. Tool Search Metadata（Claude Tool Search Tool 兼容格式）
4. MCP Tool Definition（为 Layer 5 MCP Server 准备）

用途：
- 外部 Claude Agent 可以直接使用导出的 tool definition 来调用 MindLakeVM Skills
- Tool Use Examples 帮助 Claude 更准确地判断何时该调用此 Skill
- Tool Search Metadata 支持 Claude 从大量 tools 中高效检索
"""
from __future__ import annotations
from models import SemanticKernelIR


# ── 1. Claude Tool Definition ────────────────────────────────────────────────

def ir_to_claude_tool(ir: SemanticKernelIR, include_examples: bool = True) -> dict:
    """将编译好的 Skill 导出为 Claude Tool Definition 格式（OpenAI function calling 兼容）。

    生成的 tool 可被外部 Claude Agent 直接使用：
    - name: mindlake_skill_{kernel_id}
    - description: 包含语义空间、领域、约束、执行路径摘要
    - input_schema: user_input 字符串
    - 可选: examples 帮助 Claude 判断何时调用
    """
    name = f"mindlake_skill_{ir.kernel_id.replace('-', '_')}"

    # 构建丰富的描述，帮助 Claude 理解何时应调用此 tool
    desc_parts = [
        f"[MindLakeVM Skill] {ir.r.semantic_space}",
        f"领域: {ir.r.domain} | 类型: {ir.r.object_type}",
    ]
    if ir.e.hard_constraints:
        constraints_preview = "; ".join(ir.e.hard_constraints[:3])
        desc_parts.append(f"硬约束: {constraints_preview}")
    if ir.t.path:
        path_preview = " → ".join(s.name for s in ir.t.path[:5])
        if len(ir.t.path) > 5:
            path_preview += f" …（共 {len(ir.t.path)} 步）"
        desc_parts.append(f"执行路径: {path_preview}")
    if ir.e.target_entropy:
        desc_parts.append(f"目标: {ir.e.target_entropy}")

    tool_def = {
        "type": "function",
        "function": {
            "name": name,
            "description": "\n".join(desc_parts),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_input": {
                        "type": "string",
                        "description": f"用户关于「{ir.r.semantic_space}」的问题或请求"
                    }
                },
                "required": ["user_input"]
            }
        }
    }

    if include_examples:
        examples = generate_tool_examples(ir)
        if examples:
            tool_def["function"]["examples"] = examples

    return tool_def


# ── 2. Tool Use Examples 生成 ────────────────────────────────────────────────

def generate_tool_examples(ir: SemanticKernelIR) -> list[dict]:
    """从 IR 中自动生成 Tool Use Examples。

    Claude Advanced Tool Use 的 Tool Use Examples 功能：
    通过提供输入/输出示例，帮助 Claude 更准确地判断何时调用工具以及如何构造参数。

    生成策略：
    1. 从硬约束生成"应被拦截"的反面场景
    2. 从决策点生成条件判断场景
    3. 从执行路径第一步生成正常执行场景
    4. 从 semantic_space 生成通用场景
    """
    examples: list[dict] = []

    # 策略 1: 从硬约束生成触发/非触发场景对
    for i, constraint in enumerate(ir.e.hard_constraints[:2]):
        # 触发场景：直接请求被禁止的操作
        examples.append({
            "input": {"user_input": f"我需要直接执行：{constraint}"},
            "expected_behavior": "Skill 将通过 guardrail 拦截此请求并说明触发了哪条硬约束",
            "tags": ["guardrail", "hard_constraint"]
        })

    # 策略 2: 从决策点生成条件判断场景
    for step in ir.t.path:
        for dp in step.decision_points[:1]:
            examples.append({
                "input": {"user_input": f"当{dp.condition}时应该怎么做？"},
                "expected_behavior": (
                    f"Skill 将在步骤 [{step.id}] 评估此决策点，"
                    f"如果成立则「{dp.if_true}」，"
                    f"否则「{dp.if_false or '继续下一步'}」"
                ),
                "tags": ["decision_point", step.id]
            })
        if len(examples) >= 5:
            break

    # 策略 3: 从执行路径生成正常场景
    if ir.t.path:
        first_step = ir.t.path[0]
        examples.append({
            "input": {"user_input": f"请帮我处理：{first_step.name}"},
            "expected_behavior": (
                f"Skill 将按执行路径逐步处理，从 [{first_step.id}] {first_step.name} 开始"
            ),
            "tags": ["normal_execution"]
        })

    # 策略 4: 通用场景
    examples.append({
        "input": {"user_input": f"关于{ir.r.semantic_space}，我有个问题"},
        "expected_behavior": (
            f"Skill 将按 {ir.r.domain} 领域的 {ir.r.object_type} 流程处理，"
            f"输出格式为 {ir.e.format}"
        ),
        "tags": ["generic"]
    })

    return examples


# ── 3. Tool Search Metadata ──────────────────────────────────────────────────

def ir_to_tool_search_metadata(ir: SemanticKernelIR) -> dict:
    """生成 Claude Tool Search Tool 兼容的元数据。

    Tool Search Tool 是 Claude Advanced Tool Use 的特性：
    当 Agent 可用工具很多时，先用 Tool Search Tool 检索相关工具，
    再把检索到的工具动态注入到下次请求中。

    返回格式兼容 Tool Search Tool 的 index entry。
    """
    # 构建搜索关键词：领域 + 类型 + 约束关键词 + 步骤名
    keywords = [ir.r.domain, ir.r.object_type, ir.r.semantic_space]
    keywords.extend(ir.e.hard_constraints[:3])
    keywords.extend(s.name for s in ir.t.path[:5])

    return {
        "name": f"mindlake_skill_{ir.kernel_id.replace('-', '_')}",
        "description": ir.r.semantic_space,
        "keywords": keywords,
        "domain": ir.r.domain,
        "object_type": ir.r.object_type,
        "has_guardrail": len(ir.e.hard_constraints) > 0,
        "step_count": len(ir.t.path),
        "defer_loading": True,
    }


# ── 4. MCP Tool Definition ──────────────────────────────────────────────────

def ir_to_mcp_tool(ir: SemanticKernelIR, base_url: str = "") -> dict:
    """将 Skill 导出为 MCP Tool 格式（为 Layer 5 MCP Server 准备）。

    MCP (Model-Client Protocol) 是 Claude 生态的工具发现和调用协议。
    此函数生成的格式兼容 MCP Python SDK 的 Tool 类型。
    """
    return {
        "name": f"mindlake/{ir.kernel_id}",
        "description": (
            f"{ir.r.semantic_space}\n"
            f"领域: {ir.r.domain} | 类型: {ir.r.object_type}\n"
            f"步骤数: {len(ir.t.path)} | 硬约束数: {len(ir.e.hard_constraints)}"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_input": {
                    "type": "string",
                    "description": f"用户关于「{ir.r.semantic_space}」的问题或请求"
                }
            },
            "required": ["user_input"]
        },
        "annotations": {
            "domain": ir.r.domain,
            "object_type": ir.r.object_type,
            "kernel_id": ir.kernel_id,
            "hard_constraints": ir.e.hard_constraints,
            "has_guardrail": len(ir.e.hard_constraints) > 0,
            "execution_path": [s.id for s in ir.t.path],
        }
    }


# ── 5. 批量导出 ─────────────────────────────────────────────────────────────

def export_all_tools(
    skills: list[SemanticKernelIR],
    format: str = "claude",
    base_url: str = "",
    include_examples: bool = True,
) -> list[dict]:
    """批量导出所有 Skills 为指定格式的 Tool 定义。

    format:
    - "claude": OpenAI function calling 格式（兼容 OpenRouter + Claude）
    - "mcp": MCP Tool 格式
    - "search": Tool Search Metadata 格式
    """
    exporters = {
        "claude": lambda ir: ir_to_claude_tool(ir, include_examples=include_examples),
        "mcp": lambda ir: ir_to_mcp_tool(ir, base_url=base_url),
        "search": ir_to_tool_search_metadata,
    }
    exporter = exporters.get(format, exporters["claude"])
    return [exporter(ir) for ir in skills]


# ── 6. 完整导出包 ────────────────────────────────────────────────────────────

def export_skill_bundle(ir: SemanticKernelIR, base_url: str = "") -> dict:
    """导出一个 Skill 的完整工具包，包含所有格式。

    返回结构：
    {
        "skill_id": "...",
        "claude_tool": { ... },       # 可直接用于 Claude Agent
        "mcp_tool": { ... },           # 可注册到 MCP Server
        "search_metadata": { ... },    # 可索引到 Tool Search
        "examples": [ ... ],           # Tool Use Examples
    }
    """
    return {
        "skill_id": ir.kernel_id,
        "domain": ir.r.domain,
        "object_type": ir.r.object_type,
        "semantic_space": ir.r.semantic_space,
        "claude_tool": ir_to_claude_tool(ir, include_examples=True),
        "mcp_tool": ir_to_mcp_tool(ir, base_url=base_url),
        "search_metadata": ir_to_tool_search_metadata(ir),
        "examples": generate_tool_examples(ir),
    }
